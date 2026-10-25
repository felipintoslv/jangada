#!/usr/bin/env bash
# O botão do Catamarã saiu da barra padrão em 25/10/2026, junto com o comando
# jangada-barra-catamara e a logo. Esta migração tira o custom/catamara das
# listas de módulos e o bloco de definição da cópia pessoal da barra, sem
# reformatar o resto: comentários, espaços e módulos próprios ficam como estão.
# Só sai o bloco que chama o jangada-barra-catamara (com qualquer caminho e
# quaisquer cliques) ou o antigo cata tarefas --waybar / catamara-tarefas
# --waybar, com o comentário que o padrão punha acima dele. Outra definição
# pessoal fica, com o item da lista, e um aviso. O style.css não muda: um
# seletor de id sem módulo não tem efeito. Roda de novo sem efeito.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; nada a migrar"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
avisos="$(python3 - "$alvo" "$novo" <<'PY'
import json
from pathlib import Path
import re
import sys

# Posições dos tokens preservam comentários, espaços e comandos pessoais.
padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'
MODULO = 'custom/catamara'
LISTAS = ('modules-left', 'modules-center', 'modules-right')
# Comentário que o padrão punha logo acima do bloco.
COMENTARIO = [
    '// Botão do Catamarã, outro projeto. Mostra só a logo, que vem do base.css,',
    '// para a largura não mudar; os números ficam na dica e o estado vira classe.',
    '// Sem o Catamarã instalado, com erro ou demora dele, o comando não imprime',
    '// nada e a waybar esconde o módulo.',
]
# Só a chamada direta, com caminho opcional (também entre aspas); dentro de
# outro comando, com ; & | ou $( ), é personalização e fica.
PALAVRA = r"""\"(?:[^\"`\\$]|\$(?!\())*\"|'[^']*'|[^\s;&|<>`()'\"\\]+"""
COMANDO = re.compile(rf'\s*({PALAVRA})((?: +--[a-z]+)*)\s*')
ANTIGO = re.compile(
    r'\s*(?:[^\s;&|<>`()\'"\\]*/)?(?:cata tarefas|catamara-tarefas) --waybar\s*')

def ler(texto):
    tokens = [m for m in re.finditer(padrao, texto)
              if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
    limpo = ''.join(t[0] for i, t in enumerate(tokens)
                    if not (t[0] == ',' and i + 1 < len(tokens)
                            and tokens[i + 1][0] in ('}', ']')))
    dados = json.loads(limpo)
    if not isinstance(dados, (dict, list)):
        raise ValueError('configuração da barra precisa ser objeto ou lista')
    return tokens, dados

def nome(token):
    return json.loads(token[0]) if token[0].startswith('"') else None

def valor(tokens, inicio, fim):
    """Valor JSON dos tokens[inicio..fim], sem vírgula antes de fechar."""
    partes = tokens[inicio:fim + 1]
    return json.loads(''.join(t[0] for k, t in enumerate(partes)
                              if not (t[0] == ',' and k + 1 < len(partes)
                                      and partes[k + 1][0] in ('}', ']'))))

def barras(texto):
    """Tokens e, para cada barra, os campos (chave, índice da chave, valor)."""
    tokens, _ = ler(texto)
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
    saida = []
    for raiz in raizes:
        campos = []
        i = raiz + 1
        while i < fins[raiz]:
            if tokens[i][0] == ',':
                i += 1
                continue
            inicio = i + 2
            fim = fins.get(inicio, inicio)
            campos.append((json.loads(tokens[i][0]), i, inicio, fim))
            i = fim + 1
        saida.append(campos)
    return tokens, saida

def itens(tokens, campos):
    return [k for chave, _, inicio, fim in campos
            if chave in LISTAS and tokens[inicio][0] == '['
            for k in range(inicio + 1, fim) if tokens[k][0] != ',']

def do_catamara(definicao):
    exec_ = definicao.get('exec') if isinstance(definicao, dict) else None
    if not isinstance(exec_, str):
        return False
    chamada = COMANDO.fullmatch(exec_)
    if chamada and re.fullmatch(r'(?:.*/)?jangada-barra-catamara', chamada[1].strip('"\'')):
        return True
    # O antigo, cata tarefas --waybar ou catamara-tarefas --waybar.
    return ANTIGO.fullmatch(exec_) is not None

def barras_a_limpar(texto, avisos):
    """Índices das barras em que o botão sai: sem definição pessoal diferente."""
    tokens, lista = barras(texto)
    limpar = set()
    for n, campos in enumerate(lista):
        definicoes = [valor(tokens, inicio, fim)
                      for chave, _, inicio, fim in campos if chave == MODULO]
        # Sem definição na barra e com "include", o arquivo incluído pode ter
        # uma pessoal, que a migração não lê.
        herdada = not definicoes and any(chave == 'include' for chave, *_ in campos)
        if not herdada and all(do_catamara(d) for d in definicoes):
            limpar.add(n)
        else:
            avisos.append(f'{MODULO} pessoal mantido, confira se ainda é usado')
    return limpar

def linha_inteira(texto, inicio, fim):
    """Amplia o trecho à linha toda quando ele está sozinho na linha."""
    comeco = texto.rfind('\n', 0, inicio) + 1
    final = texto.find('\n', fim)
    final = len(texto) if final < 0 else final
    if texto[comeco:inicio].strip() or texto[fim:final].strip():
        return inicio, fim
    return comeco, min(final + 1, len(texto))

def com_comentario(texto, inicio):
    """Inclui no corte o comentário do padrão logo acima do bloco."""
    if inicio and texto[inicio - 1] != '\n':
        return inicio
    linhas = texto[:inicio].split('\n')[:-1]
    n = len(COMENTARIO)
    if [l.strip() for l in linhas[-n:]] == COMENTARIO:
        return inicio - sum(len(l) + 1 for l in linhas[-n:])
    return inicio

def trecho(texto, tokens, primeiro, ultimo):
    """Trecho do item tokens[primeiro..ultimo] com a vírgula vizinha."""
    inicio, fim = tokens[primeiro].start(), tokens[ultimo].end()
    if ultimo + 1 < len(tokens) and tokens[ultimo + 1][0] == ',':
        virgula = tokens[ultimo + 1]
        if texto[fim:virgula.start()].strip():
            return [(virgula.start(), virgula.end()), linha_inteira(texto, inicio, fim)]
        inicio, fim = linha_inteira(texto, inicio, virgula.end())
        if fim == virgula.end():
            while fim < len(texto) and texto[fim] in ' \t':
                fim += 1
        return [(inicio, fim)]
    if primeiro > 0 and tokens[primeiro - 1][0] == ',':
        virgula = tokens[primeiro - 1]
        if not texto[virgula.end():inicio].strip():
            return [(virgula.start(), fim)]
        return [(virgula.start(), virgula.end()), linha_inteira(texto, inicio, fim)]
    return [linha_inteira(texto, inicio, fim)]

def linha_em_branco_antes(texto, inicio):
    if inicio == 0 or texto[inicio - 1] != '\n':
        return False
    comeco = texto.rfind('\n', 0, inicio - 1) + 1
    return not texto[comeco:inicio - 1].strip()

def ultima_ocorrencia(texto, limpar):
    """Cortes da última ocorrência nas barras a limpar, ou [] quando não há."""
    tokens, lista = barras(texto)
    ocorrencias = []
    for n, campos in enumerate(lista):
        if n not in limpar:
            continue
        ocorrencias += [(i, fim, True) for chave, i, _, fim in campos if chave == MODULO]
        ocorrencias += [(k, k, False) for k in itens(tokens, campos)
                        if nome(tokens[k]) == MODULO]
    if not ocorrencias:
        return []
    primeiro, ultimo, bloco = max(ocorrencias)
    cortes = trecho(texto, tokens, primeiro, ultimo)
    if bloco:
        inicio, fim = cortes[-1]
        cortes[-1] = (com_comentario(texto, inicio), fim)
    return cortes

def sem_catamara(dados, limpar):
    """O que a barra deve ser depois da migração, calculado sobre os dados."""
    lista = dados if isinstance(dados, list) else [dados]
    # Como em barras(), só os objetos são barras.
    for n, barra in enumerate(b for b in lista if isinstance(b, dict)):
        if n not in limpar:
            continue
        barra.pop(MODULO, None)
        for chave in LISTAS:
            if isinstance(barra.get(chave), list):
                barra[chave] = [m for m in barra[chave] if m != MODULO]
    return dados

bruto = Path(sys.argv[1]).read_bytes()
try:
    original = texto = bruto.decode('utf-8')
    ler(texto)
except ValueError:
    # Cópia inválida (JSON ou UTF-8) que não cita o módulo não é desta
    # migração; falhar aqui travaria as migrações seguintes.
    if b'catamara' in bruto:
        raise
    sys.exit(0)
avisos = []
limpar = barras_a_limpar(texto, avisos)
# Uma ocorrência por vez: com o módulo repetido, os cortes vizinhos dividiriam
# a mesma vírgula se fossem calculados todos sobre o texto original.
while cortes := ultima_ocorrencia(texto, limpar):
    for inicio, fim in sorted(cortes, reverse=True):
        # Sem o bloco, as linhas em branco de antes e de depois ficariam juntas.
        if texto[fim - 1:fim + 1] == '\n\n' and linha_em_branco_antes(texto, inicio):
            fim += 1
        texto = texto[:inicio] + texto[fim:]
# Garantia contra apagar módulo pessoal: o resultado, lido como JSON, só pode
# diferir do original pela falta do custom/catamara das barras limpas.
if ler(texto)[1] != sem_catamara(ler(original)[1], limpar):
    raise ValueError('a migração mexeria em mais do que o custom/catamara')
Path(sys.argv[2]).write_bytes(texto.encode('utf-8'))
print('\n'.join(dict.fromkeys(avisos)))
PY
)"
[[ -z "$avisos" ]] || while IFS= read -r linha; do aviso "$linha: $alvo"; done <<<"$avisos"
[[ -s "$novo" && "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "Catamarã fora da barra; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "botão do Catamarã retirado da barra: $alvo"
