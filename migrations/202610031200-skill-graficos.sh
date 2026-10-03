#!/usr/bin/env bash
# Migração de 03/10/2026: skill de gráficos.
#
# default/claude/skills ganhou graficos, com o tema de gráficos em R e em
# Python, os exemplos e a checklist de revisão. A etapa install/50-agentes.sh
# já liga cada pasta de lá em ~/.claude/skills/<nome> e em ~/.gemini/config/skills/<nome>;
# esta migração cria os links novos numa instalação existente. Não mexe numa
# pasta ou link alheio com o mesmo nome.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  ligar_skill_claude
else
  ok "Claude Code não encontrado; skill não ligada"
fi

if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  ligar_skill_agy
else
  ok "agy não encontrado; skill não ligada"
fi
