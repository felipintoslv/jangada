"""Recalcula a autonomia somente sobre metadados do cache, sem ler conversas."""

import datetime as dt
import json
import sys

import subagentes


def filtrar(dados, pedido):
    registros = dados.get('registros')
    if not isinstance(registros, dict):
        return {'erro': 'cache antigo; atualize a coleta do painel'}
    inicio = dt.date.fromisoformat(pedido['inicio'])
    fim = dt.date.fromisoformat(pedido['fim'])
    projetos = pedido.get('projetos') or []

    def dentro(item, campo):
        instante = subagentes.instante(item.get(campo))
        if instante is None:
            return False
        dia = dt.datetime.fromtimestamp(instante).astimezone().date()
        return inicio <= dia <= fim and (not projetos or item.get('projeto') in projetos)

    return subagentes.resumir(
        [s for s in registros['subagentes'] if dentro(s, 'inicio')],
        [d for d in registros['delegacoes'] if dentro(d, 'data')],
        [e for e in registros['entregas'] if dentro(e, 'data')],
        dt.datetime.now().astimezone())


if __name__ == '__main__':
    pedido = json.load(sys.stdin)
    with open(pedido['cache'], encoding='utf-8') as arquivo:
        dados = json.load(arquivo)
    print(json.dumps(filtrar(dados, pedido), ensure_ascii=False, allow_nan=False))
