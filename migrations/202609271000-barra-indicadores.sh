#!/usr/bin/env bash
# Migração de 27/09/2026: módulo do painel de indicadores na barra.
#
# O default/waybar/config.jsonc ganhou o módulo custom/indicadores, logo
# depois do custom/agentes em modules-left. Ele mostra o estado do
# jangada-painel (parado, no ar, atualizando, erro), abre o painel no clique e
# encerra o app no botão direito. Atualiza pelo sinal 9.
#
# Quem lê o config.jsonc do repositório já recebeu o módulo pelo git pull, e o
# estilo vem do base.css, que o style.css lê direto do repositório. Esta
# migração é para quem tem cópia própria em ~/.config/jangada/waybar, que o
# jangada-barra prefere e que seguiria sem o módulo. Ela põe o nome do módulo
# depois de "custom/agentes" na lista em que ele estiver e a definição do
# módulo antes da definição do custom/agentes.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

alvo="$JANGADA_CONFIG/waybar/config.jsonc"

if [[ ! -f "$alvo" ]]; then
  ok "sem cópia própria de waybar/config.jsonc; nada a migrar"
  exit 0
fi

if grep -q '"custom/indicadores"' "$alvo"; then
  ok "$alvo já tem o custom/indicadores; nada a migrar"
  exit 0
fi

# Sem o custom/agentes numa lista ou sem a definição dele, o usuário mexeu na
# barra por conta própria e não há onde encaixar o módulo com segurança.
if ! grep -qE '"custom/agentes"[[:space:]]*(,|\]|$)' "$alvo" \
  || ! grep -qE '^[[:space:]]*"custom/agentes"[[:space:]]*:' "$alvo"; then
  aviso "$alvo não tem o custom/agentes onde a migração espera; acrescente o custom/indicadores à mão (veja $JANGADA_PATH/default/waybar/config.jsonc)"
  exit 0
fi

novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT

# O nome entra só na primeira lista que cita o custom/agentes; a definição
# entra antes da chave dele, com a mesma margem.
awk '
  BEGIN { na_lista = 0 }
  !na_lista && /"custom\/agentes"[[:space:]]*(,|\]|$)/ && !/"custom\/agentes"[[:space:]]*:/ {
    sub(/"custom\/agentes"/, "\"custom/agentes\", \"custom/indicadores\"")
    na_lista = 1
  }
  /^[[:space:]]*"custom\/agentes"[[:space:]]*:/ {
    match($0, /^[[:space:]]*/)
    m = substr($0, 1, RLENGTH)
    printf "%s// Painel de indicadores (jangada-painel). O exec só lê o cache; o clique\n", m
    printf "%s// roda solto (setsid -f) para não prender a barra enquanto o app R sobe.\n", m
    printf "%s\"custom/indicadores\": {\n", m
    printf "%s  \"exec\": \"$JANGADA_PATH/bin/jangada-painel --waybar\",\n", m
    printf "%s  \"return-type\": \"json\",\n", m
    printf "%s  \"interval\": 300,\n", m
    printf "%s  \"signal\": 9,\n", m
    printf "%s  \"format\": \"{}\",\n", m
    printf "%s  \"on-click\": \"setsid -f $JANGADA_PATH/bin/jangada-painel\",\n", m
    printf "%s  \"on-click-right\": \"$JANGADA_PATH/bin/jangada-painel --parar\",\n", m
    printf "%s  \"tooltip\": true\n", m
    printf "%s},\n\n", m
  }
  { print }
' "$alvo" >"$novo"

if tem_comando jq; then
  if ! sed 's#^[[:space:]]*//.*##' "$novo" | jq -e '(.["custom/indicadores"].signal == 9)
      and ([.[] | arrays | select(index("custom/indicadores"))] | length == 1)' >/dev/null 2>&1; then
    erro "o resultado da inserção não é JSON válido; $alvo fica como está"
    exit 1
  fi
fi

copia_seguranca "$alvo"
if simulando; then
  info "[simulação] acrescentaria o custom/indicadores depois do custom/agentes em $alvo"
else
  cat "$novo" >"$alvo"
fi
ok "módulo do painel de indicadores acrescentado à barra: $alvo"
