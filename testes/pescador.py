#!/usr/bin/env python3
"""Testes offline do chat, dos pareceres e da execução cancelável."""
import ast
import contextlib
import importlib.util
import io
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
sys.path.insert(0, str(RAIZ/'default/pescador'))
spec = importlib.util.spec_from_file_location('pescador', RAIZ/'default/pescador/conversa-de-pescador.py')
motor = importlib.util.module_from_spec(spec); spec.loader.exec_module(motor)
from execucao import CONTEXTO, Contexto, ConsultaCancelada, executar


def parecer(nota=95, status='COMPROVADO'):
    return {'grau_fato': nota, 'grau_pescador': 100-nota, 'veredito_resumo': 'Parecer de teste',
            'analise_itens': [{'afirmacao': 'Afirmação', 'status': status, 'detalhe': 'Evidência'}], 'referencias': []}


class MotorTest(unittest.TestCase):
    def consulta(self, **kwargs):
        fontes = {'fontes': [{'url': 'https://exemplo.org', 'titulo': 'Fonte', 'snippet': 'Trecho'}], 'texto': 'Evidência'}
        with patch.object(motor, 'resolver_par', return_value=('claude', 'agy')), \
             patch.object(motor, 'agente_pescador', return_value=(True, 'Resposta')), \
             patch.object(motor, 'agente_pesquisador', return_value=fontes):
            return motor.processar_consulta('Pergunta', callback=kwargs.pop('callback', lambda e: None), **kwargs)

    def test_sem_auditoria_nao_tem_nota(self):
        r = self.consulta(rapido=True)
        self.assertEqual(r['estado'], 'nao_verificado')
        self.assertIsNone(r['auditoria']['grau_fato'])

    def test_parecer_invalido_nao_aprova(self):
        for texto in ('{}', 'não JSON', '[]', '{"grau_fato":100}', json.dumps(parecer(101)), json.dumps(parecer(True))):
            self.assertTrue(motor.parse_json_auditoria(texto)['erro'])
        self.assertEqual(motor.parse_json_auditoria(json.dumps(parecer(0)))['grau_fato'], 0)

    def test_auditoria_falha_fica_indisponivel(self):
        with patch.object(motor, 'agente_auditor_factual', return_value=motor.auditoria_indisponivel('erro')), \
             patch.object(motor, 'agente_auditor_metodologico', return_value=parecer()):
            r = self.consulta()
        self.assertEqual(r['estado'], 'indisponivel')
        self.assertIsNone(r['auditoria']['grau_fato'])

    def test_auditores_em_paralelo(self):
        barreira = threading.Barrier(2)
        def auditar(*args): barreira.wait(timeout=2); return parecer()
        with patch.object(motor, 'agente_auditor_factual', side_effect=auditar), \
             patch.object(motor, 'agente_auditor_metodologico', side_effect=auditar):
            r = self.consulta()
        self.assertEqual(r['estado'], 'verificado')
        self.assertEqual(r['rodadas'], 1)

    def test_contestacao_nao_some_nem_aprova(self):
        with patch.object(motor, 'agente_auditor_factual', return_value=parecer()), \
             patch.object(motor, 'agente_auditor_metodologico', return_value=parecer(status='CONTROVERSO')):
            r = self.consulta(rodadas=2)
        self.assertEqual(r['estado'], 'com_ressalvas')
        self.assertEqual(r['rodadas'], 2)
        self.assertEqual(len(r['auditoria']['analise_itens']), 2)

    def test_reescrita_limpa_resposta_antes_dos_novos_trechos(self):
        eventos = []
        with patch.object(motor, 'agente_auditor_factual', return_value=parecer()), \
             patch.object(motor, 'agente_auditor_metodologico', return_value=parecer(status='CONTROVERSO')):
            self.consulta(rodadas=2, callback=eventos.append)
        respostas = [e for e in eventos if e['tipo'] == 'resposta']
        self.assertEqual([e['texto'] for e in respostas], ['Resposta', '', 'Resposta'])
        self.assertEqual(respostas[1]['estado'], 'gerando')

    def test_microfone_sem_transcritor_nao_chama_modelo_com_ferramentas(self):
        with patch.object(motor.shutil, 'which', side_effect=lambda nome: '/bin/'+nome if nome in ('pw-record', 'agy') else None), \
             patch.object(motor, 'Path') as caminho, \
             patch.object(motor.subprocess, 'Popen') as gravador, \
             patch.object(motor.subprocess, 'run') as executar_programa, \
             patch('builtins.input', return_value=''), contextlib.redirect_stdout(io.StringIO()):
            caminho.return_value.stat.return_value.st_size = 2048
            self.assertEqual(motor.ouvir_microfone(), '')
        gravador.assert_called_once()
        executar_programa.assert_not_called()

    def test_busca_sem_fontes_nao_inventa_aprovacao(self):
        with patch.object(motor, 'agente_pesquisador', return_value={'fontes': [], 'texto': ''}), \
             patch.object(motor, 'agente_auditor_factual') as auditor:
            # Não use consulta(), que instala uma busca simulada própria.
            with patch.object(motor, 'agente_pescador', return_value=(True, 'Resposta')):
                r = motor.processar_consulta('Pergunta', callback=lambda e: None)
        auditor.assert_not_called(); self.assertEqual(r['estado'], 'indisponivel')

    def test_verificacao_reutiliza_resposta(self):
        self.consulta(rapido=True, sessao_id='verificar')
        with patch.object(motor, 'agente_pescador') as autor, \
             patch.object(motor, 'agente_auditor_factual', return_value=parecer()), \
             patch.object(motor, 'agente_auditor_metodologico', return_value=parecer()):
            fontes = {'fontes': [{'url': 'https://exemplo.org', 'titulo': 'Fonte', 'snippet': 'Trecho'}], 'texto': 'Evidência'}
            with patch.object(motor, 'agente_pesquisador', return_value=fontes):
                r = motor.processar_consulta('', sessao_id='verificar', verificar_ultimo=True, callback=lambda e: None)
        autor.assert_not_called(); self.assertEqual(r['estado'], 'verificado')
        self.assertEqual(len(motor.carregar_sessao('verificar')['turnos']), 1)

    def test_cancelar_verificacao_preserva_id_da_avaliacao(self):
        anterior = self.consulta(rapido=True, sessao_id='cancelar-verificacao')
        cancelar_evento = threading.Event()
        def cancelar(*args):
            cancelar_evento.set()
            raise ConsultaCancelada()
        with patch.object(motor, 'agente_pesquisador', return_value={'fontes': [{'url':'https://exemplo.org','titulo':'Fonte','snippet':'Trecho'}], 'texto':'Evidência'}), \
             patch.object(motor, 'agente_auditor_factual', side_effect=cancelar):
            r = motor.processar_consulta('', sessao_id='cancelar-verificacao', verificar_ultimo=True,
                                         callback=lambda e: None, cancelar=cancelar_evento)
        self.assertEqual(anterior['estado'], 'nao_verificado')
        self.assertEqual(r['estado'], 'cancelado')
        self.assertNotEqual(anterior['id'], r['id'])

    def test_sessao_rejeita_traversal_e_links(self):
        for nome in ('../fora', '/tmp/fora', '..', '', 'a/b'):
            with self.assertRaises(ValueError): motor.carregar_sessao(nome)
        motor.SESSOES_DIR.mkdir(exist_ok=True)
        link = motor.SESSOES_DIR/'link.json'
        link.symlink_to(Path(TEMP.name)/'fora.json')
        with self.assertRaises(ValueError): motor.salvar_sessao({'id':'link', 'turnos':[]})

    def test_historico_nao_segue_link_simbolico(self):
        destino = Path(TEMP.name)/'historico-fora.jsonl'
        destino.write_text('protegido')
        motor.HISTORICO_ARQ.unlink(missing_ok=True)
        motor.HISTORICO_ARQ.symlink_to(destino)
        motor.salvar_historico({'id':'teste'})
        self.assertEqual(destino.read_text(), 'protegido')
        motor.HISTORICO_ARQ.unlink()

    def test_nota_painel_preserva_zero_e_ausencia(self):
        arvore = ast.parse((RAIZ/'default/painel/coletor.py').read_text())
        func = next(n for n in arvore.body if isinstance(n, ast.FunctionDef) and n.name == 'nota_pesquisa')
        env = {}; exec(compile(ast.Module(body=[func], type_ignores=[]), 'nota', 'exec'), env)
        nota = env['nota_pesquisa']
        self.assertEqual(nota({}, {'grau_fato':0}), 0)
        self.assertIsNone(nota({'estado':'nao_verificado'}, {'grau_fato':100}))
        self.assertIsNone(nota({}, {'grau_fato':100,'veredito_resumo':'sem auditoria'}))

    def test_execucao_streaming_e_cancelamento(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d); (raiz/'bin').mkdir()
            launcher = raiz/'bin/jangada-pescador-modelo'
            launcher.write_text('''#!/usr/bin/env python3
import json, os, sys, time
sys.stdin.read()
print(json.dumps({'type':'stream_event','event':{'delta':{'type':'text_delta','text':'Olá ç'}}}),flush=True)
if os.environ.get('TESTE_CANCELAR'): time.sleep(30)
print(json.dumps({'type':'assistant','message':{'content':[{'type':'text','text':'Olá ç'}]}}),flush=True)
print(json.dumps({'type':'result','subtype':'success','result':'Olá ç'}),flush=True)
''')
            launcher.chmod(0o755)
            eventos = []; ctx = Contexto(eventos.append); token = CONTEXTO.set(ctx)
            try:
                with patch.dict(os.environ, JANGADA_PATH=d):
                    ok, texto = executar('claude', 'claude', 'pedido', transmitir=True)
                self.assertTrue(ok); self.assertEqual(texto, 'Olá ç')
                self.assertEqual([e['texto'] for e in eventos], ['Olá ç'])
                ctx.callback = lambda e: ctx.cancelar.set()
                with patch.dict(os.environ, JANGADA_PATH=d, TESTE_CANCELAR='1'):
                    with self.assertRaises(ConsultaCancelada): executar('claude', 'claude', 'pedido', transmitir=True)
                self.assertEqual(ctx.rascunho, 'Olá ç')
            finally: CONTEXTO.reset(token)

    def test_cancelamento_encerra_filho_que_ignora_sigterm(self):
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d); (raiz/'bin').mkdir()
            launcher = raiz/'bin/jangada-pescador-modelo'
            pid_arquivo = raiz/'filho.pid'
            launcher.write_text('''#!/usr/bin/env python3
import json, os, subprocess, sys, time
sys.stdin.read()
filho = subprocess.Popen([sys.executable, '-c', "import os, signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); open(os.environ['TESTE_PID'], 'w').write(str(os.getpid())); time.sleep(30)"])
while not os.path.exists(os.environ['TESTE_PID']): time.sleep(0.01)
print(json.dumps({'type':'stream_event','event':{'delta':{'type':'text_delta','text':'Parcial'}}}),flush=True)
time.sleep(30)
''')
            launcher.chmod(0o755)
            ctx = Contexto(); ctx.callback = lambda e: ctx.cancelar.set()
            token = CONTEXTO.set(ctx)
            try:
                with patch.dict(os.environ, JANGADA_PATH=d, TESTE_PID=str(pid_arquivo)):
                    with self.assertRaises(ConsultaCancelada): executar('claude', 'claude', 'pedido', transmitir=True)
                pid = int(pid_arquivo.read_text())
                def encerrado():
                    try: return Path(f'/proc/{pid}/stat').read_text().split()[2] == 'Z'
                    except FileNotFoundError: return True
                limite = time.monotonic() + 2
                while not encerrado() and time.monotonic() < limite: time.sleep(0.01)
                self.assertTrue(encerrado(), 'O filho do modelo ficou em execução após cancelar.')
            finally:
                CONTEXTO.reset(token)

    def test_janela_sem_servidor_grafico(self):
        try:
            from PyQt6.QtWidgets import QApplication
            from janela import Chat
        except ImportError: self.skipTest('PyQt6 não disponível')
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        app = QApplication.instance() or QApplication([])
        janela = Chat(motor)
        janela.entrada.setPlainText('Texto\ncom várias linhas')
        app.processEvents()
        self.assertEqual(janela.modo.currentText(), 'Conversar')
        self.assertFalse(janela.parar.isEnabled())
        janela.close()

    def test_janela_envia_e_cancela_consulta_real_do_motor(self):
        try:
            from PyQt6.QtWidgets import QApplication
            from PyQt6.QtCore import QEventLoop, QTimer, QProcess
            from janela import Chat
        except ImportError: self.skipTest('PyQt6 não disponível')
        os.environ['QT_QPA_PLATFORM'] = 'offscreen'
        app = QApplication.instance() or QApplication([])
        with tempfile.TemporaryDirectory() as d:
            raiz = Path(d); (raiz/'bin').mkdir()
            launcher = raiz/'bin/jangada-pescador-modelo'
            launcher.write_text('''#!/usr/bin/env python3
import json, os, sys, time
sys.stdin.read()
print(json.dumps({'type':'stream_event','event':{'delta':{'type':'text_delta','text':'Resposta parcial ç'}}}),flush=True)
if os.environ.get('TESTE_CANCELAR'): time.sleep(30)
print(json.dumps({'type':'result','subtype':'success','result':'Resposta final ç'}),flush=True)
''')
            launcher.chmod(0o755)
            (raiz/'bin/claude').write_text('#!/bin/sh\nexit 1\n'); (raiz/'bin/claude').chmod(0o755)
            def esperar(condicao):
                loop = QEventLoop(); timer = QTimer(); timer.setInterval(20)
                timer.timeout.connect(lambda: loop.quit() if condicao() else None)
                timer.start(); QTimer.singleShot(4000, loop.quit); loop.exec(); timer.stop()
                self.assertTrue(condicao(), 'A janela não recebeu o evento esperado.')
            with patch.dict(os.environ, JANGADA_PATH=d, PATH=str(raiz/'bin')+':'+os.environ['PATH']):
                janela = Chat(motor, 'teste-janela')
                janela.entrada.setPlainText('Pergunta curta'); janela.enviar()
                esperar(lambda: janela.processo.state() == QProcess.ProcessState.NotRunning)
                self.assertEqual(janela.turnos[-1]['resposta'], 'Resposta final ç')
                self.assertEqual(janela.turnos[-1]['estado'], 'nao_verificado')
                with patch.dict(os.environ, TESTE_CANCELAR='1'):
                    janela.entrada.setPlainText('Pergunta longa'); janela.enviar()
                    esperar(lambda: bool(janela.atual and janela.atual['resposta']))
                    janela.cancelar()
                    esperar(lambda: janela.processo.state() == QProcess.ProcessState.NotRunning)
                self.assertEqual(janela.atual['estado'], 'cancelado')
                self.assertEqual(janela.atual['resposta'], 'Resposta parcial ç')
                self.assertEqual(len(janela.turnos), 1)
                janela.close()


if __name__ == '__main__':
    try: unittest.main(verbosity=2)
    finally: TEMP.cleanup()
