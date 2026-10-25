"""Projeto novo e abertura de tarefa na Central: pasta, Git, cadastro e erro visível."""
import os
from pathlib import Path
import re
import stat
import subprocess

from PyQt6.QtCore import QObject, QProcess, Qt, QTimer, pyqtSignal
from PyQt6.QtWidgets import (QDialog, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
                            QPushButton, QVBoxLayout)

PRIMEIRO_COMMIT = 'início do projeto'
PRAZO_GIT = 20
PRAZO_CADASTRO_MS = 30000
SEM_ERRO = 'O terminal não registrou erro. Confira se ele abriu.'

# Roda o agente num terminal e, se ele sair com erro, segura a janela aberta.
# O arquivo, o programa e os argumentos chegam como parâmetros posicionais.
ROTEIRO = """arquivo=$1; shift
"$@" 2> >(tee -a -- "$arquivo" >&2)
resultado=$?
wait
if ((resultado != 0)); then
  printf '\\nA tarefa não abriu. Enter fecha.\\n' >&2
  read -r _
fi
exit "$resultado"
"""


class ErroPreparo(Exception):
    pass


def pasta_base():
    return Path(os.environ.get('JANGADA_PROJETOS') or Path.home() / 'Projetos').expanduser()


def validar_nome(nome):
    """Mensagem de erro do nome de uma pasta nova, ou None se servir."""
    if not nome or nome.startswith('.') or '/' in nome or any(ord(c) < 32 for c in nome):
        return 'O nome da pasta não pode ser vazio, começar com ponto, ter barra nem caractere de controle.'
    return None


def _resumo(texto, limite=300):
    return ' '.join(texto.split())[:limite]


def _ambiente_git():
    """Sem variáveis GIT_* herdadas, que desviariam o comando para outro repositório."""
    ambiente = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    ambiente['GIT_TERMINAL_PROMPT'] = '0'
    return ambiente


def _git(pasta, *argumentos, ambiente=None):
    return subprocess.run(['git', '-C', str(pasta), *argumentos], capture_output=True,
                          encoding='utf-8', errors='replace', timeout=PRAZO_GIT,
                          env=ambiente or _ambiente_git(), stdin=subprocess.DEVNULL)


def e_git(pasta):
    """Diz se a pasta já está num repositório Git; um .git existente nunca é refeito."""
    if (Path(pasta) / '.git').exists():
        return True
    try:
        resultado = _git(pasta, 'rev-parse', '--is-inside-work-tree')
    except (OSError, subprocess.SubprocessError):
        return False
    return resultado.returncode == 0 and resultado.stdout.strip() == 'true'


def iniciar_repositorio(pasta):
    """git init e um primeiro commit vazio; não toca nos arquivos da pasta."""
    try:
        resultado = _git(pasta, 'init', '--quiet')
        if resultado.returncode:
            raise ErroPreparo('git init falhou: ' + _resumo(resultado.stderr))
        ambiente = _ambiente_git()
        for chave, sufixo, padrao in (('user.name', 'NAME', 'Jangada'), ('user.email', 'EMAIL', 'jangada@localhost')):
            if not _git(pasta, 'config', chave, ambiente=ambiente).stdout.strip():
                ambiente['GIT_AUTHOR_' + sufixo] = ambiente['GIT_COMMITTER_' + sufixo] = padrao
        resultado = _git(pasta, '-c', 'commit.gpgsign=false', 'commit', '--allow-empty', '--no-verify',
                         '--quiet', '-m', PRIMEIRO_COMMIT, ambiente=ambiente)
        if resultado.returncode:
            raise ErroPreparo('o repositório foi iniciado, mas o primeiro commit falhou: '
                              + _resumo(resultado.stderr))
    except FileNotFoundError:
        raise ErroPreparo('o git não está instalado') from None
    except (OSError, subprocess.SubprocessError) as erro:
        raise ErroPreparo('git falhou: ' + _resumo(str(erro))) from None


class Preparo(QObject):
    """Cria ou prepara uma pasta: Git se faltar, depois o cadastro pelo Core.

    Nunca apaga nem sobrescreve: pasta nova só nasce se o nome estiver livre, e
    pasta que já é repositório só é cadastrada. Na simulação não há pasta, Git
    nem processo.
    """
    pronto = pyqtSignal(str, str)
    falhou = pyqtSignal(str)

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.processo = None
        self.pasta = None
        self.situacao = ''
        self.expirou = False
        self.fechando = False
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.expirar)
        janela.preparos.append(self)

    def ocupado(self):
        return self.processo is not None

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
            self.falhou.emit('Outro projeto está sendo preparado.')
            return
        try:
            pasta.mkdir(parents=True)
        except FileExistsError:
            self.falhou.emit(f'{pasta} já existe. Escolha essa pasta em vez de digitar o nome.')
            return
        except OSError as erro:
            self.falhou.emit(f'Não foi possível criar {pasta}: {erro.strerror}.')
            return
        self.seguir(pasta, True)

    def preparar(self, pasta):
        pasta = Path(str(pasta).strip()).expanduser()
        if not pasta.is_dir():
            self.falhou.emit(f'{pasta} não é uma pasta existente.')
            return
        if not self.janela.real:
            self.simular(pasta)
        elif self.ocupado():
            self.falhou.emit('Outro projeto está sendo preparado.')
        else:
            self.seguir(pasta.resolve(), False)

    def simular(self, pasta):
        self.janela.projetos_novos[str(pasta)] = pasta.name
        self.pronto.emit(str(pasta), 'Simulação: nenhuma pasta, repositório ou cadastro foi criado.')

    def seguir(self, pasta, criada):
        try:
            if e_git(pasta):
                situacao = 'A pasta já era um repositório Git e não foi alterada.'
            else:
                iniciar_repositorio(pasta)
                situacao = 'Git iniciado com um primeiro commit vazio.'
        except ErroPreparo as erro:
            sobra = 'A pasta foi criada, mas ' if criada else 'Nada foi cadastrado: '
            self.falhou.emit(f'{sobra}{erro}.')
            return
        self.pasta, self.situacao, self.expirou = pasta, situacao, False
        processo = QProcess(self)
        self.janela.preparar(processo, ['--projeto', str(pasta), 'cadastrar'], 'jangada-projeto')
        processo.finished.connect(self.cadastro_fim)
        processo.errorOccurred.connect(self.cadastro_erro)
        self.processo = processo
        processo.start()
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
            self.falhou.emit(f'{self.situacao} Não foi possível executar jangada-projeto; '
                             'cadastre a pasta pela aba Projetos e fila.')

    def cadastro_fim(self, codigo, tipo):
        processo = self.liberar()
        if processo is None or self.fechando:
            return
        detalhe = _resumo(bytes(processo.readAllStandardError()).decode('utf-8', 'replace'), 500)
        if self.expirou:
            self.falhou.emit(f'{self.situacao} O cadastro passou do prazo. Use Preparar como projeto de novo.')
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.falhou.emit(f'{self.situacao} O Core recusou o cadastro. {detalhe}'.strip())
        else:
            self.janela.projetos_novos[str(self.pasta)] = self.pasta.name
            self.janela.operacional.atualizar()
            self.pronto.emit(str(self.pasta), self.situacao + ' Projeto cadastrado.')

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
        self.resize(600, 260)
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
            f'Um nome cria a pasta em {self.base}, inicia o Git e cadastra o projeto. '
            'Uma pasta existente só é cadastrada; o Git é iniciado apenas se ela ainda não for um '
            'repositório, e nenhum arquivo seu é alterado.' if janela.real else
            'Simulação: nenhuma pasta, repositório ou cadastro é criado.')
        orientacao.setTextFormat(Qt.TextFormat.PlainText)
        orientacao.setWordWrap(True)
        layout.addWidget(orientacao)
        self.resultado = QLabel()
        self.resultado.setTextFormat(Qt.TextFormat.PlainText)
        self.resultado.setWordWrap(True)
        layout.addWidget(self.resultado)
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

    def concluido(self, caminho, situacao):
        self.caminho = caminho
        self.resultado.setText(f'Projeto pronto em {caminho}. {situacao}')
        self.coordenador.setEnabled(self.janela.coordenadores.novo.isEnabled())
        self.coordenador.show()

    def recusado(self, mensagem):
        self.resultado.setText(mensagem)
        self.criar.setEnabled(True)

    def reeditar(self, *_):
        self.caminho = None
        self.resultado.clear()
        self.coordenador.hide()
        self.criar.setEnabled(not self.preparo.ocupado())

    def abrir_coordenador(self):
        if self.caminho:
            self.hide()
            self.janela.coordenadores.novo_coordenador_em(self.caminho)


def pasta_de_erros():
    """Pasta privada dos erros de abertura; recusa link, dono diferente e permissão aberta."""
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime or not os.path.isabs(runtime):
        raise ValueError('XDG_RUNTIME_DIR deve indicar a pasta da sessão gráfica.')
    pasta = Path(runtime) / 'jangada'
    pasta.mkdir(mode=0o700, exist_ok=True)
    dados = pasta.lstat()
    if not stat.S_ISDIR(dados.st_mode) or dados.st_uid != os.getuid() or dados.st_mode & 0o077:
        raise ValueError('A pasta de erros deve pertencer ao usuário e ter permissão 0700.')
    return pasta


def criar_arquivo_de_erros(nome):
    """Arquivo vazio e novo para a saída de erro de uma abertura; nunca reaproveita um existente."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', nome):
        raise ValueError('Nome de tarefa inválido.')
    arquivo = pasta_de_erros() / (nome + '.erro')
    os.close(os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
    return arquivo


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
