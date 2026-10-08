"""Visão conjunta somente leitura; ausência de registro não é aprovação."""

import contextlib
import json
import os
from pathlib import Path
import sqlite3
import stat
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'orquestracao'))
from projetos import chave, ler_json, ler_projeto  # noqa: E402

ESTADOS = {'QUEUED': 'Pronta', 'RUNNING': 'Executando', 'COMPLETED': 'Concluída',
           'REVIEW_REQUIRED': 'Em revisão', 'REVISION_REQUIRED': 'Em revisão',
           'WAITING_REVIEWER': 'Em revisão', 'WAITING_PROVIDER': 'Bloqueada',
           'WAITING_QUOTA': 'Bloqueada', 'BLOCKED': 'Bloqueada', 'PAUSED': 'Bloqueada',
           'FAILED': 'Falhou', 'CANCELLED': 'Cancelada'}
SESSOES = {'iniciado': 'Executando', 'ativo': 'Executando', 'trabalhando': 'Executando',
           'aguardando': 'Bloqueada', 'concluido': 'Em revisão', 'interrompido': 'Bloqueada'}


@contextlib.contextmanager
def banco_leitura(caminho):
    # Mesmo mode=ro pode criar WAL/SHM na origem. Uma cópia estável inclui o WAL
    # para não perder transações já confirmadas que ainda não chegaram ao banco.
    caminho = Path(caminho)
    with tempfile.TemporaryDirectory(prefix='jangada-consulta-') as pasta:
        copia = Path(pasta) / caminho.name
        for _ in range(3):
            antes = {}
            for nome in (caminho, Path(str(caminho) + '-wal')):
                destino = Path(pasta) / nome.name
                try:
                    fd = os.open(nome, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
                except FileNotFoundError:
                    destino.unlink(missing_ok=True)
                    antes[nome] = None
                    continue
                with os.fdopen(fd, 'rb') as origem, destino.open('wb') as saida:
                    info = os.fstat(origem.fileno())
                    if not stat.S_ISREG(info.st_mode):
                        raise ValueError('banco deve ser arquivo regular')
                    antes[nome] = (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                    while bloco := origem.read(1024 * 1024):
                        saida.write(bloco)
            depois = {}
            for nome in antes:
                try:
                    info = nome.lstat()
                    depois[nome] = (info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)
                except FileNotFoundError:
                    depois[nome] = None
            if antes == depois:
                break
        else:
            raise ValueError('banco mudou durante a consulta; tente novamente')
        db = sqlite3.connect(copia.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=5)
        try:
            db.row_factory = sqlite3.Row
            db.execute('PRAGMA query_only=ON')
            db.execute('BEGIN')
            yield db
        finally:
            db.close()


def agregado(estados):
    if not estados:
        return 'Planejada'
    if all(e == 'Concluída' for e in estados):
        return 'Concluída'
    if all(e == 'Cancelada' for e in estados):
        return 'Cancelada'
    return next((e for e in ('Executando', 'Falhou', 'Em revisão', 'Bloqueada', 'Pronta', 'Planejada')
                 if e in estados), 'Bloqueada')


def consultar(raiz, projeto=None):
    raiz = Path(raiz).resolve()
    filtro = str(Path(projeto).resolve()) if projeto is not None else None
    resultado = dict(projetos=[], atividades=[], tarefas=[], sessoes=[], execucoes=[], revisoes=[], eventos=[], erros=[])
    pastas = raiz / 'agentes/projetos'
    if pastas.is_symlink() or (raiz / 'agentes').is_symlink():
        resultado['erros'].append('estado operacional com ligação simbólica')
        return resultado
    for pasta in sorted(pastas.glob('*')):
        if not pasta.is_dir():
            continue
        try:
            if pasta.is_symlink():
                raise ValueError('pasta do projeto com ligação simbólica')
            dados = ler_projeto(pasta)
            if filtro and (dados['caminho'] != filtro if dados else pasta.name != chave(filtro)):
                continue
            dados = dados or dict(id=pasta.name, caminho=filtro, nome='projeto-' + pasta.name[:12], politica={})
            resultado['projetos'].append(dados)
            banco = pasta / 'tarefas.sqlite'
            if not banco.exists():
                continue
            if any((pasta / n).is_symlink() for n in ('tarefas.sqlite', 'tarefas.sqlite-wal', 'tarefas.sqlite-shm')):
                raise ValueError('banco com ligação simbólica')
            with banco_leitura(banco) as db:
                tabelas = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                tarefas = [dict(r) for r in db.execute('SELECT * FROM tarefas ORDER BY criado,id')]
                estados = {t['id']: t['status'] for t in tarefas}
                for tarefa in tarefas:
                    spec = json.loads(tarefa['especificacao'])
                    if not isinstance(spec, dict):
                        raise ValueError('especificação de tarefa inválida')
                    tarefa['especificacao'] = spec
                    tarefa['resultado'] = json.loads(tarefa['resultado']) if tarefa['resultado'] else None
                    if tarefa['resultado'] is not None and not isinstance(tarefa['resultado'], dict):
                        raise ValueError('resultado de tarefa inválido')
                    bloqueada = tarefa['status'] == 'QUEUED' and any(estados.get(d) != 'COMPLETED' for d in spec.get('dependencias', []))
                    tarefa.update(projeto=dados['id'], atividade=spec.get('atividade'),
                                  estado='Bloqueada' if bloqueada else ESTADOS.get(tarefa['status'], 'Bloqueada'))
                    resultado['tarefas'].append(tarefa)
                if 'atividades' in tabelas:
                    for r in db.execute('SELECT * FROM atividades ORDER BY criado,id'):
                        atividade = dict(r, projeto=dados['id'])
                        atividade['criterios'] = json.loads(atividade['criterios'])
                        resultado['atividades'].append(atividade)
                if 'execucoes' in tabelas:
                    for r in db.execute('SELECT * FROM execucoes ORDER BY inicio,id'):
                        execucao = dict(r, projeto=dados['id'])
                        if execucao.get('roteamento'):
                            execucao['roteamento'] = json.loads(execucao['roteamento'])
                        resultado['execucoes'].append(execucao)
                for r in db.execute("SELECT tarefa,data,dados FROM eventos WHERE evento='revisada' ORDER BY seq"):
                    resultado['revisoes'].append(dict(projeto=dados['id'], tarefa=r['tarefa'], data=r['data'],
                                                      **json.loads(r['dados'])))
                for r in db.execute('SELECT seq,tarefa,data,evento,dados FROM eventos ORDER BY seq'):
                    resultado['eventos'].append(dict(projeto=dados['id'], seq=r['seq'], tarefa=r['tarefa'],
                                                     data=r['data'], evento=r['evento'], dados=json.loads(r['dados'])))
        except (OSError, ValueError, KeyError, TypeError, sqlite3.Error) as erro:
            resultado['erros'].append(f'{pasta.name}: {erro}')
    for arquivo in sorted((raiz / 'agentes').glob('*.json')):
        try:
            dados = ler_json(arquivo)
            if not isinstance(dados, dict) or not isinstance(dados.get('sessao'), str):
                continue
            caminho = dados.get('raiz')
            if not isinstance(caminho, str) or not Path(caminho).is_absolute():
                raise ValueError('sessão sem raiz válida')
            if filtro and str(Path(caminho).resolve()) != filtro:
                continue
            p = next((p for p in resultado['projetos'] if p['caminho'] == caminho or p['id'] == chave(caminho)), None)
            if p is None:
                p = dict(id=chave(caminho), caminho=caminho, nome=Path(caminho).name, politica={})
                resultado['projetos'].append(p)
            resultado['sessoes'].append({**dados, 'projeto': p['id'],
                                         'estado_persistido': dados.get('estado'),
                                         'estado': SESSOES.get(dados.get('estado'), 'Bloqueada')})
        except (OSError, ValueError, KeyError, TypeError) as erro:
            resultado['erros'].append(f'{arquivo.name}: {erro}')
    for atividade in resultado['atividades']:
        estados = [t['estado'] for t in resultado['tarefas'] if t['projeto'] == atividade['projeto']
                   and t['atividade'] == atividade['id']]
        estados += [s['estado'] for s in resultado['sessoes'] if s['projeto'] == atividade['projeto']
                    and s.get('atividade') == atividade['id']]
        atividade['estado'] = agregado(estados)
    return resultado


def registro_provedores(raiz):
    resposta = subprocess.run([str(Path(raiz) / 'bin/jangada-config'), '--provedores-json'],
                              capture_output=True, text=True, timeout=10, check=True)
    dados = json.loads(resposta.stdout)
    if not isinstance(dados, list) or any(not isinstance(p, dict) or not isinstance(p.get('id'), str) for p in dados):
        raise ValueError('registro de provedores inválido')
    return dados


def catalogos(raiz):
    raiz = Path(raiz)
    dados = {'provedores': [], 'perfis': [], 'principais': [], 'configuracao': None, 'erros': []}
    for comando, campo in [(['jangada-config', '--provedores-json'], 'provedores'),
                           (['jangada-config', '--publico-json'], 'configuracao'),
                           (['jangada-agente', '--capacidades-json'], 'capacidades')]:
        try:
            resposta = subprocess.run([str(raiz / 'bin' / comando[0]), *comando[1:]],
                                      capture_output=True, text=True, timeout=10, check=True)
            valor = json.loads(resposta.stdout)
            if campo == 'capacidades':
                dados['perfis'] = valor['perfis']
                dados['principais'] = valor['principais']
            else:
                dados[campo] = valor
        except (OSError, ValueError, KeyError, subprocess.SubprocessError):
            dados['erros'].append('catálogo indisponível: ' + campo)
    return dados
