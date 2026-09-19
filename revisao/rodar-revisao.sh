#!/bin/sh
# Revisão cruzada do jangada pelo Antigravity CLI (agy), sem interação.
#
# O agente lê os arquivos do repositório com as próprias ferramentas de
# leitura. No modo não interativo, as ferramentas que pedem aprovação (escrita,
# comandos) são recusadas automaticamente, então a revisão não altera nada:
# quem grava a resposta é este script.
#
# Uso (em qualquer pasta do repositório):
#   sh revisao/rodar-revisao.sh [-m modelo] [-e esforço] [-a área]
#
#   -m modelo   modelo do agy (padrão: o configurado no agy)
#   -e esforço  low, medium ou high (padrão: high)
#   -a área     revisa só uma parte: bin, install, default, config, testes...
#               (padrão: o repositório inteiro)
#
# Resultado: revisao/gemini-<data>.md (resposta), revisao/gemini-<data>.log
# (avisos) e revisao/gemini-<data>.json (resposta completa em JSON).
# Compatível com o sh do macOS e do Linux.
set -eu

modelo=""
esforco="high"
area=""
while getopts "m:e:a:h" opcao; do
  case "$opcao" in
    m) modelo="$OPTARG" ;;
    e) esforco="$OPTARG" ;;
    a) area="$OPTARG" ;;
    *) sed -n '2,20s/^# \{0,1\}//p' "$0"; exit 0 ;;
  esac
done

cd "$(dirname "$0")/.."

command -v agy >/dev/null 2>&1 || {
  echo "agy não encontrado. Instale com:"
  echo "  curl -fsSL https://antigravity.google/cli/install.sh | bash"
  exit 1
}

# O modo -p só grava a resposta corretamente fora de um terminal a partir da
# versão 1.1.8 (erros #318 e #408 do antigravity-cli).
versao="$(agy --version 2>/dev/null | grep -Eo '[0-9]+\.[0-9]+\.[0-9]+' | head -1 || true)"
if [ -n "$versao" ]; then
  menor="$(printf '%s\n%s\n' "$versao" "1.1.8" | sort -t. -k1,1n -k2,2n -k3,3n | head -1)"
  if [ "$menor" != "1.1.8" ]; then
    echo "agy $versao é anterior à 1.1.8 e pode não gravar a resposta; atualize o agy"
    exit 1
  fi
fi

data="$(date +%Y%m%d-%H%M)"
sufixo=""
[ -n "$area" ] && sufixo="-$area"
saida="revisao/gemini-$data$sufixo.md"
registro="revisao/gemini-$data$sufixo.log"
json="revisao/gemini-$data$sufixo.json"

# Lista de arquivos a revisar (menos as próprias revisões), para o agente não
# precisar rodar comandos, que seriam recusados no modo não interativo.
if [ -n "$area" ]; then
  arquivos="$(git ls-files -- "$area" | grep -v '^revisao/gemini-' || true)"
  [ -n "$arquivos" ] || { echo "nenhum arquivo versionado em: $area"; exit 1; }
  escopo="Revise apenas os arquivos da lista abaixo (área \"$area\"). Consulte os demais só para entender o contexto."
else
  arquivos="$(git ls-files | grep -v '^revisao/gemini-')"
  escopo="Revise todos os arquivos da lista abaixo, sem pular bin/ e install/."
fi

prompt="$(cat revisao/PROMPT_GEMINI.md)

## Como trabalhar nesta execução

1. Os arquivos NÃO foram colados nesta mensagem: leia cada um com a sua
   ferramenta de leitura de arquivos, a partir da raiz do repositório.
2. $escopo
3. Não altere, crie nem apague arquivos, e não execute comandos. Esta
   execução é só de leitura; a sua resposta será gravada por um script.
4. Responda apenas com o texto da revisão em Markdown, no formato pedido acima,
   começando pela linha: # Revisão do jangada ($data)

## Arquivos

$arquivos"

set -- -p "$prompt" --output-format json --effort "$esforco"
[ -n "$modelo" ] && set -- "$@" --model "$modelo"

echo "revisando $(printf '%s\n' "$arquivos" | wc -l | tr -d ' ') arquivos com o agy ${modelo:+(modelo $modelo)}..."
echo "isso pode levar alguns minutos"

if ! agy "$@" </dev/null >"$json" 2>"$registro"; then
  echo "o agy terminou com erro; veja $registro"
  tail -5 "$registro"
  exit 1
fi

# Extrai status e resposta do JSON. Usa jq se existir; senão, python3.
extrair() {
  if command -v jq >/dev/null 2>&1; then
    jq -r "$1 // empty" "$json" 2>/dev/null
  else
    python3 - "$json" "$1" <<'PY'
import json, sys
texto = open(sys.argv[1], encoding="utf-8").read()
inicio = texto.find("{")
dados = json.loads(texto[inicio:]) if inicio >= 0 else {}
chave = sys.argv[2].lstrip(".")
valor = dados.get(chave)
print(valor if valor is not None else "")
PY
  fi
}

status="$(extrair .status || true)"
if [ "$status" != "SUCCESS" ]; then
  echo "o agy não concluiu (status: ${status:-desconhecido}); veja $json e $registro"
  exit 1
fi

extrair .response >"$saida"
if [ ! -s "$saida" ]; then
  echo "o agy concluiu, mas a resposta veio vazia; veja $registro"
  exit 1
fi

echo "revisão gravada em $saida (JSON completo em $json)"
grep -c '^### ' "$saida" | sed 's/^/apontamentos: /' || true
