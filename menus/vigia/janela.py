"""Janela Qt da conversa com o Vigia, sobre o motor de conversa.py.

O retrato e as chamadas ao agy rodam em outra linha de execução; a linha
principal só mostra texto simples. Abre pelo `jangada-vigia janela`.
"""
import argparse
import fcntl
import html
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading

RAIZ = Path(__file__).resolve().parents[2]
for _pasta in (RAIZ / 'menus/vigia', RAIZ / 'menus/tarefas', RAIZ / 'default'):
    if str(_pasta) not in sys.path:
        sys.path.insert(0, str(_pasta))
sys.dont_write_bytecode = True

from PyQt6.QtCore import QObject, QTimer, QUrl, Qt, pyqtSignal  # noqa: E402
from PyQt6.QtGui import QDesktopServices, QGuiApplication, QKeySequence, QShortcut  # noqa: E402
from PyQt6.QtWidgets import (QApplication, QComboBox, QHBoxLayout, QLabel, QPlainTextEdit,  # noqa: E402
                             QSizePolicy, QVBoxLayout, QWidget)
from aparencia import BotaoComMotivo, Cabecalho, botao, folha_de_estilo  # noqa: E402
from conversa import Conversa, ErroConversa, filtrar  # noqa: E402
from visual.fichas import carregar as carregar_fichas  # noqa: E402

LOGO = RAIZ / 'default/logo/jangada-symbolic.svg'
RISCOS = RAIZ / 'docs/vigia/riscos.md'
CLASSE = 'org.jangada.vigia'
TEMPO_RETRATO = 300
AVISO_SAIDA = ('Sai da máquina: o retrato do sistema, já mascarado, e as suas perguntas, '
               'enviados ao agy (serviço do Google). Nada é aplicado no sistema.')
SEM_PROPOSTA = 'Peça uma proposta primeiro.'


class Tentativa:
    """Retrato e conversa de uma abertura; cancelar pode vir de outra linha."""

    def __init__(self, vigia, argumentos, conversa):
        self.vigia = vigia
        self.argumentos = list(argumentos)
        self.conversa = conversa
        self._trava = threading.Lock()
        self._processo = None
        self.cancelada = False

    def abrir(self):
        return self.conversa.iniciar(self._retrato())

    def _retrato(self):
        with self._trava:
            if self.cancelada:
                raise ErroConversa('a conversa foi cancelada')
            try:
                processo = subprocess.Popen([self.vigia, 'retrato-conversa', *self.argumentos],
                                            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                            stderr=subprocess.PIPE, start_new_session=True)
            except OSError as erro:
                raise ErroConversa(f'não foi possível gerar o retrato: {erro}') from None
            self._processo = processo
        try:
            saida, erros = processo.communicate(timeout=TEMPO_RETRATO)
        except subprocess.TimeoutExpired:
            _sinalizar(processo, signal.SIGKILL)
            processo.communicate()
            raise ErroConversa(f'o retrato não ficou pronto em {TEMPO_RETRATO} s') from None
        finally:
            with self._trava:
                self._processo = None
        if self.cancelada:
            raise ErroConversa('a conversa foi cancelada')
        if processo.returncode != 0:
            detalhe = filtrar(erros.decode('utf-8', errors='replace'))[-300:]
            raise ErroConversa('não foi possível gerar o retrato' + (f': {detalhe}' if detalhe else ''))
        try:
            retrato = json.loads(saida.decode('utf-8', errors='replace'))
        except ValueError:
            raise ErroConversa('o retrato gerado não é JSON') from None
        if not isinstance(retrato, dict):
            raise ErroConversa('o retrato não é um objeto JSON')
        return retrato

    def cancelar(self):
        """Interrompe o retrato ou o agy e apaga a pasta da conversa."""
        with self._trava:
            self.cancelada = True
            processo = self._processo
        if processo is not None and processo.poll() is None:
            # TERM deixa o jangada-vigia apagar os temporários do diagnóstico.
            _sinalizar(processo, signal.SIGTERM)
            espera = threading.Timer(5, _sinalizar, (processo, signal.SIGKILL))
            espera.daemon = True
            espera.start()
        self.conversa.encerrar()


def _sinalizar(processo, sinal):
    if processo.poll() is None:
        try:
            os.killpg(processo.pid, sinal)
        except OSError:
            pass


class Ponte(QObject):
    """Leva o resultado da linha de trabalho para a linha da interface."""
    terminou = pyqtSignal(int, str, str, str)


class Janela(QWidget):

    def __init__(self, vigia, pasta, retrato=None, ambiente=None, agy='agy'):
        super().__init__()
        self.vigia = str(vigia)
        self.pasta = Path(pasta)
        self.argumentos_retrato = ['--retrato', retrato] if retrato else []
        self.ambiente = ambiente
        self.agy = agy
        self.tentativa = None
        self.linha = None
        self.geracao = 0
        self.segundos = 0
        self.espera = ''
        self.fichas = carregar_fichas()
        self.ponte = Ponte()
        self.ponte.terminou.connect(self.receber)
        self.setWindowTitle('Jangada · Vigia')
        self.resize(1000, 720)
        self.setMinimumSize(700, 460)

        layout = self.layout_principal = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        self.cabecalho = Cabecalho('Vigia', LOGO)
        self.modo = QComboBox()
        self.modo.addItems(['Escuro', 'Claro'])
        self.modo.setAccessibleName('Modo de cor')
        self.modo.setCurrentIndex(1 if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else 0)
        self.modo.currentIndexChanged.connect(self.aplicar_tema)
        self.cabecalho.linha.addWidget(self.modo)
        layout.addWidget(self.cabecalho)

        # Único texto rico da janela, e é fixo: nada do agy nem do retrato passa por aqui.
        self.aviso = QLabel(f'{html.escape(AVISO_SAIDA)} <a href="riscos">Riscos e contenção</a>')
        self.aviso.setObjectName('aviso_saida')
        self.aviso.setTextFormat(Qt.TextFormat.RichText)
        self.aviso.setWordWrap(True)
        self.aviso.setAccessibleName(AVISO_SAIDA)
        self.aviso.linkActivated.connect(self.abrir_riscos)
        layout.addWidget(self.aviso)

        self.historico = QPlainTextEdit()
        self.historico.setObjectName('historico')
        self.historico.setReadOnly(True)
        self.historico.setAccessibleName('Conversa com o Vigia')
        layout.addWidget(self.historico, 1)

        situacao = QHBoxLayout()
        situacao.setSpacing(8)
        self.situacao = QLabel()
        self.situacao.setObjectName('situacao')
        self.situacao.setTextFormat(Qt.TextFormat.PlainText)
        self.situacao.setWordWrap(True)
        situacao.addWidget(self.situacao, 1)
        self.cancelar_botao = botao('Cancelar', 'perigo')
        self.cancelar_botao.setToolTip('Interrompe a espera, encerra a conversa e apaga a pasta temporária.')
        self.cancelar_botao.clicked.connect(self.cancelar)
        situacao.addWidget(self.cancelar_botao)
        self.recomecar_botao = botao('Nova conversa')
        self.recomecar_botao.setToolTip('Gera um retrato novo e abre outra conversa com o agy.')
        self.recomecar_botao.clicked.connect(self.iniciar)
        situacao.addWidget(self.recomecar_botao)
        layout.addLayout(situacao)

        self.erro = QLabel()
        self.erro.setObjectName('erro')
        self.erro.setTextFormat(Qt.TextFormat.PlainText)
        self.erro.setWordWrap(True)
        self.erro.hide()
        layout.addWidget(self.erro)

        self.pergunta = QPlainTextEdit()
        self.pergunta.setObjectName('pergunta')
        self.pergunta.setPlaceholderText('Pergunte sobre o retrato do sistema. Ctrl+Enter envia.')
        self.pergunta.setAccessibleName('Pergunta ao Vigia')
        self.pergunta.setTabChangesFocus(True)
        self.pergunta.setFixedHeight(72)
        layout.addWidget(self.pergunta)

        acoes = QHBoxLayout()
        acoes.setSpacing(8)
        self.proposta_botao = botao('Pedir proposta')
        self.proposta_botao.setToolTip('Pede ao agy a proposta final: o que mudar, por quê, o que testar e como desfazer.')
        self.proposta_botao.clicked.connect(self.pedir_proposta)
        acoes.addWidget(self.proposta_botao)
        self.salvar_botao = botao('Salvar proposta')
        self.salvar_botao.clicked.connect(self.salvar_proposta)
        self.salvar_botao.setSizePolicy(QSizePolicy.Policy.Maximum, self.salvar_botao.sizePolicy().verticalPolicy())
        self.salvar_motivo = BotaoComMotivo(self.salvar_botao)
        self.salvar_motivo.layout().setAlignment(self.salvar_botao, Qt.AlignmentFlag.AlignLeft)
        acoes.addWidget(self.salvar_motivo, 1)
        self.fechar_botao = botao('Fechar')
        self.fechar_botao.setToolTip('Encerra a conversa e apaga a pasta temporária.')
        self.fechar_botao.clicked.connect(self.close)
        acoes.addWidget(self.fechar_botao)
        self.enviar_botao = botao('Enviar', 'principal')
        self.enviar_botao.setToolTip('Ctrl+Enter')
        self.enviar_botao.clicked.connect(self.enviar)
        acoes.addWidget(self.enviar_botao)
        layout.addLayout(acoes)
        for tecla in ('Ctrl+Return', 'Ctrl+Enter'):
            QShortcut(QKeySequence(tecla), self).activated.connect(self.enviar)

        self.relogio = QTimer(self)
        self.relogio.setInterval(1000)
        self.relogio.timeout.connect(self.contar)
        self.aplicar_tema()
        self.iniciar()

    def aplicar_tema(self):
        modo = 'light' if self.modo.currentIndex() == 1 else 'dark'
        c = self.fichas[modo]
        self.setStyleSheet(folha_de_estilo(c, modo) + f"""
            QPlainTextEdit#historico, QPlainTextEdit#pergunta {{ font-family: Inter; font-size: 14px; }}
            QLabel#aviso_saida {{ background: {c['superficie_elevada']}; padding: 8px 12px;
                border-radius: 8px; font-size: 13px; }}
            QLabel#situacao {{ color: {c['texto_suave']}; }}
            QLabel#erro {{ color: {c['atencao']}; font-weight: 600; }}
        """)
        # Cor do link no aviso: a folha não alcança o texto rico do rótulo.
        self.aviso.setText(f'{html.escape(AVISO_SAIDA)} <a href="riscos" style="color:{c["primaria"]}">'
                           'Riscos e contenção</a>')
        self.cabecalho.pintar(c)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        larga = self.width() >= 1080
        self.layout_principal.setContentsMargins(*((24, 20, 24, 16) if larga else (16, 12, 16, 12)))
        self.cabecalho.compactar(not larga)

    def abrir_riscos(self, _):
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(RISCOS)))

    # Estados: espera (retrato ou agy), pronta (conversa aberta) e encerrada.
    def mostrar_estado(self):
        esperando = self.linha is not None
        aberta = self.tentativa is not None and not self.tentativa.cancelada and bool(self.tentativa.conversa.id)
        self.cancelar_botao.setVisible(esperando)
        self.recomecar_botao.setVisible(not esperando and not aberta)
        for controle in (self.enviar_botao, self.proposta_botao, self.pergunta):
            controle.setEnabled(aberta and not esperando)
        if self.tentativa is not None and self.tentativa.conversa.ultima_proposta:
            self.salvar_motivo.disponivel()
        else:
            self.salvar_motivo.indisponivel(SEM_PROPOSTA)
        if esperando:
            self.situacao.setText(f'{self.espera} {self.segundos} s')
        elif aberta:
            self.situacao.setText('Pronto para a próxima pergunta.')
        else:
            self.situacao.setText('Conversa encerrada. A pasta temporária foi apagada.')

    def contar(self):
        self.segundos += 1
        self.mostrar_estado()

    def falar(self, quem, texto):
        if self.historico.toPlainText():
            self.historico.appendPlainText('')
        self.historico.appendPlainText(f'{quem}:\n{texto}')
        barra = self.historico.verticalScrollBar()
        barra.setValue(barra.maximum())

    def mostrar_erro(self, texto):
        self.erro.setText(f'Erro: {texto}' if texto else '')
        self.erro.setVisible(bool(texto))

    def trabalhar(self, tipo, funcao, espera):
        """Roda funcao fora da linha da interface; o resultado volta por receber."""
        self.geracao += 1
        geracao = self.geracao
        self.espera = espera
        self.segundos = 0
        self.mostrar_erro('')

        def rodar():
            try:
                resultado = ('ok', funcao())
            except ErroConversa as erro:
                resultado = ('erro', str(erro))
            except Exception as erro:  # a linha não pode morrer calada
                resultado = ('erro', f'falha inesperada: {filtrar(str(erro))[:300]}')
            try:
                self.ponte.terminou.emit(geracao, tipo, *resultado)
            except RuntimeError:
                pass

        self.linha = threading.Thread(target=rodar, name=f'vigia-{tipo}', daemon=True)
        self.linha.start()
        self.relogio.start()
        self.mostrar_estado()

    def receber(self, geracao, tipo, resultado, texto):
        if geracao != self.geracao:
            return
        self.linha = None
        self.relogio.stop()
        if resultado == 'ok':
            self.falar('Vigia', texto)
        else:
            self.mostrar_erro(texto)
            if tipo == 'abertura' and self.tentativa is not None:
                self.tentativa.cancelar()
        self.mostrar_estado()
        if self.pergunta.isEnabled():
            self.pergunta.setFocus()

    def iniciar(self):
        if self.linha is not None:
            return
        conversa = Conversa(pasta_propostas=self.pasta / 'propostas',
                            pasta_conversas=self.pasta / 'conversas',
                            agy=self.agy, ambiente=self.ambiente)
        self.tentativa = Tentativa(self.vigia, self.argumentos_retrato, conversa)
        if self.historico.toPlainText():
            self.falar('Jangada', 'Nova conversa.')
        self.trabalhar('abertura', self.tentativa.abrir,
                       'Gerando o retrato do sistema e abrindo a conversa com o agy (de 20 a 35 s por resposta)...')

    def enviar(self):
        if self.linha is not None or not self.pergunta.isEnabled():
            return
        texto = self.pergunta.toPlainText().strip()
        if not texto:
            self.mostrar_erro('escreva a pergunta antes de enviar')
            return
        self.pergunta.clear()
        self.falar('Você', filtrar(texto))
        conversa = self.tentativa.conversa
        self.trabalhar('pergunta', lambda: conversa.perguntar(texto), 'Aguardando o agy...')

    def pedir_proposta(self):
        if self.linha is not None or not self.proposta_botao.isEnabled():
            return
        self.falar('Você', '(pediu a proposta final)')
        self.trabalhar('proposta', self.tentativa.conversa.pedir_proposta, 'Aguardando a proposta do agy...')

    def salvar_proposta(self):
        if self.tentativa is None:
            return
        try:
            destino = self.tentativa.conversa.salvar_proposta()
        except ErroConversa as erro:
            self.mostrar_erro(str(erro))
            return
        self.mostrar_erro('')
        self.falar('Jangada', f'Proposta salva em {destino}')

    def cancelar(self):
        if self.tentativa is not None:
            self.tentativa.cancelar()
        self.geracao += 1
        self.linha = None
        self.relogio.stop()
        self.falar('Jangada', 'Conversa cancelada.')
        self.mostrar_estado()

    def encerrar(self, espera=5):
        """Encerra o motor e apaga a pasta; espera a linha de trabalho sair."""
        linha = self.linha
        self.geracao += 1
        self.linha = None
        self.relogio.stop()
        if self.tentativa is not None:
            self.tentativa.cancelar()
        if linha is not None:
            linha.join(espera)

    def closeEvent(self, evento):
        self.encerrar()
        super().closeEvent(evento)


def travar(pasta):
    """Trava da janela única; None quando outra janela do Vigia já está aberta."""
    fd = os.open(Path(pasta) / 'janela.trava', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        return None
    return fd


def trazer_existente():
    if not os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
        return
    try:
        subprocess.run(['hyprctl', 'dispatch', 'focuswindow', f'class:^({CLASSE.replace(".", chr(92) + ".")})$'],
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=2, check=False)
    except (OSError, subprocess.TimeoutExpired):
        pass


def main(argv=None):
    ap = argparse.ArgumentParser(prog='jangada-vigia janela')
    ap.add_argument('--vigia', required=True)
    ap.add_argument('--pasta', required=True)
    ap.add_argument('--retrato')
    args = ap.parse_args(argv)
    try:
        trava = travar(args.pasta)
    except OSError as erro:
        print(f'erro: não foi possível abrir a trava da janela: {erro}', file=sys.stderr)
        return 1
    if trava is None:
        print('O Vigia já está aberto.', file=sys.stderr)
        trazer_existente()
        return 0
    app = QApplication(sys.argv[:1])
    app.setApplicationName(CLASSE)
    app.setDesktopFileName(CLASSE)
    janela = Janela(args.vigia, args.pasta, args.retrato)
    for numero in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(numero, lambda *_: app.quit())
    # O Python só trata o sinal quando volta a rodar; o relógio o acorda.
    acordar = QTimer()
    acordar.timeout.connect(lambda: None)
    acordar.start(250)
    janela.show()
    try:
        return app.exec()
    finally:
        janela.encerrar()


if __name__ == '__main__':
    sys.exit(main())
