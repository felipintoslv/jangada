#!/usr/bin/env python3
"""Confere o botão do Catamarã na barra com um Catamarã falso."""
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
COMANDO = REPO / 'bin/jangada-barra-catamara'
LOGO = REPO / 'waybar/icones/catamara-symbolic.svg'
DICA = ('Catamara Central de Tarefas\nCasco 1: C1:71.6% (Argon)\nCasco 2: C2:45.0% (Flash)\n'
        'Ollama: 3023 MiB VRAM\nSessoes: {s} ativas\nEntregas: {e} pendentes\n'
        'Clique: abrir central (catamara tarefas --web)')


def saida(classe, sessoes=0, entregas=0, texto='󰻄󰻄 C1:71.6% C2:45.0%'):
    return json.dumps({'text': texto, 'class': classe,
                       'tooltip': DICA.format(s=sessoes, e=entregas)}, ensure_ascii=False)


class Botao(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.tmp = Path(self.pasta.name)
        self.bin = self.tmp / 'bin'
        self.bin.mkdir()
        self.projetos = self.tmp / 'projetos'
        (self.tmp / 'config/jangada').mkdir(parents=True)
        (self.tmp / 'config/jangada/jangada.conf').write_text(
            f'JANGADA_PROJETOS={self.projetos}\nJANGADA_TERMINAL={self.tmp / "terminal"}\n')
        self.registro = self.tmp / 'registro'
        self.falso(self.tmp / 'terminal', 'printf "%s\\n" "$@" >"$REGISTRO"')
        # Só o essencial no PATH, para o Catamarã instalado na máquina não valer.
        for nome in ('bash', 'jq', 'timeout', 'sleep', 'dirname', 'readlink', 'sed', 'cat'):
            caminho = subprocess.run(['bash', '-c', f'command -v {nome}'],
                                     capture_output=True, text=True).stdout.strip()
            (self.bin / nome).symlink_to(caminho)

    def falso(self, caminho, corpo):
        caminho.parent.mkdir(parents=True, exist_ok=True)
        caminho.write_text(f'#!/bin/bash\n{corpo}\n')
        caminho.chmod(0o755)
        return caminho

    def tarefas(self, corpo, pasta=None):
        return self.falso((pasta or self.bin) / 'catamara-tarefas', corpo)

    def rodar(self, *args):
        ambiente = {'PATH': str(self.bin), 'HOME': str(self.tmp),
                    'XDG_CONFIG_HOME': str(self.tmp / 'config'),
                    'XDG_STATE_HOME': str(self.tmp / 'state'),
                    'JANGADA_PATH': str(REPO), 'REGISTRO': str(self.registro)}
        return subprocess.run([str(COMANDO), *args], env=ambiente,
                              capture_output=True, text=True, timeout=20)

    def waybar(self):
        resultado = self.rodar('--waybar')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        if not resultado.stdout:
            return None
        self.assertEqual(resultado.stdout.count('\n'), 1)
        return json.loads(resultado.stdout)

    def test_estados(self):
        casos = [
            (saida('ativo'), 'repouso'),
            (saida('ativo', sessoes=2), 'ativo'),
            (saida('aviso', sessoes=1, entregas=1), 'pendente'),
            (saida('erro', texto='x | portao reprovado'), 'erro'),
            (saida('aviso', entregas=2, texto='x | 2 entregas pendentes | portao reprovado'), 'erro'),
        ]
        for linha, estado in casos:
            with self.subTest(estado=estado):
                self.tarefas(f"printf '%s\\n' '{linha}'")
                dados = self.waybar()
                self.assertEqual(set(dados), {'text', 'tooltip', 'class'})
                self.assertEqual(dados['class'], estado)
                self.assertEqual(dados['text'], ' ')
                self.assertIn('C1:71.6%', dados['tooltip'])
                self.assertIn('Ollama: 3023 MiB', dados['tooltip'])
                self.assertIn('Botão do meio: iniciar sessão', dados['tooltip'])
                self.assertNotIn('Clique: abrir central', dados['tooltip'])
                self.assertEqual('Portão reprovado' in dados['tooltip'], estado == 'erro')

    def test_dica_escapada(self):
        linha = json.dumps({'text': 'x', 'class': 'ativo', 'tooltip': 'a <b> & c\nSessoes: 1 ativas'})
        self.tarefas(f"printf '%s\\n' '{linha}'")
        dados = self.waybar()
        self.assertEqual(dados['class'], 'ativo')
        self.assertIn('a &lt;b&gt; &amp; c', dados['tooltip'])

    def test_escondido(self):
        casos = {
            'ausente': None,
            'erro': f"printf '%s\\n' '{saida('ativo')}'; exit 1",
            'aviso na saída de erro': f"echo 'Aviso: usando dados demo' >&2; printf '%s\\n' '{saida('ativo')}'",
            'JSON inválido': "echo '{\"text\": '",
            'duas linhas': f"printf '%s\\n%s\\n' '{saida('ativo')}' '{saida('ativo')}'",
            'sem class': "echo '{\"text\": \"x\", \"tooltip\": \"y\"}'",
            'vazio': 'true',
            'demora': f"sleep 10; printf '%s\\n' '{saida('ativo')}'",
        }
        for caso, corpo in casos.items():
            with self.subTest(caso=caso):
                (self.bin / 'catamara-tarefas').unlink(missing_ok=True)
                if corpo is not None:
                    self.tarefas(corpo)
                resultado = self.rodar('--waybar')
                self.assertEqual(resultado.returncode, 0)
                self.assertEqual(resultado.stdout, '')
                self.assertEqual(resultado.stderr, '')

    def test_acha_fora_do_path(self):
        linha = saida('ativo', sessoes=1)
        with self.subTest(onde='pasta de projetos'):
            self.tarefas(f"printf '%s\\n' '{linha}'", self.projetos / 'catamara/bin')
            self.assertEqual(self.waybar()['class'], 'ativo')
        with self.subTest(onde='ao lado do catamara do PATH'):
            outra = self.tmp / 'instalado/bin'
            self.tarefas(f"printf '%s\\n' '{saida('aviso', entregas=1)}'", outra)
            self.falso(outra / 'catamara', 'exit 0')
            (self.bin / 'catamara').symlink_to(outra / 'catamara')
            self.assertEqual(self.waybar()['class'], 'pendente')

    def test_cliques(self):
        catamara = self.falso(self.bin / 'catamara', 'printf "%s\\n" "$@" >"$REGISTRO"')
        tarefas = self.tarefas('exit 0')
        resultado = self.rodar('--web')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.registro.read_text().split('\n')[:2], ['tarefas', '--web'])
        resultado = self.rodar('--terminal')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        argumentos = self.registro.read_text().splitlines()
        self.assertEqual(argumentos[0], '-e')
        self.assertEqual(argumentos[-1], str(tarefas))
        resultado = self.rodar('--iniciar')
        self.assertEqual(resultado.returncode, 0, resultado.stderr)
        self.assertEqual(self.registro.read_text().splitlines()[-2:], [str(catamara), 'iniciar'])
        catamara.unlink()
        tarefas.unlink()
        for clique in ('--web', '--terminal', '--iniciar'):
            with self.subTest(sem_catamara=clique):
                resultado = self.rodar(clique)
                self.assertEqual(resultado.returncode, 1)
                self.assertIn('Catamarã não encontrado', resultado.stderr)


class Aparencia(unittest.TestCase):
    def test_logo_igual_a_do_catamara(self):
        primeira, resto = LOGO.read_text().split('\n', 1)
        self.assertTrue(primeira.startswith('<!-- ') and 'catamara-symbolic.svg' in primeira)
        self.assertIn('fill="currentColor"', resto)
        projetos = Path(os.environ.get('JANGADA_PROJETOS', Path.home() / 'Projetos'))
        original = projetos / 'catamara/core/painel/catamara-symbolic.svg'
        if not original.is_file():
            self.skipTest(f'sem {original}')
        self.assertEqual(resto, original.read_text())

    def test_estilo(self):
        css = (REPO / 'waybar/base.css').read_text()
        self.assertNotIn('indicadores', css)
        bloco = re.findall(r'^#custom-catamara \{(.*?)\}', css, re.M | re.S)[-1]
        self.assertIn('-gtk-recolor(url("icones/catamara-symbolic.svg"))', bloco)
        menu = re.search(r'^#custom-menu \{(.*?)\}', css, re.M | re.S)[1]
        for medida in ('font-size: 0;', 'min-width: 20px;', 'background-size: 20px 20px;'):
            self.assertIn(medida, bloco)
            self.assertIn(medida, menu)
        for classe in ('ativo', 'pendente', 'erro'):
            regra = re.search(rf'^#custom-catamara\.{classe} \{{(.*?)\}}', css, re.M | re.S)[1]
            self.assertIn('color: @', regra)
            # O atalho background apagaria a logo.
            self.assertNotRegex(regra, r'\bbackground:')
        self.assertRegex(css, r'#custom-sessao,\n#custom-catamara \{\n  padding: 0 8px;')
        self.assertIn('window#waybar.vertical #custom-catamara,', css)


if __name__ == '__main__':
    unittest.main()
