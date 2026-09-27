"""Subagentes do Claude e do agy e delegações do jangada-delegar.

Lê, sem rede e só com a biblioteca padrão:
  ~/.claude/projects/PROJETO/SESSAO/subagents/agent-ID.{meta.json,jsonl}
      e a conversa mãe SESSAO.jsonl (totais e retorno de cada subagente);
  ~/.gemini/antigravity-cli/brain/CONVERSA/.system_generated/subagents/*.json
      e conversations/ID.db (passos);
  ~/.local/state/jangada/delegacoes.jsonl.

Usado pelo jangada-subagentes (métrica e campo subagentes do validar.jsonl) e
pelo coletor do painel. Medida ausente fica None ("sem medida"), nunca zero.

Uso: subagentes.py --entrega PASTA [--desde ISO] [--ate ISO]
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

PAPEIS = ("explorador", "leitor", "pesquisador", "verificador")
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


def claude(raiz=None, pasta=None):
    """Um dicionário por subagente do Claude (só os da pasta, se dada)."""
    raiz = raiz or PROJETOS_CLAUDE
    maes = {}
    saida = []
    for meta in sorted(glob.glob(os.path.join(raiz, "*", "*", "subagents", "agent-*.meta.json"))):
        try:
            m = json.load(open(meta, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sessdir = os.path.dirname(os.path.dirname(meta))
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
        mae = sessdir + ".jsonl"
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
        saida.append({
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
        })
    return saida


def passos_agy(conversa):
    """(passos, passos de escrita) de uma conversa do agy, ou (None, None)."""
    banco = os.path.join(AGY, "conversations", conversa + ".db")
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


def agy(raiz=None, pasta=None):
    """Um dicionário por subagente do agy (só os da pasta, se dada)."""
    raiz = raiz or AGY
    saida = []
    for arq in sorted(glob.glob(os.path.join(raiz, "brain", "*", ".system_generated", "subagents", "*.json"))):
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
        saida.append({
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
        })
    return saida


def delegacoes(caminho=None):
    return list(linhas_json(caminho or os.path.join(ESTADO, "delegacoes.jsonl")))


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


def entrega(pasta, desde=None, ate=None):
    """Resumo dos subagentes e delegações de uma entrega (campo subagentes
    do validar.jsonl): tudo o que rodou na pasta entre desde e ate."""
    ini = instante(desde) if desde else None
    fim = instante(ate) if ate else None

    def dentro(t):
        t = instante(t)
        return t is not None and (ini is None or t >= ini) and (fim is None or t <= fim)

    subs = [s for s in claude(pasta=pasta) + agy(pasta=pasta) if dentro(s["inicio"])]
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

    agy_n = len(a) + sum(d.get("destino") == "agy" for d in atendidas)
    return {
        "n": len(subs) + len(atendidas),
        "claude": {"n": len(c), "tokens": soma(c, "tokens")},
        "agy": {"n": agy_n, "passos": soma(a, "passos") + soma(atendidas, "passos")},
        "papeis": papeis,
        "retorno_tokens": soma(c, "retorno_tokens") + soma(atendidas, "tokens_retorno"),
        "edicoes": soma(subs, "edicoes"),
        "autorrevisao": sum(bool(s["autorrevisao"]) for s in subs),
        "recusas": len(dels) - len(atendidas),
    }


def main(argv=None):
    ap = argparse.ArgumentParser(prog="jangada-subagentes")
    ap.add_argument("--entrega", metavar="PASTA")
    ap.add_argument("--desde")
    ap.add_argument("--ate")
    ap.add_argument("--registros", action="store_true")
    a = ap.parse_args(argv)
    if a.entrega:
        print(json.dumps(entrega(a.entrega, a.desde, a.ate), ensure_ascii=False))
    elif a.registros:
        for r in claude() + agy():
            print(json.dumps(r, ensure_ascii=False))
        for d in delegacoes():
            print(json.dumps(dict(d, origem="delegacao"), ensure_ascii=False))
    else:
        ap.print_usage(sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
