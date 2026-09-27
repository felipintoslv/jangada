#!/usr/bin/env bash
# Testa a configuração da barra: o módulo custom/indicadores no config.jsonc,
# na barra em pé gerada pelo jangada-barra e no base.css, o sinal 9 reservado
# a ele e a migração que o acrescenta à cópia própria do usuário.
#
# Uso: testes/barra.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
# config.jsonc sem as linhas de comentário, como em testes/verificar.sh.
sem_comentario() { sed 's#^[[:space:]]*//.*##' "$1"; }
jq_ok() { jq -e "$@" >/dev/null 2>&1; }
# Sem cmp: o diffutils não vem na imagem do CI.
iguais() { [[ "$(<"$1")" == "$(<"$2")" ]]; }
sem_comentario default/waybar/config.jsonc >"$tmp/config.json"

# Caso 1: módulo no config.jsonc do repositório.
conferir "caso 1: custom/indicadores logo depois do custom/agentes" \
  jq_ok '.["modules-left"] | index("custom/indicadores") == index("custom/agentes") + 1' "$tmp/config.json"
conferir "caso 1: exec só lê o cache, JSON, sinal 9 e intervalo longo" \
  jq_ok '.["custom/indicadores"] | .exec == "$JANGADA_PATH/bin/jangada-painel --waybar"
    and .["return-type"] == "json" and .signal == 9 and .interval >= 300' "$tmp/config.json"
conferir "caso 1: clique solto e botão direito encerra" \
  jq_ok '.["custom/indicadores"] | .["on-click"] == "setsid -f $JANGADA_PATH/bin/jangada-painel"
    and .["on-click-right"] == "$JANGADA_PATH/bin/jangada-painel --parar"' "$tmp/config.json"
conferir "caso 1: o sinal 9 é só do custom/indicadores" \
  jq_ok '[to_entries[] | select(.value | objects | .signal == 9) | .key] == ["custom/indicadores"]' "$tmp/config.json"
conferir "caso 1: nenhum outro comando manda RTMIN+9" \
  [ -z "$(grep -rl 'RTMIN+9' bin default | grep -vx 'bin/jangada-painel')" ]

# Caso 2: estilo das quatro classes e da barra em pé.
for classe in parado no-ar atualizando erro; do
  conferir "caso 2: base.css estiliza .$classe" grep -q "^#custom-indicadores\.$classe" default/waybar/base.css
done
conferir "caso 2: base.css troca a folga na barra em pé" \
  grep -q '^window#waybar\.vertical #custom-indicadores' default/waybar/base.css

# Caso 3: barra em pé gerada pelo jangada-barra, com waybar e pkill falsos.
mkdir -p "$tmp/bin" "$tmp/config/jangada"
printf '#!/bin/sh\nexit 1\n' >"$tmp/bin/pkill"
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/waybar"
chmod +x "$tmp/bin/"*
echo "JANGADA_BARRA_POSICAO=esquerda" >"$tmp/config/jangada/jangada.conf"
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
  JANGADA_PATH="$repo_jangada" bin/jangada-barra 2>"$tmp/erro-barra" || falha "caso 3: jangada-barra: $(cat "$tmp/erro-barra")"
gerado="$tmp/state/jangada/waybar/borda.jsonc"
if [[ -f "$gerado" ]]; then
  sem_comentario "$gerado" >"$tmp/borda.json"
  conferir "caso 3: borda.jsonc é JSON" jq_ok . "$tmp/borda.json"
  conferir "caso 3: barra em pé com custom/indicadores depois do custom/agentes" \
    jq_ok '.["modules-left"] | index("custom/indicadores") == index("custom/agentes") + 1' "$tmp/borda.json"
else
  falha "caso 3: jangada-barra não gerou $gerado"
fi

# Caso 4: migração sobre uma cópia própria com a barra antiga.
migracao=migrations/202609271000-barra-indicadores.sh
migrar() { XDG_CONFIG_HOME="$tmp/m" JANGADA_PATH="$repo_jangada" bash "$migracao" >/dev/null 2>&1; }
alvo="$tmp/m/jangada/waybar/config.jsonc"
mkdir -p "$(dirname "$alvo")"
# Cópia própria sem o custom/indicadores, como a de quem copiou a barra antes dele.
python3 - default/waybar/config.jsonc "$alvo" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
s = s.replace('"custom/agentes", "custom/indicadores"', '"custom/agentes"')
s = re.sub(r'  // Painel de indicadores.*?\n  "custom/indicadores": \{.*?\n  \},\n\n', '', s, flags=re.S)
open(sys.argv[2], "w").write(s)
PY
conferir "caso 4: a barra de antes não tem o módulo" bash -c '! grep -q custom/indicadores "$1"' _ "$alvo"
cp "$alvo" "$tmp/antes.jsonc"
JANGADA_SIMULAR=1 migrar
conferir "caso 4: simulação não altera o arquivo" iguais "$alvo" "$tmp/antes.jsonc"
conferir "caso 4: migração roda sem erro" migrar
sem_comentario "$alvo" >"$tmp/migrado.json"
conferir "caso 4: resultado com o mesmo módulo do padrão" \
  jq_ok --slurpfile p "$tmp/config.json" '.["custom/indicadores"] == $p[0]["custom/indicadores"]
    and .["modules-left"] == $p[0]["modules-left"]' "$tmp/migrado.json"
conferir "caso 4: deixa uma cópia de segurança" \
  [ "$(compgen -G "$alvo.jangada-*.bak" | wc -l)" = 1 ]
cp "$alvo" "$tmp/depois.jsonc"
conferir "caso 4: segunda passada roda sem erro" migrar
conferir "caso 4: segunda passada não muda nada" iguais "$alvo" "$tmp/depois.jsonc"

# Caso 5: lista em várias linhas, com o custom/agentes por último.
printf '{\n  "modules-left": [\n    "custom/menu",\n    "custom/agentes"\n  ],\n  "custom/agentes": {\n    "exec": "x"\n  }\n}\n' >"$alvo"
conferir "caso 5: migração roda sem erro" migrar
conferir "caso 5: módulo entra no fim da lista em várias linhas" \
  jq_ok '.["modules-left"] == ["custom/menu", "custom/agentes", "custom/indicadores"]
    and .["custom/indicadores"].signal == 9' <(sem_comentario "$alvo")

# Caso 6: sem o custom/agentes, a migração só avisa.
printf '{\n  "modules-left": ["custom/menu"]\n}\n' >"$alvo"
cp "$alvo" "$tmp/sem-agentes.jsonc"
conferir "caso 6: sem custom/agentes, sai sem erro" migrar
conferir "caso 6: sem custom/agentes, não altera o arquivo" iguais "$alvo" "$tmp/sem-agentes.jsonc"

# Caso 7: sem cópia própria, nada a fazer.
rm -f "$alvo"
conferir "caso 7: sem cópia própria, sai sem erro" migrar
conferir "caso 7: sem cópia própria, não cria o arquivo" [ ! -e "$alvo" ]

if ((falhas)); then
  echo "$falhas teste(s) da barra falharam"
  exit 1
fi
echo "todos os testes da barra passaram"
