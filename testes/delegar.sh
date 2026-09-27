#!/usr/bin/env bash
# Testa o jangada-delegar com um agy falso no PATH: nada vai para a rede.
#
# Uso: testes/delegar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }
# jq -e em silêncio: redirecionar a linha do conferir calaria o ok e a FALHA.
jqok() { jq "$@" >/dev/null; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/home/.gemini/antigravity-cli/log" "$tmp/falso" "$tmp/projeto"

# O agy falso responde ao /usage com a cota de $FALSO_COTA (fração) e ao
# pedido com $FALSO_RESPOSTA. Grava os argumentos de cada chamada.
cat >"$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == agents ]]; then
  printf '%s\n' ${FALSO_AGENTES:-explorador leitor pesquisador verificador}
  exit 0
fi
if [[ "$2" == /usage ]]; then
  echo usage >>"$FALSO_DIR/usage.chamadas"
  [[ "${FALSO_USAGE_FALHA:-0}" == 1 ]] && exit 1
  printf '{"status":"SUCCESS","response":"","command":{"name":"usage","data":{"groups":[{"name":"Gemini Models","buckets":[{"id":"gemini-weekly","remaining_fraction":0.9},{"id":"gemini-5h","remaining_fraction":%s}]}]}}}\n' "$FALSO_COTA"
  exit 0
fi
printf '%s\n' "$@" >"$FALSO_DIR/agy.args"
pwd >"$FALSO_DIR/agy.pasta"
[[ -n "${FALSO_LOG:-}" ]] && echo "$FALSO_LOG" >"$HOME/.gemini/antigravity-cli/log/cli-1.log"
[[ "${FALSO_CODIGO:-0}" != 0 ]] && { echo "falha falsa" >&2; exit "$FALSO_CODIGO"; }
jq -n --arg r "$FALSO_RESPOSTA" --arg n "${FALSO_NEGADO:-}" \
  '{conversation_id: "c1", status: "SUCCESS", response: $r,
    denied_actions: (if $n == "" then [] else [{action: "read_url", display_name: $n}] end)}'
EOF
chmod +x "$tmp/bin/agy"
conf_agy="$tmp/home/.gemini/antigravity-cli/settings.json"
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"

delegar() {
  rm -f "$tmp/falso/agy.args"
  (cd "$tmp/projeto" && env -u JANGADA_DELEGAR -u XDG_CACHE_HOME -u XDG_STATE_HOME -u XDG_CONFIG_HOME \
    HOME="$tmp/home" PATH="$tmp/bin:$PATH" JANGADA_PATH="$repo_jangada" FALSO_DIR="$tmp/falso" \
    FALSO_COTA="${COTA:-0.9}" FALSO_RESPOSTA="${RESPOSTA-relatorio em a.sh:1}" \
    FALSO_CODIGO="${CODIGO:-0}" FALSO_NEGADO="${NEGADO:-}" FALSO_LOG="${LOG:-}" FALSO_USAGE_FALHA="${USAGE_FALHA:-0}" \
    ${AGENTES:+FALSO_AGENTES="$AGENTES"} \
    ${DELEGAR:+JANGADA_DELEGAR=$DELEGAR} \
    "$repo_jangada/bin/jangada-delegar" "$@" >"$tmp/saida" 2>"$tmp/erro")
  echo $? >"$tmp/codigo"
}
codigo() { cat "$tmp/codigo"; }

delegar explorador "mapeie"
conferir "caso 1: código 0" [ "$(codigo)" = 0 ]
conferir "caso 1: imprime o relatório" grep -qx "relatorio em a.sh:1" "$tmp/saida"
conferir "caso 1: agente do papel" grep -qx -- explorador "$tmp/falso/agy.args"
conferir "caso 1: Flash low para o explorador" grep -qx -- gemini-3.8-flash-low "$tmp/falso/agy.args"
conferir "caso 1: roda com --sandbox" grep -qx -- --sandbox "$tmp/falso/agy.args"
conferir "caso 1: roda na pasta atual" [ "$(cat "$tmp/falso/agy.pasta")" = "$tmp/projeto" ]

delegar verificador "confira"
conferir "caso 2: Flash high para o verificador" grep -qx -- gemini-3.8-flash-high "$tmp/falso/agy.args"
# Antes da primeira, depois de cada uma; o antes da segunda vem do cache.
conferir "caso 2: cota do antes vem do cache" [ "$(wc -l <"$tmp/falso/usage.chamadas")" = 3 ]
reg="$tmp/home/.local/state/jangada/delegacoes.jsonl"
conferir "caso 2: uma linha por chamada" [ "$(wc -l <"$reg")" = 2 ]
conferir "caso 2: linha com os campos" jqok -e 'select(.papel == "verificador")
  | .destino == "agy" and .modelo == "gemini-3.8-flash-high" and .codigo_saida == 0 and .recusa == false
    and .cota_antes == 90 and .cota_depois == 90 and .palavras == 3 and .tokens_retorno == 5
    and .conversa == "c1" and .pasta != "" and (.segundos | type) == "number"' "$reg"


rm -f "$tmp/home/.cache/jangada/agy-usage.json"
COTA=0.15 delegar leitor "leia"
conferir "caso 3: cota baixa recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 3: agy não é chamado" test ! -e "$tmp/falso/agy.args"
conferir "caso 3: diz a cota" grep -q "15%" "$tmp/erro"
conferir "caso 3: indica o subagente do Claude" grep -q "subagente leitor do Claude" "$tmp/saida"
conferir "caso 3: recusa registrada com o motivo" \
  jqok -se 'last | .recusa and .codigo_saida == 4 and (.motivo | test("15"))' "$reg"

rm -f "$tmp/home/.cache/jangada/agy-usage.json"
USAGE_FALHA=1 delegar leitor "leia"
conferir "caso 4: /usage falhou, recusa" [ "$(codigo)" = 4 ]

rm -f "$tmp/home/.cache/jangada/agy-usage.json"
CODIGO=1 delegar pesquisador "busque"
conferir "caso 5: agy falhou, recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 5: indica o subagente do Claude" grep -q "subagente pesquisador do Claude" "$tmp/saida"

LOG='Agent "explorador" not found, using default' delegar explorador "mapeie"
conferir "caso 6: agente não achado, recusa" [ "$(codigo)" = 4 ]
conferir "caso 6: diz o motivo" grep -q "não achou o agente" "$tmp/erro"
rm -f "$tmp/home/.gemini/antigravity-cli/log/cli-1.log"

RESPOSTA="$(yes palavra | head -n 700 | paste -sd ' ')" delegar explorador "mapeie"
conferir "caso 7: relatório longo sai cortado" [ "$(head -n 1 "$tmp/saida" | wc -w)" = 600 ]
arq="$(sed -n 's/.*completo em \(.*\)\]$/\1/p' "$tmp/saida")"
conferir "caso 7: arquivo completo existe" [ "$(wc -w <"${arq:-/nada}" 2>/dev/null)" = 700 ]

RESPOSTA="curto" delegar explorador "mapeie" --arquivo "$tmp/rel.md"
conferir "caso 8: --arquivo grava o relatório" grep -qx curto "$tmp/rel.md"

RESPOSTA="$(printf '%s\n' "# Um título comprido sem fonte nenhuma" "- a função está em bin/jangada-validar:82, perto do fim" \
  "- esta afirmação comprida não tem fonte alguma" "- a norma está em https://exemplo.org/norma, item 3")" \
  delegar leitor "leia"
conferir "caso 8b: conta as afirmações sem fonte" jqok -se 'last | .sem_fonte == 1' "$reg"

DELEGAR=claude delegar explorador "mapeie"
conferir "caso 9: perfil claude recusa sem chamar o agy" \
  bash -c '[ "$1" = 4 ] && [ ! -e "$2" ]' _ "$(codigo)" "$tmp/falso/agy.args"
conferir "caso 9: registrada com destino claude" jqok -se 'last | .destino == "claude" and .recusa' "$reg"
DELEGAR=nativo delegar explorador "mapeie"
conferir "caso 10: sessão do agy aponta o invoke_subagent" grep -q invoke_subagent "$tmp/erro"

RESPOSTA="" NEGADO=ReadUrlContent delegar pesquisador "busque"
conferir "caso 12: ação negada sem resposta recusa e diz o quê" \
  bash -c '[ "$1" = 4 ] && grep -q "negou ReadUrlContent" "$2"' _ "$(codigo)" "$tmp/erro"
NEGADO=ReadUrlContent delegar pesquisador "busque"
conferir "caso 13: ação negada com resposta avisa e entrega" \
  bash -c '[ "$1" = 0 ] && grep -q "negou: ReadUrlContent" "$2"' _ "$(codigo)" "$tmp/erro"
conferir "caso 13: pedido manda seguir depois da negação" grep -q "não pare" "$tmp/falso/agy.args"

# Pasta sem confiança do agy: recusa, sem confiar por conta própria.
jq '.trustedWorkspaces = []' "$conf_agy" >"$tmp/conf" && cp "$tmp/conf" "$conf_agy"
delegar explorador "mapeie"
conferir "caso 14: pasta sem confiança recusa sem chamar o agy" \
  bash -c '[ "$1" = 4 ] && [ ! -e "$2" ] && grep -q "não confia" "$3"' _ "$(codigo)" "$tmp/falso/agy.args" "$tmp/erro"
conferir "caso 14: o settings.json do agy fica como estava" jqok -e '.trustedWorkspaces == []' "$conf_agy"
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"

# Pasta confiada pelo caminho com link simbólico, como o agy grava quando foi
# aberta por ele.
ln -s "$tmp/projeto" "$tmp/atalho"
jq -n --arg w "$tmp/atalho" '{trustedWorkspaces: [$w]}' >"$conf_agy"
(cd "$tmp/atalho" && env -u JANGADA_DELEGAR -u XDG_CACHE_HOME -u XDG_STATE_HOME -u XDG_CONFIG_HOME \
  HOME="$tmp/home" PATH="$tmp/bin:$PATH" JANGADA_PATH="$repo_jangada" FALSO_DIR="$tmp/falso" \
  FALSO_COTA=0.9 FALSO_RESPOSTA="relatorio em a.sh:1" PWD="$tmp/atalho" \
  "$repo_jangada/bin/jangada-delegar" explorador "mapeie" >/dev/null 2>&1)
conferir "caso 14b: pasta confiada pelo link simbólico é aceita" [ $? = 0 ]
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"

# Papel que o agy não carregou: o agy rodaria o agente padrão.
AGENTES="leitor" delegar explorador "mapeie"
conferir "caso 15: papel ausente no agy recusa antes do pedido" \
  bash -c '[ "$1" = 4 ] && [ ! -e "$2" ] && grep -q "install.sh 50" "$3"' _ "$(codigo)" "$tmp/falso/agy.args" "$tmp/erro"

# Confiança no worktree (jangada-worktree-preparar e fim da sessão): a
# primeira alteração guarda o settings.json original, e só ela.
confianca() {
  env HOME="$tmp/home" XDG_STATE_HOME="$tmp/estado" JANGADA_PATH="$repo_jangada" \
    bash -c 'source "$1/bin/jangada-config"; jangada_agy_ajustar_confianca "$2" "$3"' _ "$repo_jangada" "$@"
}
echo '{"trustedWorkspaces": [], "outra": 1}' >"$conf_agy"
confianca adicionar "$tmp/projeto"
confianca adicionar "$tmp/falso"
confianca remover "$tmp/projeto"
conferir "caso 16: confiança adicionada e removida por caminho" \
  jqok -e --arg w "$(realpath "$tmp/falso")" '.trustedWorkspaces == [$w] and .outra == 1' "$conf_agy"
conferir "caso 16: cópia do settings.json de antes da primeira alteração" \
  jqok -e '.trustedWorkspaces == [] and .outra == 1' "$conf_agy.jangada-orig"
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"

delegar revisor "revise"
conferir "caso 11: papel desconhecido dá código 2" [ "$(codigo)" = 2 ]

echo
if ((falhas)); then
  echo "$falhas teste(s) falharam"
  exit 1
fi
echo "todos os testes do jangada-delegar passaram"
