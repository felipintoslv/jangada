#!/usr/bin/env python3
"""Testes offline da janela de conversa local, com um Ollama falso."""
import fcntl
import http.server
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
TEMP = tempfile.TemporaryDirectory()
os.environ['JANGADA_ESTADO'] = TEMP.name
os.environ['JANGADA_CONFIG'] = TEMP.name
os.environ['JANGADA_LOCAL_MODELO'] = 'modelo-b'
os.environ['JANGADA_LOCAL_CTX'] = '4096'
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
sys.path.insert(0, str(RAIZ/'default/conversa'))

try:
    from PyQt6.QtWidgets import QApplication
    import janela
except ImportError:
    janela = None

PEDIDOS = []
SOLTAR = threading.Event()


class OllamaFalso(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def responder(self, codigo, linhas):
        self.send_response(codigo)
        self.send_header('Content-Type', 'application/x-ndjson')
        self.end_headers()
        for linha in linhas:
            self.wfile.write(json.dumps(linha).encode() + b'\n')
            self.wfile.flush()

    def do_GET(self):
        if self.path == '/api/tags':
            self.responder(200, [{'models': [{'name': 'modelo-b'}, {'name': 'qwen3:4b'}, {'name': 'modelo-a'}]}])
        else:
            self.responder(200, [{'models': [{'name': 'modelo-a', 'size_vram': 3000 * 2**20}]}])

    def do_POST(self):
        pedido = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        PEDIDOS.append(pedido)
        pergunta = pedido['messages'][-1]['content']
        parte = lambda texto: {'message': {'role': 'assistant', 'content': texto}, 'done': False}
        fim = {'message': {'content': ''}, 'done': True, 'total_duration': 2e9,
               'prompt_eval_count': 30, 'eval_count': 12}
        if pergunta == 'recusa':
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b'{"error":"model not found"}')
        elif pergunta == 'lenta':
            self.responder(200, [parte('Trecho parcial')])
            SOLTAR.wait(10)
        elif pergunta == 'vaza':
            self.responder(200, [parte('Okay, the user'), parte(' asks.\n</thi'), parte('nk>'), parte('\n\nResposta'),
                                 parte(' limpa'), fim])
        else:
            self.responder(200, [{'message': {'thinking': 'hm'}, 'done': False}, parte('Olá'), parte(' ç'), fim])


@unittest.skipIf(janela is None, 'PyQt6 ausente')
class ConversaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.servidor = http.server.ThreadingHTTPServer(('127.0.0.1', 0), OllamaFalso)
        cls.servidor.daemon_threads = True
        threading.Thread(target=cls.servidor.serve_forever, daemon=True).start()
        os.environ['JANGADA_OLLAMA_URL'] = f'http://127.0.0.1:{cls.servidor.server_port}'
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls):
        SOLTAR.set()
        cls.servidor.shutdown()

    def setUp(self):
        PEDIDOS.clear()
        for nome, valor in (('jogo_aberto', False), ('vram_livre', None)):
            ativo = patch.object(janela, nome, return_value=valor)
            ativo.start()
            self.addCleanup(ativo.stop)
        self.janela = janela.Conversa()
        self.addCleanup(self.janela.close)

    def esperar(self, condicao):
        limite = time.monotonic() + 5
        while not condicao() and time.monotonic() < limite:
            self.app.processEvents()
            time.sleep(0.01)
        self.assertTrue(condicao(), 'A janela não chegou ao estado esperado.')

    def perguntar(self, texto):
        self.janela.entrada.setPlainText(texto)
        self.janela.enviar()

    def trava_livre(self):
        with open(Path(TEMP.name)/'local.lock', 'w') as arquivo:
            try:
                fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                return False
        return True

    def test_modelos_e_padrao(self):
        self.assertEqual([self.janela.modelo.itemText(i) for i in range(3)], ['modelo-a', 'modelo-b', 'qwen3:4b'])
        self.assertEqual(self.janela.modelo.currentText(), 'modelo-b')
        self.assertFalse(self.janela.parar.isEnabled())

    def test_resposta_progressiva_entra_no_contexto(self):
        self.perguntar('oi')
        self.assertFalse(self.trava_livre())
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual(self.janela.mensagens, [{'role': 'user', 'content': 'oi'},
                                                 {'role': 'assistant', 'content': 'Olá ç'}])
        self.assertEqual(self.janela.status.text(), '2s. Contexto: 42 de 4096 tokens.')
        self.assertTrue(self.trava_livre())
        pedido = PEDIDOS[0]
        self.assertEqual((pedido['model'], pedido['think'], pedido['options']), ('modelo-b', False, {'num_ctx': 4096}))
        self.assertEqual(pedido['messages'][0], {'role': 'system', 'content': janela.SISTEMA})
        self.perguntar('de novo')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual([m['content'] for m in PEDIDOS[1]['messages'][1:]], ['oi', 'Olá ç', 'de novo'])
        self.janela.nova()
        self.assertEqual(self.janela.mensagens, [])

    def test_parar_mantem_o_trecho_fora_do_contexto(self):
        self.perguntar('lenta')
        self.esperar(lambda: self.janela.resposta == 'Trecho parcial')
        self.janela.cancelar()
        self.assertIsNone(self.janela.chamada)
        self.assertEqual(self.janela.mensagens, [])
        self.assertEqual(self.janela.resposta, 'Trecho parcial')
        self.assertIn('Interrompida', self.janela.status.text())
        self.assertTrue(self.trava_livre())
        self.assertTrue(self.janela.enviar_botao.isEnabled())

    def test_raciocinio_vazado_sai_da_resposta_e_muda_a_chamada_seguinte(self):
        self.perguntar('vaza')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual(self.janela.mensagens[-1]['content'], 'Resposta limpa')
        self.perguntar('oi')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual([p['think'] for p in PEDIDOS], [False, True])

    def test_modelo_que_sempre_raciocina_ja_comeca_separando_o_raciocinio(self):
        self.janela.modelo.setCurrentText('qwen3:4b')
        self.perguntar('oi')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual((PEDIDOS[0]['model'], PEDIDOS[0]['think']), ('qwen3:4b', True))

    def test_recusa_do_ollama_aparece_no_estado(self):
        self.perguntar('recusa')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual(self.janela.status.text(), 'model not found')
        self.assertEqual(self.janela.mensagens, [])
        self.assertTrue(self.trava_livre())

    def test_delegacao_em_curso_impede_o_envio(self):
        with open(Path(TEMP.name)/'local.lock', 'w') as arquivo:
            fcntl.flock(arquivo, fcntl.LOCK_EX)
            self.perguntar('oi')
        self.assertIn('ocupado com uma delegação', self.janela.status.text())
        self.assertEqual(self.janela.entrada.toPlainText(), 'oi')
        self.assertEqual(PEDIDOS, [])

    def test_jogo_aberto_impede_o_envio(self):
        janela.jogo_aberto.return_value = True
        self.perguntar('oi')
        self.assertIn('jogo aberto', self.janela.status.text())
        self.assertEqual(PEDIDOS, [])
        self.assertTrue(self.trava_livre())

    def test_memoria_de_video_soma_o_que_o_ollama_ja_ocupa(self):
        janela.vram_livre.return_value = 900
        self.perguntar('oi')
        self.assertIn('900 MiB livres e 3000 MiB do Ollama', self.janela.status.text())
        self.assertEqual(PEDIDOS, [])
        janela.vram_livre.return_value = 1000
        self.perguntar('oi')
        self.esperar(lambda: self.janela.chamada is None)
        self.assertEqual(len(PEDIDOS), 1)

    def test_ollama_fora_do_ar(self):
        with patch.dict(os.environ, {'JANGADA_OLLAMA_URL': 'http://127.0.0.1:9'}):
            fora = janela.Conversa()
        self.assertIn('Ollama fora do ar', fora.status.text())
        fora.entrada.setPlainText('oi')
        fora.enviar()
        self.assertIsNone(fora.chamada)
        fora.close()


if __name__ == '__main__':
    unittest.main()
