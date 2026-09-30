#!/usr/bin/env bash
# Codex falso: lançamento, protocolo e argumentos sem rede nem login real.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
falhas=0
conferir() {
  local nome="$1"; shift
  if "$@"; then printf 'ok    %s\n' "$nome"; else printf 'FALHA %s\n' "$nome"; falhas=$((falhas + 1)); fi
}
mkdir -p "$tmp/bin" "$tmp/config/jangada" "$tmp/state/jangada/agentes" "$tmp/projeto"
cat >"$tmp/bin/codex" <<'EOF'
#!/usr/bin/env bash
if [[ "${1:-}" == --help ]]; then
  [[ "${FALSO_ANTIGO:-0}" == 1 ]] || echo --no-daemon
  exit 0
fi
printf '%s\0' "$@" >"$FALSO_DIR/codex.args"
EOF
cat >"$tmp/bin/tmux" <<'EOF'
#!/usr/bin/env bash
case " $* " in
  *" has-session "*) exit 1 ;;
  *" new-session "*) printf '%s\n' "$@" >"$FALSO_DIR/tmux.ambiente" ;;
  *" send-keys "*) printf '%s' "${*: -2:1}" >"$FALSO_DIR/tmux.comando" ;;
esac
EOF
for c in claude agy notify-send pkill; do
  printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/$c"
done
chmod +x "$tmp/bin/"*
rodar() {
  env -u JANGADA_SESSAO -u JANGADA_ISOLADO -u JANGADA_DELEGAR -u JANGADA_VALIDAR_REVISOR \
    PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp" JANGADA_PATH="$repo_jangada" \
    XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" "$@"
}
git init -q -b main "$tmp/projeto"
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio
printf 'JANGADA_WORKTREES=%s\n' "$tmp/worktrees" >"$tmp/config/jangada/jangada.conf"
rodar "$repo_jangada/bin/jangada-agente" --perfil codex-codex --projeto "$tmp/projeto" \
  --nome tarefa --prompt $'primeira linha\nsegunda linha' >"$tmp/saida" 2>&1
conferir "perfil codex-codex cria a sessão" [ "$?" = 0 ]
conferir "worktree próprio" test -f "$tmp/worktrees/projeto/tarefa/.git"
conferir "revisor e delegação no estado" jq -e '.agente == "codex" and .revisor == "codex" and .delegar == "local" and .isolar' \
  "$tmp/state/jangada/agentes/projeto--tarefa.json"
conferir "protocolo compatível com Codex" grep -q 'Não tente chamar subagentes do Claude' \
  "$tmp/state/jangada/agentes/protocolo-projeto--tarefa.md"
conferir "lançamento isolado pelo adaptador" grep -q 'jangada-isolar -- .*jangada-codex --protocolo .* -- codex' "$tmp/tmux.comando"
conferir "metadados externos para revisão" jq -e '.revisor == "codex" and .agente == "codex"' \
  "$tmp/state/jangada/revisoes/projeto--tarefa.json"

rodar "$repo_jangada/bin/jangada-codex" -- codex >"$tmp/saida" 2>&1
conferir "adaptador sem isolamento recusa antes de chamar CLI" [ "$?" != 0 ]
conferir "recusa não executa Codex" test ! -e "$tmp/codex.args"

protocolo="$tmp/protocolo com espaço.md"
printf 'Regra com aspas: "texto"\nSegunda linha\n' >"$protocolo"
rodar JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ "$repo_jangada/bin/jangada-codex" --protocolo "$protocolo" -- codex --model modelo 'pedido com espaço'
conferir "adaptador executa Codex" [ "$?" = 0 ]
# Confere o TOML que o CLI realmente receberá, incluindo comandos dos hooks.
python3 - "$tmp/codex.args" "$protocolo" "$repo_jangada" <<'PY'
import pathlib, sys, tomllib
args = pathlib.Path(sys.argv[1]).read_bytes().decode().split("\0")[:-1]
cfg = {}
for i, arg in enumerate(args):
    if arg == "-c":
        cfg.update(tomllib.loads(args[i + 1]))
assert cfg["developer_instructions"] == pathlib.Path(sys.argv[2]).read_text()
assert cfg["approvals_reviewer"] == "user"
assert "--no-daemon" in args and "workspace-write" in args and "on-request" in args
assert not any("bypass" in arg for arg in args)
assert args.count("pedido com espaço") == 1
hooks = {}
for i, arg in enumerate(args):
    if arg == "-c" and args[i + 1].startswith("hooks."):
        hooks.update(tomllib.loads(args[i + 1])["hooks"])
assert set(hooks) == {"SessionStart", "SessionEnd", "UserPromptSubmit", "PreToolUse",
                      "PostToolUse", "PermissionRequest", "Stop", "Interrupt"}
assert all(h[0]["hooks"][0]["command"].startswith("'" + sys.argv[3] + "/bin/jangada-hook-codex'")
           for h in hooks.values())
PY
conferir "TOML, protocolo, permissões e hooks válidos" [ "$?" = 0 ]
uuid=0123abcd-4567-89ab-cdef-0123456789ab
rodar JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ "$repo_jangada/bin/jangada-codex" --conversa "$uuid" -- codex
conferir "retoma pelo UUID" python3 -c 'import pathlib,sys; a=pathlib.Path(sys.argv[1]).read_bytes().split(b"\0"); assert a[-3:-1]==[b"resume",sys.argv[2].encode()]' "$tmp/codex.args" "$uuid"
rodar JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ "$repo_jangada/bin/jangada-codex" --retomar -- codex
conferir "retomada sem UUID usa filtro da pasta" python3 -c 'import pathlib,sys; a=pathlib.Path(sys.argv[1]).read_bytes().split(b"\0"); assert a[-3:-1]==[b"resume",b"--last"]' "$tmp/codex.args"
rm -f "$tmp/codex.args"
rodar JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ FALSO_ANTIGO=1 "$repo_jangada/bin/jangada-codex" -- codex >"$tmp/saida" 2>&1
conferir "versão sem execução própria é recusada" [ "$?" != 0 ]
conferir "versão recusada não abre sessão" test ! -e "$tmp/codex.args"
rodar JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ "$repo_jangada/bin/jangada-codex" --conversa 'id; touch /tmp/invadido' -- codex >"$tmp/saida" 2>&1
conferir "UUID inválido é recusado" [ "$?" != 0 ]
conferir "UUID inválido não executa" test ! -e "$tmp/codex.args"

# Hooks não aprovam permissões, repetição não duplica eventos e subagentes
# não marcam o principal como concluído.
hook() {
  printf '%s' "$2" | rodar JANGADA_SESSAO=projeto--tarefa "$repo_jangada/bin/jangada-hook-codex" "$1" >"$tmp/hook.saida"
}
hook inicio "{\"session_id\":\"$uuid\"}"
hook trabalhando '{}'
hook trabalhando '{}'
hook aguardando '{"tool_input":{"description":"permissão"}}'
conferir "pedido de permissão mantém saída vazia" test ! -s "$tmp/hook.saida"
conferir "permissão registra aguardando" jq -e '.estado == "aguardando"' "$tmp/state/jangada/agentes/projeto--tarefa.json"
hook concluido '{"agent_id":"filho"}'
conferir "subagente não conclui a sessão" jq -e '.estado == "aguardando"' "$tmp/state/jangada/agentes/projeto--tarefa.json"
hook trabalhando '{}'
hook concluido '{"last_assistant_message":"feito"}'
hook fim '{}'
conferir "conversa registrada" jq -e --arg c "$uuid" '.conversa == $c and .estado == "concluido"' "$tmp/state/jangada/agentes/projeto--tarefa.json"
conferir "eventos sem repetição" jq -se '[.[] | select(.agente == "codex") | .estado] == ["inicio", "trabalhando", "aguardando", "trabalhando", "concluido", "fim"]' "$tmp/state/jangada/eventos-agentes.jsonl"
antes="$(sha256sum "$tmp/state/jangada/agentes/projeto--tarefa.json")"
hook trabalhando 'não é JSON'
conferir "JSON inválido não altera o estado" [ "$(sha256sum "$tmp/state/jangada/agentes/projeto--tarefa.json")" = "$antes" ]
rm -f "$tmp/state/jangada/agentes/projeto--tarefa.json"
hook inicio '{}'
conferir "hook não recria sessão encerrada" test ! -e "$tmp/state/jangada/agentes/projeto--tarefa.json"
((falhas == 0))
