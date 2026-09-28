"""Hook PreToolUse do subagente leitor do Claude, chamado pelo
bin/jangada-hook-leitor: só deixa passar comandos de leitura no Bash.

Recebe o JSON do evento pela entrada padrão. Sai com 0 para liberar e com 2,
e o motivo na saída de erro, para recusar.

O leitor lê documentos de fora, que podem trazer injeção de prompt; a regra
"não grave" do texto não basta. Vale uma lista de comandos que não gravam
nem executam outro programa, ligados só por "|". Redirecionamento, ";", "&",
substituição de comando e variáveis são recusados. O pdftotext só escreve
na saída padrão ("-" como último argumento).
"""

import json
import re
import shlex
import sys

PERMITIDOS = {"pdftotext", "pdfinfo", "grep", "head", "tail", "wc", "cut", "tr", "cat", "ls"}
# $( ${ $VAR e crase executam ou expandem; "$'" (texto) e "$" no fim de um
# padrão do grep ficam de fora da recusa.
EXPANSAO = re.compile(r"`|\$[({A-Za-z0-9_@*#?!$-]")


def recusar(motivo):
    print(f"jangada-hook-leitor: {motivo}. O leitor só roda comandos de leitura "
          f"({', '.join(sorted(PERMITIDOS))}), ligados por '|'.", file=sys.stderr)
    sys.exit(2)


def main():
    try:
        evento = json.load(sys.stdin)
    except ValueError:
        recusar("evento ilegível")
    if not isinstance(evento, dict):
        recusar("evento ilegível")
    if evento.get("tool_name") != "Bash":
        return
    comando = (evento.get("tool_input") or {}).get("command")
    if not isinstance(comando, str) or not comando.strip():
        recusar("comando vazio")
    if "\n" in comando or "\\" in comando:
        recusar("quebra de linha ou barra invertida no comando")
    if EXPANSAO.search(comando):
        recusar("substituição de comando ou variável")
    try:
        lexer = shlex.shlex(comando, posix=True, punctuation_chars=True)
        lexer.whitespace_split = True
        partes = list(lexer)
    except ValueError:
        recusar("aspas sem fechar")
    trechos = [[]]
    for p in partes:
        if p == "|":
            trechos.append([])
        elif p and set(p) <= set("();<>|&"):
            recusar(f"'{p}' não é permitido")
        else:
            trechos[-1].append(p)
    for t in trechos:
        if not t:
            recusar("trecho vazio entre '|'")
        if t[0] not in PERMITIDOS:
            recusar(f"'{t[0]}' não está na lista")
        if t[0] == "pdftotext" and t[-1] != "-":
            recusar("o pdftotext precisa de '-' como último argumento (saída padrão)")


main()
