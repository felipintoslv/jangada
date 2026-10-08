"""Medições sob demanda, sem geração de modelos ou gravação de estado."""
import datetime as dt
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request

sys.dont_write_bytecode = True


class SemRedirecionar(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def numero_invalido(valor):
    raise ValueError('número JSON inválido: ' + valor)


def coletar():
    resultado = {'data': dt.datetime.now().astimezone().isoformat(timespec='seconds'),
                 'cpu_ticks': None, 'memoria_bytes': None, 'gpu': None, 'modelos_carregados': None, 'erros': []}
    try:
        ticks = [int(v) for v in Path('/proc/stat').read_text().splitlines()[0].split()[1:9]]
        if len(ticks) != 8 or any(v < 0 for v in ticks):
            raise ValueError('contadores inválidos')
        resultado['cpu_ticks'] = {'total': sum(ticks), 'ocioso': ticks[3] + ticks[4], 'fonte': '/proc/stat'}
        memoria = {linha.split(':')[0]: int(linha.split()[1]) * 1024
                   for linha in Path('/proc/meminfo').read_text().splitlines()}
        total, disponivel = memoria['MemTotal'], memoria['MemAvailable']
        if not total > 0 or not 0 <= disponivel <= total:
            raise ValueError('memória inválida')
        resultado['memoria_bytes'] = {'total': total, 'usada': total - disponivel, 'fonte': '/proc/meminfo'}
    except (OSError, ValueError, KeyError):
        resultado['erros'].append('medição de CPU ou memória indisponível')
    if shutil.which('nvidia-smi'):
        try:
            resposta = subprocess.run(['nvidia-smi', '--query-gpu=index,utilization.gpu,memory.used,memory.total',
                                       '--format=csv,noheader,nounits'], capture_output=True, text=True,
                                      timeout=2, check=True)
            placas = []
            for linha in resposta.stdout.splitlines():
                indice, carga, usada, total = [float(v.strip()) for v in linha.split(',')]
                if any(not math.isfinite(v) or v < 0 for v in (indice, carga, usada, total)) or carga > 100 or usada > total:
                    raise ValueError('medição inválida')
                placas.append({'indice': int(indice), 'uso_percentual_medido': carga,
                               'memoria_usada_mib': usada, 'memoria_total_mib': total, 'fonte': 'nvidia-smi'})
            resultado['gpu'] = placas or None
        except (ValueError, OSError, subprocess.SubprocessError):
            resultado['erros'].append('medição da GPU indisponível')
    else:
        resultado['erros'].append('nvidia-smi ausente; GPU sem medição')
    host = os.environ.get('OLLAMA_HOST', 'http://127.0.0.1:11434')
    host = host if '://' in host else 'http://' + host
    try:
        url = urllib.parse.urlsplit(host)
        if url.port is not None and not 1 <= url.port <= 65535:
            raise ValueError('porta inválida')
    except ValueError:
        resultado['erros'].append('endereço do Ollama inválido; consulta recusada')
        return resultado
    if url.hostname == '0.0.0.0' and not url.username and not url.password:
        url = url._replace(netloc='127.0.0.1' + (f':{url.port}' if url.port else ':11434'))
    if url.scheme != 'http' or url.hostname not in {'127.0.0.1', 'localhost', '::1'} or url.username or url.password:
        resultado['erros'].append('endereço do Ollama não é local; consulta recusada')
        return resultado
    try:
        abertura = urllib.request.build_opener(urllib.request.ProxyHandler({}), SemRedirecionar())
        with abertura.open(urllib.parse.urlunsplit((url.scheme, url.netloc, '/api/ps', '', '')), timeout=2) as resposta:
            bruto = resposta.read(1024 * 1024 + 1)
        if len(bruto) > 1024 * 1024:
            raise ValueError('listagem acima do limite')
        dados = json.loads(bruto, parse_constant=numero_invalido)
        modelos = dados.get('models')
        if not isinstance(modelos, list) or any(not isinstance(m, dict) for m in modelos):
            raise ValueError('listagem inválida')
        resultado['modelos_carregados'] = modelos
    except urllib.error.HTTPError as erro:
        erro.close()
        resultado['erros'].append('modelos carregados indisponíveis')
    except (OSError, ValueError, urllib.error.URLError):
        resultado['erros'].append('modelos carregados indisponíveis')
    return resultado


if __name__ == '__main__':
    print(json.dumps(coletar(), ensure_ascii=False, allow_nan=False))
