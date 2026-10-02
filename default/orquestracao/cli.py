"""Comandos da fila do jangada. Os arquivos de plano contêm somente dados."""

import argparse
import hashlib
import json
import os
import pathlib
import sqlite3
import sys

sys.dont_write_bytecode = True
from estado import Estado


def especificacoes(caminho, projeto):
    tarefas = json.loads(pathlib.Path(caminho).read_text())
    if not isinstance(tarefas, list):
        raise ValueError('plano deve ser uma lista de tarefas')
    resultado = []
    for original in tarefas:
        if not isinstance(original, dict) or not isinstance(original.get('fontes'), list):
            raise ValueError('tarefa deve informar fontes')
        tarefa = dict(original)
        fontes, hashes = [], {}
        for nome in tarefa['fontes']:
            if not isinstance(nome, str):
                raise ValueError('fonte deve ser um caminho')
            fonte = (projeto / nome).resolve()
            if not fonte.is_relative_to(projeto) or not fonte.is_file():
                raise ValueError(f'fonte ausente ou fora do projeto: {nome}')
            fontes.append(str(fonte))
            hashes[str(fonte)] = hashlib.sha256(fonte.read_bytes()).hexdigest()
        tarefa['fontes'] = fontes
        tarefa['hashes_fontes'] = hashes
        resultado.append(tarefa)
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    comandos = parser.add_subparsers(dest='comando', required=True)
    fila = comandos.add_parser('fila', help='inspeciona ou importa tarefas')
    fila.add_argument('--importar', type=pathlib.Path)
    fila.add_argument('--json', action='store_true')
    tarefa = comandos.add_parser('task', help='altera somente o estado da tarefa')
    tarefa.add_argument('id')
    tarefa.add_argument('acao', choices=['pausar', 'retomar', 'cancelar', 'repetir', 'revisar'])
    tarefa.add_argument('--parecer')
    decisao = tarefa.add_mutually_exclusive_group()
    decisao.add_argument('--aprovar', action='store_true')
    decisao.add_argument('--reprovar', action='store_true')
    args = parser.parse_args()
    projeto = pathlib.Path.cwd().resolve()
    if not projeto.is_dir():
        raise ValueError('projeto não existe')
    chave = hashlib.sha256(str(projeto).encode()).hexdigest()
    pasta = pathlib.Path(os.environ['JANGADA_ESTADO']) / 'agentes/projetos' / chave
    estado = Estado(pasta)
    try:
        if args.comando == 'fila':
            if args.importar:
                estado.importar(especificacoes(args.importar, projeto))
            tarefas = estado.listar()
            if args.json:
                print(json.dumps({'projeto': str(projeto), 'estado': str(pasta), 'tarefas': tarefas}, ensure_ascii=False))
            else:
                for item in tarefas:
                    spec = item['especificacao']
                    print(f'{item["id"]}\t{item["status"]}\t{spec["capacidade"]}\t{item["tentativas"]} tentativa(s)')
        else:
            if args.acao == 'revisar':
                if not args.parecer or not (args.aprovar or args.reprovar):
                    raise ValueError('revisar exige --parecer e --aprovar ou --reprovar')
                estado.revisar(args.id, args.parecer, args.aprovar)
            else:
                if args.parecer or args.aprovar or args.reprovar:
                    raise ValueError('parecer e decisão só são usados na revisão')
                estado.alterar(args.id, args.acao)
            print(json.dumps({'tarefa': args.id, 'acao': args.acao}, ensure_ascii=False))
    finally:
        estado.fechar()


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, sqlite3.Error) as erro:
        print(f'jangada-fila: {erro}', file=sys.stderr)
        sys.exit(2)
