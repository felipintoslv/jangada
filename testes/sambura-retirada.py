#!/usr/bin/env python3
"""Confere a retirada do Samburá da barra com configurações temporárias."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
MIGRACAO = REPO / 'migrations/202610171200-barra-sem-sambura.sh'
MODULO = 'custom/sambura'
BLOCO = '''  "custom/sambura": {
    "format": "Samburá",
    "tooltip": true,
    "tooltip-format": "Abrir Samburá",
    "on-click": "setsid -f \\"${JANGADA_PROJETOS:-$HOME/Projetos}/sambura/bin/sambura\\""
  },

'''


def carregar(texto):
    tokens = re.findall(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[^/" ]+', texto)
    limpo = ''.join(t for t in tokens if not t.startswith(('//', '/*')))
    return json.loads(re.sub(r',\s*([}\]])', r'\1', limpo))


class Retirada(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.tmp = Path(self.pasta.name)
        self.alvo = self.tmp / 'jangada/waybar/config.jsonc'
        self.alvo.parent.mkdir(parents=True)
        self.ambiente = dict(os.environ, XDG_CONFIG_HOME=str(self.tmp),
                             JANGADA_PATH=str(REPO), JANGADA_SIMULAR='0')
        self.padrao = (REPO / 'waybar/config.jsonc').read_text()

    def migrar(self, simular=False):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        return subprocess.run(['bash', str(MIGRACAO)], env=ambiente,
                              capture_output=True, text=True)

    def copias(self):
        return list(self.alvo.parent.glob('config.jsonc.jangada-*.bak'))

    def conferir(self, antes, esperado):
        self.alvo.write_text(antes)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.alvo.read_text(), esperado)
        self.assertEqual([c.read_text() for c in self.copias()], [antes])
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual(self.alvo.read_text(), esperado)
        self.assertEqual(len(self.copias()), 1)

    def test_padrao_sem_sambura(self):
        dados = carregar(self.padrao)
        self.assertNotIn(MODULO, dados)
        self.assertEqual(dados['modules-left'][:2], ['custom/menu', 'hyprland/workspaces'])
        self.assertNotIn('sambura', (REPO / 'waybar/base.css').read_text())
        self.assertNotIn('sambura', (REPO / 'bin/jangada-barra').read_text())

    def test_copia_do_padrao_antigo_volta_ao_padrao(self):
        antigo = self.padrao.replace('"custom/menu", "hyprland',
                                     '"custom/menu", "custom/sambura", "hyprland', 1)
        antigo = antigo.replace('  "hyprland/workspaces": {', BLOCO + '  "hyprland/workspaces": {', 1)
        self.assertIn(MODULO, carregar(antigo))
        self.conferir(antigo, self.padrao)

    def test_preserva_comentarios_e_simulacao(self):
        antes = '''{
 // custom/sambura em comentário fica
 "modules-right": ["clock", /* pessoal */ "custom/menu", "custom/sambura",],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"},
 "height": 47,
  "custom/sambura": {"format": "Meu Samburá", "on-click": "pessoal"}
}'''
        esperado = '''{
 // custom/sambura em comentário fica
 "modules-right": ["clock", /* pessoal */ "custom/menu", ],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"},
 "height": 47
}'''
        self.alvo.write_text(antes)
        self.assertEqual(self.migrar(simular=True).returncode, 0)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])
        self.conferir(antes, esperado)

    def test_posicoes_na_lista_e_no_objeto(self):
        casos = [
            ('{"modules-left": ["custom/sambura"]}', '{"modules-left": []}'),
            ('{"modules-left": ["a", "custom/sambura"]}', '{"modules-left": ["a"]}'),
            ('{"modules-left": ["a", /* x */ "custom/sambura"]}',
             '{"modules-left": ["a" /* x */ ]}'),
            ('{\n  "modules-center": [\n    "a",\n    "custom/sambura",\n    "b"\n  ]\n}',
             '{\n  "modules-center": [\n    "a",\n    "b"\n  ]\n}'),
            ('{\n  "custom/sambura": {"format": "S"},\n  "height": 1\n}',
             '{\n  "height": 1\n}'),
            ('[{"modules-left": ["custom/sambura", "a"]}, {"modules-right": ["b"]}]',
             '[{"modules-left": ["a"]}, {"modules-right": ["b"]}]'),
        ]
        for antes, esperado in casos:
            with self.subTest(antes=antes):
                for copia in self.copias():
                    copia.unlink()
                self.conferir(antes, esperado)
                carregar(esperado)

    def test_migracao_antiga_e_nova_sem_sambura(self):
        self.alvo.write_text(self.padrao)
        for migracao in [REPO / 'migrations/202610121200-barra-sambura.sh', MIGRACAO]:
            with self.subTest(migracao=migracao.name):
                resultado = subprocess.run(['bash', str(migracao)], env=self.ambiente,
                                           capture_output=True, text=True)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertIn('nada a migrar', resultado.stdout)
                self.assertEqual(self.alvo.read_text(), self.padrao)
                self.assertEqual(self.copias(), [])

    def test_sem_arquivo_sem_modulo_e_invalido(self):
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertFalse(self.alvo.exists())
        for texto, codigo in [('{"modules-left": ["clock"]} // custom/sambura', 0),
                              ('{"modules-left": ["custom/sambura"', 1)]:
            with self.subTest(texto=texto):
                self.alvo.write_text(texto)
                self.assertEqual(self.migrar().returncode != 0, bool(codigo))
                self.assertEqual(self.alvo.read_text(), texto)
                self.assertEqual(self.copias(), [])


if __name__ == '__main__':
    unittest.main()
