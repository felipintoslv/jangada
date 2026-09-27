#!/usr/bin/env bash
# Migração de 26/09/2026: skills do jangada no Antigravity (agy).
#
# O agy carrega skills da raiz global ~/.gemini/config/skills/<nome>/SKILL.md,
# a mesma pasta do hooks.json, e aceita o formato do Claude Code sem ajuste. A
# etapa install/50-agentes.sh passou a ligar cada pasta de default/claude/skills
# lá também. Esta migração cria os links. Não mexe numa pasta ou link alheio
# com o mesmo nome.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando agy && [[ ! -d "$HOME/.gemini" ]]; then
  ok "agy não encontrado; nada a migrar"
  exit 0
fi

ligar_skill_agy
