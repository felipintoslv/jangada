#!/usr/bin/env python3
"""Verifica o contrato das referências documentais."""

import importlib.util
import pathlib
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.dont_write_bytecode = True
SPEC = importlib.util.spec_from_file_location("validar", RAIZ / "default/delegacao/validar.py")
VALIDAR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDAR)


class Referencias(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.fonte = pathlib.Path(self.pasta.name) / "fonte.txt"
        self.fonte.write_text("primeira\nsegunda\n")

    def test_caminho_absoluto_e_intervalo(self):
        VALIDAR.verificar(f"Resultado em {self.fonte}:1-2", [str(self.fonte)])

    def test_posicoes_inexistentes(self):
        for referencia in ("fonte.txt:0", "fonte.txt:3", "fonte.txt:1-3", "fonte.txt:2-1"):
            with self.subTest(referencia=referencia), self.assertRaises(ValueError):
                VALIDAR.verificar(referencia, [str(self.fonte)])

    def test_exige_cobertura_das_fontes(self):
        outra = pathlib.Path(self.pasta.name) / "outra.txt"
        outra.write_text("conteúdo\n")
        with self.assertRaises(ValueError):
            VALIDAR.verificar("fonte.txt:1", [str(self.fonte), str(outra)])

    def test_nome_ambiguo_nao_identifica_duas_fontes(self):
        outra = pathlib.Path(self.pasta.name) / "outra" / "fonte.txt"
        outra.parent.mkdir()
        outra.write_text("conteúdo\n")
        with self.assertRaises(ValueError):
            VALIDAR.verificar("fonte.txt:1", [str(self.fonte), str(outra)])
        VALIDAR.verificar(f"{self.fonte}:1; {outra}:1", [str(self.fonte), str(outra)])

    def test_pdf_confere_paginas(self):
        fonte = pathlib.Path(self.pasta.name) / "fonte.pdf"
        fonte.write_text("arquivo simulado")
        with patch.object(VALIDAR.subprocess, "run") as executar:
            executar.side_effect = [
                subprocess.CompletedProcess([], 0, "application/pdf\n"),
                subprocess.CompletedProcess([], 0, "primeira\fsegunda\f"),
            ]
            VALIDAR.verificar("fonte.pdf, p. 2", [str(fonte)])
            executar.side_effect = [
                subprocess.CompletedProcess([], 0, "application/pdf\n"),
                subprocess.CompletedProcess([], 0, "primeira\fsegunda\f"),
            ]
            with self.assertRaises(ValueError):
                VALIDAR.verificar("fonte.pdf, p. 3", [str(fonte)])

    def test_requisito_exige_explicacao_com_referencia(self):
        VALIDAR.verificar(
            "## Destino\nUse o modelo local para ler os documentos. fonte.txt:1",
            [str(self.fonte)], ["Destino"],
        )
        for texto in (
            "Destino: fonte.txt:1",
            "## Destino\nfonte.txt:1",
            "## Destino\nDestino: fonte.txt:1",
            "fonte.txt:1\n## Destino\nUse o modelo local para ler os documentos.",
            "## Destino\nUse o modelo local para ler os documentos. fonte.txt:1\n"
            "## Destino\nUse o modelo local para ler os documentos. fonte.txt:1",
        ):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                VALIDAR.verificar(texto, [str(self.fonte)], ["Destino"])

    def test_requisito_omitido_reprova(self):
        with self.assertRaises(ValueError):
            VALIDAR.verificar(
                "## Destino\nUse o modelo local para ler os documentos. fonte.txt:1",
                [str(self.fonte)], ["Destino", "Permissão"],
            )


if __name__ == "__main__":
    unittest.main()
