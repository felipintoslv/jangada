#!/usr/bin/env python3
"""Monitoramento com API local sintética; nenhum modelo é executado."""
import http.server
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'monitor/painel'))
import monitoramento


class Monitoramento(unittest.TestCase):
    def setUp(self):
        self.pedidos = []
        self.corpo = b'{"models": []}'
        self.redirecionar = False
        teste = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):
                teste.pedidos.append(self.path)
                self.send_response(302 if teste.redirecionar else 200)
                if teste.redirecionar:
                    self.send_header('Location', '/api/chat')
                self.end_headers()
                self.wfile.write(teste.corpo)

            def log_message(self, *_):
                pass

        self.servidor = http.server.ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.servidor.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.servidor.server_close)
        self.addCleanup(self.servidor.shutdown)

    def coletar(self):
        host = 'http://127.0.0.1:' + str(self.servidor.server_port)
        with patch.dict(os.environ, {'OLLAMA_HOST': host}), patch.object(monitoramento.shutil, 'which', return_value=None):
            return monitoramento.coletar()

    def test_leitura_real_de_proc_e_somente_listagem_local(self):
        dados = self.coletar()
        self.assertGreater(dados['cpu_ticks']['total'], 0)
        self.assertGreater(dados['memoria_bytes']['total'], 0)
        self.assertIsNone(dados['gpu'])
        self.assertEqual(dados['modelos_carregados'], [])
        self.assertEqual(self.pedidos, ['/api/ps'])
        json.dumps(dados, allow_nan=False)

    def test_endereco_de_escuta_consulta_apenas_loopback(self):
        for host in ('0.0.0.0', 'http://0.0.0.0', '0.0.0.0:11434',
                     '0.0.0.0:' + str(self.servidor.server_port)):
            with self.subTest(host=host), patch.dict(os.environ, {'OLLAMA_HOST': host}), \
                    patch.object(monitoramento.shutil, 'which', return_value=None), \
                    patch.object(monitoramento.urllib.request, 'build_opener') as construir:
                construir.return_value.open.return_value.__enter__.return_value.read.return_value = self.corpo
                dados = monitoramento.coletar()
            porta = self.servidor.server_port if host.endswith(':' + str(self.servidor.server_port)) else 11434
            construir.return_value.open.assert_called_once_with(f'http://127.0.0.1:{porta}/api/ps', timeout=2)
            self.assertEqual(dados['modelos_carregados'], [])

    def test_enderecos_locais_sem_porta_usam_padrao_ollama(self):
        for host, esperado in (('127.0.0.1', '127.0.0.1'), ('http://127.0.0.1', '127.0.0.1'),
                               ('localhost', 'localhost'), ('http://localhost', 'localhost'),
                               ('[::1]', '[::1]'), ('http://[::1]', '[::1]')):
            with self.subTest(host=host), patch.dict(os.environ, {'OLLAMA_HOST': host}), \
                    patch.object(monitoramento.shutil, 'which', return_value=None), \
                    patch.object(monitoramento.urllib.request, 'build_opener') as construir:
                construir.return_value.open.return_value.__enter__.return_value.read.return_value = self.corpo
                dados = monitoramento.coletar()
            construir.return_value.open.assert_called_once_with(f'http://{esperado}:11434/api/ps', timeout=2)
            self.assertEqual(dados['modelos_carregados'], [])

    def test_sem_redirecionamento_e_sem_confundir_erro_com_zero(self):
        self.redirecionar = True
        dados = self.coletar()
        self.assertIsNone(dados['modelos_carregados'])
        self.assertEqual(self.pedidos, ['/api/ps'])
        self.redirecionar = False
        self.corpo = b'{"models": [{"size": NaN}]}'
        self.assertIsNone(self.coletar()['modelos_carregados'])
        for corpo in ('JSON inválido'.encode(), b'{"models": {}}', b'x' * (1024 * 1024 + 1)):
            self.corpo = corpo
            dados = self.coletar()
            self.assertIsNone(dados['modelos_carregados'])
            self.assertIn('modelos carregados indisponíveis', dados['erros'])

    def test_gpu_e_servidor_indisponiveis_nao_inventam_medidas(self):
        with patch.object(monitoramento.shutil, 'which', return_value='/falso/nvidia-smi'), \
                patch.object(monitoramento.subprocess, 'run', side_effect=subprocess.TimeoutExpired('nvidia-smi', 2)), \
                patch.object(monitoramento.urllib.request, 'build_opener') as construir:
            construir.return_value.open.side_effect = monitoramento.urllib.error.URLError('servidor indisponível')
            dados = monitoramento.coletar()
        self.assertIsNone(dados['gpu'])
        self.assertIsNone(dados['modelos_carregados'])
        self.assertIn('medição da GPU indisponível', dados['erros'])
        self.assertIn('modelos carregados indisponíveis', dados['erros'])
        self.assertEqual(self.pedidos, [])

    def test_endereco_remoto_e_malformado_nao_faz_pedido(self):
        for host in ('http://externo.example', 'https://externo.example', 'http://[inválido', 'http://usuario@0.0.0.0',
                     'http://0.0.0.0:0', 'http://0.0.0.0:65536'):
            with patch.dict(os.environ, {'OLLAMA_HOST': host}), patch.object(monitoramento.shutil, 'which', return_value=None):
                dados = monitoramento.coletar()
            self.assertIsNone(dados['modelos_carregados'])
        self.assertEqual(self.pedidos, [])

    def test_comando_json_nao_abre_terminal(self):
        raiz = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as pasta:
            copia = Path(pasta)
            (copia / 'bin').mkdir()
            (copia / 'default').mkdir()
            shutil.copytree(raiz / 'monitor', copia / 'monitor', symlinks=True)
            shutil.copytree(raiz / 'shell/bin', copia / 'shell/bin', symlinks=True)
            shutil.copy2(raiz / 'bin/jangada-config', copia / 'bin/jangada-config')
            (copia / 'bin/jangada-monitor').symlink_to('../shell/bin/jangada-monitor')
            (copia / 'default/painel').symlink_to('../monitor/painel')
            (copia / 'bin/jangada-terminal').write_text('#!/bin/sh\necho terminal-aberto >&2\nexit 99\n')
            (copia / 'bin/jangada-terminal').chmod(0o755)
            ambiente = dict(os.environ, JANGADA_PATH=str(copia), XDG_CONFIG_HOME=str(copia / 'config'),
                            OLLAMA_HOST='http://127.0.0.1:' + str(self.servidor.server_port))
            falsos = copia / 'falsos'
            falsos.mkdir()
            gpu = falsos / 'nvidia-smi'
            gpu.write_text('#!/bin/sh\nexit 1\n')
            gpu.chmod(0o755)
            ambiente['PATH'] = str(falsos) + os.pathsep + os.environ['PATH']
            resposta = subprocess.run([str(copia / 'bin/jangada-monitor'), '--json'], env=ambiente,
                                      capture_output=True, text=True, timeout=15)
            self.assertFalse((copia / 'core').exists())
            shutil.rmtree(copia / 'monitor')
            ausente = subprocess.run([str(copia / 'bin/jangada-monitor'), '--json'], env=ambiente,
                                    capture_output=True, text=True, timeout=15)
            self.assertEqual(ausente.returncode, 1)
            self.assertEqual(ausente.stdout, '')
            self.assertIn('módulo Monitor ausente ou incompleto', ausente.stderr)
            self.assertNotIn('terminal-aberto', ausente.stderr)
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        self.assertNotIn('terminal-aberto', resposta.stderr)
        dados = json.loads(resposta.stdout)
        self.assertEqual(set(dados), {'data', 'cpu_ticks', 'memoria_bytes', 'gpu', 'modelos_carregados', 'erros'})
        self.assertIsNone(dados['gpu'])
        self.assertIn('medição da GPU indisponível', dados['erros'])
        self.assertGreater(dados['cpu_ticks']['total'], 0)
        self.assertEqual(dados['modelos_carregados'], [])
        self.assertEqual(self.pedidos, ['/api/ps'])


if __name__ == '__main__':
    unittest.main()
