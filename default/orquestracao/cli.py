"""Comandos da fila do jangada. Os arquivos de plano contêm somente dados."""

import argparse
import hashlib
import json
import os
import pathlib
import sqlite3
import subprocess
import sys

sys.dont_write_bytecode = True
from estado import Estado
from executor import executar
from saude import Saude, retomar


def especificacoes(caminho, projeto):
    tarefas = json.loads(pathlib.Path(caminho).read_text(encoding='utf-8'))
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
    fila.add_argument('--projeto', type=pathlib.Path)
    fila.add_argument('--importar', type=pathlib.Path)
    fila.add_argument('--json', action='store_true')
    execucao = comandos.add_parser('executar', help='executa tarefas elegíveis sem aprová-las')
    execucao.add_argument('--projeto', type=pathlib.Path)
    execucao.add_argument('--perfil', choices=['balanced', 'quality', 'offline'], default='balanced')
    execucao.add_argument('--limite', type=int, default=1)
    execucao.add_argument('--permitir-remoto', action='store_true')
    execucao.add_argument('--permitir-codex', action='store_true')
    retomada = comandos.add_parser('retomar', help='retoma esperas com provedor disponível')
    retomada.add_argument('--projeto', type=pathlib.Path)
    retomada.add_argument('--perfil', choices=['balanced', 'quality', 'offline'], default='balanced')
    retomada.add_argument('--permitir-remoto', action='store_true')
    retomada.add_argument('--permitir-codex', action='store_true')
    retomada.add_argument('--atualizar', action='store_true')
    retomada.add_argument('--executar', action='store_true')
    retomada.add_argument('--limite', type=int, default=1)
    router = comandos.add_parser('router', help='consulta provedores de todos os projetos')
    router.add_argument('acao', choices=['status'])
    router.add_argument('--atualizar', action='store_true')
    router.add_argument('--atualizar-codex', action='store_true')
    router.add_argument('--permitir-remoto', action='store_true')
    provedor = comandos.add_parser('provedor', help='pausa ou ativa um provedor')
    provedor.add_argument('acao', choices=['pausar', 'ativar'])
    provedor.add_argument('id')
    tarefa = comandos.add_parser('task', help='altera somente o estado da tarefa')
    tarefa.add_argument('--projeto', type=pathlib.Path)
    tarefa.add_argument('id')
    tarefa.add_argument('acao', choices=['pausar', 'retomar', 'cancelar', 'repetir', 'revisar'])
    tarefa.add_argument('--parecer')
    decisao = tarefa.add_mutually_exclusive_group()
    decisao.add_argument('--aprovar', action='store_true')
    decisao.add_argument('--reprovar', action='store_true')
    args = parser.parse_args()
    raiz_estado = pathlib.Path(os.environ['JANGADA_ESTADO'])
    if args.comando in {'router', 'provedor'}:
        global_estado = Estado(raiz_estado / 'agentes/runtime', raiz=raiz_estado)
        try:
            saude = Saude(global_estado)
            if args.comando == 'provedor':
                saude.pausar(args.id, args.acao == 'pausar')
            elif args.atualizar:
                saude.atualizar(args.permitir_remoto)
            if args.comando == 'router' and args.atualizar_codex:
                saude.atualizar_codex(args.permitir_remoto)
            print(json.dumps({'provedores': saude.listar()}, ensure_ascii=False))
        finally:
            global_estado.fechar()
        return
    if args.projeto:
        projeto = args.projeto.resolve()
    else:
        git = subprocess.run(['git', '-c', 'core.fsmonitor=false', '-c', 'core.hooksPath=/dev/null',
                              'rev-parse', '--show-toplevel'], capture_output=True, text=True, check=False)
        projeto = pathlib.Path(git.stdout.strip()).resolve() if git.returncode == 0 else pathlib.Path.cwd().resolve()
    if not projeto.is_dir():
        raise ValueError('projeto não existe')
    chave = hashlib.sha256(str(projeto).encode()).hexdigest()
    pasta = pathlib.Path(os.environ['JANGADA_ESTADO']) / 'agentes/projetos' / chave
    estado = Estado(pasta, raiz=os.environ['JANGADA_ESTADO'])
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
        elif args.comando in {'executar', 'retomar'}:
            global_estado = Estado(raiz_estado / 'agentes/runtime', raiz=raiz_estado)
            try:
                saude = Saude(global_estado)
                raiz = pathlib.Path(os.environ['JANGADA_PATH'])
                retomadas, resultados = [], []
                if args.comando == 'retomar':
                    if args.atualizar:
                        saude.atualizar(args.permitir_remoto)
                        if (args.permitir_remoto and args.permitir_codex and args.perfil != 'offline'
                                and (os.environ.get('JANGADA_DELEGAR') or 'agy') == 'agy'
                                and os.environ.get('JANGADA_CODEX_ECONOMICO_MODELO')):
                            saude.atualizar_codex(True)
                    retomadas = retomar(estado, saude, raiz, os.environ['JANGADA_CONFIG'],
                                       args.perfil, args.permitir_remoto, args.permitir_codex)
                if args.comando == 'executar' or args.executar:
                    resultados = executar(estado, projeto, raiz, args.perfil,
                                          args.limite, args.permitir_remoto, saude, args.permitir_codex)
                print(json.dumps({'projeto': str(projeto), 'retomadas': retomadas,
                                  'resultados': resultados}, ensure_ascii=False))
            finally:
                global_estado.fechar()
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
    except KeyboardInterrupt:
        print('jangada-executar: execução interrompida; nenhuma outra tarefa iniciada', file=sys.stderr)
        sys.exit(130)
    except (OSError, ValueError, KeyError, sqlite3.Error) as erro:
        print(f'jangada-fila: {erro}', file=sys.stderr)
        sys.exit(2)
