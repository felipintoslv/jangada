#!/usr/bin/env bash
# Migração de 26/09/2026: skills de relatório técnico e acadêmico.
#
# default/claude/skills ganhou relatorio-tecnico (investigação, postmortem,
# RFC, ADR, NBR 10719) e relatorio-academico (artigo, monografia, tese), e a
# etapa install/50-agentes.sh passou a ligar cada pasta de lá em
# ~/.claude/skills/<nome>. Esta migração cria os links novos. Não mexe numa
# pasta ou link alheio com o mesmo nome.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando claude && [[ ! -d "$HOME/.claude" ]]; then
  ok "Claude Code não encontrado; nada a migrar"
  exit 0
fi

ligar_skill_claude
