#!/usr/bin/env bash
# Em 17/10/2026 a barra padrão trocou dois módulos. O custom/indicadores saiu:
# ele chamava o jangada-painel, retirado com o Monitor, e os indicadores estão
# na aba Indicadores da Central. O custom/catamara, botão do Catamarã, entrou
# logo depois do custom/menu, no lugar do antigo Samburá. Esta migração faz as
# duas trocas na cópia pessoal da barra sem reformatar o resto: comentários,
# espaços e módulos próprios ficam como estão. Só sai junto o comentário do
# custom/indicadores escrito pelo padrão antigo ou pela migração que o pôs.
# Roda de novo sem efeito.
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
SAI = 'custom/indicadores'
ENTRA = 'custom/catamara'
MENU = 'custom/menu'
LISTAS = ('modules-left', 'modules-center', 'modules-right')
# Comentários que o padrão antigo e a 202609271000-barra-indicadores.sh
# escreveram logo acima do bloco do custom/indicadores.
COMENTARIOS = [
    ['// Painel de indicadores do uso de IA. O exec só lê o cache do',
     '// jangada-painel, então roda barato; quem muda o estado (coleta, app que',
     '// sobe ou sai, erro) avisa pelo sinal 9, e o intervalo longo é só a rede de',
     '// segurança. O clique atualiza o cache e sobe o app R, o que leva segundos:',
     '// roda solto (setsid -f) para não prender a barra. O botão direito encerra o',
     '// app e libera a memória do R.'],
    ['// Painel de indicadores (jangada-painel). O exec só lê o cache; o clique',
     '// roda solto (setsid -f) para não prender a barra enquanto o app R sobe.'],
]

def ler(texto):
    tokens = [m for m in re.finditer(padrao, texto)
              if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
    limpo = ''.join(t[0] for i, t in enumerate(tokens)
                    if not (t[0] == ',' and i + 1 < len(tokens)
                            and tokens[i + 1][0] in ('}', ']')))
    return tokens, json.loads(limpo)

def nome(token):
    return json.loads(token[0]) if token[0].startswith('"') else None

def barras(texto):
    """Tokens e, para cada barra, o índice do '{', do '}' e dos campos."""
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
        saida.append((raiz, fins[raiz], campos))
    return tokens, saida

def itens_das_listas(tokens, campos):
    return [k for chave, _, inicio, fim in campos
            if chave in LISTAS and tokens[inicio][0] == '['
            for k in range(inicio + 1, fim) if tokens[k][0] != ',']

def linha_inteira(texto, inicio, fim):
    """Amplia o trecho à linha toda quando ele está sozinho na linha."""
    comeco = texto.rfind('\n', 0, inicio) + 1
    final = texto.find('\n', fim)
    final = len(texto) if final < 0 else final
    if texto[comeco:inicio].strip() or texto[fim:final].strip():
        return inicio, fim
    return comeco, min(final + 1, len(texto))

def com_comentario(texto, inicio):
    """Inclui no corte o comentário conhecido logo acima do bloco."""
    if inicio and texto[inicio - 1] != '\n':
        return inicio
    linhas = texto[:inicio].split('\n')[:-1]
    for comentario in COMENTARIOS:
        n = len(comentario)
        if [l.strip() for l in linhas[-n:]] == comentario:
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

def ultima_ocorrencia(texto):
    """Cortes da última ocorrência do custom/indicadores, ou [] quando não há."""
    tokens, lista = barras(texto)
    ocorrencias = []
    for _, _, campos in lista:
        ocorrencias += [(i, fim, True) for chave, i, _, fim in campos if chave == SAI]
        ocorrencias += [(k, k, False) for k in itens_das_listas(tokens, campos)
                        if nome(tokens[k]) == SAI]
    if not ocorrencias:
        return []
    primeiro, ultimo, bloco = max(ocorrencias)
    cortes = trecho(texto, tokens, primeiro, ultimo)
    if bloco:
        inicio, fim = cortes[-1]
        cortes[-1] = (com_comentario(texto, inicio), fim)
    return cortes

def bloco_padrao(texto):
    """Texto do bloco do custom/catamara no padrão, com o comentário de cima."""
    tokens, lista = barras(texto)
    for _, _, campos in lista:
        for chave, i, _, fim in campos:
            if chave != ENTRA:
                continue
            inicio = texto.rfind('\n', 0, tokens[i].start()) + 1
            while inicio:
                comeco = texto.rfind('\n', 0, inicio - 1) + 1
                if not texto[comeco:inicio].strip().startswith('//'):
                    break
                inicio = comeco
            return texto[inicio:tokens[fim].end()]
    return None

def acrescentar(texto, bloco):
    tokens, lista = barras(texto)
    edicoes = []
    for raiz, fim_raiz, campos in lista:
        itens = itens_das_listas(tokens, campos)
        if not any(nome(tokens[k]) == ENTRA for k in itens):
            menu = next((k for k in itens if nome(tokens[k]) == MENU), None)
            if menu is None:
                continue
            edicoes.append((tokens[menu].end(), ', "custom/catamara"'))
        if any(chave == ENTRA for chave, *_ in campos):
            continue
        definicao = next((fim for chave, _, _, fim in campos if chave == MENU), None)
        if definicao is not None and definicao + 1 < fim_raiz:
            depois = tokens[definicao + 1]
            if depois[0] == ',':
                edicoes.append((depois.end(), '\n\n' + bloco + ','))
            else:
                edicoes.append((tokens[definicao].end(), ',\n\n' + bloco))
            continue
        ultimo = tokens[fim_raiz - 1]
        edicoes.append((tokens[fim_raiz].start(), '\n' + bloco + '\n'))
        if ultimo[0] not in (',', '{'):
            edicoes.append((ultimo.end(), ','))
    for posicao, valor in sorted(edicoes, key=lambda e: e[0], reverse=True):
        texto = texto[:posicao] + valor + texto[posicao:]
    return texto

texto = Path(sys.argv[1]).read_text()
try:
    if not isinstance(ler(texto)[1], (dict, list)):
        raise ValueError('configuração da barra precisa ser objeto ou lista')
except ValueError:
    # Cópia inválida que não cita os módulos não é desta migração; falhar aqui
    # travaria as migrações seguintes.
    if 'indicadores' in texto or 'catamara' in texto:
        raise
    sys.exit(0)
# Uma ocorrência por vez: com o módulo repetido, os cortes vizinhos dividiriam
# a mesma vírgula se fossem calculados todos sobre o texto original.
while cortes := ultima_ocorrencia(texto):
    for inicio, fim in sorted(cortes, reverse=True):
        # Sem o bloco, as linhas em branco de antes e de depois ficariam juntas.
        if texto[fim - 1:fim + 1] == '\n\n' and linha_em_branco_antes(texto, inicio):
            fim += 1
        texto = texto[:inicio] + texto[fim:]
# Sem o custom/catamara no padrão, não há o que acrescentar.
bloco = bloco_padrao(Path(sys.argv[3]).read_text())
if bloco is not None:
    texto = acrescentar(texto, bloco)
_, dados = ler(texto)
for barra in dados if isinstance(dados, list) else [dados]:
    if isinstance(barra, dict) and SAI in barra:
        raise ValueError('custom/indicadores continua na barra')
Path(sys.argv[2]).write_text(texto)
PY
[[ -s "$novo" && "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "barra já com o Catamarã e sem os indicadores; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "botão do Catamarã acrescentado e indicadores retirados da barra: $alvo"
