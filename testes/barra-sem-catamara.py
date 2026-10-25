#!/usr/bin/env python3
"""Confere o padrão da barra sem o Catamarã e a migração que o tira da cópia pessoal."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
MIGRACOES = [REPO / 'migrations' / n for n in (
    '202610172200-barra-catamara.sh', '202610172210-barra-catamara-estilo.sh',
    '202610250000-barra-sem-catamara.sh')]
MIGRACAO = MIGRACOES[-1]
BLOCO = '''  // Botão do Catamarã, outro projeto. Mostra só a logo, que vem do base.css,
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
ANTIGO = '''  "custom/catamara": {
    "exec": "$HOME/.local/bin/cata tarefas --waybar",
    "return-type": "json",
    "interval": 15,
    "signal": 11,
    "format": "{}",
    "on-click": "setsid -f $HOME/.local/bin/cata tarefas --web",
    "tooltip": true
  },
'''
STYLE_ANTIGO = '''@import url("base.css");

/* Catamarã: estados ativo, aviso (entregas pendentes) e erro (portão reprovado). */
#custom-catamara {
  padding: 0 8px;
  border-radius: 8px;
  color: @primaria;
  background: alpha(@primaria, 0.12);
  border: 1px solid alpha(@primaria, 0.30);
}

#custom-catamara:hover {
  background: alpha(@primaria, 0.22);
}

#custom-catamara.aviso {
  color: @atencao;
  background: alpha(@atencao, 0.16);
  border: 1px solid alpha(@atencao, 0.40);
  font-weight: bold;
}

#custom-catamara.erro {
  color: @superficie;
  background: @atencao;
  border: 1px solid @atencao;
  font-weight: bold;
}
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
        self.padrao = (REPO / 'waybar/config.jsonc').read_text()
        # A barra de antes: o padrão atual com o botão de volta.
        self.com_botao = self.padrao.replace(
            '"custom/menu", "hyprland/workspaces"', '"custom/menu", "custom/catamara", "hyprland/workspaces"', 1)
        self.com_botao = self.com_botao.replace(
            '  "hyprland/workspaces": {', BLOCO + '  "hyprland/workspaces": {', 1)

    def migrar(self, simular=False, migracao=MIGRACAO):
        ambiente = dict(self.ambiente, JANGADA_SIMULAR=str(int(simular)))
        return subprocess.run(['bash', str(migracao)], env=ambiente,
                              capture_output=True, text=True)

    def copias(self):
        return list(self.alvo.parent.glob('config.jsonc.jangada-*.bak'))

    def conferir(self, antes, esperado=None):
        """Migra, confere o resultado, a cópia e a segunda passada sem efeito."""
        for copia in self.copias():
            copia.unlink()
        self.alvo.write_text(antes)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        depois = self.alvo.read_text()
        if esperado is not None:
            self.assertEqual(depois, esperado)
        self.assertEqual([c.read_text() for c in self.copias()], [antes])
        segunda = self.migrar()
        self.assertEqual(segunda.returncode, 0, segunda.stderr)
        self.assertIn('nada a migrar', segunda.stdout)
        self.assertEqual(self.alvo.read_text(), depois)
        self.assertEqual(len(self.copias()), 1)
        return resultado

    def mantido(self, antes, aviso):
        self.alvo.write_text(antes)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual('custom/catamara pessoal mantido' in resultado.stderr, aviso)
        self.assertEqual(self.alvo.read_text(), antes)
        self.assertEqual(self.copias(), [])

    def test_padrao_sem_o_botao(self):
        dados = carregar(self.padrao)
        self.assertNotIn('custom/catamara', dados)
        self.assertEqual(dados['modules-left'],
                         ['custom/menu', 'hyprland/workspaces', 'custom/agentes', 'hyprland/window'])
        self.assertNotIn('catamar', self.padrao.lower())
        self.assertNotIn('catamar', (REPO / 'waybar/base.css').read_text().lower())
        self.assertNotIn('catamar', (REPO / 'bin/jangada-barra').read_text().lower())
        self.assertFalse((REPO / 'bin/jangada-barra-catamara').exists())
        self.assertFalse((REPO / 'waybar/icones/catamara-symbolic.svg').exists())

    def test_padrao_atual_nao_muda(self):
        self.alvo.write_text(self.padrao)
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertEqual(self.alvo.read_text(), self.padrao)
        self.assertEqual(self.copias(), [])

    def test_padrao_de_antes_volta_ao_padrao_atual(self):
        self.assertIn('custom/catamara', carregar(self.com_botao))
        self.conferir(self.com_botao, self.padrao)

    def test_clique_pessoal_desktop(self):
        antes = self.com_botao.replace('jangada-barra-catamara --web', 'jangada-barra-catamara --desktop')
        self.assertIn('--desktop', antes)
        self.conferir(antes, self.padrao)

    def test_exec_com_outro_caminho_e_outros_cliques(self):
        for exec_ in ('/opt/jangada/bin/jangada-barra-catamara --waybar',
                      '$HOME/.local/share/jangada/bin/jangada-barra-catamara --waybar',
                      'jangada-barra-catamara --waybar',
                      '~/bin/jangada-barra-catamara',
                      '\\"/opt/jangada local/bin/jangada-barra-catamara\\" --waybar',
                      '\\"$JANGADA_PATH/bin/jangada-barra-catamara\\" --waybar',
                      "'/opt/jangada local/bin/jangada-barra-catamara' --waybar",
                      '/opt/jangada+local/bin/jangada-barra-catamara --waybar',
                      '/opt/j@ng,ada=1/bin/jangada-barra-catamara --waybar'):
            with self.subTest(exec=exec_):
                antes = self.com_botao.replace('$JANGADA_PATH/bin/jangada-barra-catamara --waybar', exec_, 1)
                antes = antes.replace('"on-click-right": "setsid -f $JANGADA_PATH/bin/jangada-barra-catamara --terminal"',
                                      '"on-click-right": "meu-terminal -e catamara"', 1)
                self.conferir(antes, self.padrao)

    def test_exec_antigo_do_catamara(self):
        for exec_ in ('$HOME/.local/bin/cata tarefas --waybar', 'catamara-tarefas --waybar',
                      '/x/catamara-tarefas --waybar'):
            with self.subTest(exec=exec_):
                antes = self.com_botao.replace(
                    '"$JANGADA_PATH/bin/jangada-barra-catamara --waybar"', f'"{exec_}"', 1)
                self.conferir(antes, self.padrao)
        antes = re.sub(r'  // Botão do Catamarã.*?\n  \},\n', ANTIGO, self.com_botao, count=1, flags=re.S)
        self.assertIn('cata tarefas', antes)
        self.conferir(antes, self.padrao)

    def test_definicao_pessoal_diferente_fica_com_aviso(self):
        for exec_ in ('$HOME/.local/bin/meu-catamara --waybar',
                      'jangada-barra-catamara --waybar; cata tarefas --waybar',
                      "sh -c 'jangada-barra-catamara --waybar'",
                      'echo jangada-barra-catamara',
                      '\\"/opt/x\\"; jangada-barra-catamara --waybar',
                      '/opt/outro-jangada-barra-catamara --waybar',
                      '$(jangada-barra-catamara --waybar)',
                      '\\"$(rm -rf x)/jangada-barra-catamara\\" --waybar',
                      'jangada-barra-catamara --waybar | cat'):
            with self.subTest(exec=exec_):
                antes = self.com_botao.replace('$JANGADA_PATH/bin/jangada-barra-catamara --waybar', exec_, 1)
                self.mantido(antes, aviso=True)
        for texto in ('{"modules-left": ["custom/menu", "custom/catamara"], "custom/catamara": {"format": "meu"}}',
                      '{"modules-left": ["custom/catamara"], "custom/catamara": "texto"}',
                      '{"modules-left": ["custom/catamara"], "custom/catamara": {"exec": 3}}'):
            with self.subTest(texto=texto):
                self.mantido(texto, aviso=True)

    def test_sem_definicao_na_barra_com_include_fica(self):
        # O arquivo incluído pode ter uma definição pessoal, que a migração não lê.
        d = '"custom/catamara": {"exec": "jangada-barra-catamara --waybar"}'
        self.mantido('{"include": ["pessoal.jsonc"], "modules-left": ["custom/menu", "custom/catamara"]}',
                     aviso=True)
        antes = f'{{"include": ["pessoal.jsonc"], "modules-left": ["custom/catamara"], {d}}}'
        self.conferir(antes, '{"include": ["pessoal.jsonc"], "modules-left": []}')

    def test_aviso_nomeia_o_arquivo(self):
        self.alvo.write_text('{"modules-left": ["custom/catamara"], "custom/catamara": {"format": "meu"}}')
        self.assertIn(str(self.alvo), self.migrar().stderr)

    def test_lista_em_uma_linha_e_em_varias(self):
        d = '"custom/catamara": {"exec": "jangada-barra-catamara --waybar"}'
        casos = [
            (f'{{"modules-left": ["custom/menu", "custom/catamara", "a"], {d}}}',
             '{"modules-left": ["custom/menu", "a"]}'),
            (f'{{"modules-left": ["custom/catamara", "a"], {d}}}', '{"modules-left": ["a"]}'),
            (f'{{"modules-left": ["a", "custom/catamara"], {d}}}', '{"modules-left": ["a"]}'),
            (f'{{"modules-left": ["custom/catamara"], {d}}}', '{"modules-left": []}'),
            ('{"modules-left": ["a", "custom/catamara"]}', '{"modules-left": ["a"]}'),
            (f'{{"modules-left": ["a", /* x */ "custom/catamara"], {d}}}',
             '{"modules-left": ["a" /* x */ ]}'),
            (f'{{"modules-left": ["custom\\/catamara", "a"], "custom\\u002fcatamara": {{"exec": "cata tarefas --waybar"}}}}',
             '{"modules-left": ["a"]}'),
            (f'{{"modules-left": ["custom/menu", "custom/catamara",], {d}}}',
             '{"modules-left": ["custom/menu", ]}'),
            (f'{{"modules-left": ["a", "custom/catamara", "custom/catamara", "b"], {d}}}',
             '{"modules-left": ["a", "b"]}'),
            (f'{{"modules-left": ["custom/menu", "a"], "modules-right": ["custom/catamara", "b"], {d}}}',
             '{"modules-left": ["custom/menu", "a"], "modules-right": ["b"]}'),
            ('{\n  "modules-left": [\n    "custom/menu",\n    "custom/catamara",\n    "hyprland/workspaces"\n  ],\n'
             '  "custom/catamara": {"exec": "catamara-tarefas --waybar"},\n  "height": 1\n}',
             '{\n  "modules-left": [\n    "custom/menu",\n    "hyprland/workspaces"\n  ],\n  "height": 1\n}'),
            ('{\n  "modules-left": [\n    "a",\n    "custom/catamara"\n  ]\n}',
             '{\n  "modules-left": [\n    "a"\n  ]\n}'),
            ('{\n  "modules-center": [\n    "a",\n    "custom/catamara",\n    "b"\n  ]\n}',
             '{\n  "modules-center": [\n    "a",\n    "b"\n  ]\n}'),
            (f'{{"custom/catamara": {{"exec": "cata tarefas --waybar"}}, {d}}}', '{}'),
        ]
        for antes, esperado in casos:
            with self.subTest(antes=antes):
                self.conferir(antes, esperado)
                carregar(esperado)

    def test_varias_barras(self):
        d = '"custom/catamara": {"exec": "jangada-barra-catamara --waybar"}'
        antes = (f'[{{"modules-left": ["custom/menu", "custom/catamara"], {d}}},'
                 ' {"modules-left": ["custom/catamara", "x"]},'
                 ' {"modules-left": ["custom/catamara"], "custom/catamara": {"format": "meu"}}]')
        resultado = self.conferir(antes)
        self.assertEqual(carregar(self.alvo.read_text()),
                         [{'modules-left': ['custom/menu']}, {'modules-left': ['x']},
                          {'modules-left': ['custom/catamara'], 'custom/catamara': {'format': 'meu'}}])
        self.assertIn('custom/catamara pessoal mantido', resultado.stderr)

    def test_preserva_comentarios_e_modulos_pessoais(self):
        antes = '''{
 // custom/catamara em comentário fica
 // comentário pessoal do módulo
 "modules-right": ["clock", /* pessoal */ "custom/menu", "custom/catamara",],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"}, // fim do menu
 "custom/outro": {"exec": "jangada-barra-catamara-outro"},
 "custom/catamara": {"exec": "jangada-barra-catamara --waybar"},
 "height": 47
}'''
        esperado = '''{
 // custom/catamara em comentário fica
 // comentário pessoal do módulo
 "modules-right": ["clock", /* pessoal */ "custom/menu", ],
 "clock": {"format": "http://exemplo//*texto*/"},
 "custom/menu": {"on-click": "menu pessoal"}, // fim do menu
 "custom/outro": {"exec": "jangada-barra-catamara-outro"},
 "height": 47
}'''
        self.conferir(antes, esperado)

    def test_comentario_pessoal_acima_do_bloco_fica(self):
        antes = ('{\n  "modules-left": ["custom/catamara"],\n  // meu botão\n'
                 '  "custom/catamara": {"exec": "jangada-barra-catamara --waybar"}\n}')
        self.conferir(antes, '{\n  "modules-left": []\n  // meu botão\n}')

    def test_simulacao_nao_grava(self):
        self.alvo.write_text(self.com_botao)
        resultado = self.migrar(simular=True)
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.alvo.read_text(), self.com_botao)
        self.assertEqual(self.copias(), [])
        self.assertIn('simulação', resultado.stdout)

    def test_sem_copia_pessoal(self):
        resultado = self.migrar()
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertIn('nada a migrar', resultado.stdout)
        self.assertFalse(self.alvo.exists())

    def test_copia_invalida(self):
        casos = [('{"modules-left": ["clock"]} // custom/catamara', 0),
                 ('{"modules-left": ["clock"', 0),
                 ('', 0),
                 ('42', 0),
                 ('{"modules-left": ["custom/catamara"', 1),
                 ('[1, {"modules-left": ["custom/catamara"]', 1)]
        for texto, codigo in casos:
            with self.subTest(texto=texto):
                self.alvo.write_text(texto)
                self.assertEqual(self.migrar().returncode != 0, bool(codigo))
                self.assertEqual(self.alvo.read_text(), texto)
                self.assertEqual(self.copias(), [])

    def test_copia_com_bytes_invalidos(self):
        for bruto, codigo in [(b'{"modules-left": ["clock"]} // \xff\xfe', 0),
                              (b'\xff\xfe{"modules-left": ["clock"]}', 0),
                              (b'{"modules-left": ["custom/catamara"]} // \xff', 1)]:
            with self.subTest(bruto=bruto):
                self.alvo.write_bytes(bruto)
                resultado = self.migrar()
                self.assertEqual(resultado.returncode != 0, bool(codigo), resultado.stderr)
                self.assertEqual(self.alvo.read_bytes(), bruto)
                self.assertEqual(self.copias(), [])

    def test_lista_com_valor_que_nao_e_barra(self):
        self.conferir('[1, {"modules-left": ["a", "custom/catamara"]}, "x"]',
                      '[1, {"modules-left": ["a"]}, "x"]')

    def test_sequencia_das_tres_migracoes_da_barra(self):
        style = self.alvo.parent / 'style.css'
        style.write_text(STYLE_ANTIGO)
        antes = self.com_botao.replace('jangada-barra-catamara --web', 'jangada-barra-catamara --desktop')
        self.alvo.write_text(antes)
        for rodada in (1, 2):
            for migracao in MIGRACOES:
                with self.subTest(rodada=rodada, migracao=migracao.name):
                    resultado = self.migrar(migracao=migracao)
                    self.assertEqual(resultado.returncode, 0, resultado.stderr)
            dados = carregar(self.alvo.read_text())
            self.assertNotIn('custom/catamara', dados)
            self.assertNotIn('custom/catamara', dados['modules-left'])
            self.assertEqual(dados['modules-left'][:2], ['custom/menu', 'hyprland/workspaces'])
            self.assertEqual(self.alvo.read_text(), self.padrao)
            self.assertNotIn('catamara', style.read_text())

    def test_sequencia_com_o_botao_ja_no_lugar_antigo(self):
        # O Catamarã punha o botão depois do custom/indicadores, de texto.
        antes = self.padrao.replace('"custom/agentes", "hyprland/window"',
                                    '"custom/agentes", "custom/catamara", "hyprland/window"', 1)
        antes = antes.replace('  "hyprland/workspaces": {', ANTIGO + '\n  "hyprland/workspaces": {', 1)
        self.alvo.write_text(antes)
        for migracao in MIGRACOES:
            with self.subTest(migracao=migracao.name):
                resultado = self.migrar(migracao=migracao)
                self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.alvo.read_text(), self.padrao)

    def test_sequencia_mantem_botao_pessoal_diferente(self):
        antes = '{"modules-left": ["custom/menu", "custom/catamara"], "custom/catamara": {"exec": "meu-botao"}}'
        self.alvo.write_text(antes)
        for migracao in MIGRACOES:
            self.assertEqual(self.migrar(migracao=migracao).returncode, 0)
        self.assertEqual(carregar(self.alvo.read_text())['custom/catamara'], {'exec': 'meu-botao'})
        self.assertIn('custom/catamara', carregar(self.alvo.read_text())['modules-left'])


if __name__ == '__main__':
    unittest.main()
