#!/usr/bin/env python3
"""Confere extração tipada, referências por trecho e preservação entre partes."""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "default/delegacao"))
import extracao


class Extracao(unittest.TestCase):
    def setUp(self):
        self.campos = extracao.campos_de(["prazo:inteiro", "reenvio:booleano", "responsavel:texto"])
        self.fonte = "/fontes/a.txt:1: O prazo é 7 dias.\n/fontes/a.txt:2: Reenvio não autorizado.\n"
        self.resposta = {"prazo": {"valor": 7, "referencia": "a.txt:1"},
                         "reenvio": {"valor": False, "referencia": "a.txt:2"},
                         "responsavel": {"valor": None, "referencia": None}}

    def conferir(self):
        return extracao.conferir(json.dumps(self.resposta), self.fonte, self.campos)

    def test_declaracoes_invalidas_e_repetidas(self):
        for campos in ([], ["prazo:numero"], ["-nome:texto"], ["a:texto", "a:inteiro"]):
            with self.subTest(campos=campos), self.assertRaises(ValueError):
                extracao.campos_de(campos)

    def test_referencia_normalizada_e_ausencia(self):
        resposta = self.conferir()
        self.assertEqual(resposta["prazo"]["referencia"], "/fontes/a.txt:1")
        self.assertEqual(resposta["responsavel"], {"valor": None, "referencia": None})

    def test_referencia_fora_da_parte(self):
        for referencia in ("a.txt:3", "/outra/a.txt:1", None):
            self.resposta["prazo"]["referencia"] = referencia
            with self.subTest(referencia=referencia), self.assertRaises(ValueError):
                self.conferir()

    def test_nome_ambiguo_exige_caminho(self):
        self.fonte += "/outra/a.txt:1: Outro prazo.\n"
        with self.assertRaises(ValueError):
            self.conferir()
        self.resposta["prazo"]["referencia"] = "/fontes/a.txt:1"
        self.resposta["reenvio"]["referencia"] = "/fontes/a.txt:2"
        self.conferir()

    def test_pagina_de_pdf_precisa_aparecer_na_parte(self):
        self.fonte = "/fontes/a.pdf, p. 2:1: Prazo.\n/fontes/a.pdf, p. 2:2: Reenvio.\n"
        for fato in ("prazo", "reenvio"):
            self.resposta[fato]["referencia"] = "a.pdf, p. 2"
        self.assertEqual(self.conferir()["prazo"]["referencia"], "/fontes/a.pdf, p. 2")
        self.resposta["prazo"]["referencia"] = "a.pdf, p. 1"
        with self.assertRaises(ValueError):
            self.conferir()

    def test_false_e_zero_nao_sao_ausencia(self):
        self.resposta["prazo"]["valor"] = 0
        partes = [self.conferir(), {k: {"valor": None, "referencia": None} for k in self.campos}]
        resultado = extracao.consolidar(partes, self.campos)
        self.assertIs(resultado["reenvio"]["valor"], False)
        self.assertEqual(resultado["prazo"]["valor"], 0)

    def test_tipo_exato_e_par_nulo(self):
        for nome, valor, ref in (("reenvio", 0, "a.txt:2"), ("prazo", False, "a.txt:1"),
                                 ("responsavel", None, "a.txt:1"), ("responsavel", "Helena", None),
                                 ("responsavel", "", "a.txt:1"), ("responsavel", " \t\n", "a.txt:1")):
            original = self.resposta[nome]
            self.resposta[nome] = {"valor": valor, "referencia": ref}
            with self.subTest(nome=nome, valor=valor), self.assertRaises(ValueError):
                self.conferir()
            self.resposta[nome] = original

    def test_chaves_omitidas_extras_e_repetidas(self):
        for texto in ('{}', '[]', '{"prazo": {}, "prazo": {}}',
                      json.dumps({**self.resposta, "extra": {}})):
            with self.subTest(texto=texto), self.assertRaises(ValueError):
                extracao.conferir(texto, self.fonte, self.campos)

    def test_parte_posterior_completa_ausencia_sem_apagar_fatos(self):
        primeira = self.conferir()
        segunda = {k: {"valor": None, "referencia": None} for k in self.campos}
        segunda["responsavel"] = {"valor": "Helena", "referencia": "/fontes/a.txt:25"}
        resultado = extracao.consolidar([primeira, segunda], self.campos)
        self.assertEqual(resultado["prazo"], primeira["prazo"])
        self.assertEqual(resultado["responsavel"], segunda["responsavel"])

    def test_fatos_iguais_preservam_primeira_citacao_e_conflito_recusa(self):
        primeira = self.conferir()
        segunda = json.loads(json.dumps(primeira))
        segunda["prazo"]["referencia"] = "/fontes/a.txt:10"
        self.assertEqual(extracao.consolidar([primeira, segunda], self.campos)["prazo"], primeira["prazo"])
        segunda["prazo"]["valor"] = 8
        with self.assertRaisesRegex(ValueError, "conflitantes"):
            extracao.consolidar([primeira, segunda], self.campos)


if __name__ == "__main__":
    unittest.main()
