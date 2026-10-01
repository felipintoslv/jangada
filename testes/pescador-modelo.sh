#!/usr/bin/env bash
# O executor nunca usa a pasta do projeto nem abre sem isolamento.
set -euo pipefail
cd "$(dirname "$0")/.."
repo="$PWD"
tmp="$(mktemp -d "$repo/.pescador-teste.XXXXXX")"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/casa" "$tmp/tarefa" "$tmp/config/jangada"
printf 'JANGADA_AGENTE_ISOLAR=0\n' >"$tmp/config/jangada/jangada.conf"
cat >"$tmp/tarefa/claude" <<'EOF'
#!/usr/bin/env bash
[[ "${JANGADA_ISOLADO:-}" == 1 ]] || exit 1
[[ "${JANGADA_HOOK_DESLIGADO:-}" == 1 && -z "${JANGADA_SESSAO:-}" ]] || exit 1
printf '%s\n' "$@" >args.txt
cat >pedido.txt
! touch "$HOME/fora.txt" 2>/dev/null || exit 1
echo '{"type":"result","subtype":"success","result":"resposta"}'
EOF
chmod +x "$tmp/tarefa/claude"
if command -v bwrap >/dev/null && bwrap --ro-bind / / --dev /dev --proc /proc true 2>/dev/null; then
  (cd "$tmp/tarefa" && env -u JANGADA_ISOLADO -u JANGADA_MARCA_ISOLADO -u CODEX_HOME \
    HOME="$tmp/casa" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
    JANGADA_PATH="$repo" JANGADA_SESSAO=nao-alterar \
    "$repo/bin/jangada-pescador-modelo" claude "$tmp/tarefa/claude" <<< 'pedido de teste') >"$tmp/saida"
  grep -qx -- --safe-mode "$tmp/tarefa/args.txt"
  grep -qx -- --tools "$tmp/tarefa/args.txt"
  grep -qx -- --strict-mcp-config "$tmp/tarefa/args.txt"
  grep -qx -- --no-session-persistence "$tmp/tarefa/args.txt"
  grep -qx 'pedido de teste' "$tmp/tarefa/pedido.txt"
  [[ ! -e "$tmp/casa/fora.txt" ]]
  echo 'ok    executor sem ferramentas e isolado, mesmo com configuração global desligada'
else
  echo 'pulado: isolamento real exige bubblewrap e namespaces permitidos'
fi
