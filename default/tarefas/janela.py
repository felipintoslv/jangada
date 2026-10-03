"""Janela companheira experimental. Sem instalação ou terminal embutido."""
import argparse
from dataclasses import dataclass, replace
from datetime import datetime
import html
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import QApplication, QComboBox, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QSplitter, QTabWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget
import re
import stat

NOME = re.compile(r"[A-Za-z0-9_.-]+")
LIMITE = 1024 * 1024
CORES = {'aguardando': '#f2c66d', 'trabalhando': '#85baff', 'concluido': '#96d6a8', 'interrompido': '#f09d93'}
ROTULOS = {'aguardando': 'Precisa de você', 'trabalhando': 'Em andamento', 'concluido': 'Turno encerrado', 'interrompido': 'Interrompida'}
ORDEM = {'aguardando': 0, 'interrompido': 1, 'trabalhando': 2, 'concluido': 4}
AGENTES = ('claude', 'codex', 'agy')

def estado_exibido(sessao):
    return 'trabalhando' if sessao.estado in ('ativo', 'iniciado') else sessao.estado

def idade(atualizado, agora=None):
    try:
        data = datetime.fromisoformat(atualizado)
        agora = agora or datetime.now().astimezone()
        if data.tzinfo is None:
            data = data.astimezone()
        segundos = (agora - data).total_seconds()
        if segundos < -60:
            return 'Horário futuro'
        if segundos < 60:
            return 'Agora'
        minutos = int(segundos // 60)
        if minutos < 60:
            return f'Há {minutos} min'
        horas = minutos // 60
        dias = horas // 24
        return f'Há {horas} h' if horas < 24 else f'Há {dias} ' + ('dia' if dias == 1 else 'dias')
    except (ValueError, TypeError, OverflowError):
        return 'Sem horário'

def resumo_barra(sessoes):
    contagem = {estado: sum((estado_exibido(s) == estado for s in sessoes.values())) for estado in CORES}
    partes = [f'Tarefas {len(sessoes)}']
    for estado, rotulo in (('trabalhando', 'em andamento'), ('aguardando', 'precisam de você'), ('interrompido', 'interrompidas')):
        if contagem[estado]:
            if estado == 'aguardando' and contagem[estado] == 1:
                rotulo = 'precisa de você'
            if estado == 'interrompido' and contagem[estado] == 1:
                rotulo = 'interrompida'
            partes.append(f'{contagem[estado]} {rotulo}')
    classe = next((e for e in ORDEM if contagem[e]), 'vazio' if not sessoes else 'ativo')
    linhas = [f'{s.projeto} · {(s.tarefa.splitlines()[0] if s.tarefa else s.nome)} [{ROTULOS.get(estado_exibido(s), estado_exibido(s))}]' for s in sorted(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.projeto, s.nome))]
    return {'text': ' · '.join(partes), 'class': classe, 'tooltip': html.escape('\n'.join(linhas + ['Clique: central de tarefas · Clique direito: nova tarefa']))}

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
            self.projeto.setText(s.dir)
        elif not janela.real:
            self.projeto.setText(str(Path.cwd()))
        escolher = QPushButton('Escolher pasta')
        escolher.clicked.connect(self.escolher_pasta)
        linha = QHBoxLayout()
        linha.addWidget(self.projeto)
        linha.addWidget(escolher)
        formulario.addRow('Projeto', linha)
        self.agente = QComboBox()
        self.agente.addItems(AGENTES)
        formulario.addRow('Agente', self.agente)
        layout.addLayout(formulario)
        layout.addWidget(QLabel('O que você quer que o agente faça?'))
        self.pedido = QPlainTextEdit()
        self.pedido.setPlaceholderText('Descreva a tarefa, o resultado esperado e as restrições.')
        layout.addWidget(self.pedido)
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
        self.agente.currentTextChanged.connect(self.reeditar)
        botoes.addWidget(fechar)
        botoes.addStretch()
        botoes.addWidget(self.enviar)
        layout.addLayout(botoes)

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Escolher projeto', self.projeto.text())
        if pasta:
            self.projeto.setText(pasta)

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
        nome = 'tarefa-' + uuid.uuid4().hex[:12]
        if not self.janela.real:
            sessao = Sessao(nome, 'trabalhando', str(projeto), datetime.now().isoformat(), 'agente/' + nome, pedido, agente, projeto.name, 'Tarefa simulada. Nenhum agente foi executado.')
            self.janela.criadas[nome] = sessao
            self.janela.atualizar()
            self.janela.selecionar_nome(nome)
            self.erro.setText('Tarefa simulada criada. Você pode acompanhar na lista.')
        else:
            processo = QProcess(self)
            self.janela.preparar(processo, ['--janela', '--projeto', str(projeto), '--nome', nome, '--agente', agente, '--prompt', pedido], 'jangada-agente')
            iniciado, _ = processo.startDetached()
            if not iniciado:
                self.erro.setText('Não foi possível iniciar jangada-agente. Confira --jangada.')
                return
            self.erro.setText('Abertura solicitada. Confira no terminal se a tarefa iniciou. Seu pedido foi preservado.')
        self.enviar.setEnabled(False)

    def reeditar(self, *_):
        self.enviar.setEnabled(True)
        self.erro.clear()

@dataclass
class Sessao:
    nome: str
    estado: str
    dir: str
    atualizado: str
    ramo: str
    tarefa: str
    agente: str = 'Não informado'
    projeto: str = 'Sem projeto'
    mensagem: str = ''
    inicio: str = ''

def texto(valor):
    return valor[:16000] if isinstance(valor, str) else ''

def registro(pasta, nome):
    try:
        fd = os.open(pasta / (nome + ".json"), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as arquivo:
            if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                return {}
            bruto = arquivo.read(LIMITE + 1)
        if len(bruto) > LIMITE:
            return {}
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def ler_lista(saida, pasta):
    sessoes = {}
    for linha in saida.splitlines():
        campos = linha.split('\t')
        if len(campos) != 6:
            raise ValueError('A listagem recebida não tem os seis campos esperados.')
        estado, nome, diretorio, atualizado, ramo, tarefa = campos
        if not NOME.fullmatch(nome) or nome in ('.', '..'):
            raise ValueError('A listagem contém um nome de sessão inválido.')
        dados = registro(pasta, nome)
        raiz = texto(dados.get('raiz')) or diretorio
        inicio = texto(dados.get('desde'))
        sessoes[nome] = Sessao(nome, estado, diretorio, atualizado, html.unescape(ramo), texto(dados.get('tarefa')) or html.unescape(tarefa), texto(dados.get('agente')) or 'Não informado', Path(raiz).name or 'Sem projeto', texto(dados.get('mensagem')), inicio)
    return sessoes

def simuladas(passo):
    estados = ['aguardando', 'trabalhando', 'concluido', 'interrompido']
    tarefas = ['Conferir a proposta de interface', 'Ajustar o roteamento de tarefas', 'Revisar as referências do artigo', 'Retomar a revisão da instalação']
    resultado = {}
    for i, nome in enumerate(['jangada--interface', 'jangada--router', 'artigo--fontes', 'jangada--instalacao']):
        if passo % 4 == 3 and i == 2:
            continue
        estado = estados[i]
        if i == 1:
            estado = ['trabalhando', 'aguardando', 'concluido', 'trabalhando'][passo % 4]
        projeto = 'artigo' if i == 2 else 'jangada'
        resultado[nome] = Sessao(nome, estado, f'/exemplo/{projeto}', datetime.now().astimezone().isoformat(), 'agente/' + nome.split('--')[1], tarefas[i], ['claude', 'codex', 'agy', 'claude'][i], projeto, ['Podemos começar pelo contador da Waybar?', 'Ajustando o roteamento de tarefas.', 'Referências conferidas. Quer acrescentar alguma fonte?', 'A sessão foi interrompida e pode ser retomada.'][i])
    return resultado

class Janela(QMainWindow):

    def __init__(self, real=False, jangada=None, estado=None):
        super().__init__()
        self.real = real
        self.eventos = {}
        self.observadas = {}
        self.jangada = Path(jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
        self.estado_dir = Path(estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser()
        self.sessoes = {}
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
        direito.addWidget(self.abas)
        self.abrir = QPushButton('Abrir sessão')
        self.abrir.setEnabled(False)
        self.abrir.clicked.connect(self.focar)
        direito.addWidget(self.abrir)
        explicacao = QLabel('A conversa abre no terminal neste piloto. Uma tarefa corresponde a uma sessão. Turno encerrado não confirma a conclusão da tarefa.')
        explicacao.setWordWrap(True)
        direito.addWidget(explicacao)
        divisor.addWidget(detalhes)
        divisor.setSizes([650, 400])
        layout.addWidget(divisor, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.setStyleSheet('\n            QWidget { background: #182128; color: #e1e9ec; font-size: 13px; }\n            QTreeWidget, QPlainTextEdit, QLineEdit, QComboBox { background: #11191f; border: 1px solid #35454f;\n                border-radius: 6px; padding: 8px; }\n            QTreeWidget::item { padding: 8px 3px; }\n            QTreeWidget::item:selected { background: #2d4956; }\n            QHeaderView::section { background: #23313b; border: none; padding: 8px; }\n            QPushButton { background: #294551; border: 1px solid #48616b;\n                border-radius: 6px; padding: 10px 16px; }\n            QPushButton:hover { background: #365b69; }\n            QPushButton:disabled { color: #74838a; background: #202c33; }\n        ')
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
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self.atualizar)
        if real:
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
        anterior = self.selecionada()
        primeira_carga = not self.sessoes and anterior is None
        self.sessoes = sessoes
        self.acompanhar_mudancas(sessoes)
        self.lista.blockSignals(True)
        self.lista.clear()
        grupos = {}
        itens = {}
        for s in sorted(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.projeto, s.nome)):
            grupo = {'aguardando': 'Precisa de você', 'interrompido': 'Interrompidas', 'trabalhando': 'Em andamento', 'concluido': 'Turno encerrado'}.get(estado_exibido(s), 'Outras tarefas')
            if grupo not in grupos:
                grupos[grupo] = QTreeWidgetItem(self.lista, [grupo])
                grupos[grupo].setFlags(Qt.ItemFlag.ItemIsEnabled)
                grupos[grupo].setExpanded(True)
            tarefa = s.tarefa.splitlines()[0] if s.tarefa else s.nome
            item = QTreeWidgetItem(grupos[grupo], [tarefa, s.projeto, ROTULOS.get(estado_exibido(s), estado_exibido(s)), idade(s.atualizado)])
            item.setToolTip(0, '<qt>' + html.escape(s.tarefa or s.nome).replace('\n', '<br>') + '</qt>')
            item.setData(0, Qt.ItemDataRole.UserRole, s.nome)
            item.setForeground(2, QColor(CORES.get(estado_exibido(s), '#b7c6cd')))
            itens[s.nome] = item
        escolhido = itens.get(anterior)
        if primeira_carga and itens:
            prioridade = min(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.nome))
            escolhido = itens[prioridade.nome]
        if escolhido:
            self.lista.setCurrentItem(escolhido)
        self.lista.blockSignals(False)
        self.selecionar()
        esperando = sum((estado_exibido(s) == 'aguardando' for s in sessoes.values()))
        interrompidas = sum((estado_exibido(s) == 'interrompido' for s in sessoes.values()))
        rotulo = 'interrompida' if interrompidas == 1 else 'interrompidas'
        self.resumo.setText((f'{len(sessoes)} tarefas acompanhadas · Atualização a cada 2 segundos' if self.real else f'{len(sessoes)} tarefas fictícias · Avance a simulação para acompanhar as mudanças') if sessoes else 'Nenhuma tarefa. Inicie pelo botão Nova tarefa.')
        andando = sum((estado_exibido(s) == 'trabalhando' for s in sessoes.values()))
        encerrados = sum((estado_exibido(s) == 'concluido' for s in sessoes.values()))
        espera_rotulo = 'precisa de você' if esperando == 1 else 'precisam de você'
        turno_rotulo = 'turno encerrado' if encerrados == 1 else 'turnos encerrados'
        self.cartoes.setText(f'{esperando} {espera_rotulo}    ·    {andando} em andamento    ·    {interrompidas} {rotulo}    ·    {encerrados} {turno_rotulo}')
        if anterior and anterior not in sessoes:
            self.status.setText('A sessão selecionada saiu da lista. Selecione outra sessão.')

    def selecionar(self, *_):
        s = self.sessoes.get(self.selecionada())
        ocupada = self.acao.state() != QProcess.ProcessState.NotRunning
        self.abrir.setEnabled(s is not None and (not ocupada))
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
            self.iniciar(self.consulta, ['--lista'])
            self.espera.start(10000)

    def consulta_fim(self, codigo, tipo):
        self.espera.stop()
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
        self.mostrar({})
        self.status.setText(mensagem)

    def consulta_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.espera.stop()
            self.falha('Não foi possível iniciar jangada-agentes. Confira o caminho em --jangada.')

    def expirar(self):
        self.consulta.kill()

    def focar(self):
        nome = self.selecionada()
        if nome not in self.sessoes or not NOME.fullmatch(nome):
            return
        if not self.real:
            self.status.setText(f'Simulação: abriria a sessão {nome}.')
            return
        if self.acao.state() != QProcess.ProcessState.NotRunning:
            return
        self.iniciar(self.acao, ['--focar', nome])
        self.abrir.setEnabled(False)
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
        self.fechando = True
        for timer in (self.timer, self.espera, self.tempo_acao, self.tempo_previa):
            timer.stop()
        for processo in (self.consulta, self.acao, self.previa):
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
                processo.waitForFinished(1000)
        evento.accept()

def barra(args):
    if not args.real:
        return resumo_barra(simuladas(0))
    jangada = Path(args.jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
    estado = Path(args.estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser()
    try:
        ambiente = dict(os.environ, JANGADA_PATH=str(jangada),
                        XDG_STATE_HOME=str(estado.parent.parent))
        resposta = subprocess.run([str(jangada / 'bin/jangada-agentes'), '--lista'], capture_output=True, timeout=10, env=ambiente, check=True)
        if len(resposta.stdout) > LIMITE:
            raise ValueError('A listagem excedeu o limite de leitura.')
        return resumo_barra(ler_lista(resposta.stdout.decode('utf-8', 'replace'), estado))
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'text': 'Tarefas · erro', 'class': 'erro', 'tooltip': 'Não foi possível consultar sessões. Clique para abrir a central e conferir o erro.'}

def encaminhar(nome, nova=False):
    socket = QLocalSocket()
    socket.setSocketOptions(QLocalSocket.SocketOption.AbstractNamespaceOption)
    socket.connectToServer(nome)
    if not socket.waitForConnected(500):
        return False
    socket.write(b'nova\n' if nova else b'mostrar\n')
    enviado = socket.waitForBytesWritten(1000)
    socket.disconnectFromServer()
    return enviado

def receber(servidor, janela):
    while servidor.hasPendingConnections():
        socket = servidor.nextPendingConnection()
        buffer = bytearray()

        def ler(socket=socket, buffer=buffer):
            buffer.extend(bytes(socket.readAll()))
            if len(buffer) > 32:
                socket.disconnectFromServer()
                return
            if b'\n' not in buffer:
                return
            janela.showNormal()
            janela.raise_()
            janela.activateWindow()
            if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
                QProcess.startDetached('hyprctl', ['dispatch', 'focuswindow', f'pid:{os.getpid()}'])
            if bytes(buffer).split(b'\n', 1)[0] == b'nova':
                janela.nova_tarefa()
            socket.disconnectFromServer()
        socket.readyRead.connect(ler)
        socket.disconnected.connect(socket.deleteLater)
        if socket.bytesAvailable():
            ler()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', action='store_true', help='Consultar e abrir sessões reais')
    parser.add_argument('--jangada', type=Path, help='Pasta do jangada; padrão: ~/.local/share/jangada')
    parser.add_argument('--estado', type=Path, help='Pasta dos JSON de sessões; padrão: estado XDG do jangada/agentes')
    parser.add_argument('--waybar', action='store_true', help='Emitir contador JSON e sair')
    parser.add_argument('--mostrar', action='store_true', help='Abrir ou focar a central em segundo plano')
    parser.add_argument('--nova', action='store_true', help='Abrir o formulário de nova tarefa')
    args = parser.parse_args()
    if args.waybar:
        print(json.dumps(barra(args), ensure_ascii=False))
        return
    app = QApplication(sys.argv[:1])
    app.setApplicationName('org.jangada.tarefas')
    app.setDesktopFileName('org.jangada.tarefas')
    jangada = Path(args.jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
    estado = Path(args.estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser().resolve()
    identidade = f'{os.getuid()}:{Path(__file__).resolve()}:tarefas-v0.1:{args.real}:{jangada}:{estado}'
    nome = 'jangada-tarefas-' + hashlib.sha256(identidade.encode()).hexdigest()[:24]
    if encaminhar(nome, args.nova):
        return
    if args.mostrar:
        argumentos = [a for a in sys.argv[1:] if a != '--mostrar']
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *argumentos], start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return
    servidor = QLocalServer(app)
    servidor.setSocketOptions(QLocalServer.SocketOption.AbstractNamespaceOption)
    if not servidor.listen(nome):
        if encaminhar(nome, args.nova):
            return
        parser.exit(1, 'Não foi possível abrir a central.\n')
    janela = Janela(args.real, args.jangada, args.estado)
    servidor.newConnection.connect(lambda: receber(servidor, janela))
    janela.show()
    if args.nova:
        janela.nova_tarefa()
    sys.exit(app.exec())
if __name__ == '__main__':
    main()
