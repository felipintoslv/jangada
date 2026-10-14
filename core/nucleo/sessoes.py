"""Consulta de apresentação de sessões, sem escrita nem dependência gráfica."""

import html
import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import sys
import time

LIMITE = 1024 * 1024
TEXTO_MAX = 16000
NOME = re.compile(r'[A-Za-z0-9_.-]+')
CAMPOS = ('estado', 'dir', 'atualizado', 'ramo', 'tarefa', 'agente',
          'raiz', 'mensagem', 'desde', 'coordenador', 'revisor')


def nome_valido(nome):
    return bool(NOME.fullmatch(nome)) and nome not in ('.', '..') and len(nome) <= 255


def eh_sessao(nome):
    return (nome.endswith('.json') and not nome.startswith(('revisao-', 'delegacao-'))
            and not re.fullmatch(r'validacao-.+-r[0-9]+\.contexto\.json', nome))


def registro(pasta_fd, nome):
    try:
        fd = os.open(nome + '.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                     dir_fd=pasta_fd)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, 'rb') as arquivo:
        info = os.fstat(arquivo.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_size > LIMITE:
            raise ValueError('Registro deve ser regular e ter no máximo 1 MiB.')
        bruto = arquivo.read(LIMITE + 1)
    if len(bruto) > LIMITE:
        raise ValueError('Registro excedeu 1 MiB.')
    dados = json.loads(bruto)
    if not isinstance(dados, dict):
        raise ValueError('Registro deve ser objeto JSON.')
    for campo in CAMPOS:
        valor = dados.get(campo)
        if valor is not None and (not isinstance(valor, str) or len(valor) > TEXTO_MAX):
            raise ValueError('Campo de apresentação inválido: ' + campo)
    pid = dados.get('pid')
    if pid is not None and (type(pid) is not int or pid <= 0 or pid > 2147483647):
        raise ValueError('PID inválido.')
    return dados


def vencido(quando, horas):
    if not quando:
        return True
    comando = shutil.which('gdate') or shutil.which('date')
    resultado = subprocess.run([comando, '-d', quando, '+%s'], capture_output=True,
                               timeout=2, check=False)
    try:
        marca = int(resultado.stdout) if resultado.returncode == 0 else None
    except ValueError:
        marca = None
    return marca is None or int(time.time()) - marca > horas * 3600


def pid_vivo(pid):
    if pid is None:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def selecionar(pasta, vivas, horas):
    if any(not nome_valido(s) for s in vivas):
        raise ValueError('Nome de sessão inválido.')
    try:
        pasta_fd = os.open(pasta, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    except FileNotFoundError:
        pasta_fd = None
    try:
        nomes = []
        if pasta_fd is not None:
            with os.scandir(pasta_fd) as entradas:
                for entrada in entradas:
                    if eh_sessao(entrada.name):
                        nomes.append(entrada.name[:-5])
                        if len(nomes) > 4096:
                            raise ValueError('Consulta excedeu 4096 registros.')
        nomes = list(dict.fromkeys(vivas + sorted(nomes)))
        if len(nomes) > 4096:
            raise ValueError('Consulta excedeu 4096 sessões.')
        sessoes = []
        tamanho = 0
        for nome in nomes:
            if not nome_valido(nome):
                raise ValueError('Nome de sessão inválido.')
            dados = registro(pasta_fd, nome) if pasta_fd is not None else {}
            s = {campo: dados.get(campo) or '' for campo in CAMPOS}
            s['nome'] = nome
            s['estado'] = s['estado'] or 'ativo'
            estado = s['estado']
            pid = dados.get('pid')
            final = estado in ('concluido', 'aguardando')
            if nome not in vivas and not pid_vivo(pid):
                guardado = ((final or estado == 'interrompido') and
                            not vencido(s['atualizado'], horas if final else 168))
                if not guardado:
                    restauravel = (pid is None and estado != 'interrompido' and not final
                                   and s['agente'] and s['agente'] != 'par' and s['dir']
                                   and Path(s['dir']).is_dir())
                    if not restauravel:
                        continue
                    s['estado'] = 'interrompido'
            s['raiz'] = s['raiz'] or s['dir']
            s['projeto'] = Path(s['raiz']).name or 'Sem projeto'
            s['agente'] = s['agente'] or 'Não informado'
            s['coordenador'] = s['coordenador'] or 'dono'
            s['revisor'] = s['revisor'] or 'Não informado'
            tamanho += len(json.dumps(s, ensure_ascii=False).encode('utf-8'))
            if tamanho > LIMITE:
                raise ValueError('Resposta excedeu 1 MiB.')
            sessoes.append(s)
        return sessoes
    finally:
        if pasta_fd is not None:
            os.close(pasta_fd)


def emitir(sessoes, formato):
    if formato == 'json':
        saida = json.dumps({'versao': 1, 'sessoes': sessoes}, ensure_ascii=False) + '\n'
    else:
        linhas = []
        for s in sessoes:
            tarefa = html.escape(s['tarefa'].split('\n')[0], quote=False)
            if len(tarefa) > 50:
                tarefa = tarefa[:47] + '...'
            campos = [s['estado'], s['nome'], s['dir'], s['atualizado'],
                      html.escape(s['ramo'], quote=False), tarefa]
            linhas.append('\t'.join(re.sub(r'[\t\n\x1f]', ' ', c) for c in campos))
        saida = ''.join(linha + '\n' for linha in linhas)
    if len(saida.encode('utf-8')) > LIMITE:
        raise ValueError('Resposta excedeu 1 MiB.')
    sys.stdout.write(saida)


if __name__ == '__main__':
    try:
        bruto = sys.stdin.buffer.read(LIMITE + 1)
        if len(bruto) > LIMITE:
            raise ValueError('Lista de sessões vivas excedeu 1 MiB.')
        vivas = list(dict.fromkeys(bruto.decode('utf-8').splitlines()))
        horas = int(sys.argv[2])
        if horas < 0:
            raise ValueError('Retenção inválida.')
        emitir(selecionar(sys.argv[1], vivas, horas), sys.argv[3])
    except (OSError, ValueError, RecursionError, subprocess.SubprocessError) as erro:
        sys.stderr.write('Não foi possível consultar sessões: ' + str(erro) + '\n')
        sys.exit(1)
