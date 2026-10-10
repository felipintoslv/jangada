#!/usr/bin/env bash
# Testa a configuração da barra: o módulo custom/indicadores no config.jsonc,
# na barra em pé gerada pelo jangada-barra e no base.css, o sinal 9 reservado
# a ele e a migração que o acrescenta à cópia própria do usuário; os cliques
# que abrem janela com setsid -f e a migração que os solta.
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

# Caso 8: todo clique que chama script do jangada roda solto, senão a waybar
# congela o módulo enquanto a janela estiver aberta. --parar e toggle terminam
# na hora e ficam de fora.
presos="$(jq -r '[to_entries[] | .key as $m | .value | objects | to_entries[]
  | select(.key | test("^on-click")) | select(.value | type == "string")
  | select(.value | test("^\\$JANGADA_PATH/bin/"))
  | select(.value | test(" (--parar|toggle)$") | not) | "\($m).\(.key)"] | join(" ")' "$tmp/config.json")"
conferir "caso 8: nenhum clique que abre janela sem setsid -f ($presos)" [ -z "$presos" ]

# Caso 9: migração que solta os cliques na cópia própria.
migracao=migrations/202609281200-barra-cliques-soltos.sh
rm -f "$alvo.jangada-"*.bak
sed -E 's#setsid -f (\$JANGADA_PATH/bin/jangada-(calendario|rede|monitor))#\1#' default/waybar/config.jsonc >"$alvo"
conferir "caso 9: a barra de antes tem clique preso" grep -q '"on-click": "$JANGADA_PATH/bin/jangada-calendario"' "$alvo"
cp "$alvo" "$tmp/antes.jsonc"
JANGADA_SIMULAR=1 migrar
conferir "caso 9: simulação não altera o arquivo" iguais "$alvo" "$tmp/antes.jsonc"
conferir "caso 9: migração roda sem erro" migrar
conferir "caso 9: resultado igual ao padrão" iguais "$alvo" default/waybar/config.jsonc
conferir "caso 9: deixa uma cópia de segurança" \
  [ "$(compgen -G "$alvo.jangada-*.bak" | wc -l)" = 1 ]
conferir "caso 9: segunda passada roda sem erro" migrar
conferir "caso 9: segunda passada não muda nada" iguais "$alvo" default/waybar/config.jsonc
conferir "caso 9: segunda passada não faz outra cópia" \
  [ "$(compgen -G "$alvo.jangada-*.bak" | wc -l)" = 1 ]

# Caso 10: fonte e saída têm volumes independentes; preserve controles pessoais.
conferir "caso 10: microfone controla a fonte e mostra seu volume" \
  jq_ok '.["pulseaudio#microfone"] | .["tooltip-format"] == "{source_desc} · {source_volume}%"
    and (.["on-scroll-up"] | contains("@DEFAULT_AUDIO_SOURCE@"))
    and (.["on-scroll-down"] | contains("@DEFAULT_AUDIO_SOURCE@"))' "$tmp/config.json"
migracao=migrations/202609301900-barra-microfone.sh
python3 - "$tmp/config.json" "$alvo" <<'PY'
import json, sys
p = json.load(open(sys.argv[1]))
m = p['pulseaudio#microfone']
m.pop('on-scroll-up'); m.pop('on-scroll-down')
m['scroll-step'] = 5
m['tooltip-format'] = '{source_desc} · {volume}%'
json.dump(p, open(sys.argv[2], 'w'), ensure_ascii=False, indent=2)
PY
cp "$alvo" "$tmp/microfone-antes"
JANGADA_SIMULAR=1 migrar
conferir "caso 10: simulação preserva a barra" iguais "$alvo" "$tmp/microfone-antes"
conferir "caso 10: migra a configuração anterior" migrar
conferir "caso 10: configurações novas iguais ao padrão" \
  jq_ok --slurpfile p "$tmp/config.json" '.["pulseaudio#microfone"] | del(.["scroll-step"]) == $p[0]["pulseaudio#microfone"]' "$alvo"
cp "$alvo" "$tmp/microfone-depois"
conferir "caso 10: migração repetível" migrar
conferir "caso 10: segunda passada não muda nada" iguais "$alvo" "$tmp/microfone-depois"
printf '{"pulseaudio#microfone":{"on-scroll-up":"controle pessoal","tooltip-format":"pessoal"}}\n' >"$alvo"
cp "$alvo" "$tmp/microfone-pessoal"
conferir "caso 10: migração aceita configuração personalizada" migrar
conferir "caso 10: controles pessoais preservados" iguais "$alvo" "$tmp/microfone-pessoal"
printf '{"pulseaudio#microfone":{\n // comentário pessoal\n "tooltip-format":"{source_desc} · {volume}%%", /* volume */\n "scroll-step":5,\n}}\n' >"$alvo"
conferir "caso 10: migra JSONC com comentários e vírgula final" migrar
conferir "caso 10: preserva comentário de linha" grep -q '// comentário pessoal' "$alvo"
conferir "caso 10: preserva comentário de bloco" grep -q '/\* volume \*/' "$alvo"
conferir "caso 10: comentário não impede corrigir a dica" grep -q '{source_volume}' "$alvo"
conferir "caso 10: comentário não impede corrigir a rolagem" grep -q 'on-scroll-up' "$alvo"
cp "$alvo" "$tmp/microfone-comentado"
conferir "caso 10: JSONC comentado também é repetível" migrar
conferir "caso 10: comentários mantidos na segunda passada" iguais "$alvo" "$tmp/microfone-comentado"

# Caso 11: contrato K8 dos três módulos, sem consultar estado ou pacotes reais.
formato_waybar() {
  [[ "$(wc -l <"$1")" == 1 ]] &&
    jq_ok -s 'length == 1 and (.[0] | type == "object"
      and has("text") and has("tooltip") and has("class")
      and (.text | type == "string")
      and (.tooltip | type == "string")
      and (.class | type == "string"))' "$1"
}
printf '{"text":"","tooltip":"sistema em dia","class":"vazio"}\n' >"$tmp/vazio.json"
conferir "caso 11: texto vazio é saída válida" formato_waybar "$tmp/vazio.json"
printf '{"text":"","tooltip":"sistema em dia"}\n' >"$tmp/sem-classe.json"
if formato_waybar "$tmp/sem-classe.json"; then
  falha "caso 11: saída sem class foi aceita"
else
  ok "caso 11: saída sem class é rejeitada"
fi
cat "$tmp/vazio.json" "$tmp/vazio.json" >"$tmp/duas-linhas.json"
if formato_waybar "$tmp/duas-linhas.json"; then
  falha "caso 11: saída com duas linhas foi aceita"
else
  ok "caso 11: saída com duas linhas é rejeitada"
fi
mkdir -p "$tmp/modulos/bin" "$tmp/modulos/config/jangada" \
  "$tmp/modulos/state" "$tmp/modulos/cache" "$tmp/modulos/runtime"
printf 'JANGADA_PROJETOS=%s\n' "$tmp/modulos/projetos" >"$tmp/modulos/config/jangada/jangada.conf"
for comando in checkupdates paru yay tmux; do
  printf '#!/bin/sh\nexit 0\n' >"$tmp/modulos/bin/$comando"
  chmod +x "$tmp/modulos/bin/$comando"
done
for modulo in tarefas painel atualizacoes; do
  saida="$tmp/modulos/$modulo.json"
  if PATH="$tmp/modulos/bin:$PATH" XDG_CONFIG_HOME="$tmp/modulos/config" \
    XDG_STATE_HOME="$tmp/modulos/state" XDG_CACHE_HOME="$tmp/modulos/cache" \
    XDG_RUNTIME_DIR="$tmp/modulos/runtime" JANGADA_PATH="$repo_jangada" \
    "bin/jangada-$modulo" --waybar >"$saida" 2>"$tmp/modulos/$modulo.erro"; then
    conferir "caso 11: jangada-$modulo emite uma linha JSON com text, tooltip e class" \
      formato_waybar "$saida"
  else
    falha "caso 11: jangada-$modulo --waybar: $(cat "$tmp/modulos/$modulo.erro")"
  fi
done

if ((falhas)); then
  echo "$falhas teste(s) da barra falharam"
  exit 1
fi
echo "todos os testes da barra passaram"
