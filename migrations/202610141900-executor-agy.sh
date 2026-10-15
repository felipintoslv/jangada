#!/usr/bin/env bash
# O registro existente lê os papéis da cópia instalada, incluindo implementador.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  mesclar_agentes_agy
else
  ok "agy não encontrado; implementador não registrado"
fi
