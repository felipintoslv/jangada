"""Retrato da fila e dos provedores; nunca cria nem atualiza o estado de execução."""

import hashlib
import os
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'orquestracao'))
from estado import Estado  # noqa: E402
from metricas_projeto import calcular, ler_precos  # noqa: E402
from saude import Saude  # noqa: E402


class Consulta(Estado):
    def __init__(self, caminho):
        self.db = sqlite3.connect(caminho.as_uri() + '?mode=ro', uri=True, isolation_level=None, timeout=5)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA query_only=ON')


def coletar(raiz, projetos, projeto_de):
    raiz = Path(raiz).resolve()
    nomes = {hashlib.sha256(str(p.resolve()).encode()).hexdigest(): projeto_de(str(p)) for p in projetos}
    config = Path(os.environ.get('JANGADA_CONFIG') or
                  str(Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'jangada'))
    resultado = dict(tarefas=[], projetos=[], provedores=[], erros=[])
    try:
        precos = ler_precos(config / 'precos.json')
    except (OSError, ValueError) as erro:
        precos = None
        resultado['erros'].append(f'preços: {erro}')
    for arquivo in sorted((raiz / 'agentes/projetos').glob('*/tarefas.sqlite')):
        projeto = nomes.get(arquivo.parent.name, 'projeto-' + arquivo.parent.name[:12])
        if arquivo.is_symlink() or arquivo.parent.is_symlink() or not arquivo.resolve().is_relative_to(raiz):
            resultado['erros'].append(f'{projeto}: estado com link simbólico não foi lido')
            continue
        consulta = None
        try:
            consulta = Consulta(arquivo)
            consulta.db.execute('BEGIN')
            tarefas = consulta.listar()
            estados = {t['id']: t['status'] for t in tarefas}
            for tarefa in tarefas:
                spec = tarefa['especificacao']
                consumo = consulta.consumo(tarefa['id'])
                chamadas = consumo['chamadas'] if tarefa['status'] != 'RUNNING' else None
                segundos = consumo['segundos'] if chamadas is not None else None
                dependencias = [d for d in spec.get('dependencias', []) if estados.get(d) != 'COMPLETED']
                status = 'BLOCKED' if tarefa['status'] == 'QUEUED' and dependencias else tarefa['status']
                resultado['tarefas'].append(dict(
                    projeto=projeto, id=tarefa['id'], estado=status,
                    papel=spec['papel'], capacidade=spec['capacidade'],
                    prioridade=spec.get('prioridade', 'normal'), tentativas=tarefa['tentativas'],
                    motivo=tarefa['motivo'] or ('dependências pendentes' if status == 'BLOCKED' else ''),
                    dependencias=', '.join(dependencias),
                    atualizado=tarefa['atualizado'], chamadas=chamadas, segundos=segundos,
                    limite_chamadas=spec.get('max_chamadas', 8), limite_segundos=spec.get('tempo_total', 600),
                    saldo_chamadas=max(0, spec.get('max_chamadas', 8) - chamadas) if chamadas is not None else None,
                    saldo_segundos=max(0, spec.get('tempo_total', 600) - segundos) if segundos is not None else None))
            resultado['projetos'].append(dict(projeto=projeto, **calcular(consulta, precos)))
            consulta.db.execute('ROLLBACK')
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError, AttributeError) as erro:
            resultado['tarefas'] = [t for t in resultado['tarefas'] if t['projeto'] != projeto]
            resultado['erros'].append(f'{projeto}: {type(erro).__name__}')
        finally:
            if consulta is not None:
                consulta.fechar()
    arquivo = raiz / 'agentes/runtime/tarefas.sqlite'
    if (arquivo.exists() and not arquivo.is_symlink() and not arquivo.parent.is_symlink()
            and arquivo.resolve().is_relative_to(raiz)):
        consulta = None
        try:
            consulta = Consulta(arquivo)
            saude = Saude.__new__(Saude)
            saude.db = consulta.db
            resultado['provedores'] = saude.listar()
        except sqlite3.Error as erro:
            resultado['erros'].append(f'provedores: {type(erro).__name__}')
        finally:
            if consulta is not None:
                consulta.fechar()
    return resultado
