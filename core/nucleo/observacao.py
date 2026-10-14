"""Caminhos públicos para a Central acompanhar mudanças de estado."""
import json
import os
from pathlib import Path
import stat
import sys

LIMITE_CAMINHOS = 4096
LIMITE_COMPRIMENTO = 4096
LIMITE_SAIDA = 1024 * 1024


def existentes(caminho):
    atual = caminho
    while True:
        try:
            info = atual.lstat()
        except FileNotFoundError:
            if atual == atual.parent:
                raise ValueError('Não há antepassado existente para observar.')
            atual = atual.parent
            continue
        if stat.S_ISDIR(info.st_mode):
            return atual
        if atual == atual.parent:
            raise ValueError('Não há diretório existente para observar.')
        atual = atual.parent


def adicionar(caminhos, caminho):
    nome = str(caminho)
    if len(nome) > LIMITE_COMPRIMENTO or any(ord(c) < 32 for c in nome):
        return False
    caminhos.add(nome)
    if len(caminhos) > LIMITE_CAMINHOS:
        raise ValueError('A observação excedeu o limite de caminhos.')
    return True


def observar(estado):
    estado = Path(estado)
    if not estado.is_absolute() or any(ord(c) < 32 for c in str(estado)):
        raise ValueError('A pasta de estado precisa ser absoluta e válida.')
    caminhos = set()
    bases = (estado / 'agentes', estado / 'revisoes', estado / 'agentes/projetos')
    for base in bases:
        pasta = existentes(base)
        if not adicionar(caminhos, pasta):
            continue
        if pasta != base or not base.is_dir() or base.is_symlink():
            continue
        with os.scandir(base) as itens:
            for item in itens:
                if (item.name.endswith('.json') or item.name.startswith('tarefas.sqlite')) \
                        and item.is_file(follow_symlinks=False):
                    adicionar(caminhos, item.path)
        if base.name == 'projetos':
            with os.scandir(base) as projetos:
                for projeto in projetos:
                    try:
                        if len(projeto.path) > LIMITE_COMPRIMENTO or any(ord(c) < 32 for c in projeto.path):
                            continue
                        if not projeto.is_dir(follow_symlinks=False):
                            continue
                        adicionar(caminhos, projeto.path)
                        with os.scandir(projeto.path) as itens:
                            for item in itens:
                                if item.name.startswith('tarefas.sqlite') and item.is_file(follow_symlinks=False):
                                    adicionar(caminhos, item.path)
                    except (FileNotFoundError, PermissionError):
                        continue
    resposta = json.dumps({'versao': 1, 'caminhos': sorted(caminhos)}, ensure_ascii=False)
    if len(resposta.encode('utf-8')) > LIMITE_SAIDA:
        raise ValueError('A observação excedeu o limite de saída.')
    return resposta


if __name__ == '__main__':
    try:
        if len(sys.argv) != 2:
            raise ValueError('Informe a pasta de estado.')
        print(observar(sys.argv[1]))
    except (OSError, ValueError, RecursionError) as erro:
        print(f'jangada-agentes: {erro}', file=sys.stderr)
        raise SystemExit(1)
