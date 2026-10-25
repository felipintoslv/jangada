#!/usr/bin/env python3
"""Confere a migração que põe o Catamarã e tira os indicadores da barra."""
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
NOME = '202610172200-barra-catamara.sh'
NOME_ANTIGA = '202609271000-barra-indicadores.sh'
# A migração lê o padrão ao lado dela. O padrão atual já não tem o botão, então
# o teste monta uma árvore temporária com o padrão de 17/10/2026, que tinha.
BLOCO_PADRAO = '''  // Botão do Catamarã, outro projeto. Mostra só a logo, que vem do base.css,
  // para a largura não mudar; os números ficam na dica e o estado vira classe.
  // Sem o Catamarã instalado, com erro ou demora dele, o comando não imprime
  // nada e a waybar esconde o módulo.
  "custom/catamara": {
    "exec": "$JANGADA_PATH/bin/jangada-barra-catamara --waybar",
    "return-type": "json",
    "interval": 10,
    "format": "{}",
    "on-click": "setsid -f $JANGADA_PATH/bin/jangada-barra-catamara --web",
    "on-click-right": "setsid -f $JANGADA_PATH/bin/jangada-barra-catamara --terminal",
    "on-click-middle": "setsid -f $JANGADA_PATH/bin/jangada-barra-catamara --iniciar",
    "tooltip": true
  },

'''
INDICADORES = '''  // Painel de indicadores do uso de IA. O exec só lê o cache do
  // jangada-painel, então roda barato; quem muda o estado (coleta, app que
  // sobe ou sai, erro) avisa pelo sinal 9, e o intervalo longo é só a rede de
  // segurança. O clique atualiza o cache e sobe o app R, o que leva segundos:
  // roda solto (setsid -f) para não prender a barra. O botão direito encerra o
  // app e libera a memória do R.
  "custom/indicadores": {
    "exec": "jangada-painel --waybar",
    "return-type": "json",
    "interval": 300,
    "signal": 9,
    "format": "{}",
    "on-click": "setsid -f jangada-painel",
    "on-click-right": "jangada-painel --parar",
    "tooltip": true
  },

'''

# Definição que o próprio Catamarã punha na barra pessoal, antes do botão novo.
CATAMARA_ANTIGO = '''  "custom/catamara": {
    "exec": "$HOME/.local/bin/cata tarefas --waybar",
    "return-type": "json",
    "interval": 15,
    "signal": 11,
    "format": "{}",
    "on-click": "setsid -f $HOME/.local/bin/cata tarefas --web",
    "on-click-right": "setsid -f $JANGADA_PATH/bin/jangada-terminal --classe catamara-tarefas -e $HOME/.local/bin/cata tarefas",
    "tooltip": true
  },
'''


def carregar(texto):
    tokens = re.findall(r'//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[^/" ]+', texto)
    limpo = ''.join(t for t in tokens if not t.startswith(('//', '/*')))
    return json.loads(re.sub(r',\s*([}\]])', r'\1', limpo))


class Migracao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.tmp = Path(self.pasta.name)
        self.alvo = self.tmp / 'jangada/waybar/config.jsonc'
        self.alvo.parent.mkdir(parents=True)
        self.ambiente = dict(os.environ, XDG_CONFIG_HOME=str(self.tmp),
                             JANGADA_PATH=str(REPO), JANGADA_SIMULAR='0')
        self.raiz = self.tmp / 'repo'
        (self.raiz / 'migrations').mkdir(parents=True)
        (self.raiz / 'install').mkdir()
        (self.raiz / 'waybar').mkdir()
        shutil.copy(REPO / 'install/lib.sh', self.raiz / 'install/lib.sh')
        for nome in (NOME, NOME_ANTIGA):
            shutil.copy(REPO / 'migrations' / nome, self.raiz / 'migrations' / nome)
        atual = (REPO / 'waybar/config.jsonc').read_text()
        self.padrao = atual.replace('"custom/menu", "hyprland/workspaces"',
                                    '"custom/menu", "custom/catamara", "hyprland/workspaces"', 1)
        self.padrao = self.padrao.replace('  "hyprland/workspaces": {',
                                          BLOCO_PADRAO + '  "hyprland/workspaces": {', 1)
        (self.raiz / 'waybar/config.jsonc').write_text(self.padrao)
        self.definicao = carregar(self.padrao)['custom/catamara']

    def migrar(self, simular=False, migracao=NOME):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        return subprocess.run(['bash', str(self.raiz / 'migrations' / migracao)], env=ambiente,
                              capture_output=True, text=True)

    def copias(self):
        return list(self.alvo.parent.glob('config.jsonc.jangada-*.bak'))

    def conferir(self, antes, esperado=None):
        for copia in self.copias():
            copia.unlink()
        self.alvo.write_text(antes)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        depois = self.alvo.read_text()
        if esperado is not None:
            self.assertEqual(depois, esperado)
        self.assertEqual([c.read_text() for c in self.copias()], [antes])
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual(self.alvo.read_text(), depois)
        self.assertEqual(len(self.copias()), 1)
        return carregar(depois)

    def test_padrao_atual_nao_traz_o_botao_de_volta(self):
        # Com o padrão de hoje, sem o botão, a migração só tira os indicadores.
        shutil.copy(REPO / 'waybar/config.jsonc', self.raiz / 'waybar/config.jsonc')
        antes = self.padrao.replace('"custom/menu", "custom/catamara", "hyprland/workspaces", "custom/agentes",',
                                    '"custom/menu", "hyprland/workspaces", "custom/agentes", "custom/indicadores",', 1)
        antes = re.sub(r'  // Botão do Catamarã.*?\n  \},\n\n', '', antes, count=1, flags=re.S)
        antes = antes.replace('  // Título da janela', INDICADORES + '  // Título da janela', 1)
        self.assertIn('custom/indicadores', carregar(antes))
        self.alvo.write_text(antes)
        self.assertEqual(self.migrar().returncode, 0)
        self.assertEqual(self.alvo.read_text(), (REPO / 'waybar/config.jsonc').read_text())

    def test_padrao_novo(self):
        dados = carregar(self.padrao)
        self.assertNotIn('custom/indicadores', dados)
        self.assertEqual(dados['modules-left'][:3],
                         ['custom/menu', 'custom/catamara', 'hyprland/workspaces'])

    def test_padrao_antigo_vira_o_novo(self):
        antigo = self.padrao.replace('"custom/menu", "custom/catamara", "hyprland/workspaces", "custom/agentes",',
                                     '"custom/menu", "hyprland/workspaces", "custom/agentes", "custom/indicadores",', 1)
        antigo = re.sub(r'  // Botão do Catamarã.*?\n  \},\n\n', '', antigo, count=1, flags=re.S)
        antigo = antigo.replace('  // Título da janela', INDICADORES + '  // Título da janela', 1)
        self.assertIn('custom/indicadores', carregar(antigo))
        self.assertNotIn('custom/catamara', carregar(antigo))
        self.conferir(antigo, self.padrao)

    def test_migracao_antiga_desfeita(self):
        # A de 27/09 ainda põe o módulo onde ele falta; esta tira, e a ordem
        # dos nomes faz esta rodar depois.
        self.alvo.write_text(self.padrao)
        resultado = self.migrar(migracao=NOME_ANTIGA)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('custom/indicadores', carregar(self.alvo.read_text()))
        for copia in self.copias():
            copia.unlink()
        self.conferir(self.alvo.read_text(), self.padrao)

    def test_simulacao_e_comentarios(self):
        antes = '''{
 // custom/indicadores em comentário fica
 // comentário pessoal do módulo
 "custom/indicadores": {"exec": "pessoal"},
 "modules-right": ["clock", /* pessoal */ "custom/menu", "custom/indicadores",],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"}, // fim do menu
 "height": 47
}'''
        self.alvo.write_text(antes)
        self.assertEqual(self.migrar(simular=True).returncode, 0)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])
        dados = self.conferir(antes)
        texto = self.alvo.read_text()
        for trecho in ('// custom/indicadores em comentário fica',
                       '// comentário pessoal do módulo', '/* pessoal */',
                       '// fim do menu', '"menu pessoal"', 'http://exemplo//*texto*/'):
            self.assertIn(trecho, texto)
        self.assertEqual(dados['modules-right'], ['clock', 'custom/menu', 'custom/catamara'])
        self.assertEqual(dados['custom/catamara'], self.definicao)
        self.assertNotIn('custom/indicadores', dados)
        self.assertEqual(dados['height'], 47)

    def test_posicoes(self):
        d = self.definicao
        casos = [
            ('{"modules-left": ["custom/menu"]}',
             {'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d}),
            ('{"modules-left": ["custom/indicadores", "custom/menu", "custom/indicadores"]}',
             {'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d}),
            ('{"modules-left": ["custom\\/menu", "custom\\u002findicadores"], '
             '"custom\\/indicadores": {"exec": "x"}}',
             {'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d}),
            ('{"modules-left": ["custom/menu", "custom/menu"], "custom/menu": {"format": "M"}}',
             {'modules-left': ['custom/menu', 'custom/catamara', 'custom/menu'],
              'custom/menu': {'format': 'M'}, 'custom/catamara': d}),
            ('{"modules-left": ["custom/menu"], "modules-right": ["custom/menu"]}',
             {'modules-left': ['custom/menu', 'custom/catamara'],
              'modules-right': ['custom/menu'], 'custom/catamara': d}),
            ('{"custom/menu": {"format": "M"}, "modules-left": ["custom/menu"],}',
             {'modules-left': ['custom/menu', 'custom/catamara'],
              'custom/menu': {'format': 'M'}, 'custom/catamara': d}),
            ('{"modules-left": ["custom/menu"], "custom/catamara": {"format": "meu"}}',
             {'modules-left': ['custom/menu', 'custom/catamara'],
              'custom/catamara': {'format': 'meu'}}),
            ('{"modules-left": ["custom/catamara", "clock", "custom/indicadores"]}',
             {'modules-left': ['custom/catamara', 'clock'], 'custom/catamara': d}),
            ('{\n  "modules-center": [\n    "custom/menu",\n    "custom/indicadores",\n'
             '    "b"\n  ]\n}',
             {'modules-center': ['custom/menu', 'custom/catamara', 'b'], 'custom/catamara': d}),
            ('[{"modules-left": ["custom/menu", "custom/indicadores"]}, {"modules-right": ["b"]}]',
             [{'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d},
              {'modules-right': ['b']}]),
            ('{"modules-left": ["clock", "custom/indicadores"], "custom/indicadores": {}}',
             {'modules-left': ['clock']}),
        ]
        for antes, esperado in casos:
            with self.subTest(antes=antes):
                self.assertEqual(self.conferir(antes), esperado)

    def antigo_do_catamara(self):
        antigo = self.padrao.replace(
            '"custom/menu", "custom/catamara", "hyprland/workspaces", "custom/agentes",',
            '"custom/menu", "hyprland/workspaces", "custom/agentes", "custom/indicadores", '
            '"custom/catamara",', 1)
        antigo = re.sub(r'  // Botão do Catamarã.*?\n  \},\n', CATAMARA_ANTIGO, antigo,
                        count=1, flags=re.S)
        return antigo.replace('  // Título da janela', INDICADORES + '  // Título da janela', 1)

    def test_catamara_antigo_vai_para_o_lugar_novo(self):
        antigo = self.antigo_do_catamara()
        self.assertIn('cata tarefas --waybar', antigo)
        self.conferir(antigo, self.padrao)

    def test_catamara_antigo_em_lista_de_uma_linha_por_item(self):
        antes = '''{
  "modules-left": [
    "custom/menu",
    "hyprland/workspaces",
    // pessoal
    "custom/indicadores",
    "custom/catamara"
  ],
  "custom/catamara": {"exec": "catamara-tarefas --waybar"}
}'''
        self.conferir(antes)
        texto = self.alvo.read_text()
        self.assertIn('[\n    "custom/menu",\n    "custom/catamara",\n    "hyprland/workspaces"\n'
                      '    // pessoal\n  ],\n  // Botão do Catamarã', texto)
        dados = carregar(texto)
        self.assertEqual(dados['custom/catamara'], self.definicao)

    def test_catamara_pessoal_desconhecido_fica_com_aviso(self):
        antes = self.antigo_do_catamara().replace('cata tarefas --waybar', 'meu-catamara --waybar')
        self.alvo.write_text(antes)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('custom/catamara pessoal mantido', resultado.stderr)
        dados = carregar(self.alvo.read_text())
        self.assertEqual(dados['modules-left'][:3],
                         ['custom/menu', 'custom/catamara', 'hyprland/workspaces'])
        self.assertEqual(dados['custom/catamara']['exec'], '$HOME/.local/bin/meu-catamara --waybar')
        self.assertNotIn('custom/indicadores', dados)
        depois = self.alvo.read_text()
        resultado = self.migrar()
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual(self.alvo.read_text(), depois)

    def test_catamara_com_exec_composto_fica(self):
        for exec_ in ('jangada-barra-catamara --waybar; cata tarefas --waybar',
                      'echo cata tarefas --waybar',
                      'meu-comando; cata tarefas --waybar',
                      'cata tarefas --waybar && meu-comando',
                      'x;/bin/cata tarefas --waybar'):
            with self.subTest(exec_=exec_):
                antes = json.dumps({'custom/catamara': {'exec': exec_}})
                self.alvo.write_text(antes)
                resultado = self.migrar()
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
                self.assertIn('custom/catamara pessoal mantido', resultado.stderr)
                self.assertEqual(self.alvo.read_text(), antes)
                self.assertEqual(self.copias(), [])

    def test_catamara_ja_no_lugar_sem_aviso(self):
        self.alvo.write_text(self.padrao)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertNotIn('mantido', resultado.stderr)
        self.assertEqual(self.alvo.read_text(), self.padrao)

    def test_catamara_movido(self):
        d = self.definicao
        casos = [
            ('{"modules-left": ["custom/catamara", "custom/menu"]}',
             {'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d}),
            ('{"modules-left": ["custom/menu", "a", "custom/catamara", "b", "custom/catamara"]}',
             {'modules-left': ['custom/menu', 'custom/catamara', 'a', 'b', 'custom/catamara'],
              'custom/catamara': d}),
            ('{"modules-left": ["custom/menu",], "modules-right": ["custom\\/catamara"],'
             ' "custom\\/catamara": {"exec": "cata tarefas --waybar"}}',
             {'modules-left': ['custom/menu', 'custom/catamara'], 'modules-right': [],
              'custom/catamara': d}),
            ('{"modules-left": ["custom/menu", "x"], "custom/catamara": {"exec": "cata tarefas --waybar"},'
             ' "custom/catamara": {"exec": "catamara-tarefas --waybar"}}',
             {'modules-left': ['custom/menu', 'custom/catamara', 'x'], 'custom/catamara': d}),
            ('{"modules-left": ["x", "custom/catamara"], "custom/catamara": {"exec": "cata tarefas --waybar"}}',
             {'modules-left': ['x', 'custom/catamara'], 'custom/catamara': d}),
            ('[{"modules-left": ["custom/menu", "custom/indicadores", "custom/catamara"]},'
             ' {"modules-left": ["custom/catamara", "custom/menu"],'
             ' "custom/catamara": {"exec": "/x/cata tarefas --waybar"}}]',
             [{'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d},
              {'modules-left': ['custom/menu', 'custom/catamara'], 'custom/catamara': d}]),
        ]
        for antes, esperado in casos:
            with self.subTest(antes=antes):
                self.assertEqual(self.conferir(antes), esperado)

    def test_sem_arquivo_sem_modulos_e_invalido(self):
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertFalse(self.alvo.exists())
        for texto, falha in [('{"modules-left": ["clock"]} // custom/indicadores', False),
                             ('{"modules-left": ["custom/catamara"], "custom/catamara": {}}', False),
                             ('{"modules-left": ["clock"', False),
                             ('42', False),
                             ('{"modules-left": ["custom/indicadores"', True),
                             ('{"modules-left": ["custom/catamara"', True)]:
            with self.subTest(texto=texto):
                self.alvo.write_text(texto)
                self.assertEqual(self.migrar().returncode != 0, falha)
                self.assertEqual(self.alvo.read_text(), texto)
                self.assertEqual(self.copias(), [])


if __name__ == '__main__':
    unittest.main()
