#!/usr/bin/env bash
# Migração de 20/09/2026: temperatura da barra sem número de hwmon fixo.
#
# O default/waybar/config.jsonc listava caminhos /sys/class/hwmon/hwmonN com o
# número escrito no arquivo. Esse número sai na ordem em que os módulos do
# kernel registram os sensores e muda entre partidas, então a barra podia estar
# mostrando a temperatura da placa de vídeo, de um disco NVMe ou da placa de
# rede sem nenhum aviso. O padrão passou a usar hwmon-path-abs com
# input-filename, que apontam o diretório do dispositivo e deixam a waybar
# resolver o hwmonN de dentro dele.
#
# Quem lê o config.jsonc do repositório já recebeu a correção pelo git pull.
# Esta migração é para quem tem cópia própria em ~/.config/jangada/waybar, que
# o jangada-barra prefere e que seguiria com a lista antiga.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

alvo="$JANGADA_CONFIG/waybar/config.jsonc"

if [[ ! -f "$alvo" ]]; then
  ok "sem cópia própria de waybar/config.jsonc; nada a migrar"
  exit 0
fi

if ! grep -q '"hwmon-path"' "$alvo"; then
  ok "$alvo já não usa hwmon-path; nada a migrar"
  exit 0
fi

novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT

# Troca a chave "hwmon-path" inteira, com a lista que vier depois dela, pelas
# chaves novas. A margem da linha original é reaproveitada para a indentação
# não destoar do resto do arquivo. Um arquivo já alterado à mão não chega aqui,
# porque o grep acima não encontraria "hwmon-path".
if ! awk '
  BEGIN { dentro = 0; trocou = 0 }
  dentro { if ($0 ~ /\]/) dentro = 0; next }
  /"hwmon-path"[[:space:]]*:/ {
    match($0, /^[[:space:]]*/)
    margem = substr($0, 1, RLENGTH)
    printf "%s// Trocado pela migração de 20/09/2026: a numeração de hwmonN muda\n", margem
    printf "%s// entre partidas e o caminho fixo podia ler o sensor errado.\n", margem
    printf "%s\"hwmon-path-abs\": [\n", margem
    printf "%s  \"/sys/devices/platform/coretemp.0/hwmon\",\n", margem
    printf "%s  \"/sys/devices/pci0000:00/0000:00:18.3/hwmon\",\n", margem
    printf "%s  \"/sys/devices/platform/thinkpad_hwmon/hwmon\"\n", margem
    printf "%s],\n", margem
    printf "%s\"input-filename\": \"temp1_input\",\n", margem
    printf "%s\"thermal-zone\": 0,\n", margem
    if ($0 ~ /\[/ && $0 !~ /\]/) dentro = 1
    trocou = 1
    next
  }
  { print }
  END { if (!trocou) exit 1 }
' "$alvo" >"$novo"; then
  erro "não foi possível localizar a chave hwmon-path em $alvo; ajuste à mão"
  exit 1
fi

# O arquivo tem comentários, então o jq só valida depois que as linhas de
# comentário saem, do mesmo jeito que testes/verificar.sh faz.
if tem_comando jq; then
  if ! sed 's#^[[:space:]]*//.*##' "$novo" | jq empty 2>/dev/null; then
    erro "o resultado da troca não é JSON válido; $alvo fica como está"
    exit 1
  fi
fi

copia_seguranca "$alvo"
if simulando; then
  info "[simulação] gravaria $alvo com hwmon-path-abs no lugar de hwmon-path"
else
  cat "$novo" >"$alvo"
fi
ok "temperatura da barra passou a resolver o sensor por dispositivo: $alvo"
