"""Janela de chat. O motor continua num processo separado e cancelável."""
import codecs
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from PyQt6.QtCore import QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QTextDocument, QDesktopServices
from PyQt6.QtWidgets import (QApplication, QComboBox, QDialog, QDialogButtonBox,
                            QFormLayout, QGroupBox, QHBoxLayout, QLabel, QListWidget,
                            QListWidgetItem, QMessageBox, QPlainTextEdit, QPushButton,
                            QSpinBox, QSplitter, QTextBrowser, QVBoxLayout, QWidget)


class Leitura(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setOpenLinks(False)
        self.anchorClicked.connect(self.abrir_link)

    def abrir_link(self, url):
        if url.scheme() in ('https', 'http') and url.host() and not url.userInfo():
            QDesktopServices.openUrl(url)

    def loadResource(self, tipo, nome):
        # Markdown de fora não pode carregar imagens ou arquivos locais.
        return None


class Chat(QWidget):
    def __init__(self, motor, sessao=None, par=None):
        super().__init__()
        self.motor = motor
        self.sessao = sessao or f"sessao-{uuid4().hex[:16]}"
        motor.validar_sessao(self.sessao)
        self.par = par or 'claude-claude'
        self.rodadas = 1
        self.turnos = []
        self.atual = None
        self.buffer = ''; self.decoder = codecs.getincrementaldecoder('utf-8')('replace')
        self.erros = ''
        self.fim_recebido = False
        self.sujo = False
        self.segundos = 0
        self.setWindowTitle('Conversa de Pescador')
        self.resize(1080, 760)
        layout = QVBoxLayout(self)
        topo = QHBoxLayout()
        novo = QPushButton('Nova conversa'); novo.clicked.connect(self.nova)
        opcoes = QPushButton('Opções'); opcoes.clicked.connect(self.opcoes)
        self.modo = QComboBox(); self.modo.addItems(['Conversar', 'Pesquisar com fontes'])
        topo.addWidget(novo); topo.addStretch(); topo.addWidget(self.modo); topo.addWidget(opcoes)
        layout.addLayout(topo)
        divisor = QSplitter()
        self.sessoes = QListWidget(); self.sessoes.setMinimumWidth(200)
        self.sessoes.itemClicked.connect(self.abrir_sessao)
        divisor.addWidget(self.sessoes)
        self.conversa = Leitura(); self.conversa.setOpenLinks(False)
        divisor.addWidget(self.conversa); divisor.setStretchFactor(1, 1)
        layout.addWidget(divisor, 1)
        self.detalhes = QGroupBox('Fontes e detalhes da checagem')
        self.detalhes.setCheckable(True); self.detalhes.setChecked(False)
        self.texto_detalhes = Leitura(); self.texto_detalhes.setOpenLinks(False)
        self.texto_detalhes.setMaximumHeight(170)
        QVBoxLayout(self.detalhes).addWidget(self.texto_detalhes)
        self.texto_detalhes.hide()
        self.detalhes.toggled.connect(self.texto_detalhes.setVisible)
        layout.addWidget(self.detalhes)
        self.status = QLabel('Envie uma pergunta. Conversar não executa auditoria automática.')
        self.status.setWordWrap(True); layout.addWidget(self.status)
        self.entrada = QPlainTextEdit()
        self.entrada.setPlaceholderText('Escreva sua pergunta. Você pode colar várias linhas.')
        self.entrada.setMaximumHeight(110); layout.addWidget(self.entrada)
        botoes = QHBoxLayout()
        self.copiar = QPushButton('Copiar resposta'); self.copiar.clicked.connect(self.copiar_resposta)
        self.verificar = QPushButton('Verificar resposta'); self.verificar.clicked.connect(lambda: self.enviar(True))
        self.repetir = QPushButton('Repetir pergunta'); self.repetir.clicked.connect(self.repetir_pergunta)
        self.parar = QPushButton('Parar'); self.parar.clicked.connect(self.cancelar)
        self.enviar_botao = QPushButton('Enviar'); self.enviar_botao.clicked.connect(lambda: self.enviar(False))
        for botao in (self.copiar, self.verificar, self.repetir, self.parar, self.enviar_botao): botoes.addWidget(botao)
        layout.addLayout(botoes)
        self.processo = QProcess(self)
        self.processo.readyReadStandardOutput.connect(self.ler_saida)
        self.processo.readyReadStandardError.connect(self.ler_erro)
        self.processo.finished.connect(self.terminou)
        self.processo.errorOccurred.connect(self.erro_processo)
        self.timer = QTimer(self); self.timer.setInterval(100); self.timer.timeout.connect(self.atualizar)
        self.timer.start()
        self.fase = ''
        self.tema()
        self.listar_sessoes()
        self.carregar()
        self.ocupado(False)

    def tema(self):
        config = Path(os.environ.get('JANGADA_CONFIG', Path.home()/'.config/jangada'))
        arquivo = config/'waybar/cores.css'
        if not arquivo.exists(): return
        cores = dict(re.findall(r'@define-color\s+(\w+)\s+(#[0-9a-fA-F]{6});', arquivo.read_text()))
        fundo = cores.get('superficie', '#202020'); texto = cores.get('texto', '#eeeeee')
        self.setStyleSheet(f'QWidget {{ background: {fundo}; color: {texto}; }} '
                           'QPushButton { padding: 7px 12px; } QTextBrowser, QPlainTextEdit { padding: 8px; }')

    def listar_sessoes(self):
        self.sessoes.clear()
        pasta = self.motor.SESSOES_DIR
        if not pasta.exists() or pasta.is_symlink(): return
        arquivos = []
        for arquivo in pasta.glob('*.json'):
            try:
                if not arquivo.is_symlink(): arquivos.append((arquivo.stat().st_mtime, arquivo))
            except OSError: continue
        for _, arquivo in sorted(arquivos, key=lambda item: item[0], reverse=True):
            try:
                dados = self.motor.carregar_sessao(arquivo.stem)
                turnos = dados.get('turnos', [])
                titulo = turnos[0]['pergunta'].replace('\n', ' ')[:48] if turnos else arquivo.stem
                item = QListWidgetItem(titulo); item.setData(Qt.ItemDataRole.UserRole, arquivo.stem)
                item.setToolTip(arquivo.stem); self.sessoes.addItem(item)
            except (ValueError, OSError, KeyError, TypeError): continue

    def carregar(self):
        self.turnos = self.motor.carregar_sessao(self.sessao).get('turnos', [])
        self.atual = None; self.sujo = True
        self.mostrar_detalhes(self.turnos[-1] if self.turnos else {})

    def abrir_sessao(self, item):
        if self.processo.state() != QProcess.ProcessState.NotRunning: return
        self.sessao = item.data(Qt.ItemDataRole.UserRole)
        self.carregar(); self.ocupado(False)

    def nova(self):
        if self.processo.state() != QProcess.ProcessState.NotRunning: return
        self.sessao = f'sessao-{uuid4().hex[:16]}'
        self.carregar(); self.ocupado(False); self.entrada.setFocus()

    def opcoes(self):
        dialogo = QDialog(self); dialogo.setWindowTitle('Opções da conversa')
        formulario = QFormLayout(dialogo)
        par = QComboBox(); par.addItems(['claude-claude', 'claude-agy', 'agy-claude', 'agy-agy'])
        par.setCurrentText(self.par)
        rodadas = QSpinBox(); rodadas.setRange(1, 4); rodadas.setValue(self.rodadas)
        formulario.addRow('Par de modelos', par); formulario.addRow('Máximo de rodadas', rodadas)
        formulario.addRow(QLabel('Mais rodadas podem aumentar o tempo e o consumo.'))
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        botoes.accepted.connect(dialogo.accept); botoes.rejected.connect(dialogo.reject); formulario.addRow(botoes)
        if dialogo.exec(): self.par = par.currentText(); self.rodadas = rodadas.value()

    def ocupado(self, valor):
        self.enviar_botao.setEnabled(not valor); self.parar.setEnabled(valor)
        self.sessoes.setEnabled(not valor)
        self.verificar.setEnabled(not valor and bool(self.turnos))
        self.repetir.setEnabled(not valor and bool(self.turnos or self.atual))

    def enviar(self, verificar=False):
        if self.processo.state() != QProcess.ProcessState.NotRunning: return
        pergunta = self.turnos[-1]['pergunta'] if verificar and self.turnos else self.entrada.toPlainText().strip()
        if not pergunta: return
        if len(pergunta) > 32000:
            self.status.setText('A pergunta é muito longa. Envie até 32 mil caracteres.'); return
        self.atual = {'pergunta': pergunta, 'resposta': '', 'estado': 'gerando'}
        if verificar: self.atual['resposta'] = self.turnos[-1]['resposta']
        self.substituir_ultimo = verificar
        self.buffer = ''; self.decoder = codecs.getincrementaldecoder('utf-8')('replace'); self.erros = ''; self.fim_recebido = False; self.sujo = True
        self.segundos = 0; self.fase = 'Preparando resposta…'
        args = [str(Path(self.motor.__file__).resolve()), '--eventos', '--sessao', self.sessao,
                '--par', self.par, '--rodadas', str(self.rodadas)]
        if verificar: args.append('--verificar-ultima')
        else:
            if self.modo.currentIndex() == 0: args.append('--rapido')
            args.extend(['--', pergunta])
        env = QProcessEnvironment.systemEnvironment(); env.insert('PYTHONUNBUFFERED', '1')
        self.processo.setProcessEnvironment(env)
        self.processo.start(sys.executable, args)
        self.ocupado(True); self.entrada.clear()

    def ler_saida(self):
        self.buffer += self.decoder.decode(bytes(self.processo.readAllStandardOutput()))
        while '\n' in self.buffer:
            linha, self.buffer = self.buffer.split('\n', 1)
            try: evento = json.loads(linha)
            except ValueError: continue
            if evento.get('tipo') == 'trecho': self.atual['resposta'] += evento['texto']; self.sujo = True
            elif evento.get('tipo') == 'resposta':
                self.atual['resposta'] = evento['texto']; self.atual['estado'] = evento['estado']; self.sujo = True
            elif evento.get('tipo') == 'fase': self.fase = evento['texto']
            elif evento.get('tipo') == 'fim':
                self.atual = evento['registro']; self.fim_recebido = True
                self.fase = self.motor.ROTULOS[self.atual['estado']]
                self.mostrar_detalhes(self.atual); self.sujo = True

    def ler_erro(self):
        self.erros = (self.erros + bytes(self.processo.readAllStandardError()).decode('utf-8', 'replace'))[-2000:]

    def atualizar(self):
        if self.processo.state() != QProcess.ProcessState.NotRunning:
            self.segundos += 0.1; self.status.setText(f'{self.fase} {int(self.segundos)}s')
        if not self.sujo: return
        self.sujo = False
        registros = self.turnos[:-1] if self.atual and getattr(self, 'substituir_ultimo', False) else self.turnos
        if self.atual: registros = [*registros, self.atual]
        partes = []
        for registro in registros:
            estado = registro.get('estado', 'legado')
            rotulo = self.motor.ROTULOS.get(estado, {'gerando': 'Gerando resposta', 'verificando': 'Em verificação'}.get(estado, 'Histórico anterior, sem estado registrado'))
            partes.append(f"### Você\n\n{registro['pergunta']}\n\n### Pescador · {rotulo}\n\n{registro['resposta']}\n\n---")
        self.conversa.document().setMarkdown('\n\n'.join(partes), QTextDocument.MarkdownFeature.MarkdownNoHTML)
        self.conversa.verticalScrollBar().setValue(self.conversa.verticalScrollBar().maximum())

    def mostrar_detalhes(self, registro):
        aud = registro.get('auditoria', {})
        linhas = [aud.get('veredito_resumo', '')]
        for item in aud.get('analise_itens', []): linhas.append(f"{item['status']}: {item['afirmacao']}\n{item['detalhe']}")
        for fonte in registro.get('fontes', []): linhas.append(f"{fonte['titulo']}\n{fonte['url']}")
        if registro.get('fontes'): linhas.append('A checagem usa trechos da busca, não a leitura integral das fontes.')
        self.texto_detalhes.document().setMarkdown('\n\n'.join(linhas), QTextDocument.MarkdownFeature.MarkdownNoHTML)

    def terminou(self, *_):
        self.ler_saida(); self.ler_erro()
        if self.fim_recebido:
            estado = self.atual['estado']
            if estado not in ('cancelado', 'erro'):
                self.carregar(); self.listar_sessoes()
            self.status.setText(self.fase)
        else:
            if self.atual: self.atual['estado'] = 'erro'
            self.status.setText(self.erros.strip() or 'A consulta terminou sem resposta. Você pode tentar novamente.')
        self.ocupado(False); self.sujo = True

    def erro_processo(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.status.setText('Não foi possível iniciar o motor da conversa.'); self.ocupado(False)

    def cancelar(self):
        self.processo.terminate(); self.fase = 'Interrompendo consulta…'; self.parar.setEnabled(False)

    def copiar_resposta(self):
        registro = self.atual or (self.turnos[-1] if self.turnos else {})
        QApplication.clipboard().setText(registro.get('resposta', ''))

    def repetir_pergunta(self):
        registro = self.atual or (self.turnos[-1] if self.turnos else {})
        self.entrada.setPlainText(registro.get('pergunta', '')); self.entrada.setFocus()

    def closeEvent(self, evento):
        if self.processo.state() != QProcess.ProcessState.NotRunning:
            self.cancelar()
            QMessageBox.information(self, 'Consulta em andamento', 'A consulta está sendo interrompida. Feche a janela após o encerramento.')
            evento.ignore()
        else: evento.accept()


def abrir(sessao, par, motor):
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setDesktopFileName('org.jangada.pescador')
    janela = Chat(motor, sessao, par)
    janela.show()
    return app.exec()
