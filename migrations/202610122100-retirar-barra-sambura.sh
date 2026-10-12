#!/usr/bin/env bash
# Retira o atalho da Waybar acrescentado em 202610121200-barra-sambura.sh.
# Definições personalizadas ficam intactas; o símbolo pertence ao aplicativo.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; nada a migrar"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
python3 - "$alvo" "$novo" <<'PY'
import json
from pathlib import Path
import re
import sys

padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'


def campos_unicos(pares):
    dados = {}
    for chave, valor in pares:
        if chave in dados:
            raise ValueError('chave duplicada na configuração da barra')
        dados[chave] = valor
    return dados


def ler(texto):
    tokens = [m for m in re.finditer(padrao, texto)
              if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
    limpo = ''.join(t[0] for i, t in enumerate(tokens)
                    if not (t[0] == ',' and i + 1 < len(tokens)
                            and tokens[i + 1][0] in ('}', ']')))
    return tokens, json.loads(limpo, object_pairs_hook=campos_unicos)


texto = Path(sys.argv[1]).read_text()
tokens, dados = ler(texto)
original = {
    'format': 'Samburá',
    'tooltip': True,
    'tooltip-format': 'Abrir Samburá',
    'on-click': 'setsid -f "${JANGADA_PROJETOS:-$HOME/Projetos}/sambura/bin/sambura"',
}
modulo = 'custom/sambura'
pilha = []
fins = {}
raizes = []
for i, token in enumerate(tokens):
    if token[0] in ('{', '['):
        if token[0] == '{' and (not pilha or pilha == [0] and tokens[0][0] == '['):
            raizes.append(i)
        pilha.append(i)
    elif token[0] in ('}', ']'):
        fins[pilha.pop()] = i
if not isinstance(dados, (dict, list)) or isinstance(dados, list) and any(
        not isinstance(barra, dict) for barra in dados):
    raise ValueError('configuração da barra precisa ser objeto ou lista de objetos')
remover = set()


def retirar(inicio, fim):
    remover.update(range(inicio, fim + 1))
    if tokens[fim + 1][0] == ',':
        remover.add(fim + 1)
    elif tokens[inicio - 1][0] == ',':
        remover.add(inicio - 1)


for raiz, barra in zip(raizes, [dados] if isinstance(dados, dict) else dados):
    # Igualdade serializada também distingue true de 1 e campos adicionais.
    if json.dumps(barra.get(modulo), sort_keys=True) != json.dumps(original, sort_keys=True):
        continue
    campos = {}
    i = raiz + 1
    while i < fins[raiz]:
        if tokens[i][0] == ',':
            i += 1
            continue
        inicio = i + 2
        fim = fins.get(inicio, inicio)
        campos[json.loads(tokens[i][0])] = (i, inicio, fim)
        i = fim + 1
    for chave in ('modules-left', 'modules-center', 'modules-right'):
        if chave not in campos:
            continue
        _, inicio, fim = campos[chave]
        if tokens[inicio][0] != '[':
            continue
        i = inicio + 1
        while i < fim:
            ultimo = fins.get(i, i)
            if tokens[i][0] == json.dumps(modulo):
                retirar(i, ultimo)
            i = ultimo + 1
    chave, _, fim = campos[modulo]
    retirar(chave, fim)
# Apagar só tokens mantém comentários e espaços pessoais, inclusive no módulo.
for i in sorted(remover, reverse=True):
    texto = texto[:tokens[i].start()] + texto[tokens[i].end():]
ler(texto)
Path(sys.argv[2]).write_text(texto)
PY
[[ "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "sem atalho Samburá original; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "atalho Samburá retirado: $alvo"
