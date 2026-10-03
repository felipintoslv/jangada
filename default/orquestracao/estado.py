"""Fila persistente de tarefas e artefatos, sem executar comandos do estado."""

import contextlib
import hashlib
import json
import math
import os
import pathlib
import re
import sqlite3
import tempfile
import time
import uuid

ESTADOS = {
    'QUEUED', 'RUNNING', 'COMPLETED', 'REVIEW_REQUIRED', 'REVISION_REQUIRED',
    'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER', 'FAILED', 'CANCELLED', 'PAUSED', 'BLOCKED',
}
FINAIS = {'COMPLETED', 'FAILED', 'CANCELLED'}
IDENTIFICADOR = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,95}$')


def serializar(valor):
    return json.dumps(valor, ensure_ascii=False, sort_keys=True, allow_nan=False)


def tarefa_valida(tarefa):
    if not isinstance(tarefa, dict):
        raise ValueError('tarefa deve ser um objeto')
    obrigatorios = {'id', 'pedido', 'papel', 'capacidade', 'risco', 'qualidade', 'fontes'}
    if not obrigatorios <= tarefa.keys():
        raise ValueError('campos obrigatórios ausentes na tarefa')
    if not isinstance(tarefa['id'], str) or not IDENTIFICADOR.fullmatch(tarefa['id']):
        raise ValueError('identificador inválido')
    for campo in ('pedido', 'papel', 'capacidade'):
        if not isinstance(tarefa[campo], str) or not tarefa[campo].strip():
            raise ValueError(f'{campo} deve ser texto não vazio')
    if type(tarefa['risco']) is not int or not 0 <= tarefa['risco'] <= 4:
        raise ValueError('risco deve estar entre 0 e 4')
    if tarefa['qualidade'] not in ('low', 'medium', 'high', 'critical'):
        raise ValueError('qualidade inválida')
    if not isinstance(tarefa['fontes'], list) or not tarefa['fontes'] or any(
        not isinstance(fonte, str) or not fonte for fonte in tarefa['fontes']
    ):
        raise ValueError('fontes devem ser uma lista não vazia de caminhos')
    dependencias = tarefa.get('dependencias', [])
    if not isinstance(dependencias, list) or any(
        not isinstance(dep, str) or not IDENTIFICADOR.fullmatch(dep) for dep in dependencias
    ) or len(dependencias) != len(set(dependencias)):
        raise ValueError('dependências inválidas ou repetidas')
    if tarefa['id'] in dependencias:
        raise ValueError('tarefa não pode depender de si mesma')
    requisitos = tarefa.get('requisitos', [])
    if not isinstance(requisitos, list) or any(
        not isinstance(item, str) or not item.strip() or item.startswith('-') or '\n' in item
        for item in requisitos
    ) or len(requisitos) != len(set(requisitos)):
        raise ValueError('requisitos inválidos ou repetidos')
    for campo, padrao in (('max_tentativas', 2), ('tempo_total', 600), ('max_chamadas', 8)):
        valor = tarefa.get(campo, padrao)
        if type(valor) is not int or not 1 <= valor <= 999999:
            raise ValueError(f'{campo} deve ser inteiro positivo')
    for campo in ('permitir_remoto', 'permitir_codex'):
        if campo in tarefa and type(tarefa[campo]) is not bool:
            raise ValueError(f'{campo} deve ser booleano')
    serializar(tarefa)


class Estado:
    def __init__(self, pasta, raiz=None):
        original = pathlib.Path(pasta).absolute()
        base = pathlib.Path(raiz).absolute() if raiz is not None else original.parent
        relativo = original.relative_to(base)
        if '..' in relativo.parts:
            raise ValueError('pasta de estado fora da raiz configurada')
        base.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.pasta = base.resolve()
        for componente in relativo.parts:
            self.pasta /= componente
            if self.pasta.is_symlink():
                raise ValueError('pasta de estado não pode conter links simbólicos')
            self.pasta.mkdir(mode=0o700, exist_ok=True)
        if self.pasta.is_symlink() or any((self.pasta / nome).is_symlink() for nome in (
            'tarefas.sqlite', 'tarefas.sqlite-wal', 'tarefas.sqlite-shm',
        )):
            raise ValueError('estado não pode usar links simbólicos')
        try:
            fd = os.open(self.pasta / 'tarefas.sqlite', os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.close(fd)
        except FileExistsError:
            pass
        self.db = sqlite3.connect(self.pasta / 'tarefas.sqlite', timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS tarefas (
                id TEXT PRIMARY KEY, especificacao TEXT NOT NULL, status TEXT NOT NULL,
                tentativas INTEGER NOT NULL DEFAULT 0, dono TEXT, prazo REAL,
                artefato TEXT, hash_artefato TEXT, resultado TEXT, motivo TEXT,
                criado REAL NOT NULL, atualizado REAL NOT NULL
            );
            CREATE TABLE IF NOT EXISTS eventos (
                seq INTEGER PRIMARY KEY, tarefa TEXT NOT NULL, data REAL NOT NULL,
                evento TEXT NOT NULL, dados TEXT NOT NULL,
                FOREIGN KEY(tarefa) REFERENCES tarefas(id)
            );
        ''')

    def fechar(self):
        self.db.close()

    @contextlib.contextmanager
    def transacao(self):
        self.db.execute('BEGIN IMMEDIATE')
        try:
            yield
            self.db.execute('COMMIT')
        except BaseException:
            self.db.execute('ROLLBACK')
            raise

    def evento(self, tarefa, evento, dados):
        self.db.execute('INSERT INTO eventos(tarefa,data,evento,dados) VALUES(?,?,?,?)',
                        (tarefa, time.time(), evento, serializar(dados)))

    def importar(self, tarefas):
        if not isinstance(tarefas, list) or not tarefas:
            raise ValueError('plano deve conter uma lista não vazia de tarefas')
        for tarefa in tarefas:
            tarefa_valida(tarefa)
        if len({t['id'] for t in tarefas}) != len(tarefas):
            raise ValueError('identificadores repetidos no plano')
        with self.transacao():
            existentes = {r['id']: json.loads(r['especificacao']) for r in self.db.execute('SELECT * FROM tarefas')}
            mapa = existentes | {t['id']: t for t in tarefas}
            visitados, caminho = set(), set()

            def visitar(identificador):
                if identificador in caminho:
                    raise ValueError('ciclo nas dependências')
                if identificador in visitados:
                    return
                if identificador not in mapa:
                    raise ValueError(f'dependência inexistente: {identificador}')
                caminho.add(identificador)
                for dep in mapa[identificador].get('dependencias', []):
                    visitar(dep)
                caminho.remove(identificador)
                visitados.add(identificador)

            for identificador in mapa:
                visitar(identificador)
            agora = time.time()
            for tarefa in tarefas:
                anterior = existentes.get(tarefa['id'])
                if anterior is not None:
                    if serializar(anterior) != serializar(tarefa):
                        raise ValueError(f'tarefa existente mudou: {tarefa["id"]}; use outro identificador')
                    continue
                self.db.execute('INSERT INTO tarefas(id,especificacao,status,criado,atualizado) VALUES(?,?,?,?,?)',
                                (tarefa['id'], serializar(tarefa), 'QUEUED', agora, agora))
                self.evento(tarefa['id'], 'criada', {'especificacao': tarefa})

    def listar(self):
        resultado = []
        for linha in self.db.execute('SELECT * FROM tarefas ORDER BY criado,id'):
            item = dict(linha)
            item['especificacao'] = json.loads(item['especificacao'])
            item['resultado'] = json.loads(item['resultado']) if item['resultado'] else None
            resultado.append(item)
        return resultado

    def consumo(self, identificador):
        chamadas, segundos = 0, 0
        for linha in self.db.execute('SELECT evento,dados FROM eventos WHERE tarefa=? AND evento IN (?,?)',
                                     (identificador, 'execucao_encerrada', 'reserva_expirada')):
            if linha['evento'] == 'reserva_expirada':
                chamadas = None
                continue
            resultado = json.loads(linha['dados']).get('resultado')
            metrica = resultado.get('metricas') if isinstance(resultado, dict) else None
            if not isinstance(metrica, dict):
                chamadas = None
                continue
            quantidade = metrica.get('chamadas')
            duracao = metrica.get('segundos')
            if type(quantidade) is not int or quantidade < 0:
                chamadas = None
            elif chamadas is not None:
                chamadas += quantidade
            if type(duracao) is int and duracao >= 0:
                segundos += duracao
            else:
                chamadas = None
        return {'chamadas': chamadas, 'segundos': segundos}

    def reservar(self, duracao=660):
        if not isinstance(duracao, (int, float)) or not math.isfinite(duracao) or duracao <= 0:
            raise ValueError('duração da reserva inválida')
        with self.transacao():
            agora = time.time()
            for antiga in self.db.execute('SELECT * FROM tarefas WHERE status=? AND prazo<=?', ('RUNNING', agora)).fetchall():
                self.db.execute('UPDATE tarefas SET status=?,dono=NULL,prazo=NULL,motivo=?,atualizado=? WHERE id=?',
                                ('REVISION_REQUIRED', 'executor interrompido; conferir antes de repetir', agora, antiga['id']))
                self.evento(antiga['id'], 'reserva_expirada', {'dono': antiga['dono']})
            tarefas = self.listar()
            estados = {t['id']: t['status'] for t in tarefas}
            for tarefa in tarefas:
                if tarefa['status'] == 'QUEUED' and tarefa['tentativas'] >= tarefa['especificacao'].get('max_tentativas', 2):
                    self.db.execute('UPDATE tarefas SET status=?,motivo=?,atualizado=? WHERE id=?',
                                    ('FAILED', 'limite de tentativas atingido', agora, tarefa['id']))
                    estados[tarefa['id']] = 'FAILED'
                    self.evento(tarefa['id'], 'limite_tentativas', {})
            alterou = True
            while alterou:
                alterou = False
                for tarefa in tarefas:
                    bloqueadas = [dep for dep in tarefa['especificacao'].get('dependencias', [])
                                  if estados[dep] in {'FAILED', 'CANCELLED', 'BLOCKED'}]
                    if estados[tarefa['id']] == 'QUEUED' and bloqueadas:
                        self.db.execute('UPDATE tarefas SET status=?,motivo=?,atualizado=? WHERE id=?',
                                        ('BLOCKED', 'dependências impedidas: ' + ', '.join(bloqueadas), agora, tarefa['id']))
                        estados[tarefa['id']] = 'BLOCKED'
                        self.evento(tarefa['id'], 'dependencia_impedida', {'dependencias': bloqueadas})
                        alterou = True
            for tarefa in tarefas:
                spec = tarefa['especificacao']
                if estados[tarefa['id']] != 'QUEUED' or any(estados[dep] != 'COMPLETED' for dep in spec.get('dependencias', [])):
                    continue
                dono = str(uuid.uuid4())
                self.db.execute('UPDATE tarefas SET status=?,tentativas=tentativas+1,dono=?,prazo=?,atualizado=? WHERE id=?',
                                ('RUNNING', dono, agora + duracao, agora, tarefa['id']))
                self.evento(tarefa['id'], 'reservada', {'dono': dono})
                return spec, dono
        return None

    def finalizar(self, identificador, dono, status, resultado, artefato=None):
        if status not in {'REVIEW_REQUIRED', 'REVISION_REQUIRED', 'FAILED',
                          'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER'}:
            raise ValueError('resultado de execução deve aguardar revisão ou informar falha')
        if artefato is not None and not isinstance(artefato, str):
            raise ValueError('artefato deve ser texto')
        if status == 'REVIEW_REQUIRED' and (artefato is None or not artefato.strip()):
            raise ValueError('revisão exige artefato não vazio')
        if not isinstance(resultado, dict):
            raise ValueError('resultado deve ser um objeto')
        metricas = resultado.get('metricas', {})
        if not isinstance(metricas, dict):
            raise ValueError('métricas devem ser um objeto')
        if metricas.get('chamadas') is not None and (
            type(metricas['chamadas']) is not int or metricas['chamadas'] < 0
        ):
            raise ValueError('quantidade de chamadas inválida')
        segundos = metricas.get('segundos', 0)
        if type(segundos) is not int or segundos < 0:
            raise ValueError('tempo de execução inválido')
        serializar(resultado)
        with self.transacao():
            tarefa = self.db.execute('SELECT * FROM tarefas WHERE id=?', (identificador,)).fetchone()
            if not tarefa or tarefa['status'] != 'RUNNING' or tarefa['dono'] != dono or tarefa['prazo'] <= time.time():
                raise ValueError('executor não possui reserva válida da tarefa')
            hash_artefato = None
            if artefato is not None:
                hash_artefato = hashlib.sha256(artefato.encode()).hexdigest()
                objetos = self.pasta / 'artefatos'
                objetos.mkdir(exist_ok=True)
                if objetos.is_symlink():
                    raise ValueError('pasta de artefatos não pode ser link simbólico')
                destino = objetos / f'{hash_artefato}.txt'
                if destino.exists() or destino.is_symlink():
                    self.ler_artefato(hash_artefato)
                else:
                    fd, temporario = tempfile.mkstemp(prefix='.artefato-', dir=objetos)
                    try:
                        with os.fdopen(fd, 'w', encoding='utf-8') as arquivo:
                            arquivo.write(artefato)
                            arquivo.flush()
                            os.fsync(arquivo.fileno())
                        os.replace(temporario, destino)
                    finally:
                        pathlib.Path(temporario).unlink(missing_ok=True)
            self.db.execute('UPDATE tarefas SET status=?,resultado=?,artefato=?,hash_artefato=?,dono=NULL,prazo=NULL,atualizado=? WHERE id=?',
                            (status, serializar(resultado), hash_artefato, hash_artefato, time.time(), identificador))
            if resultado.get('execucao_iniciada') is False:
                self.db.execute('UPDATE tarefas SET tentativas=tentativas-1 WHERE id=?', (identificador,))
            self.evento(identificador, 'execucao_encerrada', {'status': status, 'resultado': resultado, 'artefato': hash_artefato})

    def revisar(self, identificador, parecer, aprovar):
        if not isinstance(parecer, str) or not parecer.strip() or type(aprovar) is not bool:
            raise ValueError('revisão exige parecer e decisão explícitos')
        with self.transacao():
            tarefa = self.db.execute('SELECT * FROM tarefas WHERE id=?', (identificador,)).fetchone()
            if not tarefa or tarefa['status'] != 'REVIEW_REQUIRED' or not tarefa['hash_artefato']:
                raise ValueError('tarefa sem artefato aguardando revisão')
            self.ler_artefato(tarefa['hash_artefato'])
            status = 'COMPLETED' if aprovar else 'REVISION_REQUIRED'
            self.db.execute('UPDATE tarefas SET status=?,motivo=?,atualizado=? WHERE id=?',
                            (status, parecer, time.time(), identificador))
            self.evento(identificador, 'revisada', {'status': status, 'parecer': parecer})

    def ler_artefato(self, resumo):
        if not isinstance(resumo, str) or not re.fullmatch(r'[0-9a-f]{64}', resumo):
            raise ValueError('identificador de artefato inválido')
        pasta = self.pasta / 'artefatos'
        objeto = pasta / f'{resumo}.txt'
        if pasta.is_symlink() or objeto.is_symlink():
            raise ValueError('artefato não pode usar links simbólicos')
        conteudo = objeto.read_bytes()
        if hashlib.sha256(conteudo).hexdigest() != resumo:
            raise ValueError('artefato adulterado antes da revisão')
        return conteudo.decode('utf-8')

    def alterar(self, identificador, acao):
        destinos = {'cancelar': 'CANCELLED', 'pausar': 'PAUSED', 'retomar': 'QUEUED', 'repetir': 'QUEUED'}
        if acao not in destinos:
            raise ValueError('ação desconhecida')
        with self.transacao():
            tarefa = self.db.execute('SELECT * FROM tarefas WHERE id=?', (identificador,)).fetchone()
            if not tarefa or tarefa['status'] in FINAIS or tarefa['status'] == 'RUNNING':
                raise ValueError('tarefa inexistente, finalizada ou em execução')
            if acao == 'pausar' and tarefa['status'] in {'REVIEW_REQUIRED', 'REVISION_REQUIRED'}:
                raise ValueError('tarefa aguardando conferência não pode contornar a revisão por pausa')
            permitidos = {'retomar': {'PAUSED', 'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER'},
                          'repetir': {'REVISION_REQUIRED'}}
            if acao in permitidos and tarefa['status'] not in permitidos[acao]:
                raise ValueError('transição de tarefa inválida')
            self.db.execute('UPDATE tarefas SET status=?,motivo=NULL,atualizado=? WHERE id=?',
                            (destinos[acao], time.time(), identificador))
            if destinos[acao] == 'QUEUED':
                self.db.execute('UPDATE tarefas SET artefato=NULL,hash_artefato=NULL,resultado=NULL WHERE id=?', (identificador,))
            self.evento(identificador, acao, {})
