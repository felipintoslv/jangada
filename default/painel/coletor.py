#!/usr/bin/env python3
"""Coletor do jangada-painel: lê os registros e grava o cache em Parquet.

Uso: coletor.py PASTA_DO_CACHE

Lê, de forma incremental, as conversas do Claude Code (~/.claude/projects) e,
inteiros, os registros pequenos do jangada (validar.jsonl, pareceres antigos,
eventos-agentes.jsonl). Grava em PASTA_DO_CACHE:

  validacoes.parquet   uma linha por rodada do jangada-validar
  eventos.parquet      o histórico de estados dos agentes
  sessoes.parquet      as sessões abertas agora (retrato dos SESSAO.json)
  mensagens/           uma linha por resposta do Claude, com o consumo
  ferramentas/         uma linha por chamada de ferramenta
  resultados/          uma linha por resultado de ferramenta (erro ou não)
  posicoes.json        até onde cada jsonl foi lido
  coleta.json          resumo da última coleta
  hoje.json            os indicadores do dia (jangada-painel --json)

As pastas mensagens, ferramentas e resultados recebem um arquivo novo por
coleta com dado novo, e são compactadas num só quando passam de 40.

Variáveis: JANGADA_ESTADO, JANGADA_CLAUDE_PROJETOS (padrão
~/.claude/projects), JANGADA_PROJETOS e JANGADA_WORKTREES.
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
import pyarrow.dataset as ds
import pyarrow.parquet as pq

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


def gravar_json(caminho, dado):
    tmp = caminho + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(dado, f, ensure_ascii=False, indent=1)
    os.replace(tmp, caminho)


def gravar_tabela(caminho, linhas, esquema):
    tabela = pa.Table.from_pylist(linhas, schema=esquema)
    tmp = caminho + ".tmp"
    pq.write_table(tabela, tmp)
    os.replace(tmp, caminho)


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
ESQ_VALIDACOES = pa.schema([
    ("data", TS), ("dia", pa.string()), ("projeto", pa.string()), ("rotulo", pa.string()),
    ("rodada", pa.int64()), ("resultado", pa.string()), ("etapa", pa.string()),
    ("revisor", pa.string()), ("modelo", pa.string()), ("autor", pa.string()),
    ("arquivos", pa.int64()), ("mais", pa.int64()), ("menos", pa.int64()),
    ("itens", pa.int64()), ("segundos", pa.int64()), ("entrega", pa.string()),
    ("origem", pa.string()),
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


def acrescentar(pasta, linhas, esquema, carimbo):
    """Grava as linhas novas como mais um arquivo da pasta; compacta se preciso."""
    os.makedirs(pasta, exist_ok=True)
    if linhas:
        gravar_tabela(os.path.join(pasta, f"parte-{carimbo}.parquet"), linhas, esquema)
    partes = sorted(glob.glob(os.path.join(pasta, "parte-*.parquet")))
    if len(partes) > PARTES_MAX:
        tabela = ds.dataset(partes, format="parquet", schema=esquema).to_table()
        destino = os.path.join(pasta, f"parte-{carimbo}-c.parquet")
        pq.write_table(tabela, destino + ".tmp")
        os.replace(destino + ".tmp", destino)
        for p in partes:
            if p != destino:
                os.remove(p)


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
        with open(caminho, "rb") as f:
            f.seek(pos)
            bloco = f.read()
        fim = bloco.rfind(b"\n")
        if fim < 0:
            novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos}
            continue
        novas_posicoes[caminho] = {"ino": st.st_ino, "pos": pos + fim + 1}
        resumo["bytes_lidos"] += fim + 1
        for bruto in bloco[:fim].split(b"\n"):
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

def validacoes():
    """Rodadas do validar.jsonl e, antes dele, as dos pareceres antigos."""
    linhas = []
    arq = os.path.join(ESTADO, "validar.jsonl")
    try:
        with open(arq, encoding="utf-8", errors="replace") as f:
            brutas = f.readlines()
    except OSError:
        brutas = []
    for bruta in brutas:
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
            "origem": "validar.jsonl",
        })
    # Pareceres antigos: a validação grava o parecer no mesmo segundo da linha
    # do validar.jsonl; um parecer só entra se não houver linha do mesmo rótulo
    # a até 60 s. As avaliacao-* são avaliações do Claude, não revisões. O N
    # do arquivo não é a rodada: o antigo jangada-par recomeçava do r1 e
    # sobrescrevia o arquivo. A ordem vem do mtime.
    ja = {}
    for l in linhas:
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
    # rodada 1, quando a entrega foi abandonada sem aprovação).
    linhas.sort(key=lambda l: (l["rotulo"], l["data"]))
    seq, rot_ant, fechada = 0, None, True
    for l in linhas:
        if l["rotulo"] != rot_ant:
            seq, rot_ant, fechada = 1, l["rotulo"], False
        elif fechada or l["rodada"] == 1:
            seq, fechada = seq + 1, False
        l["entrega"] = f'{l["rotulo"]}#{seq}'
        if l["resultado"] == "aprovado":
            fechada = True
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
            # O foco não muda o estado da sessão; o intervalo vai até o próximo
            # evento de estado.
            # Sem evento depois, a sessão pode ter sido esquecida em aguardando:
            # conta no máximo 12 horas, como no app.
            b = next((x["data"] for x in lista[i + 1:] if x["estado"] != "foco"),
                     min(agora, a + dt.timedelta(hours=12)))
            a, b = max(a, ini), min(b, fim)
            if b > a:
                total += (b - a).total_seconds()
    return total


def indicadores_do_dia(cache, vals, evs, agora):
    hoje = dia_de(agora)
    ini = dt.datetime.combine(agora.astimezone(FUSO).date(), dt.time(), FUSO).astimezone(UTC)
    fim = ini + dt.timedelta(days=1)
    aprov = [v for v in vals if v["dia"] == hoje and v["resultado"] == "aprovado"]
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
    vals = validacoes()
    evs = eventos()
    gravar_tabela(os.path.join(cache, "validacoes.parquet"), vals, ESQ_VALIDACOES)
    gravar_tabela(os.path.join(cache, "eventos.parquet"), evs, ESQ_EVENTOS)
    gravar_tabela(os.path.join(cache, "sessoes.parquet"), sessoes(), ESQ_SESSOES)
    gravar_json(os.path.join(cache, "hoje.json"), indicadores_do_dia(cache, vals, evs, agora))
    resumo.update({"mensagens_novas": len(mens), "ferramentas_novas": len(ferr),
                   "resultados_novos": len(res), "validacoes": len(vals), "eventos": len(evs),
                   "data": agora.astimezone(FUSO).isoformat(timespec="seconds"),
                   "segundos": round(time.monotonic() - INICIO, 2)})
    gravar_json(os.path.join(cache, "coleta.json"), resumo)
    print(json.dumps(resumo, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
