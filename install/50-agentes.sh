# shellcheck shell=bash
# Etapa 50: camada de agentes (tmux isolado, hooks e skill do Claude Code).

executar mkdir -p "$JANGADA_ESTADO/agentes"

# Hooks do Claude Code: acrescenta os hooks do jangada a ~/.claude/settings.json
# sem apagar hooks existentes. Só age se o Claude Code estiver instalado.
if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  mesclar_hooks_claude
  # Skill com as regras e pegadinhas do jangada, lida pelo Claude Code quando a
  # tarefa envolve a sessão (default/claude/skills/jangada).
  ligar_skill_claude
else
  aviso "Claude Code não encontrado; hooks e skill não instalados (rode ./install.sh 50 depois de instalar)"
fi
