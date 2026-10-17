#!/usr/bin/env bash
# O Samburá foi aposentado em 17/10/2026 e o atalho saiu da barra padrão. Esta
# migração tira "custom/sambura" das listas de módulos e o bloco do módulo da
# cópia pessoal da barra, sem reformatar o resto: comentários (inclusive os que
# citam o módulo), espaços e módulos próprios ficam como estão. Roda de novo
# sem efeito.
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

# Posições dos tokens preservam comentários, espaços e comandos pessoais.
padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'
modulo = 'custom/sambura'

def ler(texto):
    tokens = [m for m in re.finditer(padrao, texto)
              if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
    limpo = ''.join(t[0] for i, t in enumerate(tokens)
                    if not (t[0] == ',' and i + 1 < len(tokens)
                            and tokens[i + 1][0] in ('}', ']')))
    return tokens, json.loads(limpo)

def eh_modulo(token):
    return token[0].startswith('"') and json.loads(token[0]) == modulo

def linha_inteira(texto, inicio, fim):
    """Amplia o trecho à linha toda quando ele está sozinho na linha."""
    comeco = texto.rfind('\n', 0, inicio) + 1
    final = texto.find('\n', fim)
    final = len(texto) if final < 0 else final
    if texto[comeco:inicio].strip() or texto[fim:final].strip():
        return inicio, fim
    return comeco, min(final + 1, len(texto))

def trecho(texto, tokens, primeiro, ultimo):
    """Trecho do item tokens[primeiro..ultimo] com a vírgula vizinha."""
    inicio, fim = tokens[primeiro].start(), tokens[ultimo].end()
    if ultimo + 1 < len(tokens) and tokens[ultimo + 1][0] == ',':
        fim = tokens[ultimo + 1].end()
        inicio, fim = linha_inteira(texto, inicio, fim)
        if fim == tokens[ultimo + 1].end():
            while fim < len(texto) and texto[fim] in ' \t':
                fim += 1
        return [(inicio, fim)]
    if primeiro > 0 and tokens[primeiro - 1][0] == ',':
        virgula = tokens[primeiro - 1]
        if not texto[virgula.end():inicio].strip():
            return [(virgula.start(), fim)]
        return [(virgula.start(), virgula.end()), linha_inteira(texto, inicio, fim)]
    return [linha_inteira(texto, inicio, fim)]

texto = Path(sys.argv[1]).read_text()
if f'"{modulo}"' not in texto:
    sys.exit(0)
tokens, dados = ler(texto)
if not isinstance(dados, (dict, list)):
    raise ValueError('configuração da barra precisa ser objeto ou lista')
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
cortes = []
for raiz in raizes:
    i = raiz + 1
    while i < fins[raiz]:
        if tokens[i][0] == ',':
            i += 1
            continue
        chave = json.loads(tokens[i][0])
        inicio = i + 2
        fim = fins.get(inicio, inicio)
        if chave == modulo:
            cortes += trecho(texto, tokens, i, fim)
        elif (chave in ('modules-left', 'modules-center', 'modules-right')
              and tokens[inicio][0] == '['):
            for k in range(inicio + 1, fim):
                if eh_modulo(tokens[k]):
                    cortes += trecho(texto, tokens, k, k)
        i = fim + 1
def linha_em_branco_antes(texto, inicio):
    if inicio == 0 or texto[inicio - 1] != '\n':
        return False
    comeco = texto.rfind('\n', 0, inicio - 1) + 1
    return not texto[comeco:inicio - 1].strip()

for inicio, fim in sorted(cortes, reverse=True):
    # Sem o bloco, as linhas em branco de antes e de depois ficariam juntas.
    if texto[fim - 1:fim + 1] == '\n\n' and linha_em_branco_antes(texto, inicio):
        fim += 1
    texto = texto[:inicio] + texto[fim:]
_, dados = ler(texto)
for barra in dados if isinstance(dados, list) else [dados]:
    if isinstance(barra, dict) and modulo in barra:
        raise ValueError('custom/sambura continua na barra')
Path(sys.argv[2]).write_text(texto)
PY
[[ -s "$novo" && "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "Samburá fora da barra; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "atalho Samburá retirado da barra: $alvo"
