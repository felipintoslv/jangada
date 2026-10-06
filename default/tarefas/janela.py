"""Janela da central de tarefas e acompanhamento das sessões."""
from dataclasses import replace
from datetime import datetime
import hashlib
import html
import json
import os
import re
from pathlib import Path
import time
import uuid

from PyQt6.QtCore import QFileSystemWatcher, QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QColor, QKeySequence, QPixmap
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout,
                            QHBoxLayout, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
                            QPlainTextEdit, QPushButton, QSplitter, QTabWidget,
                            QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from dados import (CORES, LIMITE, NOME, ORDEM, ROTULOS, Sessao,
                   estado_exibido, idade, ler_lista, simuladas)

# Só para a janela simulada e para quando a consulta falha: o catálogo vem do
# jangada-agente --capacidades-json, que também é quem valida a escolha.
AGENTES = ("claude", "codex")

GRUPOS = {'aguardando': 'Precisa da sua resposta', 'interrompido': 'Interrompidas',
          'trabalhando': 'Em execução', 'concluido': 'Pronto para conferir'}

class NovaTarefa(QDialog):

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.setWindowTitle('Nova tarefa' + ('' if janela.real else ' · Simulação'))
        self.resize(600, 440)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.projeto = QLineEdit()
        self.projeto.setPlaceholderText('Pasta do projeto')
        s = janela.sessoes.get(janela.selecionada())
        if s and janela.real:
            self.projeto.setText(s.raiz or s.dir)
        elif not janela.real:
            self.projeto.setText(str(Path.cwd()))
        escolher = QPushButton('Escolher pasta')
        escolher.clicked.connect(self.escolher_pasta)
        linha = QHBoxLayout()
        linha.addWidget(self.projeto)
        linha.addWidget(escolher)
        self.base = Path(os.environ.get('JANGADA_PROJETOS') or Path.home() / 'Projetos').expanduser()
        nova = QPushButton('Nova pasta')
        nova.setToolTip(f'Cria a pasta de um projeto novo em {self.base}' if janela.real else 'Simulação: nenhuma pasta é criada.')
        nova.setEnabled(janela.real)
        nova.clicked.connect(self.nova_pasta)
        linha.addWidget(nova)
        formulario.addRow('Projeto', linha)
        self.agente = QComboBox()
        self.agente.addItems(AGENTES)
        layout.addLayout(formulario)
        layout.addWidget(QLabel('O que precisa ser feito?'))
        self.pedido = QPlainTextEdit()
        self.pedido.setPlaceholderText('Descreva a tarefa, o resultado esperado e as restrições.')
        layout.addWidget(self.pedido)
        self.recomendado = None if janela.real else AGENTES[0]
        self.modo = QComboBox()
        self.modo.addItems(['Recomendado', 'Personalizado'])
        modo_linha = QFormLayout()
        modo_linha.addRow('Modo', self.modo)
        layout.addLayout(modo_linha)
        self.avancadas = QPushButton('Opções avançadas')
        self.avancadas.setCheckable(True)
        layout.addWidget(self.avancadas)
        self.opcoes = QWidget()
        opcoes = QFormLayout(self.opcoes)
        opcoes.addRow('Executor ou perfil', self.agente)
        self.revisor = QComboBox()
        self.revisor.addItems(['Padrão configurado', 'oposto', 'claude', 'codex', 'agy', 'mesmo'])
        opcoes.addRow('Revisor', self.revisor)
        self.seguranca = QComboBox()
        self.seguranca.addItems(['Padrão configurado', 'Sem isolamento'])
        opcoes.addRow('Segurança', self.seguranca)
        self.delegacao = QComboBox()
        self.delegacao.addItems(['Padrão configurado', 'local', 'agy', 'claude'])
        opcoes.addRow('Delegação', self.delegacao)
        layout.addWidget(self.opcoes)
        self.opcoes.hide()
        self.avancadas.toggled.connect(self.opcoes.setVisible)
        self.aviso = QLabel('Em projetos Git, a tarefa usa um worktree próprio.' if janela.real else 'Simulação: a tarefa aparece na lista sem executar agentes.')
        self.aviso.setTextFormat(Qt.TextFormat.PlainText)
        self.aviso.setWordWrap(True)
        layout.addWidget(self.aviso)
        self.erro = QLabel()
        self.erro.setTextFormat(Qt.TextFormat.PlainText)
        self.erro.setWordWrap(True)
        layout.addWidget(self.erro)
        botoes = QHBoxLayout()
        fechar = QPushButton('Fechar')
        fechar.clicked.connect(self.hide)
        self.enviar = QPushButton('Iniciar tarefa' if janela.real else 'Criar tarefa simulada')
        self.enviar.clicked.connect(self.criar)
        self.projeto.textChanged.connect(self.reeditar)
        self.pedido.textChanged.connect(self.reeditar)
        self.modo.currentTextChanged.connect(self.reeditar)
        for controle in (self.agente, self.revisor, self.seguranca, self.delegacao):
            controle.currentTextChanged.connect(self.personalizar)
        botoes.addWidget(fechar)
        botoes.addStretch()
        botoes.addWidget(self.enviar)
        layout.addLayout(botoes)

        if janela.real:
            self.perfis = QProcess(self)
            janela.preparar(self.perfis, ['--capacidades-json'], 'jangada-agente')
            self.perfis.finished.connect(self.carregar_perfis)
            self.perfis.errorOccurred.connect(lambda _: self.aviso.setText('Não foi possível consultar os perfis. Claude e Codex continuam disponíveis.'))
            self.perfis.start()
            QTimer.singleShot(3000, self.perfis.kill)

    def carregar_perfis(self, codigo, estado):
        try:
            if codigo != 0 or estado != QProcess.ExitStatus.NormalExit:
                raise ValueError('consulta falhou')
            catalogo = json.loads(bytes(self.perfis.readAllStandardOutput()))
            if not isinstance(catalogo, dict):
                raise ValueError('catálogo inválido')
            principais, perfis = catalogo.get('principais'), catalogo.get('perfis')
            if not isinstance(principais, list) or not principais or any(
                not isinstance(a, dict) or not isinstance(a.get('nome'), str)
                or not isinstance(a.get('instalado'), bool) for a in principais
            ):
                raise ValueError('agentes inválidos')
            if not isinstance(perfis, list) or any(
                not isinstance(p, dict) or not isinstance(p.get('nome'), str)
                or not isinstance(p.get('descricao'), str) for p in perfis
            ):
                raise ValueError('perfis inválidos')
        except (ValueError, UnicodeDecodeError):
            self.aviso.setText('Não foi possível consultar os perfis. Claude e Codex continuam disponíveis.')
            return
        # Sem os sinais: a troca da lista não é edição do usuário, e reabriria
        # o envio de um pedido que já saiu.
        escolhido = self.agente.currentText()
        self.agente.blockSignals(True)
        self.agente.clear()
        self.agente.addItems([a['nome'] for a in principais if a['instalado']])
        for perfil in perfis:
            nome = perfil['nome']
            texto = nome + (': ' + perfil['descricao'] if perfil['descricao'] else '')
            self.agente.addItem(texto, nome)
        if self.agente.findText(escolhido) >= 0:
            self.agente.setCurrentIndex(self.agente.findText(escolhido))
        self.agente.blockSignals(False)
        self.recomendado = next((a['nome'] for a in principais if a['instalado']), None)
        if self.recomendado:
            self.aviso.setText(f'Recomendado: {self.recomendado}, primeiro executor instalado no catálogo. Revisor, segurança e delegação seguem os padrões configurados.')
        if not self.agente.count():
            self.aviso.setText('Nenhum agente instalado: instale o claude ou o codex.')
            self.enviar.setEnabled(False)

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Escolher projeto', self.projeto.text())
        if pasta:
            self.projeto.setText(pasta)

    def nova_pasta(self):
        nome, aceito = QInputDialog.getText(self, 'Nova pasta', f'Nome do projeto, criado em {self.base}')
        if aceito:
            self.criar_pasta(nome)

    def criar_pasta(self, nome):
        nome = nome.strip()
        if not nome or nome.startswith('.') or '/' in nome or '\0' in nome:
            self.erro.setText('O nome da pasta não pode ser vazio, começar com ponto, ter barra nem caractere nulo.')
            return
        pasta = self.base / nome
        try:
            pasta.mkdir(parents=True)
        except FileExistsError:
            self.erro.setText(f'{pasta} já existe. Use Escolher pasta para abrir esse projeto.')
            return
        except OSError as erro:
            self.erro.setText(f'Não foi possível criar {pasta}: {erro.strerror}.')
            return
        self.projeto.setText(str(pasta))

    def criar(self):
        pedido = self.pedido.toPlainText().strip()
        pasta = self.projeto.text().strip()
        if not pasta or not Path(pasta).expanduser().is_dir():
            self.erro.setText('Escolha uma pasta de projeto existente.')
            return
        if not pedido:
            self.erro.setText('Escreva o pedido para o agente.')
            return
        if len(pedido) > 16000:
            self.erro.setText('O pedido pode ter até 16.000 caracteres.')
            return
        projeto = Path(pasta).expanduser().resolve()
        agente = self.agente.currentText()
        perfil = self.agente.currentData()
        if self.modo.currentText() == 'Recomendado':
            if not self.recomendado:
                self.erro.setText('Nenhum executor recomendado disponível. Confira o catálogo ou escolha nas opções avançadas.')
                return
            agente, perfil = self.recomendado, None
        nome = 'tarefa-' + uuid.uuid4().hex[:12]
        if not self.janela.real:
            sessao = Sessao(nome, 'trabalhando', str(projeto), datetime.now().isoformat(), 'agente/' + nome, pedido, agente, projeto.name, 'Tarefa simulada. Nenhum agente foi executado.')
            self.janela.criadas[nome] = sessao
            self.janela.atualizar()
            self.janela.selecionar_nome(nome)
            self.erro.setText('Tarefa simulada criada. Você pode acompanhar na lista.')
        else:
            processo = QProcess(self)
            argumentos = ['--janela', '--projeto', str(projeto), '--nome', nome,
                          '--perfil' if perfil else '--agente', perfil or agente, '--prompt', pedido]
            personalizado = self.modo.currentText() == 'Personalizado'
            if personalizado and self.revisor.currentIndex():
                argumentos += ['--revisor', self.revisor.currentText()]
            if personalizado and self.seguranca.currentIndex():
                argumentos += ['--sem-isolar']
            if personalizado and self.delegacao.currentIndex():
                argumentos += ['--delegacao', self.delegacao.currentText()]
            self.janela.preparar(processo, argumentos, 'jangada-agente')
            iniciado, _ = processo.startDetached()
            if not iniciado:
                self.erro.setText('Não foi possível iniciar jangada-agente. Confira --jangada.')
                return
            self.erro.setText('Abertura solicitada. Se o agente falhar ao iniciar, o erro aparece no terminal. Confira se a tarefa entrou na lista. Seu pedido foi preservado.')
        self.enviar.setEnabled(False)

    def personalizar(self, *_):
        self.modo.setCurrentText('Personalizado')
        self.reeditar()

    def reeditar(self, *_):
        self.enviar.setEnabled(True)
        self.erro.clear()


class Janela(QMainWindow):

    def __init__(self, real=False, jangada=None, estado=None):
        super().__init__()
        self.real = real
        self.eventos = {}
        self.observadas = {}
        self.jangada = Path(jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
        self.estado_dir = Path(estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser()
        self.sessoes = {}
        self.estrutura = None
        self.itens = {}
        self.finalizando = {}
        self.aviso_finalizacao = None
        self.dados_validos = False
        self.criadas = {}
        self.formulario = None
        self.previas = {}
        self.atividade_sessao = None
        self.previa_alvo = None
        self.passo = 0
        self.fechando = False
        nome_central = 'Central de tarefas'
        self.setWindowTitle('Jangada · ' + nome_central + ('' if real else ' · Simulação'))
        self.resize(1200, 780)
        self.setMinimumSize(700, 460)
        centro = QWidget()
        self.setCentralWidget(centro)
        layout = QVBoxLayout(centro)
        layout.setContentsMargins(24, 22, 24, 18)
        topo = QHBoxLayout()
        topo.setSpacing(8)
        marca = QLabel()
        marca.setAccessibleName('Jangada')
        marca.setPixmap(QPixmap(str(Path(__file__).resolve().parents[1] / 'logo/jangada.png')))
        marca.setFixedSize(24, 24)
        marca.setScaledContents(True)
        topo.addWidget(marca)
        titulo = QLabel(nome_central)
        titulo.setStyleSheet('font-size: 24px; font-weight: 600;')
        topo.addWidget(titulo)
        topo.addStretch()
        self.atualizar_botao = QPushButton('Atualizar' if real else 'Avançar simulação')
        self.atualizar_botao.clicked.connect(self.avancar)
        topo.addWidget(self.atualizar_botao)
        self.nova = QPushButton('Nova tarefa')
        self.nova.clicked.connect(self.nova_tarefa)
        topo.addWidget(self.nova)
        for rotulo, comando in (('Conversa de Pescador', 'jangada-pescador'), ('Painel de indicadores', 'jangada-painel')):
            botao = QPushButton(rotulo)
            botao.clicked.connect(lambda _, c=comando: self.abrir_ferramenta(c))
            topo.addWidget(botao)
        layout.addLayout(topo)
        self.resumo = QLabel()
        self.resumo.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.resumo)
        self.cartoes = QLabel()
        self.cartoes.setTextFormat(Qt.TextFormat.PlainText)
        self.cartoes.setStyleSheet('background: #23313b; padding: 14px; font-size: 16px;')
        layout.addWidget(self.cartoes)
        divisor = QSplitter()
        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(['Tarefa', 'Projeto', 'Estado', 'Atualização'])
        self.lista.setColumnWidth(0, 270)
        self.lista.setColumnWidth(1, 130)
        self.lista.setColumnWidth(2, 155)
        self.lista.currentItemChanged.connect(self.selecionar)
        divisor.addWidget(self.lista)
        detalhes = QWidget()
        direito = QVBoxLayout(detalhes)
        direito.setContentsMargins(18, 0, 0, 0)
        self.nome = QLabel('Selecione uma sessão')
        self.nome.setTextFormat(Qt.TextFormat.PlainText)
        self.nome.setWordWrap(True)
        self.nome.setStyleSheet('font-size: 18px; font-weight: 600;')
        direito.addWidget(self.nome)
        self.situacao = QLabel()
        self.situacao.setTextFormat(Qt.TextFormat.PlainText)
        self.situacao.setWordWrap(True)
        self.situacao.setStyleSheet('background: #23313b; padding: 12px;')
        direito.addWidget(self.situacao)
        self.detalhes = QPlainTextEdit()
        self.detalhes.setReadOnly(True)
        self.abas = QTabWidget()
        self.atividade = QPlainTextEdit()
        self.atividade.setReadOnly(True)
        acompanhamento = QWidget()
        acompanhamento_layout = QVBoxLayout(acompanhamento)
        acompanhamento_layout.addWidget(QLabel('Última atividade recebida'))
        self.ultima_atividade = QLabel()
        self.ultima_atividade.setTextFormat(Qt.TextFormat.PlainText)
        self.ultima_atividade.setWordWrap(True)
        acompanhamento_layout.addWidget(self.ultima_atividade)
        acompanhamento_layout.addWidget(QLabel('Mudanças acompanhadas nesta janela'))
        self.linha_tempo = QPlainTextEdit()
        self.linha_tempo.setReadOnly(True)
        acompanhamento_layout.addWidget(self.linha_tempo, 1)
        self.abas.addTab(acompanhamento, 'Acompanhamento')
        self.abas.addTab(self.atividade, 'Saída do agente')
        self.abas.addTab(self.detalhes, 'Detalhes')
        self.entrega = QPlainTextEdit()
        self.entrega.setReadOnly(True)
        self.entrega.setPlainText('Use Conferir e integrar para consultar a entrega antes da confirmação.')
        self.abas.addTab(self.entrega, 'Entrega')
        direito.addWidget(self.abas)
        self.abrir = QPushButton('Abrir sessão')
        self.abrir.setEnabled(False)
        self.abrir.clicked.connect(self.focar)
        direito.addWidget(self.abrir)
        self.integrar = QPushButton('Conferir e integrar')
        self.encerrar = QPushButton('Encerrar sem integrar')
        self.integrar.setObjectName('integrar')
        self.encerrar.setObjectName('encerrar')
        self.integrar.setToolTip('Integra as alterações ao projeto e encerra a sessão. Atalho: Alt+I.')
        self.encerrar.setToolTip('Encerra a sessão sem integrar as alterações ao projeto. Atalho: Ctrl+X.')
        self.integrar.setShortcut(QKeySequence('Alt+I'))
        self.encerrar.setShortcut(QKeySequence('Ctrl+X'))
        self.integrar.setEnabled(False)
        self.encerrar.setEnabled(False)
        self.integrar.clicked.connect(self.integrar_interface)
        self.integrar_terminal = QPushButton('Integrar pelo terminal')
        self.integrar_terminal.clicked.connect(lambda: self.finalizar(True))
        direito.addWidget(self.integrar_terminal)
        self.encerrar.clicked.connect(lambda: self.finalizar(False))
        direito.addWidget(self.integrar)
        direito.addWidget(self.encerrar)
        explicacao = QLabel('A integração mostra a entrega e pede confirmação. O terminal permite diagnóstico e encerramento. Pronto para conferir não confirma conclusão.')
        explicacao.setWordWrap(True)
        direito.addWidget(explicacao)
        divisor.addWidget(detalhes)
        divisor.setSizes([650, 400])
        layout.addWidget(divisor, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setStyleSheet('\n            QWidget { background: #182128; color: #e1e9ec; font-size: 13px; }\n            QTreeWidget, QPlainTextEdit, QLineEdit, QComboBox { background: #11191f; border: 1px solid #35454f;\n                border-radius: 6px; padding: 8px; }\n            QTreeWidget::item { padding: 8px 3px; }\n            QTreeWidget::item:selected { background: #2d4956; }\n            QHeaderView::section { background: #23313b; border: none; padding: 8px; }\n            QPushButton { background: #294551; border: 1px solid #48616b;\n                border-radius: 6px; padding: 10px 16px; }\n            QPushButton:hover { background: #365b69; }\n            QPushButton#integrar:enabled { background: #345647; border-color: #628574; }\n            QPushButton#encerrar:enabled { background: #182128; }\n            QPushButton:disabled { color: #74838a; background: #202c33; }\n        ')
        self.integracao = QProcess(self)
        self.integracao.finished.connect(self.integracao_fim)
        self.integracao.errorOccurred.connect(self.integracao_erro)
        self.integracao_etapa = None
        self.integracao_nome = None
        self.integracao_pasta = None
        self.consulta = QProcess(self)
        self.consulta.finished.connect(self.consulta_fim)
        self.consulta.errorOccurred.connect(self.consulta_erro)
        self.acao = QProcess(self)
        self.acao.finished.connect(self.acao_fim)
        self.acao.errorOccurred.connect(self.acao_erro)
        self.previa = QProcess(self)
        self.previa.finished.connect(self.previa_fim)
        self.previa.errorOccurred.connect(self.previa_erro)
        self.tempo_previa = QTimer(self)
        self.tempo_previa.setSingleShot(True)
        self.tempo_previa.timeout.connect(self.previa.kill)
        self.espera = QTimer(self)
        self.espera.setSingleShot(True)
        self.espera.timeout.connect(self.expirar)
        self.tempo_acao = QTimer(self)
        self.tempo_acao.setSingleShot(True)
        self.tempo_acao.timeout.connect(self.expirar_acao)
        self.tempo_finalizacao = QTimer(self)
        self.tempo_finalizacao.setInterval(500)
        self.tempo_finalizacao.timeout.connect(self.conferir_finalizacoes)
        self.timer = QTimer(self)
        self.timer.setInterval(30000)
        self.timer.timeout.connect(self.atualizar)
        self.observador = QFileSystemWatcher(self)
        self.observador.directoryChanged.connect(self.mudanca_estado)
        self.observador.fileChanged.connect(self.mudanca_estado)
        self.evento_estado = QTimer(self)
        self.evento_estado.setSingleShot(True)
        self.evento_estado.setInterval(200)
        self.evento_estado.timeout.connect(self.atualizar)
        self.atualizacao_pendente = False
        if real:
            self.observar_estado()
            self.timer.start()
        self.atualizar()

    def selecionada(self):
        item = self.lista.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def abrir_ferramenta(self, comando):
        if comando not in ('jangada-pescador', 'jangada-painel'):
            return
        if not self.real:
            self.status.setText(f'Simulação: abriria {comando}. Nenhum comando foi executado.')
            return
        processo = QProcess(self)
        self.preparar(processo, ['--janela'] if comando == 'jangada-pescador' else [], comando)
        iniciado, _ = processo.startDetached()
        self.status.setText('Abertura solicitada.' if iniciado else f'Não foi possível abrir {comando}. Confira --jangada.')

    def acompanhar_mudancas(self, sessoes):
        for s in sessoes.values():
            anterior = self.observadas.get(s.nome)
            assinatura = (s.inicio, estado_exibido(s), s.mensagem, s.atualizado)
            entradas = self.eventos.setdefault(s.nome, [])
            if anterior is None or anterior[0] != s.inicio:
                entradas.clear()
                self.previas.pop(s.nome, None)
                entradas.append('Tarefa encontrada · ' + ROTULOS.get(estado_exibido(s), estado_exibido(s)))
            elif anterior != assinatura:
                mudancas = []
                if anterior[1] != assinatura[1]:
                    mudancas.append(ROTULOS.get(assinatura[1], assinatura[1]))
                if anterior[2] != s.mensagem and s.mensagem:
                    mudancas.append(s.mensagem)
                if mudancas:
                    entradas.append(datetime.now().strftime('%H:%M:%S') + ' · ' + '\n'.join(mudancas))
                    del entradas[:-50]
            self.observadas[s.nome] = assinatura
        for nome in set(self.observadas) - set(sessoes):
            self.observadas.pop(nome, None)
            self.eventos.pop(nome, None)
            self.previas.pop(nome, None)

    def nova_tarefa(self):
        if self.formulario is None:
            self.formulario = NovaTarefa(self)
        self.formulario.show()
        self.formulario.raise_()
        self.formulario.activateWindow()

    def selecionar_nome(self, nome):
        for i in range(self.lista.topLevelItemCount()):
            grupo = self.lista.topLevelItem(i)
            for j in range(grupo.childCount()):
                item = grupo.child(j)
                if item.data(0, Qt.ItemDataRole.UserRole) == nome:
                    self.lista.setCurrentItem(item)
                    return

    def mostrar(self, sessoes):
        self.dados_validos = True
        anterior = self.selecionada()
        primeira_carga = not self.sessoes and anterior is None
        self.sessoes = sessoes
        self.acompanhar_mudancas(sessoes)
        ordenadas = sorted(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.projeto, s.nome))
        estrutura = [(GRUPOS.get(estado_exibido(s), 'Outras tarefas'), s.nome) for s in ordenadas]
        self.lista.blockSignals(True)
        # A lista só é refeita quando muda de ordem ou de grupo; no resto das
        # atualizações os itens ficam e só o texto muda.
        if estrutura != self.estrutura:
            fechados = {g.text(0) for g in map(self.lista.topLevelItem, range(self.lista.topLevelItemCount()))
                        if not g.isExpanded()}
            self.lista.clear()
            self.itens = {}
            grupos = {}
            for grupo, nome in estrutura:
                if grupo not in grupos:
                    grupos[grupo] = QTreeWidgetItem(self.lista, [grupo])
                    grupos[grupo].setFlags(Qt.ItemFlag.ItemIsEnabled)
                    grupos[grupo].setExpanded(grupo not in fechados)
                self.itens[nome] = QTreeWidgetItem(grupos[grupo])
                self.itens[nome].setData(0, Qt.ItemDataRole.UserRole, nome)
            self.estrutura = estrutura
        itens = self.itens
        for s in ordenadas:
            item = itens[s.nome]
            tarefa = s.tarefa.splitlines()[0] if s.tarefa else s.nome
            textos = [tarefa, s.projeto, ROTULOS.get(estado_exibido(s), estado_exibido(s)), idade(s.atualizado)]
            for coluna, texto in enumerate(textos):
                if item.text(coluna) != texto:
                    item.setText(coluna, texto)
            dica = '<qt>' + html.escape(s.tarefa or s.nome).replace('\n', '<br>') + '</qt>'
            if item.toolTip(0) != dica:
                item.setToolTip(0, dica)
            item.setForeground(2, QColor(CORES.get(estado_exibido(s), '#b7c6cd')))
        escolhido = itens.get(anterior)
        if primeira_carga and itens:
            prioridade = min(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.nome))
            escolhido = itens[prioridade.nome]
        if escolhido and escolhido is not self.lista.currentItem():
            self.lista.setCurrentItem(escolhido)
        self.lista.blockSignals(False)
        self.selecionar()
        esperando = sum((estado_exibido(s) == 'aguardando' for s in sessoes.values()))
        interrompidas = sum((estado_exibido(s) == 'interrompido' for s in sessoes.values()))
        rotulo = 'interrompida' if interrompidas == 1 else 'interrompidas'
        self.resumo.setText((f'{len(sessoes)} tarefas acompanhadas · Atualização por eventos; reserva a cada 30 segundos' if self.real else f'{len(sessoes)} tarefas fictícias · Avance a simulação para acompanhar as mudanças') if sessoes else 'Nenhuma tarefa. Inicie pelo botão Nova tarefa.')
        andando = sum((estado_exibido(s) == 'trabalhando' for s in sessoes.values()))
        encerrados = sum((estado_exibido(s) == 'concluido' for s in sessoes.values()))
        espera_rotulo = 'precisa da sua resposta' if esperando == 1 else 'precisam da sua resposta'
        turno_rotulo = 'pronto para conferir' if encerrados == 1 else 'prontos para conferir'
        self.cartoes.setText(f'{esperando} {espera_rotulo}    ·    {andando} em execução    ·    {interrompidas} {rotulo}    ·    {encerrados} {turno_rotulo}')
        if anterior and anterior not in sessoes:
            self.status.setText('A sessão selecionada saiu da lista. Selecione outra sessão.')

    def selecionar(self, *_):
        s = self.sessoes.get(self.selecionada())
        ocupada = (self.acao.state() != QProcess.ProcessState.NotRunning
                   or self.integracao_etapa is not None)
        pendente = self.finalizacao_pendente(s.nome) if self.dados_validos and s else False
        for botao in (self.abrir, self.integrar, self.integrar_terminal, self.encerrar):
            botao.setEnabled(self.dados_validos and s is not None and (not ocupada) and not pendente)
        if not s:
            self.nome.setText('Selecione uma tarefa')
            self.situacao.clear()
            self.ultima_atividade.clear()
            self.linha_tempo.clear()
            self.detalhes.setPlainText('Nenhuma sessão selecionada.')
            self.exibir_atividade('Selecione uma sessão para acompanhar a atividade.', None)
            return
        self.nome.setText(s.tarefa.splitlines()[0] if s.tarefa else s.nome)
        estado = estado_exibido(s)
        pendencia = 'Confira o pedido no terminal.' if estado == 'aguardando' else 'A sessão pode ser retomada pelo terminal.' if estado == 'interrompido' else 'Confira o resultado na conversa; a tarefa pode continuar.' if estado == 'concluido' else 'Acompanhando a atividade do agente.'
        self.situacao.setText(f'{ROTULOS.get(estado, estado)} · {idade(s.atualizado)}\n{pendencia}')
        self.ultima_atividade.setText(s.mensagem or 'Nenhuma mensagem de atividade publicada pelo agente.')
        self.linha_tempo.setPlainText('\n\n'.join(self.eventos.get(s.nome, [])))
        self.linha_tempo.verticalScrollBar().setValue(self.linha_tempo.verticalScrollBar().maximum())
        self.abrir.setText('Retomar no terminal' if s.estado == 'interrompido' else 'Abrir terminal')
        self.detalhes.setPlainText(f"Estado: {ROTULOS.get(estado, estado)}\nAgente: {s.agente}\nProjeto: {s.projeto}\n\nSessão\n{s.nome}\n\nTarefa\n{s.tarefa or 'Não informada'}\n\nRamo\n{s.ramo or 'Não informado'}\n\nDiretório\n{s.dir or 'Não informado'}\n\nÚltima atualização\n{s.atualizado or 'Não informada'}\n\nMensagem da sessão\n{s.mensagem or 'Sem mensagem'}")
        if not self.real:
            self.exibir_atividade(s.mensagem or 'Sem atividade registrada.', s.nome)
        else:
            conteudo = self.previas.get(s.nome, 'Consultando atividade da sessão…')
            self.exibir_atividade(conteudo, s.nome)
            self.solicitar_previa(s)

    def exibir_atividade(self, conteudo, nome):
        barra = self.atividade.verticalScrollBar()
        posicao = barra.value()
        acompanhar = nome != self.atividade_sessao or posicao >= barra.maximum() - 1
        self.atividade_sessao = nome
        if self.atividade.toPlainText() != conteudo:
            self.atividade.setPlainText(conteudo)
        barra.setValue(barra.maximum() if acompanhar else posicao)

    def solicitar_previa(self, sessao):
        if not self.dados_validos:
            return
        if self.previa.state() != QProcess.ProcessState.NotRunning:
            return
        self.previa_alvo = (sessao.nome, sessao.atualizado, sessao.inicio)
        self.iniciar(self.previa, ['--previa', sessao.nome])
        self.tempo_previa.start(10000)

    def previa_fim(self, codigo, tipo):
        self.tempo_previa.stop()
        bruto = bytes(self.previa.readAllStandardOutput())
        self.previa.readAllStandardError()
        if self.fechando or not self.previa_alvo:
            return
        nome, atualizado, inicio = self.previa_alvo
        sessao = self.sessoes.get(nome)
        if sessao and (sessao.atualizado, sessao.inicio) == (atualizado, inicio):
            conteudo = bruto.decode('utf-8', 'replace')[:16000] or 'Nenhuma atividade recente.' if codigo == 0 and tipo == QProcess.ExitStatus.NormalExit and (len(bruto) <= LIMITE) else 'Não foi possível consultar a atividade da sessão.'
            self.previas[nome] = conteudo
            if self.selecionada() == nome:
                self.exibir_atividade(conteudo, nome)
        if self.selecionada() != nome or (sessao and sessao.atualizado != atualizado):
            atual = self.sessoes.get(self.selecionada())
            if atual:
                self.solicitar_previa(atual)

    def previa_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.tempo_previa.stop()
            if self.previa_alvo and self.selecionada() == self.previa_alvo[0]:
                self.exibir_atividade('Não foi possível consultar a atividade da sessão.', self.previa_alvo[0])

    def preparar(self, processo, argumentos, comando='jangada-agentes'):
        ambiente = QProcessEnvironment.systemEnvironment()
        ambiente.insert('JANGADA_PATH', str(self.jangada))
        ambiente.insert('XDG_STATE_HOME', str(self.estado_dir.parent.parent))
        processo.setProcessEnvironment(ambiente)
        processo.setProgram(str(self.jangada / 'bin' / comando))
        processo.setArguments(argumentos)

    def iniciar(self, processo, argumentos):
        self.preparar(processo, argumentos)
        processo.start()

    def observar_estado(self):
        caminhos = set()
        for pasta in (self.estado_dir, self.estado_dir.parent / 'revisoes'):
            if pasta.is_dir():
                caminhos.add(str(pasta))
                caminhos.update(str(p) for p in pasta.glob('*.json') if p.is_file())
            else:
                while not pasta.is_dir() and pasta != pasta.parent:
                    pasta = pasta.parent
                caminhos.add(str(pasta))
        atuais = set(self.observador.directories() + self.observador.files())
        if atuais - caminhos:
            self.observador.removePaths(sorted(atuais - caminhos))
        if caminhos - atuais:
            self.observador.addPaths(sorted(caminhos - atuais))

    def mudanca_estado(self, *_):
        self.atualizacao_pendente = True
        if not self.evento_estado.isActive():
            self.evento_estado.start()

    def avancar(self):
        self.passo += 1
        self.atualizar()

    def atualizar(self):
        if not self.real:
            self.status.setText(f'Simulação · cenário {self.passo % 4 + 1} de 4')
            sessoes = simuladas(self.passo) | self.criadas
            for nome, s in sessoes.items():
                anterior = self.sessoes.get(nome)
                if anterior and (anterior.estado, anterior.mensagem) == (s.estado, s.mensagem):
                    sessoes[nome] = replace(s, atualizado=anterior.atualizado)
            self.mostrar(sessoes)
        elif self.consulta.state() == QProcess.ProcessState.NotRunning:
            self.atualizacao_pendente = False
            self.observar_estado()
            self.iniciar(self.consulta, ['--lista'])
            self.espera.start(10000)

    def consulta_fim(self, codigo, tipo):
        self.espera.stop()
        if self.atualizacao_pendente and not self.fechando:
            self.evento_estado.start()
        if self.fechando:
            return
        saida = bytes(self.consulta.readAllStandardOutput())
        erro = bytes(self.consulta.readAllStandardError()).decode('utf-8', 'replace')[:500]
        if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.falha('Não foi possível consultar as sessões. ' + erro)
            return
        if len(saida) > LIMITE:
            self.falha('A listagem excedeu o limite de leitura.')
            return
        try:
            sessoes = ler_lista(saida.decode('utf-8', 'replace'), self.estado_dir)
        except ValueError as exc:
            self.falha(str(exc))
            return
        self.status.setText('Atualizado às ' + datetime.now().strftime('%H:%M:%S') if sessoes else 'Nenhuma sessão disponível. Abra um agente pelo jangada.')
        self.mostrar(sessoes)

    def falha(self, mensagem):
        self.dados_validos = False
        self.selecionar()
        self.status.setText(mensagem + ' Últimos dados preservados; ações indisponíveis até atualizar.')

    def consulta_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.espera.stop()
            self.falha('Não foi possível iniciar jangada-agentes. Confira o caminho em --jangada.')

    def expirar(self):
        self.consulta.kill()

    def pasta_finalizacao(self, nome):
        from central import nome_soquete
        runtime = Path(nome_soquete(self.jangada, self.estado_dir, self.real)).parent
        identidade = f'{self.jangada}:{self.estado_dir.resolve()}:{nome}'
        return runtime / ('acao-' + hashlib.sha256(identidade.encode()).hexdigest()[:24])

    def finalizacao_pendente(self, nome):
        if not self.real:
            return False
        try:
            raiz = self.pasta_finalizacao(nome)
            if not raiz.exists():
                self.aviso_finalizacao = None
                self.finalizando.pop(nome, None)
                return False
            tentativas = list(raiz.iterdir())
            if not tentativas:
                raiz.rmdir()
                self.aviso_finalizacao = None
                self.finalizando.pop(nome, None)
                return False
            if len(tentativas) != 1 or not tentativas[0].is_dir():
                self.aviso_finalizacao = None
                return True
            pasta = tentativas[0]
        except (OSError, ValueError) as erro:
            aviso = f'Ações indisponíveis: {erro}'
            if aviso != self.aviso_finalizacao and self.dados_validos:
                self.status.setText(aviso)
            self.aviso_finalizacao = aviso
            return True
        self.aviso_finalizacao = None
        if not pasta.exists():
            self.finalizando.pop(nome, None)
            return False
        self.finalizando[nome] = pasta
        self.tempo_finalizacao.start()
        if not (pasta / 'pronta').exists():
            try:
                inicio = json.loads((pasta / 'inicio.json').read_text())
                if time.monotonic() - inicio['criado'] >= 10:
                    try:
                        os.kill(inicio['pid'], 0)
                    except ProcessLookupError:
                        (pasta / 'inicio.json').unlink()
                        # Uma pronta criada neste intervalo impede a remoção da pasta.
                        pasta.rmdir()
                        raiz.rmdir()
                        self.finalizando.pop(nome, None)
                        self.status.setText('O terminal não iniciou a ação. Você pode tentar novamente.')
                        return False
            except (OSError, ValueError, KeyError, TypeError):
                pass
        return True

    def conferir_finalizacoes(self):
        liberou = False
        for nome in list(self.finalizando):
            if not self.finalizacao_pendente(nome):
                liberou = True
        if not self.finalizando:
            self.tempo_finalizacao.stop()
        if liberou:
            self.selecionar()

    def confirmar_entrega(self, dados):
        marca = dados.get('marca') or {}
        independencia = ('Sim' if marca['independent'] else 'Não') if isinstance(marca.get('independent'), bool) else 'Não informado'
        correspondencia = ('Sim' if dados['marca_atual'] else 'Não') if isinstance(dados.get('marca_atual'), bool) else 'Não informado'
        texto = (f"Base: {dados['base_sha']}\nCandidato: {dados['candidate_sha']}\n\n"
                 f"Arquivos e linhas (+/-)\n{dados['arquivos']}\n\n"
                 f"Validação local: {dados['validacao_local']}\n"
                 f"Revisor da marca: {marca.get('reviewer', 'Não informado')}\n"
                 f"Independência declarada na marca: {independencia}\n"
                 f"Marca corresponde aos SHA exibidos: {correspondencia}\n"
                 f"Base da aprovação: {marca.get('base_sha', 'Sem marca')}\n"
                 f"Candidato aprovado: {marca.get('candidate_sha', 'Sem marca')}\n\n"
                 f"Parecer\n{dados['parecer'] or 'Sem parecer externo'}")
        self.entrega.setPlainText(texto)
        self.abas.setCurrentWidget(self.entrega)
        pergunta = QMessageBox(self)
        pergunta.setWindowTitle('Confirmar integração')
        pergunta.setTextFormat(Qt.TextFormat.PlainText)
        pergunta.setText('Mesclar esta entrega e encerrar a sessão?')
        pergunta.setInformativeText(texto)
        pergunta.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        pergunta.setDefaultButton(QMessageBox.StandardButton.No)
        return pergunta.exec() == QMessageBox.StandardButton.Yes

    def integrar_interface(self):
        nome = self.selecionada()
        if (not self.dados_validos or nome not in self.sessoes or self.integracao_etapa is not None
                or not NOME.fullmatch(nome) or nome.startswith('-')):
            return
        if self.acao.state() != QProcess.ProcessState.NotRunning or self.finalizacao_pendente(nome):
            return
        if not self.real:
            self.status.setText('Simulação: integração não executada.')
            return
        self.integracao_nome = nome
        self.integracao_etapa = 'previa'
        self.preparar(self.integracao, ['--integracao-json', nome])
        self.integracao.start()
        self.selecionar()

    def limpar_integracao(self):
        pasta = self.integracao_pasta
        if pasta:
            try:
                (pasta / 'pronta').unlink(missing_ok=True)
                (pasta / 'inicio.json').unlink(missing_ok=True)
                pasta.rmdir()
                pasta.parent.rmdir()
            except OSError:
                self.status.setText('A trava da ação não pôde ser removida; confira o terminal.')
        self.integracao_pasta = None
        self.integracao_etapa = None
        self.selecionar()

    def integracao_fim(self, codigo, tipo):
        bruto = bytes(self.integracao.readAllStandardOutput())
        erro = bytes(self.integracao.readAllStandardError()).decode('utf-8', 'replace')[:16000]
        if self.integracao_etapa != 'previa':
            self.entrega.appendPlainText(bruto.decode('utf-8', 'replace')[:16000] + '\n' + erro)
            self.status.setText('Integração encerrada; confira o resultado na aba Entrega.'
                                if codigo == 0 else 'Integração recusada ou falhou. Confira a aba Entrega ou o terminal.')
            self.limpar_integracao()
            self.atualizar()
            return
        try:
            if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit or len(bruto) > LIMITE:
                raise ValueError('consulta da entrega falhou')
            dados = json.loads(bruto)
            if not isinstance(dados, dict) or not isinstance(dados.get('marca'), dict):
                raise ValueError('prévia inválida')
            if any(not isinstance(dados.get(c), str) for c in ('arquivos', 'validacao_local', 'parecer')):
                raise ValueError('conteúdo inválido na prévia')
            for campo in ('base_sha', 'candidate_sha'):
                if not isinstance(dados.get(campo), str) or not re.fullmatch('[0-9a-f]{40}', dados[campo]):
                    raise ValueError('SHA inválido na prévia')
            if not self.confirmar_entrega(dados):
                self.status.setText('Integração cancelada; nenhum merge solicitado.')
                self.limpar_integracao()
                return
            nome = self.integracao_nome
            raiz = self.pasta_finalizacao(nome)
            raiz.mkdir(mode=0o700)
            pasta = raiz / uuid.uuid4().hex
            self.integracao_pasta = pasta
            pasta.mkdir(mode=0o700)
            (pasta / 'inicio.json').write_text(json.dumps({'pid': os.getpid(), 'criado': time.monotonic()}))
            (pasta / 'pronta').touch(mode=0o600)
            self.finalizando[nome] = pasta
            argumentos = ['--integrar', '--confirmacao', dados['base_sha'], dados['candidate_sha'], nome]
            self.preparar(self.integracao, argumentos, 'jangada-agente-fim')
            self.integracao.setProgram('flock')
            self.integracao.setArguments(['-n', str(raiz.with_suffix('.trava')),
                str(self.jangada / 'bin/jangada-agente-fim'), *argumentos])
            self.integracao_etapa = 'mescla'
            self.integracao.start()
            self.integracao.closeWriteChannel()
            self.status.setText('Integrando a entrega confirmada; acompanhe a aba Entrega.')
        except (OSError, ValueError, KeyError, TypeError) as exc:
            self.status.setText(f'Não foi possível integrar pela interface: {exc}. Use o terminal para diagnóstico.')
            self.limpar_integracao()

    def integracao_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.status.setText('Não foi possível iniciar a integração. Use o terminal para diagnóstico.')
            self.limpar_integracao()

    def finalizar(self, integrar):
        nome = self.selecionada()
        if not self.dados_validos or nome not in self.sessoes or not NOME.fullmatch(nome) or nome.startswith('-'):
            return
        if (self.acao.state() != QProcess.ProcessState.NotRunning or self.integracao_etapa is not None
                or self.finalizacao_pendente(nome)):
            return
        acao = 'integrar e encerrar' if integrar else 'encerrar sem integrar'
        if not self.real:
            self.status.setText(f'Simulação: solicitaria {acao} a sessão {nome}. Nenhum comando foi executado.')
            return
        comando = [str(self.jangada / 'bin' / 'jangada-agente-fim')]
        if integrar:
            comando.append('--integrar')
        comando.append(nome)
        raiz = pasta = None
        criou_raiz = criou_pasta = False
        try:
            raiz = self.pasta_finalizacao(nome)
            raiz.mkdir(mode=0o700)
            criou_raiz = True
            pasta = raiz / uuid.uuid4().hex
            pasta.mkdir(mode=0o700)
            criou_pasta = True
            inicio = {'pid': os.getpid(), 'criado': time.monotonic()}
            (pasta / 'inicio.json').write_text(json.dumps(inicio))
        except (OSError, ValueError) as erro:
            if criou_pasta:
                try:
                    (pasta / 'inicio.json').unlink(missing_ok=True)
                    pasta.rmdir()
                except OSError:
                    pass
            if criou_raiz:
                try:
                    raiz.rmdir()
                except OSError:
                    pass
            if isinstance(erro, FileExistsError):
                self.selecionar()
            else:
                self.status.setText(f'Não foi possível preparar a ação: {erro}')
            return
        # A pasta persiste ao fechar a central; o terminal a remove ao terminar.
        roteiro = """pasta=$1; trava=$2; shift 2
umask 077
limpar() { rm -f -- "$pasta/pronta" "$pasta/inicio.json"; rmdir -- "$pasta" 2>/dev/null && rmdir -- "${pasta%/*}" 2>/dev/null || true; }
trap limpar EXIT
trap 'exit 130' HUP INT TERM
: > "$pasta/pronta" || exit 1
flock -n -E 75 "$trava" "$@"
resultado=$?
if ((resultado == 75)); then printf "%s\n" "Outra ação desta sessão ainda está em andamento."; fi
limpar
trap - EXIT
read -r -p "Enter para fechar " _
exit "$resultado"
"""
        argumentos = ['--classe', 'org.jangada.tarefas.acao', '--titulo', 'Tarefa: ' + nome,
                      '-e', 'bash', '-c', roteiro, 'jangada-tarefas', str(pasta), str(raiz.with_suffix('.trava')), *comando]
        processo = QProcess(self)
        self.preparar(processo, argumentos, 'jangada-terminal')
        iniciado, pid = processo.startDetached()
        processo.deleteLater()
        if iniciado:
            inicio['pid'] = pid
            try:
                if not (pasta / 'pronta').exists():
                    (pasta / 'inicio.json').write_text(json.dumps(inicio))
            except OSError:
                pass
            self.finalizando[nome] = pasta
            self.tempo_finalizacao.start()
            self.selecionar()
        else:
            (pasta / 'inicio.json').unlink()
            pasta.rmdir()
            raiz.rmdir()
        self.status.setText(f'Pedido para {acao} {nome} enviado ao terminal. Confira o resultado lá.'
                            if iniciado else 'Não foi possível abrir o terminal da ação.')

    def focar(self):
        nome = self.selecionada()
        if not self.dados_validos or nome not in self.sessoes or not NOME.fullmatch(nome):
            return
        if not self.real:
            self.status.setText(f'Simulação: abriria a sessão {nome}.')
            return
        if self.acao.state() != QProcess.ProcessState.NotRunning:
            return
        self.iniciar(self.acao, ['--focar', nome])
        self.selecionar()
        self.status.setText('Solicitando abertura da sessão…')
        self.tempo_acao.start(30000)

    def acao_fim(self, codigo, tipo):
        self.tempo_acao.stop()
        erro = bytes(self.acao.readAllStandardError()).decode('utf-8', 'replace')[:500]
        self.acao.readAllStandardOutput()
        if not self.fechando:
            self.status.setText('Pedido enviado ao jangada.' if codigo == 0 and tipo == QProcess.ExitStatus.NormalExit else 'Não foi possível abrir a sessão. ' + erro)
            self.selecionar()

    def acao_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.tempo_acao.stop()
            self.status.setText('Não foi possível iniciar o comando de abertura.')
            self.selecionar()

    def expirar_acao(self):
        self.acao.kill()

    def closeEvent(self, evento):
        if self.integracao_etapa is not None:
            self.status.setText('Aguarde a consulta ou integração terminar antes de fechar a Central.')
            evento.ignore()
            return
        self.fechando = True
        for timer in (self.timer, self.evento_estado, self.espera, self.tempo_acao, self.tempo_previa, self.tempo_finalizacao):
            timer.stop()
        for processo in (self.consulta, self.acao, self.previa, self.integracao):
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
                processo.waitForFinished(1000)
        self.finalizando.clear()
        evento.accept()
