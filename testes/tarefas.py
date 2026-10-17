"""Verifica a central com sessões fictícias, sem configuração ativa."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'menus/tarefas'))
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['JANGADA_PATH'] = str(Path(__file__).resolve().parents[1])
try:
    import PyQt6
except ImportError:
    print('PyQt6 ausente; testes gráficos da central ignorados')
    sys.exit(1 if os.environ.get('CI') else 0)
import json
import fcntl
import shutil
import subprocess
import tempfile
import time
import unittest
import uuid
from unittest.mock import patch
from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtNetwork import QLocalServer
from PyQt6.QtGui import QTextDocument, QKeySequence
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLabel, QPushButton
import dados
import janela
from janela import Janela
import central
from central import encaminhar, receber
from dados import LIMITE, barra, idade, ler_lista, ler_observacao, pasta_sessoes, resumo_barra
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

def carga(tsv):
    sessoes = []
    for linha in tsv.splitlines():
        estado, nome, diretorio, atualizado, ramo, tarefa = linha.split('\t')
        sessoes.append(dict(nome=nome, estado=estado, dir=diretorio, atualizado=atualizado,
                            ramo=ramo, tarefa=tarefa, agente='Não informado', raiz=diretorio,
                            projeto=Path(diretorio).name or 'Sem projeto', mensagem='', desde='',
                            coordenador='dono', revisor='Não informado'))
    return json.dumps(dict(versao=1, sessoes=sessoes), ensure_ascii=False)


class Lista:
    def __init__(self, caminho):
        self.caminho = caminho

    def write_text(self, texto):
        self.caminho.write_text(texto if texto.startswith('{') else carga(texto))

    def read_text(self):
        return self.caminho.read_text()


class Interface(unittest.TestCase):

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.raiz = Path(self.pasta.name)
        self.runtime_anterior = os.environ.get('XDG_RUNTIME_DIR')
        os.environ['XDG_RUNTIME_DIR'] = str(self.raiz)
        self.estado = self.raiz / 'estado'
        self.estado.mkdir()
        ambiente = patch.dict(os.environ, JANGADA_SESSOES=str(self.estado), JANGADA_CORE_PATH=str(self.raiz))
        ambiente.start()
        self.addCleanup(ambiente.stop)
        self.bin = self.raiz / 'bin'
        self.bin.mkdir()
        self.comando = self.bin / 'jangada-agentes'
        self.observados = self.raiz / 'observados'
        self.observados.mkdir()
        (self.observados / 'aviso.json').write_text('{}')
        self.comando.write_text("#!/usr/bin/env python3\nimport pathlib, sys, json\npasta = pathlib.Path(__file__).resolve().parent.parent\nif sys.argv[1] == '--observacao-json':\n    if (pasta / 'falhar_observacao').exists():\n        print('Falha de observação simulada', file=sys.stderr)\n        sys.exit(1)\n    print(json.dumps({'versao': 1, 'caminhos': [str(pasta / 'observados'), str(pasta / 'observados' / 'aviso.json')]}))\nelif sys.argv[1] in ('--lista-json',):\n    if (pasta / 'falhar').exists():\n        print('Erro de consulta simulado', file=sys.stderr)\n        sys.exit(1)\n    dados = json.loads((pasta / 'lista').read_text())\n    if (pasta / 'apresentacao.json').exists():\n        detalhe = json.loads((pasta / 'apresentacao.json').read_text())\n        for sessao in dados['sessoes']:\n            if sessao['nome'] == 'projeto--um':\n                sessao.update(detalhe)\n                sessao['projeto'] = pathlib.Path(sessao['raiz']).name\n    print(json.dumps(dados, ensure_ascii=False))\nelif sys.argv[1] == '--contexto-json':\n    contexto = pasta / ('contexto-' + sys.argv[2])\n    print(contexto.read_text() if contexto.exists() else json.dumps({'versao': 1, 'sessao': sys.argv[2], 'tarefa': '', 'parecer': None}))\nelif sys.argv[1] == '--previa':\n    previa = pasta / ('previa-' + sys.argv[2])\n    print(previa.read_text() if previa.exists() else 'Atividade da sessão ' + sys.argv[2])\nelse:\n    (pasta / 'acao.json').write_text(json.dumps(sys.argv[1:]))\n")
        self.comando.chmod(448)
        self.criar_comando = self.bin / 'jangada-agente'
        self.criar_comando.write_text(self.comando.read_text().replace(
            "if sys.argv[1] in ('--lista-json',):",
            "if sys.argv[1] == '--capacidades-json':\n    perfis = (pasta / 'perfis.json').read_text() if (pasta / 'perfis.json').exists() else '[]'\n    principais = (pasta / 'principais.json').read_text() if (pasta / 'principais.json').exists() else '[{\"nome\": \"claude\", \"instalado\": true}, {\"nome\": \"codex\", \"instalado\": true}]'\n    print('{\"principais\": ' + principais + ', \"perfis\": ' + perfis + '}')\nelif sys.argv[1] in ('--lista-json',):"))
        self.criar_comando.chmod(448)
        self.lista = Lista(self.raiz / 'lista')
        self.lista.write_text('aguardando\tprojeto--um\t/tmp/projeto\thoje\tagente/um\tTarefa um\ntrabalhando\tprojeto--dois\t/tmp/projeto\thoje\tagente/dois\tTarefa dois\n')
        (self.raiz / 'apresentacao.json').write_text(json.dumps({'agente': 'codex', 'tarefa': "<img src='https://exemplo/imagem'>", 'raiz': '/tmp/projeto', 'mensagem': '<b>Texto puro</b>'}))
        self.janela = Janela(True, self.raiz, self.estado)
        self.janela.timer.stop()
        self.esperar_consulta()

    def esperar_consulta(self):
        aguardar(lambda: self.janela.consulta.state() == QProcess.ProcessState.NotRunning)
        aguardar(lambda: self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)

    def test_parser_de_observacao_valida_referencias_opacas_e_recusa_entrada_invalida(self):
        caminhos = ['/fora/do/estado/arquivo.json', '/referencia/opaca']
        self.assertEqual(ler_observacao(json.dumps({'versao': 1, 'caminhos': caminhos})), caminhos)
        for dados in ({'versao': True, 'caminhos': []}, {'versao': 2, 'caminhos': []},
                      {'versao': 1, 'caminhos': [{}]},
                      {'versao': 1, 'caminhos': ['/a', '/a']},
                      {'versao': 1, 'caminhos': ['relativo']},
                      {'versao': 1, 'caminhos': ['/a\n']},
                      {'versao': 1, 'caminhos': ['/x' * 2049]},
                      {'versao': 1, 'caminhos': ['/a'] * 4097}):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                ler_observacao(json.dumps(dados))
        with self.assertRaises(ValueError):
            ler_observacao(json.dumps({'versao': 1, 'caminhos': ['/x' * 200000]}))

    def test_marca_carrega_com_transparencia_e_preserva_titulo_quando_ausente(self):
        marcas = [rotulo for rotulo in self.janela.findChildren(QLabel)
                  if rotulo.accessibleName() == 'Jangada']
        self.assertEqual(len(marcas), 1)
        imagem = marcas[0].pixmap().toImage()
        self.assertEqual((imagem.width(), imagem.height()), (24, 24))
        self.assertEqual(imagem.pixelColor(0, 0).alpha(), 0)
        self.assertTrue((janela.RAIZ / 'default/logo/jangada-symbolic.svg').is_file())
        with patch.object(janela, 'QPixmap', return_value=janela.QPixmap()):
            central_sem_marca = Janela(False, self.raiz, self.estado)
        try:
            central_sem_marca.show()
            APP.processEvents()
            self.assertFalse(any(rotulo.accessibleName() == 'Jangada'
                                 for rotulo in central_sem_marca.findChildren(QLabel)))
            self.assertTrue(any(rotulo.text() == 'Central de tarefas'
                                for rotulo in central_sem_marca.findChildren(QLabel)))
        finally:
            central_sem_marca.close()

    def carregar_operacional(self):
        projetos = [dict(id='a' * 64, nome='Mesmo nome', caminho='/projeto-a'),
                    dict(id='b' * 64, nome='Mesmo nome', caminho='/projeto-b')]
        dados = dict(projetos=projetos, atividades=[], sessoes=[], execucoes=[], revisoes=[], eventos=[], erros=[],
                     tarefas=[dict(id='T1', projeto=p['id'], status='QUEUED', estado='Pronta',
                                   especificacao={'pedido': '<b>Texto como dado</b>'}) for p in projetos])
        self.janela.operacional.mostrar(dados)
        return self.janela.operacional

    def test_operacional_identifica_tarefa_por_projeto_e_preserva_alvo(self):
        op = self.carregar_operacional()
        primeiro = op.lista.topLevelItem(0).child(0)
        segundo = op.lista.topLevelItem(1).child(0)
        op.lista.setCurrentItem(primeiro)
        self.assertIn('<b>Texto como dado</b>', op.detalhes.toPlainText())
        op.busca.setText('Texto como dado')
        op.buscar()
        self.assertEqual(op.detalhes.textCursor().selectedText(), 'Texto como dado')
        self.assertTrue(op.botoes['pausar'].isEnabled())
        with patch.object(op, 'executar') as executar:
            op.agir('pausar')
            self.assertEqual(executar.call_args.args[1], ['--projeto', '/projeto-a', 'T1', 'pausar'])
        op.lista.setCurrentItem(segundo)
        with patch.object(op, 'executar') as executar:
            op.agir('pausar')
            self.assertEqual(executar.call_args.args[1], ['--projeto', '/projeto-b', 'T1', 'pausar'])
        self.assertFalse(op.sessao.isEnabled())
        op.mostrar(dict(op.dados, tarefas=[]))
        self.assertFalse(op.botoes['pausar'].isEnabled())

    def test_operacional_recusa_cancelamento_e_dados_parciais(self):
        op = self.carregar_operacional()
        op.lista.setCurrentItem(op.lista.topLevelItem(0).child(0))
        with patch.object(janela.Operacional, 'executar') as executar, \
             patch('operacional.QMessageBox.exec', return_value=janela.QMessageBox.StandardButton.No.value):
            op.agir('cancelar')
            executar.assert_not_called()
        op.falhar('Consulta parcial')
        self.assertFalse(op.botoes['cancelar'].isEnabled())
        self.assertIn('Texto como dado', op.detalhes.toPlainText())

    def test_projeto_sem_caminho_fica_somente_leitura(self):
        op = self.carregar_operacional()
        op.dados['projetos'][0]['caminho'] = None
        op.mostrar(op.dados)
        op.lista.setCurrentItem(op.lista.topLevelItem(0).child(0))
        self.assertIn('Texto como dado', op.detalhes.toPlainText())
        self.assertTrue(all(not b.isEnabled() for b in op.botoes.values()))
        for titulo in ('Nova atividade', 'Importar plano'):
            self.assertFalse(op.botoes_projeto[titulo].isEnabled())
        self.assertTrue(op.botoes_projeto['Cadastrar projeto'].isEnabled())
        with patch.object(op, 'executar') as executar:
            op.agir('pausar')
            op.atividade()
            op.importar()
            with patch('operacional.QFileDialog.getExistingDirectory', return_value='') as escolher:
                op.cadastrar()
                escolher.assert_called_once()
            executar.assert_not_called()
        op.executar('tarefa', ['--projeto', None, 'T1', 'pausar'])
        self.assertIn('Ação recusada', op.status.text())
        self.assertEqual(op.acao.state(), QProcess.ProcessState.NotRunning)

    def test_eventos_reiniciam_espera_e_consulta_operacional_dispensa_catalogos(self):
        op = self.janela.operacional
        aguardar(lambda: op.consulta.state() == QProcess.ProcessState.NotRunning)
        with patch.object(self.janela, 'preparar') as preparar:
            op.atualizar()
            self.assertEqual(preparar.call_args.args[1], ['consultar', '--todos', '--sem-catalogos'])
        aguardar(lambda: op.consulta.state() == QProcess.ProcessState.NotRunning)
        self.janela.evento_estado.stop()
        with patch.object(op, 'atualizar') as atualizar:
            for _ in range(20):
                self.janela.mudanca_estado()
            self.assertEqual(atualizar.call_count, 0)
            aguardar(lambda: atualizar.call_count == 1)

    def test_eventos_continuos_nao_adiam_atualizacao_indefinidamente(self):
        self.janela.evento_estado.stop()
        self.janela.limite_evento.stop()
        produtor = QTimer(self.janela)
        produtor.setInterval(40)
        produtor.timeout.connect(self.janela.mudanca_estado)
        chamadas = []
        inicio = time.monotonic()
        try:
            with patch.object(self.janela.operacional, 'atualizar', side_effect=lambda: chamadas.append(time.monotonic())):
                produtor.start()
                QTest.qWait(1400)
                self.assertTrue(chamadas)
                self.assertLess(chamadas[0] - inicio, 1.4)
        finally:
            produtor.stop()

    def test_modos_da_central_e_navegacao_por_teclado(self):
        self.janela.show()
        self.janela.modo.setCurrentText('Claro')
        self.assertIn(self.janela.fichas['light']['superficie'], self.janela.styleSheet())
        self.janela.modo.setFocus()
        QTest.keyClick(self.janela.modo, Qt.Key.Key_Tab)
        self.assertIsNot(APP.focusWidget(), self.janela.modo)
        self.janela.modo.setCurrentText('Escuro')
        self.assertIn(self.janela.fichas['dark']['superficie'], self.janela.styleSheet())

    def test_central_de_tarefas_acompanha_mudancas_sem_enviar_respostas(self):
        central = Janela(True, self.raiz, self.estado)
        central.timer.stop()
        try:
            aguardar(lambda: central.consulta.state() == QProcess.ProcessState.NotRunning)
            central.show()
            APP.processEvents()
            self.assertIn('Central de tarefas', central.windowTitle())
            self.assertEqual([central.abas.tabText(i) for i in range(central.abas.count())], ['Acompanhamento', 'Saída do agente', 'Detalhes', 'Rodadas', 'Entrega'])
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
            central.abrir_ferramenta('jangada-conversa')
            self.assertIn('Nenhum comando', central.status.text())
        finally:
            central.close()

    def test_lancador_da_conversa_e_painel_sem_aplicativo(self):
        with patch.object(QProcess, 'startDetached', return_value=(True, 123)) as iniciar, patch.object(self.janela, 'preparar') as preparar:
            self.janela.abrir_ferramenta('jangada-conversa')
            self.assertEqual(preparar.call_args.args[1:], ([], 'jangada-conversa'))
            self.janela.abrir_ferramenta('jangada-painel')
            self.janela.abrir_ferramenta('outro-comando')
            self.assertEqual(iniciar.call_count, 1)

    def indicadores_falso(self, saida, espera=0):
        (self.raiz / 'indicadores-saida').write_text(saida if isinstance(saida, str) else json.dumps(saida))
        comando = self.bin / 'jangada-indicadores'
        comando.write_text("#!/usr/bin/env python3\nimport pathlib, sys, time\n"
                           "pasta = pathlib.Path(__file__).resolve().parent.parent\n"
                           "assert sys.argv[1:] == ['--json']\n"
                           f"time.sleep({espera})\n"
                           "sys.stdout.write((pasta / 'indicadores-saida').read_text())\n")
        comando.chmod(0o700)

    def ler_indicadores(self):
        ind = self.janela.indicadores
        ind.atualizar()
        aguardar(lambda: ind.consulta.state() == QProcess.ProcessState.NotRunning)
        return ind

    def textos_da_aba(self, ind):
        textos = [r.text() for c in ind.cartoes.values() for r in c.rotulos.values()]
        for i in range(ind.tabela.topLevelItemCount()):
            item = ind.tabela.topLevelItem(i)
            textos += [item.text(c) for c in range(ind.tabela.columnCount())]
        return textos

    def test_indicadores_mostra_cartoes_tabela_e_nulos(self):
        sem_tokens = dict(entrada=None, saida=None, cache_lido=None, modelo=None, motivo='consumo não registrado')
        self.indicadores_falso(dict(versao=1, tarefas=[
            dict(sessao='jangada--a\x1b[31m', autor='claude', tokens=sem_tokens, rodadas=0, rodadas_sessao=2,
                 ultimo_resultado=None, delegacoes=[], segundos_revisao=0),
            dict(sessao='jangada--b', autor='codex', rodadas=2, rodadas_sessao=0, ultimo_resultado='aprovado',
                 tokens=dict(entrada=1000, saida=500, cache_lido=20000, modelo='gpt', motivo=None),
                 delegacoes=[dict(papel='leitor', destino='local')], segundos_revisao=185.4),
            dict(sessao='jangada--c', autor='claude', rodadas=1, rodadas_sessao=1, ultimo_resultado='revisar',
                 tokens=dict(entrada=3000, saida=1500, cache_lido=None, modelo='opus', motivo=None),
                 delegacoes=[], segundos_revisao=None)],
            revisores=[
                dict(revisor='agy', modelo='?', origem='sessao', pareceres=9, apontamentos=7, procedentes=0,
                     rejeitados=0, sem_classificacao=0, casos=0, casos_taxa=0, taxa_procedencia=None),
                dict(revisor='claude', modelo='sonnet', origem='protegida', pareceres=17, apontamentos=40,
                     procedentes=12, rejeitados=1, sem_classificacao=0, casos=13, casos_taxa=13,
                     taxa_procedencia=12 / 13)],
            local_vs_agy=[
                dict(papel='leitor', destino='local', origem='sessao', chamadas=4, sucesso=3, recusas=0,
                     segundos_medianos=7.5, tokens_entrada=None, tokens_saida=None, mudancas_local=1),
                dict(papel='explorador', destino='agy', origem='sessao', chamadas=10, sucesso=5, recusas=5,
                     segundos_medianos=62.0, tokens_entrada=None, tokens_saida=None, mudancas_local=0)]))
        self.janela.centrais.setCurrentWidget(self.janela.indicadores)
        ind = self.janela.indicadores
        aguardar(lambda: ind.dados is not None)
        custo = ind.cartoes['tarefas'].rotulos
        self.assertEqual(custo['numero'].text(), '3.000 tokens')
        self.assertEqual(custo['rodape'].text(), '2 de 3 tarefas com consumo medido')
        self.assertEqual(ind.tabela.topLevelItemCount(), 3)
        primeira = [ind.tabela.topLevelItem(0).text(c) for c in range(ind.tabela.columnCount())]
        self.assertEqual(primeira[0], 'jangada--a[31m')
        self.assertEqual(primeira[2:5], ['sem dado'] * 3)
        self.assertEqual(primeira[-1], 'consumo não registrado')
        self.assertEqual(ind.tabela.topLevelItem(1).text(9), '3 min 5 s')
        revisores = ind.cartoes['revisores'].rotulos
        self.assertEqual(revisores['numero'].text(), '92%')
        self.assertIn('claude, sonnet, registro protegido, 13 casos', revisores['apoio'].text())
        destinos = ind.cartoes['local_vs_agy'].rotulos
        self.assertEqual(destinos['numero'].text(), 'local 75% · agy 50%')
        self.assertIn('recusas: local 0, agy 5', destinos['apoio'].text())
        ind.cartoes['revisores'].click()
        self.assertEqual(ind.tabela.headerItem().text(0), 'Revisor')
        self.assertEqual(ind.tabela.topLevelItem(0).text(8), 'sem dado')
        self.assertEqual(ind.tabela.topLevelItem(1).text(8), '92% (13 casos)')
        self.assertEqual(ind.tabela.topLevelItem(1).text(2), 'registro protegido')
        self.assertEqual(ind.tabela.columnCount(), 9)
        ind.cartoes['local_vs_agy'].click()
        self.assertEqual(ind.tabela.columnCount(), 10)
        self.assertEqual(ind.tabela.headerItem().text(9), 'Mudanças do local')
        self.assertEqual(ind.tabela.topLevelItem(0).text(6), '7,5 s')
        self.assertEqual(ind.tabela.topLevelItem(1).text(6), '1 min 2 s')
        self.assertFalse(any('None' in t for t in self.textos_da_aba(ind)))
        self.assertFalse(ind.status.property('falha'))
        ind.cartoes['tarefas'].click()
        self.assertEqual(ind.tabela.columnCount(), 12)
        self.assertEqual(ind.tabela.headerItem().text(11), 'Motivo sem consumo')

    def test_indicadores_por_teclado_a_partir_do_botao(self):
        self.indicadores_falso(dict(versao=1, tarefas=[], local_vs_agy=[], revisores=[
            dict(revisor='claude', modelo='opus', origem='sessao', casos_taxa=2, taxa_procedencia=0.5)]))
        self.janela.show()
        QTest.qWaitForWindowExposed(self.janela)
        self.janela.activateWindow()
        self.janela.painel.click()
        ind = self.janela.indicadores
        self.assertIs(self.janela.centrais.currentWidget(), ind)
        aguardar(lambda: ind.dados is not None)
        self.assertTrue(ind.cartoes['tarefas'].hasFocus())
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Right)
        self.assertIs(APP.focusWidget(), ind.cartoes['revisores'])
        self.assertTrue(ind.cartoes['revisores'].isChecked())
        self.assertEqual(ind.tabela.headerItem().text(0), 'Revisor')
        self.assertEqual(ind.detalhe.text(), 'Detalhe: Procedência dos revisores')
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Tab)
        self.assertIs(APP.focusWidget(), ind.atualizar_botao)
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Tab)
        self.assertIs(APP.focusWidget(), ind.tabela)
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Backtab)
        QTest.keyClick(APP.focusWidget(), Qt.Key.Key_Backtab)
        self.assertIs(APP.focusWidget(), ind.cartoes['revisores'])
        folha = self.janela.styleSheet()
        self.assertIn('QPushButton#cartao:focus', folha)
        self.assertIn('QPushButton#cartao:checked', folha)

    def test_indicadores_lista_vazia(self):
        self.indicadores_falso(dict(versao=1, tarefas=[], revisores=[], local_vs_agy=[]))
        ind = self.ler_indicadores()
        self.assertIn('Ainda não há dados de indicadores', ind.status.text())
        self.assertTrue(ind.vazio.isVisibleTo(ind))
        self.assertFalse(ind.tabela.isVisibleTo(ind))
        self.assertTrue(ind.atualizar_botao.isEnabled())
        self.assertEqual(ind.tabela.topLevelItemCount(), 0)
        self.assertEqual(ind.cartoes['revisores'].rotulos['numero'].text(), 'sem dado')
        self.assertFalse(any('None' in t for t in self.textos_da_aba(ind)))

    def test_indicadores_comando_ausente(self):
        ind = self.ler_indicadores()
        self.assertIn('Comando jangada-indicadores não encontrado', ind.status.text())
        self.assertIn('jangada-core', ind.status.text())
        self.assertTrue(ind.status.property('falha'))
        self.assertIsNone(ind.dados)
        self.assertEqual(ind.consulta.state(), QProcess.ProcessState.NotRunning)
        self.janela.centrais.setCurrentIndex(0)
        self.assertTrue(self.janela.dados_validos)

    def test_indicadores_saida_invalida_versao_e_prazo_mantem_leitura(self):
        self.indicadores_falso(dict(versao=1, tarefas=[], revisores=[
            dict(revisor='claude', modelo='opus', origem='sessao', casos_taxa=2, taxa_procedencia=0.5)],
            local_vs_agy=[]))
        ind = self.ler_indicadores()
        self.assertEqual(ind.cartoes['revisores'].rotulos['numero'].text(), '50%')
        for saida, aviso in (('não é JSON', 'não é JSON válido'),
                             (dict(versao=2, tarefas=[], revisores=[], local_vs_agy=[]), 'Versão 2'),
                             (dict(versao=1, tarefas={}, revisores=[], local_vs_agy=[]), 'listas esperadas'),
                             ('{"versao": 1, "tarefas": [], "local_vs_agy": [], "revisores": ['
                              '{"casos_taxa": 1e999, "taxa_procedencia": NaN}]}', 'não é JSON válido'),
                             (dict(versao=1, tarefas=[], revisores=[], local_vs_agy=[
                                 dict(destino='local', chamadas=1, sucesso=10 ** 400)]), 'formato inesperado')):
            self.indicadores_falso(saida)
            self.ler_indicadores()
            self.assertIn(aviso, ind.status.text())
            self.assertIn('leitura anterior', ind.status.text())
            self.assertTrue(ind.status.property('falha'))
            self.assertEqual(ind.cartoes['revisores'].rotulos['numero'].text(), '50%')
        self.indicadores_falso(dict(versao=1, local_vs_agy=[], tarefas=[dict(sessao=[], tokens=[], delegacoes={})],
                                    revisores=[dict(revisor={}, origem=[], casos_taxa='2', taxa_procedencia=2)]))
        self.ler_indicadores()
        self.assertFalse(ind.status.property('falha'))
        self.assertEqual(ind.cartoes['revisores'].rotulos['numero'].text(), 'sem dado')
        self.assertEqual({ind.tabela.topLevelItem(0).text(c) for c in range(12)} - {''}, {'sem dado'})
        self.indicadores_falso(dict(versao=1, tarefas=[], revisores=[], local_vs_agy=[]), espera=5)
        ind.prazo_ms = 300
        ind.atualizar()
        self.assertIn('Carregando', ind.status.text())
        self.assertFalse(ind.atualizar_botao.isEnabled())
        aguardar(lambda: ind.consulta.state() == QProcess.ProcessState.NotRunning)
        self.assertIn('Tempo esgotado', ind.status.text())
        self.assertIn('leitura anterior', ind.status.text())
        self.assertTrue(ind.atualizar_botao.isEnabled())
        self.assertTrue(self.janela.nova.isEnabled())

    def test_indicadores_simulados_nao_consultam(self):
        simulada = Janela()
        try:
            simulada.centrais.setCurrentWidget(simulada.indicadores)
            self.assertIn('Simulação', simulada.indicadores.status.text())
            self.assertEqual(simulada.indicadores.consulta.state(), QProcess.ProcessState.NotRunning)
            self.assertFalse(simulada.indicadores.atualizar_botao.isEnabled())
        finally:
            simulada.close()

    def tarefa_indicador(self, sessao, **campos):
        return dict(dict(sessao=sessao, autor='claude', rodadas=2, rodadas_sessao=1, ultimo_resultado='aprovado',
                         tokens=dict(entrada=1000, saida=500, cache_lido=None, modelo='opus', motivo=None),
                         delegacoes=[], segundos_revisao=65), **campos)

    def contexto_falso(self, sessao, parecer=None, bruto=None):
        (self.raiz / ('contexto-' + sessao)).write_text(bruto if bruto is not None else json.dumps(
            dict(versao=1, sessao=sessao, tarefa='Tarefa', parecer=parecer)))

    def linha_de_custo(self, sessao):
        ind = self.janela.indicadores
        self.janela.centrais.setCurrentWidget(ind)
        aguardar(lambda: ind.dados is not None and ind.consulta.state() == QProcess.ProcessState.NotRunning)
        linhas = [ind.tabela.topLevelItem(i) for i in range(ind.tabela.topLevelItemCount())]
        return ind, next(item for item in linhas if item.text(0) == sessao)

    def abrir_rodadas(self):
        rod = self.janela.rodadas
        if not self.janela.isVisible():
            self.janela.show()
            QTest.qWaitForWindowExposed(self.janela)
        self.janela.activateWindow()
        QTest.keyClick(self.janela, Qt.Key.Key_4, Qt.KeyboardModifier.AltModifier)
        self.assertIs(self.janela.abas.currentWidget(), rod)
        aguardar(lambda: not rod.consulta_indicadores.ocupada() and not rod.consulta_parecer.ocupada())
        return rod

    def textos_rodadas(self, rod):
        return ([r.text() for r in rod.valores.values()]
                + [rod.status.text(), rod.status_rodadas.text(), rod.status_parecer.text(),
                   rod.titulo_parecer.text(), rod.parecer.toPlainText()])

    def test_rodadas_do_indicador_a_sessao_existente_com_parecer(self):
        self.indicadores_falso(dict(versao=1, tarefas=[self.tarefa_indicador('projeto--dois')],
                                    revisores=[], local_vs_agy=[]))
        self.contexto_falso('projeto--dois', dict(rodada=3, origem='validacao-projeto--dois-r3.md',
                                                  texto='STATUS: APROVADO\n\x1b[31mSem apontamentos\u202e.\tfim'))
        self.janela.show()
        QTest.qWaitForWindowExposed(self.janela)
        self.janela.activateWindow()
        self.assertEqual(self.janela.selecionada(), 'projeto--um')
        ind, item = self.linha_de_custo('projeto--dois')
        ind.tabela.setFocus()
        ind.tabela.setCurrentItem(item)
        QTest.keyClick(ind.tabela, Qt.Key.Key_Return)
        self.assertEqual(self.janela.centrais.currentIndex(), 0)
        self.assertEqual(self.janela.selecionada(), 'projeto--dois')
        self.assertIs(APP.focusWidget(), self.janela.lista)
        self.assertFalse(self.janela.aviso_encerrada.isVisibleTo(self.janela))
        self.assertTrue(self.janela.abrir.isEnabled())
        self.janela.lista.setCurrentItem(self.janela.itens['projeto--um'])
        ind, item = self.linha_de_custo('projeto--dois')
        ponto = ind.tabela.visualItemRect(item).center()
        QTest.mouseClick(ind.tabela.viewport(), Qt.MouseButton.LeftButton, pos=ponto)
        QTest.mouseDClick(ind.tabela.viewport(), Qt.MouseButton.LeftButton, pos=ponto)
        self.assertEqual(self.janela.centrais.currentIndex(), 0)
        self.assertEqual(self.janela.selecionada(), 'projeto--dois')
        rod = self.abrir_rodadas()
        self.assertEqual(rod.valores['rodadas'].text(), '2')
        self.assertEqual(rod.valores['rodadas_sessao'].text(), '1')
        self.assertEqual(rod.valores['ultimo_resultado'].text(), 'aprovado')
        self.assertEqual(rod.valores['segundos_revisao'].text(), '1 min 5 s')
        self.assertEqual(rod.valores['tokens'].text(), '1.000 e 500')
        self.assertEqual(rod.titulo_parecer.text(), 'Último parecer, rodada 3')
        self.assertEqual(rod.parecer.toPlainText(), 'STATUS: APROVADO\n[31mSem apontamentos.\tfim')
        self.assertTrue(rod.parecer.isReadOnly())
        self.assertIn('não aprova nem executa', rod.status.text())
        self.assertFalse(any('None' in t for t in self.textos_rodadas(rod)))
        self.assertEqual([b.text() for b in rod.findChildren(QPushButton)], ['Atualizar rodadas'])
        self.assertIn('QLabel#aviso_encerrada', self.janela.styleSheet())
        self.janela.modo.setCurrentIndex(1 - self.janela.modo.currentIndex())
        self.assertIn(self.janela.fichas['light' if self.janela.modo.currentIndex() else 'dark']['atencao'],
                      self.janela.styleSheet())

    def test_rodadas_sessao_encerrada_mostra_registro_e_aviso(self):
        self.indicadores_falso(dict(versao=1, revisores=[], local_vs_agy=[], tarefas=[self.tarefa_indicador(
            'projeto--velho', tokens=dict(entrada=None, saida=None, cache_lido=None, modelo=None,
                                          motivo='consumo não registrado'), ultimo_resultado=None)]))
        self.janela.show()
        QTest.qWaitForWindowExposed(self.janela)
        ind, item = self.linha_de_custo('projeto--velho')
        ind.tabela.setCurrentItem(item)
        QTest.keyClick(ind.tabela, Qt.Key.Key_Enter)
        self.assertEqual(self.janela.centrais.currentIndex(), 0)
        self.assertIsNone(self.janela.selecionada())
        self.assertTrue(self.janela.aviso_encerrada.isVisibleTo(self.janela))
        self.assertIn('encerrada', self.janela.status.text())
        self.assertEqual(self.janela.nome.text(), 'projeto--velho')
        detalhe = self.janela.detalhes.toPlainText()
        self.assertIn('Estado: encerrada', detalhe)
        self.assertIn('Motivo sem consumo: consumo não registrado', detalhe)
        self.assertIn('Último resultado: sem dado', detalhe)
        self.assertNotIn('None', detalhe)
        for botao in (self.janela.abrir, self.janela.integrar, self.janela.integrar_terminal, self.janela.encerrar):
            self.assertFalse(botao.isEnabled())
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertTrue(self.janela.aviso_encerrada.isVisibleTo(self.janela))
        rod = self.abrir_rodadas()
        self.assertEqual(rod.alvo, 'projeto--velho')
        self.assertEqual(rod.valores['ultimo_resultado'].text(), 'sem dado')
        self.assertTrue(rod.valores['ultimo_resultado'].property('semdado'))
        self.assertEqual(rod.valores['tokens'].text(), 'sem dado')
        self.janela.lista.setCurrentItem(self.janela.itens['projeto--um'])
        self.assertFalse(self.janela.aviso_encerrada.isVisibleTo(self.janela))
        self.assertIsNone(self.janela.encerrada)
        self.assertEqual(rod.alvo, 'projeto--um')

    def test_rodadas_parecer_ausente_e_sessao_sem_registro(self):
        self.indicadores_falso(dict(versao=1, tarefas=[], revisores=[], local_vs_agy=[]))
        rod = self.abrir_rodadas()
        self.assertEqual(rod.alvo, 'projeto--um')
        self.assertEqual(rod.parecer.toPlainText(), 'sem dado')
        self.assertIn('Nenhum parecer registrado', rod.status_parecer.text())
        self.assertIn('ainda não têm registro', rod.status_rodadas.text())
        self.assertEqual({r.text() for r in rod.valores.values()}, {'sem dado'})
        self.assertFalse(rod.status.property('falha'))
        self.assertFalse(any('None' in t for t in self.textos_rodadas(rod)))
        self.assertIn('pareceres antigos: sem dado', ' '.join(r.text() for r in rod.findChildren(QLabel)))

    def test_rodadas_comando_ausente(self):
        rod = self.abrir_rodadas()
        self.assertIn('Comando jangada-indicadores não encontrado', rod.status_rodadas.text())
        self.assertTrue(rod.status_rodadas.property('falha'))
        self.assertTrue(rod.status.property('falha'))
        self.assertEqual(rod.valores['rodadas'].text(), 'sem dado')
        self.assertIn('Nenhum parecer registrado', rod.status_parecer.text())
        self.comando.unlink()
        rod.atualizar()
        aguardar(lambda: not rod.consulta_parecer.ocupada())
        self.assertIn('Comando jangada-agentes não encontrado', rod.status_parecer.text())
        self.assertTrue(rod.atualizar_botao.isEnabled())

    def test_rodadas_saida_invalida_e_prazo(self):
        self.indicadores_falso('não é JSON')
        self.contexto_falso('projeto--um', bruto=json.dumps(dict(versao=1, sessao='outra', parecer=None)))
        rod = self.abrir_rodadas()
        self.assertIn('não é JSON válido', rod.status_rodadas.text())
        self.assertIn('outra sessão', rod.status_parecer.text())
        self.assertTrue(rod.status.property('falha'))
        for bruto, aviso in (('{', 'não é JSON válido'),
                             (json.dumps(dict(versao=2, sessao='projeto--um')), 'Versão 2'),
                             (json.dumps(dict(versao=1, sessao='projeto--um', parecer=dict(rodada='1', origem='a', texto='b'))),
                              'formato inesperado'),
                             (json.dumps(dict(versao=1, sessao='projeto--um', parecer='texto')), 'formato inesperado')):
            self.contexto_falso('projeto--um', bruto=bruto)
            rod.atualizar()
            aguardar(lambda: not rod.consulta_parecer.ocupada())
            self.assertIn(aviso, rod.status_parecer.text())
            self.assertEqual(rod.parecer.toPlainText(), 'sem dado')
        self.indicadores_falso(dict(versao=1, tarefas=[], revisores=[], local_vs_agy=[]), espera=5)
        rod.consulta_indicadores.prazo_ms = 300
        rod.atualizar()
        self.assertIn('Carregando as rodadas', rod.status_rodadas.text())
        self.assertFalse(rod.atualizar_botao.isEnabled())
        aguardar(lambda: not rod.consulta_indicadores.ocupada())
        self.assertIn('Tempo esgotado', rod.status_rodadas.text())
        self.assertTrue(rod.atualizar_botao.isEnabled())

    def test_rodadas_resultado_de_outra_sessao_e_descartado(self):
        self.indicadores_falso(dict(versao=1, revisores=[], local_vs_agy=[],
                                    tarefas=[self.tarefa_indicador('projeto--um', rodadas=7)]), espera=0.5)
        self.contexto_falso('projeto--dois', dict(rodada=1, origem='a.md', texto='parecer dois'))
        rod = self.janela.rodadas
        self.janela.abas.setCurrentWidget(rod)
        self.assertTrue(rod.consulta_indicadores.ocupada())
        self.janela.lista.setCurrentItem(self.janela.itens['projeto--dois'])
        self.assertEqual(rod.alvo, 'projeto--dois')
        aguardar(lambda: not rod.consulta_indicadores.ocupada() and not rod.consulta_parecer.ocupada()
                 and rod.consultado == 'projeto--dois' and 'Lido' in rod.status.text())
        self.assertEqual(rod.valores['rodadas'].text(), 'sem dado')
        self.assertEqual(rod.parecer.toPlainText(), 'parecer dois')

    def test_rodadas_linha_sem_nome_valido_nao_navega(self):
        self.indicadores_falso(dict(versao=1, revisores=[], local_vs_agy=[],
                                    tarefas=[self.tarefa_indicador('../fora')]))
        ind, item = self.linha_de_custo('../fora')
        ind.abrir_tarefa(item)
        self.assertIs(self.janela.centrais.currentWidget(), ind)
        self.assertIn('nome de sessão válido', ind.status.text())

    def test_rodadas_simuladas_nao_consultam(self):
        simulada = Janela()
        try:
            simulada.abas.setCurrentWidget(simulada.rodadas)
            self.assertIn('Simulação', simulada.rodadas.status.text())
            self.assertFalse(simulada.rodadas.consulta_parecer.ocupada())
            self.assertFalse(simulada.rodadas.atualizar_botao.isEnabled())
        finally:
            simulada.close()

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

    def test_central_usa_a_pasta_de_sessoes_da_variavel(self):
        outra = self.raiz / 'sessoes'
        outra.mkdir()
        (outra / 'projeto--um.json').write_text(json.dumps({'agente': 'da-variavel'}))
        with patch.dict(os.environ, JANGADA_SESSOES=str(outra)):
            self.assertEqual(pasta_sessoes(self.estado), self.estado)
            self.assertIn('Tarefas 2', barra(Namespace(real=True, jangada=self.raiz, estado=None))['text'])
            aberta = Janela(True, self.raiz)
            aberta.timer.stop()
            try:
                aguardar(lambda: aberta.consulta.state() == QProcess.ProcessState.NotRunning)
                self.assertEqual(aberta.estado_dir, outra)
                self.assertEqual(aberta.sessoes['projeto--um'].agente, 'codex')
                self.assertNotEqual(aberta.sessoes['projeto--um'].agente, 'da-variavel')
            finally:
                aberta.close()
        with patch.dict(os.environ):
            del os.environ['JANGADA_SESSOES']
            with self.assertRaises(ValueError):
                pasta_sessoes()
            self.assertEqual(barra(Namespace(real=True, jangada=self.raiz, estado=None))['class'], 'erro')
            resultado = subprocess.run(
                [sys.executable, str(Path(central.__file__)), '--real', '--jangada', str(self.raiz)],
                capture_output=True, text=True, timeout=5)
            self.assertEqual(resultado.returncode, 1)
            self.assertIn('pasta de sessões não foi informada', resultado.stderr)

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
        registro = self.raiz / 'apresentacao.json'
        dados = json.loads(registro.read_text())
        dados['raiz'] = str(self.raiz / 'original')
        registro.write_text(json.dumps(dados))
        self.janela.atualizar()
        self.esperar_consulta()
        self.janela.nova_tarefa()
        self.assertEqual(self.janela.formulario.projeto.text(), dados['raiz'])
        sem_raiz = ler_lista(carga('ativo\tsem-raiz\t/tmp/worktree\t\t\tTarefa\n'))
        self.assertEqual(sem_raiz['sem-raiz'].raiz, '/tmp/worktree')

    def test_observador_publico_avisa_troca_atomica_fora_da_estrutura_de_estado(self):
        self.assertEqual(self.janela.timer.interval(), 30000)
        registro = self.observados / 'aviso.json'
        registro.write_text('{}')
        self.janela.observar_estado()
        aguardar(lambda: str(self.observados) in self.janela.observador.directories())
        dados = json.loads((self.raiz / 'apresentacao.json').read_text())
        dados['mensagem'] = 'Aviso recebido por evento'
        novo = registro.with_suffix('.tmp')
        (self.raiz / 'apresentacao.json').write_text(json.dumps(dados))
        novo.write_text('{}')
        novo.replace(registro)
        aguardar(lambda: 'Aviso recebido por evento' in self.janela.ultima_atividade.text())
        dados['mensagem'] = 'Segunda substituição'
        (self.raiz / 'apresentacao.json').write_text(json.dumps(dados))
        novo.write_text('{}')
        novo.replace(registro)
        aguardar(lambda: 'Segunda substituição' in self.janela.ultima_atividade.text())

    def test_falha_da_observacao_mantem_dados_e_reserva_periodica(self):
        (self.raiz / 'falhar_observacao').touch()
        anterior = dict(self.janela.sessoes)
        self.janela.observar_estado()
        aguardar(lambda: self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
        self.assertEqual(self.janela.sessoes, anterior)
        self.assertEqual(self.janela.timer.interval(), 30000)
        self.assertIn('Atualização periódica mantida', self.janela.status.text())
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertIn('Falha de observação simulada', self.janela.status.text())
        (self.raiz / 'falhar_observacao').unlink()
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertNotIn('Falha de observação simulada', self.janela.status.text())

    def test_timeout_e_limite_de_saida_da_observacao(self):
        original = self.comando.read_text()
        self.janela.observacao_limite.setInterval(30)
        lento = original.replace("    print(json.dumps({'versao': 1, 'caminhos': [",
                                "    import time\n    time.sleep(3)\n    print(json.dumps({'versao': 1, 'caminhos': [", 1)
        self.comando.write_text(lento)
        self.janela.observar_estado()
        aguardar(lambda: self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
        self.assertIn('Tempo da consulta', self.janela.observacao_falha)
        grande = original.replace("    print(json.dumps({'versao': 1, 'caminhos': [",
                                  "    sys.stdout.write('x' * (1024 * 1024 + 1))\n    sys.exit(0)\n    print(json.dumps({'versao': 1, 'caminhos': [", 1)
        self.comando.write_text(grande)
        self.janela.observacao_limite.setInterval(1000)
        self.janela.observar_estado()
        aguardar(lambda: self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
        self.assertIn('excedeu o limite', self.janela.observacao_falha)
        self.comando.write_text(original)

    def test_failed_to_start_da_consulta_de_observacao_e_persistente(self):
        with patch.object(self.janela, 'preparar',
                          side_effect=lambda processo, argumentos: processo.setProgram('/caminho/inexistente')):
            self.janela.observar_estado()
            aguardar(lambda: 'Não foi possível iniciar a consulta' in self.janela.status.text())
        self.assertIn('Atualização periódica mantida', self.janela.status.text())

    def test_recusa_parcial_de_addpaths_preserva_caminhos_anteriores(self):
        caminhos_anteriores = set(self.janela.observador.directories() + self.janela.observador.files())
        aceito = self.observados / 'novo-aceito.json'
        recusado = str(self.observados / 'novo-recusado.json')
        aceito.write_text('{}')
        self.janela.observacao_saida = bytearray(json.dumps({'versao': 1, 'caminhos':
            sorted(caminhos_anteriores | {str(aceito), recusado})}).encode())
        adicionar_caminhos = self.janela.observador.addPaths

        def aceitar_parte(caminhos):
            adicionar_caminhos([caminho for caminho in caminhos if caminho != recusado])
            return [recusado]

        with patch.object(self.janela, 'observacao_ler'):
            with patch.object(self.janela.observador, 'addPaths', side_effect=aceitar_parte):
                self.janela.observacao_fim(0, QProcess.ExitStatus.NormalExit)
        caminhos_atuais = set(self.janela.observador.directories() + self.janela.observador.files())
        self.assertTrue(caminhos_anteriores <= caminhos_atuais)
        self.assertIn(str(aceito), caminhos_atuais)
        self.assertNotIn(recusado, caminhos_atuais)
        self.assertIn('nova consulta agendada', self.janela.observacao_falha)
        self.janela.observacao_repetir.setInterval(20)
        iniciou = []
        self.janela.consulta_observacao.started.connect(lambda: iniciou.append(True))
        aguardar(lambda: iniciou and
                 self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
        self.assertFalse(self.janela.observacao_falha)

    def test_criacao_de_projeto_observado_atualiza_dados(self):
        pasta_projeto = self.observados / 'projeto-novo'
        self.janela.observar_estado()
        aguardar(lambda: str(self.observados) in self.janela.observador.directories())
        dados = json.loads(self.lista.read_text())
        dados['sessoes'].append(json.loads(carga(
            'aguardando\tprojeto--novo\t/tmp/novo\thoje\tagente/novo\tNova tarefa\n'))['sessoes'][0])
        self.lista.write_text(json.dumps(dados))
        pasta_projeto.mkdir()
        self.janela.observador.directoryChanged.emit(str(self.observados))
        aguardar(lambda: 'projeto--novo' in self.janela.sessoes)
        pasta_projeto.rmdir()

    def test_eventos_continuos_respeitam_prazo_maximo(self):
        inicio = time.monotonic()
        self.assertEqual(self.janela.evento_estado.interval(), 200)
        self.assertEqual(self.janela.limite_evento.interval(), 1000)
        self.janela.evento_estado.setInterval(80)
        self.janela.limite_evento.setInterval(250)
        pulsos = QTimer()
        pulsos.setInterval(30)
        pulsos.timeout.connect(self.janela.mudanca_estado)
        pulsos.start()
        try:
            aguardar(lambda: self.janela.consulta.state() != QProcess.ProcessState.NotRunning)
        finally:
            pulsos.stop()
            pulsos.deleteLater()
        duracao = time.monotonic() - inicio
        self.assertNotEqual(self.janela.consulta.state(), QProcess.ProcessState.NotRunning)
        self.assertGreaterEqual(duracao, 0.2)
        self.assertLess(duracao, 0.8)

    def test_abertura_real_inicia_consulta_de_observacao(self):
        chamadas = []
        iniciar_original = Janela.iniciar

        def iniciar_registrando(janela_aberta, processo, argumentos):
            if processo is janela_aberta.consulta_observacao:
                chamadas.append(argumentos)
            return iniciar_original(janela_aberta, processo, argumentos)

        with patch.object(Janela, 'iniciar', iniciar_registrando):
            aberta = Janela(True, self.raiz, self.estado)
        try:
            aguardar(lambda: aberta.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
            self.assertEqual(chamadas, [['--observacao-json']])
        finally:
            aberta.close()

    def test_pedido_de_observacao_durante_consulta_reinicia_ao_fim(self):
        original = self.comando.read_text()
        lento = original.replace("    print(json.dumps({'versao': 1, 'caminhos': [",
                                "    import time\n    time.sleep(0.2)\n    print(json.dumps({'versao': 1, 'caminhos': [", 1)
        self.comando.write_text(lento)
        chamadas = []
        self.janela.consulta_observacao.started.connect(lambda: chamadas.append(True))
        self.janela.observar_estado()
        self.janela.observar_estado()
        aguardar(lambda: len(chamadas) == 2 and
                 self.janela.consulta_observacao.state() == QProcess.ProcessState.NotRunning)
        self.comando.write_text(original)

    def test_timer_atualiza_sem_intervencao(self):
        self.lista.write_text(self.lista.read_text().replace('aguardando', 'concluido'))
        # Reduz o intervalo só neste teste.
        self.janela.timer.setInterval(30)
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

    def test_detalhe_mostra_coordenador_autor_e_revisor(self):
        # Registro antigo, sem os campos: o coordenador é o dono.
        detalhe = self.janela.detalhes.toPlainText()
        self.assertIn('Coordenador: dono\nAutor: codex\nRevisor: Não informado\n', detalhe)
        (self.raiz / 'apresentacao.json').write_text(json.dumps(
            {'agente': 'codex', 'coordenador': 'claude', 'revisor': 'agy', 'raiz': '/tmp/projeto'}))
        self.janela.atualizar()
        self.esperar_consulta()
        sessao = self.janela.sessoes['projeto--um']
        self.assertEqual((sessao.coordenador, sessao.agente, sessao.revisor), ('claude', 'codex', 'agy'))
        self.janela.atualizar()
        self.esperar_consulta()
        self.assertIn('Coordenador: claude\nAutor: codex\nRevisor: agy\n', self.janela.detalhes.toPlainText())

    def test_json_invalido_versao_tipos_e_campos_ausentes(self):
        original = json.loads(self.lista.read_text())
        for dados in ('não é JSON', dict(versao=2, sessoes=[]), dict(versao=True, sessoes=[]),
                      dict(versao=1), dict(versao=1, sessoes=[{}])):
            with self.subTest(dados=dados), self.assertRaises(ValueError):
                ler_lista(dados if isinstance(dados, str) else json.dumps(dados))
        for valor in (None, 1, [], {}):
            original['sessoes'][0]['mensagem'] = valor
            with self.subTest(valor=valor), self.assertRaises(ValueError):
                ler_lista(json.dumps(original))
        with self.assertRaises(ValueError):
            ler_lista(carga('ativo\t../../fora\t/tmp\t\t\t\n'))

    def test_consulta_independe_de_arquivos_internos(self):
        for nome in ('projeto--um', 'projeto--dois'):
            (self.estado / (nome + '.json')).write_text('registro privado inválido')
            (self.estado / (nome + '.json')).chmod(0)
        with patch('dados.os.open', side_effect=AssertionError('Leitura interna proibida')):
            self.janela.atualizar()
            self.esperar_consulta()
            self.assertTrue(self.janela.dados_validos)
            self.assertEqual(barra(Namespace(real=True, jangada=self.raiz, estado=self.estado))['class'], 'aguardando')

    def test_multilinha_unicode_sem_interpretacao_html(self):
        texto = 'ação\nsegunda linha\t雪 &lt;b&gt; <b>literal</b>'
        dados = json.loads(self.lista.read_text())
        dados['sessoes'][1].update(tarefa=texto, mensagem=texto, ramo='&lt;ramo&gt;',
                                  desde='2026-10-14T00:00:00+00:00', revisor='claude')
        self.lista.write_text(json.dumps(dados))
        self.janela.atualizar()
        self.esperar_consulta()
        sessao = self.janela.sessoes['projeto--dois']
        self.assertEqual(sessao.tarefa, texto)
        self.assertEqual(sessao.ramo, '&lt;ramo&gt;')
        self.assertEqual(sessao.inicio, dados['sessoes'][1]['desde'])
        self.assertEqual(self.janela.selecionada(), 'projeto--um')
        self.janela.mostrar(self.janela.sessoes)
        self.assertEqual(sessao.revisor, 'claude')

    def test_falhas_json_timeout_e_excesso_preservam_dados(self):
        anterior = self.janela.selecionada()
        for corpo, esperado in (("print('{\"versao\":2,\"sessoes\":[]}')", 'Versão'),
                                ("print('{\"versao\":1,\"sessoes\":[{}]}')", 'incompleta'),
                                ("print('x' * (1024 * 1024 + 1))", 'limite'),
                                ("import sys; sys.stderr.write('x' * (1024 * 1024 + 1))", 'limite'),
                                ("import sys; sys.stdout.buffer.write(b'\\xff')", 'utf-8'),
                                ("import time; time.sleep(30)", 'Tempo')):
            self.comando.write_text('#!/usr/bin/env python3\n' + corpo + '\n')
            self.janela.atualizar()
            if esperado == 'Tempo':
                self.janela.espera.start(20)
            self.esperar_consulta()
            self.assertIn(esperado, self.janela.status.text())
            self.assertEqual(self.janela.selecionada(), anterior)
            self.assertFalse(self.janela.abrir.isEnabled())
            if esperado == 'Tempo':
                with patch('dados.time.monotonic', side_effect=[0, 11]):
                    self.assertEqual(barra(Namespace(real=True, jangada=self.raiz, estado=self.estado))['class'], 'erro')
            else:
                self.assertEqual(barra(Namespace(real=True, jangada=self.raiz, estado=self.estado))['class'], 'erro')

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
        (self.raiz / 'apresentacao.json').write_text(json.dumps({'tarefa': tarefa}))
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
            {'nome': 'codex-claude', 'descricao': 'Codex implementa, Claude revisa'},
            {'nome': 'claude-codex', 'descricao': 'Claude implementa, Codex revisa'},
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
        self.assertEqual(argumentos[5:7], ['--perfil', 'codex-claude'])

    def test_catalogo_de_agentes_vem_do_jangada_agente(self):
        (self.raiz / 'principais.json').write_text(json.dumps([
            {'nome': 'claude', 'instalado': True}, {'nome': 'codex', 'instalado': False},
        ]))
        (self.raiz / 'perfis.json').write_text(json.dumps([{'nome': 'claude-codex', 'descricao': ''}]))
        self.janela.nova_tarefa()
        form = self.janela.formulario
        aguardar(lambda: form.agente.itemText(1) == 'claude-codex')
        self.assertEqual([form.agente.itemText(i) for i in range(form.agente.count())], ['claude', 'claude-codex'])
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


class RaizDoCore(unittest.TestCase):
    """Comandos do Core: raiz do ambiente, depois a do jangada-config do Core, depois o PATH."""

    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.base = Path(self.pasta.name)
        dados._raiz_core_da_configuracao.cache_clear()
        self.addCleanup(dados._raiz_core_da_configuracao.cache_clear)

    def ambiente(self, **variaveis):
        anterior = {k: v for k, v in os.environ.items() if k not in ('JANGADA_CORE_PATH', 'PATH')}
        anterior.update(variaveis)
        return patch.dict(os.environ, anterior, clear=True)

    def falso_config(self, raiz):
        pasta = self.base / 'path'
        pasta.mkdir()
        comando = pasta / 'jangada-config'
        comando.write_text(f'#!/bin/sh\necho JANGADA_PATH=/x\necho JANGADA_CORE_PATH={raiz}\n')
        comando.chmod(0o755)
        return str(pasta)

    def test_ambiente_tem_precedencia(self):
        with self.ambiente(JANGADA_CORE_PATH=str(self.base / 'core'), PATH=self.falso_config('/outra')):
            self.assertEqual(dados.raiz_core(), self.base / 'core')
            programa, extra = dados.resolver_comando('jangada-agentes', self.base / 'shell')
        self.assertEqual(programa, str(self.base / 'core/bin/jangada-agentes'))
        self.assertEqual(extra, {'JANGADA_CORE_PATH': str(self.base / 'core')})

    def test_ambiente_vazio_usa_o_jangada_config_do_core(self):
        with self.ambiente(JANGADA_CORE_PATH='', PATH=self.falso_config('/raiz/do/core')):
            self.assertEqual(dados.raiz_core(), Path('/raiz/do/core'))

    def test_sem_raiz_vai_pelo_nome_e_sem_variavel(self):
        with self.ambiente(PATH='/nao/existe'):
            self.assertIsNone(dados.raiz_core())
            self.assertEqual(dados.resolver_comando('jangada-agentes', self.base), ('jangada-agentes', {}))

    def test_comando_do_shell_sai_da_raiz_do_shell(self):
        with self.ambiente(PATH='/nao/existe'):
            programa, extra = dados.resolver_comando('jangada-terminal', self.base / 'shell')
        self.assertEqual(programa, str(self.base / 'shell/bin/jangada-terminal'))
        self.assertEqual(extra, {'JANGADA_PATH': str(self.base / 'shell')})

    def test_comando_de_fora_vai_pelo_nome_mesmo_com_raiz_do_core(self):
        with self.ambiente(JANGADA_CORE_PATH=str(self.base / 'core'), PATH='/nao/existe'), \
             patch.object(dados, 'COMANDOS_DE_FORA', frozenset({'jangada-exemplo'})):
            programa, extra = dados.resolver_comando('jangada-exemplo', self.base / 'shell')
        self.assertEqual(programa, 'jangada-exemplo')
        self.assertEqual(extra, {'JANGADA_CORE_PATH': str(self.base / 'core')})

    def test_comando_disponivel_depende_do_path(self):
        cache = Path.home() / '.cache'
        cache.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=cache) as temporaria:
            pasta = Path(temporaria)
            with self.ambiente(PATH=str(pasta)):
                self.assertFalse(dados.comando_disponivel('jangada-indicadores', self.base))
                falso = pasta / 'jangada-indicadores'
                falso.write_text('#!/bin/sh\n')
                falso.chmod(0o755)
                self.assertTrue(dados.comando_disponivel('jangada-indicadores', self.base))
            with self.ambiente(JANGADA_CORE_PATH=str(pasta)):
                (pasta / 'bin').mkdir()
                self.assertFalse(dados.comando_disponivel('jangada-agentes', self.base))
                (pasta / 'bin/jangada-agentes').write_text('#!/bin/sh\n')
                self.assertFalse(dados.comando_disponivel('jangada-agentes', self.base))
                (pasta / 'bin/jangada-agentes').chmod(0o755)
                self.assertTrue(dados.comando_disponivel('jangada-agentes', self.base))

    def test_botao_do_painel_abre_a_aba_mesmo_sem_o_comando(self):
        estado = self.base / 'estado'
        estado.mkdir()
        for real in (True, False):
            with self.ambiente(PATH='/nao/existe'):
                aberta = Janela(real, self.base, estado)
                aberta.timer.stop()
                try:
                    self.assertIn('Conversa de Pescador', {b.text() for b in aberta.findChildren(QPushButton)})
                    self.assertEqual(aberta.centrais.tabText(2), 'Indicadores')
                    aberta.painel.click()
                    self.assertIs(aberta.centrais.currentWidget(), aberta.indicadores)
                    if real:
                        self.assertIn('não encontrado', aberta.indicadores.status.text())
                finally:
                    aberta.close()


class Links(unittest.TestCase):

    def test_visual_e_logo_com_pastas_acessadas_por_link(self):
        repo = Path(__file__).resolve().parents[1]
        codigo = """
import sys
from pathlib import Path
raiz = Path(sys.argv[1])
# Como no lançamento pelo jangada-tarefas: o Python põe em sys.path a pasta física do script.
sys.path.insert(0, str((raiz / 'default/tarefas').resolve()))
from PyQt6.QtWidgets import QApplication, QLabel
app = QApplication([])
import janela
import visual
assert Path(janela.__file__).parent in (raiz / 'menus/tarefas', raiz / 'shell/menus/tarefas'), janela.__file__
assert Path(visual.__file__).parent == raiz / 'default/visual', visual.__file__
central = janela.Janela(False, raiz, raiz / 'estado')
central.timer.stop()
assert any(rotulo.accessibleName() == 'Jangada' and not rotulo.pixmap().isNull()
           for rotulo in central.findChildren(QLabel)), 'logo ausente'
"""
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta).resolve() / 'jangada'
            pasta_tarefas = raiz / 'menus/tarefas'
            pasta_logo = raiz / 'temas/logo'
            shutil.copytree(repo / 'menus/tarefas', pasta_tarefas,
                            ignore=shutil.ignore_patterns('__pycache__'))
            shutil.copytree(repo / 'default/logo', pasta_logo)
            shutil.copytree(repo / 'default/visual', raiz / 'default/visual',
                            ignore=shutil.ignore_patterns('__pycache__'))
            (raiz / 'default').mkdir(parents=True, exist_ok=True)
            (raiz / 'default/tarefas').symlink_to('../menus/tarefas')
            (raiz / 'default/logo').symlink_to('../temas/logo')
            resultado = subprocess.run(
                [sys.executable, '-c', codigo, str(raiz)], capture_output=True, text=True, timeout=30,
                env=dict(os.environ, JANGADA_PATH=str(raiz), XDG_RUNTIME_DIR=pasta))
            self.assertEqual(resultado.returncode, 0, resultado.stderr)


if __name__ == '__main__':
    unittest.main(verbosity=2)
