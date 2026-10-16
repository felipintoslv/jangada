#!/usr/bin/env bash
# Testa, em repositórios temporários, o que chega à cópia instalada: o
# jangada-sistema-update só aplica commits novos da origem com confirmação e,
# com allowed_signers, só os assinados; o install.sh recusa a cópia de
# trabalho e os worktrees. pacman, checkupdates, sudo, paru e tmux são
# substituídos por scripts falsos.
#
# Uso: testes/update.sh
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Nada da configuração do git do usuário (assinatura, ganchos) entra no teste.
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_NOSYSTEM=1
: >"$GIT_CONFIG_GLOBAL"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/home/.config" XDG_STATE_HOME="$tmp/home/.local/state"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_STATE_HOME"
unset HYPRLAND_INSTANCE_SIGNATURE JANGADA_SESSAO JANGADA_REPO JANGADA_SIMULAR

# Comandos do sistema falsos: registram a chamada e não alteram nada.
falsos="$tmp/falsos"; mkdir -p "$falsos"
registro="$tmp/chamadas"
cat >"$falsos/pacman" <<EOF
#!/bin/sh
echo "pacman \$*" >>"$registro"
case "\$1" in -Q*) exit 1 ;; esac
exit 0
EOF
cat >"$falsos/sudo" <<EOF
#!/bin/sh
echo "sudo \$*" >>"$registro"
exec "\$@"
EOF
cat >"$falsos/checkupdates" <<'EOF'
#!/bin/sh
exit 2
EOF
cat >"$falsos/paru" <<EOF
#!/bin/sh
echo "paru \$*" >>"$registro"
exit 0
EOF
cat >"$falsos/yay" <<EOF
#!/bin/sh
echo "yay \$*" >>"$registro"
exit 0
EOF
cat >"$falsos/tmux" <<'EOF'
#!/bin/sh
for a in "$@"; do [ "$a" = has-session ] && exit 1; done
exit 0
EOF
chmod +x "$falsos"/*
export PATH="$falsos:$PATH"

# Origem (a cópia de trabalho) com o bin/ atual e sem migrações; a cópia
# instalada é um clone dela, como na máquina.
origem="$tmp/origem"; instalado="$tmp/instalado"
mkdir -p "$origem/migrations"
cp -r "$repo_jangada/bin" "$origem/"
echo "migrações" >"$origem/migrations/README.md"
git -C "$origem" init --quiet -b main
git -C "$origem" add -A
git -C "$origem" commit --quiet -m "feat(base): início"
git clone --quiet "$origem" "$instalado"
export JANGADA_PATH="$instalado"

marca="$HOME/migracao-nova"
cat >"$origem/migrations/900-teste.sh" <<'EOF'
touch "$HOME/migracao-nova"
EOF
git -C "$origem" add -A
git -C "$origem" commit --quiet -m $'feat(teste): migração \e[2Jnova'
novo="$(git -C "$origem" rev-parse HEAD)"
antes="$(git -C "$instalado" rev-parse HEAD)"

atualizar() { (cd "$tmp" && "$instalado/bin/jangada-sistema-update") >"$tmp/saida" 2>&1; rc=$?; }
head_instalado() { git -C "$instalado" rev-parse HEAD; }

echo "== jangada-sistema-update"

atualizar <<<n
conferir "resposta n: termina sem erro ($rc)" test "$rc" -eq 0
conferir "resposta n: cópia instalada não avança" test "$(head_instalado)" = "$antes"
conferir "resposta n: migração nova não roda" test ! -e "$marca"
conferir "resposta n: pacman -Syu roda mesmo assim" grep -q 'sudo pacman -Syu' "$registro"
conferir "mostra o commit novo" grep -q 'migração \[2Jnova' "$tmp/saida"
conferir "assunto sem o caractere ESC" bash -c '! grep -q $'"'"'\e'"'"' "$1"' _ "$tmp/saida"
conferir "destaca a mudança em migrations/" grep -q '^   migrations/900-teste.sh' "$tmp/saida"
conferir "avisa que não aplicou" grep -q 'não aplicadas' "$tmp/saida"
conferir "checkupdates sem atualização não é falha" bash -c '! grep -q "checkupdates falhou" "$1"' _ "$tmp/saida"

atualizar </dev/null
conferir "sem terminal: termina sem erro ($rc)" test "$rc" -eq 0
conferir "sem terminal: cópia instalada não avança" test "$(head_instalado)" = "$antes"
conferir "sem terminal: migração nova não roda" test ! -e "$marca"

atualizar <<<s
conferir "resposta s: termina sem erro ($rc)" test "$rc" -eq 0
conferir "resposta s: cópia instalada avança" test "$(head_instalado)" = "$novo"
conferir "resposta s: migração nova roda" test -e "$marca"

# A origem reescrita (não avança em linha reta) é recusada como antes.
git -C "$origem" commit --quiet --amend -m "fix(teste): reescrito"
atualizar <<<s
conferir "origem reescrita: termina sem erro ($rc)" test "$rc" -eq 0
conferir "origem reescrita: cópia instalada não muda" test "$(head_instalado)" = "$novo"
conferir "origem reescrita: explica a recusa" grep -q 'não avança em linha reta' "$tmp/saida"


echo "== assinaturas"

# Com allowed_signers, a cópia instalada só avança por commits assinados. A
# assinatura é feita aqui com o git; quem assina no dia a dia é o Core.
# A origem foi reescrita acima: volta ao commit que a cópia instalada tem.
git -C "$origem" reset --quiet --hard "$novo"
atualizar <<<s
mkdir -p "$HOME/.ssh" "$XDG_CONFIG_HOME/jangada"
ssh-keygen -q -t ed25519 -N '' -C t -f "$HOME/.ssh/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C outra -f "$tmp/outra"
printf 't@t namespaces="git" %s\n' "$(cat "$HOME/.ssh/id_ed25519.pub")" >"$XDG_CONFIG_HOME/jangada/allowed_signers"
assinatura() { git -C "$origem" -c gpg.ssh.allowedSignersFile="$XDG_CONFIG_HOME/jangada/allowed_signers" log -1 --format=%G? "$1"; }

echo c1 >"$origem/c1.txt"
git -C "$origem" add c1.txt
git -C "$origem" commit --quiet -m "feat(teste): sem assinatura"
antes_ass="$(head_instalado)"
atualizar <<<s
conferir "sem assinatura: a cópia instalada não avança" test "$(head_instalado)" = "$antes_ass"
conferir "sem assinatura: diz o commit" \
  bash -c 'grep -q "sem assinatura válida" "$1" && grep -q "feat(teste): sem assinatura" "$1"' _ "$tmp/saida"

git -C "$origem" -c gpg.format=ssh -c user.signingkey="$HOME/.ssh/id_ed25519" \
  commit --quiet --amend --no-edit -S
conferir "assinado: o commit tem assinatura válida" [ "$(assinatura HEAD)" = G ]
c1="$(git -C "$origem" rev-parse HEAD)"
atualizar <<<s
conferir "assinado: a cópia instalada avança" test "$(head_instalado)" = "$c1"

echo c2 >"$origem/c2.txt"
git -C "$origem" add c2.txt
git -C "$origem" -c gpg.format=ssh -c user.signingkey="$tmp/outra" commit --quiet -S -m "feat(teste): outra chave"
atualizar <<<s
conferir "outra chave: a cópia instalada não avança" test "$(head_instalado)" = "$c1"
rm -f "$XDG_CONFIG_HOME/jangada/allowed_signers"
git -C "$origem" reset --quiet --hard "$c1"


echo "== install.sh só da cópia instalada"

# Cópia só com o install.sh, a lib, a configuração e uma etapa que só marca
# que rodou.
inst="$tmp/inst"; mkdir -p "$inst/install" "$inst/bin"
cp "$repo_jangada/install.sh" "$inst/"
echo 'touch "$HOME/etapa-rodou"' >"$inst/install/00-teste.sh"
cp "$repo_jangada/install/lib.sh" "$inst/install/"
cp "$repo_jangada/bin/jangada-shell-config" "$inst/bin/"
git -C "$inst" init --quiet -b main
git -C "$inst" add -A
git -C "$inst" commit --quiet -m "feat(base): instalação"
instalar() { env -u JANGADA_PATH "$@" >"$tmp/saida" 2>&1; }
mkdir -p "$XDG_CONFIG_HOME/jangada"

instalar "$inst/install.sh"; rc=$?
conferir "instala de um clone comum ($rc)" test "$rc" -eq 0
conferir "a etapa rodou" test -e "$HOME/etapa-rodou"
rm -f "$HOME/etapa-rodou"

printf 'JANGADA_REPO=%s\n' "$inst" >"$XDG_CONFIG_HOME/jangada/jangada.conf"
instalar "$inst/install.sh"; rc=$?
conferir "recusa a cópia de trabalho ($rc)" test "$rc" -ne 0
conferir "diz por que recusou" grep -q 'cópia de trabalho (JANGADA_REPO)' "$tmp/saida"
conferir "nenhuma etapa rodou" test ! -e "$HOME/etapa-rodou"
instalar env JANGADA_SIMULAR=1 "$inst/install.sh"; rc=$?
conferir "simula na cópia de trabalho ($rc)" test "$rc" -eq 0
conferir "a simulação avisa" grep -q 'só a simulação roda daqui' "$tmp/saida"
rm -f "$XDG_CONFIG_HOME/jangada/jangada.conf"

git -C "$inst" worktree add --quiet -b agente/inst "$tmp/inst-wt" main
instalar "$tmp/inst-wt/install.sh"; rc=$?
conferir "recusa um worktree ($rc)" test "$rc" -ne 0

mkdir -p "$HOME/.local/share/jangada-worktrees"
git clone --quiet "$inst" "$HOME/.local/share/jangada-worktrees/copia"
instalar "$HOME/.local/share/jangada-worktrees/copia/install.sh"; rc=$?
conferir "recusa um clone em JANGADA_WORKTREES ($rc)" test "$rc" -ne 0

if ((falhas)); then
  echo "--- última saída"; cat "$tmp/saida"
  echo "$falhas falha(s)"
  exit 1
fi
echo "tudo certo"
