"""Janela de conversa direta com o modelo local do Ollama, sem ferramentas nem histórico."""
import fcntl
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import urllib.request

from PyQt6.QtCore import QByteArray, QTimer, QUrl
from PyQt6.QtGui import QKeySequence, QShortcut, QTextDocument
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit,
                             QPushButton, QTextBrowser, QVBoxLayout, QWidget)

SISTEMA = 'Responda em português, de forma direta.'


def consultar(url):
    with urllib.request.urlopen(url, timeout=2) as resposta:
        return json.load(resposta)


def jogo_aberto():
    return subprocess.run(['pgrep', '-f', 'reaper SteamLaunch'], capture_output=True).returncode == 0


def vram_livre():
    try:
        saida = subprocess.run(
            ['nvidia-smi', '--query-gpu=memory.free', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=5).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    # Sem driver, o nvidia-smi escreve a falha na saída padrão; texto não é medição.
    linha = saida.strip().splitlines()[0].strip() if saida.strip() else ''
    return int(linha) if linha.isdigit() else None


class Leitura(QTextBrowser):
    def loadResource(self, tipo, nome):
        # A resposta do modelo não pode carregar imagens nem arquivos locais.
        return None


class Conversa(QWidget):
    def __init__(self):
        super().__init__()
        self.url = os.environ.get('JANGADA_OLLAMA_URL', 'http://localhost:11434')
        self.contexto = int(os.environ.get('JANGADA_LOCAL_CTX', 8192))
        estado = os.environ.get('JANGADA_ESTADO', Path.home()/'.local/state/jangada')
        self.arquivo_trava = Path(estado)/'local.lock'
        self.mensagens = []
        self.pergunta = ''
        self.resposta = ''
        self.chamada = None
        self.trava = None
        self.pendente = b''
        self.final = {}
        self.sujo = False
        # Modelos que ignoram think=false e despejam o raciocínio na resposta.
        self.sempre_pensam = set()
        self.rede = QNetworkAccessManager(self)
        self.setWindowTitle('Conversa local')
        self.resize(900, 720)
        layout = QVBoxLayout(self)
        topo = QHBoxLayout()
        nova = QPushButton('Nova conversa')
        nova.clicked.connect(self.nova)
        self.modelo = QComboBox()
        topo.addWidget(nova)
        topo.addStretch()
        topo.addWidget(self.modelo)
        layout.addLayout(topo)
        self.conversa = Leitura()
        self.conversa.setOpenLinks(False)
        layout.addWidget(self.conversa, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.entrada = QPlainTextEdit()
        self.entrada.setPlaceholderText('Escreva a pergunta. Ctrl+Enter envia.')
        self.entrada.setMaximumHeight(110)
        layout.addWidget(self.entrada)
        botoes = QHBoxLayout()
        copiar = QPushButton('Copiar resposta')
        copiar.clicked.connect(lambda: QApplication.clipboard().setText(self.resposta))
        self.parar = QPushButton('Parar')
        self.parar.clicked.connect(self.cancelar)
        self.enviar_botao = QPushButton('Enviar')
        self.enviar_botao.clicked.connect(self.enviar)
        for botao in (copiar, self.parar, self.enviar_botao):
            botoes.addWidget(botao)
        layout.addLayout(botoes)
        QShortcut(QKeySequence('Ctrl+Return'), self.entrada, self.enviar)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self.desenhar)
        self.timer.start()
        self.tema()
        self.ocupado(False)
        self.carregar_modelos()

    def tema(self):
        config = Path(os.environ.get('JANGADA_CONFIG', Path.home()/'.config/jangada'))
        arquivo = config/'waybar/cores.css'
        if not arquivo.exists():
            return
        cores = dict(re.findall(r'@define-color\s+(\w+)\s+(#[0-9a-fA-F]{6});', arquivo.read_text()))
        fundo = cores.get('superficie', '#202020')
        texto = cores.get('texto', '#eeeeee')
        self.setStyleSheet(f'QWidget {{ background: {fundo}; color: {texto}; }} '
                           'QPushButton { padding: 7px 12px; } QTextBrowser, QPlainTextEdit { padding: 8px; }')

    def carregar_modelos(self):
        try:
            nomes = sorted(modelo['name'] for modelo in consultar(f'{self.url}/api/tags')['models'])
        except (OSError, ValueError, KeyError, TypeError):
            self.status.setText(f'Ollama fora do ar em {self.url}.')
            return False
        self.modelo.clear()
        self.modelo.addItems(nomes)
        padrao = os.environ.get('JANGADA_LOCAL_MODELO', '')
        if padrao in nomes:
            self.modelo.setCurrentText(padrao)
        self.status.setText('Resposta do modelo local, sem verificação.' if nomes
                            else 'Nenhum modelo instalado no Ollama.')
        return bool(nomes)

    def ocupado(self, valor):
        self.enviar_botao.setEnabled(not valor)
        self.modelo.setEnabled(not valor)
        self.parar.setEnabled(valor)

    def impedimento(self):
        if jogo_aberto():
            return 'Há um jogo aberto; a placa de vídeo fica com ele.'
        livre = vram_livre()
        if livre is None:
            return None
        try:
            residentes = consultar(f'{self.url}/api/ps').get('models') or []
        except (OSError, ValueError, AttributeError):
            return f'Ollama fora do ar em {self.url}.'
        # O Ollama descarrega os modelos residentes para abrir espaço ao escolhido.
        residente = sum(modelo.get('size_vram', 0) for modelo in residentes) // 2**20
        minimo = int(os.environ.get('JANGADA_LOCAL_VRAM_MIN', 4000))
        if livre + residente < minimo:
            return (f'Memória de vídeo insuficiente: {livre} MiB livres e {residente} MiB '
                    f'do Ollama, com mínimo de {minimo} MiB.')
        return None

    def enviar(self):
        if self.chamada is not None:
            return
        pergunta = self.entrada.toPlainText().strip()
        if not pergunta or not (self.modelo.count() or self.carregar_modelos()):
            return
        self.arquivo_trava.parent.mkdir(parents=True, exist_ok=True)
        trava = open(self.arquivo_trava, 'w')
        try:
            fcntl.flock(trava, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            trava.close()
            self.status.setText('O modelo local está ocupado com uma delegação. Tente de novo em instantes.')
            return
        motivo = self.impedimento()
        if motivo:
            trava.close()
            self.status.setText(motivo)
            return
        self.trava = trava
        self.pergunta = pergunta
        self.resposta = ''
        self.pendente = b''
        self.final = {}
        self.sujo = True
        modelo = self.modelo.currentText()
        corpo = {'model': modelo, 'stream': True, 'think': modelo in self.sempre_pensam,
                 'options': {'num_ctx': self.contexto},
                 'messages': [{'role': 'system', 'content': SISTEMA}, *self.mensagens,
                              {'role': 'user', 'content': pergunta}]}
        pedido = QNetworkRequest(QUrl(f'{self.url}/api/chat'))
        pedido.setHeader(QNetworkRequest.KnownHeaders.ContentTypeHeader, 'application/json')
        self.chamada = self.rede.post(pedido, QByteArray(json.dumps(corpo).encode()))
        self.chamada.readyRead.connect(self.ler)
        self.chamada.finished.connect(self.terminou)
        self.entrada.clear()
        self.status.setText('Carregando o modelo…')
        self.ocupado(True)

    def ler(self, fim=False):
        # A recusa do Ollama chega como um objeto só, sem quebra de linha no fim.
        self.pendente += bytes(self.chamada.readAll()) + (b'\n' if fim else b'')
        *linhas, self.pendente = self.pendente.split(b'\n')
        for linha in linhas:
            try:
                parte = json.loads(linha)
            except ValueError:
                continue
            mensagem = parte.get('message') or {}
            if mensagem.get('thinking'):
                self.status.setText('Pensando…')
            if mensagem.get('content'):
                self.resposta += mensagem['content']
                self.status.setText('Respondendo…')
                self.sujo = True
            if parte.get('done') or parte.get('error'):
                self.final = parte
        if '</think>' in self.resposta:
            self.resposta = self.resposta.split('</think>', 1)[1]
            self.sempre_pensam.add(self.modelo.currentText())

    def terminou(self):
        self.ler(fim=True)
        self.resposta = self.resposta.strip()
        erro = self.chamada.error()
        self.chamada.deleteLater()
        self.chamada = None
        self.trava.close()
        self.trava = None
        if erro == QNetworkReply.NetworkError.OperationCanceledError:
            self.status.setText('Interrompida. O trecho parcial não entra no contexto da conversa.')
        elif erro != QNetworkReply.NetworkError.NoError or not self.final.get('done'):
            self.status.setText(self.final.get('error') or f'O Ollama não respondeu em {self.url}.')
        else:
            self.mensagens += [{'role': 'user', 'content': self.pergunta},
                               {'role': 'assistant', 'content': self.resposta}]
            self.pergunta = ''
            segundos = self.final.get('total_duration', 0) / 1e9
            usados = self.final.get('prompt_eval_count', 0) + self.final.get('eval_count', 0)
            self.status.setText(f'{segundos:.0f}s. Contexto: {usados} de {self.contexto} tokens.')
        self.ocupado(False)
        self.sujo = True

    def desenhar(self):
        if not self.sujo:
            return
        self.sujo = False
        mensagens = list(self.mensagens)
        if self.pergunta:
            mensagens += [{'role': 'user', 'content': self.pergunta},
                          {'role': 'assistant', 'content': self.resposta}]
        nomes = {'user': 'Você', 'assistant': 'Modelo local'}
        texto = '\n\n'.join(f"### {nomes[m['role']]}\n\n{m['content']}" for m in mensagens)
        self.conversa.document().setMarkdown(texto, QTextDocument.MarkdownFeature.MarkdownNoHTML)
        self.conversa.verticalScrollBar().setValue(self.conversa.verticalScrollBar().maximum())

    def cancelar(self):
        if self.chamada is not None:
            self.chamada.abort()

    def nova(self):
        if self.chamada is not None:
            return
        self.mensagens = []
        self.pergunta = ''
        self.resposta = ''
        self.sujo = True
        self.entrada.setFocus()

    def closeEvent(self, evento):
        self.cancelar()
        evento.accept()


if __name__ == '__main__':
    app = QApplication(sys.argv[:1])
    app.setDesktopFileName('org.jangada.conversa')
    janela = Conversa()
    janela.show()
    sys.exit(app.exec())
