"""Normaliza metadados de consumo. Nunca guarda pedidos, respostas ou credenciais."""
import collections
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import stat
import tempfile

MAX_ARQUIVO = 128 * 1024 * 1024
MAX_LINHA = 4 * 1024 * 1024
MAX_ARQUIVOS = 4096
TOKENS = ('entrada_total', 'cache_lido', 'cache_criado', 'saida', 'raciocinio')
TEMPOS = ('tempo_total_ms', 'tempo_carregamento_ms', 'tempo_entrada_ms', 'tempo_geracao_ms')


def numero(v):
    return v if type(v) in (int, float) and math.isfinite(v) and v >= 0 else None


def texto(v):
    return v[:512] if isinstance(v, str) else ''


def data(v):
    if isinstance(v, dt.datetime):
        return v if v.tzinfo else v.replace(tzinfo=dt.timezone.utc)
    try:
        if not isinstance(v, str):
            return None
        t = dt.datetime.fromisoformat(v.replace('Z', '+00:00'))
        return (t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)).astimezone(dt.timezone.utc)
    except (ValueError, TypeError):
        return None


def arquivos(raiz):
    """Não segue diretórios simbólicos; lê apenas rollouts dentro da raiz."""
    raiz = Path(raiz)
    if raiz.is_symlink():
        raise OSError('raiz simbólica')
    encontrados = []
    for pasta, dirs, nomes in os.walk(raiz, followlinks=False):
        dirs[:] = sorted(d for d in dirs if not Path(pasta, d).is_symlink())
        for nome in sorted(nomes):
            if nome.startswith('rollout') and nome.endswith('.jsonl'):
                encontrados.append(Path(pasta, nome))
                if len(encontrados) > MAX_ARQUIVOS:
                    raise OSError('limite de arquivos')
    return encontrados


def linhas(caminho):
    fd = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as arq:
        s = os.fstat(arq.fileno())
        if not stat.S_ISREG(s.st_mode) or s.st_size > MAX_ARQUIVO:
            raise OSError('fonte fora dos limites')
        while True:
            linha = arq.readline(MAX_LINHA + 1)
            if not linha:
                return
            if len(linha) > MAX_LINHA:
                raise OSError('linha fora dos limites')
            if not linha.endswith(b'\n'):
                return  # registro em gravação; será relido na próxima coleta
            try:
                d = json.loads(linha)
            except (ValueError, UnicodeDecodeError):
                raise OSError('registro inválido') from None
            if isinstance(d, dict):
                yield d


def base(ident, quando, origem, executor, provedor, modelo='', sessao='', projeto='', papel=''):
    return dict(id=ident, data=quando, dia='', origem=origem, executor=executor,
                provedor=provedor, modelo=texto(modelo), sessao=texto(sessao),
                projeto=texto(projeto), papel=texto(papel), delegacao_id='', chamada_id='', estado='registrado')


def uso(b, u):
    return dict(b, entrada_total=numero(u.get('input_tokens')), cache_lido=numero(u.get('cached_input_tokens')),
                cache_criado=numero(u.get('cache_write_input_tokens')), saida=numero(u.get('output_tokens')),
                raciocinio=numero(u.get('reasoning_output_tokens')), **dict.fromkeys(TEMPOS))


def codex_arquivo(caminho, origem, anterior):
    fd = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as arq:
        st = os.fstat(arq.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_ARQUIVO:
            raise OSError('fonte fora dos limites')
        memo = anterior or {}
        mesmo = (memo.get('ino') == st.st_ino and memo.get('dev') == st.st_dev
                 and st.st_size >= memo.get('tamanho', 0)
                 and not (st.st_size == memo.get('tamanho') and st.st_mtime_ns != memo.get('mtime')))
        if not mesmo:
            memo = dict(pos=0, sessao=caminho.stem, projeto='', modelo='', anterior={},
                        consumo={}, cumulativo={}, ferramentas={}, resultados=[])
        arq.seek(memo['pos'])
        bytes_lidos = linhas_lidas = 0
        resultados = set(memo['resultados'])
        while True:
            inicio = arq.tell()
            linha = arq.readline(MAX_LINHA + 1)
            bytes_lidos += len(linha)
            if not linha:
                break
            if len(linha) > MAX_LINHA:
                raise OSError('linha fora dos limites')
            if not linha.endswith(b'\n'):
                arq.seek(inicio)
                break
            try:
                d = json.loads(linha)
            except (ValueError, UnicodeDecodeError):
                raise OSError('registro inválido') from None
            linhas_lidas += 1
            if not isinstance(d, dict) or not isinstance(d.get('payload'), dict):
                continue
            p = d['payload']
            t = data(d.get('timestamp'))
            if d.get('type') == 'session_meta':
                memo['sessao'] = texto(p.get('id')) or caminho.stem
                memo['projeto'] = Path(texto(p.get('cwd'))).name
            if d.get('type') == 'turn_context':
                memo['modelo'] = texto(p.get('model'))
            sessao = memo['sessao']
            if d.get('type') == 'token_usage_record' and isinstance(p.get('usage'), dict):
                rid = texto(p.get('response_id'))
                if rid and t:
                    ident = 'codex:' + rid
                    memo['consumo'][ident] = uso(base(ident, t.isoformat(), origem, 'codex', 'openai',
                                                     memo['modelo'], sessao, memo['projeto']), p['usage'])
            elif d.get('type') == 'event_msg' and p.get('type') == 'token_count':
                info = p.get('info')
                total = info.get('total_token_usage') if isinstance(info, dict) else None
                if not isinstance(total, dict) or not t:
                    continue
                atual = {k: numero(total.get(k)) for k in ('input_tokens', 'cached_input_tokens',
                         'cache_write_input_tokens', 'output_tokens', 'reasoning_output_tokens')}
                anterior_uso = memo['anterior']
                delta = {k: (v - (anterior_uso.get(k) or 0)
                             if v is not None and v >= (anterior_uso.get(k) or 0) else v)
                         for k, v in atual.items()}
                if any(v for v in delta.values() if v is not None):
                    ident = 'codex-cumulativo:' + sessao + ':' + d['timestamp']
                    memo['cumulativo'][ident] = uso(base(ident, t.isoformat(), origem, 'codex', 'openai',
                                                        memo['modelo'], sessao, memo['projeto']), delta)
                memo['anterior'] = atual
            if d.get('type') == 'response_item':
                call = texto(p.get('call_id'))
                ident = 'codex-ferramenta:' + sessao + ':' + call
                if p.get('type') in ('function_call', 'custom_tool_call') and call and t:
                    memo['ferramentas'][ident] = dict(base(ident, t.isoformat(), origem, 'codex', 'openai',
                        memo['modelo'], sessao, memo['projeto']), ferramenta=texto(p.get('name')),
                        resultado='sem_resultado')
                elif p.get('type') in ('function_call_output', 'custom_tool_call_output') and call:
                    resultados.add(ident)
        for ident in resultados:
            if ident in memo['ferramentas']:
                memo['ferramentas'][ident]['resultado'] = 'registrado'
        memo.update(pos=arq.tell(), ino=st.st_ino, dev=st.st_dev, tamanho=st.st_size,
                    mtime=st.st_mtime_ns, resultados=sorted(resultados))
        return memo, bytes_lidos, linhas_lidas


def codex(raiz, origem, cache=None, leitura=None):
    consumo, ferramentas, novos = {}, {}, {}
    caminho_memo = Path(cache, 'codex-' + origem + '.json') if cache is not None else None
    memo = {}
    if caminho_memo is not None:
        try:
            fd = os.open(caminho_memo, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, 'rb') as arq:
                st = os.fstat(arq.fileno())
                if not stat.S_ISREG(st.st_mode) or st.st_size > MAX_ARQUIVO:
                    raise OSError('cache fora dos limites')
                guardado = json.load(arq)
            if isinstance(guardado, dict) and guardado.get('versao') == 1 and guardado.get('raiz') == str(raiz):
                memo = guardado.get('arquivos', {})
        except (FileNotFoundError, ValueError, UnicodeDecodeError):
            memo = {}
    for caminho in arquivos(raiz):
        item, nbytes, nlinhas = codex_arquivo(caminho, origem, memo.get(str(caminho)))
        novos[str(caminho)] = item
        if leitura is not None:
            leitura['arquivos_lidos'] += int(nbytes > 0)
            leitura['bytes_lidos'] += nbytes
            leitura['linhas_lidas'] += nlinhas
        # O formato por resposta substitui os cumulativos também quando chega depois.
        consumo.update(item['consumo'] or item['cumulativo'])
        ferramentas.update(item['ferramentas'])
    if caminho_memo is not None:
        temporario = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=cache, prefix='.codex-', delete=False) as arq:
                temporario = arq.name
                json.dump(dict(versao=1, raiz=str(raiz), arquivos=novos), arq, ensure_ascii=False, allow_nan=False)
            os.replace(temporario, caminho_memo)
        finally:
            if temporario and os.path.exists(temporario):
                os.unlink(temporario)
    for tabela in (consumo, ferramentas):
        for r in tabela.values():
            r['data'] = data(r['data'])
    return list(consumo.values()), list(ferramentas.values())


def ollama(caminho):
    consumo = []
    repetidos = collections.Counter()
    for d in linhas(caminho):
        if d.get('destino') != 'local':
            continue
        t = data(d.get('data'))
        if not t:
            continue
        canon = json.dumps(d, sort_keys=True, ensure_ascii=True, separators=(',', ':'))
        h = hashlib.sha256(canon.encode()).hexdigest()
        repetidos[h] += 1
        ident = texto(d.get('delegacao_id')) or h + ':' + str(repetidos[h])
        b = base('ollama:' + ident, t, 'jangada', 'ollama', 'ollama', d.get('modelo'), d.get('sessao'), d.get('projeto'), d.get('papel'))
        chamadas = d.get('chamadas_local')
        if isinstance(chamadas, list):
            for i, c in enumerate(chamadas):
                if not isinstance(c, dict):
                    continue
                tempos = c.get('tempos_ms') or {}
                if not isinstance(tempos, dict):
                    tempos = {}
                consumo.append(dict(b, id=b['id'] + ':' + (texto(c.get('id')) or str(i)),
                    delegacao_id=ident, chamada_id=texto(c.get('id')) or str(i), estado='parcial' if d.get('recusa') else 'registrado',
                    modelo=texto(c.get('modelo')) or b['modelo'], entrada_total=numero(c.get('tokens_entrada')),
                    saida=numero(c.get('tokens_saida')), cache_lido=numero(c.get('cache_lido')), cache_criado=None,
                    raciocinio=None, **{'tempo_' + k + '_ms': numero(tempos.get(k)) for k in ('total', 'carregamento', 'entrada', 'geracao')}))
        elif any(numero(d.get(k)) is not None for k in ('tokens_local_entrada', 'tokens_local_saida')):
            consumo.append(dict(b, entrada_total=numero(d.get('tokens_local_entrada')), saida=numero(d.get('tokens_local_saida')),
                                cache_lido=None, cache_criado=None, raciocinio=None, **dict.fromkeys(TEMPOS)))
    return consumo, []


def claude(cache):
    import pyarrow.parquet as pq
    consumo, ferramentas = [], []
    def tabela(caminho):
        if caminho.is_symlink() or caminho.stat().st_size > MAX_ARQUIVO:
            raise OSError('cache fora dos limites')
        return pq.read_table(caminho).to_pylist()
    caminhos = sorted(Path(cache, 'mensagens').glob('*.parquet'))
    agregado = Path(cache, 'mensagens-dias.parquet')
    if agregado.exists():
        caminhos.append(agregado)
    for caminho in caminhos:
        for d in tabela(caminho):
            if d.get('modelo') == '<synthetic>':
                continue
            t = data(d.get('data')) or data((d.get('dia') or '') + 'T12:00:00+00:00')
            vals = [numero(d.get(k)) for k in ('entrada', 'cache_lido', 'cache_criado')]
            ident = texto(d.get('id')) or hashlib.sha256(json.dumps(d, sort_keys=True, default=str).encode()).hexdigest()
            b = base('claude:' + ident, t, 'jangada' if d.get('sessao') else 'historico_claude', 'claude', 'anthropic',
                     d.get('modelo'), d.get('sessao'), d.get('projeto'), d.get('subagente'))
            consumo.append(dict(b, entrada_total=sum(vals) if all(v is not None for v in vals) else None,
                                cache_lido=vals[1], cache_criado=vals[2], saida=numero(d.get('saida')),
                                raciocinio=numero(d.get('raciocinio')), **dict.fromkeys(TEMPOS)))
    resultados = {}
    for caminho in sorted(Path(cache, 'resultados').glob('*.parquet')):
        for d in tabela(caminho):
            ident = texto(d.get('id'))
            if ident:
                resultados[ident] = 'erro' if d.get('erro') is True else 'registrado'
    for caminho in sorted(Path(cache, 'ferramentas').glob('*.parquet')):
        for d in tabela(caminho):
            ident = texto(d.get('id'))
            t = data(d.get('data'))
            if not ident or not t:
                continue
            b = base('claude-ferramenta:' + ident, t,
                     'jangada' if d.get('sessao') else 'historico_claude',
                     'claude', 'anthropic', sessao=d.get('sessao'),
                     projeto=d.get('projeto'), papel=d.get('subagente'))
            ferramentas.append(dict(b, chamada_id=ident, ferramenta=texto(d.get('ferramenta')),
                                     resultado=resultados.get(ident, 'sem_resultado')))
    return consumo, ferramentas


def coletar(cache, agora, retencao_dias=180):
    """Devolve consumo, ferramentas e cobertura; uma fonte falha independentemente."""
    estado = Path(os.environ.get('JANGADA_ESTADO', str(Path.home() / '.local/state/jangada')))
    home_codex = Path(os.environ.get('CODEX_HOME', str(Path.home() / '.codex')))
    gerenciado = estado / 'codex'
    fontes = [('claude', 'misto', lambda: claude(cache)),
              ('ollama', 'jangada', lambda: ollama(estado / 'delegacoes.jsonl')),
              ('codex_jangada', 'jangada', lambda: codex(gerenciado, 'jangada', cache, leituras['codex_jangada']))]
    if not home_codex.resolve().is_relative_to(gerenciado.resolve()):
        fontes.append(('codex_externo', 'interface_externa', lambda: codex(home_codex / 'sessions', 'interface_externa', cache, leituras['codex_externo'])))
    leituras = {fonte: dict(arquivos_lidos=0, bytes_lidos=0, linhas_lidas=0) for fonte, _, _ in fontes}
    consumo, ferramentas, cobertura = [], [], []
    limite = agora - dt.timedelta(days=retencao_dias) if retencao_dias else None
    for fonte, origem, ler in fontes:
        erro = ''
        try:
            cs, fs = ler()
            status = 'ok' if cs or fs else 'sem_dados'
        except FileNotFoundError:
            cs, fs, status = [], [], 'sem_dados'
        except Exception as exc:
            cs, fs, status = [], [], 'erro'
            erro = type(exc).__name__
        for tabela in (cs, fs):
            tabela[:] = [r for r in tabela if r['data'] and r['data'] <= agora and (not limite or r['data'] >= limite)]
            tabela[:] = list({r['id']: r for r in tabela}.values())
            for r in tabela:
                r['dia'] = r['data'].astimezone(agora.tzinfo).date().isoformat()
                r['fonte'] = fonte
        if status != 'erro':
            status = 'ok' if cs or fs else 'sem_dados'
        consumo.extend(cs); ferramentas.extend(fs)
        datas = [r['data'] for r in cs + fs]
        cobertura.append(dict(fonte=fonte, origem=origem, estado=status, registros=len(cs), ferramentas=len(fs),
                              atualizado=agora, ultima_tentativa=agora, erro=erro,
                              ultimo_dado=max(datas) if datas else None,
                              **(leituras[fonte] if fonte.startswith('codex_') else {})))
    # A fonte gerenciada ganha de uma eventual cópia no histórico externo.
    def unicos(linhas):
        vistos = {}
        for r in linhas:
            vistos.setdefault(r['id'], r)
        return list(vistos.values())
    return unicos(consumo), unicos(ferramentas), cobertura
