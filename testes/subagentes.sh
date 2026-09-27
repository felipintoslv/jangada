#!/usr/bin/env bash
# Testa os papéis de subagente (default/claude/agents e default/agy/agents) e
# a instalação deles num HOME temporário.
#
# Uso: testes/subagentes.sh
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

papeis=(explorador leitor pesquisador verificador)

# Frontmatter e corpo de um agent.md: o corpo começa depois do segundo "---".
cabeca() { awk 'NR > 1 && /^---$/ { exit } NR > 1' "$1"; }
corpo() { awk 'f; /^---$/ && ++n == 2 { f = 1 }' "$1"; }
campo() { cabeca "$1" | sed -n "s/^$2: //p"; }

# Papéis: mesmos nomes e mesmo texto nos dois agentes; só o frontmatter muda.
declare -A modelo_claude=([explorador]=haiku [leitor]=haiku [pesquisador]=haiku [verificador]=sonnet)
for p in "${papeis[@]}"; do
  c="default/claude/agents/$p.md"
  a="default/agy/agents/$p/agent.md"
  conferir "$p: existe nos dois agentes" test -r "$c" -a -r "$a"
  conferir "$p: mesmo nome nos dois" [ "$(campo "$c" name) $(campo "$a" name)" = "$p $p" ]
  conferir "$p: mesmo texto nos dois" [ "$(corpo "$c")" = "$(corpo "$a")" ]
  conferir "$p: corpo começa por título H1" bash -c '[[ "$(sed -n "/./{p;q}" <<<"$1")" == "# "* ]]' _ "$(corpo "$a")"
  conferir "$p: modelo do Claude" [ "$(campo "$c" model)" = "${modelo_claude[$p]}" ]
  # O agy descarta em silêncio o agente com model fora de flash, pro ou
  # inherit; o esforço (low, medium, high) vai na chamada.
  conferir "$p: modelo do agy é flash" [ "$(campo "$a" model)" = flash ]
  conferir "$p: subagente no agy" [ "$(campo "$a" subagent)" = true ]
  conferir "$p: nenhuma ferramenta de escrita no Claude" \
    bash -c '! grep -qE "^tools:.*\b(Edit|Write|NotebookEdit|Agent)\b" "$1"' _ "$c"
  conferir "$p: nenhuma ferramenta de escrita no agy" \
    bash -c '! grep -qE "^  - (write_to_file|replace_file_content|multi_replace_file_content|notebook_edit|invoke_subagent|define_subagent)$" "$1"' _ "$a"
  conferir "$p: exige citar a origem" grep -qE 'caminho:linha|URL|p\. N' "$c"
  conferir "$p: não edita" grep -q 'Não crie, edite, mova nem apague arquivos' "$c"
done
conferir "só o pesquisador busca na web (Claude)" \
  [ "$(grep -l '^tools:.*WebSearch' default/claude/agents/*.md | xargs -n1 basename)" = pesquisador.md ]
# O agy roda comandos com run_command quando o Claude do mesmo papel tem Bash.
for p in "${papeis[@]}"; do
  bash_claude=0; cmd_agy=0
  grep -qE '^tools:.*\bBash\b' "default/claude/agents/$p.md" && bash_claude=1
  grep -qx '  - run_command' "default/agy/agents/$p/agent.md" && cmd_agy=1
  conferir "$p: run_command no agy se e só se Bash no Claude" [ "$bash_claude" = "$cmd_agy" ]
done

# Instalação num HOME temporário.
instalar() {
  env HOME="$tmp/home" JANGADA_PATH="$repo_jangada" JANGADA_SIMULAR="${SIMULAR:-0}" \
    bash -c 'source install/lib.sh; ligar_agentes_claude; mesclar_agentes_agy' >"$tmp/saida.log" 2>&1
}
mkdir -p "$tmp/home"
SIMULAR=1 instalar
conferir "simulação não cria nada" [ -z "$(find "$tmp/home" -mindepth 1 -print -quit)" ]

mkdir -p "$tmp/home/.gemini/config" "$tmp/home/.claude/agents"
echo '{"entries":[{"path":"/outro/agents"},{"path":"/velho/jangada/default/agy/agents"}],"inherits":[]}' \
  >"$tmp/home/.gemini/config/agents.json"
echo "alheio" >"$tmp/home/.claude/agents/leitor.md"
instalar
agentes_json="$tmp/home/.gemini/config/agents.json"
conferir "agents.json aponta para a pasta do jangada" \
  jqok -e --arg p "$repo_jangada/default/agy/agents" '[.entries[].path] == ["/outro/agents", $p]' "$agentes_json"
conferir "agents.json mantém as outras chaves" jqok -e 'has("inherits")' "$agentes_json"
conferir "agents.json ganhou cópia de segurança" \
  bash -c 'ls "$1"/agents.json.jangada-*.bak >/dev/null 2>&1' _ "$tmp/home/.gemini/config"
conferir "subagente do Claude ligado ao repositório" \
  [ "$(readlink "$tmp/home/.claude/agents/explorador.md")" = "$repo_jangada/default/claude/agents/explorador.md" ]
conferir "arquivo alheio com o mesmo nome fica" [ "$(cat "$tmp/home/.claude/agents/leitor.md")" = alheio ]
antes="$(cat "$agentes_json")"
n_bak="$(find "$tmp/home/.gemini/config" -name '*.bak' | wc -l)"
instalar
conferir "rodar de novo não muda nada" \
  bash -c '[ "$1" = "$(cat "$2")" ] && [ "$3" = "$(find "$4" -name "*.bak" | wc -l)" ] && grep -q "já registrados" "$5"' \
  _ "$antes" "$agentes_json" "$n_bak" "$tmp/home/.gemini/config" "$tmp/saida.log"

# Registros de subagentes e delegações, com as amostras de
# testes/amostras-subagentes.py.
amostra="$tmp/amostra"
mkdir -p "$amostra/projeto"
python3 testes/amostras-subagentes.py "$amostra" "$amostra/projeto"
subagentes() {
  env -u JANGADA_ESTADO JANGADA_CLAUDE_PROJETOS="$amostra/claude/projects" JANGADA_AGY_DIR="$amostra/agy" \
    XDG_STATE_HOME="$amostra/state" "$repo_jangada/bin/jangada-subagentes" "$@"
}
subagentes --registros >"$tmp/registros.jsonl"
reg() { jq -e --arg id "$1" "select(.id == \$id) | $2" "$tmp/registros.jsonl" >/dev/null; }
conferir "registros: primeiro plano com totais e retorno da conversa mãe" \
  reg a1 '.papel == "explorador" and .forma == "foreground" and .tokens == 20000 and .retorno_tokens == 104
          and .casamento and .edicoes == 0 and (.autorrevisao | not) and .sem_fonte == 0'
conferir "registros: segundo plano com totais do aviso e retorno do handback" \
  reg a2 '.estado == "completed" and .tokens == 50000 and .ferramentas == 7 and .retorno_tokens > 100
          and .edicoes == 1 and .autorrevisao and .generico and .sem_fonte == 20'
conferir "registros: sem totais na mãe, usa o contexto do último turno" \
  reg a3 '.tokens == 500 and .retorno_tokens == null and .casamento == null'
conferir "registros: subagente do agy com passos e escrita" \
  reg s1 '.origem == "agy" and .passos == 5 and .edicoes == 1 and .autorrevisao and .generico'
subagentes --entrega "$amostra/projeto" >"$tmp/entrega.json"
conferir "entrega: soma subagentes e delegações da pasta" jqok -e '.n == 5 and .claude == {n: 3, tokens: 70500}
  and .agy == {n: 2, passos: 17} and .papeis == {explorador: 2} and .edicoes == 2 and .autorrevisao == 2
  and .recusas == 1' "$tmp/entrega.json"
subagentes --entrega "$amostra/projeto" --desde 2026-09-27T10:05:30Z >"$tmp/entrega.json"
conferir "entrega: --desde deixa só o que veio depois" jqok -e '.n == 0 and .recusas == 1' "$tmp/entrega.json"
subagentes --entrega "$tmp" >"$tmp/entrega.json"
conferir "entrega: outra pasta não conta nada" jqok -e '.n == 0 and .recusas == 0' "$tmp/entrega.json"

echo
if ((falhas)); then
  echo "$falhas teste(s) falharam"
  exit 1
fi
echo "todos os testes de subagentes passaram"
