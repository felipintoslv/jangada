#!/usr/bin/env bash
# Migração de 28/09/2026: hook do leitor no Antigravity (agy).
#
# O leitor do agy lê documentos de fora e tinha no terminal só a regra do
# texto do papel e o permissions.allow do usuário. O PreToolUse do
# run_command passa a chamar o jangada-hook-leitor --agy, que recusa o que não
# é comando de leitura quando o agente é o leitor. O jangada-delegar recusa o
# papel leitor sem esse hook.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando agy && [[ ! -d "$HOME/.gemini" ]]; then
  ok "agy não encontrado; nada a migrar"
  exit 0
fi

mesclar_hooks_agy
