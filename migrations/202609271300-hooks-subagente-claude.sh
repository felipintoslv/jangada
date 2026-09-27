#!/usr/bin/env bash
# Migração de 27/09/2026: hooks SubagentStart e SubagentStop do Claude Code.
#
# O jangada-hook-claude passou a gravar no eventos-agentes.jsonl o início e o
# fim de cada subagente, com o id e o tipo, sem mudar o estado da sessão. A
# etapa 50 não roda de novo na atualização; esta migração mescla os dois
# eventos, sem duplicar o que já está lá e com cópia de segurança do
# settings.json.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando claude && [[ ! -d "$HOME/.claude" ]]; then
  ok "Claude Code não encontrado; nada a migrar"
  exit 0
fi

mesclar_hooks_claude
