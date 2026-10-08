#!/usr/bin/env python3
"""Monitoramento com API local sintética; nenhum modelo é executado."""
import http.server
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'default'))
from nucleo import monitoramento


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

    def test_sem_redirecionamento_e_sem_confundir_erro_com_zero(self):
        self.redirecionar = True
        dados = self.coletar()
        self.assertIsNone(dados['modelos_carregados'])
        self.assertEqual(self.pedidos, ['/api/ps'])
        self.redirecionar = False
        self.corpo = b'{"models": [{"size": NaN}]}'
        self.assertIsNone(self.coletar()['modelos_carregados'])

    def test_endereco_remoto_e_malformado_nao_faz_pedido(self):
        for host in ('http://externo.example', 'https://externo.example', 'http://[inválido', 'http://usuario@0.0.0.0',
                     'http://0.0.0.0:0', 'http://0.0.0.0:65536'):
            with patch.dict(os.environ, {'OLLAMA_HOST': host}), patch.object(monitoramento.shutil, 'which', return_value=None):
                dados = monitoramento.coletar()
            self.assertIsNone(dados['modelos_carregados'])
        self.assertEqual(self.pedidos, [])

    def test_comando_json_nao_abre_terminal(self):
        raiz = Path(__file__).resolve().parents[1]
        ambiente = dict(os.environ, JANGADA_PATH=str(raiz), OLLAMA_HOST='http://127.0.0.1:' + str(self.servidor.server_port))
        resposta = subprocess.run([str(raiz / 'bin/jangada-monitor'), '--json'], env=ambiente,
                                  capture_output=True, text=True, timeout=15)
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        dados = json.loads(resposta.stdout)
        self.assertGreater(dados['cpu_ticks']['total'], 0)
        self.assertEqual(dados['modelos_carregados'], [])
        self.assertEqual(self.pedidos, ['/api/ps'])


if __name__ == '__main__':
    unittest.main()
