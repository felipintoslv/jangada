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


class ConsultaGit(QObject):
    """Roda `janela.e_git` fora da linha da interface e entrega o resultado por sinal."""
    fim = pyqtSignal(int, bool)

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.pendentes = {}
        self.ultimo = 0
        self.fechando = False
        self.fim.connect(self.entregar)

    def consultar(self, pasta, retorno):
        self.ultimo += 1
        self.pendentes[self.ultimo] = retorno
        threading.Thread(target=self.rodar, args=(self.ultimo, pasta), daemon=True).start()

    def rodar(self, numero, pasta):
        try:
            resultado = bool(self.janela.e_git(pasta))
        except Exception:
            resultado = False
        try:
            self.fim.emit(numero, resultado)
        except RuntimeError:
            pass

    def entregar(self, numero, resultado):
        retorno = self.pendentes.pop(numero, None)
        if retorno is not None and not self.fechando:
            retorno(resultado)

    def fechar(self):
        self.fechando = True
        self.pendentes.clear()


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


class Preparo(QObject):
    """Do nome ou da pasta ao cadastro, sem tocar no Git.

    A pasta nova é criada por `janela.criar_pasta_vazia`. Pasta que já é
    repositório com commit é cadastrada pelo Core; as demais pedem os comandos
    do terminal (`sem_git`). Na simulação não há pasta, git nem processo.
    """
    pronto = pyqtSignal(str, str)
    falhou = pyqtSignal(str)
    sem_git = pyqtSignal(str)

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.processo = None
        self.pasta = None
        self.conferindo = False
        self.expirou = False
        self.fechando = False
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.expirar)
        janela.preparos.append(self)

    def ocupado(self):
        return self.conferindo or self.processo is not None

    def criar(self, nome, base):
        nome = nome.strip()
        erro = validar_nome(nome)
        if erro:
            self.falhou.emit(erro)
            return
        pasta = Path(base) / nome
        if not self.janela.real:
            self.simular(pasta)
            return
        if self.ocupado():
            self.falhou.emit('Outro projeto está sendo conferido ou cadastrado.')
            return
        erro = self.janela.criar_pasta_vazia(pasta)
        if erro:
            self.falhou.emit(erro)
        else:
            self.sem_git.emit(str(pasta))

    def preparar(self, pasta):
        pasta = Path(str(pasta).strip()).expanduser()
        if not pasta.is_dir():
            self.falhou.emit(f'{pasta} não é uma pasta existente.')
        elif not self.janela.real:
            self.simular(pasta)
        elif self.ocupado():
            self.falhou.emit('Outro projeto está sendo conferido ou cadastrado.')
        else:
            pasta = pasta.resolve()
            self.conferindo = True
            self.janela.git.consultar(pasta, lambda ok: self.conferido(pasta, ok))

    def conferido(self, pasta, e_git):
        self.conferindo = False
        if self.fechando:
            return
        if e_git:
            self.cadastrar(pasta)
        else:
            self.sem_git.emit(str(pasta))

    def simular(self, pasta):
        self.janela.projetos_novos[str(pasta)] = pasta.name
        self.pronto.emit(str(pasta), 'Simulação: nenhuma pasta, git ou cadastro foi criado.')

    def cadastrar(self, pasta):
        self.pasta, self.expirou = pasta, False
        processo = self.janela.iniciar_cadastro(pasta)
        processo.finished.connect(self.cadastro_fim)
        processo.errorOccurred.connect(self.cadastro_erro)
        self.processo = processo
        self.prazo.start(PRAZO_CADASTRO_MS)

    def liberar(self):
        self.prazo.stop()
        processo, self.processo = self.processo, None
        if processo is not None:
            processo.deleteLater()
        return processo

    def cadastro_erro(self, erro):
        if erro != QProcess.ProcessError.FailedToStart or self.processo is None:
            return
        self.liberar()
        if not self.fechando:
            self.falhou.emit('Não foi possível executar jangada-projeto; '
                             'cadastre a pasta pela aba Projetos e fila.')

    def cadastro_fim(self, codigo, tipo):
        processo = self.liberar()
        if processo is None or self.fechando:
            return
        detalhe = _resumo(bytes(processo.readAllStandardError()).decode('utf-8', 'replace'), 500)
        if self.expirou:
            self.falhou.emit('O cadastro passou do prazo. Confira a pasta e tente de novo.')
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.falhou.emit(f'O Core recusou o cadastro. {detalhe}'.strip())
        else:
            self.janela.projetos_novos[str(self.pasta)] = self.pasta.name
            self.janela.operacional.atualizar()
            self.pronto.emit(str(self.pasta), 'Projeto cadastrado.')

    def expirar(self):
        self.expirou = True
        if self.processo is not None:
            self.processo.kill()

    def fechar(self):
        self.fechando = True
        self.prazo.stop()
        if self.processo is not None:
            self.processo.blockSignals(True)
            self.processo.kill()
            self.processo.waitForFinished(1000)


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
        escolher = QPushButton('Escolher pasta existente')
        escolher.clicked.connect(self.escolher_pasta)
        linha = QHBoxLayout()
        linha.addWidget(self.nome)
        linha.addWidget(escolher)
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
        fechar = QPushButton('Fechar')
        fechar.clicked.connect(self.hide)
        self.coordenador = QPushButton('Abrir coordenador neste projeto')
        self.coordenador.clicked.connect(self.abrir_coordenador)
        self.coordenador.hide()
        self.criar = QPushButton('Criar projeto')
        self.criar.setDefault(True)
        self.criar.clicked.connect(self.confirmar)
        botoes.addWidget(fechar)
        botoes.addStretch()
        botoes.addWidget(self.coordenador)
        botoes.addWidget(self.criar)
        layout.addLayout(botoes)
        self.preparo = Preparo(janela)
        self.preparo.pronto.connect(self.concluido)
        self.preparo.falhou.connect(self.recusado)
        self.preparo.sem_git.connect(self.pedir_git)
        self.aviso.conferir.connect(self.conferir)
        self.nome.textChanged.connect(self.reeditar)
        self.nome.returnPressed.connect(self.confirmar)

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Escolher projeto', str(self.base if self.base.is_dir() else Path.home()))
        if pasta:
            self.nome.setText(pasta)

    def confirmar(self):
        texto = self.nome.text().strip()
        if not self.criar.isEnabled():
            return
        self.resultado.clear()
        self.criar.setEnabled(False)
        if texto.startswith('~') or '/' in texto:
            self.preparo.preparar(texto)
        else:
            self.preparo.criar(texto, self.base)

    def conferir(self, pasta):
        self.resultado.clear()
        self.preparo.preparar(pasta)

    def pedir_git(self, pasta):
        self.aviso.mostrar(pasta)
        self.criar.setEnabled(True)

    def concluido(self, caminho, situacao):
        self.caminho = caminho
        self.aviso.hide()
        self.resultado.setText(f'Projeto pronto em {caminho}. {situacao}')
        self.coordenador.setEnabled(self.janela.coordenadores.novo.isEnabled())
        self.coordenador.show()

    def recusado(self, mensagem):
        self.resultado.setText(mensagem)
        self.criar.setEnabled(True)

    def reeditar(self, *_):
        self.caminho = None
        self.resultado.clear()
        self.aviso.hide()
        self.coordenador.hide()
        self.criar.setEnabled(not self.preparo.ocupado())

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
