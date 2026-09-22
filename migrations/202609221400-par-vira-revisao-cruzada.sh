#!/usr/bin/env bash
# Migração de 22/09/2026: o jangada-par saiu.
#
# O agente criado pelo jangada-agente passou a validar a entrega com o outro
# modelo (jangada-validar: o agy revisa o Claude, o Claude revisa o agy), e o
# par virou uma segunda porta para o mesmo fluxo. Saíram o comando, o atalho
# SUPER+P, a entrada do menu e a função "par" do jangada shell; o gancho
# pos-par deu lugar ao pos-validar. Esta migração não altera nada do usuário:
# só avisa onde a configuração dele ainda cita o que saiu.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

config="${XDG_CONFIG_HOME:-$HOME/.config}/jangada"
achou=0
if [[ -d "$config" ]]; then
  while IFS= read -r arq; do
    aviso "$arq cita o jangada-par, que saiu; use jangada-agente (SUPER+A)"
    achou=1
  done < <(grep -rl 'jangada-par' "$config" 2>/dev/null || true)
  for g in "$config/ganchos/pos-par" "$config/ganchos/pos-par.d"; do
    if [[ -e "$g" ]]; then
      aviso "gancho $g não roda mais; renomeie para pos-validar (recebe sessão e status)"
      achou=1
    fi
  done
fi
((achou)) || ok "nada do jangada-par na configuração do usuário"
