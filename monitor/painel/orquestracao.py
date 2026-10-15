"""Retrato da fila e dos provedores; nunca cria nem atualiza o estado de execução."""

import os
from pathlib import Path
import sys

# Sem JANGADA_CORE_PY, a pasta acima desta pelo caminho recebido, sem seguir links.
NUCLEO = Path(os.environ.get('JANGADA_CORE_PY') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(NUCLEO / 'orquestracao'))
sys.dont_write_bytecode = True
sys.path.insert(0, str(NUCLEO))
from nucleo.consultas import consultar_filas  # noqa: E402
from metricas_projeto import ler_precos  # noqa: E402


def coletar(raiz, projetos, projeto_de):
    raiz = Path(raiz).resolve()
    config = Path(os.environ.get('JANGADA_CONFIG') or
                  str(Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'jangada'))
    resultado = dict(tarefas=[], projetos=[], provedores=[], erros=[])
    try:
        precos = ler_precos(config / 'precos.json')
    except (OSError, ValueError) as erro:
        precos = None
        resultado['erros'].append(f'preços: {erro}')
    try:
        filas = consultar_filas(raiz, projetos, precos)
        if (not isinstance(filas, dict) or type(filas.get('versao')) is not int or filas['versao'] != 1
                or any(not isinstance(filas.get(campo), list) for campo in ('projetos', 'provedores', 'erros'))):
            raise ValueError('Contrato de filas desconhecido ou inválido.')
        if (any(not isinstance(p, dict) or not isinstance(p.get('id'), str)
                or p.get('caminho') is not None and not isinstance(p['caminho'], str)
                or any(not isinstance(p.get(c), tipo) for c, tipo in
                       (('tarefas', list), ('consumos', dict), ('metricas', dict))) for p in filas['projetos'])
                or any(not isinstance(e, dict) or not isinstance(e.get('mensagem'), str)
                       or 'projeto' not in e or 'caminho' not in e for e in filas['erros'])):
            raise ValueError('Campos da consulta de filas inválidos.')
    except (OSError, ValueError, TypeError) as erro:
        resultado['erros'].append('filas: ' + str(erro))
        return resultado

    def nome(item):
        return projeto_de(item['caminho']) if item['caminho'] else 'projeto-' + item['id'][:12]

    for erro in filas['erros']:
        prefixo = nome(dict(id=erro['projeto'], caminho=erro['caminho'])) + ': ' if erro['projeto'] else ''
        resultado['erros'].append(prefixo + erro['mensagem'])
    resultado['provedores'] = filas['provedores']
    for fila in filas['projetos']:
        projeto = nome(fila)
        try:
            tarefas = fila['tarefas']
            estados = {t['id']: t['status'] for t in tarefas}
            for tarefa in tarefas:
                spec = tarefa['especificacao']
                consumo = fila['consumos'][tarefa['id']]
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
            resultado['projetos'].append(dict(projeto=projeto, **fila['metricas']))
        except (ValueError, KeyError, TypeError, AttributeError) as erro:
            resultado['tarefas'] = [t for t in resultado['tarefas'] if t['projeto'] != projeto]
            resultado['erros'].append(f'{projeto}: {type(erro).__name__}')
    return resultado
