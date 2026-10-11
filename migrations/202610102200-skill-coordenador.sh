#!/usr/bin/env bash
# Migração de 10/10/2026: skill coordenador.
#
# default/claude/skills ganhou coordenador, o papel da sessão que abre,
# acompanha e confere tarefas de agentes em qualquer projeto. O jangada-update
# não repete a etapa install/50-agentes.sh; esta migração cria o link novo em
# ~/.claude/skills/coordenador e, com o Codex instalado, em
# ~/.codex/skills/coordenador (ou na pasta de CODEX_HOME). O agy fica de fora
# porque não abre sessão principal. Não mexe numa pasta ou link alheio com o
# mesmo nome.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  ligar_skill_claude
else
  ok "Claude Code não encontrado; skill não ligada"
fi

if tem_comando codex || [[ -d "${CODEX_HOME:-$HOME/.codex}" ]]; then
  ligar_skill_codex
else
  ok "Codex não encontrado; skill não ligada"
fi
