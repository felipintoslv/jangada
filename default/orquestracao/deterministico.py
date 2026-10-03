"""Critérios locais de formato, sem executar instruções das fontes."""

import hashlib
import json
import math
import os
import pathlib
import stat

CAPACIDADE = 'validacao_json'


def elegivel(tarefa):
    return (tarefa['capacidade'] == CAPACIDADE and tarefa['papel'] == 'verificador'
            and tarefa['risco'] == 0 and not tarefa.get('requisitos'))


def objeto_sem_repeticoes(pares):
    objeto = {}
    for chave, valor in pares:
        if chave in objeto:
            raise ValueError('chave repetida no objeto JSON')
        objeto[chave] = valor
    return objeto


def conferir_valores(valor):
    pendentes = [(valor, 0)]
    while pendentes:
        item, profundidade = pendentes.pop()
        if profundidade > 64:
            raise ValueError('JSON excede 64 níveis de profundidade')
        if isinstance(item, float) and not math.isfinite(item):
            raise ValueError('número JSON fora do intervalo finito')
        if isinstance(item, str) and any(0xD800 <= ord(c) <= 0xDFFF for c in item):
            raise ValueError('texto JSON contém substituto Unicode isolado')
        if isinstance(item, dict):
            pendentes.extend((v, profundidade + 1) for v in item.values())
            pendentes.extend((k, profundidade + 1) for k in item)
        elif isinstance(item, list):
            pendentes.extend((v, profundidade + 1) for v in item)


def constante_invalida(_):
    raise ValueError('constante não permitida em JSON')


def conferir(tarefa):
    if not elegivel(tarefa):
        raise ValueError('conclusão automática exige validação JSON de risco zero sem requisitos adicionais')
    if len(tarefa['fontes']) > 32:
        raise ValueError('validação JSON aceita até 32 fontes')
    fontes, total = [], 0
    for nome in tarefa['fontes']:
        caminho = pathlib.Path(nome)
        descritor = os.open(caminho, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(descritor, 'rb') as arquivo:
            if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                raise ValueError('fonte JSON deve ser arquivo regular')
            bruto = arquivo.read(1024 * 1024 + 1)
        total += len(bruto)
        if len(bruto) > 1024 * 1024 or total > 4 * 1024 * 1024:
            raise ValueError('fontes JSON excedem 1 MiB por arquivo ou 4 MiB no total')
        resumo = hashlib.sha256(bruto).hexdigest()
        if resumo != tarefa.get('hashes_fontes', {}).get(nome):
            raise ValueError('fonte JSON mudou após a importação')
        try:
            valor = json.loads(bruto.decode('utf-8'), object_pairs_hook=objeto_sem_repeticoes,
                               parse_constant=constante_invalida)
            conferir_valores(valor)
        except (ValueError, UnicodeError, RecursionError) as erro:
            if isinstance(erro, json.JSONDecodeError):
                motivo = f'JSON inválido na linha {erro.lineno}, coluna {erro.colno}'
            elif isinstance(erro, UnicodeError):
                motivo = 'fonte JSON não está em UTF-8'
            elif isinstance(erro, RecursionError):
                motivo = 'JSON excede a profundidade do analisador'
            else:
                motivo = str(erro)
            raise ValueError(f'{nome}: {motivo}') from None
        fontes.append({'arquivo': nome, 'sha256': resumo, 'bytes': len(bruto)})
    return json.dumps({'task_id': tarefa['id'], 'capacidade': CAPACIDADE,
                       'criterio': 'sintaxe_json_estrita', 'resultado': 'PASS',
                       'fontes': fontes}, ensure_ascii=False, sort_keys=True, allow_nan=False)
