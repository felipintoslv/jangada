#!/usr/bin/env bash
# Testa, em repositórios temporários, o que chega à cópia instalada: o
# jangada-update só aplica commits novos da origem com confirmação e, com
# allowed_signers, só os assinados, que o jangada-assinar assina; o
# jangada-agente-fim --integrar não atualiza a cópia instalada nem roda o git
# com fsmonitor ou ganchos do repositório do agente; o install.sh recusa a
# cópia de trabalho e os worktrees. pacman, checkupdates,
# sudo, paru e tmux são substituídos por scripts falsos.
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

atualizar() { (cd "$tmp" && "$instalado/bin/jangada-update") >"$tmp/saida" 2>&1; rc=$?; }
head_instalado() { git -C "$instalado" rev-parse HEAD; }

echo "== jangada-update"

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

echo "== jangada-agente-fim --integrar"

# Sessão de agente num worktree da origem, com um commit a integrar.
git -C "$origem" reset --quiet --hard "$novo"
# O caminho é o que o jangada-agente cria: $JANGADA_WORKTREES/REPO/NOME.
wt="$HOME/.local/share/jangada-worktrees/origem/x"
git -C "$origem" worktree add --quiet -b agente/x "$wt" main
echo "tarefa" >"$wt/tarefa.txt"
git -C "$wt" add tarefa.txt
git -C "$wt" commit --quiet -m "feat(teste): tarefa"
mkdir -p "$XDG_STATE_HOME/jangada/agentes"
jq -n --arg w "$wt" --arg r "$origem" \
  '{worktree: $w, ramo: "agente/x", base: "main", raiz: $r, estado: "concluido"}' \
  >"$XDG_STATE_HOME/jangada/agentes/x.json"
git -C "$instalado" fetch --quiet origin
antes_fim="$(head_instalado)"

# O que o agente poderia gravar no .git comum: fsmonitor e ganchos.
alerta="$tmp/executou-codigo-do-agente"
printf '#!/bin/sh\ntouch "%s"\n' "$alerta" >"$tmp/fsmonitor.sh"
mkdir -p "$tmp/ganchos"
for h in pre-merge-commit post-merge post-checkout reference-transaction; do
  cp "$tmp/fsmonitor.sh" "$tmp/ganchos/$h"
done
chmod +x "$tmp/fsmonitor.sh" "$tmp/ganchos"/*
git -C "$origem" config core.fsmonitor "$tmp/fsmonitor.sh"
git -C "$origem" config core.hooksPath "$tmp/ganchos"

printf 's\n' | (cd "$tmp" && "$repo_jangada/bin/jangada-agente-fim" --integrar x) >"$tmp/saida" 2>&1
rc=$?
git -C "$origem" config --unset core.fsmonitor
git -C "$origem" config --unset core.hooksPath
conferir "integra sem erro ($rc)" test "$rc" -eq 0
conferir "ramo integrado na origem" grep -q 'feat(teste): tarefa' <(git -C "$origem" log --oneline main)
conferir "ramo apagado depois da integração" test -z "$(git -C "$origem" branch --list agente/x)"
conferir "worktree removido" test ! -d "$wt"
conferir "cópia instalada não é atualizada" test "$(head_instalado)" = "$antes_fim"
conferir "pede para rodar jangada-update" grep -q 'rode jangada-update' "$tmp/saida"
conferir "fsmonitor e ganchos do repositório não rodam" test ! -e "$alerta"

echo "== assinaturas"

# A cópia instalada alcança a origem antes de as assinaturas valerem; o que
# já foi enviado a um remoto (o GitHub, na máquina) não é reescrito.
atualizar <<<s
remoto="$tmp/remoto.git"
git init --quiet --bare "$remoto"
git -C "$origem" remote add github "$remoto"
git -C "$origem" push --quiet -u github main 2>/dev/null
mkdir -p "$HOME/.ssh" "$XDG_CONFIG_HOME/jangada"
ssh-keygen -q -t ed25519 -N '' -C t -f "$HOME/.ssh/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C outra -f "$tmp/outra"
printf 't@t namespaces="git" %s\n' "$(cat "$HOME/.ssh/id_ed25519.pub")" >"$XDG_CONFIG_HOME/jangada/allowed_signers"
assinar() { (cd "$tmp" && "$repo_jangada/bin/jangada-assinar" "$origem") >"$tmp/saida" 2>&1; rc=$?; }
assinatura() { git -C "$origem" -c gpg.ssh.allowedSignersFile="$XDG_CONFIG_HOME/jangada/allowed_signers" log -1 --format=%G? "$1"; }

echo c1 >"$origem/c1.txt"
git -C "$origem" add c1.txt
git -C "$origem" commit --quiet -m "feat(teste): sem assinatura"
antes_ass="$(head_instalado)"
atualizar <<<s
conferir "sem assinatura: a cópia instalada não avança" test "$(head_instalado)" = "$antes_ass"
conferir "sem assinatura: diz o commit e o jangada-assinar" \
  bash -c 'grep -q "sem assinatura válida" "$1" && grep -q "feat(teste): sem assinatura" "$1"' _ "$tmp/saida"

assinar </dev/null
conferir "assinar sem terminal: não assina ($rc)" [ "$rc" -ne 0 ]
conferir "assinar sem terminal: o commit segue sem assinatura" [ "$(assinatura HEAD)" != G ]
assinar <<<s
conferir "assinar: termina sem erro ($rc)" [ "$rc" -eq 0 ]
conferir "assinar: mostra o commit" grep -q "feat(teste): sem assinatura" "$tmp/saida"
conferir "assinar: o commit tem assinatura válida" [ "$(assinatura HEAD)" = G ]
conferir "assinar: o já enviado não muda" [ "$(git -C "$origem" rev-parse "main@{upstream}")" = "$(git -C "$remoto" rev-parse main)" ]
c1="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "assinar de novo: nada a assinar" grep -q "nada a assinar" "$tmp/saida"
atualizar <<<s
conferir "assinado: a cópia instalada avança" test "$(head_instalado)" = "$c1"

# Assinado por uma chave fora do allowed_signers vale como sem assinatura, e
# o jangada-assinar só reescreve dali em diante.
echo c2 >"$origem/c2.txt"
git -C "$origem" add c2.txt
git -C "$origem" -c gpg.format=ssh -c user.signingkey="$tmp/outra" commit --quiet -S -m "feat(teste): outra chave"
atualizar <<<s
conferir "outra chave: a cópia instalada não avança" test "$(head_instalado)" = "$c1"
assinar <<<s
conferir "outra chave: assinar só reescreve o commit dela" \
  bash -c '[ "$(git -C "$1" rev-parse HEAD^)" = "$2" ] && ! grep -q "feat(teste): sem assinatura" "$3"' _ "$origem" "$c1" "$tmp/saida"
atualizar <<<s
conferir "outra chave, depois de assinar: a cópia instalada avança" \
  test "$(head_instalado)" = "$(git -C "$origem" rev-parse HEAD)"

# O gpg.ssh.program do repositório não roda na assinatura nem na conferência.
printf '#!/bin/sh\ntouch "%s"\nexit 1\n' "$alerta" >"$tmp/programa.sh"
chmod +x "$tmp/programa.sh"
git -C "$origem" config gpg.ssh.program "$tmp/programa.sh"
git -C "$instalado" config gpg.ssh.program "$tmp/programa.sh"
echo c3 >"$origem/c3.txt"
git -C "$origem" add c3.txt
git -C "$origem" commit --quiet -m "feat(teste): terceiro"
assinar <<<s
atualizar <<<s
conferir "gpg.ssh.program do repositório: assina e aplica" test "$(head_instalado)" = "$(git -C "$origem" rev-parse HEAD)"
conferir "gpg.ssh.program do repositório: não roda" test ! -e "$alerta"
git -C "$origem" config --unset gpg.ssh.program
git -C "$instalado" config --unset gpg.ssh.program

# Sem a chave (como no isolamento, com o ~/.ssh oculto), recusa com o motivo.
mv "$HOME/.ssh" "$HOME/.ssh-fora"
echo c4 >"$origem/c4.txt"
git -C "$origem" add c4.txt
git -C "$origem" commit --quiet -m "feat(teste): sem chave"
assinar <<<s
conferir "sem a chave: recusa ($rc)" [ "$rc" -ne 0 ]
conferir "sem a chave: indica o terminal comum" grep -q "terminal comum" "$tmp/saida"
mv "$HOME/.ssh-fora" "$HOME/.ssh"
git -C "$origem" reset --quiet --hard HEAD^
rm -f "$XDG_CONFIG_HOME/jangada/allowed_signers"

echo "== install.sh só da cópia instalada"

# Cópia só com o install.sh, a lib, a configuração e uma etapa que só marca
# que rodou.
inst="$tmp/inst"; mkdir -p "$inst/install" "$inst/bin"
cp "$repo_jangada/install.sh" "$inst/"
echo 'touch "$HOME/etapa-rodou"' >"$inst/install/00-teste.sh"
cp "$repo_jangada/install/lib.sh" "$inst/install/"
cp "$repo_jangada/bin/jangada-config" "$inst/bin/"
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
