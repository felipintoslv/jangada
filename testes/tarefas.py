"""Verifica a central com sessões fictícias, sem configuração ativa."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'default/tarefas'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
try:
    import PyQt6
except ImportError:
    print('PyQt6 ausente; testes gráficos da central ignorados')
    sys.exit(1 if os.environ.get('CI') else 0)
import json
import fcntl
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from PyQt6.QtCore import QProcess, Qt
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtGui import QTextDocument, QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QPushButton
import janela
from janela import Janela
import central
from central import encaminhar, receber
from dados import barra, idade, ler_lista, registro, resumo_barra
from argparse import Namespace
APP = QApplication([])

def aguardar(condicao):
    limite = time.monotonic() + 4
    while not condicao() and time.monotonic() < limite:
        APP.processEvents()
        time.sleep(0.005)
    APP.processEvents()
    if not condicao():
        raise AssertionError('O processo não terminou no prazo da verificação')

class Interface(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = Path(self.pasta.name)
        self.runtime_anterior = os.environ.get('XDG_RUNTIME_DIR')
        os.environ['XDG_RUNTIME_DIR'] = str(self.raiz)
        self.estado = self.raiz / 'estado'
        self.estado.mkdir()
        self.bin = self.raiz / 'bin'
        self.bin.mkdir()
        self.comando = self.bin / 'jangada-agentes'
        self.comando.write_text("#!/usr/bin/env python3\nimport pathlib, sys, json\npasta = pathlib.Path(__file__).resolve().parent.parent\nif sys.argv[1] in ('--lista', '--lista-atualizada'):\n    if (pasta / 'falhar').exists():\n        print('Erro de consulta simulado', file=sys.stderr)\n        sys.exit(1)\n    print((pasta / 'lista').read_text(), end='')\nelif sys.argv[1] == '--previa':\n    previa = pasta / ('previa-' + sys.argv[2])\n    print(previa.read_text() if previa.exists() else 'Atividade da sessão ' + sys.argv[2])\nelse:\n    (pasta / 'acao.json').write_text(json.dumps(sys.argv[1:]))\n")
        self.comando.chmod(448)
        self.criar_comando = self.bin / 'jangada-agente'
        self.criar_comando.write_text(self.comando.read_text().replace(
            "if sys.argv[1] in ('--lista', '--lista-atualizada'):",
            "if sys.argv[1] == '--capacidades-json':\n    perfis = (pasta / 'perfis.json').read_text() if (pasta / 'perfis.json').exists() else '[]'\n    principais = (pasta / 'principais.json').read_text() if (pasta / 'principais.json').exists() else '[{\"nome\": \"claude\", \"instalado\": true}, {\"nome\": \"codex\", \"instalado\": true}]'\n    print('{\"principais\": ' + principais + ', \"perfis\": ' + perfis + '}')\nelif sys.argv[1] in ('--lista', '--lista-atualizada'):"))
        self.criar_comando.chmod(448)
        self.lista = self.raiz / 'lista'
        self.lista.write_text('aguardando\tprojeto--um\t/tmp/projeto\thoje\tagente/um\tTarefa um\ntrabalhando\tprojeto--dois\t/tmp/projeto\thoje\tagente/dois\tTarefa dois\n')
        (self.estado / 'projeto--um.json').write_text(json.dumps({'agente': 'codex', 'tarefa': "<img src='https://exemplo/imagem'>", 'raiz': '/tmp/projeto', 'mensagem': '<b>Texto puro</b>'}))
        self.janela = Janela(True, self.raiz, self.estado)
        self.janela.timer.stop()
        self.esperar_consulta()

    def esperar_consulta(self):
        aguardar(lambda: self.janela.consulta.state() == QProcess.ProcessState.NotRunning)

    def test_central_de_tarefas_acompanha_mudancas_sem_enviar_respostas(self):
        central = Janela(True, self.raiz, self.estado)
        central.timer.stop()
        try:
            aguardar(lambda: central.consulta.state() == QProcess.ProcessState.NotRunning)
            central.show()
            APP.processEvents()
            self.assertIn('Central de tarefas', central.windowTitle())
            self.assertEqual([central.abas.tabText(i) for i in range(central.abas.count())], ['Acompanhamento', 'Saída do agente', 'Detalhes', 'Entrega'])
            self.assertFalse(hasattr(central, 'resposta'))
            self.assertIn('1 precisa da sua resposta', central.cartoes.text())
            self.assertIn('<b>Texto puro</b>', central.ultima_atividade.text())
            self.assertIn('Precisa da sua resposta', central.situacao.text())
            original = central.linha_tempo.toPlainText()
            central.mostrar(central.sessoes)
            self.assertEqual(central.linha_tempo.toPlainText(), original)
            self.lista.write_text(self.lista.read_text().replace('aguardando', 'concluido'))
            central.atualizar()
            aguardar(lambda: central.consulta.state() == QProcess.ProcessState.NotRunning)
            self.assertIn('Pronto para conferir', central.situacao.text())
            self.assertIn('Pronto para conferir', central.linha_tempo.toPlainText())
            self.assertEqual(central.selecionada(), 'projeto--um')
            historico = central.linha_tempo.toPlainText()
            atividade = central.ultima_atividade.text()
            central.falha('Falha de consulta')
            self.assertEqual(central.linha_tempo.toPlainText(), historico)
            self.assertEqual(central.ultima_atividade.text(), atividade)
            self.assertFalse(central.abrir.isEnabled())
        finally:
            central.close()

    def test_tarefa_reiniciada_nao_herda_eventos_da_execucao_anterior(self):
        from dataclasses import replace
        central = Janela()
        try:
            nome = central.selecionada()
            s = central.sessoes[nome]
            central.mostrar({nome: replace(s, inicio='primeira', estado='trabalhando')})
            central.mostrar({nome: replace(s, inicio='primeira', estado='interrompido')})
            self.assertIn('Interrompida', central.linha_tempo.toPlainText())
            central.mostrar({nome: replace(s, inicio='segunda', estado='trabalhando')})
            self.assertNotIn('Interrompida', central.linha_tempo.toPlainText())
            self.assertEqual(len(central.eventos[nome]), 1)
            central.abrir_ferramenta('jangada-pescador')
            self.assertIn('Nenhum comando', central.status.text())
        finally:
            central.close()

    def test_lancadores_do_painel_e_pescador(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)) as iniciar, patch.object(self.janela, 'preparar') as preparar:
            self.janela.abrir_ferramenta('jangada-pescador')
            self.assertEqual(preparar.call_args.args[1:], (['--janela'], 'jangada-pescador'))
            self.janela.abrir_ferramenta('jangada-painel')
            self.assertEqual(preparar.call_args.args[1:], ([], 'jangada-painel'))
            self.janela.abrir_ferramenta('outro-comando')
            self.assertEqual(iniciar.call_count, 2)

    def test_idade_de_atualizacao_aceita_fuso_e_rejeita_horario_invalido(self):
        from datetime import datetime
        agora = datetime.fromisoformat('2026-10-03T12:00:00+00:00')
        self.assertEqual(idade('2026-10-03T08:58:00-03:00', agora), 'Há 2 min')
        self.assertEqual(idade('2026-10-03T12:00:00+00:00', agora), 'Agora')
        self.assertEqual(idade('2026-10-03T13:00:00+00:00', agora), 'Horário futuro')
        self.assertEqual(idade('hoje', agora), 'Sem horário')

    def tearDown(self):
        self.janela.close()
        APP.processEvents()
        if self.runtime_anterior is None:
            os.environ.pop('XDG_RUNTIME_DIR', None)
        else:
            os.environ['XDG_RUNTIME_DIR'] = self.runtime_anterior
        self.pasta.cleanup()

    def test_selecao_detalhes_e_desaparecimento(self):
        self.assertEqual(self.janela.selecionada(), 'projeto--um')
        self.assertIn('<img', self.janela.detalhes.toPlainText())
        self.assertIn('<b>Texto puro</b>', self.janela.detalhes.toPlainText())
        self.lista.write_text('concluido\tprojeto--dois\t/tmp/projeto\thoje\tagente/dois\tOutra tarefa\ntrabalhando\tprojeto--um\t/tmp/projeto\thoje\tagente/um\tTarefa um\n')
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertEqual(self.janela.selecionada(), 'projeto--um')
        self.lista.write_text('concluido\tprojeto--dois\t/tmp/projeto\thoje\tagente/dois\tOutra tarefa\n')
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertIsNone(self.janela.selecionada())
        self.assertFalse(self.janela.abrir.isEnabled())
        self.assertIn('saiu da lista', self.janela.status.text())

    def test_confirmacao_grafica_mostra_sha_e_recusa_padrao(self):
        dados = dict(base_sha='a' * 40, candidate_sha='b' * 40, arquivos='arquivo.py | +2 -1',
                     marca={'reviewer': 'claude', 'independent': True}, parecer='STATUS: APROVADO',
                     validacao_local='consulte o parecer')
        with patch.object(janela.QMessageBox, 'exec', return_value=janela.QMessageBox.StandardButton.No):
            self.assertFalse(self.janela.confirmar_entrega(dados))
        texto = self.janela.entrega.toPlainText()
        self.assertIn('a' * 40, texto)
        self.assertIn('b' * 40, texto)
        self.assertIn('arquivo.py', texto)
        self.assertIn('claude', texto)
        with patch.object(janela.QMessageBox, 'exec', return_value=janela.QMessageBox.StandardButton.Yes):
            self.assertTrue(self.janela.confirmar_entrega(dados))

    def test_previa_identifica_revisor_e_independencia_como_dados_da_marca(self):
        dados = dict(base_sha='a' * 40, candidate_sha='b' * 40, arquivos='+1 -0 inteiro.py',
                     marca={'reviewer': 'codex', 'independent': True, 'base_sha': 'c' * 40},
                     marca_atual=False, parecer='STATUS: APROVADO',
                     validacao_local='marca de outra entrega; validação atual desconhecida')
        with patch.object(janela.QMessageBox, 'exec', return_value=janela.QMessageBox.StandardButton.No):
            self.janela.confirmar_entrega(dados)
        texto = self.janela.entrega.toPlainText()
        self.assertIn('Revisor da marca: codex', texto)
        self.assertIn('Marca corresponde aos SHA exibidos: Não', texto)
        self.assertIn('outra entrega', texto)

    def test_integracao_grafica_envia_so_a_entrega_confirmada(self):
        dados = dict(base_sha='a' * 40, candidate_sha='b' * 40, arquivos='teste.py | +2 -1',
                     marca={}, parecer='Sem revisão', validacao_local='Não certificada')
        self.comando.write_text(self.comando.read_text().replace(
            "elif sys.argv[1] == '--previa':",
            "elif sys.argv[1] == '--integracao-json':\n    print(" + repr(json.dumps(dados)) + ")\nelif sys.argv[1] == '--previa':"))
        fim = self.bin / 'jangada-agente-fim'
        fim.write_text('#!/usr/bin/env python3\nimport json, pathlib, sys, time\n'
                       'pathlib.Path(__file__).parent.parent.joinpath("gui.json").write_text(json.dumps(sys.argv[1:]))\n'
                       'time.sleep(.3)\n')
        fim.chmod(0o700)
        with patch.object(janela.QMessageBox, 'exec', return_value=janela.QMessageBox.StandardButton.No):
            self.janela.integrar_interface()
            aguardar(lambda: self.janela.integracao_etapa is None)
        self.assertFalse((self.raiz / 'gui.json').exists())
        with patch.object(janela.QMessageBox, 'exec', return_value=janela.QMessageBox.StandardButton.Yes):
            self.janela.integrar_interface()
            aguardar(lambda: (self.raiz / 'gui.json').exists())
            self.janela.close()
            self.assertFalse(self.janela.fechando)
            with patch.object(QProcess, 'startDetached') as terminal:
                self.janela.finalizar(True)
                terminal.assert_not_called()
            aguardar(lambda: self.janela.integracao_etapa is None)
        self.assertEqual(json.loads((self.raiz / 'gui.json').read_text()),
                         ['--integrar', '--confirmacao', 'a' * 40, 'b' * 40, 'projeto--um'])
        self.assertFalse(self.janela.pasta_finalizacao('projeto--um').exists())

    def test_botoes_acionam_a_tarefa_selecionada(self):
        self.assertEqual(self.janela.integrar.shortcut(), QKeySequence("Alt+I"))
        self.assertEqual(self.janela.encerrar.shortcut(), QKeySequence("Ctrl+X"))
        self.janela.selecionar_nome('projeto--dois')
        with patch.object(self.janela, 'solicitar_previa'), patch.object(QProcess, 'startDetached', return_value=(True, 123)), patch.object(self.janela, 'preparar') as preparar:
            self.janela.integrar_terminal.click()
            aguardar(lambda: preparar.call_count == 1)
            argumentos = preparar.call_args.args[1]
            self.assertEqual(preparar.call_args.args[2], 'jangada-terminal')
            self.assertEqual(argumentos[-3:], [str(self.bin / 'jangada-agente-fim'), '--integrar', 'projeto--dois'])
            pasta = self.janela.finalizando['projeto--dois']
            (pasta / 'inicio.json').unlink()
            pasta.rmdir()
            pasta.parent.rmdir()
            self.janela.conferir_finalizacoes()
            self.janela.encerrar.click()
            aguardar(lambda: preparar.call_count == 2)
            self.assertEqual(preparar.call_args.args[1][-2:], [str(self.bin / 'jangada-agente-fim'), 'projeto--dois'])
            self.assertEqual(preparar.call_count, 2)
            self.assertIn('Confira o resultado lá', self.janela.status.text())

    def test_finalizacao_bloqueada_sem_dados_e_na_simulacao(self):
        with patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.falha('Erro')
            self.assertFalse(self.janela.integrar.isEnabled())
            self.assertFalse(self.janela.encerrar.isEnabled())
            self.janela.finalizar(True)
            self.janela.finalizar(False)
            self.janela.mostrar({})
            self.janela.finalizar(False)
            iniciar.assert_not_called()
            simulacao = Janela()
            try:
                simulacao.finalizar(True)
                simulacao.finalizar(False)
                self.assertIn('Nenhum comando', simulacao.status.text())
                iniciar.assert_not_called()
            finally:
                simulacao.close()

    def test_finalizacao_impede_pedidos_simultaneos_e_permite_nova_tentativa(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)) as iniciar:
            self.janela.finalizar(True)
            self.janela.finalizar(True)
            self.janela.finalizar(False)
            self.assertEqual(iniciar.call_count, 1)
            self.assertFalse(self.janela.integrar.isEnabled())
            self.assertFalse(self.janela.encerrar.isEnabled())
            pasta = self.janela.finalizando['projeto--um']
            (pasta / 'inicio.json').unlink()
            pasta.rmdir()
            pasta.parent.rmdir()
            self.janela.conferir_finalizacoes()
            self.assertTrue(self.janela.encerrar.isEnabled())
            self.janela.finalizar(False)
            self.assertEqual(iniciar.call_count, 2)

    def test_reabrir_central_preserva_bloqueio_da_acao(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)) as iniciar:
            self.janela.finalizar(True)
            self.janela.close()
            outra = Janela(True, self.raiz, self.estado)
            outra.timer.stop()
            try:
                aguardar(lambda: outra.consulta.state() == QProcess.ProcessState.NotRunning)
                self.assertFalse(outra.integrar.isEnabled())
                self.assertFalse(outra.encerrar.isEnabled())
                outra.finalizar(True)
                outra.finalizar(False)
                self.assertEqual(iniciar.call_count, 1)
            finally:
                outra.close()

    def test_terminal_morto_antes_da_acao_libera_nova_tentativa(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)):
            self.janela.finalizar(True)
        pasta = self.janela.finalizando['projeto--um']
        inicio = json.loads((pasta / 'inicio.json').read_text())
        inicio['criado'] -= 11
        (pasta / 'inicio.json').write_text(json.dumps(inicio))
        with patch.object(os, 'kill', side_effect=ProcessLookupError):
            self.janela.conferir_finalizacoes()
        self.assertFalse(pasta.exists())
        self.assertTrue(self.janela.encerrar.isEnabled())

    def test_terminal_desacoplado_nao_libera_acao_que_ja_comecou(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)):
            self.janela.finalizar(True)
        pasta = self.janela.finalizando['projeto--um']
        (pasta / 'pronta').touch()
        inicio = json.loads((pasta / 'inicio.json').read_text())
        inicio['criado'] -= 11
        (pasta / 'inicio.json').write_text(json.dumps(inicio))
        with patch.object(os, 'kill', side_effect=ProcessLookupError):
            self.janela.conferir_finalizacoes()
        self.assertTrue(pasta.exists())
        self.assertFalse(self.janela.encerrar.isEnabled())

    def test_runtime_invalido_bloqueia_acoes_sem_abortar_a_janela(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': 'relativo'}), patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.selecionar()
            self.assertFalse(self.janela.integrar.isEnabled())
            self.assertFalse(self.janela.encerrar.isEnabled())
            self.janela.finalizar(True)
            self.janela.finalizar(False)
            iniciar.assert_not_called()
            self.assertIn('Ações indisponíveis', self.janela.status.text())
        self.janela.selecionar()
        self.assertTrue(self.janela.integrar.isEnabled())

    def test_terminal_atrasado_nao_usa_pasta_da_nova_tentativa(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)), patch.object(self.janela, 'preparar') as preparar:
            self.janela.finalizar(True)
            argumentos = preparar.call_args.args[1]
        pasta = self.janela.finalizando['projeto--um']
        inicio = json.loads((pasta / 'inicio.json').read_text())
        inicio['criado'] -= 11
        (pasta / 'inicio.json').write_text(json.dumps(inicio))
        with patch.object(os, 'kill', side_effect=ProcessLookupError):
            self.janela.conferir_finalizacoes()
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)):
            self.janela.finalizar(False)
        nova = self.janela.finalizando['projeto--um']
        self.assertNotEqual(nova, pasta)
        comando = self.bin / 'jangada-agente-fim'
        comando.write_text('#!/bin/sh\ntouch "' + str(self.raiz / 'executou-fim') + '"\n')
        comando.chmod(448)
        resultado = subprocess.run(argumentos[argumentos.index('-e') + 1:], input='\n', text=True, capture_output=True)
        self.assertNotEqual(resultado.returncode, 0)
        self.assertFalse((self.raiz / 'executou-fim').exists())
        self.assertTrue(nova.exists())

    def test_raiz_vazia_nao_bloqueia_a_sessao(self):
        raiz = self.janela.pasta_finalizacao('projeto--um')
        raiz.mkdir(mode=0o700)
        self.janela.selecionar()
        self.assertFalse(raiz.exists())
        self.assertTrue(self.janela.integrar.isEnabled())
        self.assertTrue(self.janela.encerrar.isEnabled())

    def test_falha_de_gravacao_remove_preparacao_incompleta(self):
        raiz = self.janela.pasta_finalizacao('projeto--um')
        with patch.object(Path, 'write_text', side_effect=OSError('disco cheio')), patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.finalizar(True)
            iniciar.assert_not_called()
        self.assertFalse(raiz.exists())
        self.assertIn('disco cheio', self.janela.status.text())
        self.janela.selecionar()
        self.assertTrue(self.janela.integrar.isEnabled())

    def test_falha_ao_criar_tentativa_remove_raiz_sem_tocar_acao_existente(self):
        raiz = self.janela.pasta_finalizacao('projeto--um')
        mkdir_original = Path.mkdir
        def criar(pasta, *args, **kwargs):
            if pasta.parent == raiz:
                raise OSError('quota excedida')
            return mkdir_original(pasta, *args, **kwargs)
        with patch.object(Path, 'mkdir', criar), patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.finalizar(False)
            iniciar.assert_not_called()
        self.assertFalse(raiz.exists())
        self.janela.selecionar()
        self.assertTrue(self.janela.encerrar.isEnabled())

    def test_aviso_de_runtime_nao_sobrescreve_erro_de_consulta(self):
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': 'relativo'}):
            self.janela.selecionar()
            self.janela.status.setText('Erro de consulta mais recente')
            self.janela.selecionar()
            self.assertEqual(self.janela.status.text(), 'Erro de consulta mais recente')
        self.janela.selecionar()
        with patch.dict(os.environ, {'XDG_RUNTIME_DIR': 'relativo'}):
            self.janela.selecionar()
            self.assertIn('Ações indisponíveis', self.janela.status.text())

    def test_registros_ambiguos_preservam_bloqueio_de_seguranca(self):
        raiz = self.janela.pasta_finalizacao('projeto--um')
        (raiz / 'primeira').mkdir(mode=0o700, parents=True)
        (raiz / 'segunda').mkdir(mode=0o700)
        self.janela.selecionar()
        with patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.finalizar(True)
            iniciar.assert_not_called()
        self.assertFalse(self.janela.integrar.isEnabled())
        self.assertTrue((raiz / 'primeira').exists())
        self.assertTrue((raiz / 'segunda').exists())

    def test_trava_de_execucao_impede_segunda_acao_no_terminal(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)), patch.object(self.janela, 'preparar') as preparar:
            self.janela.finalizar(True)
            argumentos = preparar.call_args.args[1]
        trava = Path(argumentos[argumentos.index('jangada-tarefas') + 2])
        comando = self.bin / 'jangada-agente-fim'
        comando.write_text('#!/bin/sh\ntouch "' + str(self.raiz / 'executou-fim') + '"\n')
        comando.chmod(448)
        with trava.open('w') as arquivo:
            fcntl.flock(arquivo, fcntl.LOCK_EX | fcntl.LOCK_NB)
            resultado = subprocess.run(argumentos[argumentos.index('-e') + 1:], input='\n', text=True, capture_output=True)
        self.assertEqual(resultado.returncode, 75)
        self.assertIn('Outra ação', resultado.stdout)
        self.assertFalse((self.raiz / 'executou-fim').exists())
        self.janela.conferir_finalizacoes()
        self.assertTrue(self.janela.integrar.isEnabled())

    def test_finalizacao_recusa_nome_interpretavel_como_opcao(self):
        from dataclasses import replace
        s = self.janela.sessoes['projeto--um']
        self.janela.mostrar({'--sem-revisao': replace(s, nome='--sem-revisao')})
        self.janela.selecionar_nome('--sem-revisao')
        with patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.finalizar(True)
            self.janela.finalizar(False)
            iniciar.assert_not_called()

    def test_finalizacao_bloqueada_durante_abertura(self):
        with patch.object(self.janela.acao, 'state', return_value=QProcess.ProcessState.Running), patch.object(QProcess, 'startDetached') as iniciar:
            self.janela.selecionar()
            self.assertFalse(self.janela.integrar.isEnabled())
            self.assertFalse(self.janela.encerrar.isEnabled())
            self.janela.finalizar(True)
            self.janela.finalizar(False)
            iniciar.assert_not_called()

    def test_falha_na_abertura_do_terminal_nao_anuncia_encerramento(self):
        with patch.object(QProcess, 'startDetached', return_value=(False, 0)):
            self.janela.finalizar(True)
            self.assertIn('Não foi possível', self.janela.status.text())
            self.assertIn('projeto--um', self.janela.sessoes)

    def test_ctrl_x_no_pedido_nao_encerra_sessao(self):
        self.janela.show()
        self.janela.nova_tarefa()
        formulario = self.janela.formulario
        formulario.activateWindow()
        formulario.pedido.setFocus()
        formulario.pedido.setPlainText('Pedido para recortar')
        formulario.pedido.selectAll()
        APP.processEvents()
        with patch.object(QProcess, 'startDetached') as iniciar:
            QTest.keyClick(formulario.pedido, Qt.Key.Key_X, Qt.KeyboardModifier.ControlModifier)
            self.assertEqual(formulario.pedido.toPlainText(), '')
            iniciar.assert_not_called()
        formulario.close()

    def test_terminal_preserva_argumentos_confirmacao_e_resultado(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)), patch.object(self.janela, 'preparar') as preparar:
            self.janela.finalizar(True)
            argumentos = preparar.call_args.args[1]
        inicio = argumentos.index('-e') + 1
        comando = self.bin / 'jangada-agente-fim'
        comando.write_text('#!/usr/bin/env python3\nimport json, sys\nprint(json.dumps(sys.argv[1:]))\nresposta = input("Confirmar? ")\nsys.exit(7 if resposta == "n" else 0)\n')
        comando.chmod(448)
        resultado = subprocess.run(argumentos[inicio:], input='n\n\n', text=True, capture_output=True)
        self.assertEqual(resultado.returncode, 7)
        self.assertIn('["--integrar", "projeto--um"]', resultado.stdout)
        self.assertIn('Confirmar?', resultado.stdout)
        self.janela.conferir_finalizacoes()
        self.assertFalse(self.janela.finalizando)
        self.assertTrue(self.janela.encerrar.isEnabled())

    def test_foco_argumentos_separados(self):
        self.janela.focar()
        aguardar(lambda: self.janela.acao.state() == QProcess.ProcessState.NotRunning)
        self.assertEqual(json.loads((self.raiz / 'acao.json').read_text()), ['--focar', 'projeto--um'])

    def test_erro_preserva_selecao_e_historico_sem_permitir_acao(self):
        self.janela.selecionar_nome('projeto--dois')
        historico = self.janela.linha_tempo.toPlainText()
        (self.raiz / 'falhar').touch()
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertEqual(self.janela.selecionada(), 'projeto--dois')
        self.assertEqual(self.janela.linha_tempo.toPlainText(), historico)
        self.assertFalse(self.janela.abrir.isEnabled())
        self.assertIn('Erro de consulta simulado', self.janela.status.text())
        self.janela.selecionar()
        self.assertFalse(self.janela.abrir.isEnabled())
        with patch.object(self.janela.acao, 'start') as abrir:
            self.janela.focar()
            abrir.assert_not_called()
        (self.raiz / 'falhar').unlink()
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertEqual(self.janela.selecionada(), 'projeto--dois')
        self.assertEqual(self.janela.linha_tempo.toPlainText(), historico)
        self.assertTrue(self.janela.abrir.isEnabled())

    def test_opcoes_avancadas_preservam_controles_explicitos(self):
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: form.perfis.state() == QProcess.ProcessState.NotRunning)
        form.projeto.setText(str(self.raiz))
        form.pedido.setPlainText('Aplicar controles explícitos')
        form.revisor.setCurrentText('agy')
        form.seguranca.setCurrentIndex(1)
        form.delegacao.setCurrentText('local')
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)), patch.object(self.janela, 'preparar') as preparar:
            form.criar()
        args = preparar.call_args.args[1]
        self.assertEqual(args[-5:], ['--revisor', 'agy', '--sem-isolar', '--delegacao', 'local'])

    def test_modo_recomendado_e_opcoes_recolhidas(self):
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: form.perfis.state() == QProcess.ProcessState.NotRunning)
        self.assertEqual(form.modo.currentText(), 'Recomendado')
        self.assertTrue(form.opcoes.isHidden())
        self.assertEqual(form.recomendado, 'claude')
        form.avancadas.click()
        self.assertFalse(form.opcoes.isHidden())
        form.agente.setCurrentText('codex')
        self.assertEqual(form.modo.currentText(), 'Personalizado')
        form.avancadas.click()
        self.assertTrue(form.opcoes.isHidden())
        self.assertEqual(form.agente.currentText(), 'codex')

    def test_nova_tarefa_sugere_raiz_em_vez_de_worktree(self):
        registro = self.estado / 'projeto--um.json'
        dados = json.loads(registro.read_text())
        dados['raiz'] = str(self.raiz / 'original')
        registro.write_text(json.dumps(dados))
        self.janela.atualizar()
        self.esperar_consulta()
        self.janela.nova_tarefa()
        self.assertEqual(self.janela.formulario.projeto.text(), dados['raiz'])
        sem_raiz = ler_lista('ativo\tsem-raiz\t/tmp/worktree\t\t\tTarefa\n', self.estado)
        self.assertEqual(sem_raiz['sem-raiz'].raiz, '/tmp/worktree')

    def test_observador_acompanha_substituicao_atomica(self):
        self.assertEqual(self.janela.timer.interval(), 30000)
        registro = self.estado / 'projeto--um.json'
        dados = json.loads(registro.read_text())
        dados['mensagem'] = 'Aviso recebido por evento'
        novo = registro.with_suffix('.tmp')
        novo.write_text(json.dumps(dados))
        novo.replace(registro)
        aguardar(lambda: 'Aviso recebido por evento' in self.janela.ultima_atividade.text())
        dados['mensagem'] = 'Segunda substituição'
        novo.write_text(json.dumps(dados))
        novo.replace(registro)
        aguardar(lambda: 'Segunda substituição' in self.janela.ultima_atividade.text())

    def test_timer_atualiza_sem_intervencao(self):
        self.lista.write_text(self.lista.read_text().replace('aguardando', 'concluido'))
        self.janela.timer.start()
        try:
            aguardar(lambda: self.janela.sessoes.get('projeto--um') and
                     self.janela.sessoes['projeto--um'].estado == 'concluido')
            self.assertIn('Pronto para conferir', self.janela.situacao.text())
        finally:
            self.janela.timer.stop()

    def test_atualizacao_sem_mudanca_de_ordem_preserva_itens_e_grupos(self):
        grupo = self.janela.lista.topLevelItem(0)
        item = self.janela.lista.topLevelItem(1).child(0)
        grupo.setExpanded(False)
        self.lista.write_text(self.lista.read_text().replace('Tarefa dois', 'Tarefa renomeada'))
        self.janela.atualizar()
        aguardar(lambda: self.janela.itens['projeto--dois'].text(0) == 'Tarefa renomeada')
        self.assertIs(self.janela.lista.topLevelItem(1).child(0), item)
        self.assertFalse(grupo.isExpanded())
        self.lista.write_text(self.lista.read_text().replace('trabalhando', 'interrompido'))
        self.janela.atualizar()
        aguardar(lambda: self.janela.lista.topLevelItemCount() == 2
                 and self.janela.lista.topLevelItem(1).text(0) == 'Interrompidas')
        self.assertFalse(self.janela.lista.topLevelItem(0).isExpanded())
        self.assertTrue(self.janela.lista.topLevelItem(1).isExpanded())

    def test_lista_vazia(self):
        self.lista.write_text('')
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertFalse(self.janela.sessoes)
        self.assertFalse(self.janela.abrir.isEnabled())

    def test_comando_ausente(self):
        self.comando.unlink()
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertTrue(self.janela.sessoes)
        self.assertFalse(self.janela.abrir.isEnabled())
        self.assertIn('Confira o caminho', self.janela.status.text())

    def test_registro_invalido_e_link(self):
        (self.estado / 'ruim.json').write_text('não é JSON')
        (self.estado / 'link.json').symlink_to(self.estado / 'projeto--um.json')
        self.assertEqual(registro(self.estado, 'ruim'), {})
        self.assertEqual(registro(self.estado, 'link'), {})
        resultado = ler_lista('ativo\truim\t/tmp/projeto\t\t\tSem detalhes\n', self.estado)
        self.assertEqual(resultado['ruim'].tarefa, 'Sem detalhes')
        with self.assertRaises(ValueError):
            ler_lista('ativo\t../../fora\t/tmp\t\t\t\n', self.estado)

    def test_simulacao_nao_executa(self):
        demo = Janela(False, self.raiz, self.estado)
        try:
            demo.focar()
            self.assertIn('Simulação: abriria', demo.status.text())
            self.assertFalse((self.raiz / 'acao.json').exists())
            for _ in range(3):
                demo.avancar()
            self.assertEqual(len(demo.sessoes), 3)
        finally:
            demo.close()

    def test_atencao_antes_de_projeto(self):
        self.lista.write_text('trabalhando\ta--um\t/tmp/a\thoje\t\tExecutar tarefa\naguardando\tz--um\t/tmp/z\thoje\t\tResponder dúvida\ninterrompido\ta--dois\t/tmp/a\thoje\t\tRetomar revisão\n')
        self.janela.atualizar()
        self.esperar_consulta()
        grupos = [self.janela.lista.topLevelItem(i) for i in range(3)]
        self.assertEqual([g.text(0) for g in grupos], ['Precisa da sua resposta', 'Interrompidas', 'Em execução'])
        self.assertEqual(grupos[0].child(0).text(0), 'Responder dúvida')
        self.assertEqual(grupos[0].child(0).text(1), 'z')
        self.janela.selecionar_nome('a--dois')
        self.assertEqual(self.janela.abrir.text(), 'Retomar no terminal')

    def test_tooltip_renderiza_html_da_tarefa_como_texto(self):
        tarefa = "<b>Texto</b> & <img src='https://exemplo/imagem'>\n</qt><a href='x'>Outra linha</a>"
        (self.estado / 'projeto--um.json').write_text(json.dumps({'tarefa': tarefa}))
        self.janela.atualizar()
        self.esperar_consulta()
        item = self.janela.lista.topLevelItem(0).child(0)
        documento = QTextDocument()
        documento.setHtml(item.toolTip(0))
        self.assertEqual(documento.toPlainText(), tarefa)
        self.assertIn(tarefa, self.janela.detalhes.toPlainText())

    def test_formulario_preserva_rascunho_e_valida(self):
        self.janela.nova_tarefa()
        form = self.janela.formulario
        form.projeto.setText(str(self.raiz))
        form.criar()
        self.assertIn('Escreva o pedido', form.erro.text())
        form.pedido.setPlainText('Meu pedido')
        form.projeto.setText(str(self.raiz / 'ausente'))
        form.criar()
        self.assertIn('existente', form.erro.text())
        form.hide()
        self.janela.nova_tarefa()
        self.assertIs(form, self.janela.formulario)
        self.assertEqual(form.pedido.toPlainText(), 'Meu pedido')
        self.assertFalse((self.raiz / 'acao.json').exists())

    def test_nova_pasta_cria_o_projeto_e_preenche_o_campo(self):
        base = self.raiz / 'projetos'
        with patch.dict(os.environ, {'JANGADA_PROJETOS': str(base)}):
            self.janela.nova_tarefa()
        form = self.janela.formulario
        form.criar_pasta(' novo ')
        self.assertTrue((base / 'novo').is_dir())
        self.assertEqual(form.projeto.text(), str(base / 'novo'))
        form.projeto.clear()
        form.criar_pasta('novo')
        self.assertIn('já existe', form.erro.text())
        self.assertEqual(form.projeto.text(), '')
        for invalido in ('', '.oculta', '..', '../fora', 'a/b', 'a\0b'):
            form.criar_pasta(invalido)
            self.assertIn('não pode', form.erro.text())
        self.assertEqual([p.name for p in base.iterdir()], ['novo'])
        self.assertFalse((self.raiz / 'fora').exists())

    def test_nova_pasta_desligada_na_simulacao(self):
        demo = Janela(False, self.raiz, self.estado)
        try:
            demo.nova_tarefa()
            botao = next(b for b in demo.formulario.findChildren(QPushButton) if b.text() == 'Nova pasta')
            self.assertFalse(botao.isEnabled())
        finally:
            demo.close()

    def test_criar_simulada_persiste_entre_cenarios(self):
        demo = Janela(False, self.raiz, self.estado)
        try:
            demo.nova_tarefa()
            form = demo.formulario
            form.projeto.setText(str(self.raiz))
            form.agente.setCurrentText('codex')
            form.pedido.setPlainText('Minha nova tarefa\nDetalhes da execução')
            form.criar()
            nome = demo.selecionada()
            self.assertEqual(demo.sessoes[nome].tarefa, form.pedido.toPlainText())
            self.assertEqual(demo.sessoes[nome].agente, 'codex')
            self.assertFalse(form.enviar.isEnabled())
            for _ in range(4):
                demo.avancar()
            self.assertIn(nome, demo.sessoes)
            self.assertEqual(demo.selecionada(), nome)
            self.assertFalse((self.raiz / 'acao.json').exists())
        finally:
            demo.close()

    def test_criar_real_argumentos_e_pedido_preservados(self):
        self.janela.nova_tarefa()
        form = self.janela.formulario
        self.assertEqual([form.agente.itemText(i) for i in range(form.agente.count())], ['claude', 'codex'])
        form.projeto.setText(str(self.raiz))
        form.agente.setCurrentText('codex')
        pedido = "Confira 'aspas', $(comando) e `texto`\nOutra linha: çã"
        form.pedido.setPlainText(pedido)
        form.criar()
        arquivo = self.raiz / 'acao.json'
        aguardar(arquivo.exists)
        argumentos = json.loads(arquivo.read_text())
        self.assertEqual(argumentos[:3], ['--janela', '--projeto', str(self.raiz)])
        self.assertEqual(argumentos[3], '--nome')
        self.assertRegex(argumentos[4], '^tarefa-[a-f0-9]{12}$')
        self.assertEqual(argumentos[5:], ['--agente', 'codex', '--prompt', pedido])
        self.assertEqual(form.pedido.toPlainText(), pedido)
        self.assertIn('Abertura solicitada', form.erro.text())
        self.assertFalse(form.enviar.isEnabled())

    def test_perfil_preserva_escolha_de_revisor_e_delegacao_no_lancamento(self):
        (self.raiz / 'perfis.json').write_text(json.dumps([
            {'nome': 'codex-agy', 'descricao': 'Codex implementa, agy revisa'},
            {'nome': 'claude-claude', 'descricao': 'Claude implementa e revisa'},
        ]))
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: form.agente.count() == 4)
        form.agente.setCurrentIndex(2)
        form.projeto.setText(str(self.raiz))
        form.pedido.setPlainText('Executar com o perfil escolhido')
        form.criar()
        arquivo = self.raiz / 'acao.json'
        aguardar(arquivo.exists)
        argumentos = json.loads(arquivo.read_text())
        self.assertEqual(argumentos[:3], ['--janela', '--projeto', str(self.raiz)])
        self.assertEqual(argumentos[5:7], ['--perfil', 'codex-agy'])

    def test_catalogo_de_agentes_vem_do_jangada_agente(self):
        (self.raiz / 'principais.json').write_text(json.dumps([
            {'nome': 'claude', 'instalado': True}, {'nome': 'codex', 'instalado': False},
        ]))
        (self.raiz / 'perfis.json').write_text(json.dumps([{'nome': 'claude-agy', 'descricao': ''}]))
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: form.agente.itemText(1) == 'claude-agy')
        self.assertEqual([form.agente.itemText(i) for i in range(form.agente.count())], ['claude', 'claude-agy'])
        self.assertNotIn('agy', [form.agente.itemText(i) for i in range(form.agente.count())])

    def test_catalogo_com_agente_fora_do_formato_e_recusado(self):
        (self.raiz / 'principais.json').write_text(json.dumps([{'nome': 'agy'}]))
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: 'Não foi possível consultar' in form.aviso.text())
        self.assertEqual([form.agente.itemText(i) for i in range(form.agente.count())], ['claude', 'codex'])

    def test_falha_de_consulta_preserva_agentes_simples(self):
        (self.raiz / 'perfis.json').write_text('inválido')
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: 'Não foi possível consultar' in form.aviso.text())
        self.assertEqual([form.agente.itemText(i) for i in range(form.agente.count())], ['claude', 'codex'])

    def test_criar_comando_ausente_permite_tentar_novamente(self):
        self.criar_comando.unlink()
        self.janela.nova_tarefa()
        form = self.janela.formulario
        form.modo.setCurrentText('Personalizado')
        form.projeto.setText(str(self.raiz))
        form.pedido.setPlainText('Pedido preservado')
        form.criar()
        self.assertIn('Não foi possível iniciar', form.erro.text())
        self.assertEqual(form.pedido.toPlainText(), 'Pedido preservado')
        self.assertTrue(form.enviar.isEnabled())

    def test_waybar_estados_erro_e_texto_escapado(self):
        args = Namespace(real=True, jangada=self.raiz, estado=self.estado)
        resultado = barra(args)
        self.assertEqual(resultado['class'], 'aguardando')
        self.assertIn('Tarefas 2', resultado['text'])
        self.assertIn('1 precisa da sua resposta', resultado['text'])
        self.assertNotIn('<img', resultado['tooltip'])
        self.lista.write_text('')
        self.assertEqual(barra(args)['class'], 'vazio')
        (self.raiz / 'falhar').touch()
        self.assertEqual(barra(args)['class'], 'erro')
        self.assertIn('erro', barra(args)['text'])
        self.assertEqual(resumo_barra({})['text'], 'Tarefas 0')

    def test_segundo_clique_reutiliza_janela_e_abre_formulario(self):
        servidor = QLocalServer(APP)
        nome = str(self.raiz / ('jangada-teste-' + uuid.uuid4().hex))
        self.assertTrue(servidor.listen(nome))
        servidor.newConnection.connect(lambda: receber(servidor, self.janela))
        try:
            self.assertTrue(encaminhar(nome, nova=True))
            aguardar(lambda: self.janela.formulario is not None)
            form = self.janela.formulario
            form.pedido.setPlainText('Rascunho do primeiro clique')
            form.hide()
            self.assertTrue(encaminhar(nome, nova=True))
            aguardar(form.isVisible)
            self.assertIs(form, self.janela.formulario)
            self.assertEqual(form.pedido.toPlainText(), 'Rascunho do primeiro clique')
        finally:
            servidor.close()
            servidor.deleteLater()

    def test_soquete_sem_confirmacao_nao_indica_sucesso(self):
        servidor = QLocalServer(APP)
        nome = str(self.raiz / 'sem-confirmacao')
        self.assertTrue(servidor.listen(nome))
        try:
            self.assertFalse(encaminhar(nome))
        finally:
            servidor.close()

    def test_pasta_do_soquete_rejeita_link_e_permissao_aberta(self):
        pasta = self.raiz / 'jangada-tarefas'
        pasta.rmdir()
        pasta.symlink_to(self.estado, target_is_directory=True)
        with self.assertRaises(ValueError):
            central.nome_soquete(self.raiz, self.estado, True)
        pasta.unlink()
        pasta.mkdir(mode=0o755)
        with self.assertRaises(ValueError):
            central.nome_soquete(self.raiz, self.estado, True)
        pasta.chmod(0o700)
        nome = central.nome_soquete(self.raiz, self.estado, True)
        self.assertEqual(Path(nome).parent, pasta)

    def test_importacao_interna_informa_causa_sem_pedir_qt(self):
        codigo = ('import sys, types, central; '
                  'sys.modules["janela"] = types.ModuleType("janela"); central.main()')
        resultado = subprocess.run(
            [sys.executable, '-c', codigo, '--real', '--jangada', str(self.raiz),
             '--estado', str(self.estado)], capture_output=True, text=True, timeout=5,
            env=dict(os.environ, PYTHONPATH=str(Path(central.__file__).parent)))
        self.assertNotEqual(resultado.returncode, 0)
        self.assertIn('falha ao importar janela', resultado.stderr)
        self.assertNotIn('instale python-pyqt6', resultado.stderr)

    def test_cli_waybar_sem_display(self):
        ambiente = dict(os.environ, QT_QPA_PLATFORM='inexistente')
        resposta = subprocess.run([sys.executable, str(Path(central.__file__)), '--waybar'], capture_output=True, text=True, env=ambiente, timeout=5)
        self.assertEqual(resposta.returncode, 0, resposta.stderr)
        self.assertEqual(json.loads(resposta.stdout)['class'], 'aguardando')

    def test_previa_da_selecao_antiga_nao_substitui_a_atual(self):
        self.janela.previa_alvo = ('projeto--um', 'hoje', '')
        self.janela.selecionar_nome('projeto--dois')
        self.janela.atividade.setPlainText('Atividade da segunda sessão')
        with patch.object(self.janela.previa, 'readAllStandardOutput', return_value=b'Atividade antiga'):
            self.janela.previa_fim(0, QProcess.ExitStatus.NormalExit)
        self.assertEqual(self.janela.atividade.toPlainText(), 'Atividade da segunda sessão')

    def test_previa_mostra_opcoes_no_fim_sem_perder_leitura_anterior(self):
        aguardar(lambda: self.janela.previa.state() == QProcess.ProcessState.NotRunning)
        self.janela.show()
        APP.processEvents()
        conteudo = '\n'.join([f'Etapa {i}' for i in range(60)] + ['Como continuar?', '1. Ajustar contador', '2. Ajustar janela'])
        self.janela.previa_alvo = ('projeto--um', 'hoje', '')
        with patch.object(self.janela.previa, 'readAllStandardOutput', return_value=conteudo.encode()):
            self.janela.previa_fim(0, QProcess.ExitStatus.NormalExit)
        APP.processEvents()
        barra = self.janela.atividade.verticalScrollBar()
        self.assertGreater(barra.maximum(), 0)
        self.assertEqual(barra.value(), barra.maximum())
        barra.setValue(10)
        with patch.object(self.janela.previa, 'readAllStandardOutput', return_value=(conteudo + '\nEscolha uma opção').encode()):
            self.janela.previa_fim(0, QProcess.ExitStatus.NormalExit)
        APP.processEvents()
        self.assertEqual(barra.value(), 10)

    def test_cli_reutiliza_processo_existente(self):
        pronta = self.raiz / 'pronta'
        nova = self.raiz / 'nova'
        codigo = "\nfrom pathlib import Path\nimport os\nimport janela\nimport central\nmostrar = janela.Janela.show\nformulario = janela.Janela.nova_tarefa\ndef show(self):\n    mostrar(self)\n    Path(os.environ['PILOTO_TESTE_PRONTA']).touch()\ndef nova_tarefa(self):\n    formulario(self)\n    Path(os.environ['PILOTO_TESTE_NOVA']).touch()\njanela.Janela.show = show\njanela.Janela.nova_tarefa = nova_tarefa\ncentral.main()\n"
        argumentos = ['--real', '--jangada', str(self.raiz), '--estado', str(self.estado)]
        ambiente = dict(os.environ, PILOTO_TESTE_PRONTA=str(pronta), PILOTO_TESTE_NOVA=str(nova), PYTHONPATH=str(Path(janela.__file__).parent))
        processo = subprocess.Popen([sys.executable, '-c', codigo, *argumentos], env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            aguardar(pronta.exists)
            resposta = subprocess.run([sys.executable, str(Path(central.__file__)), *argumentos, '--mostrar', '--nova'], capture_output=True, timeout=4, env=dict(os.environ, QT_QPA_PLATFORM='inexistente'))
            self.assertEqual(resposta.returncode, 0, resposta.stderr)
            aguardar(nova.exists)
            self.assertIsNone(processo.poll())
        finally:
            processo.terminate()
            try:
                processo.wait(timeout=4)
            except subprocess.TimeoutExpired:
                processo.kill()
                processo.wait(timeout=4)
if __name__ == '__main__':
    unittest.main(verbosity=2)
