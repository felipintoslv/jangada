#!/usr/bin/env bash
# Migração de 27/09/2026: papéis de subagente auditor, arquiteto, otimizador e
# redator.
#
# A migração 202609271200-subagentes.sh ligou só os papéis que existiam quando
# rodou e não roda de novo. As mesmas funções ligam agora os papéis novos em
# ~/.claude/agents/ e conferem o registro do agy; o que já está ligado fica
# como está.
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
