#!/usr/bin/env bash
# Acrescenta o atalho Samburá junto ao menu sem reformatar a cópia pessoal.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; nada a migrar"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
origem="$(dirname "${BASH_SOURCE[0]}")/../waybar/config.jsonc"
[[ -f "$origem" ]] || origem="$(dirname "${BASH_SOURCE[0]}")/../shell/waybar/config.jsonc"
python3 - "$alvo" "$novo" "$origem" <<'PY'
import json
from pathlib import Path
import re
import sys

# Posições dos tokens preservam comentários, espaços e comandos pessoais.
padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'

def ler(texto):
    tokens = [m for m in re.finditer(padrao, texto)
              if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
    limpo = ''.join(t[0] for i, t in enumerate(tokens)
                    if not (t[0] == ',' and i + 1 < len(tokens)
                            and tokens[i + 1][0] in ('}', ']')))
    return tokens, json.loads(limpo)

texto = Path(sys.argv[1]).read_text()
tokens, dados = ler(texto)
_, padrao_barra = ler(Path(sys.argv[3]).read_text())
modulo = 'custom/sambura'
definicao = json.dumps(padrao_barra[modulo], ensure_ascii=False, indent=2)
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
if not isinstance(dados, (dict, list)):
    raise ValueError('configuração da barra precisa ser objeto ou lista')
edicoes = []
for raiz in raizes:
    campos = {}
    i = raiz + 1
    while i < fins[raiz]:
        if tokens[i][0] == ',':
            i += 1
            continue
        chave = json.loads(tokens[i][0])
        inicio = i + 2
        fim = fins.get(inicio, inicio)
        campos[chave] = (inicio, fim)
        i = fim + 1
    listas = [campos[c] for c in ('modules-left', 'modules-center', 'modules-right')
              if c in campos and tokens[campos[c][0]][0] == '[']
    presente = any(any(t[0] == json.dumps(modulo) for t in tokens[a:b])
                   for a, b in listas)
    menu = next((t for a, b in listas for t in tokens[a:b]
                 if t[0] == '"custom/menu"'), None)
    if not presente and menu is None:
        continue
    if not presente:
        edicoes.append((menu.end(), ', "custom/sambura"'))
    if modulo not in campos:
        ultimo = tokens[fins[raiz] - 1]
        edicoes.append((tokens[fins[raiz]].start(),
                        '\n  "custom/sambura": ' + definicao + '\n'))
        if ultimo[0] not in (',', '{'):
            edicoes.append((ultimo.end(), ','))
for posicao, valor in sorted(edicoes, key=lambda e: e[0], reverse=True):
    texto = texto[:posicao] + valor + texto[posicao:]
ler(texto)
Path(sys.argv[2]).write_text(texto)
PY
[[ "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "Samburá já configurado ou sem menu; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "atalho Samburá acrescentado: $alvo"
