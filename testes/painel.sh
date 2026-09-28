#!/usr/bin/env bash
# Testa o painel de indicadores: o coletor (default/painel/coletor.py) sobre
# registros de exemplo, a leitura incremental, o módulo da barra e, com os
# pacotes R presentes, os indicadores e o app no ar.
#
# Uso: testes/painel.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

export PYTHONDONTWRITEBYTECODE=1

if ! python3 -c 'import pyarrow' 2>/dev/null; then
  echo "pyarrow do Python ausente; testes do painel ignorados"
  exit 0
fi

tmp="$(mktemp -d)"
estado="$tmp/state/jangada"
cache="$estado/painel"
conversas="$tmp/claude/projects"
mkdir -p "$estado/agentes" "$conversas/-proj" "$tmp/bin"
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/notify-send"
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/pkill"
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/xdg-open"
chmod +x "$tmp/bin/"*

# Porta livre para o app, fora da do usuário.
porta=$((20000 + RANDOM % 20000))
rodar() {
  env -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" XDG_STATE_HOME="$tmp/state" \
    XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" JANGADA_CLAUDE_PROJETOS="$conversas" \
    JANGADA_PROJETOS="$tmp/Projetos" JANGADA_WORKTREES="$tmp/wt" JANGADA_PAINEL_PORTA="$porta" \
    JANGADA_AGY_DIR="$tmp/sub/agy" "$@"
}
painel() { rodar "$repo_jangada/bin/jangada-painel" "$@"; }
trap 'painel --parar >/dev/null 2>&1 || true; [[ -n "${PAINEL_MANTER:-}" ]] || rm -rf "$tmp"' EXIT
consulta() { python3 - "$cache"; }
jq_ok() { jq -e "$@" >/dev/null; }

# Tudo a poucos minutos de agora, para cair no "hoje" do hoje.json (falha só
# nos 3 primeiros minutos do dia). O parecer velho, de 9 dias atrás, entra nos
# 30 dias do filtro do app: 1 de 3 entregas aprovadas de primeira.
antes="$(date -Iseconds -d '-3 minutes')"
depois="$(date -Iseconds -d '-2 minutes')"
agora="$(date -Iseconds)"

# validar.jsonl: uma entrega reprovada e depois aprovada, outra aprovada de
# primeira. O projeto vem com nome real e maiúscula, como o jangada grava.
{
  jq -cn --arg d "$antes" '{data: $d, projeto: "Meu Projeto", rotulo: "meu-projeto", rodada: 1, resultado: "revisar", etapa: "revisor", revisor: "agy", modelo: "", autor: "claude", arquivos: 2, mais: 40, menos: 3, itens: 2, segundos: 90}'
  jq -cn --arg d "$depois" '{data: $d, projeto: "Meu Projeto", rotulo: "meu-projeto", rodada: 2, resultado: "aprovado", etapa: "revisor", revisor: "agy", modelo: "", autor: "claude", arquivos: 2, mais: 45, menos: 3, itens: 0, segundos: 60}'
  jq -cn --arg d "$agora" '{data: $d, projeto: "Meu Projeto", rotulo: "meu-projeto", rodada: 1, resultado: "aprovado", etapa: "revisor", revisor: "agy", modelo: "", autor: "claude", arquivos: 1, mais: 5, menos: 0, itens: 0, segundos: 30}'
} >"$estado/validar.jsonl"
# Parecer do mesmo segundo de uma linha do validar.jsonl: não conta de novo.
printf 'STATUS: APROVADO\n' >"$estado/agentes/validacao-meu-projeto-r2.md"
touch -d "$depois" "$estado/agentes/validacao-meu-projeto-r2.md"
# Pareceres antigos do jangada-par: o r1 foi sobrescrito depois do r2, e a
# ordem certa é a do mtime. A avaliacao-* não é revisão.
printf 'STATUS: REVISAR\n\n1. falta teste em `src/a.R`\n2. nome ruim (app.R:12)\n3. sem arquivo\n' >"$estado/agentes/parecer-velho--tarefa-r2.md"
touch -d '-10 days' "$estado/agentes/parecer-velho--tarefa-r2.md"
printf '# Parecer\n\nSTATUS: APROVADO\n' >"$estado/agentes/parecer-velho--tarefa-r1.md"
touch -d '-9 days' "$estado/agentes/parecer-velho--tarefa-r1.md"
printf 'STATUS: APROVADO\n' >"$estado/agentes/avaliacao-velho--tarefa-r1.md"

# Subagente do agy e delegações de testes/amostras-subagentes.py; as
# conversas do Claude de lá ficam de fora, para não mudar as contas abaixo.
mkdir -p "$tmp/sub/projeto"
python3 testes/amostras-subagentes.py "$tmp/sub" "$tmp/sub/projeto"
cp "$tmp/sub/state/jangada/delegacoes.jsonl" "$estado/"

# Histórico de estados e uma sessão aberta. Foco e subagente não mudam o estado.
{
  jq -cn --arg d "$antes" '{data: $d, sessao: "meu-projeto", projeto: "Meu Projeto", agente: "claude", estado: "inicio"}'
  jq -cn --arg d "$antes" '{data: $d, sessao: "meu-projeto", projeto: "Meu Projeto", agente: "claude", estado: "aguardando"}'
  jq -cn --arg d "$depois" '{data: $d, sessao: "meu-projeto", projeto: "Meu Projeto", agente: "claude", estado: "foco"}'
  jq -cn --arg d "$depois" '{data: $d, sessao: "meu-projeto", projeto: "Meu Projeto", agente: "claude", estado: "subagente-inicio", subagente_id: "a1", subagente_tipo: "explorador"}'
  jq -cn --arg d "$agora" '{data: $d, sessao: "meu-projeto", projeto: "Meu Projeto", agente: "claude", estado: "trabalhando"}'
} >"$estado/eventos-agentes.jsonl"
jq -n --arg d "$antes" '{sessao: "meu-projeto", raiz: "/x/Meu Projeto", agente: "claude", estado: "trabalhando", desde: $d, atualizado: $d}' \
  >"$estado/agentes/meu-projeto.json"

# Conversa do Claude: a mesma resposta em duas linhas (a primeira com a saída
# parcial), um ciclo de retrabalho (edita, o teste falha, edita de novo), uma
# recusa de permissão e uma linha <synthetic>, que não é consumo real.
cwd="$tmp/Projetos/Meu Projeto"
linha() { jq -cn --arg d "$agora" --arg c "$cwd" "$@"; }
assistente() {
  linha --arg id "$1" --arg r "$2" --argjson s "$3" --argjson b "$4" --arg m "${5:-claude-opus-5-5}" \
    '{type: "assistant", timestamp: $d, cwd: $c, sessionId: "conv1", requestId: $r,
      message: {id: $id, model: $m, content: $b,
        usage: {input_tokens: 10, output_tokens: $s, cache_creation_input_tokens: 100,
                cache_read_input_tokens: 1000, output_tokens_details: {thinking_tokens: 5}}}}'
}
resultado() {
  linha --arg t "$1" --argjson e "$2" --arg x "$3" \
    '{type: "user", timestamp: $d, cwd: $c, sessionId: "conv1",
      message: {role: "user", content: [{type: "tool_result", tool_use_id: $t, is_error: $e, content: $x}]}}'
}
{
  assistente m1 r1 16 '[{"type": "text", "text": "vou"}]'
  assistente m1 r1 250 '[{"type": "tool_use", "id": "t1", "name": "Edit", "input": {"file_path": "/p/a.R"}}]'
  resultado t1 false ok
  assistente m2 r2 30 '[{"type": "tool_use", "id": "t2", "name": "Bash", "input": {"command": "testes/verificar.sh"}}]'
  resultado t2 true 'Exit code 1'
  assistente m3 r3 40 '[{"type": "tool_use", "id": "t3", "name": "Edit", "input": {"file_path": "/p/a.R"}}]'
  resultado t3 false ok
  assistente m4 r4 20 '[{"type": "tool_use", "id": "t4", "name": "Bash", "input": {"command": "rm -rf x"}}]'
  resultado t4 true "The user doesn't want to proceed with this tool use."
  assistente m5 r5 0 '[{"type": "text", "text": "x"}]' '<synthetic>'
} >"$conversas/-proj/conv1.jsonl"

# Caso 1: primeira coleta.
if painel --gerar >"$tmp/coleta1.json" 2>"$tmp/erro1"; then ok "caso 1: coleta sem erro"; else falha "caso 1: coleta: $(cat "$tmp/erro1")"; fi
conferir "caso 1: lê as 10 linhas da conversa" jq_ok '.linhas_lidas == 10' "$tmp/coleta1.json"
conferir "caso 1: resposta repetida conta uma vez, com a saída final" \
  [ "$(consulta <<'PY'
import sys, pyarrow.dataset as ds
t = ds.dataset(sys.argv[1] + "/mensagens").to_table().to_pylist()
m1 = [x for x in t if x["id"] == "m1:r1"]
print(len(t), len(m1), m1[0]["saida"], m1[0]["raciocinio"], m1[0]["projeto"], m1[0]["sessao"])
PY
)" = "4 1 250 5 meu-projeto meu-projeto" ]
conferir "caso 1: falha de teste é erro; recusa do usuário não" \
  [ "$(consulta <<'PY'
import sys, pyarrow.dataset as ds
t = {x["id"]: x["erro"] for x in ds.dataset(sys.argv[1] + "/resultados").to_table().to_pylist()}
f = {x["id"]: x["alvo"] for x in ds.dataset(sys.argv[1] + "/ferramentas").to_table().to_pylist()}
print(t["t1"], t["t2"], t["t4"], f["t1"], f["t2"])
PY
)" = "False True False a.R testes" ]
conferir "caso 1: rodadas, entregas, pareceres antigos e slug do projeto" \
  [ "$(consulta <<'PY'
import sys, pyarrow.parquet as pq
t = pq.read_table(sys.argv[1] + "/validacoes.parquet").to_pylist()
print(" ".join(f'{x["projeto"]}:{x["rodada"]}:{x["resultado"]}:{x["entrega"]}:{x["origem"][0]}' for x in t))
PY
)" = "meu-projeto:1:revisar:meu-projeto#1:v meu-projeto:2:aprovado:meu-projeto#1:v meu-projeto:1:aprovado:meu-projeto#2:v velho:1:revisar:velho--tarefa#1:p velho:2:aprovado:velho--tarefa#1:p" ]
conferir "caso 1: arquivos citados nos itens do parecer REVISAR" \
  [ "$(consulta <<'P'
import sys, pyarrow.parquet as pq
t = pq.read_table(sys.argv[1] + "/apontamentos.parquet").to_pylist()
print(" ".join(sorted(l["projeto"] + ":" + l["arquivo"] for l in t)))
P
)" = "velho:app.R velho:src/a.R" ]
conferir "caso 1: indicadores do dia" \
  jq_ok '.entregas_aprovadas == 2 and .aprovacao_1a_rodada == 50 and .tokens.saida == 340
    and .tokens.cache_lido == 4000 and .aguardando_segundos >= 55' "$cache/hoje.json"

# Caso 2: a segunda coleta não relê nada; uma linha nova é lida sozinha.
painel --gerar >"$tmp/coleta2.json" 2>/dev/null
conferir "caso 2: segunda coleta incremental" jq_ok '.linhas_lidas == 0 and .mensagens_novas == 0' "$tmp/coleta2.json"
assistente m6 r6 7 '[{"type": "text", "text": "fim"}]' >>"$conversas/-proj/conv1.jsonl"
assistente m1 r1 250 '[{"type": "text", "text": "retomada"}]' >>"$conversas/-proj/conv1.jsonl"
painel --gerar >"$tmp/coleta3.json" 2>/dev/null
conferir "caso 2: só as linhas novas, sem duplicar a resposta já contada" \
  jq_ok '.linhas_lidas == 2 and .mensagens_novas == 1' "$tmp/coleta3.json"

# Caso 3: módulo da barra.
conferir "caso 3: --waybar com o app parado" \
  jq_ok '.class == "parado" and (.tooltip | test("aprovação na 1ª rodada: 50%"))' <(painel --waybar)
: >"$cache/atualizando"
conferir "caso 3: --waybar durante a coleta" jq_ok '.class == "atualizando"' <(painel --waybar)
rm -f "$cache/atualizando"
echo "a coleta falhou" >"$cache/erro.txt"
conferir "caso 3: --waybar com erro" jq_ok '.class == "erro" and (.tooltip | test("falhou"))' <(painel --waybar)
rm -f "$cache/erro.txt"

# Caso 3: --conferir aponta o que falta e não instala nada. Um Rscript que
# falha faz faltar todos os pacotes R.
mkdir -p "$tmp/rquebrado"
printf '#!/bin/sh\nexit 1\n' >"$tmp/rquebrado/Rscript"
chmod +x "$tmp/rquebrado/Rscript"
rc=0
rodar env PATH="$tmp/rquebrado:$PATH" "$repo_jangada/bin/jangada-painel" --conferir >"$tmp/conferir" 2>&1 || rc=$?
conferir "caso 3: --conferir com o R quebrado lista os pacotes R" \
  bash -c '[ "$1" = 1 ] && grep -q "falta pacotes R: shiny" "$2"' _ "$rc" "$tmp/conferir"

# Caso 4: entrega nova que começa barrada na verificação local, e sessão
# esquecida em aguardando (sem evento depois), que conta no máximo 12 horas.
mkdir -p "$tmp/e5"
{
  jq -cn '{data: "2026-01-01T10:00:00-03:00", projeto: "x", rotulo: "x", rodada: 1, resultado: "revisar", etapa: "revisor", revisor: "agy", modelo: "", autor: "claude"}'
  jq -cn '{data: "2026-01-02T10:00:00-03:00", projeto: "x", rotulo: "x", rodada: 1, resultado: "revisar", etapa: "local", revisor: "agy", modelo: "", autor: "claude"}'
} >"$tmp/e5/validar.jsonl"
conferir "caso 4: rodada 1 barrada na verificação local abre outra entrega" \
  [ "$(JANGADA_ESTADO="$tmp/e5" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=default/painel python3 -c '
import coletor
print(" ".join(l["entrega"] for l in coletor.validacoes()))')" = "x#1 x#2" ]
conferir "caso 4: sessão esquecida em aguardando conta no máximo 12 horas" \
  [ "$(PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=default/painel python3 -c '
import datetime as dt, coletor
agora = dt.datetime.now(dt.timezone.utc)
evs = [{"sessao": "s", "estado": "aguardando", "data": agora - dt.timedelta(hours=30)}]
print(int(coletor.segundos_aguardando(evs, agora - dt.timedelta(hours=48), agora, agora)))')" = "43200" ]

# Caso 4: uma coleta interrompida no meio da gravação deixa o parcial com
# ponto inicial, que a leitura da pasta ignora; interrompida no meio da
# compactação, deixa as linhas em dobro, que a compactação seguinte desfaz.
mkdir -p "$tmp/e6"
conferir "caso 4: parcial de coleta interrompida e compactação sem repetidos" \
  [ "$(cd "$tmp/e6" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo_jangada/default/painel" python3 -c '
import os, shutil, coletor, pyarrow.dataset as ds
esq = coletor.ESQ_RESULTADOS
coletor.acrescentar("r", [{"id": "a", "erro": False}], esq, "1")
print(os.path.basename(coletor.temporario("r/parte-2.parquet")), end=" ")
open(coletor.temporario("r/parte-2.parquet"), "w").write("meio arquivo")
shutil.copy("r/parte-1.parquet", "r/parte-1b.parquet")
print(ds.dataset("r", format="parquet").count_rows(), end=" ")
coletor.PARTES_MAX = 1
coletor.acrescentar("r", [{"id": "b", "erro": True}], esq, "3")
print(*sorted(ds.dataset("r", format="parquet").to_table().column("id").to_pylist()))
')" = ".parte-2.parquet.tmp 2 a b" ]
# Caso 4: a retenção tira, por dia inteiro, o que é de antes dos últimos
# JANGADA_PAINEL_RETENCAO dias e soma o consumo desses dias; as mesmas linhas
# de volta (poda interrompida ou jsonl relido) não contam em dobro.
mkdir -p "$tmp/e8"
conferir "caso 4: retenção do cache, com o consumo dos dias antigos somado" \
  [ "$(cd "$tmp/e8" && PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$repo_jangada/default/painel" python3 -c '
import datetime as dt, coletor as c, pyarrow.dataset as ds, pyarrow.parquet as pq
agora = dt.datetime.now(c.UTC)
def t(dias): return agora - dt.timedelta(days=dias)
def m(i, dias, proj="p"):
    return {"id": f"m{i}", "data": t(dias), "dia": c.dia_de(t(dias)), "conversa": "c", "subagente": "",
            "projeto": proj, "sessao": "", "cwd": "", "modelo": "opus", "entrada": 1, "saida": 10,
            "cache_criado": 0, "cache_lido": 5, "raciocinio": 2}
c.acrescentar("mensagens", [m(1, 200), m(2, 200), m(3, 200, "q"), m(4, 5)], c.ESQ_MENSAGENS, "1")
c.acrescentar("ferramentas", [{"id": f"f{i}", "data": t(d), "dia": c.dia_de(t(d)), "ferramenta": "Bash"}
                              for i, d in ((1, 200), (2, 1))], c.ESQ_FERRAMENTAS, "1")
c.acrescentar("resultados", [{"id": "f1", "data": t(200), "erro": True}, {"id": "f2", "data": t(1), "erro": False}],
              c.ESQ_RESULTADOS, "1")
ids = lambda n: ",".join(ds.dataset(n).to_table().column("id").to_pylist())
print(*c.podar(".", agora, "2", 180), ids("mensagens"), ids("ferramentas"), ids("resultados"), end=" ")
c.acrescentar("mensagens", [m(1, 200), m(2, 200)], c.ESQ_MENSAGENS, "3")
print(*c.podar(".", agora, "4", 180), end=" ")
s = pq.read_table("mensagens-dias.parquet")
print(",".join(f"{p}:{r}:{sa}" for p, r, sa in zip(*(s.column(k).to_pylist() for k in ("projeto", "respostas", "saida")))), end=" ")
print(c.podar(".", agora, "5", 0), end=" ")
import os
os.environ["JANGADA_PAINEL_RETENCAO"] = "x"
print(c.retencao())
' 2>/dev/null)" = "1 5 m4 f2 f2 0 2 p:2:20,q:1:10 (0, 0) 180" ]
mkdir -p "$tmp/config/jangada"
echo "JANGADA_PAINEL_RETENCAO=x" >"$tmp/config/jangada/jangada.conf"
painel --gerar >/dev/null 2>&1
conferir "caso 4: o JANGADA_PAINEL_RETENCAO do jangada.conf chega ao coletor" \
  grep -q "JANGADA_PAINEL_RETENCAO inválido ('x')" "$cache/coleta.log"
rm "$tmp/config/jangada/jangada.conf"
# Caso 4: delegacoes.jsonl é escrito por agentes; campo com tipo errado vira
# ausente, e um erro nos indicadores de subagentes vai para o subagentes.json.
mkdir -p "$tmp/e7/painel"
printf '%s\n' '{"data": "2026-01-01T10:00:00-03:00", "papel": 7, "tokens_retorno": "9999", "passos": true, "recusa": "sim", "motivo": "x"}' \
  >"$tmp/e7/delegacoes.jsonl"
conferir "caso 4: delegação com tipos errados não derruba os indicadores" \
  [ "$(JANGADA_ESTADO="$tmp/e7" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=default/painel python3 -c '
import subagentes
d = subagentes.delegacoes()[0]
subagentes.indicadores()
print(d["papel"], d["tokens_retorno"], d["passos"], d["recusa"])')" = "None None None True" ]
conferir "caso 4: erro nos indicadores de subagentes vai para o subagentes.json" \
  bash -c 'JANGADA_ESTADO="$1" PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=default/painel python3 -c "
import coletor, sys
sys.argv = [\"coletor.py\", \"$1/painel\"]
def quebra(): raise ValueError(\"quebrou\")
coletor.subagentes.indicadores = quebra
coletor.main()" >/dev/null 2>&1; jq -e ".erro | test(\"quebrou\")" "$1/painel/subagentes.json" >/dev/null' _ "$tmp/e7"

# Caso 5: indicadores em R e o app no ar.
if ! command -v Rscript >/dev/null 2>&1 \
  || ! Rscript -e 'for (p in c("shiny", "bslib", "bsicons", "plotly", "visNetwork", "igraph", "DT", "arrow", "jsonlite", "htmltools")) if (!requireNamespace(p, quietly = TRUE)) quit(status = 1)' 2>/dev/null; then
  echo "R ou pacotes do app ausentes; caso 5 ignorado"
else
  conferir "caso 5: indicadores em R sobre o cache" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      d <- carregar_cache(commandArgs(TRUE)[1])
      e <- entregas(d$validacoes)
      r <- resumo_aprovacao(e[e$projeto == "meu-projeto", ])
      b <- consumo_por(d$mensagens[d$mensagens$modelo != "<synthetic>", ], "projeto")
      cat(nrow(e), r$primeira_pct, r$rodadas_media, b$saida[b$projeto == "meu-projeto"], nrow(sessoes_paradas(d$sessoes, e)))
    ' "$cache" 2>/dev/null)" = "3 50 1.5 347 0" ]
  conferir "caso 5: o consumo junta o detalhe e os dias somados pela retenção" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      d <- carregar_cache(commandArgs(TRUE)[1])
      b <- consumo_por(consumo_diario(d$mensagens, d$mensagens_dias), "projeto")
      cat(paste(b$projeto, b$respostas, b$saida, b$raciocinio, sep = ":"))
    ' "$tmp/e8" 2>/dev/null)" = "p:3:30:6 q:1:10:2" ]
  conferir "caso 5: redes sobre o cache (retrabalho, transições, pontos quentes)" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      d <- carregar_cache(commandArgs(TRUE)[1])
      ch <- chamadas(d$ferramentas, d$resultados)
      ci <- ciclos_retrabalho(ch)
      g <- rede_transicoes(ch, peso_min = 1, destaque = basename(ci$arquivo))
      q <- rede_pontos_quentes(edicoes(ch))
      cat(nrow(ci), basename(ci$arquivo), "edição com retrabalho" %in% g$nos$group, nrow(q$nos), q$arestas$value)
    ' "$cache" 2>/dev/null)" = "1 a.R TRUE 2 2" ]
  conferir "caso 5: pontos quentes contam os itens REVISAR do mesmo arquivo" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      ch <- data.frame(ferramenta = "Edit", alvo = "a.R", conversa = c("c1", "c2", "c3"), sessao = c("s1", "s2", "s2"),
                       projeto = "meu-projeto", data = Sys.time() - 1:3,
                       arquivo = c("/pr/Meu Projeto/R/a.R", "/wt/Meu Projeto/tarefa/R/a.R", "/pr/Meu Projeto/b.R"))
      ed <- edicoes(ch)
      ed$arq <- normalizar_arquivo(ed$arquivo, projetos = "/pr", worktrees = "/wt")
      ap <- data.frame(projeto = "meu-projeto", arquivo = c("R/a.R", "R/a.R", "c.R"))
      q <- pontos_quentes(ed, ap)
      cat(q$arquivo[1], q$sessoes[1], q$revisar[1], q$revisar[2])
    ' 2>&1)" = "Meu Projeto/R/a.R 2 2 0" ]
  conferir "caso 5: espaço de capacidades (RCA, proximidade e típico)" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      ch <- data.frame(projeto = rep(c("a", "b", "c"), each = 40), alvo = "",
                       ferramenta = c(rep(c("Read", "Edit"), 20), rep(c("Read", "Edit"), 20), rep(c("Grep", "Bash"), 20)))
      ch$alvo[ch$ferramenta == "Bash"] <- "testes"
      e <- espaco_capacidades(ch)
      r <- rede_capacidades(e, projeto = "c")
      cat(e$proximidade["Read", "Edit"], e$proximidade["Read", "Grep"], e$projetos$projeto[1],
          sort(unique(r$nos$group)))
    ' 2>&1)" = "1 0 a outra vantagem de c" ]
  conferir "caso 5: sessão parada sem nenhuma entrega aprovada" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      v <- data.frame(data = Sys.time() - 5 * 86400, projeto = "p", rotulo = "s", rodada = 1L,
                      resultado = "revisar", etapa = "revisor", revisor = "agy", modelo = "", autor = "claude",
                      mais = NA_real_, menos = NA_real_, entrega = "s#1", stringsAsFactors = FALSE)
      s <- data.frame(sessao = "s", projeto = "p", agente = "claude", estado = "aguardando",
                      desde = Sys.time() - 5 * 86400, stringsAsFactors = FALSE)
      cat(nrow(sessoes_paradas(s, entregas(v))))
    ' 2>&1)" = "1" ]
  conferir "caso 5: o servidor do app calcula os cartões" \
    [ "$(cd default/painel && Rscript -e '
      options(jangada.painel.cache = commandArgs(TRUE)[1])
      shiny::testServer(shiny::shinyAppDir("."), {
        session$setInputs(periodo = c(Sys.Date() - 30, Sys.Date()), projeto = NULL, agente = NULL, par = NULL)
        cat(output$vb_primeira, output$vb_limite, output$vb_saida, output$vb_ciclos, output$vb_multi)
      })
    ' "$cache" 2>/dev/null)" = "33% 0 347 1 0" ]
  conferir "caso 5: a aba de subagentes calcula os cartões e o grafo" \
    [ "$(cd default/painel && Rscript -e '
      options(jangada.painel.cache = commandArgs(TRUE)[1])
      shiny::testServer(shiny::shinyAppDir("."), {
        session$setInputs(periodo = c(Sys.Date() - 30, Sys.Date()), projeto = NULL, agente = NULL, par = NULL)
        cat(output$e_fracao, output$e_recusas, output$e_desvios, grepl("recusa", output$e_arvore),
            grepl("com agy", output$e_tokens))
      })
    ' "$cache" 2>/dev/null)" = "50% 50% 3 TRUE TRUE" ]
  # Antes da primeira coleta com o módulo não há subagentes.json.
  cp -r "$cache" "$tmp/cache-sem-sub" && rm -f "$tmp/cache-sem-sub/subagentes.json"
  conferir "caso 5: a aba de subagentes sem subagentes.json" \
    [ "$(cd default/painel && Rscript -e '
      options(jangada.painel.cache = commandArgs(TRUE)[1])
      shiny::testServer(shiny::shinyAppDir("."), {
        session$setInputs(periodo = c(Sys.Date() - 30, Sys.Date()), projeto = NULL, agente = NULL, par = NULL)
        cat(output$e_fracao, grepl("com agy", output$e_tokens), grepl("sem agy", output$e_agy),
            grepl("desvio", output$e_desvios_tab))
      })
    ' "$tmp/cache-sem-sub" 2>/dev/null)" = "- TRUE TRUE TRUE" ]
  conferir "caso 5: a leitura descarta linha repetida de compactação interrompida" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      r <- file.path(commandArgs(TRUE)[1], "resultados")
      p <- list.files(r, full.names = TRUE)[1]
      invisible(file.copy(p, file.path(r, "parte-copia.parquet")))
      n <- nrow(arrow::read_parquet(p))
      cat(nrow(carregar_cache(commandArgs(TRUE)[1])$resultados) == n)
      invisible(file.remove(file.path(r, "parte-copia.parquet")))
    ' "$cache" 2>&1 | tail -n 1)" = "TRUE" ]
  conferir "caso 5: a árvore de delegação escapa o HTML dos títulos" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      a <- arvore_rede(list(list(pasta = "/p/<img src=x onerror=alert(1)>", conversa = "c:1", n = 1,
        tokens_claude = 10, passos_agy = 0, filhos = list(list(origem = "claude", id = "<b>", papel = "leitor")))))
      cat(any(grepl("<img|<b>", a$nos$title)), any(grepl("&lt;img", a$nos$title)))
    ' 2>&1 | tail -n 1)" = "FALSE TRUE" ]
  conferir "caso 5: só Host e Origin locais abrem sessão" \
    [ "$(cd default/painel && Rscript -e '
      source("indicadores.R")
      cat(origem_local("127.0.0.1:8765"), origem_local("localhost:8765", "http://localhost:8765"),
          origem_local(NULL), origem_local("evil.example:8765"), origem_local("127.0.0.1:8765", "http://evil.example"),
          origem_local("127.0.0.1.evil.example:8765"))
    ' 2>&1 | tail -n 1)" = "TRUE TRUE TRUE FALSE FALSE FALSE" ]
  conferir "caso 5: --conferir com tudo instalado" painel --conferir
  if painel >/dev/null 2>"$tmp/erro4"; then
    ok "caso 5: o app sobe"
    conferir "caso 5: a página tem o título do painel" \
      grep -q "Indicadores do jangada" <(curl -s --max-time 5 "http://127.0.0.1:$porta")
    conferir "caso 5: --waybar vê o app no ar" jq_ok '.class == "no-ar"' <(painel --waybar)
    painel --parar >/dev/null
    sleep 1
    conferir "caso 5: --parar encerra o app" \
      bash -c "! curl -s -o /dev/null --max-time 1 http://127.0.0.1:$porta"
  else
    falha "caso 5: o app não subiu: $(cat "$tmp/erro4")"
    painel --parar >/dev/null
  fi
fi

if ((falhas)); then
  echo "$falhas teste(s) do painel falharam"
  exit 1
fi
echo "todos os testes do painel passaram"
