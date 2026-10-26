"""Projeto novo na Central: nome, conferência do Git e cadastro pelo Core.

Este módulo não grava nada e não inicia o Git: lê o repositório, monta os
comandos que o usuário roda no terminal e pede ao Core o cadastro. A pasta nova
e os arquivos de erro nascem em `janela.py`.
"""
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import threading

from PyQt6.QtCore import QObject, QProcess, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QApplication, QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel,
                            QLineEdit, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget)

MENSAGEM_COMMIT = 'Inicia repositório'
PRAZO_CONSULTA = 5
PRAZO_CADASTRO_MS = 30000
SEM_ERRO = 'O terminal não registrou erro. Confira se ele abriu.'


def pasta_base():
    return Path(os.environ.get('JANGADA_PROJETOS') or Path.home() / 'Projetos').expanduser()


def validar_nome(nome):
    """Mensagem de erro do nome de uma pasta nova, ou None se servir."""
    if not nome or nome.startswith('.') or '/' in nome or any(ord(c) < 32 for c in nome):
        return 'O nome da pasta não pode ser vazio, começar com ponto, ter barra nem caractere de controle.'
    return None


def _resumo(texto, limite=300):
    return ' '.join(texto.split())[:limite]


def _git(pasta, *argumentos):
    """Só consulta: o chamador passa apenas subcomandos de leitura."""
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    ambiente['GIT_TERMINAL_PROMPT'] = '0'
    return subprocess.run(['git', '-C', str(pasta), *argumentos], capture_output=True,
                          encoding='utf-8', errors='replace', timeout=PRAZO_CONSULTA,
                          env=ambiente, stdin=subprocess.DEVNULL)


def e_git(pasta):
    """Pasta que é a raiz de um repositório com ao menos um commit, o que o worktree da tarefa exige."""
    try:
        raiz = _git(pasta, 'rev-parse', '--show-toplevel')
        texto = raiz.stdout.strip()
        if raiz.returncode or not texto or Path(texto).resolve() != Path(pasta).resolve():
            return False
        return _git(pasta, 'rev-parse', '--verify', '--quiet', 'HEAD').returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def texto_dos_comandos(pasta):
    """Os mesmos comandos como texto de shell para copiar; o caminho vai citado, a mensagem é fixa."""
    alvo = shlex.quote(str(pasta))
    return f'git -C {alvo} init\ngit -C {alvo} commit --allow-empty -m "{MENSAGEM_COMMIT}"'


class AvisoGit(QWidget):
    """Aviso de pasta sem repositório: os comandos para o terminal, copiar e conferir."""
    conferir = pyqtSignal(str)

    def __init__(self, pai=None):
        super().__init__(pai)
        self.pasta = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.texto = QLabel()
        self.texto.setTextFormat(Qt.TextFormat.PlainText)
        self.texto.setWordWrap(True)
        layout.addWidget(self.texto)
        self.comandos = QPlainTextEdit()
        self.comandos.setReadOnly(True)
        self.comandos.setAccessibleName('Comandos para rodar no terminal')
        self.comandos.setFixedHeight(self.comandos.fontMetrics().lineSpacing() * 5 + 24)
        layout.addWidget(self.comandos)
        botoes = QHBoxLayout()
        self.copiar = QPushButton('Copiar comandos')
        self.copiar.clicked.connect(self.copiar_comandos)
        self.rodei = QPushButton('Já rodei, conferir')
        self.rodei.clicked.connect(lambda: self.conferir.emit(self.pasta))
        botoes.addWidget(self.copiar)
        botoes.addWidget(self.rodei)
        botoes.addStretch()
        layout.addLayout(botoes)
        self.hide()

    def mostrar(self, pasta):
        repetido = self.pasta == str(pasta) and not self.isHidden()
        self.pasta = str(pasta)
        aviso = 'Esta pasta ainda não é um repositório git. Rode no terminal:'
        if repetido:
            aviso = 'Ainda não é um repositório git com ao menos um commit. ' + aviso
        self.texto.setText(aviso)
        self.comandos.setPlainText(texto_dos_comandos(pasta))
        self.show()

    def copiar_comandos(self):
        if self.pasta:
            QApplication.clipboard().setText(texto_dos_comandos(self.pasta))


class Conferencia(QObject):
    """Porta única de um diálogo para conferir o git de uma pasta e, se pedido, cadastrá-la pelo Core.

    Cada chamada abre uma geração e trava o diálogo. Só o resultado da geração
    atual, com o diálogo visível, destrava e chega a `ao_terminar(pasta,
    situacao, mensagem)`, com a pasta guardada na chamada; o resto é descartado
    sem tocar no diálogo. Situações: `git`, `sem_git`, `cadastrado` e `falhou`.
    Na simulação não há git nem processo: toda pasta conta como repositório.
    """
    fim = pyqtSignal(int, bool)

    def __init__(self, dialogo, janela, travar):
        super().__init__(dialogo)
        self.dialogo = dialogo
        self.janela = janela
        self.travar = travar
        self.geracao = 0
        self.ativa = False
        self.fechando = False
        self.pasta = None
        self.ao_terminar = None
        self.cadastrar = False
        self.processos = {}
        self.fim.connect(self.conferido)
        janela.conferencias.append(self)

    def ocupada(self):
        return self.ativa

    def conferir(self, pasta, ao_terminar, cadastrar=False):
        """Devolve False, sem fazer nada, se já há uma conferência em curso ou o diálogo está escondido."""
        if self.ativa or self.fechando or self.dialogo.isHidden():
            return False
        self.geracao += 1
        self.ativa, self.ao_terminar, self.cadastrar = True, ao_terminar, cadastrar
        self.pasta = Path(pasta).expanduser()
        self.travar(True)
        if not self.janela.real:
            self.conferido(self.geracao, True)
        elif not self.pasta.is_dir():
            self.terminar('falhou', f'{self.pasta} não é uma pasta existente.')
        else:
            self.pasta = self.pasta.resolve()
            threading.Thread(target=self.rodar, args=(self.geracao, self.pasta), daemon=True).start()
        return True

    def rodar(self, geracao, pasta):
        try:
            resultado = bool(self.janela.e_git(pasta))
        except Exception:
            resultado = False
        try:
            self.fim.emit(geracao, resultado)
        except RuntimeError:
            pass

    def atual(self, geracao):
        return geracao == self.geracao and self.ativa and not self.fechando and not self.dialogo.isHidden()

    def conferido(self, geracao, e_git):
        if not self.atual(geracao):
            return
        if not e_git:
            self.terminar('sem_git', '')
        elif not self.cadastrar:
            self.terminar('git', '')
        elif not self.janela.real:
            self.janela.projetos_novos[str(self.pasta)] = self.pasta.name
            self.terminar('cadastrado', 'Simulação: nenhuma pasta, git ou cadastro foi criado.')
        else:
            self.iniciar_cadastro(geracao, self.pasta)

    def terminar(self, situacao, mensagem):
        self.ativa = False
        self.travar(False)
        self.ao_terminar(self.pasta, situacao, mensagem)

    def cancelar(self):
        """Invalida a conferência em curso e destrava; um cadastro já pedido ao Core segue até o fim."""
        if not self.ativa:
            return False
        self.geracao += 1
        self.ativa = False
        self.travar(False)
        return True

    def iniciar_cadastro(self, geracao, pasta):
        processo = self.janela.iniciar_cadastro(pasta)
        prazo = QTimer(self)
        prazo.setSingleShot(True)
        registro = {'geracao': geracao, 'pasta': pasta, 'prazo': prazo, 'expirou': False}
        prazo.timeout.connect(lambda: self.expirar(processo, registro))
        processo.finished.connect(lambda codigo, tipo: self.cadastro_fim(processo, registro, codigo, tipo))
        processo.errorOccurred.connect(lambda erro: self.cadastro_erro(processo, registro, erro))
        self.processos[processo] = registro
        prazo.start(PRAZO_CADASTRO_MS)
        # A falha de início pode ter saído dentro de start(), antes das ligações acima.
        if processo.state() == QProcess.ProcessState.NotRunning:
            self.cadastro_erro(processo, registro, QProcess.ProcessError.FailedToStart)

    def liberar(self, processo, registro):
        registro['prazo'].stop()
        registro['prazo'].deleteLater()
        if self.processos.pop(processo, None) is None:
            return False
        processo.deleteLater()
        return True

    def expirar(self, processo, registro):
        registro['expirou'] = True
        processo.kill()

    def cadastro_erro(self, processo, registro, erro):
        if erro != QProcess.ProcessError.FailedToStart or processo not in self.processos:
            return
        self.liberar(processo, registro)
        if self.atual(registro['geracao']):
            self.terminar('falhou', 'Não foi possível executar jangada-projeto; '
                                    'cadastre a pasta pela aba Projetos e fila.')

    def cadastro_fim(self, processo, registro, codigo, tipo):
        if not self.liberar(processo, registro) or self.fechando:
            return
        detalhe = _resumo(bytes(processo.readAllStandardError()).decode('utf-8', 'replace'), 500)
        pasta = registro['pasta']
        if registro['expirou']:
            situacao = 'falhou', 'O cadastro passou do prazo. Confira a pasta e tente de novo.'
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            situacao = 'falhou', f'O Core recusou o cadastro. {detalhe}'.strip()
        else:
            # O projeto vale para a Central mesmo que o diálogo tenha fechado durante o cadastro.
            self.janela.projetos_novos[str(pasta)] = pasta.name
            self.janela.operacional.atualizar()
            situacao = 'cadastrado', 'Projeto cadastrado.'
        if self.atual(registro['geracao']):
            self.terminar(*situacao)

    def fechar(self):
        self.fechando = True
        self.geracao += 1
        self.ativa = False
        for processo, registro in list(self.processos.items()):
            registro['prazo'].stop()
            processo.blockSignals(True)
            processo.kill()
            processo.waitForFinished(1000)
        self.processos.clear()


class NovoProjeto(QDialog):
    """Primeiro passo do trabalho: o projeto, antes do coordenador e da tarefa."""

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.caminho = None
        self.base = pasta_base()
        self.setWindowTitle('Novo projeto' + ('' if janela.real else ' · Simulação'))
        self.resize(640, 380)
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.nome = QLineEdit()
        self.nome.setAccessibleName('Nome do projeto novo ou pasta existente')
        self.nome.setPlaceholderText('Nome da pasta nova')
        self.escolher = QPushButton('Escolher pasta existente')
        self.escolher.clicked.connect(self.escolher_pasta)
        linha = QHBoxLayout()
        linha.addWidget(self.nome)
        linha.addWidget(self.escolher)
        formulario.addRow('Projeto', linha)
        layout.addLayout(formulario)
        orientacao = QLabel(
            f'Um nome cria a pasta vazia em {self.base}. Pasta que já é repositório git com commit é '
            'cadastrada na hora; as outras mostram os comandos para você rodar no terminal. '
            'A Central não inicia o git nem altera seus arquivos.' if janela.real else
            'Simulação: nenhuma pasta, git ou cadastro é criado.')
        orientacao.setTextFormat(Qt.TextFormat.PlainText)
        orientacao.setWordWrap(True)
        layout.addWidget(orientacao)
        self.resultado = QLabel()
        self.resultado.setTextFormat(Qt.TextFormat.PlainText)
        self.resultado.setWordWrap(True)
        layout.addWidget(self.resultado)
        self.aviso = AvisoGit()
        layout.addWidget(self.aviso)
        layout.addStretch()
        botoes = QHBoxLayout()
        self.fechar = QPushButton('Fechar')
        self.fechar.clicked.connect(self.hide)
        self.coordenador = QPushButton('Abrir coordenador neste projeto')
        self.coordenador.clicked.connect(self.abrir_coordenador)
        self.coordenador.hide()
        self.criar = QPushButton('Criar projeto')
        self.criar.setDefault(True)
        self.criar.clicked.connect(self.confirmar)
        # Travar o grupo guarda o estado próprio de cada botão de ação, que volta ao destravar.
        self.acoes = QWidget()
        acoes = QHBoxLayout(self.acoes)
        acoes.setContentsMargins(0, 0, 0, 0)
        acoes.addWidget(self.coordenador)
        acoes.addWidget(self.criar)
        botoes.addWidget(self.fechar)
        botoes.addStretch()
        botoes.addWidget(self.acoes)
        layout.addLayout(botoes)
        self.conferencia = Conferencia(self, janela, self.travar)
        self.aviso.conferir.connect(self.ja_rodei)
        self.nome.textChanged.connect(self.reeditar)
        self.nome.returnPressed.connect(self.confirmar)

    @property
    def conferindo(self):
        return self.conferencia.ocupada()

    def travar(self, travado):
        for controle in (self.nome, self.escolher, self.aviso, self.acoes):
            controle.setEnabled(not travado)

    def conferir(self, pasta, ao_terminar, cadastrar=False):
        """Porta única de toda conferência do git neste diálogo."""
        self.resultado.setText('Conferindo o repositório git da pasta...')

        def fim(pasta, situacao, mensagem):
            self.resultado.clear()
            ao_terminar(pasta, situacao, mensagem)
        self.conferencia.conferir(pasta, fim, cadastrar)

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Escolher projeto', str(self.base if self.base.is_dir() else Path.home()))
        if pasta:
            self.conferir(pasta, self.escolhida)

    def escolhida(self, pasta, situacao, mensagem):
        self.nome.setText(str(pasta))
        if situacao == 'sem_git':
            self.aviso.mostrar(pasta)
        elif situacao == 'falhou':
            self.resultado.setText(mensagem)

    def confirmar(self):
        if self.conferindo or not self.criar.isEnabled():
            return
        texto = self.nome.text().strip()
        self.resultado.clear()
        if not (texto.startswith('~') or '/' in texto):
            erro = validar_nome(texto)
            pasta = self.base / texto
            if not erro and self.janela.real:
                erro = self.janela.criar_pasta_vazia(pasta)
            if erro:
                self.resultado.setText(erro)
                return
            texto = str(pasta)
        self.conferir(texto, self.conferido, cadastrar=True)

    def ja_rodei(self, pasta):
        self.conferir(pasta, self.conferido, cadastrar=True)

    def conferido(self, pasta, situacao, mensagem):
        if situacao == 'cadastrado':
            self.caminho = str(pasta)
            self.aviso.hide()
            self.resultado.setText(f'Projeto pronto em {pasta}. {mensagem}')
            self.coordenador.setEnabled(self.janela.coordenadores.novo.isEnabled())
            self.coordenador.show()
            self.criar.setEnabled(False)
        elif situacao == 'sem_git':
            self.aviso.mostrar(pasta)
        else:
            self.resultado.setText(mensagem)

    def reeditar(self, *_):
        self.caminho = None
        self.resultado.clear()
        self.aviso.hide()
        self.coordenador.hide()
        self.criar.setEnabled(True)

    def hideEvent(self, evento):
        if self.conferencia.cancelar():
            self.resultado.clear()
        super().hideEvent(evento)

    def abrir_coordenador(self):
        if self.caminho:
            self.hide()
            self.janela.coordenadores.novo_coordenador_em(self.caminho)


def ultimas_linhas(arquivo, linhas=8, limite=2000):
    """Fim do arquivo de erros como texto simples: sem controles nem sequências de cor."""
    try:
        fd = os.open(arquivo, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as aberto:
            dados = os.fstat(aberto.fileno())
            if not stat.S_ISREG(dados.st_mode):
                return ''
            aberto.seek(max(0, dados.st_size - limite * 4))
            bruto = aberto.read(limite * 4)
    except OSError:
        return ''
    texto = re.sub(r'\x1b\[[0-9;?]*[ -/]*[@-~]', '', bruto.decode('utf-8', 'replace'))
    texto = ''.join(c if c == '\n' or c.isprintable() else ' ' for c in texto.replace('\r', '\n'))
    return '\n'.join([l.rstrip() for l in texto.splitlines() if l.strip()][-linhas:])[-limite:]
