#!/usr/bin/env bash
# Testa a instalação e a conferência dos hooks do Claude e do agy com o
# arquivo de configuração vazio ou inválido: a mescla trata o vazio como {} e
# grava os hooks, e o jangada-verificar aponta o arquivo em vez de dar tudo
# certo (o jq não devolve nada para uma entrada vazia).
#
# Uso: testes/hooks.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/estado"
export JANGADA_PATH="$PWD" JANGADA_SIMULAR=0
unset HYPRLAND_INSTANCE_SIGNATURE
claude_cfg="$HOME/.claude/settings.json"
agy_cfg="$HOME/.gemini/config/hooks.json"
mkdir -p "$HOME/.claude" "$HOME/.gemini/config"

mesclar() { # função da lib
  bash -c 'source install/lib.sh && "$1"' _ "$1" >"$tmp/saida" 2>&1
}
# Linha logo abaixo do título da seção na saída do jangada-verificar.
secao() {
  bin/jangada-verificar 2>&1 | grep -A1 -F "== $1" | tail -1
}
eventos_claude() { jq -r '.hooks | keys | join(" ")' default/claude/hooks.json; }

echo "== settings.json do Claude vazio"
: >"$claude_cfg"
conferir "verificar aponta o arquivo vazio" bash -c '[[ "$1" == *"settings.json vazio ou inválido"* ]]' _ "$(secao "hooks do Claude Code")"
mesclar mesclar_hooks_claude
conferir "a mescla grava os hooks" \
  [ "$(jq -r '.hooks | keys | join(" ")' "$claude_cfg" 2>/dev/null)" = "$(eventos_claude)" ]
conferir "a mescla não diz que já estavam instalados" bash -c '! grep -q "já instalados" "$1"' _ "$tmp/saida"
conferir "a mescla guarda a cópia do vazio" \
  bash -c 'ls "$1".jangada-*.bak >/dev/null 2>&1' _ "$claude_cfg"
conferir "verificar dá os hooks por instalados" bash -c '[[ "$1" == *"hooks instalados em todos os eventos"* ]]' _ "$(secao "hooks do Claude Code")"
mesclar mesclar_hooks_claude
conferir "rodar de novo não muda nada" grep -q "já instalados" "$tmp/saida"

echo "== settings.json do Claude inválido"
printf '{"hooks": \n' >"$claude_cfg"
mesclar mesclar_hooks_claude
conferir "a mescla avisa e não grava" \
  bash -c 'grep -q "não consegui ler" "$1" && [ "$(cat "$2")" = "{\"hooks\": " ]' _ "$tmp/saida" "$claude_cfg"
conferir "verificar aponta o arquivo inválido" bash -c '[[ "$1" == *"settings.json vazio ou inválido"* ]]' _ "$(secao "hooks do Claude Code")"

echo "== hooks.json do agy vazio"
: >"$agy_cfg"
conferir "verificar aponta o arquivo vazio" bash -c '[[ "$1" == *"hooks.json vazio ou inválido"* ]]' _ "$(secao "hooks do Antigravity")"
mesclar mesclar_hooks_agy
conferir "a mescla grava os hooks" bash -c 'jq -e "$1" "$2" >/dev/null' _ '.jangada.PreToolUse and .jangada.Stop' "$agy_cfg"
conferir "a mescla não diz que já estavam instalados" bash -c '! grep -q "já instalados" "$1"' _ "$tmp/saida"
conferir "a mescla guarda a cópia do vazio" \
  bash -c 'ls "$1".jangada-*.bak >/dev/null 2>&1' _ "$agy_cfg"
conferir "verificar dá os hooks por instalados" bash -c '[[ "$1" == *"hooks instalados em todos os eventos"* ]]' _ "$(secao "hooks do Antigravity")"
mesclar mesclar_hooks_agy
conferir "rodar de novo não muda nada" grep -q "já instalados" "$tmp/saida"

echo "== hooks.json do agy inválido"
printf '{"jangada": \n' >"$agy_cfg"
mesclar mesclar_hooks_agy
conferir "a mescla avisa e não grava" \
  bash -c 'grep -q "não consegui ler" "$1" && [ "$(cat "$2")" = "{\"jangada\": " ]' _ "$tmp/saida" "$agy_cfg"
conferir "verificar aponta o arquivo inválido" bash -c '[[ "$1" == *"hooks.json vazio ou inválido"* ]]' _ "$(secao "hooks do Antigravity")"

if ((falhas)); then
  echo "$falhas teste(s) dos hooks falharam"
  exit 1
fi
echo "todos os testes dos hooks passaram"
