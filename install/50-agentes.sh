# shellcheck shell=bash
# Etapa 50: camada de agentes (tmux isolado, hooks e skills do Claude Code).

executar mkdir -p "$JANGADA_ESTADO/agentes"

# Hooks do Claude Code: acrescenta os hooks do jangada a ~/.claude/settings.json
# sem apagar hooks existentes. Só age se o Claude Code estiver instalado.
if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  mesclar_hooks_claude
  # Skills de default/claude/skills: regras e pegadinhas do jangada e os
  # protocolos de relatório técnico e acadêmico.
  ligar_skill_claude
else
  aviso "Claude Code não encontrado; hooks e skills não instalados (rode ./install.sh 50 depois de instalar)"
fi

# Hooks do Antigravity (agy): estado da sessão na barra, como no Claude Code.
if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_hooks_agy
fi
