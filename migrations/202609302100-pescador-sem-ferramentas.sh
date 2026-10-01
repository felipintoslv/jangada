#!/usr/bin/env bash
# Registra o papel sem ferramentas para o chat e a auditoria do Pescador.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_agentes_agy
fi
