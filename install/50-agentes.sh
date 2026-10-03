# shellcheck shell=bash
# Etapa 50: camada de agentes (tmux isolado, hooks e skills do Claude Code e do agy).

executar mkdir -p "$JANGADA_ESTADO/agentes"

# Hooks do Claude Code: acrescenta os hooks do jangada a ~/.claude/settings.json
# sem apagar hooks existentes. Só age se o Claude Code estiver instalado.
if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  mesclar_hooks_claude
  # Skills de default/claude/skills: regras e pegadinhas do jangada e os
  # protocolos de relatório técnico e acadêmico.
  ligar_skill_claude
  # Papéis de subagente, incluindo o supervisor de relatórios intermediários.
  ligar_agentes_claude
else
  aviso "Claude Code não encontrado; hooks e skills não instalados (rode ./install.sh 50 depois de instalar)"
fi

# Hooks do Antigravity (agy): estado da sessão na barra, como no Claude Code.
# As mesmas skills vão para ~/.gemini/config/skills.
if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_hooks_agy
  ligar_skill_agy
  mesclar_agentes_agy
fi

# Painel de indicadores (jangada-painel): opcional. Só avisa o que falta;
# não instala R, pacote R nem o pyarrow.
# O código 1 do --conferir (falta algo) não pode derrubar a instalação.
{ "$JANGADA_PATH/bin/jangada-painel" --conferir 2>/dev/null || true; } | while IFS= read -r l; do
  aviso "painel de indicadores: $l"
done
