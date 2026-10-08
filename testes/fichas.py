#!/usr/bin/env python3
"""Contraste real, reserva e migração sem alterar configurações existentes."""
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

sys.dont_write_bytecode = True
RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / 'default'))
from visual.fichas import PADRAO, ESTADOS, contraste, validar


class Fichas(unittest.TestCase):
    def conferir(self, dados):
        for modo, cores in dados.items():
            for fundo in ('superficie', 'superficie_elevada'):
                for texto in ('texto', 'texto_suave'):
                    self.assertGreaterEqual(contraste(cores[texto], cores[fundo]), 4.5)
                for cor in ESTADOS[modo].values():
                    self.assertGreaterEqual(contraste(cor, cores[fundo]), 4.5)
            self.assertGreaterEqual(contraste(cores['primaria'], cores['superficie']), 4.5)
            self.assertGreaterEqual(contraste(cores['texto_primario'], cores['primaria']), 4.5)

    def test_reserva_e_paleta_sem_contraste(self):
        self.conferir(PADRAO)
        ruim = {modo: {k: '#808080' for k in cores} for modo, cores in PADRAO.items()}
        self.assertEqual(validar(ruim), PADRAO)
        self.assertEqual(validar({'dark': {'texto': 'url(externo)'}}), PADRAO)

    def test_gravacao_recupera_arquivo_ausente_e_json_invalido(self):
        with tempfile.TemporaryDirectory() as tmp:
            destino = Path(tmp) / 'fichas.json'
            for conteudo in (None, '{inválido'):
                if conteudo is not None:
                    destino.write_text(conteudo)
                resposta = subprocess.run([sys.executable, str(RAIZ / 'default/visual/fichas.py'), str(destino)],
                                          capture_output=True, text=True, timeout=10)
                self.assertEqual(resposta.returncode, 0, resposta.stderr)
                self.assertEqual(json.loads(destino.read_text()), PADRAO)
                self.assertIn('paleta de reserva', resposta.stderr)
                self.assertNotIn('Traceback', resposta.stderr)

    def test_uso_invalido_sem_traceback(self):
        for argumentos in ([], ['um', 'dois']):
            with self.subTest(argumentos=argumentos):
                resposta = subprocess.run([sys.executable, str(RAIZ / 'default/visual/fichas.py'), *argumentos],
                                          capture_output=True, text=True, timeout=10)
                self.assertNotEqual(resposta.returncode, 0)
                self.assertIn('uso:', resposta.stderr)
                self.assertNotIn('Traceback', resposta.stderr)

    def test_tema_simulado_nao_grava_nem_recarrega(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            ambiente = dict(os.environ, JANGADA_PATH=str(RAIZ), XDG_CONFIG_HOME=str(pasta / 'config'),
                            XDG_STATE_HOME=str(pasta / 'estado'), JANGADA_SIMULAR='1')
            for argumentos in (['--cor', '#4f8fba'], [str(pasta / 'ausente.png')]):
                resposta = subprocess.run([str(RAIZ / 'bin/jangada-tema'), *argumentos], env=ambiente,
                                          capture_output=True, text=True, timeout=10)
                self.assertEqual(resposta.returncode, 0, resposta.stderr)
                self.assertIn('[simulação]', resposta.stdout)
                self.assertEqual(list(pasta.iterdir()), [])

    @unittest.skipUnless(shutil.which('matugen'), 'matugen ausente')
    def test_tres_imagens_dois_modos_com_matugen_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            cfg = pasta / 'config.toml'
            destino = pasta / 'fichas.json'
            cfg.write_text('[config]\nversion_check = false\n[templates.fichas]\ninput_path = '
                           + json.dumps(str(RAIZ / 'default/matugen/modelos/fichas.json'))
                           + '\noutput_path = ' + json.dumps(str(destino)) + '\n')
            for nome, rgb in [('azul', (79, 143, 186)), ('vermelho', (186, 45, 45)), ('cinza', (128, 128, 128))]:
                def chunk(tipo, dados):
                    return struct.pack('!I', len(dados)) + tipo + dados + struct.pack('!I', zlib.crc32(tipo + dados))
                imagem = pasta / (nome + '.png')
                imagem.write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', 32, 32, 8, 2, 0, 0, 0))
                                   + chunk(b'IDAT', zlib.compress((b'\0' + bytes(rgb) * 32) * 32)) + chunk(b'IEND', b''))
                resposta = subprocess.run(['matugen', 'image', str(imagem), '-c', str(cfg), '-m', 'dark',
                                           '-t', 'scheme-fidelity', '--source-color-index', '0'],
                                          capture_output=True, text=True, timeout=20)
                self.assertEqual(resposta.returncode, 0, resposta.stderr)
                dados = json.loads(destino.read_text())
                self.assertEqual(set(dados), {'dark', 'light'})
                self.conferir(dados)
                self.conferir(validar(dados))

    def test_migracao_repetivel_simulada_preserva_personalizacao(self):
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            destino = pasta / 'config/jangada/fichas.json'
            ambiente = dict(os.environ, JANGADA_PATH=str(RAIZ), XDG_CONFIG_HOME=str(pasta / 'config'),
                            XDG_STATE_HOME=str(pasta / 'estado'), JANGADA_SIMULAR='1')
            comando = [str(RAIZ / 'migrations/202610081200-fichas-visuais.sh')]
            subprocess.run(comando, env=ambiente, check=True, capture_output=True)
            self.assertFalse(destino.exists())
            ambiente['JANGADA_SIMULAR'] = '0'
            subprocess.run(comando, env=ambiente, check=True, capture_output=True)
            self.assertEqual(json.loads(destino.read_text()), PADRAO)
            destino.write_text('personalização')
            subprocess.run(comando, env=ambiente, check=True, capture_output=True)
            self.assertEqual(destino.read_text(), 'personalização')


if __name__ == '__main__':
    unittest.main()
