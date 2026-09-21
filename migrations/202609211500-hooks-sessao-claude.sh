#!/usr/bin/env bash
# Migração de 21/09/2026: hooks SessionStart e SessionEnd do Claude Code.
#
# O jangada-hook-claude passou a guardar o id da conversa (session_id), que o
# jangada-agentes --restaurar usa para reabrir a sessão com claude --resume
# depois de um reboot, e a marcar quando o Claude sai. A etapa 50 só mesclava
# os hooks quando nenhum hook do jangada existia, então instalações anteriores
# não recebem os eventos novos. Esta migração mescla evento por evento, sem
# duplicar o que já está lá e com cópia de segurança do settings.json.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando claude && [[ ! -d "$HOME/.claude" ]]; then
  ok "Claude Code não encontrado; nada a migrar"
  exit 0
fi

mesclar_hooks_claude
