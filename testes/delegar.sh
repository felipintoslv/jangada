#!/usr/bin/env bash
# Testa o jangada-delegar com um agy falso no PATH: nada vai para a rede.
#
# Uso: testes/delegar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
source "$repo_jangada/bin/jangada-config"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }
# jq -e em silêncio: redirecionar a linha do conferir calaria o ok e a FALHA.
jqok() { jq "$@" >/dev/null; }

tmp="$(mktemp -d)"
pid_ollama=""
limpar() {
  [[ -n "$pid_ollama" ]] && kill "$pid_ollama" 2>/dev/null || true
  rm -rf "$tmp"
}
trap limpar EXIT
mkdir -p "$tmp/bin" "$tmp/home/.gemini/antigravity-cli/log" "$tmp/falso" "$tmp/projeto"

# O agy falso responde ao /usage com a cota de $FALSO_COTA (fração) e ao
# pedido com $FALSO_RESPOSTA. Grava os argumentos de cada chamada.
cat >"$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == agents ]]; then
  printf '%s\n' ${FALSO_AGENTES:-explorador leitor pesquisador verificador auditor arquiteto otimizador redator}
  exit 0
fi
if [[ "$2" == /usage ]]; then
  echo usage >>"$FALSO_DIR/usage.chamadas"
  if [[ -n "${FALSO_ESPERA_USAGE:-}" ]]; then
    trap '' TERM
    sleep "$FALSO_ESPERA_USAGE"
  fi
  [[ "${FALSO_USAGE_FALHA:-0}" == 1 ]] && exit 1
  printf '{"status":"SUCCESS","response":"","command":{"name":"usage","data":{"groups":[{"name":"Gemini Models","buckets":[{"id":"gemini-weekly","remaining_fraction":0.9},{"id":"gemini-5h","remaining_fraction":%s}]}]}}}\n' "$FALSO_COTA"
  exit 0
fi
printf '%s\n' "$@" >"$FALSO_DIR/agy.args"
printf '%s\n' "${TMPDIR:-/tmp}" >"$FALSO_DIR/temporario"
printf '%s\n' "$$" >"$FALSO_DIR/agy.pid"
if [[ "${FALSO_IGNORAR_TERM:-0}" == 1 ]]; then
  trap '' TERM
fi
if [[ -n "${FALSO_ESPERA:-}" ]]; then
  sleep "$FALSO_ESPERA" &
  espera_pid=$!
  printf '%s\n' "$espera_pid" >"$FALSO_DIR/filho.pid"
  wait "$espera_pid"
fi
printf '%s\n' "${JANGADA_AGY_PAPEL:-}" >"$FALSO_DIR/agy.papel"
pwd >"$FALSO_DIR/agy.pasta"
[[ -n "${FALSO_LOG:-}" ]] && echo "$FALSO_LOG" >"$HOME/.gemini/antigravity-cli/log/cli-1.log"
[[ "${FALSO_CODIGO:-0}" != 0 ]] && { echo "falha falsa" >&2; exit "$FALSO_CODIGO"; }
jq -n --arg r "$FALSO_RESPOSTA" --arg n "${FALSO_NEGADO:-}" \
  '{conversation_id: "c1", status: "SUCCESS", response: $r,
    denied_actions: (if $n == "" then [] else [{action: "read_url", display_name: $n}] end)}'
EOF
chmod +x "$tmp/bin/agy"
cat >"$tmp/bin/nvidia-smi" <<'EOF'
#!/bin/sh
if [ "${FALSO_SEM_VRAM:-0}" = "1" ]; then
  exit 1
fi
if [ "${FALSO_SEM_VRAM:-0}" = "2" ]; then
  echo "NVIDIA-SMI has failed because it couldn't communicate with the NVIDIA driver."
  exit 1
fi
echo "${FALSO_VRAM:-8000}"
EOF
chmod +x "$tmp/bin/nvidia-smi"
cat >"$tmp/bin/pgrep" <<'EOF'
#!/bin/sh
if [ -n "${FALSO_JOGO_ATIVO:-}" ] || [ -f "${FALSO_DIR:-}/jogo-ativo" ]; then
  for arg in "$@"; do
    if [ "$arg" = "reaper SteamLaunch" ]; then
      echo 9999
      exit 0
    fi
  done
fi
exit 1
EOF
chmod +x "$tmp/bin/pgrep"
conf_agy="$tmp/home/.gemini/antigravity-cli/settings.json"
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"
mkdir -p "$tmp/home/.gemini/config"
sed "s|@JANGADA_PATH@|$repo_jangada|g" default/agy/hooks.json >"$tmp/home/.gemini/config/hooks.json"

delegar() {
  rm -f "$tmp/falso/agy.args"
  (cd "$tmp/projeto" && env -u JANGADA_DELEGAR -u JANGADA_ISOLADO -u XDG_CACHE_HOME -u XDG_STATE_HOME -u XDG_CONFIG_HOME \
    -u JANGADA_DELEGAR_ROTEAMENTO_ID -u JANGADA_DELEGAR_TENTATIVAS -u JANGADA_DELEGAR_CHAMADAS_RESTANTES \
    HOME="$tmp/home" PATH="$tmp/bin:$PATH" JANGADA_PATH="$repo_jangada" FALSO_DIR="$tmp/falso" \
    FALSO_COTA="${COTA:-0.9}" FALSO_RESPOSTA="${RESPOSTA-relatorio em a.sh:1}" \
    FALSO_CODIGO="${CODIGO:-0}" FALSO_NEGADO="${NEGADO:-}" FALSO_LOG="${LOG:-}" FALSO_USAGE_FALHA="${USAGE_FALHA:-0}" \
    ${AGENTES:+FALSO_AGENTES="$AGENTES"} \
    ${DELEGAR:+JANGADA_DELEGAR=$DELEGAR} \
    ${AGENTE:+JANGADA_AGENTE=$AGENTE} \
    ${CHAMADAS_MAX:+JANGADA_DELEGAR_CHAMADAS_MAX=$CHAMADAS_MAX} \
    ${TEMPO_TOTAL:+JANGADA_DELEGAR_TEMPO_TOTAL=$TEMPO_TOTAL} \
    ${ESPERA_AGY:+FALSO_ESPERA=$ESPERA_AGY} \
    ${IGNORAR_TERM:+FALSO_IGNORAR_TERM=$IGNORAR_TERM} \
    ${ESPERA_USAGE:+FALSO_ESPERA_USAGE=$ESPERA_USAGE} \
    ${FALSO_JOGO_ATIVO:+FALSO_JOGO_ATIVO="$FALSO_JOGO_ATIVO"} \
    ${FALSO_VRAM:+FALSO_VRAM="$FALSO_VRAM"} \
    ${SEM_VRAM:+FALSO_SEM_VRAM="$SEM_VRAM"} \
    ${ISOLADO:+JANGADA_ISOLADO="$ISOLADO"} \
    ${LOCAL_IGNORAR_VRAM:+JANGADA_LOCAL_IGNORAR_VRAM="$LOCAL_IGNORAR_VRAM"} \
    ${OLLAMA_URL:+JANGADA_OLLAMA_URL="$OLLAMA_URL"} \
    ${LOCAL_MODELO:+JANGADA_LOCAL_MODELO="$LOCAL_MODELO"} \
    ${LOCAL_CTX:+JANGADA_LOCAL_CTX="$LOCAL_CTX"} \
    ${LOCAL_VRAM_MIN:+JANGADA_LOCAL_VRAM_MIN="$LOCAL_VRAM_MIN"} \
    ${LOCAL_ESPERA:+JANGADA_LOCAL_ESPERA="$LOCAL_ESPERA"} \
    ${LOCAL_FATIAS_MAX:+JANGADA_LOCAL_FATIAS_MAX="$LOCAL_FATIAS_MAX"} \
    "$repo_jangada/bin/jangada-delegar" "$@" >"$tmp/saida" 2>"$tmp/erro")
  echo $? >"$tmp/codigo"
}
codigo() { cat "$tmp/codigo"; }

delegar explorador "mapeie"
conferir "caso 1: código 0" [ "$(codigo)" = 0 ]
conferir "caso 1: imprime o relatório" grep -qx "relatorio em a.sh:1" "$tmp/saida"
conferir "caso 1: o agy recebe o papel, que o hook do leitor lê" grep -qx explorador "$tmp/falso/agy.papel"
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

# O worktree só herda a confiança do repositório principal: com a raiz fora
# do trustedWorkspaces, o jangada-worktree-preparar não confia no worktree.
git init --quiet "$tmp/raiz"
git -C "$tmp/raiz" -c user.name=t -c user.email=t@t commit --quiet --allow-empty -m inicio
git -C "$tmp/raiz" worktree add --quiet -b agente/t "$tmp/wt"
preparar() {
  env HOME="$tmp/home" XDG_STATE_HOME="$tmp/estado" JANGADA_PATH="$repo_jangada" \
    "$repo_jangada/bin/jangada-worktree-preparar" "$tmp/raiz" "$tmp/wt" </dev/null >"$tmp/saida-preparar" 2>&1
}
echo '{"trustedWorkspaces": []}' >"$conf_agy"
preparar
conferir "caso 17: raiz sem confiança, worktree sem confiança" jqok -e '.trustedWorkspaces == []' "$conf_agy"
conferir "caso 17: avisa que o worktree fica sem confiança" grep -q "fica sem confiança" "$tmp/saida-preparar"
jq -n --arg w "$(realpath "$tmp/raiz")" '{trustedWorkspaces: [$w]}' >"$conf_agy"
preparar
conferir "caso 17: raiz confiável, worktree confiável" \
  jqok -e --arg w "$(realpath "$tmp/wt")" '.trustedWorkspaces | index($w)' "$conf_agy"
jq -n --arg w "$(realpath "$tmp/projeto")" '{trustedWorkspaces: [$w]}' >"$conf_agy"

# O leitor sem o jangada-hook-leitor no agy teria no terminal o
# permissions.allow do usuário inteiro.
jq 'del(.jangada.PreToolUse)' "$tmp/home/.gemini/config/hooks.json" >"$tmp/h" && cp "$tmp/h" "$tmp/home/.gemini/config/hooks.json"
delegar leitor "leia"
conferir "caso 18: leitor sem o hook no agy recusa antes do pedido" \
  bash -c '[ "$1" = 4 ] && [ ! -e "$2" ] && grep -q "hook do leitor" "$3"' _ "$(codigo)" "$tmp/falso/agy.args" "$tmp/erro"
delegar explorador "mapeie"
conferir "caso 18: os outros papéis não dependem do hook" [ "$(codigo)" = 0 ]
sed "s|@JANGADA_PATH@|$repo_jangada|g" default/agy/hooks.json >"$tmp/home/.gemini/config/hooks.json"

delegar revisor "revise"
conferir "caso 11: papel desconhecido dá código 2" [ "$(codigo)" = 2 ]

# ==============================================================================
# Destino local (Ollama)
# ==============================================================================
echo "teste de conteudo" >"$tmp/projeto/doc1.txt"

# 1. Papel não permitido (explorador)
delegar --destino local explorador "mapeie" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 19: destino local recusa papel não permitido (código 4)" [ "$(codigo)" = 4 ]
conferir "caso 19: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]
conferir "caso 19: erro indica papéis leitor e redator" grep -q "só aceita os papéis leitor e redator" "$tmp/erro"
conferir "caso 19: recusa registrada com destino local" \
  jqok -se 'last | .destino == "local" and .papel == "explorador" and .codigo_saida == 4 and .recusa == true' "$reg"

# 2. Sem --arquivos
delegar --destino local leitor "leia"
conferir "caso 20: destino local sem --arquivos dá código 2" [ "$(codigo)" = 2 ]

# 3. Arquivo inexistente
delegar --destino local leitor "leia" --arquivos "$tmp/projeto/inexistente.txt"
conferir "caso 21: arquivo inexistente recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 21: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 4. Ollama fora do ar
OLLAMA_URL="http://127.0.0.1:1" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 22: Ollama fora do ar recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 22: erro indica Ollama fora do ar" grep -q "Ollama fora do ar" "$tmp/erro"
conferir "caso 22: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# Servidor Ollama falso
cat >"$tmp/servidor_ollama.py" <<'EOF'
import http.server, socketserver, json, sys, os

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass

    def do_GET(self):
        if self.path == '/api/tags':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            modelos = sys.argv[1].split()
            data = {"models": [{"name": m, "model": m} for m in modelos]}
            self.wfile.write(json.dumps(data).encode())
        elif self.path == '/api/ps':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            try:
                with open(sys.argv[5], 'r') as pf:
                    data = json.load(pf)
            except Exception:
                data = {"models": []}
            self.wfile.write(json.dumps(data).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        if self.path == '/api/chat':
            length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(length)
            with open(sys.argv[2], 'a') as f:
                f.write(body.decode('utf-8') + '\n')
            with open(sys.argv[3], 'r') as f:
                conteudo = f.read()
            eval_in = 120
            if os.path.exists(sys.argv[6]):
                try:
                    payload = json.loads(body.decode('utf-8'))
                    eval_in = payload.get('options', {}).get('num_ctx', 8192)
                except Exception:
                    eval_in = 8192
            resp = {
                "model": "qwen3:4b",
                "message": {"role": "assistant", "content": conteudo},
                "prompt_eval_count": eval_in,
                "eval_count": 45,
                "done": True
            }
            if os.path.exists(sys.argv[3] + '.limite'):
                resp['done_reason'] = 'length'
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(resp).encode())
        else:
            self.send_response(404)
            self.end_headers()

httpd = socketserver.TCPServer(('127.0.0.1', int(sys.argv[4])), Handler)
httpd.serve_forever()
EOF

porta_ollama="$(python3 -c 'import socket; s=socket.socket(); s.bind(("127.0.0.1", 0)); print(s.getsockname()[1]); s.close()')"
ollama_reqs="$tmp/ollama.reqs"
ollama_resp="$tmp/ollama.resp"
ollama_ps="$tmp/ollama.ps"
ollama_estouro="$tmp/ollama.estouro"
printf '%s\n' "doc1.txt:1: trecho relevante extraido do arquivo." >"$ollama_resp"
: >"$ollama_reqs"
printf '{"models": []}\n' >"$ollama_ps"

python3 "$tmp/servidor_ollama.py" "qwen3:4b modelo-simples" "$ollama_reqs" "$ollama_resp" "$porta_ollama" "$ollama_ps" "$ollama_estouro" &
pid_ollama=$!

for _ in {1..20}; do
  if curl -s "http://127.0.0.1:$porta_ollama/api/tags" >/dev/null 2>&1; then break; fi
  sleep 0.1
done

# 5. Modelo ausente
LOCAL_MODELO="modelo_inexistente" OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 23: modelo ausente recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 23: indica modelo não encontrado" grep -q "modelo_inexistente não encontrado" "$tmp/erro"
conferir "caso 23: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 6. Jogo aberto (simulado com marcador no pgrep falso)
FALSO_JOGO_ATIVO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 24: jogo aberto recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 24: indica jogo aberto" grep -q "jogo aberto" "$tmp/erro"
conferir "caso 24: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 7. Memória livre insuficiente (nvidia-smi falso retorna 1000 MiB)
FALSO_VRAM=1000 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 25: memória livre insuficiente recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 25: indica memória livre insuficiente" grep -q "memória de vídeo livre insuficiente" "$tmp/erro"
conferir "caso 25: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 8. Vaga ocupada (flock)
trava_local="$tmp/home/.local/state/jangada/local.lock"
mkdir -p "${trava_local%/*}"
(
  exec {tfd}>"$trava_local"
  flock -x "$tfd"
  sleep 4
) &
pid_trava=$!
sleep 0.2
LOCAL_ESPERA=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
kill "$pid_trava" 2>/dev/null || true
wait "$pid_trava" 2>/dev/null || true
conferir "caso 26: vaga ocupada recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 26: indica vaga ocupada" grep -q "vaga ocupada" "$tmp/erro"
conferir "caso 26: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 9. Sucesso: papel leitor e --arquivos
: >"$ollama_reqs"
printf '%s\n' "doc1.txt:1: informacao encontrada com sucesso." >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia este trecho" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 27: código 0 no destino local" [ "$(codigo)" = 0 ]
conferir "caso 27: imprime o relatório retornado" grep -q "doc1.txt:1:" "$tmp/saida"
conferir "caso 27: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]
conferir "caso 27: registro com destino local e tokens Ollama" \
  jqok -se 'last | .destino == "local" and .codigo_saida == 0 and .tokens_local_entrada == 120 and .tokens_local_saida == 45 and .sem_fonte == 0 and .modelo == "qwen3:4b"' "$reg"

# 10. Sucesso: papel redator
printf '%s\n' "doc1.txt:1: remover termo de enchimento." >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local redator "revise este trecho" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 28: redator no destino local código 0" [ "$(codigo)" = 0 ]
conferir "caso 28: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 11. Afirmações sem fonte
printf '%s\n' "Esta frase possui mais de vinte e cinco caracteres mas nao tem fonte." >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 29: conta afirmações sem fonte no destino local" \
  jqok -se 'last | .destino == "local" and .sem_fonte == 1' "$reg"

# 11b. Filtragem de tags think na mesma linha
printf '%s\n' "<think>raciocinio interno</think>doc1.txt:1: trecho util extraido." >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 29b: tags think na mesma linha sao filtradas" [ "$(codigo)" = 0 ]
conferir "caso 29b: mantem o texto util da linha" grep -q "doc1.txt:1: trecho util extraido." "$tmp/saida"
conferir "caso 29b: remove a tag think" [ "$(grep -c "<think>" "$tmp/saida" || true)" -eq 0 ]

# 12. Fatiamento de documento maior que o contexto
doc_grande="$tmp/projeto/doc_grande.txt"
: >"$doc_grande"
for i in {1..8}; do
  printf 'Linha %02d com texto suficiente para ocupar caracteres e testar o fatiamento de blocos.\n' "$i" >>"$doc_grande"
done
: >"$ollama_reqs"
printf '%s\n' "doc_grande.txt:1: resumo da fatia." >"$ollama_resp"
LOCAL_CTX=2100 LOCAL_FATIAS_MAX=5 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "resuma tudo" --arquivos "$doc_grande"
conferir "caso 30: documento fatiado termina com código 0" [ "$(codigo)" = 0 ]
conferir "caso 30: executou fatias mais passada de consolidação" [ "$(wc -l <"$ollama_reqs")" -ge 3 ]
chamadas_fatiadas="$(wc -l <"$ollama_reqs")"
conferir "caso 30: todas as 8 linhas numeradas aparecem nas fatias" \
  bash -c 'for i in {1..8}; do grep -q "doc_grande\.txt:$i: Linha 0$i" "$1" || exit 1; done' _ "$ollama_reqs"
conferir "caso 30: passada final de consolidação executada" grep -q "Consolide os resumos" <(tail -n1 "$ollama_reqs")
conferir "caso 30: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 13. Documento excede limite de fatias (JANGADA_LOCAL_FATIAS_MAX)
LOCAL_FATIAS_MAX=2 LOCAL_CTX=2100 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "resuma tudo" --arquivos "$doc_grande"
conferir "caso 31: documento excedendo fatias máximas recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 31: erro indica fatias máximas" grep -q "documento muito grande para o modelo local" "$tmp/erro"
conferir "caso 31: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]

# 14. Modelo residente no Ollama (/api/ps) permite chamada mesmo com VRAM livre baixa
printf '{"models": [{"name": "qwen3:4b", "size_vram": 3774873600}]}\n' >"$ollama_ps"
FALSO_VRAM=1000 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia com modelo residente" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 32: modelo residente permite chamada com pouca memória livre" [ "$(codigo)" = 0 ]
conferir "caso 32: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]
printf '{"models": []}\n' >"$ollama_ps"

# 15. Perfil DELEGAR=claude recusa qualquer delegação
DELEGAR=claude OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 33: JANGADA_DELEGAR=claude recusa --destino local" [ "$(codigo)" = 4 ]
conferir "caso 33: erro indica recusa do perfil" grep -q "não delega ao agy nem ao destino local" "$tmp/erro"
conferir "caso 33: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]
DELEGAR=claude delegar --destino agy explorador "explore"
conferir "caso 33b: JANGADA_DELEGAR=claude recusa --destino agy" [ "$(codigo)" = 4 ]
conferir "caso 33b: erro indica recusa do perfil" grep -q "não delega ao agy nem ao destino local" "$tmp/erro"

# 16. DELEGAR=local sem flag --destino resolve para local
DELEGAR=local OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "leia sem destino explicito" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 34: JANGADA_DELEGAR=local sem --destino chama local" [ "$(codigo)" = 0 ]
conferir "caso 34: gravou destino local no registro" jqok -se 'last | .destino == "local"' "$reg"

# 17. jangada_delegacao aceita local
conferir "caso 35: jangada_delegacao aceita local para claude" [ "$(jangada_delegacao claude local)" = "local" ]
conferir "caso 35: jangada_delegacao mantém nativo para agy" [ "$(jangada_delegacao agy local)" = "nativo" ]

# 18. Destino inválido
delegar --destino inexistente leitor "leia"
conferir "caso 36: --destino inválido dá código 2" [ "$(codigo)" = 2 ]
conferir "caso 36: erro indica destino inválido" grep -q "destino inválido" "$tmp/erro"

# 19. Linha única gigante é fatiada
doc_linha_gigante="$tmp/projeto/doc_linha_gigante.txt"
python3 -c 'print("a" * 1500)' >"$doc_linha_gigante"
LOCAL_CTX=2100 LOCAL_FATIAS_MAX=10 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia gigante" --arquivos "$doc_linha_gigante"
conferir "caso 37: linha única gigante é fatiada com sucesso" [ "$(codigo)" = 0 ]
conferir "caso 37: pedaços seguintes da linha gigante mantêm prefixo" grep -q "doc_linha_gigante.txt:1: a" "$ollama_reqs"

# 19b. Caminho longo com prefixo grande e contexto pequeno
pasta_longa="$tmp/projeto/caminho_$(printf 'longo_%.0s' {1..12})"
mkdir -p "$pasta_longa"
doc_longo="$pasta_longa/doc.txt"
python3 -c 'print("b" * 600)' >"$doc_longo"
LOCAL_CTX=2060 LOCAL_FATIAS_MAX=10 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia caminho longo" --arquivos "$doc_longo"
conferir "caso 37b: caminho longo com prefixo grande não entra em laço infinito" [ "$(codigo)" = 0 ]

# 20. Truncamento de contexto detectado
touch "$ollama_estouro"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia estouro" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 38: truncamento de contexto recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 38: erro indica contexto estourado" grep -q "contexto do modelo local estourado" "$tmp/erro"
conferir "caso 38: agy não é chamado" [ ! -e "$tmp/falso/agy.args" ]
rm -f "$ollama_estouro"

# 21. PDF extraído com pdftotext e numeração de páginas
cat >"$tmp/bin/pdftotext" <<'EOF'
#!/bin/sh
printf 'Texto de pagina um\n\fTexto de pagina dois\n'
EOF
chmod +x "$tmp/bin/pdftotext"
touch "$tmp/projeto/documento.pdf"
: >"$ollama_reqs"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia o pdf" --arquivos "$tmp/projeto/documento.pdf"
conferir "caso 39: PDF extraído com pdftotext tem código 0" [ "$(codigo)" = 0 ]
conferir "caso 39: texto enviado traz numeracao de paginas" grep -q "p\. 1:" "$ollama_reqs"

# 22. Perfil nativo recusa mesmo com --destino explícito
DELEGAR=nativo delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 40: DELEGAR=nativo recusa --destino local" [ "$(codigo)" = 4 ]
conferir "caso 40: erro indica invoke_subagent" grep -q "use invoke_subagent" "$tmp/erro"

# 23. Perfil local recusa --destino agy
DELEGAR=local delegar --destino agy leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 41: DELEGAR=local recusa --destino agy" [ "$(codigo)" = 4 ]
conferir "caso 41: erro indica restricao ao destino local" grep -q "restringe a delegação ao destino local" "$tmp/erro"

# 24. Argumentos posicionais após --
: >"$ollama_reqs"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor --arquivos "$tmp/projeto/doc1.txt" -- "pedido posicional apos tracos"
conferir "caso 42: argumentos posicionais apos -- tratados corretamente" [ "$(codigo)" = 0 ]
conferir "caso 42: pedido apos -- enviado ao modelo" grep -q "pedido posicional apos tracos" "$ollama_reqs"
delegar -- explorador "pedido apos tracos agy"
conferir "caso 42b: papel e pedido apos -- com agy" [ "$(codigo)" = 0 ]

# 25. Marca de jogo ativo no estado
mkdir -p "$tmp/home/.local/state/jangada/marcas"
# 25a. Fora do isolamento a marca é ignorada
printf '%s\n' "$(date +%s)" >"$tmp/home/.local/state/jangada/marcas/jogo-ativo"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 43a: marca jogo-ativo fora do isolamento é ignorada" [ "$(codigo)" = 0 ]

# 25b. Na sessão isolada com marca recente recusa com código 4
ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 43b: marca jogo-ativo recente no isolamento recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 43b: erro indica jogo aberto" grep -q "jogo aberto detectado" "$tmp/erro"

# 25c. Na sessão isolada com marca expirada (>120s) a marca é ignorada
printf '%s\n' "$(( $(date +%s) - 300 ))" >"$tmp/home/.local/state/jangada/marcas/jogo-ativo"
ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 43c: marca jogo-ativo expirada no isolamento é ignorada" [ "$(codigo)" = 0 ]

# 25d. Na sessão isolada com marca malformada recusa por segurança (código 4)
printf 'invalido\n' >"$tmp/home/.local/state/jangada/marcas/jogo-ativo"
ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 43d: marca jogo-ativo malformada no isolamento recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 43d: erro indica jogo aberto" grep -q "jogo aberto detectado" "$tmp/erro"
rm -f "$tmp/home/.local/state/jangada/marcas/jogo-ativo"

# 26. Marca de VRAM livre gravada pelo host no estado
# 26a. Na sessão isolada com marca recente permite chamada sem nvidia-smi
printf '6000 %s\n' "$(date +%s)" >"$tmp/home/.local/state/jangada/marcas/vram-livre"
SEM_VRAM=1 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 44a: marca vram-livre recente permite medicao no isolamento" [ "$(codigo)" = 0 ]

SEM_VRAM=2 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 44a2: erro do nvidia-smi na saída padrão usa marca recente" [ "$(codigo)" = 0 ]
printf '1000 %s\n' "$(date +%s)" >"$tmp/home/.local/state/jangada/marcas/vram-livre"
SEM_VRAM=2 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 44a3: erro do nvidia-smi não ignora limite de memória" [ "$(codigo)" = 4 ]
conferir "caso 44a3: informa memória insuficiente medida pelo host" grep -q 'memória de vídeo livre insuficiente: 1000 MiB' "$tmp/erro"

# 26b. Na sessão isolada com marca expirada (>120s) recusa
printf '6000 %s\n' "$(( $(date +%s) - 300 ))" >"$tmp/home/.local/state/jangada/marcas/vram-livre"
SEM_VRAM=2 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 44b: marca vram-livre expirada no isolamento recusa com código 4" [ "$(codigo)" = 4 ]
conferir "caso 44b: erro indica vram nao verificada" grep -q "não pôde ser verificada na sessão isolada" "$tmp/erro"

# 26c. Na sessão isolada com marca malformada recusa com código 4
printf '6000 invalido\n' >"$tmp/home/.local/state/jangada/marcas/vram-livre"
SEM_VRAM=1 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 44c: marca vram-livre com timestamp invalido recusa" [ "$(codigo)" = 4 ]
rm -f "$tmp/home/.local/state/jangada/marcas/vram-livre"

# 27. Sessão isolada sem medição de VRAM e sem modelo residente recusa
SEM_VRAM=1 ISOLADO=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 45: sessao isolada sem medicao de vram recusa" [ "$(codigo)" = 4 ]
conferir "caso 45: erro indica vram nao verificada" grep -q "não pôde ser verificada na sessão isolada" "$tmp/erro"

# 28. JANGADA_LOCAL_IGNORAR_VRAM=1 ignora checagem na sessão isolada
SEM_VRAM=1 ISOLADO=1 LOCAL_IGNORAR_VRAM=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar --destino local leitor "leia" --arquivos "$tmp/projeto/doc1.txt"
conferir "caso 46: JANGADA_LOCAL_IGNORAR_VRAM=1 libera chamada" [ "$(codigo)" = 0 ]

# 29. Protocolo de delegação local presente e referenciado
conferir "caso 47: arquivo protocolo-delegar-local.md existe e legivel" test -r "$repo_jangada/default/agentes/protocolo-delegar-local.md"
conferir "caso 47: protocolo contém instrução de delegação local" grep -q "delegação local" "$repo_jangada/default/agentes/protocolo-delegar-local.md"

# Cotas antigas ou inválidas nunca autorizam uma chamada.
cache_cota="$tmp/home/.cache/jangada/agy-usage.json"
delegar leitor "leia"
touch -d '10 minutes ago' "$cache_cota"
USAGE_FALHA=1 delegar leitor "leia" --json
conferir "cota expirada: falha de atualização recusa antes do pedido" test ! -e "$tmp/falso/agy.args"
conferir "cota expirada: motivo estruturado" jqok -e '.motivo_codigo == "cota_desconhecida"' "$tmp/saida"
rm -f "$cache_cota"
COTA='"invalida"' delegar leitor "leia" --json
conferir "cota textual: recusa estruturada" jqok -e '.motivo_codigo == "cota_desconhecida"' "$tmp/saida"
COTA=1.5 delegar leitor "leia" --json
conferir "cota fora da faixa: recusa" [ "$(codigo)" = 4 ]
COTA=0 delegar leitor "leia" --json
conferir "cota zero: insuficiente" jqok -e '.motivo_codigo == "cota_insuficiente"' "$tmp/saida"
rm -f "$cache_cota"
AGENTE=codex DELEGAR=local delegar --destino agy leitor "leia"
conferir "recusa no Codex: orienta continuar na sessão" grep -q "nesta sessão do Codex" "$tmp/saida"
conferir "recusa no Codex: não recomenda Claude" bash -c '! grep -q Claude "$1"' _ "$tmp/saida"

# Roteamento documental usa os mesmos executores falsos dos casos anteriores.
printf 'Relatório em doc1.txt:1\n' >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" \
  --capacidade resumo_curto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: seleciona local e valida referência" jqok -e \
  '.destino == "local" and .capacidade == "resumo_curto" and .verificacao == "referencias_validas"
    and .decisao == "ordem_configurada_por_capacidade" and .chamadas_executor == 1' "$tmp/saida"
conferir "capacidade: mantém medidas por chamada local" jqok -e '.chamadas_local | length == 1' "$tmp/saida"
RESPOSTA='Relatório em doc1.txt:1' delegar leitor "compare" --capacidade analise_documental \
  --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: agy normal" jqok -e '.destino == "agy" and .verificacao == "referencias_validas"' "$tmp/saida"
conferir "capacidade: agy recebe fonte explícita" grep -qx "$tmp/projeto/doc1.txt" "$tmp/falso/agy.args"

rm -f "$cache_cota"
COTA=0.1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "compare" \
  --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: cota baixa troca agy por local" jqok -e \
  '.destino == "local" and (.tentativas | length) == 2
    and .tentativas[0].motivo_codigo == "cota_insuficiente"' "$tmp/saida"
conferir "capacidade: tentativas compartilham identificação" jqok -se \
  '.[-1].roteamento_id == .[-2].roteamento_id' "$reg"
rm -f "$cache_cota"
USAGE_FALHA=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "compare" \
  --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: cota desconhecida tenta local" jqok -e \
  '.destino == "local" and .tentativas[0].motivo_codigo == "cota_desconhecida"' "$tmp/saida"

OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "compare" \
  --capacidade analise_documental --json --arquivos "$tmp/projeto/doc1.txt"
conferir "privacidade: sem autorização remota descarta agy" jqok -e \
  '.destino == "local" and .tentativas[0].motivo_codigo == "destino_proibido"' "$tmp/saida"
conferir "privacidade: agy não recebe pedido" test ! -e "$tmp/falso/agy.args"
DELEGAR=local OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "compare" \
  --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "perfil local: autorização da tarefa não amplia perfil" test ! -e "$tmp/falso/agy.args"

printf 'Relatório sem referência\n' >"$ollama_resp"
RESPOSTA='Relatório em doc1.txt:1' OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" \
  --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "qualidade: saída inválida tenta outro executor" jqok -e \
  '.destino == "agy" and .tentativas[0].motivo_codigo == "saida_invalida"' "$tmp/saida"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" \
  --capacidade resumo_curto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "privacidade: falha local não autoriza nuvem" test ! -e "$tmp/falso/agy.args"
conferir "sem executor: recusa explicável" jqok -e \
  '.motivo_codigo == "sem_executor" and .tentativas[0].motivo_codigo == "saida_invalida"' "$tmp/saida"
printf 'Relatório em doc1.txt:99\n' >"$ollama_resp"
printf 'original\n' >"$tmp/preservar.md"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --destino local \
  --capacidade resumo_curto --json --arquivo "$tmp/preservar.md" --arquivos "$tmp/projeto/doc1.txt"
conferir "qualidade: linha inexistente reprova" [ "$(codigo)" = 4 ]
conferir "qualidade: saída reprovada preserva arquivo" grep -qx original "$tmp/preservar.md"
conferir "destino explícito: não troca executor" jqok -e \
  '.tentativas | map(select(.destino == "agy")) | length == 0' "$tmp/saida"

RESPOSTA='Relatório em doc1.txt:1' CHAMADAS_MAX=1 OLLAMA_URL="http://127.0.0.1:$porta_ollama" \
  delegar leitor "resuma" --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "limite: não chama segundo executor" test ! -e "$tmp/falso/agy.args"
conferir "limite: registra esgotamento" jqok -e '.motivo_codigo == "limite_chamadas"' "$tmp/saida"
TEMPO_TOTAL=1 ESPERA_AGY=3 RESPOSTA='Relatório em doc1.txt:1' delegar leitor "compare" \
  --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "tempo total: interrompe executor" jqok -e \
  '.motivo_codigo == "limite_tempo" and .chamadas_executor == null' "$tmp/saida"

mkdir -p "$tmp/home/.config/jangada"
printf '{"resumo_curto":["agy","local"]}\n' >"$tmp/home/.config/jangada/delegacao.json"
RESPOSTA='Relatório em doc1.txt:1' delegar leitor "resuma" --capacidade resumo_curto \
  --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "política: ordem do usuário prevalece" jqok -e '.destino == "agy"' "$tmp/saida"
printf '{"resumo_curto":["claude"]}\n' >"$tmp/home/.config/jangada/delegacao.json"
delegar leitor "resuma" --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "política: rejeita executor não integrado" jqok -e '.motivo_codigo == "politica_invalida"' "$tmp/saida"
conferir "política: não executa agy" test ! -e "$tmp/falso/agy.args"
rm -f "$tmp/home/.config/jangada/delegacao.json"

# Negação de ferramenta e restrição de perfil não são falhas recuperáveis.
NEGADO=ReadUrlContent RESPOSTA='Relatório em doc1.txt:1' OLLAMA_URL="http://127.0.0.1:$porta_ollama" \
  delegar leitor "compare" --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "permissão: negação não dispara troca" jqok -e \
  '.tentativas[0].motivo_codigo == "destino_proibido"
    and (.tentativas | map(select(.destino == "local")) | length == 0)' "$tmp/saida"
DELEGAR=claude delegar leitor "resuma" --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "perfil Claude: não delega a outro executor" test ! -e "$tmp/falso/agy.args"
delegar explorador "resuma" --capacidade resumo_curto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: papel incompatível recusa" jqok -e '.motivo_codigo == "capacidade_incompativel"' "$tmp/saida"
delegar redator "resuma" --capacidade resumo_curto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: redator não substitui leitor" jqok -e '.motivo_codigo == "capacidade_incompativel"' "$tmp/saida"
delegar leitor "resuma" --capacidade inexistente --arquivos "$tmp/projeto/doc1.txt"
conferir "capacidade: desconhecida é erro de uso" [ "$(codigo)" = 2 ]

printf 'Relatório em doc1.txt:1\n' >"$ollama_resp"
printf 'outra fonte\n' >"$tmp/projeto/doc2.txt"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --destino local --capacidade resumo_curto \
  --json --arquivos "$tmp/projeto/doc1.txt" "$tmp/projeto/doc2.txt"
conferir "qualidade: fonte omitida reprova" [ "$(codigo)" = 4 ]
OLLAMA_URL="http://127.0.0.1:1" delegar leitor "resuma" --capacidade resumo_curto \
  --json --arquivos "$tmp/projeto/doc1.txt"
conferir "sem executor: indisponibilidade registrada" jqok -e \
  '.motivo_codigo == "sem_executor" and .tentativas[0].motivo_codigo == "indisponivel"' "$tmp/saida"

CHAMADAS_MAX=1 LOCAL_CTX=2100 LOCAL_FATIAS_MAX=5 OLLAMA_URL="http://127.0.0.1:$porta_ollama" \
  delegar leitor "resuma" --destino local --capacidade resumo_curto --json --arquivos "$doc_grande"
conferir "limite: reserva consolidação antes de consumir chamadas" jqok -e \
  '.tentativas[0].motivo_codigo == "limite_chamadas" and .tentativas[0].chamadas == 0' "$tmp/saida"

printf '## Destino\nUse o modelo local para ler os documentos. doc1.txt:1\n' >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "extraia a regra" \
  --capacidade leitura_documental --requisito Destino --json --arquivos "$tmp/projeto/doc1.txt"
conferir "completude: explica requisito com referência" jqok -e \
  '.verificacao == "referencias_e_requisitos_validos" and .codigo_saida == 0
    and .requisitos == ["Destino"]' "$tmp/saida"
conferir "geração: desativa raciocínio e limita saída" jqok -se \
  'last | .think == false and .options.num_predict == 1024
    and (.messages[1].content | endswith("/no_think"))' "$ollama_reqs"
printf '## Destino\ndoc1.txt:1\n' >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "extraia a regra" \
  --capacidade leitura_documental --requisito Destino --json --arquivos "$tmp/projeto/doc1.txt"
conferir "completude: localizador sozinho reprova" jqok -e \
  '.tentativas[0].motivo_codigo == "saida_invalida"' "$tmp/saida"
artefato_reprovado="$(jq -rs 'map(select(.destino == "local")) | last | .artefato' "$reg")"
conferir "completude: preserva relatório reprovado para diagnóstico" grep -q doc1.txt:1 "$artefato_reprovado"
touch "$ollama_resp.limite"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "extraia a regra" \
  --capacidade leitura_documental --json --arquivos "$tmp/projeto/doc1.txt"
conferir "geração: relatório cortado pelo limite reprova" jqok -e \
  '.tentativas[0].motivo_codigo == "saida_invalida"' "$tmp/saida"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar redator "revise" --destino local \
  --arquivos "$tmp/projeto/doc1.txt"
conferir "compatibilidade: saída longa sem capacidade mantém contrato" [ "$(codigo)" = 0 ]
conferir "compatibilidade: não altera opções antigas de geração" jqok -se \
  'last | (has("think") | not) and (.options | has("num_predict") | not)
    and (.messages[1].content | endswith("/no_think") | not)' "$ollama_reqs"
rm "$ollama_resp.limite"
printf 'Regra explicada com referência válida em doc1.txt:1\n' >"$ollama_resp"
LOCAL_MODELO=modelo-simples OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "leia" \
  --capacidade leitura_documental --json --arquivos "$tmp/projeto/doc1.txt"
conferir "geração: outros modelos não recebem controle Qwen3" jqok -se \
  'last | .model == "modelo-simples" and (.messages[1].content | endswith("/no_think") | not)' "$ollama_reqs"
delegar leitor "leia" --requisito Destino --arquivos "$tmp/projeto/doc1.txt"
conferir "uso: requisito exige capacidade" [ "$(codigo)" = 2 ]
delegar leitor "leia" --capacidade leitura_documental --requisito -Foo --arquivos "$tmp/projeto/doc1.txt"
conferir "uso: requisito começando com hífen é recusado" [ "$(codigo)" = 2 ]
conferir "uso: ajuda apresenta requisito" grep -q -- --requisito "$tmp/erro"
printf 'doc_grande.txt:1: resumo completo com fonte.\n' >"$ollama_resp"
: >"$ollama_reqs"
CHAMADAS_MAX="$chamadas_fatiadas" LOCAL_CTX=2100 LOCAL_FATIAS_MAX=5 OLLAMA_URL="http://127.0.0.1:$porta_ollama" \
  delegar leitor "resuma" --capacidade resumo_curto --json --arquivos "$doc_grande"
conferir "limite: orçamento exato inclui consolidação" jqok -e --argjson total "$chamadas_fatiadas" \
  '.codigo_saida == 0 and .chamadas_executor == $total and .chamadas_local[-1].fase == "consolidacao"' "$tmp/saida"
RESPOSTA='Resposta sem referências' CHAMADAS_MAX="$chamadas_fatiadas" LOCAL_CTX=2100 \
  OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --capacidade analise_documental \
  --permitir-remoto --json --arquivos "$doc_grande"
conferir "limite: desconta chamada anterior antes das partes locais" jqok -e \
  '.tentativas[0].destino == "agy" and .tentativas[0].chamadas == 1
    and .tentativas[1].destino == "local" and .tentativas[1].chamadas == 0
    and .tentativas[1].motivo_codigo == "limite_chamadas"' "$tmp/saida"

# A prévia cortada declara que a verificação vale para o arquivo completo.
python3 -c 'print("palavra " * 610 + "doc1.txt:1")' >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --capacidade resumo_curto \
  --json --arquivo "$tmp/completo.md" --arquivos "$tmp/projeto/doc1.txt"
conferir "arquivo: roteamento bem-sucedido grava relatório completo" grep -q doc1.txt:1 "$tmp/completo.md"
conferir "prévia: escopo da verificação é explícito" jqok -e \
  '.relatorio_cortado and .verificacao_escopo == "relatorio_completo"
    and .artefato != "" and (.relatorio | contains("doc1.txt:1") | not)' "$tmp/saida"

# O pai limpa temporários mesmo quando o executor ignora SIGTERM.
TEMPO_TOTAL=1 ESPERA_AGY=5 IGNORAR_TERM=1 RESPOSTA='Relatório em doc1.txt:1' delegar leitor "compare" \
  --capacidade analise_documental --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "encerramento forçado: recusa estruturada" jqok -e '.motivo_codigo == "limite_tempo"' "$tmp/saida"
conferir "encerramento forçado: diretório dos temporários removido" \
  test ! -d "$(cat "$tmp/falso/temporario")"
processo_encerrado() {
  local estado
  estado="$(ps -o stat= -p "$1" 2>/dev/null || true)"
  estado="${estado//[[:space:]]/}"
  [[ -z "$estado" || "$estado" == Z* ]]
}
conferir "encerramento forçado: agy não continua executando" processo_encerrado "$(cat "$tmp/falso/agy.pid")"
conferir "encerramento forçado: filho do agy não continua executando" processo_encerrado "$(cat "$tmp/falso/filho.pid")"
rm -f "$cache_cota"
TEMPO_TOTAL=1 ESPERA_USAGE=5 delegar leitor "compare" --capacidade analise_documental \
  --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "consulta interrompida: recusa estruturada" jqok -e '.motivo_codigo == "limite_tempo"' "$tmp/saida"
conferir "consulta interrompida: temporário ao lado do cache removido" \
  bash -c '! compgen -G "$1.*" >/dev/null' _ "$cache_cota"

# Um executor sem resultado JSON não pode produzir uma entrega aceita.
cat >"$tmp/bin/bash" <<'EOF'
#!/bin/sh
if [ -n "${JANGADA_DELEGAR_ROTEAMENTO_ID:-}" ]; then
  echo 'resultado sem JSON'
  exit 0
fi
exec /usr/bin/bash "$@"
EOF
chmod +x "$tmp/bin/bash"
delegar leitor "resuma" --capacidade resumo_curto --json --arquivos "$tmp/projeto/doc1.txt"
conferir "executor: resultado não JSON recusa" jqok -e \
  '.motivo_codigo == "erro_execucao" and .tentativas[0].destino == "local"
    and .tentativas[0].chamadas == null' "$tmp/saida"
rm -f "$tmp/bin/bash"

printf '\377\n' >"$tmp/projeto/binario.txt"
printf 'Referência em binario.txt:1\n' >"$ollama_resp"
OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --capacidade resumo_curto \
  --json --arquivos "$tmp/projeto/binario.txt"
conferir "fonte: codificação inválida reprova saída" jqok -e \
  '.tentativas[0].motivo_codigo == "saida_invalida"' "$tmp/saida"

if command -v pdftotext >/dev/null; then
  python3 - "$tmp/projeto/fonte.pdf" <<'PY'
import pathlib
import sys

conteudo = b"BT /F1 12 Tf 72 720 Td (Fonte de teste.) Tj ET"
objetos = [
    b"<< /Type /Catalog /Pages 2 0 R >>",
    b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
    b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    b"<< /Length " + str(len(conteudo)).encode() + b" >>\nstream\n" + conteudo + b"\nendstream",
]
pdf = b"%PDF-1.4\n"
posicoes = [0]
for i, objeto in enumerate(objetos, 1):
    posicoes.append(len(pdf))
    pdf += f"{i} 0 obj\n".encode() + objeto + b"\nendobj\n"
xref = len(pdf)
pdf += f"xref\n0 {len(posicoes)}\n0000000000 65535 f \n".encode()
pdf += b"".join(f"{p:010d} 00000 n \n".encode() for p in posicoes[1:])
pdf += f"trailer\n<< /Size {len(posicoes)} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
pathlib.Path(sys.argv[1]).write_bytes(pdf)
PY
  printf 'Referência em fonte.pdf, p. 1\n' >"$ollama_resp"
  OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" --capacidade resumo_curto \
    --json --arquivos "$tmp/projeto/fonte.pdf"
  conferir "PDF: extrai e valida página no fluxo completo" jqok -e '.verificacao == "referencias_validas"' "$tmp/saida"
else
  echo "pulado PDF no fluxo completo: pdftotext ausente"
fi

# A contagem do painel é por registro, mas o consumo não duplica o histórico.
printf 'Relatório sem referência\n' >"$ollama_resp"
RESPOSTA='Relatório em doc1.txt:1' OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" \
  --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
id_roteamento="$(jq -r '.roteamento_id' "$tmp/saida")"
jq -c --arg id "$id_roteamento" 'select(.roteamento_id == $id)' "$reg" >"$tmp/roteamento.jsonl"
painel_roteamento() {
  python3 - "$repo_jangada" "$tmp/roteamento.jsonl" "$1" <<'PY'
import importlib.util
import pathlib
import sys

sys.dont_write_bytecode = True
modulos = {}
for nome in ("metricas", "subagentes"):
    spec = importlib.util.spec_from_file_location(nome, pathlib.Path(sys.argv[1]) / f"default/painel/{nome}.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    modulos[nome] = modulo
delegacoes = modulos["subagentes"].delegacoes(sys.argv[2])
assert len(delegacoes) == int(sys.argv[3])
assert len({d["roteamento_id"] for d in delegacoes}) == 1
consumo, _ = modulos["metricas"].ollama(sys.argv[2])
assert len(consumo) == 1
assert consumo[0]["entrada_total"] == 120 and consumo[0]["saida"] == 45
PY
}
conferir "painel: troca de executor conta duas entradas, sem duplicar consumo" painel_roteamento 2
RESPOSTA='Relatório sem referência' OLLAMA_URL="http://127.0.0.1:$porta_ollama" delegar leitor "resuma" \
  --capacidade resumo_curto --permitir-remoto --json --arquivos "$tmp/projeto/doc1.txt"
id_roteamento="$(jq -r '.roteamento_id' "$tmp/saida")"
jq -c --arg id "$id_roteamento" 'select(.roteamento_id == $id)' "$reg" >"$tmp/roteamento.jsonl"
conferir "painel: falha total conta executores e recusa final, sem duplicar consumo" painel_roteamento 3

echo
if ((falhas)); then
  echo "$falhas teste(s) falharam"
  exit 1
fi
echo "todos os testes do jangada-delegar passaram"
