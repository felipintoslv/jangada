#!/usr/bin/env bash
# Migração de 22/09/2026: hooks do Antigravity (agy).
#
# O agy passou a ser um agente de primeira classe no jangada-agente (perfil
# default/agentes/agy.conf, com o jangada-validar chamando o Claude só para
# revisar). Para a barra acompanhar o estado dessas sessões, o hook
# jangada-hook-agy vai para ~/.gemini/config/hooks.json, na chave "jangada".
# Hooks alheios no mesmo arquivo ficam como estão.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

if ! tem_comando agy && [[ ! -d "$HOME/.gemini" ]]; then
  ok "agy não encontrado; nada a migrar"
  exit 0
fi

mesclar_hooks_agy
