# shellcheck shell=bash
# Etapa 50: camada de agentes (tmux isolado, hooks e skill do Claude Code).

executar mkdir -p "$JANGADA_ESTADO/agentes"

# Hooks do Claude Code: acrescenta os hooks do jangada a ~/.claude/settings.json
# sem apagar hooks existentes. Só age se o Claude Code estiver instalado.
_claude="$HOME/.claude/settings.json"
if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  executar mkdir -p "$HOME/.claude"
  [[ -f "$_claude" ]] || { simulando || echo '{}' >"$_claude"; }
  if [[ -f "$_claude" ]] && grep -q 'jangada-hook-claude' "$_claude"; then
    ok "hooks do Claude Code já instalados"
  else
    copia_seguranca "$_claude"
    _hooks="$(sed "s|@JANGADA_PATH@|$JANGADA_PATH|g" "$JANGADA_PATH/default/claude/hooks.json")"
    if simulando; then
      info "[simulação] mesclaria os hooks do jangada em $_claude"
    else
      _tmp="$(mktemp)"
      # Para cada evento, concatena a lista existente com a do jangada.
      jq --argjson novos "$_hooks" '
        .hooks = (
          (.hooks // {}) as $atuais
          | reduce ($novos.hooks | keys[]) as $ev ($atuais; .[$ev] = ((.[$ev] // []) + $novos.hooks[$ev]))
        )' "$_claude" >"$_tmp" && mv "$_tmp" "$_claude"
    fi
    ok "hooks do Claude Code instalados em $_claude"
  fi
  # Skill com as regras e pegadinhas do jangada, lida pelo Claude Code quando a
  # tarefa envolve a sessão (default/claude/skills/jangada).
  ligar_skill_claude
else
  aviso "Claude Code não encontrado; hooks e skill não instalados (rode ./install.sh 50 depois de instalar)"
fi
unset _claude _hooks _tmp
