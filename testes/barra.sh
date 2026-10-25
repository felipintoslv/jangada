#!/usr/bin/env bash
# Testa a configuração da barra: a ordem dos módulos e a retirada do
# custom/indicadores e do custom/catamara, no config.jsonc e na barra em pé
# gerada pelo jangada-barra; os cliques que abrem janela com setsid -f e a
# migração que os solta.
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

# Caso 1: ordem dos módulos da barra deitada, sem o custom/catamara nem o
# custom/indicadores, cujos comandos saíram do padrão.
conferir "caso 1: módulos da esquerda na ordem, com as áreas de trabalho logo depois do menu" \
  jq_ok '.["modules-left"] == ["custom/menu", "hyprland/workspaces", "custom/agentes", "hyprland/window"]' "$tmp/config.json"
conferir "caso 1: módulos do centro e da direita na ordem" \
  jq_ok '.["modules-center"] == ["clock"] and .["modules-right"] == ["tray", "custom/atualizacoes",
    "systemd-failed-units", "privacy", "idle_inhibitor", "cpu", "memory", "temperature", "disk",
    "network", "bluetooth", "pulseaudio", "pulseaudio#microfone", "battery", "custom/sessao"]' "$tmp/config.json"
conferir "caso 1: sem custom/catamara na barra deitada" \
  jq_ok '(has("custom/catamara") | not) and ([.[] | arrays | index("custom/catamara")] | all(. == null))' "$tmp/config.json"
conferir "caso 1: sem custom/indicadores na barra deitada" \
  jq_ok '(has("custom/indicadores") | not) and ([.[] | arrays | index("custom/indicadores")] | all(. == null))' "$tmp/config.json"
conferir "caso 1: sem custom/indicadores no base.css e no jangada-barra" \
  bash -c '! grep -q indicadores default/waybar/base.css bin/jangada-barra'
conferir "caso 1: sem Catamarã no padrão da barra nem no jangada-barra" \
  bash -c '! grep -qi catamar default/waybar/config.jsonc default/waybar/base.css bin/jangada-barra'

# Caso 3: barra em pé gerada pelo jangada-barra, com waybar e pkill falsos.
mkdir -p "$tmp/bin" "$tmp/config/jangada"
printf '#!/bin/sh\nexit 1\n' >"$tmp/bin/pkill"
printf '#!/bin/sh\nprintf "%%s" "$XDG_DATA_DIRS" >"$FALSO_DADOS"\n' >"$tmp/bin/waybar"
chmod +x "$tmp/bin/"*
echo "JANGADA_BARRA_POSICAO=esquerda" >"$tmp/config/jangada/jangada.conf"
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
  FALSO_DADOS="$tmp/dados" JANGADA_PATH="$repo_jangada" bin/jangada-barra 2>"$tmp/erro-barra" || falha "caso 3: jangada-barra: $(cat "$tmp/erro-barra")"
gerado="$tmp/state/jangada/waybar/borda.jsonc"
if [[ -f "$gerado" ]]; then
  sem_comentario "$gerado" >"$tmp/borda.json"
  conferir "caso 3: borda.jsonc é JSON" jq_ok . "$tmp/borda.json"
  conferir "caso 3: barra em pé com os mesmos módulos da deitada, sem custom/catamara nem custom/indicadores" \
    jq_ok '.["modules-left"] == ["custom/menu", "hyprland/workspaces", "custom/agentes"]
      and has("custom/indicadores") == false and has("custom/catamara") == false' "$tmp/borda.json"
  conferir "caso 3: barra em pé sem o Samburá, aposentado" \
    jq_ok '.["modules-left"] | index("custom/sambura") == null' "$tmp/borda.json"
else
  falha "caso 3: jangada-barra não gerou $gerado"
fi

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
migrar() { XDG_CONFIG_HOME="$tmp/m" JANGADA_PATH="$repo_jangada" bash "$migracao" >/dev/null 2>&1; }
alvo="$tmp/m/jangada/waybar/config.jsonc"
mkdir -p "$(dirname "$alvo")"
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
  [[ -x "bin/jangada-$modulo" ]] || continue
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

# Caso 12: sobreposição por nome e tamanho, sem fixar os estados do Fcitx5.
icones="$tmp/state/jangada/waybar/icones"
for ambiente in ausente vazio; do
  if [[ "$ambiente" == ausente ]]; then
    dados_ambiente=(env -u XDG_DATA_DIRS)
  else
    dados_ambiente=(env XDG_DATA_DIRS=)
  fi
  PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
    FALSO_DADOS="$tmp/dados" JANGADA_PATH="$repo_jangada" \
    "${dados_ambiente[@]}" bin/jangada-barra 2>"$tmp/erro-barra" || falha "caso 12: variável $ambiente"
  conferir "caso 12: variável $ambiente usa a busca padrão com a sobreposição" \
    [ "$(cat "$tmp/dados")" = "/usr/local/share:$icones:/usr/share" ]
done
for tema in breeze breeze-dark; do
  indice="/usr/share/icons/$tema/index.theme"
  [[ -f "$indice" ]] || continue
  conferir "caso 12: $tema mantém o índice original" \
    [ "$(readlink "$icones/icons/$tema/index.theme")" = "$indice" ]
  conferir "caso 12: $tema substitui só o teclado de 32px" \
    [ "$(readlink "$icones/icons/$tema/devices/32/input-keyboard-symbolic.svg")" = \
      "$repo_jangada/default/waybar/icones/input-keyboard-symbolic.svg" ]
done
if [[ -f /usr/share/icons/breeze/index.theme || -f /usr/share/icons/breeze-dark/index.theme ]]; then
  mkdir -p "$tmp/falha-state/jangada/waybar"
  touch "$tmp/falha-state/jangada/waybar/icones"
  if PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/falha-state" \
    FALSO_DADOS="$tmp/dados-falha" JANGADA_PATH="$repo_jangada" \
    bin/jangada-barra 2>"$tmp/erro-barra"; then
    falha "caso 12: erro na criação da sobreposição deveria interromper o lançador"
  else
    conferir "caso 12: erro na sobreposição não inicia Waybar com busca incompleta" \
      [ ! -e "$tmp/dados-falha" ]
  fi
fi
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
  XDG_DATA_DIRS="$tmp/pessoal:/usr/local/share:/usr/share" FALSO_DADOS="$tmp/dados" \
  JANGADA_PATH="$repo_jangada" bin/jangada-barra 2>"$tmp/erro-barra" || falha "caso 12: jangada-barra"
conferir "caso 12: caminhos pessoais precedem a sobreposição" \
  [ "$(cat "$tmp/dados")" = "$tmp/pessoal:/usr/local/share:$icones:/usr/share" ]
PATH="$tmp/bin:$PATH" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" \
  XDG_DATA_DIRS="$tmp/pessoal" FALSO_DADOS="$tmp/dados" \
  JANGADA_PATH="$repo_jangada" bin/jangada-barra 2>"$tmp/erro-barra" || falha "caso 12: caminho exclusivo"
conferir "caso 12: busca exclusiva do usuário permanece exclusiva" \
  [ "$(cat "$tmp/dados")" = "$tmp/pessoal" ]
conferir "caso 12: recurso simbólico e estados preservados" python3 testes/teclado-waybar.py

conferir "caso 13: barra sem o Samburá e migração preserva configurações pessoais" \
  python3 testes/sambura-retirada.py

if ((falhas)); then
  echo "$falhas teste(s) da barra falharam"
  exit 1
fi
echo "todos os testes da barra passaram"
