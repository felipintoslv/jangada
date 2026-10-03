#!/usr/bin/env bash
# Registra o supervisor sem substituir papéis personalizados do usuário.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  ligar_agentes_claude
else
  ok "Claude Code não encontrado; supervisor do Claude não ligado"
fi

if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_agentes_agy
else
  ok "agy não encontrado; supervisor do agy não registrado"
fi
