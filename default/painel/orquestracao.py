"""Retrato da fila e dos provedores; nunca cria nem atualiza o estado de execução."""

import hashlib
import os
from pathlib import Path
import sqlite3
import sys

# Sem JANGADA_CORE_PY, a pasta acima desta pelo caminho recebido, sem seguir links.
NUCLEO = Path(os.environ.get('JANGADA_CORE_PY') or os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, str(NUCLEO / 'orquestracao'))
sys.dont_write_bytecode = True
sys.path.insert(0, str(NUCLEO))
from nucleo.consultas import banco_leitura, consumo_tarefa, listar_provedores, listar_tarefas  # noqa: E402
from metricas_projeto import calcular, ler_precos  # noqa: E402


class Consulta:
    def __init__(self, caminho):
        self.pasta = Path(caminho).absolute().parent
        self.leitura = banco_leitura(caminho)
        self.db = self.leitura.__enter__()

    def listar(self):
        return listar_tarefas(self.db, self.pasta)

    def fechar(self):
        self.leitura.__exit__(None, None, None)


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
            tarefas = consulta.listar()
            estados = {t['id']: t['status'] for t in tarefas}
            for tarefa in tarefas:
                spec = tarefa['especificacao']
                consumo = consumo_tarefa(consulta.db, tarefa['id'])
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
            resultado['provedores'] = listar_provedores(consulta.db)
        except (sqlite3.Error, OSError, ValueError, KeyError, TypeError) as erro:
            resultado['erros'].append(f'provedores: {type(erro).__name__}')
        finally:
            if consulta is not None:
                consulta.fechar()
    return resultado
