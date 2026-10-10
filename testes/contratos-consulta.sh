#!/usr/bin/env bash
# Testa o contrato K4 (docs/modularizacao-3.0/03-contratos.md): as consultas
# jangada-agentes --lista, --lista-atualizada e --waybar não gravam nada no
# estado, e só --limpar-orfaos remove as sessões órfãs, com o mesmo critério
# de antes.
#
# Uso: testes/contratos-consulta.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
estado="$tmp/state/jangada/agentes"
mkdir -p "$estado" "$tmp/bin" "$tmp/home" "$tmp/config" "$tmp/pasta"

# O tmux falso só conhece a sessão "viva".
printf '#!/bin/sh\n[ "$*" != "${*#*list-sessions}" ] && echo viva\nexit 0\n' >"$tmp/bin/tmux"
chmod +x "$tmp/bin/tmux"

agora="$(date -Iseconds)"
morto="$(sh -c 'echo $$')"
jq -n --arg a "$agora" '{estado:"trabalhando", atualizado:$a}' >"$estado/viva.json"
jq -n --arg a "$agora" '{estado:"concluido", atualizado:$a}' >"$estado/concluida.json"
jq -n --arg a "$agora" --argjson p "$morto" '{estado:"trabalhando", pid:$p, atualizado:$a}' >"$estado/orfa.json"
jq -n '{estado:"concluido", atualizado:"2000-01-01T00:00:00+00:00"}' >"$estado/vencida.json"
jq -n --arg a "$agora" --arg d "$tmp/pasta" '{estado:"trabalhando", agente:"codex", dir:$d, atualizado:$a}' >"$estado/caida.json"

agentes() {
  env -u TMUX -u JANGADA_ISOLADO -u JANGADA_AGENTES_GUARDAR PATH="$tmp/bin:$PATH" HOME="$tmp/home" \
    XDG_STATE_HOME="$tmp/state" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
    "$repo_jangada/bin/jangada-agentes" "$@"
}

retrato() {
  (cd "$tmp/state" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum && find . | sort)
}

consultas=(--lista --lista-atualizada --waybar)
for opcao in "${consultas[@]}"; do
  antes="$(retrato)"
  agentes "$opcao" >"$tmp/antes$opcao" 2>&1
  conferir "$opcao sai com 0" [ "$?" -eq 0 ]
  conferir "$opcao não grava no estado" [ "$antes" == "$(retrato)" ]
done
conferir "a órfã continua no estado depois das consultas" test -e "$estado/orfa.json"
conferir "--lista mostra a sessão viva" grep -q $'^trabalhando\tviva\t' "$tmp/antes--lista"
conferir "--lista mostra a concluída dentro do prazo" grep -q $'^concluido\tconcluida\t' "$tmp/antes--lista"
conferir "--lista mostra a sessão que dá para restaurar" grep -q $'^interrompido\tcaida\t' "$tmp/antes--lista"
conferir "--lista tem só as três sessões" [ "$(cut -f2 "$tmp/antes--lista" | sort | tr '\n' ' ')" == "caida concluida viva " ]
conferir "--waybar conta as três sessões" \
  jq -e '.text == "󰚩 3  󰑮 1  󰄬 1  󰜺 1" and .class == "trabalhando" and (.tooltip | type) == "string"' "$tmp/antes--waybar" >/dev/null

conferir "--limpar-orfaos sai com 0" agentes --limpar-orfaos
conferir "--limpar-orfaos remove a órfã" test ! -e "$estado/orfa.json"
conferir "--limpar-orfaos remove a concluída vencida" test ! -e "$estado/vencida.json"
conferir "--limpar-orfaos mantém a sessão viva" test -e "$estado/viva.json"
conferir "--limpar-orfaos mantém a concluída dentro do prazo" test -e "$estado/concluida.json"
conferir "--limpar-orfaos marca como interrompida a sessão que dá para restaurar" \
  jq -e '.estado == "interrompido"' "$estado/caida.json" >/dev/null

# A órfã já não aparecia na consulta; sem ela no disco, a saída é a mesma. A
# marcação de interrompida regrava "atualizado", quarto campo da lista.
for opcao in "${consultas[@]}"; do
  agentes "$opcao" >"$tmp/depois$opcao" 2>&1
  conferir "$opcao sai com 0 depois da limpeza" [ "$?" -eq 0 ]
  conferir "$opcao igual antes e depois da limpeza" \
    cmp -s <(cut -f1-3,5- "$tmp/antes$opcao") <(cut -f1-3,5- "$tmp/depois$opcao")
done

if ((falhas)); then
  echo "$falhas falha(s)"
  exit 1
fi
echo "todos os testes do contrato de consulta passaram"
