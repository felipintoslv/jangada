#!/usr/bin/env bash
# Testa, em repositórios temporários, o que chega à cópia instalada: o
# jangada-update só aplica commits novos da origem com confirmação, e o
# jangada-agente-fim --integrar não atualiza a cópia instalada nem roda o git
# com fsmonitor ou ganchos do repositório do agente. pacman, checkupdates,
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

if ((falhas)); then
  echo "--- última saída"; cat "$tmp/saida"
  echo "$falhas falha(s)"
  exit 1
fi
echo "tudo certo"
