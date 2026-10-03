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

papeis=(explorador leitor pesquisador verificador auditor arquiteto otimizador redator supervisor)

# Frontmatter e corpo de um agent.md: o corpo começa depois do segundo "---".
cabeca() { awk 'NR > 1 && /^---$/ { exit } NR > 1' "$1"; }
corpo() { awk 'f; /^---$/ && ++n == 2 { f = 1 }' "$1"; }
campo() { cabeca "$1" | sed -n "s/^$2: //p"; }

# Papéis: mesmos nomes e mesmo texto nos dois agentes; só o frontmatter muda.
declare -A modelo_claude=([explorador]=haiku [leitor]=haiku [pesquisador]=haiku [verificador]=sonnet [auditor]=sonnet [arquiteto]=sonnet [otimizador]=sonnet [redator]=haiku [supervisor]=haiku)
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

# O leitor lê documentos de fora; o Bash dele passa pelo jangada-hook-leitor,
# que só deixa comandos de leitura. O verificador roda os testes do projeto e
# fica com o Bash livre.
conferir "leitor: hook PreToolUse no Bash" \
  bash -c 'sed -n "/^hooks:/,/^---$/p" "$1" | grep -qx "          command: jangada-hook-leitor || exit 2"' _ default/claude/agents/leitor.md
conferir "papel com Bash sem hook: só o verificador" [ "$(for p in "${papeis[@]}"; do
    f="default/claude/agents/$p.md"
    grep -qE '^tools:.*\bBash\b' "$f" && ! grep -q 'jangada-hook-leitor' "$f" && echo "$p"
  done)" = verificador ]
hook_leitor() { jq -cn --arg c "$1" '{tool_name: "Bash", tool_input: {command: $c}}' | bin/jangada-hook-leitor 2>/dev/null; }
export -f hook_leitor
for c in "pdftotext -layout -f 2 -l 3 'Relatório final.pdf' - | grep -n 'Total' | head -40" \
         "grep -c 'fim\$' notas.txt" "ls -la docs" "pdfinfo a.pdf" "tail -n 5 a.csv | cut -d, -f2"; do
  conferir "hook do leitor libera: $c" hook_leitor "$c"
done
for c in "pdftotext a.pdf saida.txt" "cat a.pdf > b" "grep x a; rm -rf ~" "echo \$(id)" "head \`id\`" \
         "rm a" "python3 -c 1" "head a && touch b" "grep x a &" "A=1 grep x a" "grep x \$HOME/.ssh/id" \
         "cat a | sh" "tee b" $'head a\ntouch b' "grep 'x" "grep x a |" "cat <a"; do
  conferir "hook do leitor recusa: ${c//$'\n'/\\n}" bash -c '! hook_leitor "$1"' _ "$c"
done
conferir "hook do leitor: recusa sai com 2" bash -c 'hook_leitor "rm a"; [ $? = 2 ]'
conferir "hook do leitor: outra ferramenta passa" \
  bash -c 'jq -cn "{tool_name: \"Read\", tool_input: {file_path: \"a\"}}" | bin/jangada-hook-leitor'
conferir "hook do leitor: evento ilegível recusa" bash -c '! echo x | bin/jangada-hook-leitor 2>/dev/null'

# No agy o hook é global (~/.gemini/config/hooks.json) e responde em JSON:
# "deny" para o comando recusado do leitor, "ask" no resto, que segue as
# permissões do agy. O leitor vem do JANGADA_AGY_PAPEL (jangada-delegar) ou do
# json do subagente na pasta brain da conversa-mãe.
leitor_id=0b7c2f4e-1111-4222-8333-444455556666
outro_id=0b7c2f4e-1111-4222-8333-777788889999
mkdir -p "$tmp/agy/brain/mae/.system_generated/subagents"
echo '{"subagentDescriptor": {"typeName": "leitor"}}' >"$tmp/agy/brain/mae/.system_generated/subagents/$leitor_id.json"
echo '{"subagentDescriptor": {"typeName": "explorador"}}' >"$tmp/agy/brain/mae/.system_generated/subagents/$outro_id.json"
hook_agy() { # conversa, comando; demais argumentos vão para o env
  local conv="$1" cmd="$2"; shift 2
  jq -cn --arg i "$conv" --arg c "$cmd" '{conversationId: $i, toolCall: {name: "run_command", args: {CommandLine: $c}}}' \
    | env -u JANGADA_AGY_PAPEL JANGADA_AGY_DIR="$tmp/agy" "$@" bin/jangada-hook-leitor --agy
}
decisao() { hook_agy "$@" | jq -r .decision; }
export -f hook_agy decisao
export tmp
conferir "hook do agy: leitor pelo papel, comando que grava recusado" \
  [ "$(decisao x "cp a b" JANGADA_AGY_PAPEL=leitor)" = deny ]
conferir "hook do agy: a recusa traz o motivo" \
  bash -c 'hook_agy x "cat a > b" JANGADA_AGY_PAPEL=leitor | jq -e ".reason | test(\"não é permitido\")" >/dev/null'
conferir "hook do agy: leitor pelo papel, leitura segue as permissões" \
  [ "$(decisao x "head a.txt" JANGADA_AGY_PAPEL=leitor)" = ask ]
conferir "hook do agy: subagente leitor pelo json da conversa" [ "$(decisao "$leitor_id" "rm a")" = deny ]
conferir "hook do agy: outro subagente não é limitado" [ "$(decisao "$outro_id" "rm a")" = ask ]
conferir "hook do agy: agente principal não é limitado" \
  [ "$(decisao 0b7c2f4e-1111-4222-8333-000000000000 "rm a")" = ask ]
conferir "hook do agy: conversa fora do formato não vira caminho" \
  [ "$(decisao "../../mae/.system_generated/subagents/$leitor_id" "rm a")" = ask ]
conferir "hook do agy: JANGADA_HOOK_DESLIGADO não solta o leitor" \
  [ "$(decisao x "rm a" JANGADA_AGY_PAPEL=leitor JANGADA_HOOK_DESLIGADO=1)" = deny ]
conferir "hook do agy: evento ilegível do leitor recusa" \
  [ "$(echo x | JANGADA_AGY_PAPEL=leitor bin/jangada-hook-leitor --agy | jq -r .decision)" = deny ]
conferir "hook do agy: evento ilegível de outro agente segue as permissões" \
  [ "$(echo x | env -u JANGADA_AGY_PAPEL bin/jangada-hook-leitor --agy | jq -r .decision)" = ask ]
mkdir -p "$tmp/pyquebrado"
printf '#!/bin/sh\nexit 1\n' >"$tmp/pyquebrado/python3"
chmod +x "$tmp/pyquebrado/python3"
conferir "hook do agy: falha do Python recusa" \
  [ "$(decisao x "head a" PATH="$tmp/pyquebrado:$PATH")" = deny ]
conferir "hook do agy: PreToolUse do run_command no hooks.json do jangada" \
  jqok -e '.jangada.PreToolUse | any(.matcher == "run_command" and any(.hooks[]; .command == "@JANGADA_PATH@/bin/jangada-hook-leitor --agy"))' default/agy/hooks.json

# O revisor do jangada-validar lê a entrega, conteúdo não confiável: no agy
# roda só com ferramentas de leitura e não aparece como subagente.
rev=default/agy/agents/revisor/agent.md
conferir "revisor do agy existe" test -r "$rev"
conferir "revisor do agy não é subagente" [ "$(campo "$rev" subagent)" = false ]
conferir "revisor do agy só lê" [ "$(sed -n '/^tools:/,/^[a-z]/p' "$rev" | grep '^  - ' | sort | tr -d ' -' | paste -sd,)" = find_by_name,grep_search,list_dir,view_file ]

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
conferir "entrega: soma subagentes e delegações da pasta" jqok -e '.n == 5 and .claude == {n: 3, tokens: 70500, principal: 1000, principal_cache_lido: 7000}
  and .delegadas_agy == 1
  and .agy == {n: 2, passos: 17} and .papeis == {explorador: 2} and .edicoes == 2 and .autorrevisao == 2
  and .recusas == 1' "$tmp/entrega.json"
subagentes --entrega "$amostra/projeto" --desde 2026-09-27T10:05:30Z >"$tmp/entrega.json"
conferir "entrega: --desde deixa só o que veio depois" jqok -e '.n == 0 and .recusas == 1' "$tmp/entrega.json"
subagentes --entrega "$tmp" >"$tmp/entrega.json"
conferir "entrega: outra pasta não conta nada" jqok -e '.n == 0 and .recusas == 0' "$tmp/entrega.json"

# Os oito indicadores sobre as amostras, com duas entregas aprovadas: uma
# com delegação ao agy e verificador, outra sem.
{
  jq -cn '{data: "2026-09-27T08:00:00-03:00", projeto: "proj", rotulo: "s", rodada: 1, resultado: "aprovado",
           mais: 10, menos: 0, subagentes: {n: 2, claude: {n: 1, tokens: 1000, principal: 5000},
           delegadas_agy: 1, papeis: {verificador: 1}}}'
  jq -cn '{data: "2026-09-27T09:00:00-03:00", projeto: "proj", rotulo: "s", rodada: 2, resultado: "aprovado",
           mais: 90, menos: 10, subagentes: {n: 0, claude: {n: 0, tokens: 0, principal: 20000},
           delegadas_agy: 0, papeis: {}}}'
  jq -cn '{data: "2026-09-27T09:30:00-03:00", projeto: "proj", rotulo: "s", rodada: 1, resultado: "aprovado"}'
} >"$amostra/state/jangada/validar.jsonl"
subagentes --json >"$tmp/ind.json"
conferir "indicadores: só entregas com resumo" jqok -e '.entregas_com_resumo == 2' "$tmp/ind.json"
conferir "indicadores 1: tokens do Claude com e sem agy" jqok -e '.tokens_por_entrega[-1]
  | .faixa == "todas" and .com.mediana_tokens == 6000 and .sem.mediana_tokens == 20000 and .com.pouco_dado' "$tmp/ind.json"
conferir "indicadores 2: fração ao agy e recusa com motivo" jqok -e '.fracao_agy
  | .delegadas_agy == 1 and .fracao_agy_pct == 20 and .taxa_recusa_pct == 50
    and (.motivos | keys == ["cota de N horas do Gemini em N, abaixo de N"])' "$tmp/ind.json"
conferir "indicadores 3: compressão em séries separadas" jqok -e '.compressao
  | .claude.n == 2 and .agy.n == 1 and .agy.mediana_passos_por_mil_tokens == 120' "$tmp/ind.json"
conferir "indicadores 4: cota por delegação e por semana" jqok -e '.cota_agy
  | .n == 1 and .media_pp == 0.4 and .delegacoes_por_bloco == 250 and (.por_semana_pp | length) == 1' "$tmp/ind.json"
conferir "indicadores 5: aprovação com e sem verificador" jqok -e '.validacao.verificador[-1]
  | .com.primeira_pct == 100 and .sem.primeira_pct == 0 and .sem.rodadas_media == 2' "$tmp/ind.json"
conferir "indicadores 6: afirmações sem fonte" jqok -e '.qualidade.claude.total == 20 and .qualidade.desmentidos == null' "$tmp/ind.json"
conferir "indicadores 7: desvios" jqok -e '.desvios | (.edicoes | length) == 2 and (.autorrevisao | length) == 2
  and (.generico | length) == 3 and ([.claude_sem_recusa[].id] == ["a1"])' "$tmp/ind.json"
conferir "indicadores 8: árvore por pasta e conversa" jqok -e '[.arvore[] | .conversa] | sort
  == ["agy:c1", "claude:sess1", "delegar:s"]' "$tmp/ind.json"
subagentes >"$tmp/ind.txt"
conferir "indicadores: texto para o terminal" grep -q "^7. Desvios do protocolo" "$tmp/ind.txt"

# Com memo (o do coletor do painel), o subagente cujos arquivos não mudaram
# sai do memo: sem permissão de leitura, o resultado é o mesmo. O que muda é
# relido, e o que some sai do memo.
memo() {
  env -u JANGADA_ESTADO JANGADA_CLAUDE_PROJETOS="$amostra/claude/projects" JANGADA_AGY_DIR="$amostra/agy" \
    XDG_STATE_HOME="$amostra/state" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo_jangada/default/painel" python3 -c '
import json, sys, subagentes
m = json.load(open(sys.argv[1])) if sys.argv[2] == "de-novo" else {}
r = subagentes.indicadores(memo=m)
json.dump(m, open(sys.argv[1], "w"))
r.pop("data", None)
print(json.dumps(r, sort_keys=True))' "$tmp/memo.json" "$1"
}
jq -S 'del(.data)' "$tmp/ind.json" | jq -c . >"$tmp/ind-sem-memo.json"
memo inicio | jq -Sc . >"$tmp/ind-memo1.json"
conferir "memo: mesmo resultado que sem memo" cmp -s "$tmp/ind-sem-memo.json" "$tmp/ind-memo1.json"
conferir "memo: um registro por subagente" jqok -e '(.claude | length) == 3 and (.agy | length) == 1' "$tmp/memo.json"
mapfile -t lidos < <(find "$amostra/claude/projects" "$amostra/agy" -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.db' \))
chmod a-r "${lidos[@]}"
memo de-novo | jq -Sc . >"$tmp/ind-memo2.json"
chmod u+r "${lidos[@]}"
conferir "memo: a segunda leitura não abre arquivo sem mudança" cmp -s "$tmp/ind-memo1.json" "$tmp/ind-memo2.json"
a1="$(find "$amostra/claude/projects" -name 'agent-a1.jsonl')"
jq -c '.' "$a1" | tail -n 1 | jq -c '.message.content = [{type: "tool_use", name: "Edit", id: "novo"}]' >>"$a1"
memo de-novo >/dev/null
conferir "memo: arquivo alterado é relido" \
  jqok -e '[.claude[] | .registro | select(.id == "a1")][0].edicoes == 1' "$tmp/memo.json"
rm "$(find "$amostra/claude/projects" -name 'agent-a3.meta.json')"
memo de-novo >/dev/null
conferir "memo: subagente apagado sai do memo" jqok -e '(.claude | length) == 2' "$tmp/memo.json"

echo
if ((falhas)); then
  echo "$falhas teste(s) falharam"
  exit 1
fi
echo "todos os testes de subagentes passaram"
