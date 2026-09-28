#!/usr/bin/env bash
# Migração de 28/09/2026: cliques da barra que abrem janela rodam soltos.
#
# A waybar espera o fim do on-click antes de rodar o exec do módulo de novo,
# então um clique que abre janela sem setsid -f congela o módulo enquanto a
# janela estiver aberta. Relógio, rede, monitor, bluetooth, áudio, energia,
# menu, terminal e agentes chamavam o script direto. O padrão passou a usar
# setsid -f em todo clique que chama um script do jangada, exceto --parar e
# toggle, que só mudam um estado e terminam na hora.
#
# Quem lê o config.jsonc do repositório já recebeu a correção pelo git pull.
# Esta migração é para quem tem cópia própria em ~/.config/jangada/waybar, que
# o jangada-barra prefere.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

alvo="$JANGADA_CONFIG/waybar/config.jsonc"

if [[ ! -f "$alvo" ]]; then
  ok "sem cópia própria de waybar/config.jsonc; nada a migrar"
  exit 0
fi

novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT

# Só casa o clique que começa direto por "$JANGADA_PATH/bin/", então um clique
# que já tem setsid -f, ou que foi trocado à mão por outro comando, fica como
# está, e a segunda passada não muda nada.
sed -E 's#("on-click(-right)?"[[:space:]]*:[[:space:]]*")(\$JANGADA_PATH/bin/)#\1setsid -f \3#
        s#setsid -f (\$JANGADA_PATH/bin/[^"]*( --parar| toggle)")#\1#' "$alvo" >"$novo"

if [[ "$(<"$novo")" == "$(<"$alvo")" ]]; then
  ok "$alvo já abre as janelas soltas; nada a migrar"
  exit 0
fi

copia_seguranca "$alvo"
if simulando; then
  info "[simulação] gravaria $alvo com setsid -f nos cliques que abrem janela"
else
  cat "$novo" >"$alvo"
fi
ok "cliques da barra que abrem janela passaram a rodar soltos: $alvo"
