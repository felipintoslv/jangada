"""Disponibilidade compartilhada entre projetos, sem autorizar execução."""

import json
import math
import os
import pathlib
import subprocess
import time
import urllib.error
import urllib.request

from estado import IDENTIFICADOR, serializar
from executor import CAPACIDADES

ESTADOS = {'AVAILABLE', 'DEGRADED', 'UNKNOWN', 'UNAVAILABLE', 'COOLDOWN',
           'QUOTA_LOW', 'QUOTA_EXHAUSTED', 'AUTH_ERROR', 'RATE_LIMITED', 'NETWORK_ERROR'}


class Saude:
    def __init__(self, estado):
        self.estado = estado
        self.db = estado.db
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS provedores (
                id TEXT PRIMARY KEY, status TEXT NOT NULL, pausado INTEGER NOT NULL DEFAULT 0,
                falhas INTEGER NOT NULL DEFAULT 0, motivo TEXT NOT NULL,
                atualizado REAL NOT NULL, valido_ate REAL NOT NULL,
                cota REAL, modelo TEXT
            );
            CREATE TABLE IF NOT EXISTS eventos_provedores (
                seq INTEGER PRIMARY KEY, provedor TEXT NOT NULL, data REAL NOT NULL,
                evento TEXT NOT NULL, dados TEXT NOT NULL
            );
        ''')

    def observar(self, provedor, status, motivo, validade=60, cota=None, modelo=None):
        if not isinstance(provedor, str) or not IDENTIFICADOR.fullmatch(provedor) or not isinstance(status, str) or status not in ESTADOS:
            raise ValueError('provedor ou estado inválido')
        if type(validade) is not int or not 1 <= validade <= 86400:
            raise ValueError('validade da observação inválida')
        if cota is not None and (type(cota) not in (int, float) or not math.isfinite(cota) or not 0 <= cota <= 100):
            raise ValueError('cota deve ser percentual entre 0 e 100')
        if not isinstance(motivo, str) or not motivo.strip() or (modelo is not None and not isinstance(modelo, str)):
            raise ValueError('motivo ou modelo inválido')
        if provedor == 'agy' and status == 'AVAILABLE':
            minimo = float(os.environ.get('JANGADA_DELEGAR_COTA_MIN', '20'))
            if not math.isfinite(minimo) or not 0 <= minimo <= 100:
                raise ValueError('reserva de cota inválida')
            if cota is None:
                status = 'UNKNOWN'
            elif cota < minimo:
                status = 'QUOTA_EXHAUSTED' if cota == 0 else 'QUOTA_LOW'
        agora = time.time()
        with self.estado.transacao():
            anterior = self.db.execute('SELECT * FROM provedores WHERE id=?', (provedor,)).fetchone()
            falhas = anterior['falhas'] if anterior else 0
            if status in {'UNAVAILABLE', 'NETWORK_ERROR', 'RATE_LIMITED'}:
                falhas += 1
                if falhas >= 3:
                    status, validade = 'COOLDOWN', 900
            elif status == 'AVAILABLE':
                falhas = 0
            self.db.execute('''INSERT INTO provedores(id,status,motivo,atualizado,valido_ate,cota,modelo,falhas)
                VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET status=excluded.status,
                motivo=excluded.motivo,atualizado=excluded.atualizado,valido_ate=excluded.valido_ate,
                cota=excluded.cota,modelo=excluded.modelo,falhas=excluded.falhas''',
                            (provedor, status, motivo, agora, agora + validade, cota, modelo, falhas))
            self.db.execute('INSERT INTO eventos_provedores(provedor,data,evento,dados) VALUES(?,?,?,?)',
                            (provedor, agora, 'observado', serializar({'status': status, 'motivo': motivo, 'cota': cota})))

    def listar(self):
        mapa = {linha['id']: dict(linha) for linha in self.db.execute('SELECT * FROM provedores')}
        for provedor in ('local', 'agy'):
            mapa.setdefault(provedor, {'id': provedor, 'status': 'UNKNOWN', 'pausado': 0,
                                       'falhas': 0, 'motivo': 'sem observação', 'atualizado': 0,
                                       'valido_ate': 0, 'cota': None, 'modelo': None})
        agora = time.time()
        for item in mapa.values():
            if item['pausado']:
                item.update(status='UNAVAILABLE', motivo='provedor pausado')
            elif item['valido_ate'] <= agora:
                item.update(status='UNKNOWN', motivo='observação ausente ou expirada', cota=None)
            elif item['id'] == 'agy' and item['status'] == 'AVAILABLE' and item['cota'] is None:
                item.update(status='UNKNOWN', motivo='cota não confirmada')
            item['espera_segundos'] = max(0, math.ceil(item['valido_ate'] - agora)) if item['status'] == 'COOLDOWN' else 0
        return [mapa[nome] for nome in sorted(mapa)]

    def pausar(self, provedor, pausado):
        if not isinstance(provedor, str) or not IDENTIFICADOR.fullmatch(provedor) or type(pausado) is not bool:
            raise ValueError('provedor ou pausa inválida')
        with self.estado.transacao():
            agora = time.time()
            self.db.execute('''INSERT INTO provedores(id,status,pausado,motivo,atualizado,valido_ate)
                VALUES(?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET pausado=excluded.pausado,
                status='UNKNOWN',valido_ate=0,atualizado=excluded.atualizado''',
                            (provedor, 'UNKNOWN', int(pausado), 'aguarda verificação', agora))
            self.db.execute('INSERT INTO eventos_provedores(provedor,data,evento,dados) VALUES(?,?,?,?)',
                            (provedor, agora, 'pausado' if pausado else 'ativado', '{}'))

    def impedimentos(self):
        resultado = []
        for item in self.listar():
            if item['id'] not in {'local', 'agy'}:
                continue
            if item['status'] in {'AVAILABLE', 'DEGRADED', 'UNKNOWN'}:
                continue
            codigo = 'cota_indisponivel' if item['status'] in {'QUOTA_LOW', 'QUOTA_EXHAUSTED'} else 'provedor_em_espera'
            if item['pausado']:
                codigo = 'provedor_pausado'
            resultado.append({'destino': item['id'], 'motivo_codigo': codigo, 'motivo': item['motivo']})
        return resultado

    def registrar_delegacao(self, registro, codigo):
        provedor = registro.get('destino')
        for tentativa in registro.get('tentativas', []):
            if isinstance(tentativa, dict) and tentativa.get('destino') != provedor:
                self.registrar_delegacao(tentativa, tentativa.get('codigo_saida', 4))
        if provedor not in {'local', 'agy'}:
            return
        motivo = registro.get('motivo_codigo')
        if motivo in {'provedor_em_espera', 'provedor_pausado', 'cota_indisponivel', 'destino_proibido'}:
            return
        if codigo == 0:
            cota = registro.get('cota_depois') if provedor == 'agy' else None
            status = 'AVAILABLE'
            if provedor == 'agy':
                if cota is None:
                    status = 'UNKNOWN'
                elif cota < float(os.environ.get('JANGADA_DELEGAR_COTA_MIN', '20')):
                    status = 'QUOTA_EXHAUSTED' if cota == 0 else 'QUOTA_LOW'
            self.observar(provedor, status, 'executor concluiu chamada', cota=cota, modelo=registro.get('modelo'))
        elif motivo == 'cota_insuficiente':
            cota = registro.get('cota_antes')
            self.observar(provedor, 'QUOTA_EXHAUSTED' if cota == 0 else 'QUOTA_LOW',
                          'cota insuficiente', validade=300, cota=cota)
        elif motivo == 'cota_desconhecida':
            self.observar(provedor, 'UNKNOWN', 'cota desconhecida')
        elif motivo in {'indisponivel', 'erro_execucao', 'modelo_ausente'}:
            self.observar(provedor, 'UNAVAILABLE', motivo)

    def atualizar(self, permitir_remoto=False):
        mapa = {item['id']: item for item in self.listar()}
        if not mapa['local']['pausado'] and mapa['local']['status'] != 'COOLDOWN':
            try:
                url = os.environ.get('JANGADA_OLLAMA_URL', 'http://localhost:11434').rstrip('/') + '/api/tags'
                with urllib.request.urlopen(url, timeout=3) as resposta:
                    dados = json.loads(resposta.read(1024 * 1024).decode('utf-8'))
                if (not isinstance(dados, dict) or not isinstance(dados.get('models'), list)
                        or any(not isinstance(m, dict) or not isinstance(m.get('name'), str) for m in dados['models'])):
                    raise ValueError('lista de modelos inválida')
                nomes = {modelo.get('name') for modelo in dados['models']}
                modelo = os.environ.get('JANGADA_LOCAL_MODELO', 'qwen3:4b')
                if modelo not in nomes:
                    self.observar('local', 'UNAVAILABLE', 'modelo local ausente')
                else:
                    self.observar('local', 'AVAILABLE', 'serviço e modelo presentes', modelo=modelo)
            except (OSError, ValueError, KeyError, TypeError, urllib.error.URLError):
                self.observar('local', 'NETWORK_ERROR', 'serviço local não respondeu')
        if mapa['agy']['pausado'] or mapa['agy']['status'] == 'COOLDOWN':
            return
        try:
            cache = pathlib.Path(os.environ.get('XDG_CACHE_HOME', pathlib.Path.home() / '.cache')) / 'jangada/agy-usage.json'
            idade = time.time() - cache.stat().st_mtime if cache.is_file() else math.inf
            validade = int(os.environ.get('JANGADA_DELEGAR_CACHE', '5')) * 60
            dados = json.loads(cache.read_text(encoding='utf-8')) if 0 <= idade < validade else None
            if dados is None and permitir_remoto and os.environ.get('JANGADA_DELEGAR', 'agy') == 'agy':
                ambiente = os.environ.copy()
                ambiente.pop('JANGADA_SESSAO', None)
                ambiente['JANGADA_HOOK_DESLIGADO'] = '1'
                consulta = subprocess.run(['timeout', '--signal=KILL', '10', 'agy', '-p', '/usage',
                                           '--sandbox', '--output-format', 'json', '--print-timeout', '10s'],
                                          capture_output=True, text=True, timeout=12, check=True,
                                          stdin=subprocess.DEVNULL, cwd=pathlib.Path.home(), env=ambiente)
                dados = json.loads(consulta.stdout)
                idade = 0
            grupos = dados['command']['data']['groups']
            if not isinstance(grupos, list) or any(not isinstance(g, dict) for g in grupos):
                raise ValueError('grupos de cota inválidos')
            cotas = []
            for grupo in grupos:
                buckets = grupo.get('buckets', [])
                if not isinstance(buckets, list) or any(not isinstance(b, dict) for b in buckets):
                    raise ValueError('cotas inválidas')
                cotas.extend(b['remaining_fraction'] for b in buckets if b.get('id') == 'gemini-5h')
            if len(cotas) != 1 or type(cotas[0]) not in (int, float) or not math.isfinite(cotas[0]) or not 0 <= cotas[0] <= 1:
                raise ValueError('cota inválida')
            percentual = cotas[0] * 100
            status = 'AVAILABLE' if percentual >= float(os.environ.get('JANGADA_DELEGAR_COTA_MIN', '20')) else 'QUOTA_LOW'
            if percentual == 0:
                status = 'QUOTA_EXHAUSTED'
            self.observar('agy', status, 'cota consultada', cota=percentual,
                          validade=max(1, min(60, int(validade - idade))) if dados is not None and math.isfinite(idade) else 60)
        except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
            self.observar('agy', 'UNKNOWN', 'cota desconhecida ou expirada')


def retomar(estado, saude, raiz, config, perfil, permitir_remoto):
    politica = pathlib.Path(config) / 'delegacao.json'
    if not politica.is_file():
        politica = raiz / 'default/delegacao/roteamento.json'
    preferencias = json.loads(politica.read_text(encoding='utf-8'))
    if not isinstance(preferencias, dict) or any(
        capacidade not in CAPACIDADES or not isinstance(destinos, list) or not destinos
        or any(not isinstance(d, str) or d not in {'local', 'agy'} for d in destinos)
        or len(destinos) != len(set(destinos))
        for capacidade, destinos in preferencias.items()
    ):
        raise ValueError('política de capacidades inválida')
    disponiveis = {item['id'] for item in saude.listar() if item['status'] == 'AVAILABLE'}
    retomadas = []
    for item in estado.listar():
        tarefa = item['especificacao']
        if item['status'] not in {'WAITING_PROVIDER', 'WAITING_QUOTA'} or tarefa['papel'] != 'leitor':
            continue
        if tarefa['risco'] > 2 or tarefa['qualidade'] not in {'low', 'medium'}:
            continue
        candidatos = preferencias.get(tarefa['capacidade'], [])
        if perfil == 'offline':
            candidatos = [c for c in candidatos if c == 'local']
        elif perfil == 'quality':
            candidatos = [c for c in candidatos if c == 'agy']
        sessao = os.environ.get('JANGADA_DELEGAR') or 'agy'
        if sessao in {'claude', 'nativo'}:
            continue
        if sessao == 'local' or not permitir_remoto or not tarefa.get('permitir_remoto', False):
            candidatos = [c for c in candidatos if c != 'agy']
        consumo = estado.consumo(item['id'])
        if (consumo['chamadas'] is None or consumo['chamadas'] >= tarefa.get('max_chamadas', 8)
                or consumo['segundos'] >= tarefa.get('tempo_total', 600)
                or item['tentativas'] >= tarefa.get('max_tentativas', 2)):
            continue
        if any(c in disponiveis for c in candidatos):
            try:
                estado.alterar(item['id'], 'retomar')
            except ValueError:
                continue
            retomadas.append(item['id'])
    return retomadas
