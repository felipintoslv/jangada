#!/usr/bin/env python3
"""Confere o atalho e a migração com configurações temporárias."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
MIGRACAO = REPO / 'migrations/202610121200-barra-sambura.sh'
MODULO = 'custom/sambura'


def carregar(texto):
    tokens = re.findall(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[^/" ]+', texto)
    limpo = ''.join(t for t in tokens if not t.startswith(('//', '/*')))
    return json.loads(re.sub(r',\s*([}\]])', r'\1', limpo))


class Sambura(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.tmp = Path(self.pasta.name)
        self.alvo = self.tmp / 'jangada/waybar/config.jsonc'
        self.alvo.parent.mkdir(parents=True)
        self.ambiente = dict(os.environ, XDG_CONFIG_HOME=str(self.tmp),
                             JANGADA_PATH=str(REPO), JANGADA_SIMULAR='0')
        waybar_cfg = REPO / 'waybar/config.jsonc' if (REPO / 'waybar/config.jsonc').exists() else REPO / 'shell/waybar/config.jsonc'
        self.padrao = carregar(waybar_cfg.read_text())

    def migrar(self, simular=False):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        return subprocess.run(['bash', str(MIGRACAO)], env=ambiente,
                              capture_output=True, text=True)

    def copias(self):
        return list(self.alvo.parent.glob('config.jsonc.jangada-*.bak'))

    def test_padrao_e_clique(self):
        self.assertEqual(self.padrao['modules-left'][:2], ['custom/menu', MODULO])
        modulo = self.padrao[MODULO]
        self.assertEqual(modulo['format'], 'Samburá')
        self.assertTrue(modulo['tooltip'])
        self.assertEqual(modulo['tooltip-format'], 'Abrir Samburá')
        comando = modulo['on-click']
        self.assertTrue(comando.startswith('setsid -f '))
        # O programa falso permanece vivo após o retorno do comando da barra.
        projetos = self.tmp / 'projetos com espaços'
        executavel = projetos / 'sambura/bin/sambura'
        executavel.parent.mkdir(parents=True)
        executavel.write_text('#!/bin/sh\ntouch "$MARCA"\nsleep 1\ntouch "$FIM"\n')
        executavel.chmod(0o755)
        marca, fim = self.tmp / 'marca', self.tmp / 'fim'
        ambiente = dict(self.ambiente, JANGADA_PROJETOS=str(projetos),
                         MARCA=str(marca), FIM=str(fim))
        subprocess.run(['sh', '-c', comando], env=ambiente, check=True, timeout=0.5,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.assertFalse(fim.exists())
        subprocess.run(['sh', '-c', 'while [ ! -f "$FIM" ]; do sleep 0.05; done'],
                       env=ambiente, check=True, timeout=3)
        self.assertTrue(marca.exists())
        # Sem projetos definidos, confira a expansão sem abrir o programa real.
        binario = self.tmp / 'bin'
        binario.mkdir()
        setsid = binario / 'setsid'
        setsid.write_text('#!/bin/sh\nprintf "%s" "$2"\n')
        setsid.chmod(0o755)
        ambiente.pop('JANGADA_PROJETOS')
        ambiente['PATH'] = str(binario) + os.pathsep + ambiente['PATH']
        resultado = subprocess.run(['sh', '-c', comando], env=ambiente, check=True,
                                   capture_output=True, text=True)
        self.assertEqual(resultado.stdout, str(Path.home() / 'Projetos/sambura/bin/sambura'))

    def test_migracao_preserva_jsonc(self):
        antes = '''{
 // custom/sambura em comentário não é um módulo
 "modules-right": ["clock", /* pessoal */ "custom/menu",],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"},
 "height": 47,
}'''
        self.alvo.write_text(antes)
        self.assertEqual(self.migrar(simular=True).returncode, 0)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        depois = self.alvo.read_text()
        dados = carregar(depois)
        esperado = carregar(antes)
        esperado['modules-right'].append(MODULO)
        esperado[MODULO] = self.padrao[MODULO]
        self.assertEqual(dados, esperado)
        self.assertIn('// custom/sambura em comentário', depois)
        self.assertIn('/* pessoal */', depois)
        self.assertEqual(len(self.copias()), 1)
        self.assertEqual(self.copias()[0].read_text(), antes)
        self.assertEqual(self.migrar().returncode, 0)
        self.assertEqual(self.alvo.read_text(), depois)
        self.assertEqual(len(self.copias()), 1)

    def test_texto_sem_simbolo_e_legibilidade(self):
        waybar_base = REPO / 'waybar/base.css' if (REPO / 'waybar/base.css').exists() else REPO / 'shell/waybar/base.css'
        css = waybar_base.read_text()
        menu = re.search(r'^#custom-menu \{([^}]+)\}', css, re.M)[1]
        sambura = re.search(r'^#custom-sambura \{([^}]+)\}', css, re.M)[1]
        self.assertIn('background-image: -gtk-recolor(url("../logo/jangada-symbolic.svg"));', menu)
        self.assertNotIn('background-', sambura)
        self.assertIn('padding: 0 8px;', sambura)
        self.assertIn('color: @primaria;', sambura)
        self.assertNotIn('font-size: 0', sambura)
        self.assertIn('#custom-sambura:hover {\n  color: @atencao;', css)
        vertical = re.search(r'window#waybar.vertical #custom-sambura \{([^}]+)\}', css)[1]
        self.assertIn('padding: 8px 0;', vertical)
        self.assertNotIn('background-', vertical)

    def test_modulo_pessoal_e_insercao_parcial(self):
        for lista, definido in [(['custom/menu'], True), ([MODULO], False),
                                (['custom/menu', MODULO], True)]:
            with self.subTest(lista=lista, definido=definido):
                dados = {'modules-left': lista}
                if definido:
                    dados[MODULO] = {'format': 'Meu Samburá', 'on-click': 'pessoal'}
                self.alvo.write_text(json.dumps(dados))
                self.assertEqual(self.migrar().returncode, 0)
                depois = carregar(self.alvo.read_text())
                self.assertEqual(depois['modules-left'].count(MODULO), 1)
                self.assertEqual(depois[MODULO], dados.get(MODULO, self.padrao[MODULO]))
                texto = self.alvo.read_text()
                self.assertEqual(self.migrar().returncode, 0)
                self.assertEqual(self.alvo.read_text(), texto)

    def test_sem_copia_sem_menu_e_invalido(self):
        self.assertEqual(self.migrar().returncode, 0)
        self.assertFalse(self.alvo.exists())
        for texto in ['{"modules-left":["clock"]}', '{"modules-left": [']:
            self.alvo.write_text(texto)
            resultado = self.migrar()
            self.assertEqual(resultado.returncode == 0, texto.endswith('}'))
            self.assertEqual(self.alvo.read_text(), texto)
            self.assertEqual(self.copias(), [])

    def test_varias_barras(self):
        antes = [{'modules-left': ['custom/menu', 'clock']},
                 {'modules-center': ['custom/menu'], 'position': 'bottom'},
                 {'modules-right': ['tray']}]
        self.alvo.write_text(json.dumps(antes))
        self.assertEqual(self.migrar().returncode, 0)
        depois = carregar(self.alvo.read_text())
        for barra, lista in zip(depois[:2], ['modules-left', 'modules-center']):
            self.assertEqual(barra[lista][:2], ['custom/menu', MODULO])
            self.assertEqual(barra[MODULO], self.padrao[MODULO])
        self.assertEqual(depois[2], antes[2])
        texto = self.alvo.read_text()
        self.assertEqual(self.migrar().returncode, 0)
        self.assertEqual(self.alvo.read_text(), texto)


if __name__ == '__main__':
    unittest.main()
