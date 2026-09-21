#!/usr/bin/env bash
# Migração de 21/09/2026: skill do jangada para o Claude Code.
#
# A etapa install/50-agentes.sh passou a ligar ~/.claude/skills/jangada à pasta
# default/claude/skills/jangada do repositório. A skill reúne as regras do
# projeto e as pegadinhas já resolvidas (hyprctl só com Lua, hypridle que
# ignora -c, on-click da waybar com setsid, agy sem terminal), para que um
# agente aberto em outro projeto não precise redescobri-las.
#
# Instalações anteriores não rodam a etapa 50 de novo; esta migração cria o
# link. Não mexe numa pasta ou link alheio com o mesmo nome.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando claude && [[ ! -d "$HOME/.claude" ]]; then
  ok "Claude Code não encontrado; nada a migrar"
  exit 0
fi

ligar_skill_claude
