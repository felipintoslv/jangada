#!/usr/bin/env python3
"""Coletor do jangada-painel: lê os registros e grava o cache em Parquet.

Uso: coletor.py PASTA_DO_CACHE

Lê, de forma incremental, as conversas do Claude Code (~/.claude/projects) e,
inteiros, os registros pequenos do jangada (validar.jsonl, pareceres antigos,
eventos-agentes.jsonl). Grava em PASTA_DO_CACHE:

  validacoes.parquet   uma linha por rodada do jangada-validar
  eventos.parquet      o histórico de estados dos agentes
  sessoes.parquet      as sessões abertas agora (retrato dos SESSAO.json)
  apontamentos.parquet o arquivo citado em cada item dos pareceres REVISAR
  mensagens/           uma linha por resposta do Claude, com o consumo
  ferramentas/         uma linha por chamada de ferramenta
  resultados/          uma linha por resultado de ferramenta (erro ou não)
  mensagens-dias.parquet  o consumo por dia, projeto e modelo dos dias que
                       já saíram de mensagens/
  posicoes.json        até onde cada jsonl foi lido
  coleta.json          resumo da última coleta
  hoje.json            os indicadores do dia (jangada-painel --json)
  subagentes.json      os indicadores de subagentes e delegações (subagentes.py)
  subagentes-memo.json um registro por subagente, com a assinatura dos arquivos lidos

As pastas mensagens, ferramentas e resultados recebem um arquivo novo por
coleta com dado novo, e são compactadas num só quando passam de 40. Guardam
só os últimos JANGADA_PAINEL_RETENCAO dias (padrão 180; 0 guarda tudo); o
que é mais antigo sai por dia inteiro, e o consumo desses dias fica em
mensagens-dias.parquet.

Variáveis: JANGADA_ESTADO, JANGADA_CLAUDE_PROJETOS (padrão
~/.claude/projects), JANGADA_PROJETOS, JANGADA_WORKTREES e
JANGADA_PAINEL_RETENCAO.
"""

import datetime as dt
import glob
import json
import os
import re
import sys
import time
import unicodedata

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import subagentes  # noqa: E402

INICIO = time.monotonic()
CASA = os.path.expanduser("~")
ESTADO = os.environ.get("JANGADA_ESTADO") or os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.join(CASA, ".local/state"), "jangada")
PROJETOS_CLAUDE = os.environ.get("JANGADA_CLAUDE_PROJETOS") or os.path.join(CASA, ".claude/projects")
PROJETOS = os.environ.get("JANGADA_PROJETOS") or os.path.join(CASA, "Projetos")
WORKTREES = os.environ.get("JANGADA_WORKTREES") or os.path.join(CASA, ".local/share/jangada-worktrees")
FUSO = dt.datetime.now().astimezone().tzinfo
UTC = dt.timezone.utc
PARTES_MAX = 40
RETENCAO_PADRAO = 180

# Comandos do Bash que contam como teste no retrabalho: testes, lint,
# verificação de sintaxe e execução de script R ou Python.
TESTE = re.compile(
    r"(^|[\s/;&|(])(testes?/|pytest|test(that)?\b|R CMD check|Rscript|devtools::|lintr|"
    r"shellcheck|bash -n|luac|verificar\.sh|jangada-validar|make( |$)|npm (run )?test|"
    r"cargo (test|check|build)|go test|python3? [^|;&]*\.py|ruff|mypy|quarto render)")
GIT = re.compile(r"^\s*(cd [^;&]+(&&|;)\s*)?git\b")
BUSCA = re.compile(r"^\s*(cd [^;&]+(&&|;)\s*)?(grep|rg|find|ls|cat|head|tail|sed -n|wc|tree|fd|awk)\b")


def data_de(texto):
    """Carimbo ISO (com Z ou fuso) para datetime em UTC; None se inválido."""
    if not texto:
        return None
    try:
        t = dt.datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=FUSO)
    return t.astimezone(UTC)


def dia_de(t):
    return t.astimezone(FUSO).date().isoformat() if t else None


def slug(nome):
    """O mesmo slug do bin/jangada-agente: sem acento, minúsculas, [a-z0-9_-]."""
    nome = unicodedata.normalize("NFKD", str(nome or ""))
    nome = "".join(c for c in nome if not unicodedata.combining(c)).lower()
    return re.sub(r"[^a-z0-9_-]+", "-", nome).strip("-")


def projeto_de(cwd):
    """Projeto de uma pasta: o repositório, também nos worktrees dos agentes."""
    if not cwd:
        return ""
    cwd = cwd.rstrip("/")
    for raiz in (WORKTREES, PROJETOS):
        raiz = raiz.rstrip("/")
        if cwd.startswith(raiz + "/"):
            return slug(cwd[len(raiz) + 1:].split("/")[0])
    return slug(os.path.basename(cwd) or cwd)


def sessao_jangada_de(cwd):
    """Nome da sessão do jangada que roda na pasta (repo ou repo--tarefa)."""
    if not cwd:
        return ""
    cwd = cwd.rstrip("/")
    w = WORKTREES.rstrip("/") + "/"
    if cwd.startswith(w):
        partes = cwd[len(w):].split("/")
        if len(partes) >= 2:
            return f"{partes[0]}--{partes[1]}"
    return projeto_de(cwd)


def resumir_alvo(nome, entrada):
    """Alvo resumido de uma chamada de ferramenta, para os nós das redes."""
    if not isinstance(entrada, dict):
        return "", ""
    arquivo = entrada.get("file_path") or entrada.get("notebook_path") or ""
    if nome == "Bash":
        cmd = str(entrada.get("command") or "")
        if TESTE.search(cmd):
            return "testes", ""
        if GIT.search(cmd):
            return "git", ""
        if BUSCA.search(cmd):
            return "busca", ""
        return "outro", ""
    if nome == "Skill":
        return str(entrada.get("skill") or ""), ""
    if nome in ("Agent", "Task"):
        return str(entrada.get("subagent_type") or "general-purpose"), ""
    if arquivo:
        return os.path.basename(arquivo), arquivo
    if nome in ("Grep", "Glob"):
        return "busca", ""
    return "", ""


def ler_json(caminho, padrao):
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return padrao


def temporario(caminho):
    """Nome do arquivo parcial, com ponto inicial: o arrow, no Python e no R,
    ignora esses arquivos ao ler a pasta, e um parcial deixado por uma coleta
    interrompida não quebra a leitura."""
    return os.path.join(os.path.dirname(caminho), "." + os.path.basename(caminho) + ".tmp")


def gravar_json(caminho, dado):
    tmp = temporario(caminho)
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dado, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def gravar_tabela(caminho, linhas, esquema):
    tabela = pa.Table.from_pylist(linhas, schema=esquema)
    tmp = temporario(caminho)
    pq.write_table(tabela, tmp)
    os.replace(tmp, caminho)


def sem_repetidos(tabela):
    """Uma linha por id, a primeira. Uma compactação interrompida entre gravar
    a tabela nova e apagar as partes deixa as linhas em dobro na pasta."""
    if "id" not in tabela.column_names:
        return tabela
    vistos, manter = set(), []
    for i, v in enumerate(tabela.column("id").to_pylist()):
        if v not in vistos:
            vistos.add(v)
            manter.append(i)
    return tabela if len(manter) == tabela.num_rows else tabela.take(manter)


TS = pa.timestamp("ms", tz="UTC")
ESQ_MENSAGENS = pa.schema([
    ("id", pa.string()), ("data", TS), ("dia", pa.string()), ("conversa", pa.string()),
    ("subagente", pa.string()), ("projeto", pa.string()), ("sessao", pa.string()),
    ("cwd", pa.string()), ("modelo", pa.string()), ("entrada", pa.int64()),
    ("saida", pa.int64()), ("cache_criado", pa.int64()), ("cache_lido", pa.int64()),
    ("raciocinio", pa.int64()),
])
ESQ_FERRAMENTAS = pa.schema([
    ("id", pa.string()), ("data", TS), ("dia", pa.string()), ("conversa", pa.string()),
    ("subagente", pa.string()), ("projeto", pa.string()), ("sessao", pa.string()),
    ("ferramenta", pa.string()), ("alvo", pa.string()), ("arquivo", pa.string()),
])
ESQ_RESULTADOS = pa.schema([("id", pa.string()), ("data", TS), ("erro", pa.bool_())])
TOKENS = ["entrada", "saida", "cache_criado", "cache_lido", "raciocinio"]
ESQ_MENSAGENS_DIAS = pa.schema(
    [("dia", pa.string()), ("projeto", pa.string()), ("modelo", pa.string()), ("respostas", pa.int64())]
    + [(c, pa.int64()) for c in TOKENS])
ESQ_VALIDACOES = pa.schema([
    ("data", TS), ("dia", pa.string()), ("projeto", pa.string()), ("rotulo", pa.string()),
    ("rodada", pa.int64()), ("resultado", pa.string()), ("etapa", pa.string()),
    ("revisor", pa.string()), ("modelo", pa.string()), ("autor", pa.string()),
    ("arquivos", pa.int64()), ("mais", pa.int64()), ("menos", pa.int64()),
    ("itens", pa.int64()), ("segundos", pa.int64()), ("entrega", pa.string()),
    ("origem", pa.string()),
])
ESQ_APONTAMENTOS = pa.schema([
    ("data", TS), ("dia", pa.string()), ("projeto", pa.string()), ("rotulo", pa.string()),
    ("arquivo", pa.string()),
])
ESQ_SESSOES = pa.schema([
    ("sessao", pa.string()), ("projeto", pa.string()), ("agente", pa.string()),
    ("estado", pa.string()), ("desde", TS), ("atualizado", TS),
])
ESQ_EVENTOS = pa.schema([
    ("data", TS), ("dia", pa.string()), ("sessao", pa.string()), ("projeto", pa.string()),
    ("agente", pa.string()), ("estado", pa.string()),
])


def ids_existentes(pasta):
    if not glob.glob(os.path.join(pasta, "*.parquet")):
        return set()
    return set(ds.dataset(pasta, format="parquet").to_table(columns=["id"]).column("id").to_pylist())


def reescrever(pasta, partes, tabela, destino):
    """Troca as PARTES da pasta por um só arquivo com a TABELA."""
    destino = os.path.join(pasta, destino)
    tmp = temporario(destino)
    pq.write_table(tabela, tmp)
    os.replace(tmp, destino)
    for p in partes:
        if p != destino:
            os.remove(p)


def acrescentar(pasta, linhas, esquema, carimbo):
    """Grava as linhas novas como mais um arquivo da pasta; compacta se preciso."""
    os.makedirs(pasta, exist_ok=True)
    if linhas:
        gravar_tabela(os.path.join(pasta, f"parte-{carimbo}.parquet"), linhas, esquema)
    partes = sorted(glob.glob(os.path.join(pasta, "parte-*.parquet")))
    if len(partes) > PARTES_MAX:
        tabela = sem_repetidos(ds.dataset(partes, format="parquet", schema=esquema).to_table())
        reescrever(pasta, partes, tabela, f"parte-{carimbo}-c.parquet")


# Retenção

def retencao():
    """Dias de detalhe que o cache guarda (JANGADA_PAINEL_RETENCAO); 0 guarda tudo."""
    v = os.environ.get("JANGADA_PAINEL_RETENCAO", "").strip()
    if not v:
        return RETENCAO_PADRAO
    if v.isdigit():
        return int(v)
    print(f"JANGADA_PAINEL_RETENCAO inválido ({v!r}); usando {RETENCAO_PADRAO}", file=sys.stderr)
    return RETENCAO_PADRAO


def agregar_dias(caminho, antigas):
    """Soma o consumo das mensagens ANTIGAS por dia, projeto e modelo e junta
    ao que já está em CAMINHO. Um dia já agregado fica como está: se a poda
    parou entre gravar a soma e apagar o detalhe, ou se os jsonl foram relidos
    do começo, as mesmas linhas voltam, e somá-las de novo contaria em dobro."""
    velhas = pq.read_table(caminho) if os.path.exists(caminho) else ESQ_MENSAGENS_DIAS.empty_table()
    feitos = set(velhas.column("dia").to_pylist())
    antigas = antigas.filter(pc.invert(pc.is_in(antigas.column("dia"), value_set=pa.array(sorted(feitos), pa.string()))))
    if not antigas.num_rows:
        return 0
    soma = antigas.group_by(["dia", "projeto", "modelo"]).aggregate(
        [("id", "count")] + [(c, "sum") for c in TOKENS])
    soma = soma.rename_columns([{"id_count": "respostas"}.get(n, n.removesuffix("_sum")) for n in soma.column_names])
    soma = soma.select(ESQ_MENSAGENS_DIAS.names).cast(ESQ_MENSAGENS_DIAS)
    tabela = pa.concat_tables([velhas.cast(ESQ_MENSAGENS_DIAS), soma]).sort_by(
        [("dia", "ascending"), ("projeto", "ascending"), ("modelo", "ascending")])
    tmp = temporario(caminho)
    pq.write_table(tabela, tmp)
    os.replace(tmp, caminho)
    return len(set(soma.column("dia").to_pylist()))


def podar(cache, agora, carimbo, dias):
    """Tira de mensagens/, ferramentas/ e resultados/ o que é de antes dos
    últimos DIAS dias, por dia inteiro. O consumo desses dias fica somado em
    mensagens-dias.parquet; as chamadas e os resultados só saem, porque os
    indicadores de ferramentas dependem da sequência das chamadas, que uma
    contagem por dia não guarda. Devolve (dias agregados, linhas tiradas)."""
    if dias <= 0:
        return 0, 0
    limite = (agora.astimezone(FUSO).date() - dt.timedelta(days=dias)).isoformat()
    # Resultados não têm dia: vale a meia-noite local do dia limite.
    limite_ts = dt.datetime.combine(dt.date.fromisoformat(limite), dt.time(), FUSO).astimezone(UTC)
    agregados = tirados = 0
    for nome, esquema, campo, corte in (("mensagens", ESQ_MENSAGENS, "dia", limite),
                                        ("ferramentas", ESQ_FERRAMENTAS, "dia", limite),
                                        ("resultados", ESQ_RESULTADOS, "data", limite_ts)):
        pasta = os.path.join(cache, nome)
        partes = sorted(glob.glob(os.path.join(pasta, "parte-*.parquet")))
        if not partes:
            continue
        dados = ds.dataset(partes, format="parquet", schema=esquema)
        antigo = ds.field(campo) < pa.scalar(corte, esquema.field(campo).type)
        n = dados.count_rows(filter=antigo)
        if not n:
            continue
        if nome == "mensagens":
            agregados = agregar_dias(os.path.join(cache, "mensagens-dias.parquet"),
                                     dados.to_table(filter=antigo))
        # Linha sem data fica: não há como saber se é antiga.
        manter = sem_repetidos(dados.to_table(filter=~antigo | ds.field(campo).is_null()))
        reescrever(pasta, partes, manter, f"parte-{carimbo}-p.parquet")
        tirados += n
    return agregados, tirados


# Conversas do Claude Code

# Recusas de permissão e do usuário vêm com is_error, mas não são falha.
RECUSA = re.compile(r"doesn't want to proceed|[Pp]ermission .*denied|<tool_use_error>Blocked")


def erro_de(bloco):
    if not bloco.get("is_error"):
        return False
    c = bloco.get("content")
    if isinstance(c, list):
        c = " ".join(str(x.get("text") or "") for x in c if isinstance(x, dict))
    return not RECUSA.search(str(c or "")[:500])


def conversas_claude(cache, posicoes, resumo):
    """Lê o que é novo em cada jsonl e devolve as linhas novas das três tabelas."""
    vistos_m = ids_existentes(os.path.join(cache, "mensagens"))
    vistos_f = ids_existentes(os.path.join(cache, "ferramentas"))
    vistos_r = ids_existentes(os.path.join(cache, "resultados"))
    mensagens, ferramentas, resultados = [], [], []
    # Resposta repetida na mesma leitura: a primeira linha pode trazer a saída
    # parcial; fica a de maior output_tokens.
    indice_m = {}
    arquivos = glob.glob(os.path.join(PROJETOS_CLAUDE, "*", "*.jsonl")) \
        + glob.glob(os.path.join(PROJETOS_CLAUDE, "*", "*", "subagents", "*.jsonl"))
    novas_posicoes = {}
    for caminho in arquivos:
        try:
            st = os.stat(caminho)
        except OSError:
            continue
        ant = posicoes.get(caminho) or {}
        pos = ant.get("pos", 0)
        if ant.get("ino") != st.st_ino or st.st_size < pos:
            pos = 0  # arquivo novo, trocado ou truncado: do começo
        if st.st_size == pos:
            novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos}
            continue
        resumo["arquivos_lidos"] += 1
        linhas = []
        bytes_lidos = 0
        with open(caminho, "rb") as f:
            f.seek(pos)
            for linha in f:
                if not linha.endswith(b"\n"):
                    break
                linhas.append(linha)
                bytes_lidos += len(linha)
        if not linhas:
            novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos}
            continue
        # Se a última linha lida for de assistant com stop_reason nulo, a resposta
        # ainda está sendo escrita pelo Claude; não avança a posição sobre ela
        # para que seja lida por inteiro na coleta seguinte.
        ultima = linhas[-1]
        if b'"assistant"' in ultima and b'"stop_reason"' in ultima:
            try:
                d_ult = json.loads(ultima)
                if isinstance(d_ult, dict) and d_ult.get("type") == "assistant":
                    m_ult = d_ult.get("message")
                    if isinstance(m_ult, dict) and "stop_reason" in m_ult and m_ult.get("stop_reason") is None:
                        descartada = linhas.pop()
                        bytes_lidos -= len(descartada)
            except ValueError:
                pass
        if not linhas:
            novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos}
            continue
        novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos + bytes_lidos}
        resumo["bytes_lidos"] += bytes_lidos
        for linha in linhas:
            bruto = linha.rstrip(b"\r\n")
            resumo["linhas_lidas"] += 1
            tem_uso = b'"usage"' in bruto
            tem_ferr = b'"tool_use"' in bruto
            tem_res = b'"tool_result"' in bruto
            if not (tem_uso or tem_ferr or tem_res):
                continue
            try:
                d = json.loads(bruto)
            except ValueError:
                continue
            if not isinstance(d, dict):
                continue
            m = d.get("message")
            if not isinstance(m, dict):
                continue
            t = data_de(d.get("timestamp"))
            if t is None:
                continue
            cwd = d.get("cwd") or ""
            base = {
                "data": t, "dia": dia_de(t), "conversa": d.get("sessionId") or "",
                "subagente": d.get("agentId") or "" if d.get("isSidechain") else "",
                "projeto": projeto_de(cwd), "sessao": sessao_jangada_de(cwd),
            }
            conteudo = m.get("content") if isinstance(m.get("content"), list) else []
            if d.get("type") == "assistant":
                u = m.get("usage")
                chave = f'{m.get("id")}:{d.get("requestId")}'
                # A mesma resposta aparece numa linha por bloco de conteúdo e se
                # repete nas conversas retomadas: conta uma vez só.
                # O modelo <synthetic> é mensagem do próprio Claude Code, sem consumo.
                if m.get("model") == "<synthetic>":
                    u = None
                if isinstance(u, dict) and (chave not in vistos_m or chave in indice_m):
                    det = u.get("output_tokens_details") or {}
                    rac = det.get("thinking_tokens") if isinstance(det, dict) else None
                    linha = dict(base, id=chave, cwd=cwd, modelo=m.get("model") or "",
                                 entrada=u.get("input_tokens") or 0,
                                 saida=u.get("output_tokens") or 0,
                                 cache_criado=u.get("cache_creation_input_tokens") or 0,
                                 cache_lido=u.get("cache_read_input_tokens") or 0,
                                 raciocinio=rac)
                    if chave in indice_m:
                        if linha["saida"] > mensagens[indice_m[chave]]["saida"]:
                            mensagens[indice_m[chave]] = linha
                    else:
                        vistos_m.add(chave)
                        indice_m[chave] = len(mensagens)
                        mensagens.append(linha)
                for b in conteudo:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        tid = b.get("id") or ""
                        if not tid or tid in vistos_f:
                            continue
                        vistos_f.add(tid)
                        nome = b.get("name") or ""
                        alvo, arquivo = resumir_alvo(nome, b.get("input"))
                        ferramentas.append(dict(base, id=tid, ferramenta=nome, alvo=alvo, arquivo=arquivo))
            elif d.get("type") == "user":
                for b in conteudo:
                    if isinstance(b, dict) and b.get("type") == "tool_result":
                        tid = b.get("tool_use_id") or ""
                        if not tid or tid in vistos_r:
                            continue
                        vistos_r.add(tid)
                        resultados.append({"id": tid, "data": t, "erro": erro_de(b)})
    return mensagens, ferramentas, resultados, novas_posicoes


# Registros do jangada

# Pastas dos pareceres: agentes/, gravável pelo agente isolado, e revisoes/,
# das revisões feitas fora do isolamento, que ele não alcança.
PASTAS_PARECERES = ("agentes", "revisoes")


def validacoes():
    """Rodadas do validar.jsonl e, antes dele, as dos pareceres antigos.

    A origem diz quem gravou: "validar.jsonl" é o jangada-validar rodado
    dentro do isolamento, num arquivo que o agente pode alterar; "revisoes" é
    o rodado fora dele."""
    linhas = []
    brutas = []
    for arq, origem in ((os.path.join(ESTADO, "validar.jsonl"), "validar.jsonl"),
                        (os.path.join(ESTADO, "revisoes", "validar.jsonl"), "revisoes")):
        try:
            with open(arq, encoding="utf-8", errors="replace") as f:
                brutas += [(b, origem) for b in f]
        except OSError:
            pass
    for bruta, origem in brutas:
        try:
            d = json.loads(bruta)
        except ValueError:
            continue
        if not isinstance(d, dict):
            continue
        t = data_de(d.get("data"))
        if t is None:
            continue
        num = lambda k: d.get(k) if isinstance(d.get(k), int) else None
        linhas.append({
            "data": t, "dia": dia_de(t), "projeto": slug(d.get("projeto")),
            "rotulo": str(d.get("rotulo") or ""), "rodada": num("rodada"),
            "resultado": str(d.get("resultado") or ""), "etapa": str(d.get("etapa") or ""),
            "revisor": str(d.get("revisor") or ""), "modelo": str(d.get("modelo") or ""),
            "autor": str(d.get("autor") or ""), "arquivos": num("arquivos"), "mais": num("mais"),
            "menos": num("menos"), "itens": num("itens"), "segundos": num("segundos"),
            "origem": origem,
        })
    # Pareceres antigos: a validação grava o parecer no mesmo segundo da linha
    # do validar.jsonl; um parecer só entra se não houver linha do mesmo rótulo
    # a até 60 s. As avaliacao-* são avaliações do Claude, não revisões. O N
    # do arquivo não é a rodada: o antigo jangada-par recomeçava do r1 e
    # sobrescrevia o arquivo. A ordem vem do mtime.
    ja = {}
    for l in linhas:
        if l["origem"] == "validar.jsonl":
            ja.setdefault(l["rotulo"], []).append(l["data"])
    padrao = re.compile(r"^(validacao|parecer)-(.+)-r(\d+)\.md$")
    antigos = []
    for caminho in glob.glob(os.path.join(ESTADO, "agentes", "*-r*.md")):
        m = padrao.match(os.path.basename(caminho))
        if not m:
            continue
        try:
            t = dt.datetime.fromtimestamp(os.stat(caminho).st_mtime, UTC)
            with open(caminho, encoding="utf-8", errors="replace") as f:
                texto = f.read(20000)
        except OSError:
            continue
        rotulo = m.group(2)
        if any(abs((t - x).total_seconds()) <= 60 for x in ja.get(rotulo, [])):
            continue
        cabeca = "\n".join(texto.splitlines()[:5])
        if "APROVADO" in cabeca:
            resultado = "aprovado"
        elif "REVISAR" in cabeca:
            resultado = "revisar"
        else:
            continue
        itens = len(re.findall(r"(?m)^\s*\d+\.\s", texto)) if resultado == "revisar" else 0
        # Os parecer-* vêm do antigo jangada-par: o Claude escrevia e o agy revisava.
        par = m.group(1) == "parecer"
        antigos.append({
            "data": t, "dia": dia_de(t), "projeto": slug(rotulo.split("--")[0]), "rotulo": rotulo, "resultado": resultado, "etapa": "revisor",
            "revisor": "agy" if par else "", "modelo": "", "autor": "claude" if par else "",
            "arquivos": None, "mais": None, "menos": None, "itens": itens, "segundos": None,
            "origem": "parecer",
        })
    antigos.sort(key=lambda l: (l["rotulo"], l["data"]))
    rodada, rot_ant = 0, None
    for l in antigos:
        rodada = 1 if l["rotulo"] != rot_ant else rodada + 1
        rot_ant = l["rotulo"]
        l["rodada"] = rodada
        if l["resultado"] == "aprovado":
            rodada = 0
    linhas += antigos
    # Entrega: as rodadas de um rótulo até um APROVADO (ou até a próxima
    # rodada 1, quando a entrega foi abandonada sem aprovação). As revisões de
    # fora contam as rodadas à parte e formam entregas próprias.
    fora = lambda l: l["origem"] == "revisoes"
    linhas.sort(key=lambda l: (l["rotulo"], fora(l), l["data"]))
    seq, rot_ant, fechada = 0, None, True
    for l in linhas:
        chave = (l["rotulo"], fora(l))
        if chave != rot_ant:
            seq, rot_ant, fechada = 1, chave, False
        elif fechada or l["rodada"] == 1:
            seq, fechada = seq + 1, False
        l["entrega"] = f'{l["rotulo"]}#{"fora-" if fora(l) else ""}{seq}'
        if l["resultado"] == "aprovado":
            fechada = True
    return linhas


# Arquivo citado no início de um item do parecer: "arq:12", "`arq`" ou
# "[arq:12](file://...)". Itens sem arquivo (critérios em negrito) ficam de fora.
ITEM = re.compile(r"^\s*\d+\.\s+(.*)")
CITACAO_LINHA = re.compile(r"([\w.\-]+(?:/[\w.\-]+)*):\d+")
CITACAO_CRASE = re.compile(r"`([\w.\-]*(?:/[\w.\-]+)*\.\w+|[\w.\-]+(?:/[\w.\-]+)+)`")


def apontamentos():
    """Arquivos citados nos itens dos pareceres REVISAR, um por item."""
    linhas = []
    padrao = re.compile(r"^(?:validacao|parecer)-(.+)-r\d+\.md$")
    caminhos = [c for p in PASTAS_PARECERES for c in glob.glob(os.path.join(ESTADO, p, "*-r*.md"))]
    for caminho in caminhos:
        m = padrao.match(os.path.basename(caminho))
        if not m:
            continue
        try:
            t = dt.datetime.fromtimestamp(os.stat(caminho).st_mtime, UTC)
            with open(caminho, encoding="utf-8", errors="replace") as f:
                texto = f.read(200000).splitlines()
        except OSError:
            continue
        if "REVISAR" not in "\n".join(texto[:5]):
            continue
        rotulo = m.group(1)
        for l in texto:
            item = ITEM.match(l)
            if not item:
                continue
            c = CITACAO_LINHA.search(item.group(1)) or CITACAO_CRASE.search(item.group(1))
            if c and ("/" in c.group(1) or "." in c.group(1).lstrip(".")):
                linhas.append({"data": t, "dia": dia_de(t), "projeto": slug(rotulo.split("--")[0]),
                               "rotulo": rotulo, "arquivo": c.group(1)})
    return linhas


def eventos():
    linhas = []
    try:
        with open(os.path.join(ESTADO, "eventos-agentes.jsonl"), encoding="utf-8", errors="replace") as f:
            for bruta in f:
                try:
                    d = json.loads(bruta)
                except ValueError:
                    continue
                t = data_de(d.get("data")) if isinstance(d, dict) else None
                if t is None:
                    continue
                linhas.append({"data": t, "dia": dia_de(t), "sessao": str(d.get("sessao") or ""),
                               "projeto": slug(d.get("projeto")), "agente": str(d.get("agente") or ""),
                               "estado": str(d.get("estado") or "")})
    except OSError:
        pass
    linhas.sort(key=lambda l: l["data"])
    return linhas


def sessoes():
    """Retrato das sessões do jangada abertas agora: os SESSAO.json não têm
    histórico, e o app não lê fora do cache."""
    linhas = []
    for caminho in glob.glob(os.path.join(ESTADO, "agentes", "*.json")):
        d = ler_json(caminho, None)
        if not isinstance(d, dict) or not d.get("sessao"):
            continue
        agente = os.path.basename(str(d.get("agente") or "").split(" ")[0])
        linhas.append({"sessao": str(d["sessao"]), "projeto": slug(os.path.basename(str(d.get("raiz") or d.get("dir") or ""))),
                       "agente": agente, "estado": str(d.get("estado") or ""),
                       "desde": data_de(d.get("desde")), "atualizado": data_de(d.get("atualizado"))})
    return linhas


# Indicadores do dia

def segundos_aguardando(evs, ini, fim, agora):
    """Tempo, entre ini e fim, com alguma sessão em "aguardando"; por sessão, somado."""
    total = 0.0
    por_sessao = {}
    for e in evs:
        por_sessao.setdefault(e["sessao"], []).append(e)
    for lista in por_sessao.values():
        for i, e in enumerate(lista):
            if e["estado"] != "aguardando":
                continue
            a = e["data"]
            # O foco e os subagentes não mudam o estado da sessão; o intervalo
            # vai até o próximo evento de estado.
            # Sem evento depois, a sessão pode ter sido esquecida em aguardando:
            # conta no máximo 12 horas, como no app.
            b = next((x["data"] for x in lista[i + 1:]
                      if x["estado"] != "foco" and not x["estado"].startswith("subagente")),
                     min(agora, a + dt.timedelta(hours=12)))
            a, b = max(a, ini), min(b, fim)
            if b > a:
                total += (b - a).total_seconds()
    return total


def indicadores_do_dia(cache, vals, evs, agora):
    hoje = dia_de(agora)
    ini = dt.datetime.combine(agora.astimezone(FUSO).date(), dt.time(), FUSO).astimezone(UTC)
    fim = ini + dt.timedelta(days=1)
    # A revisão de fora repete, na integração, uma entrega já revisada dentro.
    aprov = [v for v in vals if v["dia"] == hoje and v["resultado"] == "aprovado"
             and v["origem"] != "revisoes"]
    primeira = [v for v in aprov if v["rodada"] == 1]
    saida = entrada = criado = lido = 0
    pasta = os.path.join(cache, "mensagens")
    if glob.glob(os.path.join(pasta, "*.parquet")):
        t = ds.dataset(pasta, format="parquet").to_table(
            columns=["entrada", "saida", "cache_criado", "cache_lido"], filter=ds.field("dia") == hoje)
        soma = lambda c: int(pa.compute.sum(t.column(c)).as_py() or 0) if t.num_rows else 0
        entrada, saida, criado, lido = soma("entrada"), soma("saida"), soma("cache_criado"), soma("cache_lido")
    evs_dia = [e for e in evs if e["data"] < fim]
    primeiro_evento = min((e["data"] for e in evs), default=None)
    return {
        "dia": hoje,
        "atualizado": agora.astimezone(FUSO).isoformat(timespec="seconds"),
        "entregas_aprovadas": len(aprov),
        "aprovacao_1a_rodada": round(100 * len(primeira) / len(aprov)) if aprov else None,
        "no_limite": sum(1 for v in vals if v["dia"] == hoje and v["resultado"] == "limite"),
        "tokens": {"entrada": entrada, "saida": saida, "cache_criado": criado, "cache_lido": lido},
        "aguardando_segundos": round(segundos_aguardando(evs_dia, ini, fim, agora)),
        "eventos_desde": dia_de(primeiro_evento),
    }


def main():
    if len(sys.argv) != 2:
        print(__doc__.split("\n\n")[1], file=sys.stderr)
        return 1
    cache = sys.argv[1]
    os.makedirs(cache, exist_ok=True)
    agora = dt.datetime.now(UTC)
    carimbo = agora.strftime("%Y%m%dT%H%M%S%f")
    resumo = {"arquivos_lidos": 0, "linhas_lidas": 0, "bytes_lidos": 0}
    arq_pos = os.path.join(cache, "posicoes.json")
    posicoes = ler_json(arq_pos, {})
    mens, ferr, res, novas = conversas_claude(cache, posicoes, resumo)
    acrescentar(os.path.join(cache, "mensagens"), mens, ESQ_MENSAGENS, carimbo)
    acrescentar(os.path.join(cache, "ferramentas"), ferr, ESQ_FERRAMENTAS, carimbo)
    acrescentar(os.path.join(cache, "resultados"), res, ESQ_RESULTADOS, carimbo)
    # As posições só são gravadas depois das tabelas: uma coleta interrompida
    # relê o trecho, e os ids evitam a duplicata.
    gravar_json(arq_pos, novas)
    agregados, tirados = podar(cache, agora, carimbo, retencao())
    vals = validacoes()
    evs = eventos()
    gravar_tabela(os.path.join(cache, "validacoes.parquet"), vals, ESQ_VALIDACOES)
    gravar_tabela(os.path.join(cache, "eventos.parquet"), evs, ESQ_EVENTOS)
    gravar_tabela(os.path.join(cache, "sessoes.parquet"), sessoes(), ESQ_SESSOES)
    gravar_tabela(os.path.join(cache, "apontamentos.parquet"), apontamentos(), ESQ_APONTAMENTOS)
    gravar_json(os.path.join(cache, "hoje.json"), indicadores_do_dia(cache, vals, evs, agora))
    # Os indicadores de subagentes não derrubam a coleta. O erro vai para o
    # subagentes.json, e o painel o mostra em vez dos números da coleta anterior.
    # O memo guarda um registro por subagente com a assinatura dos arquivos
    # lidos; só os que mudaram são relidos. É gravado depois dos indicadores,
    # e um memo ilegível apenas faz reler tudo.
    try:
        arq_memo = os.path.join(cache, "subagentes-memo.json")
        memo = ler_json(arq_memo, {})
        if not isinstance(memo, dict):
            memo = {}
        gravar_json(os.path.join(cache, "subagentes.json"), subagentes.indicadores(memo=memo))
        gravar_json(arq_memo, memo)
    except Exception as e:  # noqa: BLE001
        print(f"subagentes: {e!r}", file=sys.stderr)
        gravar_json(os.path.join(cache, "subagentes.json"),
                    {"erro": repr(e), "data": agora.astimezone(FUSO).isoformat(timespec="seconds")})
    resumo.update({"mensagens_novas": len(mens), "ferramentas_novas": len(ferr),
                   "resultados_novos": len(res), "dias_agregados": agregados, "linhas_podadas": tirados,
                   "validacoes": len(vals), "eventos": len(evs),
                   "data": agora.astimezone(FUSO).isoformat(timespec="seconds"),
                   "segundos": round(time.monotonic() - INICIO, 2)})
    gravar_json(os.path.join(cache, "coleta.json"), resumo)
    print(json.dumps(resumo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
