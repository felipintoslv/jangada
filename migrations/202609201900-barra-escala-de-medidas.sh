#!/usr/bin/env bash
# Migração de 20/09/2026: escala de medidas da barra.
#
# Os números soltos do estilo da barra foram reduzidos a um conjunto pequeno,
# documentado no topo de default/waybar/base.css: unidade de 4px, folga interna
# e border-radius de 8px. O "spacing" do config.jsonc, que era 6, passou a 4
# para entrar nessa escala.
#
# O base.css é lido direto do repositório pelo style.css, então quem instalou
# já recebeu a parte do estilo pelo git pull. Esta migração é só para quem tem
# cópia própria de ~/.config/jangada/waybar/config.jsonc, que o jangada-barra
# prefere e que seguiria com o espaçamento antigo.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

alvo="$JANGADA_CONFIG/waybar/config.jsonc"

if [[ ! -f "$alvo" ]]; then
  ok "sem cópia própria de waybar/config.jsonc; nada a migrar"
  exit 0
fi

# Só o valor antigo é trocado. Quem escolheu outro espaçamento fica com o dele.
if ! grep -qE '^[[:space:]]*"spacing"[[:space:]]*:[[:space:]]*6[[:space:]]*,' "$alvo"; then
  ok "$alvo não está com o spacing antigo; nada a migrar"
  exit 0
fi

copia_seguranca "$alvo"
if simulando; then
  info "[simulação] trocaria \"spacing\": 6 por \"spacing\": 4 em $alvo"
else
  sed -i -E 's/^([[:space:]]*"spacing"[[:space:]]*:[[:space:]]*)6([[:space:]]*,)/\14\2/' "$alvo"
fi
ok "espaçamento da barra alinhado à escala de medidas: $alvo"
