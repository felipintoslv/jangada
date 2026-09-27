#!/usr/bin/env bash
# Migração de 27/09/2026: papéis de subagente (explorador, leitor, pesquisador
# e verificador).
#
# A etapa install/50-agentes.sh passou a ligar default/claude/agents/*.md em
# ~/.claude/agents/ e a registrar default/agy/agents em
# ~/.gemini/config/agents.json. Esta migração faz o mesmo numa instalação
# existente. Não mexe em arquivo alheio com o mesmo nome nem nas outras
# entradas do agents.json.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  ligar_agentes_claude
else
  ok "Claude Code não encontrado; subagentes do Claude não ligados"
fi

if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_agentes_agy
else
  ok "agy não encontrado; subagentes do agy não registrados"
fi
