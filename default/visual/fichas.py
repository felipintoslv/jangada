"""Paleta validada; contraste insuficiente usa a reserva do mesmo modo."""

import json
import os
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
PADRAO = json.loads(Path(__file__).with_name('padrao.json').read_text())
ESTADOS = {
    'dark': {'Executando': '#85baff', 'Em revisão': '#c9b6f2', 'Concluída': '#96d6a8',
             'Bloqueada': '#f2c66d', 'Falhou': '#f09d93'},
    'light': {'Executando': '#005a9c', 'Em revisão': '#65408f', 'Concluída': '#22633a',
              'Bloqueada': '#715400', 'Falhou': '#a12d2b'}}
ICONES = {'Planejada': '○', 'Pronta': '●', 'Executando': '↻', 'Em revisão': '⌕',
          'Concluída': '✓', 'Bloqueada': 'Ⅱ', 'Falhou': '×', 'Cancelada': '−'}


def contraste(a, b):
    def luminancia(cor):
        canais = [int(cor[i:i+2], 16) / 255 for i in (1, 3, 5)]
        canais = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in canais]
        return sum(v * peso for v, peso in zip(canais, (0.2126, 0.7152, 0.0722)))
    menor, maior = sorted((luminancia(a), luminancia(b)))
    return (maior + 0.05) / (menor + 0.05)


def validar(dados):
    resultado = {}
    for modo, reserva in PADRAO.items():
        cores = dados.get(modo) if isinstance(dados, dict) else None
        pares = [('texto', 'superficie'), ('texto_suave', 'superficie'),
                 ('texto', 'superficie_elevada'), ('texto_suave', 'superficie_elevada'),
                 ('primaria', 'superficie'), ('texto_primario', 'primaria'), ('atencao', 'superficie')]
        if (not isinstance(cores, dict) or any(not isinstance(cores.get(k), str)
                or not re.fullmatch('#[0-9a-fA-F]{6}', cores[k]) for k in reserva)
                or any(contraste(cores[a], cores[b]) < 4.5 for a, b in pares)
                or any(contraste(cor, cores[fundo]) < 4.5 for cor in ESTADOS[modo].values()
                       for fundo in ('superficie', 'superficie_elevada'))):
            resultado[modo] = dict(reserva)
        else:
            resultado[modo] = {k: cores[k] for k in reserva}
    return resultado


def carregar(caminho=None):
    caminho = caminho or Path(os.environ.get('XDG_CONFIG_HOME', str(Path.home() / '.config'))) / 'jangada/fichas.json'
    try:
        dados = json.loads(Path(caminho).read_text())
    except (OSError, ValueError):
        dados = {}
    return validar(dados)


if __name__ == '__main__':
    if sys.argv[1:] == ['--json']:
        print(json.dumps(carregar()))
        sys.exit(0)
    caminho = Path(sys.argv[1])
    originais = json.loads(caminho.read_text())
    dados = validar(originais)
    if dados != originais:
        caminho.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + '\n')
        print('jangada-tema: contraste insuficiente; usada paleta de reserva.', file=sys.stderr)
