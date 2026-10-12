#!/usr/bin/env python3
"""Confere a retirada do atalho em configurações temporárias."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
ANTIGA = REPO / 'migrations/202610121200-barra-sambura.sh'
MIGRACAO = REPO / 'migrations/202610122100-retirar-barra-sambura.sh'
MODULO = 'custom/sambura'
ORIGINAL = {
    'format': 'Samburá',
    'tooltip': True,
    'tooltip-format': 'Abrir Samburá',
    'on-click': 'setsid -f "${JANGADA_PROJETOS:-$HOME/Projetos}/sambura/bin/sambura"',
}


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

    def migrar(self, simular=False, script=MIGRACAO):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        return subprocess.run(['bash', str(script)], env=ambiente,
                              capture_output=True, text=True)

    def copias(self):
        return list(self.alvo.parent.glob('config.jsonc.jangada-*.bak'))

    def conferir_migracao(self):
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        return self.alvo.read_text()

    def test_padrao_e_estilo_sem_sambura(self):
        padrao = carregar((REPO / 'shell/waybar/config.jsonc').read_text())
        self.assertNotIn(MODULO, padrao)
        for lista in ('modules-left', 'modules-center', 'modules-right'):
            self.assertNotIn(MODULO, padrao[lista])
        self.assertEqual(padrao['modules-left'], ['custom/menu', 'hyprland/workspaces',
                         'custom/agentes', 'custom/indicadores', 'hyprland/window'])
        self.assertNotIn('#custom-sambura', (REPO / 'shell/waybar/base.css').read_text())
        self.assertNotIn(MODULO, (REPO / 'shell/bin/jangada-barra').read_text())

    def test_migracao_preserva_jsonc_simula_e_repete(self):
        antes = '''{
 // custom/sambura em comentário não é um módulo
 "modules-right": ["clock", /* pessoal */ "custom/menu", "custom/sambura",],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"},
 "height": 47,
 "custom/sambura": %s,
}''' % json.dumps(ORIGINAL)
        self.alvo.write_text(antes)
        self.assertEqual(self.migrar(simular=True).returncode, 0)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])
        depois = self.conferir_migracao()
        esperado = carregar(antes)
        esperado['modules-right'].remove(MODULO)
        del esperado[MODULO]
        self.assertEqual(carregar(depois), esperado)
        for trecho in ['// custom/sambura em comentário não é um módulo',
                       '/* pessoal */', '"height": 47,',
                       '"clock": {"format": "http://exemplo//*texto*/"}',
                       '"custom/menu": {"on-click": "menu pessoal"}']:
            self.assertIn(trecho, depois)
        self.assertEqual(len(self.copias()), 1)
        self.assertEqual(self.copias()[0].read_text(), antes)
        self.assertEqual(self.conferir_migracao(), depois)
        self.assertEqual(len(self.copias()), 1)

    def test_modulos_personalizados_e_parciais_intactos(self):
        for definicao in [None, {'format': 'Meu Samburá', 'on-click': 'pessoal'},
                          dict(ORIGINAL, **{'on-click': 'pessoal'}),
                          dict(ORIGINAL, rotate=90), dict(ORIGINAL, tooltip=1)]:
            with self.subTest(definicao=definicao):
                dados = {'modules-left': ['custom/menu', MODULO, 'custom/sambura#pessoal'],
                         'group/pessoal': {'modules': [MODULO]}}
                if definicao is not None:
                    dados[MODULO] = definicao
                antes = json.dumps(dados)
                self.alvo.write_text(antes)
                self.assertEqual(self.conferir_migracao(), antes)
                self.assertEqual(self.copias(), [])

    def test_posicoes_virgulas_e_definicao_isolada(self):
        for lista in [[MODULO], [MODULO, 'clock'], ['clock', MODULO],
                      ['clock', MODULO, 'tray'], [MODULO, MODULO],
                      ['clock', MODULO, MODULO], []]:
            for campo in ('modules-left', 'modules-center', 'modules-right'):
                for primeiro in (True, False):
                    with self.subTest(lista=lista, campo=campo, primeiro=primeiro):
                        dados = {campo: lista, 'custom/sambura#pessoal': {'format': 'pessoal'}}
                        if primeiro:
                            dados = {MODULO: ORIGINAL, **dados}
                        else:
                            dados[MODULO] = ORIGINAL
                        self.alvo.write_text(json.dumps(dados))
                        depois = carregar(self.conferir_migracao())
                        del dados[MODULO]
                        dados[campo] = [item for item in lista if item != MODULO]
                        self.assertEqual(depois, dados)

    def test_sem_copia_sem_modulo_e_invalido(self):
        self.assertEqual(self.migrar().returncode, 0)
        self.assertFalse(self.alvo.exists())
        for texto in ['{"modules-left":["clock"]}', '{"modules-left": [',
                      '{"custom/sambura": {}, "custom/sambura": {}}', '[{}, 1]']:
            self.alvo.write_text(texto)
            resultado = self.migrar()
            self.assertEqual(resultado.returncode == 0, texto == '{"modules-left":["clock"]}')
            self.assertEqual(self.alvo.read_text(), texto)
            self.assertEqual(self.copias(), [])

    def test_varias_barras(self):
        pessoal = dict(ORIGINAL, **{'on-click': 'pessoal'})
        antes = [{'modules-left': ['custom/menu', MODULO, 'clock'], MODULO: ORIGINAL},
                 {'modules-center': [MODULO], MODULO: pessoal, 'position': 'bottom'},
                 {'modules-right': [MODULO]}, {'modules-right': ['tray']},
                 {'modules-left': [MODULO], 'modules-right': [MODULO], MODULO: ORIGINAL}]
        self.alvo.write_text(json.dumps(antes))
        depois = carregar(self.conferir_migracao())
        self.assertEqual(depois[0], {'modules-left': ['custom/menu', 'clock']})
        self.assertEqual(depois[1:4], antes[1:4])
        self.assertEqual(depois[4], {'modules-left': [], 'modules-right': []})
        texto = self.alvo.read_text()
        self.assertEqual(self.conferir_migracao(), texto)

    def test_migracao_antiga_pendente_com_padroes_novos(self):
        antes = '{"modules-left": ["custom/menu", "clock"], "height": 47}'
        self.alvo.write_text(antes)
        resultado = self.migrar(script=ANTIGA)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(carregar(self.alvo.read_text())[MODULO], ORIGINAL)
        self.assertEqual(carregar(self.conferir_migracao()), carregar(antes))


if __name__ == '__main__':
    unittest.main()
