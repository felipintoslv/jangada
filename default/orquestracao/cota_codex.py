"""Consulta somente metadados de cota, sem iniciar conversas ou executar ferramentas."""

import json
import math
import os
import pathlib
import select
import signal
import stat
import subprocess
import tempfile
import time


def percentual(dados, agora):
    if not isinstance(dados, dict):
        raise ValueError('resposta de cota inválida')
    grupos = dados.get('rateLimitsByLimitId')
    if grupos is not None:
        if not isinstance(grupos, dict) or 'codex' not in grupos:
            raise ValueError('grupo de consumo Codex ausente')
        grupo = grupos['codex']
    else:
        grupo = dados.get('rateLimits')
    if not isinstance(grupo, dict) or grupo.get('limitId') not in (None, 'codex'):
        raise ValueError('grupo de consumo Codex inválido')
    restantes, renovacoes = [], []
    for nome in ('primary', 'secondary'):
        janela = grupo.get(nome)
        if janela is None:
            continue
        if not isinstance(janela, dict):
            raise ValueError('janela de cota inválida')
        usado, fim = janela.get('usedPercent'), janela.get('resetsAt')
        if (type(usado) not in (int, float) or not math.isfinite(usado) or not 0 <= usado <= 100
                or type(fim) is not int or fim - agora < 1):
            raise ValueError('cota ausente, inválida ou aguardando renovação')
        restantes.append(100 - usado)
        renovacoes.append(fim)
    if not restantes:
        raise ValueError('nenhuma janela de cota confirmada')
    if grupo.get('rateLimitReachedType') is not None:
        restantes.append(0)
    return min(restantes), min(60, math.floor(min(renovacoes) - agora))


def consultar(pasta):
    casa = pathlib.Path(os.environ.get('CODEX_HOME', str(pathlib.Path.home() / '.codex')))
    # Uma cópia temporária impede que renovação de credenciais altere a sessão existente.
    fd = os.open(casa / 'auth.json', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as origem:
        if not stat.S_ISREG(os.fstat(origem.fileno()).st_mode):
            raise ValueError('autenticação do Codex não é um arquivo regular')
        autenticacao = origem.read(1024 * 1024 + 1)
    if len(autenticacao) > 1024 * 1024:
        raise ValueError('autenticação do Codex excede o limite')
    with tempfile.TemporaryDirectory(prefix='.cota-codex-', dir=pasta) as temporario:
        destino = pathlib.Path(temporario) / 'auth.json'
        with os.fdopen(os.open(destino, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), 'wb') as arquivo:
            arquivo.write(autenticacao)
        ambiente = os.environ.copy()
        ambiente.update(CODEX_HOME=temporario, JANGADA_HOOK_DESLIGADO='1')
        for chave in ('JANGADA_SESSAO', 'OPENAI_API_KEY', 'OPENAI_BASE_URL', 'CODEX_API_KEY'):
            ambiente.pop(chave, None)
        processo = subprocess.Popen(['codex', '--no-daemon', '-c',
                                     'log_dir=' + json.dumps(str(pathlib.Path(temporario) / 'log')),
                                     'app-server', '--stdio'], cwd=temporario, env=ambiente,
                                    stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
        limite = time.monotonic() + 10
        buffer, tamanho = b'', 0

        def enviar(mensagem):
            processo.stdin.write(json.dumps(mensagem).encode() + b'\n')
            processo.stdin.flush()

        def solicitar(identificador, metodo, parametros):
            nonlocal buffer, tamanho
            enviar({'id': identificador, 'method': metodo, 'params': parametros})
            while time.monotonic() < limite:
                if b'\n' in buffer:
                    linha, buffer = buffer.split(b'\n', 1)
                    resposta = json.loads(linha)
                    if not isinstance(resposta, dict):
                        raise ValueError('resposta de metadados inválida')
                    if type(resposta.get('id')) is int and resposta['id'] == identificador:
                        if 'error' in resposta or 'result' not in resposta:
                            raise ValueError('Codex recusou a consulta de metadados')
                        return resposta['result']
                elif select.select([processo.stdout], [], [], min(0.1, max(0, limite - time.monotonic())))[0]:
                    parte = os.read(processo.stdout.fileno(), 65536)
                    if not parte:
                        raise ValueError('Codex encerrou a consulta de metadados')
                    tamanho += len(parte)
                    if tamanho > 1024 * 1024:
                        raise ValueError('resposta de metadados excede o limite')
                    buffer += parte
            raise TimeoutError('Codex não respondeu em dez segundos')

        try:
            solicitar(1, 'initialize', {'clientInfo': {'name': 'jangada-cota', 'version': '1'}})
            enviar({'method': 'initialized', 'params': {}})
            return solicitar(2, 'account/rateLimits/read', {})
        finally:
            try:
                os.killpg(processo.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            processo.wait(timeout=5)
            processo.stdin.close()
            processo.stdout.close()
