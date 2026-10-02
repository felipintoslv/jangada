#!/usr/bin/env python3
"""Confere referências às fontes fornecidas, sem aprovar o conteúdo."""

import pathlib
import re
import subprocess
import sys


def verificar(texto, arquivos):
    nomes = [pathlib.Path(arquivo).name for arquivo in arquivos]
    for arquivo in arquivos:
        caminho = pathlib.Path(arquivo)
        mime = subprocess.run(
            ["file", "-b", "--mime-type", str(caminho)],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        pdf = caminho.suffix.lower() == ".pdf" or mime == "application/pdf"
        if pdf:
            fonte = subprocess.run(
                ["pdftotext", "-layout", str(caminho), "-"],
                capture_output=True, text=True, check=True,
            ).stdout
            partes = fonte.split("\f")
        else:
            fonte = caminho.read_text()
            partes = fonte.split("\n")
        if partes and partes[-1] == "":
            partes.pop()
        alternativas = [arquivo, str(caminho.resolve())]
        if nomes.count(caminho.name) == 1:
            alternativas.append(caminho.name)
        nome = "(?:" + "|".join(re.escape(a) for a in alternativas) + ")"
        localizador = r",\s*p\.\s*" if pdf else ":"
        localizador += r"(\d+)(?:[-–](\d+))?(?![\w-])"
        referencias = re.findall(r"(?<![\w/])" + nome + localizador, texto)
        if not referencias or any(
            not 1 <= int(inicio) <= int(fim or inicio) <= len(partes)
            for inicio, fim in referencias
        ):
            raise ValueError(f"fonte sem referência válida ou posição inexistente: {arquivo}")


if __name__ == "__main__":
    try:
        verificar(sys.stdin.read(), sys.argv[1:])
    except (OSError, UnicodeError, ValueError, subprocess.SubprocessError) as erro:
        sys.exit(str(erro))
