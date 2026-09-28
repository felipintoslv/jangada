"""Subagentes do Claude e do agy e delegações do jangada-delegar.

Lê, sem rede e só com a biblioteca padrão:
  ~/.claude/projects/PROJETO/SESSAO/subagents/agent-ID.{meta.json,jsonl}
      e a conversa mãe SESSAO.jsonl (totais e retorno de cada subagente);
  ~/.gemini/antigravity-cli/brain/CONVERSA/.system_generated/subagents/*.json
      e conversations/ID.db (passos);
  ~/.local/state/jangada/delegacoes.jsonl.

Usado pelo jangada-subagentes (métrica e campo subagentes do validar.jsonl) e
pelo coletor do painel. Medida ausente fica None ("sem medida"), nunca zero.

Uso: subagentes.py [--json]
       os oito indicadores de uso (texto, ou JSON com --json)
     subagentes.py --entrega PASTA [--desde ISO] [--ate ISO]
       resumo de uma entrega em JSON (campo subagentes do validar.jsonl)
     subagentes.py --registros
       um JSON por linha para cada subagente e delegação lida
"""

import argparse
import datetime as dt
import glob
import json
import os
import re
import sqlite3
import sys
from urllib.parse import unquote, urlparse

CASA = os.path.expanduser("~")
ESTADO = os.environ.get("JANGADA_ESTADO") or os.path.join(
    os.environ.get("XDG_STATE_HOME") or os.path.join(CASA, ".local/state"), "jangada")
PROJETOS_CLAUDE = os.environ.get("JANGADA_CLAUDE_PROJETOS") or os.path.join(CASA, ".claude/projects")
AGY = os.environ.get("JANGADA_AGY_DIR") or os.path.join(CASA, ".gemini/antigravity-cli")

PAPEIS = (
    "explorador", "leitor", "pesquisador", "verificador",
    "auditor", "arquiteto", "otimizador", "redator",
)
EDICAO_CLAUDE = {"Edit", "Write", "NotebookEdit", "MultiEdit"}
EDICAO_AGY = (b"write_to_file", b"replace_file_content", b"multi_replace_file_content")
REVISAO = re.compile(r"revis|validar|review", re.I)
# Retorno de subagente que casou errado dá razão de compressão absurda.
RAZAO_MAX = 1000
HANDBACK = re.compile(r'<agent-message from="([^"]+)">')
TAREFA = re.compile(r"<task-id>([^<]+)</task-id>")
RESULTADO = re.compile(r"<result>(.*?)</result>", re.S)
ESTADO_TAREFA = re.compile(r"<status>([^<]+)</status>")


def instante(texto):
    """Segundos desde a época para um ISO 8601 (com Z ou fuso) ou None."""
    if not texto:
        return None
    try:
        t = dt.datetime.fromisoformat(str(texto).replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.astimezone()
    return t.timestamp()


def iso(seg):
    return None if seg is None else dt.datetime.fromtimestamp(seg).astimezone().isoformat(timespec="seconds")


def tokens_de_texto(texto):
    """Estimativa de 4 caracteres por token, como no jangada-delegar."""
    return (len(texto) + 3) // 4


def texto_de(conteudo):
    if isinstance(conteudo, str):
        return conteudo
    if isinstance(conteudo, list):
        return "".join(b.get("text", "") for b in conteudo if isinstance(b, dict))
    return ""


def miolo(texto):
    """O relatório de dentro do <agent-message>, sem o invólucro."""
    i = texto.find("<agent-message")
    if i < 0:
        return texto
    i = texto.find(">", i) + 1
    j = texto.rfind("</agent-message>")
    return texto[i:j if j > i else None].strip()


def linhas_json(caminho):
    try:
        with open(caminho, encoding="utf-8", errors="replace") as f:
            for linha in f:
                try:
                    d = json.loads(linha)
                except ValueError:
                    continue
                if isinstance(d, dict):
                    yield d
    except OSError:
        return


def indice_mae(caminho):
    """Totais e retorno dos subagentes, lidos da conversa mãe.

    Primeiro plano: o tool_result da chamada Agent traz totalTokens e o texto.
    Segundo plano: o task-notification traz o uso e o relatório vem numa
    mensagem SubagentHandback à parte (ou no <result> do aviso).
    """
    frente, fundo, volta = {}, {}, {}
    for d in linhas_json(caminho):
        tur = d.get("toolUseResult")
        if d.get("type") == "user" and isinstance(tur, dict) and "totalTokens" in tur:
            conteudo = (d.get("message") or {}).get("content")
            if isinstance(conteudo, list) and conteudo and isinstance(conteudo[0], dict):
                frente[conteudo[0].get("tool_use_id")] = {
                    "tokens": tur.get("totalTokens"),
                    "ms": tur.get("totalDurationMs"),
                    "ferramentas": tur.get("totalToolUseCount"),
                    "retorno": texto_de(tur.get("content")) or texto_de(conteudo[0].get("content")),
                }
            continue
        att = d.get("attachment")
        if d.get("type") == "attachment" and isinstance(att, dict) and isinstance(att.get("prompt"), str):
            # O SubagentHandback também chega como comando na fila.
            m = HANDBACK.search(att["prompt"][:400])
            if m and "<task-notification>" not in att["prompt"]:
                volta[m.group(1)] = max(volta.get(m.group(1), ""), miolo(att["prompt"]), key=len)
                continue
            m = TAREFA.search(att["prompt"])
            if m and "<task-notification>" in att["prompt"]:
                u = att.get("usage") or {}
                r = RESULTADO.search(att["prompt"])
                r = r.group(1).strip() if r else ""
                # "entregue como mensagem" aponta para o SubagentHandback.
                if "SubagentHandback" in r or "delivered to you as a message" in r:
                    r = ""
                st = ESTADO_TAREFA.search(att["prompt"])
                fundo[m.group(1)] = {"tokens": u.get("totalTokens"), "ms": u.get("durationMs"),
                                     "ferramentas": u.get("toolUses"), "retorno": r,
                                     "estado": st.group(1) if st else None}
            continue
        if d.get("type") == "user":
            conteudo = texto_de((d.get("message") or {}).get("content"))
            m = HANDBACK.search(conteudo[:400]) if conteudo.startswith("Another Claude session") else None
            if m:
                volta[m.group(1)] = max(volta.get(m.group(1), ""), miolo(conteudo), key=len)
    return frente, fundo, volta


def assinatura(*caminhos):
    """mtime e tamanho de cada arquivo (None se faltar): muda quando o arquivo
    muda, e é o que decide se o registro guardado ainda vale."""
    saida = []
    for c in caminhos:
        try:
            st = os.stat(c)
            saida.append([st.st_mtime_ns, st.st_size])
        except OSError:
            saida.append(None)
    return saida


def guardado(memo, chave, assin):
    """Registro de memo[chave], se a assinatura dos arquivos é a mesma."""
    e = (memo or {}).get(chave)
    if isinstance(e, dict) and e.get("assinatura") == assin and isinstance(e.get("registro"), dict):
        return e["registro"]
    return None


def claude(raiz=None, pasta=None, desde=None, memo=None):
    """Um dicionário por subagente do Claude (só os da pasta, se dada).

    Com memo (dicionário de uma leitura anterior), o subagente cujo meta.json,
    jsonl e conversa mãe não mudaram sai do memo, sem reler; ao fim o memo fica
    só com os subagentes vistos nesta leitura."""
    raiz = raiz or PROJETOS_CLAUDE
    ini_limite = instante(desde) if desde else None
    padrao_proj = "*"
    if pasta:
        candidato = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(pasta))
        if os.path.isdir(os.path.join(raiz, candidato)):
            padrao_proj = candidato
    maes = {}
    saida = []
    novo = {}
    for meta in sorted(glob.glob(os.path.join(raiz, padrao_proj, "*", "subagents", "agent-*.meta.json"))):
        if ini_limite is not None:
            try:
                if os.path.getmtime(meta) < ini_limite:
                    continue
            except OSError:
                continue
        sessdir = os.path.dirname(os.path.dirname(meta))
        mae = sessdir + ".jsonl"
        assin = assinatura(meta, meta[:-len(".meta.json")] + ".jsonl", mae)
        reg = guardado(memo, meta, assin)
        if reg is not None:
            novo[meta] = {"assinatura": assin, "registro": reg}
            if not pasta or mesma_pasta(reg.get("pasta"), pasta):
                saida.append(reg)
            continue
        try:
            m = json.load(open(meta, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        agente = os.path.basename(meta)[len("agent-"):-len(".meta.json")]
        cwd = None; ini = fim = None; pedido = ""
        tokens_proprios = 0; edicoes = 0; ferramentas = 0
        for d in linhas_json(meta[:-len(".meta.json")] + ".jsonl"):
            cwd = cwd or d.get("cwd")
            t = instante(d.get("timestamp"))
            if t is not None:
                ini = t if ini is None else min(ini, t)
                fim = t if fim is None else max(fim, t)
            msg = d.get("message") or {}
            if d.get("type") == "user" and not pedido:
                pedido = texto_de(msg.get("content"))
            if d.get("type") != "assistant":
                continue
            # O totalTokens da conversa mãe é o contexto da última resposta
            # (entrada, cache e saída), não a soma das respostas: a medida
            # própria segue a mesma regra.
            u = msg.get("usage") or {}
            if u:
                tokens_proprios = sum(u.get(k) or 0 for k in (
                    "input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens"))
            for b in msg.get("content") or []:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    ferramentas += 1
                    edicoes += b.get("name") in EDICAO_CLAUDE
        if pasta and not mesma_pasta(cwd, pasta):
            continue
        if mae not in maes:
            maes[mae] = indice_mae(mae)
        frente, fundo, volta = maes[mae]
        total = frente.get(m.get("toolUseId")) or fundo.get(agente)
        retorno = (total or {}).get("retorno") or volta.get(agente) or ""
        tokens = (total or {}).get("tokens") or (tokens_proprios or None)
        ret_tok = tokens_de_texto(retorno) if retorno else None
        razao = round(tokens / ret_tok, 1) if tokens and ret_tok else None
        tipo = m.get("agentType") or ""
        descricao = m.get("description") or ""
        reg = {
            "origem": "claude", "id": agente, "conversa": os.path.basename(sessdir),
            "pasta": cwd, "inicio": iso(ini), "fim": iso(fim), "tipo": tipo,
            "papel": tipo if tipo in PAPEIS else None, "descricao": descricao,
            "profundidade": m.get("spawnDepth"), "forma": m.get("requestShape"),
            "estado": (total or {}).get("estado") or ("completed" if total else None),
            "tokens": tokens, "retorno_tokens": ret_tok, "razao": razao,
            "casamento": None if razao is None else razao <= RAZAO_MAX,
            "passos": None, "edicoes": edicoes, "ferramentas": (total or {}).get("ferramentas") or ferramentas,
            "autorrevisao": tipo not in PAPEIS and bool(REVISAO.search(descricao + " " + pedido[:200])),
            "generico": tipo == "general-purpose",
            "sem_fonte": sem_fonte(retorno) if retorno else None,
        }
        novo[meta] = {"assinatura": assin, "registro": reg}
        saida.append(reg)
    if memo is not None:
        memo.clear()
        memo.update(novo)
    return saida


def banco_agy(conversa):
    return os.path.join(AGY, "conversations", conversa + ".db")


def passos_agy(conversa):
    """(passos, passos de escrita) de uma conversa do agy, ou (None, None)."""
    banco = banco_agy(conversa)
    if not os.path.exists(banco):
        return None, None
    try:
        con = sqlite3.connect(f"file:{banco}?mode=ro", uri=True)
        try:
            n = con.execute("select count(*) from steps").fetchone()[0]
            escrita = 0
            for (carga,) in con.execute("select step_payload from steps"):
                if isinstance(carga, str):
                    carga = carga.encode()
                escrita += bool(carga) and any(e in carga for e in EDICAO_AGY)
        finally:
            con.close()
    except sqlite3.Error:
        return None, None
    return n, escrita


def agy(raiz=None, pasta=None, memo=None):
    """Um dicionário por subagente do agy (só os da pasta, se dada). O memo
    funciona como no claude(), com o json do subagente e o banco da conversa."""
    raiz = raiz or AGY
    saida = []
    novo = {}
    for arq in sorted(glob.glob(os.path.join(raiz, "brain", "*", ".system_generated", "subagents", "*.json"))):
        # O banco tem o nome da conversa, que só se sabe lendo o json: a
        # assinatura usa a conversa do registro guardado.
        ant = ((memo or {}).get(arq) or {}).get("registro") or {}
        reg = guardado(memo, arq, assinatura(arq, banco_agy(str(ant.get("id")))))
        if reg is not None:
            novo[arq] = memo[arq]
            if not pasta or mesma_pasta(reg.get("pasta"), pasta):
                saida.append(reg)
            continue
        try:
            d = json.load(open(arq, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        desc = d.get("subagentDescriptor") or {}
        tipo = desc.get("typeName") or ""
        papel_nome = desc.get("role") or ""
        conversa = d.get("conversationId") or os.path.basename(arq)[:-5]
        uris = d.get("workspaceUris") or []
        onde = unquote(urlparse(uris[0]).path) if uris else None
        if pasta and not mesma_pasta(onde, pasta):
            continue
        passos, escrita = passos_agy(conversa)
        reg = {
            "origem": "agy", "id": conversa,
            "conversa": arq.split(os.sep + "brain" + os.sep)[1].split(os.sep)[0],
            "pasta": onde, "inicio": iso(os.path.getmtime(arq)), "fim": None, "tipo": tipo,
            "papel": tipo if tipo in PAPEIS else None, "descricao": papel_nome,
            "profundidade": 1, "forma": None, "estado": d.get("state"), "tokens": None,
            "retorno_tokens": None, "razao": None, "casamento": None,
            "passos": passos, "edicoes": escrita, "ferramentas": None,
            "autorrevisao": tipo == "self" or "review" in papel_nome.lower(),
            "generico": tipo in ("self", "general", "research") and tipo not in PAPEIS,
            "sem_fonte": None,
        }
        novo[arq] = {"assinatura": assinatura(arq, banco_agy(conversa)), "registro": reg}
        saida.append(reg)
    if memo is not None:
        memo.clear()
        memo.update(novo)
    return saida


# Tipos dos campos que o jangada-delegar grava. O arquivo é gravável pelo
# agente isolado; um campo de outro tipo vira None, em vez de derrubar os
# indicadores no meio de uma soma.
CAMPOS_NUM = ("segundos", "codigo_saida", "palavras", "tokens_retorno", "passos",
              "tokens_agy", "cota_antes", "cota_depois", "sem_fonte")
CAMPOS_TEXTO = ("data", "sessao", "projeto", "pasta", "papel", "destino", "modelo",
                "motivo", "conversa")


def delegacao_limpa(d):
    for c in CAMPOS_NUM:
        v = d.get(c)
        if v is not None and (isinstance(v, bool) or not isinstance(v, (int, float))):
            d[c] = None
    for c in CAMPOS_TEXTO:
        if d.get(c) is not None and not isinstance(d[c], str):
            d[c] = None
    if not isinstance(d.get("recusa"), bool):
        d["recusa"] = bool(d.get("motivo"))
    return d


def delegacoes(caminho=None):
    return [delegacao_limpa(d) for d in linhas_json(caminho or os.path.join(ESTADO, "delegacoes.jsonl"))]


# caminho:linha com barra ou extensão (bin/jangada-validar:82, a.sh:3).
FONTE = re.compile(r"[\w.-]*[/.][\w./-]*:\d+|https?://|\bp\. ?\d+|\bp[áa]gina \d+|\bc[ée]lula [A-Z]+\d+|\blinha \d+", re.I)


def sem_fonte(texto):
    """Afirmações (itens de lista e frases de parágrafo) sem caminho:linha,
    página, célula ou URL. Contagem simples, por regex."""
    n = 0
    for linha in texto.splitlines():
        linha = linha.strip()
        if len(linha) < 25 or linha.startswith(("#", "```", "|", ">")):
            continue
        n += not FONTE.search(linha)
    return n


def mesma_pasta(a, b):
    if not a or not b:
        return False
    return os.path.realpath(a) == os.path.realpath(b)


def tokens_principal(pasta, ini=None, fim=None, raiz=None):
    """Tokens da conversa principal do Claude na pasta, entre ini e fim
    (segundos): entrada, saída e cache criado, e à parte o cache lido. Só as
    conversas da pasta de projeto do Claude com o nome da pasta; a mesma
    resposta em várias linhas conta uma vez (vale a última)."""
    raiz = raiz or PROJETOS_CLAUDE
    nome = re.sub(r"[^A-Za-z0-9]", "-", os.path.realpath(pasta))
    uso = {}
    for arq in glob.glob(os.path.join(raiz, nome, "*.jsonl")):
        if fim is None and ini is not None and os.path.getmtime(arq) < ini:
            continue
        for d in linhas_json(arq):
            if d.get("type") != "assistant" or d.get("isSidechain"):
                continue
            t = instante(d.get("timestamp"))
            if t is None or (ini is not None and t < ini) or (fim is not None and t > fim):
                continue
            msg = d.get("message") or {}
            u = msg.get("usage") or {}
            if u and msg.get("model") != "<synthetic>":
                uso[msg.get("id") or id(d)] = u
    novo = sum((u.get("input_tokens") or 0) + (u.get("output_tokens") or 0)
               + (u.get("cache_creation_input_tokens") or 0) for u in uso.values())
    return novo, sum(u.get("cache_read_input_tokens") or 0 for u in uso.values())


def entrega(pasta, desde=None, ate=None):
    """Resumo dos subagentes e delegações de uma entrega (campo subagentes
    do validar.jsonl): tudo o que rodou na pasta entre desde e ate."""
    ini = instante(desde) if desde else None
    fim = instante(ate) if ate else None

    def dentro(t):
        t = instante(t)
        return t is not None and (ini is None or t >= ini) and (fim is None or t <= fim)

    subs = [s for s in claude(pasta=pasta, desde=desde) + agy(pasta=pasta) if dentro(s["inicio"])]
    dels = [d for d in delegacoes() if mesma_pasta(d.get("pasta"), pasta) and dentro(d.get("data"))]
    atendidas = [d for d in dels if not d.get("recusa")]
    c = [s for s in subs if s["origem"] == "claude"]
    a = [s for s in subs if s["origem"] == "agy"]
    papeis = {}
    for x in subs:
        if x["papel"]:
            papeis[x["papel"]] = papeis.get(x["papel"], 0) + 1
    for d in atendidas:
        papeis[d.get("papel")] = papeis.get(d.get("papel"), 0) + 1

    def soma(itens, chave):
        v = [i.get(chave) for i in itens if isinstance(i.get(chave), (int, float))]
        return sum(v) if v else 0

    delegadas_agy = sum(d.get("destino") == "agy" for d in atendidas)
    agy_n = len(a) + delegadas_agy
    principal, cache_lido = tokens_principal(pasta, ini, fim)
    return {
        "n": len(subs) + len(atendidas),
        "claude": {"n": len(c), "tokens": soma(c, "tokens"), "principal": principal,
                   "principal_cache_lido": cache_lido},
        "delegadas_agy": delegadas_agy,
        "agy": {"n": agy_n, "passos": soma(a, "passos") + soma(atendidas, "passos")},
        "papeis": papeis,
        "retorno_tokens": soma(c, "retorno_tokens") + soma(atendidas, "tokens_retorno"),
        "edicoes": soma(subs, "edicoes"),
        "autorrevisao": sum(bool(s["autorrevisao"]) for s in subs),
        "recusas": len(dels) - len(atendidas),
    }


POUCO_DADO = 15
RETORNO_GRANDE = 2000
RECUSA_ANTES = 15 * 60


def mediana(v):
    v = sorted(x for x in v if isinstance(x, (int, float)))
    if not v:
        return None
    m = len(v) // 2
    return round(v[m] if len(v) % 2 else (v[m - 1] + v[m]) / 2, 1)


def pct(parte, todo):
    return round(100 * parte / todo, 1) if todo else None


def entregas_aprovadas(caminho=None):
    """Linhas APROVADO do validar.jsonl com o resumo de subagentes."""
    saida = []
    for d in linhas_json(caminho or os.path.join(ESTADO, "validar.jsonl")):
        r = d.get("subagentes")
        if d.get("resultado") != "aprovado" or not isinstance(r, dict):
            continue
        num = lambda k: d.get(k) if isinstance(d.get(k), int) else 0
        c = r.get("claude") or {}
        saida.append({
            "data": d.get("data"), "projeto": d.get("projeto"), "rotulo": d.get("rotulo"),
            "rodadas": d.get("rodada"), "diff": num("mais") + num("menos"),
            "tokens_claude": (c.get("principal") or 0) + (c.get("tokens") or 0),
            "com_agy": (r.get("delegadas_agy") or 0) > 0,
            "com_verificador": ((r.get("papeis") or {}).get("verificador") or 0) > 0,
        })
    return saida


def faixas(ents):
    """Tercis do tamanho do diff (mais + menos): pequeno, médio, grande."""
    v = sorted(e["diff"] for e in ents)
    if not v:
        return
    c1, c2 = v[len(v) // 3], v[2 * len(v) // 3]
    for e in ents:
        e["faixa"] = "pequeno" if e["diff"] < c1 else "médio" if e["diff"] < c2 else "grande"


def comparar(ents, chave, medida):
    """Por faixa de diff, o grupo com e sem `chave`: n e a medida de cada um."""
    linhas = []
    for f in ("pequeno", "médio", "grande", "todas"):
        linha = {"faixa": f}
        for lado, val in (("com", True), ("sem", False)):
            g = [e for e in ents if e[chave] == val and (f == "todas" or e.get("faixa") == f)]
            linha[lado] = dict(n=len(g), pouco_dado=len(g) <= POUCO_DADO, **medida(g))
        linhas.append(linha)
    return linhas


def aprovacao(g):
    return {"primeira_pct": pct(sum(e["rodadas"] == 1 for e in g), len(g)),
            "rodadas_media": round(sum(e["rodadas"] or 0 for e in g) / len(g), 2) if g else None}


def indicadores(agora=None, memo=None):
    """Os oito indicadores da etapa 4 da especificação de subagentes. O memo
    ({"claude": {}, "agy": {}}, guardado entre coletas) evita reler os
    subagentes cujos arquivos não mudaram."""
    agora = agora or dt.datetime.now().astimezone()
    if memo is None:
        subs = claude() + agy()
    else:
        for k in ("claude", "agy"):
            if not isinstance(memo.get(k), dict):
                memo[k] = {}
        subs = claude(memo=memo["claude"]) + agy(memo=memo["agy"])
    dels = delegacoes()
    atendidas = [d for d in dels if not d.get("recusa")]
    recusas = [d for d in dels if d.get("recusa")]
    ents = entregas_aprovadas()
    faixas(ents)

    # 1. Tokens do Claude por entrega aprovada, com e sem delegação ao agy.
    tokens = comparar(ents, "com_agy", lambda g: {"mediana_tokens": mediana(e["tokens_claude"] for e in g)})

    # 2. Fração delegada ao agy e recusas do jangada-delegar.
    por_papel = {}
    for x in subs:
        if x["origem"] == "claude" or x["papel"]:
            chave = x["papel"] or x["tipo"] or "?"
            por_papel.setdefault(chave, {"claude": 0, "agy": 0})[x["origem"]] += 1
    for d in atendidas:
        por_papel.setdefault(d.get("papel") or "?", {"claude": 0, "agy": 0})[
            "agy" if d.get("destino") == "agy" else "claude"] += 1
    motivos = {}
    for d in recusas:
        m = re.sub(r"\d+([.,]\d+)?%?", "N", d.get("motivo") or "")
        m = re.sub(r"\(.*\)", "", m).strip()
        motivos[m] = motivos.get(m, 0) + 1
    agy_atendidas = sum(d.get("destino") == "agy" for d in atendidas)
    fracao = {
        "delegadas_agy": agy_atendidas, "subagentes_claude": sum(x["origem"] == "claude" for x in subs),
        "subagentes_agy": sum(x["origem"] == "agy" for x in subs),
        "fracao_agy_pct": pct(agy_atendidas, len(atendidas) + len(subs)),
        "por_papel": por_papel,
        "chamadas": len(dels), "recusas": len(recusas), "taxa_recusa_pct": pct(len(recusas), len(dels)),
        "motivos": motivos,
    }

    # 3. Compressão: séries separadas, Claude em tokens e agy em passos.
    serie_claude = [x for x in subs if x["origem"] == "claude" and x["casamento"]]
    serie_agy = [d for d in atendidas if isinstance(d.get("passos"), (int, float)) and d.get("tokens_retorno")]
    grandes = [{"origem": x["origem"], "id": x["id"], "papel": x["papel"] or x["tipo"], "inicio": x["inicio"],
                "retorno_tokens": x["retorno_tokens"]}
               for x in subs if (x["retorno_tokens"] or 0) > RETORNO_GRANDE]
    grandes += [{"origem": "delegacao", "id": d.get("conversa"), "papel": d.get("papel"), "inicio": d.get("data"),
                 "retorno_tokens": d.get("tokens_retorno")}
                for d in atendidas if (d.get("tokens_retorno") or 0) > RETORNO_GRANDE]
    compressao = {
        "claude": {"n": len(serie_claude), "mediana": mediana(x["razao"] for x in serie_claude),
                   "descasados": sum(x["casamento"] is False for x in subs),
                   "sem_medida": sum(x["origem"] == "claude" and x["casamento"] is None for x in subs),
                   "por_papel": {p: mediana(x["razao"] for x in serie_claude if (x["papel"] or x["tipo"]) == p)
                                 for p in sorted({x["papel"] or x["tipo"] for x in serie_claude})}},
        "agy": {"n": len(serie_agy),
                "mediana_passos_por_mil_tokens": mediana(1000 * d["passos"] / d["tokens_retorno"] for d in serie_agy)},
        "retornos_grandes": grandes,
    }

    # 4. Custo em cota do agy, em pontos percentuais do limite de 5 horas.
    custos = [(d.get("data"), d["cota_antes"] - d["cota_depois"]) for d in atendidas
              if isinstance(d.get("cota_antes"), (int, float)) and isinstance(d.get("cota_depois"), (int, float))]
    semanas = {}
    for data, c in custos:
        t = instante(data)
        if t is not None:
            a, s_, _ = dt.datetime.fromtimestamp(t).isocalendar()
            chave = f"{a}-S{s_:02d}"
            semanas[chave] = round(semanas.get(chave, 0) + c, 2)
    media = sum(c for _, c in custos) / len(custos) if custos else None
    cota = {"n": len(custos), "media_pp": None if media is None else round(media, 2),
            "abaixo_da_resolucao": sum(c <= 0 for _, c in custos),
            "delegacoes_por_bloco": round(100 / media) if media and media > 0 else None,
            "por_semana_pp": semanas}

    # 5. Efeito na validação, com e sem verificador, e com e sem agy.
    validacao = {"verificador": comparar(ents, "com_verificador", aprovacao),
                 "agy": comparar(ents, "com_agy", aprovacao)}

    # 6. Qualidade: afirmações sem fonte. O desmentido não é detectável.
    sf = [x["sem_fonte"] for x in subs if x["sem_fonte"] is not None]
    sf_d = [d.get("sem_fonte") for d in atendidas if isinstance(d.get("sem_fonte"), int)]
    qualidade = {"claude": {"n": len(sf), "mediana": mediana(sf), "total": sum(sf)},
                 "delegacoes": {"n": len(sf_d), "mediana": mediana(sf_d), "total": sum(sf_d)},
                 "desmentidos": None}

    # 7. Desvios do protocolo. Meta: zero em todos.
    recusas_t = [(instante(d.get("data")), d.get("papel"), d.get("pasta")) for d in recusas]

    def sem_recusa(x):
        t = instante(x["inicio"])
        return x["origem"] == "claude" and x["papel"] and t is not None and not any(
            rt is not None and rp == x["papel"] and mesma_pasta(rpa, x["pasta"]) and 0 <= t - rt <= RECUSA_ANTES
            for rt, rp, rpa in recusas_t)

    def item(x):
        return {"origem": x["origem"], "id": x["id"], "tipo": x["tipo"], "descricao": x["descricao"][:80],
                "inicio": x["inicio"]}
    desvios = {nome: [item(x) for x in subs if f(x)] for nome, f in (
        ("edicoes", lambda x: (x["edicoes"] or 0) > 0),
        ("autorrevisao", lambda x: x["autorrevisao"]),
        ("generico", lambda x: x["generico"]),
        ("claude_sem_recusa", sem_recusa))}

    # 8. Árvore: pasta, conversa e seus subagentes e delegações.
    arvore = {}
    for x in subs:
        ramo = arvore.setdefault(x["pasta"] or "?", {}).setdefault(f'{x["origem"]}:{x["conversa"]}', [])
        ramo.append({"origem": x["origem"], "id": x["id"], "papel": x["papel"] or x["tipo"],
                     "profundidade": x["profundidade"], "tokens": x["tokens"], "passos": x["passos"],
                     "retorno_tokens": x["retorno_tokens"], "razao": x["razao"]})
    for d in dels:
        ramo = arvore.setdefault(d.get("pasta") or "?", {}).setdefault(f'delegar:{d.get("sessao") or "?"}', [])
        ramo.append({"origem": "delegacao", "id": d.get("conversa") or "", "papel": d.get("papel"),
                     "profundidade": 1, "tokens": d.get("tokens_agy"), "passos": d.get("passos"),
                     "retorno_tokens": d.get("tokens_retorno"), "razao": None, "recusa": d.get("recusa")})
    ramos = []
    for pasta, convs in sorted(arvore.items()):
        for conv, filhos in sorted(convs.items()):
            tok = sum(f["tokens"] or 0 for f in filhos if f["origem"] == "claude")
            ret = sum(f["retorno_tokens"] or 0 for f in filhos if f["origem"] == "claude")
            ramos.append({"pasta": pasta, "conversa": conv, "n": len(filhos), "tokens_claude": tok,
                          "retorno_tokens": ret, "razao": round(tok / ret, 1) if tok and ret else None,
                          "passos_agy": sum(f["passos"] or 0 for f in filhos), "filhos": filhos})

    return {
        "data": agora.isoformat(timespec="seconds"), "pouco_dado": POUCO_DADO,
        "entregas_com_resumo": len(ents),
        "tokens_por_entrega": tokens, "fracao_agy": fracao, "compressao": compressao, "cota_agy": cota,
        "validacao": validacao, "qualidade": qualidade, "desvios": desvios, "arvore": ramos,
    }


def texto(ind):
    """Os indicadores em texto curto, para o terminal."""
    n = lambda v, suf="": "-" if v is None else f"{v}{suf}".replace(".", ",")
    li = [f"Subagentes e delegações ({ind['data'][:16].replace('T', ' ')})", ""]

    def grupos(titulo, linhas, medida, fmt):
        li.append(titulo)
        for l in linhas:
            partes = []
            for lado in ("com", "sem"):
                g = l[lado]
                partes.append(f"{lado} {g['n']}: {fmt(g[medida])}{' (pouco dado)' if g['pouco_dado'] else ''}")
            li.append(f"  {l['faixa']:8} " + "; ".join(partes))

    li.append(f"Entregas aprovadas com resumo de subagentes: {ind['entregas_com_resumo']}"
              f" (sem conclusão até {ind['pouco_dado']} em cada grupo)")
    grupos("1. Tokens do Claude por entrega, com e sem delegação ao agy (mediana)",
           ind["tokens_por_entrega"], "mediana_tokens", lambda v: n(v))
    f = ind["fracao_agy"]
    li.append(f"2. Fração delegada ao agy: {n(f['fracao_agy_pct'], '%')} ({f['delegadas_agy']} delegações;"
              f" {f['subagentes_claude']} subagentes do Claude, {f['subagentes_agy']} do agy)")
    for p, v in sorted(f["por_papel"].items()):
        li.append(f"  {p}: Claude {v['claude']}, agy {v['agy']}")
    li.append(f"  recusas do jangada-delegar: {f['recusas']} de {f['chamadas']} ({n(f['taxa_recusa_pct'], '%')})")
    for m, q in sorted(f["motivos"].items(), key=lambda x: -x[1]):
        li.append(f"    {q}x {m}")
    c = ind["compressao"]
    li.append(f"3. Compressão no Claude (tokens do subagente por token devolvido): mediana"
              f" {n(c['claude']['mediana'])} em {c['claude']['n']}; {c['claude']['descasados']} descasado(s),"
              f" {c['claude']['sem_medida']} sem medida")
    for p, v in c["claude"]["por_papel"].items():
        li.append(f"  {p}: {n(v)}")
    li.append(f"  agy (passos por mil tokens devolvidos): mediana {n(c['agy']['mediana_passos_por_mil_tokens'])}"
              f" em {c['agy']['n']}")
    li.append(f"  retornos acima de {RETORNO_GRANDE} tokens: {len(c['retornos_grandes'])}")
    for g in c["retornos_grandes"]:
        li.append(f"    {g['origem']} {g['papel']} {g['id']}: {g['retorno_tokens']}")
    k = ind["cota_agy"]
    li.append(f"4. Cota do agy por delegação: {n(k['media_pp'], ' pp')} em média em {k['n']}"
              f" ({k['abaixo_da_resolucao']} sem variação medida); cabem {n(k['delegacoes_por_bloco'])} por bloco de 5 horas")
    for s_, v in sorted(k["por_semana_pp"].items()):
        li.append(f"  {s_}: {n(v, ' pp')}")
    grupos("5. Aprovação na 1ª rodada, com e sem verificador", ind["validacao"]["verificador"],
           "primeira_pct", lambda v: n(v, "%"))
    grupos("   e com e sem delegação ao agy", ind["validacao"]["agy"], "primeira_pct", lambda v: n(v, "%"))
    q = ind["qualidade"]
    li.append(f"6. Afirmações sem fonte: Claude {q['claude']['total']} em {q['claude']['n']} relatórios"
              f" (mediana {n(q['claude']['mediana'])}); delegações {q['delegacoes']['total']} em"
              f" {q['delegacoes']['n']} (mediana {n(q['delegacoes']['mediana'])}); desmentidos: não detectável")
    d = ind["desvios"]
    li.append("7. Desvios do protocolo (meta zero): " + ", ".join(f"{k_} {len(v)}" for k_, v in d.items()))
    for k_, v in d.items():
        for x in v[:5]:
            li.append(f"  {k_}: {x['origem']} {x['tipo']} {x['id']} {x['descricao']!r}")
    li.append(f"8. Árvore: {len(ind['arvore'])} ramo(s) (conversa ou sessão)")
    for r in ind["arvore"][:15]:
        li.append(f"  {os.path.basename(r['pasta'])} {r['conversa'][:30]}: {r['n']} filho(s),"
                  f" {r['tokens_claude']} tokens no Claude, razão {n(r['razao'])}, {r['passos_agy']} passos no agy")
    return "\n".join(li)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jangada-subagentes")
    ap.add_argument("--entrega", metavar="PASTA")
    ap.add_argument("--desde")
    ap.add_argument("--ate")
    ap.add_argument("--registros", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    for nome in ("desde", "ate"):
        if getattr(a, nome) and instante(getattr(a, nome)) is None:
            ap.error(f"--{nome} não é uma data ISO 8601: {getattr(a, nome)}")
    if a.entrega:
        print(json.dumps(entrega(a.entrega, a.desde, a.ate), ensure_ascii=False))
    elif a.registros:
        for r in claude() + agy():
            print(json.dumps(r, ensure_ascii=False))
        for d in delegacoes():
            print(json.dumps(dict(d, origem="delegacao"), ensure_ascii=False))
    elif a.json:
        print(json.dumps(indicadores(), ensure_ascii=False))
    else:
        print(texto(indicadores()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
