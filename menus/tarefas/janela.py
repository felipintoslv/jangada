"""Janela da central de tarefas e acompanhamento das sessões."""
from dataclasses import replace
from datetime import datetime
import hashlib
import html
import json
import os
import re
import stat
import sys
from pathlib import Path
import time
import uuid

from PyQt6.QtCore import QFileSystemWatcher, QProcess, QProcessEnvironment, QTimer, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QComboBox, QDialog, QFileDialog, QFormLayout,
                            QHBoxLayout, QHeaderView, QInputDialog, QLabel, QLineEdit, QMainWindow, QMessageBox,
                            QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTabWidget,
                            QSizePolicy, QStackedWidget, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from dados import (LIMITE, NOME, ORDEM, ROTULOS, Sessao,
                   comando_disponivel, estado_exibido, idade, ler_lista, ler_observacao, pasta_sessoes,
                   resolver_comando, sem_coordenadores, simuladas)

sys.dont_write_bytecode = True
# Com default/tarefas acessada por link, __file__ aponta para a pasta física;
# visual e logo ficam nos caminhos legados sob JANGADA_PATH.
RAIZ = Path(os.environ.get('JANGADA_PATH') or Path(__file__).absolute().parents[2])
sys.path.insert(0, str(RAIZ / 'default'))
from visual.fichas import carregar as carregar_fichas, ESTADOS, ICONES
from operacional import Operacional
from indicadores import Indicadores, SEM_DADO, inteiro, tempo, texto, tokens_da_tarefa
from rodadas import Rodadas
from coordenadores import FAIXA, Coordenadores
from cotas import SIMULACAO, ConsultaCotas, FaixaCotas
from aparencia import (BotaoComMotivo, Cabecalho, Cartao, FaixaResumo, InspetorRolavel, LinhaTempo,
                       cores_interacao, definir_tipo, folha_de_estilo, marca, misturar, separador, texto_estado)
from projeto import (SEM_ERRO, AvisoGit, Conferencia, NovoProjeto, e_git, pasta_base, ultimas_linhas,
                     validar_nome)

IDADE_ERRO = 60

# Roda o agente num terminal e, se ele sair com erro, segura a janela aberta.
# O arquivo de erros, o programa e os argumentos chegam como parâmetros posicionais.
ROTEIRO = """arquivo=$1; shift
"$@" 2> >(umask 077; tee -a -- "$arquivo" >&2)
resultado=$?
wait
if ((resultado != 0)); then
  printf '\\nA tarefa não abriu. Enter fecha.\\n' >&2
  read -r _
fi
exit "$resultado"
"""


def _pasta_privada(pasta):
    pasta.mkdir(mode=0o700, exist_ok=True)
    dados = pasta.lstat()
    if not stat.S_ISDIR(dados.st_mode) or dados.st_uid != os.getuid() or dados.st_mode & 0o077:
        raise ValueError('A pasta de erros deve pertencer ao usuário e ter permissão 0700.')
    return pasta


def pasta_de_erros():
    """`$XDG_RUNTIME_DIR/jangada-tarefas/aberturas`, fora do runtime visível ao agente isolado.

    Recusa link, dono diferente e permissão aberta, na pasta e na subpasta.
    """
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime or not os.path.isabs(runtime):
        raise ValueError('XDG_RUNTIME_DIR deve indicar a pasta da sessão gráfica.')
    return _pasta_privada(_pasta_privada(Path(runtime) / 'jangada-tarefas') / 'aberturas')


def varrer_erros(pasta, idade=IDADE_ERRO):
    """Remove arquivos de erro velhos, inclusive os recriados por um terminal que subiu depois da limpeza."""
    for velho in pasta.glob('*.erro'):
        try:
            if time.time() - velho.lstat().st_mtime > idade:
                velho.unlink()
        except OSError:
            pass


def criar_arquivo_de_erros(nome):
    """Arquivo vazio e novo para a saída de erro de uma abertura; nunca reaproveita um existente."""
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,64}', nome):
        raise ValueError('Nome de tarefa inválido.')
    pasta = pasta_de_erros()
    varrer_erros(pasta)
    arquivo = pasta / (nome + '.erro')
    os.close(os.open(arquivo, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600))
    return arquivo

# Só para a janela simulada e para quando a consulta falha: o catálogo vem do
# jangada-agente --capacidades-json, que também é quem valida a escolha.
AGENTES = ("claude", "codex")

GRUPOS = {'aguardando': 'Precisa da sua resposta', 'interrompido': 'Interrompidas',
          'trabalhando': 'Em execução', 'concluido': 'Pronto para conferir'}
PAPEL_GRUPO = Qt.ItemDataRole.UserRole + 1
# Estado da sessão e a ficha de estado que dá cor e símbolo; fim de turno não é tarefa concluída.
FICHA_SESSAO = {'aguardando': 'Bloqueada', 'trabalhando': 'Executando',
                'concluido': 'Em revisão', 'interrompido': 'Falhou'}

class NovaTarefa(QDialog):

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.setWindowTitle('Nova tarefa' + ('' if janela.real else ' · Simulação'))
        self.resize(600, 440)
        externo = QVBoxLayout(self)
        # Travar o corpo e o grupo de ações guarda o estado próprio de cada
        # controle (Nova pasta na simulação, Iniciar sem agente), que volta ao destravar.
        self.corpo = QWidget()
        layout = QVBoxLayout(self.corpo)
        layout.setContentsMargins(0, 0, 0, 0)
        externo.addWidget(self.corpo)
        formulario = QFormLayout()
        self.projeto = QLineEdit()
        self.projeto.setPlaceholderText('Pasta do projeto')
        s = janela.sessoes.get(janela.selecionada())
        if s and janela.real:
            self.projeto.setText(s.raiz or s.dir)
        elif not janela.real:
            self.projeto.setText(str(Path.cwd()))
        escolher = self.escolher = QPushButton('Escolher pasta')
        escolher.clicked.connect(self.escolher_pasta)
        linha = QHBoxLayout()
        linha.addWidget(self.projeto)
        linha.addWidget(escolher)
        self.base = pasta_base()
        self.abertura = None
        nova = self.nova = QPushButton('Nova pasta')
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
        externo.addWidget(self.erro)
        self.aviso_git = AvisoGit()
        externo.addWidget(self.aviso_git)
        self.conferencia = Conferencia(self, janela, self.travar)
        self.aviso_git.conferir.connect(self.ja_rodei)
        botoes = QHBoxLayout()
        self.fechar = QPushButton('Fechar')
        self.fechar.clicked.connect(self.hide)
        self.enviar = QPushButton('Iniciar tarefa' if janela.real else 'Criar tarefa simulada')
        self.enviar.clicked.connect(self.criar)
        self.acoes = QWidget()
        acoes = QHBoxLayout(self.acoes)
        acoes.setContentsMargins(0, 0, 0, 0)
        acoes.addWidget(self.enviar)
        self.projeto.textChanged.connect(self.reeditar)
        self.pedido.textChanged.connect(self.reeditar)
        self.modo.currentTextChanged.connect(self.reeditar)
        for controle in (self.agente, self.revisor, self.seguranca, self.delegacao):
            controle.currentTextChanged.connect(self.personalizar)
        botoes.addWidget(self.fechar)
        botoes.addStretch()
        botoes.addWidget(self.acoes)
        externo.addLayout(botoes)

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

    @property
    def conferindo(self):
        return self.conferencia.ocupada()

    def travar(self, travado):
        """Congela pasta, pedido, opções e ações enquanto o git responde; só Fechar fica livre."""
        for controle in (self.corpo, self.aviso_git, self.acoes):
            controle.setEnabled(not travado)

    def conferir(self, pasta, ao_terminar, cadastrar=False):
        """Porta única de toda conferência do git neste formulário."""
        self.erro.setText('Conferindo o repositório git da pasta...')

        def fim(pasta, situacao, mensagem):
            self.erro.clear()
            if situacao == 'falhou':
                self.erro.setText(mensagem)
            else:
                ao_terminar(pasta, situacao, mensagem)
        self.conferencia.conferir(pasta, fim, cadastrar)

    def escolher_pasta(self):
        pasta = QFileDialog.getExistingDirectory(self, 'Escolher projeto', self.projeto.text())
        if pasta:
            self.conferir(pasta, self.pasta_conferida)

    def nova_pasta(self):
        nome, aceito = QInputDialog.getText(self, 'Nova pasta', f'Nome do projeto, criado em {self.base}')
        if aceito:
            self.criar_pasta(nome)

    def criar_pasta(self, nome):
        if self.conferindo:
            return
        nome = nome.strip()
        erro = validar_nome(nome)
        pasta = self.base / nome
        if not erro and self.janela.real:
            erro = self.janela.criar_pasta_vazia(pasta)
        if erro:
            self.erro.setText(erro)
            return
        self.conferir(pasta, self.pasta_conferida)

    def ja_rodei(self, pasta):
        self.conferir(pasta, self.pasta_conferida, cadastrar=True)

    def pasta_conferida(self, pasta, situacao, mensagem):
        self.projeto.setText(str(pasta))
        if situacao == 'sem_git':
            self.pedir_git(pasta)
        elif situacao == 'cadastrado':
            self.aviso_git.hide()
            self.enviar.setEnabled(True)
            self.erro.setText(f'Projeto pronto em {pasta}. {mensagem}')

    def pedir_git(self, pasta):
        self.aviso_git.mostrar(pasta)
        self.erro.setText('A tarefa não foi aberta: a pasta ainda não é um projeto git.')

    def criar(self):
        if self.conferindo:
            return
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
        self.conferir(Path(pasta).expanduser().resolve(),
                      lambda projeto, situacao, _: self.conferido(projeto, pedido, situacao))

    def conferido(self, projeto, pedido, situacao):
        if situacao == 'git':
            self.abrir(projeto, pedido)
        else:
            self.projeto.setText(str(projeto))
            self.pedir_git(projeto)

    def hideEvent(self, evento):
        if self.conferencia.cancelar():
            self.erro.clear()
        super().hideEvent(evento)

    def abrir(self, projeto, pedido):
        agente = self.agente.currentText()
        perfil = self.agente.currentData()
        if self.modo.currentText() == 'Recomendado':
            if not self.recomendado:
                self.erro.setText('Nenhum executor recomendado disponível. Confira o catálogo ou escolha nas opções avançadas.')
                self.enviar.setEnabled(True)
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
            argumentos = ['--projeto', str(projeto), '--nome', nome,
                          '--perfil' if perfil else '--agente', perfil or agente, '--prompt', pedido]
            personalizado = self.modo.currentText() == 'Personalizado'
            if personalizado and self.revisor.currentIndex():
                argumentos += ['--revisor', self.revisor.currentText()]
            if personalizado and self.seguranca.currentIndex():
                argumentos += ['--sem-isolar']
            if personalizado and self.delegacao.currentIndex():
                argumentos += ['--delegacao', self.delegacao.currentText()]
            falha = self.janela.abrir_tarefa(nome, argumentos)
            if falha:
                self.erro.setText(falha)
                self.enviar.setEnabled(True)
                return
            self.abertura = nome
            self.erro.setText(f'Abertura solicitada. Se a tarefa não aparecer na lista em '
                              f'{self.janela.prazo_tarefa_ms // 1000} segundos, o motivo aparece aqui. Seu pedido foi preservado.')
        self.enviar.setEnabled(False)

    def personalizar(self, *_):
        self.modo.setCurrentText('Personalizado')
        self.reeditar()

    def reeditar(self, *_):
        self.enviar.setEnabled(True)
        self.erro.clear()
        self.aviso_git.hide()

    def mostrar_falha(self, nome, texto):
        if nome != self.abertura:
            return
        self.enviar.setEnabled(True)
        self.erro.setText(texto)
        self.show()
        self.raise_()


class Janela(QMainWindow):

    def __init__(self, real=False, jangada=None, estado=None):
        super().__init__()
        self.real = real
        self.eventos = {}
        self.observadas = {}
        self.jangada = Path(jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
        self.estado_dir = pasta_sessoes(estado)
        self.sessoes = {}
        self.estrutura = None
        self.itens = {}
        self.finalizando = {}
        self.aviso_finalizacao = None
        self.dados_validos = False
        self.criadas = {}
        self.encerrada = None
        self.formulario = None
        self.dialogo_projeto = None
        self.projetos_novos = {}
        self.conferencias = []
        self.aberturas = {}
        self.prazo_tarefa_ms = 20000
        self.confirmacao_tarefa_ms = 5000
        self.e_git = e_git
        self.previas = {}
        self.atividade_sessao = None
        self.previa_alvo = None
        self.passo = 0
        self.fechando = False
        self.confirmando_encerramento = False
        self.filtro_estado = None
        self.detalhe_estreito = False
        nome_central = 'Central de tarefas'
        self.setWindowTitle('Jangada · ' + nome_central + ('' if real else ' · Simulação'))
        self.resize(1200, 780)
        self.setMinimumSize(700, 460)
        centro = QWidget()
        self.setCentralWidget(centro)
        layout = QVBoxLayout(centro)
        self.layout_principal = layout
        layout.setContentsMargins(24, 20, 24, 16)
        layout.setSpacing(12)
        self.fichas = carregar_fichas()
        self.cabecalho = Cabecalho(nome_central, RAIZ / 'default/logo/jangada-symbolic.svg')
        self.marca = self.cabecalho.marca
        self.topo = self.cabecalho.linha
        self.modo = QComboBox()
        self.modo.addItems(['Escuro', 'Claro'])
        self.modo.setAccessibleName('Modo de cor')
        self.modo.setCurrentIndex(1 if QGuiApplication.styleHints().colorScheme() == Qt.ColorScheme.Light else 0)
        self.modo.currentIndexChanged.connect(self.aplicar_tema)
        self.atualizar_botao = QPushButton('Atualizar' if real else 'Avançar simulação')
        self.atualizar_botao.clicked.connect(self.avancar)
        self.novo_projeto = QPushButton('Novo projeto')
        self.novo_projeto.setToolTip('Cria a pasta ou escolhe uma existente e cadastra o projeto. Depois vêm o coordenador e a tarefa.')
        self.novo_projeto.clicked.connect(self.abrir_novo_projeto)
        self.nova = QPushButton('Nova tarefa')
        self.nova.clicked.connect(self.nova_tarefa)
        self.painel = QPushButton('Painel de indicadores')
        self.painel.clicked.connect(self.abrir_indicadores)
        self.topo.addWidget(self.modo)
        layout.addWidget(self.cabecalho)
        self.comandos = QWidget()
        self.comandos.setObjectName('comandos')
        comandos = QHBoxLayout(self.comandos)
        comandos.setContentsMargins(0, 0, 0, 0)
        comandos.setSpacing(8)
        comandos.addStretch()
        for botao in (self.atualizar_botao, self.novo_projeto, self.nova, self.painel):
            comandos.addWidget(botao)
        layout.addWidget(self.comandos)
        self.cotas = ConsultaCotas(self)
        self.faixa_cotas = FaixaCotas()
        self.cotas.ouvir(self.mostrar_cotas)
        layout.addWidget(self.faixa_cotas)
        self.faixa = QLabel(FAIXA)
        self.faixa.setObjectName('faixa')
        self.faixa.setTextFormat(Qt.TextFormat.PlainText)
        self.faixa.setWordWrap(True)
        self.coordenadores = Coordenadores(self)
        comandos.insertWidget(comandos.indexOf(self.nova), self.coordenadores.novo)
        self.coordenadores.layout().insertWidget(0, self.faixa)
        self.resumo = FaixaResumo()
        self.cartoes = {}
        for estado in ('aguardando', 'trabalhando', 'interrompido', 'concluido'):
            cartao = self.resumo.adicionar(estado, GRUPOS[estado], ICONES[FICHA_SESSAO[estado]])
            cartao.clicked.connect(lambda _, e=estado: self.filtrar_estado(e))
            self.cartoes[estado] = cartao
        layout.addWidget(self.resumo)
        divisor = QSplitter()
        self.divisor_sessoes = divisor
        self.painel_lista = QWidget()
        lista_layout = QVBoxLayout(self.painel_lista)
        lista_layout.setContentsMargins(0, 0, 0, 0)
        self.limpar_filtros = QPushButton('Limpar filtros')
        self.limpar_filtros.clicked.connect(self.limpar_busca)
        lista_layout.addWidget(self.limpar_filtros)
        self.conteudo_lista = QStackedWidget()
        self.lista = QTreeWidget()
        self.lista.setHeaderLabels(['Tarefa', 'Projeto', 'Estado', 'Atualização'])
        self.lista.setColumnWidth(0, 270)
        self.lista.setColumnWidth(1, 130)
        self.lista.setColumnWidth(2, 230)
        self.lista.header().setStretchLastSection(False)
        self.lista.header().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        for coluna in (1, 2, 3):
            self.lista.header().setSectionResizeMode(coluna, QHeaderView.ResizeMode.ResizeToContents)
        self.lista.setMinimumHeight(100)
        self.lista.currentItemChanged.connect(self.escolher_na_lista)
        self.conteudo_lista.addWidget(self.lista)
        self.vazio = QWidget()
        self.vazio.setObjectName('vazio')
        vazio_layout = QVBoxLayout(self.vazio)
        vazio_layout.addStretch()
        self.marca_vazio = QLabel()
        self.marca_vazio.setAccessibleName('Jangada')
        vazio_layout.addWidget(self.marca_vazio, alignment=Qt.AlignmentFlag.AlignHCenter)
        self.vazio_titulo = QLabel()
        self.vazio_titulo.setProperty('papel', 'subtitulo')
        self.vazio_titulo.setWordWrap(True)
        self.vazio_titulo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio_layout.addWidget(self.vazio_titulo)
        self.vazio_orientacao = QLabel()
        self.vazio_orientacao.setWordWrap(True)
        self.vazio_orientacao.setAlignment(Qt.AlignmentFlag.AlignCenter)
        vazio_layout.addWidget(self.vazio_orientacao)
        self.vazio_acao = definir_tipo(QPushButton('Nova tarefa'), 'principal')
        self.vazio_acao.clicked.connect(lambda: self.limpar_busca() if self.sessoes else self.nova_tarefa())
        vazio_layout.addWidget(self.vazio_acao, alignment=Qt.AlignmentFlag.AlignHCenter)
        vazio_layout.addStretch()
        self.conteudo_lista.addWidget(self.vazio)
        lista_layout.addWidget(self.conteudo_lista, 1)
        self.ver_detalhe = QPushButton('Ver acompanhamento da seleção')
        self.ver_detalhe.clicked.connect(lambda: self.exibir_detalhe(True))
        self.ver_detalhe.hide()
        lista_layout.addWidget(self.ver_detalhe)
        divisor.addWidget(self.painel_lista)
        detalhes = QWidget()
        direito = QVBoxLayout(detalhes)
        direito.setContentsMargins(16, 16, 16, 0)
        direito.setSpacing(8)
        self.nome = QLabel('Selecione uma sessão')
        self.nome.setTextFormat(Qt.TextFormat.PlainText)
        self.nome.setWordWrap(True)
        self.nome.setProperty('papel', 'subtitulo')
        direito.addWidget(self.nome)
        self.situacao = QLabel()
        self.situacao.setTextFormat(Qt.TextFormat.PlainText)
        self.situacao.setWordWrap(True)
        self.situacao.setObjectName('situacao')
        direito.addWidget(self.situacao)
        self.aviso_encerrada = QLabel('Sessão encerrada. Dados lidos do registro de indicadores. '
                                      'As ações ficam desligadas.')
        self.aviso_encerrada.setObjectName('aviso_encerrada')
        self.aviso_encerrada.setTextFormat(Qt.TextFormat.PlainText)
        self.aviso_encerrada.setWordWrap(True)
        self.aviso_encerrada.hide()
        direito.addWidget(self.aviso_encerrada)
        self.detalhes = QPlainTextEdit()
        self.detalhes.setReadOnly(True)
        self.abas = QTabWidget()
        self.abas.setUsesScrollButtons(True)
        self.abas.setElideMode(Qt.TextElideMode.ElideNone)
        self.atividade = QPlainTextEdit()
        self.atividade.setReadOnly(True)
        acompanhamento = QWidget()
        acompanhamento_layout = QVBoxLayout(acompanhamento)
        acompanhamento_layout.setContentsMargins(0, 12, 0, 0)
        acompanhamento_layout.setSpacing(8)
        for texto_secao in ('Última atividade recebida', 'Mudanças acompanhadas nesta janela'):
            secao = QLabel(texto_secao)
            secao.setProperty('papel', 'secao')
            acompanhamento_layout.addWidget(secao)
            if texto_secao.startswith('Última'):
                self.ultima_atividade = QLabel()
                self.ultima_atividade.setObjectName('ultima_atividade')
                self.ultima_atividade.setTextFormat(Qt.TextFormat.PlainText)
                self.ultima_atividade.setWordWrap(True)
                acompanhamento_layout.addWidget(self.ultima_atividade)
        self.linha_tempo = LinhaTempo()
        acompanhamento_layout.addWidget(self.linha_tempo, 1)
        self.abas.addTab(acompanhamento, 'Acompanhamento')
        self.abas.addTab(self.atividade, 'Saída do agente')
        self.abas.addTab(self.detalhes, 'Detalhes')
        self.rodadas = Rodadas(self)
        self.abas.addTab(self.rodadas, 'Rodadas')
        self.abas.currentChanged.connect(self.trocar_aba)
        self.entrega = QPlainTextEdit()
        self.entrega.setReadOnly(True)
        self.entrega.setPlainText('Use Conferir e integrar para consultar a entrega antes da confirmação.')
        self.abas.addTab(self.entrega, 'Entrega')
        direito.addWidget(self.abas)
        painel_detalhes = Cartao()
        direito = QVBoxLayout(painel_detalhes)
        direito.setContentsMargins(0, 0, 0, 0)
        direito.setSpacing(0)
        self.voltar_lista = QPushButton('Voltar às sessões')
        self.voltar_lista.clicked.connect(lambda: self.exibir_detalhe(False))
        self.voltar_lista.hide()
        direito.addWidget(self.voltar_lista)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        rolagem.setWidget(detalhes)
        direito.addWidget(rolagem, 1)
        self.abrir = QPushButton('Abrir sessão')
        self.abrir.setEnabled(False)
        self.abrir.clicked.connect(self.focar)
        self.integrar = QPushButton('Conferir e integrar')
        self.encerrar = definir_tipo(QPushButton('Encerrar sem integrar'), 'perigo')
        self.integrar.setObjectName('integrar')
        self.encerrar.setObjectName('encerrar')
        self.integrar.setToolTip('Integra as alterações ao projeto; a sessão permanece aberta. Atalho: Alt+I.')
        self.integrar.setShortcut(QKeySequence('Alt+I'))
        self.encerrar.setToolTip('Pede confirmação antes de encerrar sem integrar. Atalho: Ctrl+Shift+E.')
        self.integrar.setEnabled(False)
        self.encerrar.setEnabled(False)
        self.integrar.clicked.connect(self.integrar_interface)
        self.integrar_terminal = QPushButton('Integrar pelo terminal')
        self.integrar_terminal.clicked.connect(lambda: self.finalizar(True))
        self.encerrar.clicked.connect(lambda: self.finalizar(False))
        self.celulas = {chave: BotaoComMotivo(getattr(self, chave))
                        for chave in ('abrir', 'integrar_terminal', 'integrar', 'encerrar')}
        self.motivos = {chave: celula.motivo for chave, celula in self.celulas.items()}
        bloco = QWidget()
        acoes = QVBoxLayout(bloco)
        acoes.setContentsMargins(16, 12, 16, 12)
        acoes.setSpacing(8)
        for chave in ('abrir', 'integrar_terminal', 'integrar'):
            acoes.addWidget(self.celulas[chave])
        acoes.addWidget(separador())
        fecho = QHBoxLayout()
        fecho.setSpacing(8)
        explicacao = QLabel('Conferir e integrar mostra a entrega e pede confirmação. Pronto para conferir não confirma conclusão.')
        explicacao.setObjectName('motivo_acao')
        explicacao.setWordWrap(True)
        fecho.addWidget(explicacao, 1)
        fecho.addWidget(self.celulas['encerrar'], 1)
        acoes.addLayout(fecho)
        direito.addWidget(separador())
        direito.addWidget(bloco)
        self.abas.setMinimumHeight(250)
        self.painel_detalhes = InspetorRolavel()
        self.painel_detalhes.setFrameShape(QScrollArea.Shape.NoFrame)
        self.painel_detalhes.setWidget(painel_detalhes)
        painel_detalhes.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Ignored)
        self.painel_detalhes.setMinimumWidth(0)
        self.painel_lista.setMinimumWidth(0)
        divisor.addWidget(self.painel_detalhes)
        divisor.setSizes([500, 600])
        self.centrais = QTabWidget()
        sessoes = QWidget()
        QVBoxLayout(sessoes).addWidget(divisor)
        self.centrais.addTab(sessoes, 'Sessões')
        atalho_encerrar = QShortcut(QKeySequence('Ctrl+Shift+E'), sessoes)
        atalho_encerrar.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        atalho_encerrar.activated.connect(lambda: self.finalizar(False) if self.encerrar.isEnabled() else None)
        self.operacional = Operacional(self)
        self.centrais.addTab(self.operacional, 'Projetos e fila')
        self.indicadores = Indicadores(self)
        self.centrais.addTab(self.indicadores, 'Indicadores')
        self.centrais.currentChanged.connect(self.trocar_central)
        self.area = QSplitter()
        self.area.addWidget(self.coordenadores)
        self.area.addWidget(self.centrais)
        self.area.setCollapsible(0, False)
        self.area.setStretchFactor(1, 1)
        self.area.setSizes([300, 1000])
        layout.addWidget(self.area, 1)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        # Alt+1 é da coluna de coordenadores; Alt+2 em diante, das abas de detalhe.
        for numero in range(2, self.abas.count() + 1):
            atalho = QShortcut(QKeySequence(f'Alt+{numero}'), self)
            atalho.activated.connect(lambda i=numero - 1: self.ir_para_aba(i))
        self.aplicar_tema()
        self.integracao = QProcess(self)
        self.integracao.finished.connect(self.integracao_fim)
        self.integracao.errorOccurred.connect(self.integracao_erro)
        self.integracao_etapa = None
        self.integracao_nome = None
        self.integracao_pasta = None
        self.consulta = QProcess(self)
        self.consulta.finished.connect(self.consulta_fim)
        self.consulta.errorOccurred.connect(self.consulta_erro)
        self.consulta.readyReadStandardOutput.connect(self.consulta_ler)
        self.consulta.readyReadStandardError.connect(self.consulta_ler)
        self.consulta_saida = bytearray()
        self.consulta_diagnostico = bytearray()
        self.consulta_falha = ''
        self.consulta_total = 0
        self.consulta_observacao = QProcess(self)
        self.consulta_observacao.finished.connect(self.observacao_fim)
        self.consulta_observacao.errorOccurred.connect(self.observacao_erro)
        self.consulta_observacao.readyReadStandardOutput.connect(self.observacao_ler)
        self.consulta_observacao.readyReadStandardError.connect(self.observacao_ler)
        self.observacao_saida = bytearray()
        self.observacao_diagnostico = bytearray()
        self.observacao_falha = ''
        self.observacao_erro_atual = ''
        self.observacao_limite = QTimer(self)
        self.observacao_limite.setSingleShot(True)
        self.observacao_limite.setInterval(1000)
        self.observacao_limite.timeout.connect(self.observacao_expirar)
        self.observacao_repetir = QTimer(self)
        self.observacao_repetir.setSingleShot(True)
        self.observacao_repetir.setInterval(250)
        self.observacao_repetir.timeout.connect(self.observar_estado)
        self.observacao_retentativa = False
        self.observacao_pendente = False
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
        self.limite_evento = QTimer(self)
        self.limite_evento.setSingleShot(True)
        self.limite_evento.setInterval(1000)
        self.limite_evento.timeout.connect(self.atualizar)
        self.atualizacao_pendente = False
        if real:
            self.timer.start()
            self.cotas.iniciar()
        else:
            self.cotas.definir('sem_dado', None, SIMULACAO)
        self.atualizar()

    def mostrar_cotas(self):
        self.faixa_cotas.mostrar(self.cotas.variantes())

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if not hasattr(self, 'area'):
            return
        larga = self.width() >= 1080
        self.layout_principal.setContentsMargins(*((24, 20, 24, 16) if larga else (16, 12, 16, 12)))
        self.cabecalho.compactar(not larga)
        self.comandos.layout().setSpacing(8 if larga else 4)
        for botao in self.comandos.findChildren(QPushButton):
            if botao.property('compacto') != (not larga):
                botao.setProperty('compacto', not larga)
                botao.style().unpolish(botao)
                botao.style().polish(botao)
        if self.width() >= 1080 and self.layout_principal.indexOf(self.comandos) >= 0:
            self.layout_principal.removeWidget(self.comandos)
            self.topo.insertWidget(self.topo.indexOf(self.modo), self.comandos)
        elif self.width() < 1080 and self.layout_principal.indexOf(self.comandos) < 0:
            self.topo.removeWidget(self.comandos)
            self.layout_principal.insertWidget(1, self.comandos)
        estreita = self.width() < 1360
        indice = self.centrais.indexOf(self.coordenadores)
        if estreita and indice < 0:
            self.centrais.addTab(self.coordenadores, 'Coordenadores')
            self.divisor_sessoes.setSizes([420, 480])
        elif not estreita and indice >= 0:
            self.centrais.removeTab(indice)
            self.area.insertWidget(0, self.coordenadores)
            self.area.setCollapsible(0, False)
            self.coordenadores.show()
            self.area.setSizes([300, self.width() - 350])
            self.divisor_sessoes.setSizes([500, 600])
        self.lista.setColumnHidden(1, estreita)
        self.lista.setColumnHidden(3, estreita)
        self.ajustar_sessoes()

    def ajustar_sessoes(self):
        compacta = self.width() < 940
        self.painel_lista.setVisible(not compacta or not self.detalhe_estreito)
        self.painel_detalhes.setVisible(not compacta or self.detalhe_estreito)
        self.ver_detalhe.setVisible(compacta)
        self.voltar_lista.setVisible(compacta)
        self.ver_detalhe.setEnabled(self.selecionada() is not None)
        self.abas.setMinimumHeight(250 if self.height() >= 650 else 200)

    def exibir_detalhe(self, mostrar):
        self.detalhe_estreito = mostrar
        self.ajustar_sessoes()
        if self.width() < 940:
            if mostrar:
                self.painel_detalhes.verticalScrollBar().setValue(0)
                self.voltar_lista.setFocus()
            else:
                self.lista.setFocus()

    def filtrar_estado(self, estado):
        self.filtro_estado = None if self.filtro_estado == estado else estado
        self.centrais.setCurrentIndex(0)
        self.filtrar_sessoes(reselecionar=True)

    def limpar_busca(self):
        self.filtro_estado = None
        self.filtrar_sessoes(reselecionar=True)

    def filtrar_sessoes(self, reselecionar=False):
        self.lista.blockSignals(True)
        visiveis = []
        for nome, item in self.itens.items():
            s = self.sessoes[nome]
            visivel = not self.filtro_estado or estado_exibido(s) == self.filtro_estado
            item.setHidden(not visivel)
            if visivel:
                visiveis.append(item)
        for i in range(self.lista.topLevelItemCount()):
            grupo = self.lista.topLevelItem(i)
            total = sum(not grupo.child(j).isHidden() for j in range(grupo.childCount()))
            grupo.setHidden(total == 0)
            grupo.setText(0, f'{grupo.data(0, PAPEL_GRUPO)} ({total})')
            grupo.setFirstColumnSpanned(True)
        atual = self.lista.currentItem()
        sessao_atual = atual is not None and atual.parent() is not None
        if (sessao_atual and atual not in visiveis) or (reselecionar and not sessao_atual):
            if sessao_atual and not reselecionar:
                self.status.setText('A sessão selecionada saiu do filtro após mudar de estado. '
                                    'Limpe os filtros ou selecione outra sessão.')
            self.lista.setCurrentItem(visiveis[0] if reselecionar and visiveis else None)
            if not visiveis:
                self.lista.clearSelection()
            self.encerrada = None
        self.lista.blockSignals(False)
        for estado, cartao in self.cartoes.items():
            cartao.setChecked(self.filtro_estado == estado)
        self.limpar_filtros.setVisible(bool(self.filtro_estado))
        self.conteudo_lista.setCurrentWidget(self.lista if visiveis else self.vazio)
        self.vazio_titulo.setText('Nenhuma sessão neste filtro' if self.sessoes else 'Nenhuma tarefa acompanhada')
        self.vazio_orientacao.setText('Limpe os filtros para recuperar a lista.' if self.sessoes else
                                     'Crie uma tarefa para acompanhar a atividade do agente.')
        self.vazio_acao.setText('Limpar filtros' if self.sessoes else 'Nova tarefa')
        self.centrais.setTabText(0, f'Sessões ({len(visiveis)})')
        self.selecionar()
        self.ajustar_sessoes()

    def mostrar_coordenadores(self):
        if self.centrais.indexOf(self.coordenadores) >= 0:
            self.centrais.setCurrentWidget(self.coordenadores)

    def selecionada(self):
        item = self.lista.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item and item.parent() is not None else None

    def abrir_indicadores(self):
        if self.centrais.currentWidget() is self.indicadores:
            self.indicadores.atualizar()
        else:
            self.centrais.setCurrentWidget(self.indicadores)
        self.indicadores.cartoes[self.indicadores.escolhido()].setFocus()

    def trocar_central(self, _):
        if self.centrais.currentWidget() is self.indicadores:
            self.indicadores.atualizar()

    def acompanhar_mudancas(self, sessoes):
        for s in sessoes.values():
            anterior = self.observadas.get(s.nome)
            assinatura = (s.inicio, estado_exibido(s), s.mensagem, s.atualizado)
            entradas = self.eventos.setdefault(s.nome, [])
            if anterior is None or anterior[0] != s.inicio:
                entradas.clear()
                self.previas.pop(s.nome, None)
                entradas.append(datetime.now().strftime('%H:%M:%S') + ' · Tarefa encontrada · '
                                + ROTULOS.get(estado_exibido(s), estado_exibido(s)))
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

    def criar_pasta_vazia(self, pasta):
        """Cria a pasta de um projeto novo; devolve o erro, ou None se criou. Nunca reaproveita pasta existente."""
        try:
            pasta.mkdir(parents=True)
        except FileExistsError:
            return f'{pasta} já existe. Escolha essa pasta em vez de digitar o nome.'
        except OSError as erro:
            return f'Não foi possível criar {pasta}: {erro.strerror}.'
        return None

    def iniciar_cadastro(self, pasta):
        processo = QProcess(self)
        self.preparar(processo, ['--projeto', str(pasta), 'cadastrar'], 'jangada-projeto')
        processo.start()
        return processo

    def abrir_novo_projeto(self):
        if self.dialogo_projeto is None:
            self.dialogo_projeto = NovoProjeto(self)
        self.dialogo_projeto.show()
        self.dialogo_projeto.raise_()
        self.dialogo_projeto.activateWindow()

    def abrir_tarefa(self, nome, argumentos):
        """Abre o agente num terminal da Central; devolve o erro, ou None se o terminal saiu.

        O terminal fica aberto quando o agente falha, e a saída de erro vai também
        para um arquivo que a Central mostra se a tarefa não entrar na lista.
        """
        for comando in ('jangada-agente', 'jangada-terminal'):
            if not comando_disponivel(comando, self.jangada):
                return f'Não foi possível iniciar {comando}. Confira --jangada.'
        try:
            arquivo = criar_arquivo_de_erros(nome)
        except (OSError, ValueError) as erro:
            return f'Não foi possível preparar o registro de erros da abertura: {erro}'
        agente = resolver_comando('jangada-agente', self.jangada)[0]
        vetor = ['--classe', 'org.jangada.agente', '--titulo', 'Nova tarefa', '-e', 'bash', '-c', ROTEIRO,
                 'jangada-tarefa', str(arquivo), agente, *argumentos]
        processo = QProcess(self)
        self.preparar(processo, vetor, 'jangada-terminal')
        iniciado, _ = processo.startDetached()
        processo.deleteLater()
        if not iniciado:
            arquivo.unlink(missing_ok=True)
            return 'Não foi possível iniciar jangada-terminal. Confira --jangada.'
        timer = QTimer(self)
        timer.setSingleShot(True)
        timer.timeout.connect(lambda: self.abertura_vencida(nome))
        self.aberturas[nome] = {'arquivo': arquivo, 'timer': timer, 'conferida': False}
        timer.start(self.espera_inicial_ms())
        return None

    def abertura_na_lista(self, nome):
        return any(s.endswith('--' + nome) for s in self.sessoes)

    def encerrar_abertura(self, nome):
        abertura = self.aberturas.pop(nome, None)
        if abertura is not None:
            abertura['timer'].stop()
            abertura['timer'].deleteLater()
            abertura['arquivo'].unlink(missing_ok=True)
        return abertura

    def conferir_aberturas(self):
        for nome in [n for n in self.aberturas if self.abertura_na_lista(n)]:
            self.encerrar_abertura(nome)

    def espera_inicial_ms(self):
        """Quando reconsultar a lista: a confirmação cabe dentro do prazo total, nunca além dele."""
        return max(0, self.prazo_tarefa_ms - max(0, self.confirmacao_tarefa_ms))

    def abertura_vencida(self, nome):
        abertura = self.aberturas.get(nome)
        if abertura is None or self.fechando:
            return
        if self.abertura_na_lista(nome):
            self.encerrar_abertura(nome)
            return
        if not abertura['conferida']:
            abertura['conferida'] = True
            self.atualizar()
            abertura['timer'].start(self.prazo_tarefa_ms - self.espera_inicial_ms())
            return
        linhas = ultimas_linhas(abertura['arquivo'])
        self.encerrar_abertura(nome)
        inicio = ('A tarefa não abriu.' if self.dados_validos else
                  'Não foi possível confirmar que a tarefa abriu: a lista de tarefas não pôde ser consultada.')
        texto = inicio + '\n' + (linhas or SEM_ERRO)
        self.status.setText(texto)
        if self.formulario is not None:
            self.formulario.mostrar_falha(nome, texto)

    def nova_tarefa(self):
        if self.formulario is None:
            self.formulario = NovaTarefa(self)
        self.formulario.show()
        self.formulario.raise_()
        self.formulario.activateWindow()

    def selecionar_nome(self, nome):
        item = self.itens.get(nome)
        if item is not None and item.isHidden():
            self.limpar_busca()
        for i in range(self.lista.topLevelItemCount()):
            grupo = self.lista.topLevelItem(i)
            for j in range(grupo.childCount()):
                item = grupo.child(j)
                if item.data(0, Qt.ItemDataRole.UserRole) == nome:
                    self.lista.setCurrentItem(item)
                    self.exibir_detalhe(True)
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
            fechados = {g.data(0, PAPEL_GRUPO) for g in map(self.lista.topLevelItem, range(self.lista.topLevelItemCount()))
                        if not g.isExpanded()}
            self.lista.clear()
            self.itens = {}
            grupos = {}
            for grupo, nome in estrutura:
                if grupo not in grupos:
                    grupos[grupo] = QTreeWidgetItem(self.lista, [grupo])
                    grupos[grupo].setData(0, PAPEL_GRUPO, grupo)
                    grupos[grupo].setFlags(Qt.ItemFlag.ItemIsEnabled)
                    grupos[grupo].setExpanded(grupo not in fechados)
                self.itens[nome] = QTreeWidgetItem(grupos[grupo])
                self.itens[nome].setData(0, Qt.ItemDataRole.UserRole, nome)
            self.estrutura = estrutura
            self.pintar_grupos()
        itens = self.itens
        for s in ordenadas:
            item = itens[s.nome]
            tarefa = s.tarefa.splitlines()[0] if s.tarefa else s.nome
            estado = estado_exibido(s)
            textos = [tarefa, s.projeto, texto_estado(ROTULOS.get(estado, estado), FICHA_SESSAO.get(estado)), idade(s.atualizado)]
            for coluna, texto in enumerate(textos):
                if item.text(coluna) != texto:
                    item.setText(coluna, texto)
            dica = '<qt>' + html.escape(s.tarefa or s.nome).replace('\n', '<br>') + '</qt>'
            if item.toolTip(0) != dica:
                item.setToolTip(0, dica)
            item.setForeground(2, QColor(self.cores_estado.get(estado_exibido(s), self.fichas['dark']['texto'])))
        escolhido = itens.get(anterior)
        if primeira_carga and itens:
            prioridade = min(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.nome))
            escolhido = itens[prioridade.nome]
        if escolhido and escolhido is not self.lista.currentItem():
            self.lista.setCurrentItem(escolhido)
        self.lista.blockSignals(False)
        self.filtrar_sessoes()
        for estado, cartao in self.cartoes.items():
            cartao.contar(sum(estado_exibido(s) == estado for s in sessoes.values()))
        if anterior and anterior not in sessoes:
            self.status.setText('A sessão selecionada saiu da lista. Selecione outra sessão.')
        self.coordenadores.estados_das_tarefas()
        self.conferir_aberturas()

    def escolher_na_lista(self, atual, *_):
        if atual is not None:
            self.encerrada = None
        self.selecionar()

    def ir_para_aba(self, indice):
        self.centrais.setCurrentIndex(0)
        self.exibir_detalhe(True)
        self.abas.setCurrentIndex(indice)
        self.abas.tabBar().setFocus()

    def trocar_aba(self, _):
        if self.abas.currentWidget() is self.rodadas:
            self.rodadas.aberta()

    def abrir_da_tabela(self, nome, registro):
        """Do indicador à tarefa: seleciona a sessão viva ou mostra a encerrada pelo registro."""
        self.centrais.setCurrentIndex(0)
        item = self.itens.get(nome)
        if nome in self.sessoes and item is not None:
            self.encerrada = None
            self.selecionar_nome(nome)
            self.lista.scrollToItem(item)
            self.status.setText(f'Sessão {nome} aberta a partir dos indicadores.')
        else:
            self.encerrada = (nome, registro)
            self.lista.setCurrentItem(None)
            self.lista.clearSelection()
            self.selecionar()
            self.status.setText(f'A sessão {nome} foi encerrada; o detalhe vem do registro de indicadores.')
        self.lista.setFocus()
        self.exibir_detalhe(True)

    def mostrar_encerrada(self, nome, registro):
        t, entrada, saida = tokens_da_tarefa(registro)
        self.nome.setText(nome)
        self.situacao.setText('Encerrada · fora da lista de sessões\nSem ação pela Central: a sessão não existe mais.')
        self.aviso_encerrada.show()
        self.ultima_atividade.setText('Sessão encerrada; sem acompanhamento.')
        self.linha_tempo.clear()
        self.exibir_atividade(SEM_DADO, nome)
        delegacoes = registro.get('delegacoes')
        self.detalhes.setPlainText(
            f"Estado: encerrada\nAutor: {texto(registro.get('autor'))}\nModelo: {texto(t.get('modelo'))}\n"
            f"Revisor: {SEM_DADO}\n\nSessão\n{nome}\n\n"
            f"Tokens de entrada: {inteiro(entrada)}\nTokens de saída: {inteiro(saida)}\n"
            f"Cache lido: {inteiro(t.get('cache_lido'))}\n"
            + (f"Motivo sem consumo: {texto(t.get('motivo'))}\n" if entrada is None or saida is None else '')
            + f"\nRodadas protegidas: {inteiro(registro.get('rodadas'))}\n"
            f"Rodadas do agente: {inteiro(registro.get('rodadas_sessao'))}\n"
            f"Último resultado: {texto(registro.get('ultimo_resultado'))}\n"
            f"Tempo de revisão: {tempo(registro.get('segundos_revisao'))}\n"
            f"Delegações: {inteiro(len(delegacoes)) if isinstance(delegacoes, list) else SEM_DADO}\n\n"
            'Tarefa, ramo e diretório: sem dado. O registro de indicadores não traz esses campos.')
        self.rodadas.definir(nome)

    def selecionar(self, *_):
        s = self.sessoes.get(self.selecionada())
        self.ver_detalhe.setEnabled(s is not None)
        ocupada = (self.acao.state() != QProcess.ProcessState.NotRunning
                   or self.integracao_etapa is not None)
        pendente = self.finalizacao_pendente(s.nome) if self.dados_validos and s else False
        for botao in (self.abrir, self.integrar, self.integrar_terminal, self.encerrar):
            botao.setEnabled(self.dados_validos and s is not None and (not ocupada) and not pendente)
        motivo = ('Atualize a consulta para liberar as ações.' if not self.dados_validos else
                  'Uma ação está em andamento. Aguarde o resultado.' if ocupada else
                  'Finalização pendente. Confira o terminal.' if pendente else
                  'Sessão encerrada; ações indisponíveis.' if not s and self.encerrada else
                  'Selecione uma sessão.' if not s else '')
        for celula in self.celulas.values():
            celula.explicar(motivo)
        concluido = bool(s and estado_exibido(s) == 'concluido')
        definir_tipo(self.abrir, 'secundario' if concluido or not s else 'principal')
        definir_tipo(self.integrar, 'principal' if concluido else 'secundario')
        if not s and self.encerrada:
            self.mostrar_encerrada(*self.encerrada)
            return
        self.aviso_encerrada.hide()
        self.rodadas.definir(s.nome if s else None)
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
        self.linha_tempo.mostrar(self.eventos.get(s.nome, []), self.fichas['light' if self.modo.currentIndex() else 'dark'])
        self.abrir.setText('Retomar no terminal' if s.estado == 'interrompido' else 'Abrir terminal')
        self.detalhes.setPlainText(f"Estado: {ROTULOS.get(estado, estado)}\nCoordenador: {s.coordenador}\nAutor: {s.agente}\nRevisor: {s.revisor}\nProjeto: {s.projeto}\n\nSessão\n{s.nome}\n\nTarefa\n{s.tarefa or 'Não informada'}\n\nRamo\n{s.ramo or 'Não informado'}\n\nDiretório\n{s.dir or 'Não informado'}\n\nÚltima atualização\n{s.atualizado or 'Não informada'}\n\nMensagem da sessão\n{s.mensagem or 'Sem mensagem'}")
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

    def aplicar_tema(self):
        modo = 'light' if self.modo.currentIndex() == 1 else 'dark'
        c = self.fichas[modo]
        interacao = cores_interacao(c, modo)
        barra_antiga = misturar(c['superficie_elevada'], c['texto_suave'], .7)
        self.cores_estado = {estado: ESTADOS[modo][ficha] for estado, ficha in FICHA_SESSAO.items()}
        self.setStyleSheet(folha_de_estilo(c, modo) + f"""
            QLabel#situacao {{ background: {c['superficie_elevada']}; padding: 8px 12px; border-radius: 8px;
                font-size: 13px; }}
            QLabel#ultima_atividade {{ border-left: 2px solid {c['primaria']}; padding-left: 12px; }}
            QWidget#comandos QPushButton {{ padding: 8px 12px; }}
            QWidget#comandos QPushButton[compacto="true"] {{ padding: 4px 8px; }}
            QWidget#vazio {{ border: 1px dashed {c['texto_suave']}; border-radius: 8px; }}
            QWidget#vazio QLabel {{ border: none; }}
            QTextBrowser#linha_tempo {{ font-family: Inter; border: none; }}
            QPushButton#cartao {{ text-align: left; padding: 0; }}
            QPushButton#cartao:hover {{ border: 1px solid {c['primaria']}; }}
            QPushButton#cartao:checked {{ border: 2px solid {c['primaria']}; }}
            QPushButton#cartao:focus {{ border: 2px dashed {c['primaria']}; }}
            QPushButton#cartao:checked:focus {{ border: 2px dashed {c['primaria']}; }}
            QPushButton#cartao QLabel {{ background: transparent; border: none; padding: 0; }}
            QLabel#cartao_titulo {{ font-size: 13px; font-weight: 600; color: {c['texto_suave']}; }}
            QLabel#cartao_numero {{ font-size: 24px; font-weight: 700; }}
            QLabel#cartao_apoio {{ font-size: 13px; }}
            QLabel#cartao_rodape {{ font-size: 13px; color: {c['texto_suave']}; }}
            QLabel#indicadores_detalhe {{ font-size: 16px; font-weight: 600; }}
            QScrollArea#painel_cotas {{ border: 2px solid transparent; border-radius: 8px; }}
            QScrollArea#painel_cotas:focus {{ border: 2px solid {c['primaria']}; }}
            QProgressBar#barra_cota {{ background: {c['superficie_elevada']}; border: 1px solid {c['texto_suave']};
                border-radius: 6px; }}
            QProgressBar#barra_cota::chunk {{ background: {c['primaria']}; border-radius: 5px; }}
            QProgressBar#barra_cota[estado="alerta"]::chunk {{ background: {ESTADOS[modo]['Bloqueada']}; }}
            QProgressBar#barra_cota[estado="antiga"]::chunk {{ background: {barra_antiga}; }}
            QLabel#cota_valor[alerta="true"] {{ color: {ESTADOS[modo]['Bloqueada']}; font-weight: 600; }}
            QLabel#cota_rotulo {{ font-weight: 600; }}
            QLabel#indicadores_status[falha="true"], QLabel#rodadas_status[falha="true"],
            QLabel#rodadas_aviso[falha="true"] {{ color: {c['atencao']}; font-weight: 600; }}
            QLabel[semdado="true"] {{ color: {c['texto_suave']}; }}
            QLabel#rodadas_titulo {{ font-size: 16px; font-weight: 600; }}
            QLabel#rodadas_falta {{ font-size: 13px; color: {c['texto_suave']}; }}
            QLabel#faixa {{ background: {c['superficie_elevada']}; padding: 6px 12px;
                border-left: 4px solid {c['texto_suave']}; border-radius: 8px; }}
            QLabel#faixa_cotas {{ background: {c['superficie_elevada']}; padding: 4px 12px;
                border-left: 4px solid {c['texto_suave']}; border-radius: 8px; font-size: 13px; }}
            QLabel#coord_titulo, QLabel#coord_nome {{ font-size: 16px; font-weight: 600; }}
            QLabel#coord_hora {{ font-size: 13px; color: {c['texto_suave']}; }}
            QLabel#coord_linha {{ font-family: 'JetBrains Mono'; background: {c['superficie_elevada']};
                border: 1px solid {c['texto_suave']}; border-radius: 8px; padding: 8px; }}
            QLabel#coord_linha:focus {{ border: 2px solid {c['primaria']}; }}
            QLabel#coord_aviso {{ font-weight: 600; }}
            QLabel#coord_status[falha="true"], QLabel#coord_copia[falha="true"] {{
                color: {c['atencao']}; font-weight: 600; }}
            QLabel#aviso_encerrada {{ background: {c['superficie_elevada']}; color: {c['texto']};
                border: 1px solid {c['texto_suave']}; border-left: 4px solid {c['atencao']};
                border-radius: 8px; padding: 12px; font-weight: 600; }}
        """)
        for nome, item in self.itens.items():
            sessao = self.sessoes.get(nome)
            if sessao:
                item.setForeground(2, QColor(self.cores_estado.get(estado_exibido(sessao), c['texto'])))
        self.coordenadores.pintar()
        self.faixa_cotas.pintar(ESTADOS[modo]['Bloqueada'])
        for estado, cartao in self.cartoes.items():
            cartao.pintar(self.cores_estado[estado])
        self.pintar_grupos()
        if self.selecionada() in self.sessoes:
            self.linha_tempo.mostrar(self.eventos.get(self.selecionada(), []), c)

        imagem = self.cabecalho.pintar(c)
        if imagem is None:
            self.marca_vazio.setAccessibleName('')
            self.marca_vazio.hide()
        else:
            self.marca_vazio.setPixmap(imagem)
            self.marca_vazio.setAccessibleName('Jangada')
            self.marca_vazio.show()

    def pintar_grupos(self):
        c = self.fichas['light' if self.modo.currentIndex() == 1 else 'dark']
        for i in range(self.lista.topLevelItemCount()):
            grupo = self.lista.topLevelItem(i)
            grupo.setForeground(0, QColor(c['texto_suave']))
            grupo.setBackground(0, QColor(c['superficie_elevada']))

    def preparar(self, processo, argumentos, comando='jangada-agentes'):
        ambiente = QProcessEnvironment.systemEnvironment()
        programa, extra = resolver_comando(comando, self.jangada)
        for chave, valor in extra.items():
            ambiente.insert(chave, valor)
        ambiente.insert('XDG_STATE_HOME', str(self.estado_dir.parent.parent))
        processo.setProcessEnvironment(ambiente)
        processo.setProgram(programa)
        processo.setArguments(argumentos)

    def iniciar(self, processo, argumentos):
        self.preparar(processo, argumentos)
        processo.start()

    def observar_estado(self):
        if self.consulta_observacao.state() != QProcess.ProcessState.NotRunning:
            self.observacao_pendente = True
            return
        self.observacao_pendente = False
        self.observacao_saida.clear()
        self.observacao_diagnostico.clear()
        self.observacao_erro_atual = ''
        self.iniciar(self.consulta_observacao, ['--observacao-json'])
        self.observacao_limite.start()

    def observacao_ler(self):
        saida = bytes(self.consulta_observacao.readAllStandardOutput())
        erro = bytes(self.consulta_observacao.readAllStandardError())
        if len(self.observacao_saida) + len(self.observacao_diagnostico) + len(saida) + len(erro) > LIMITE:
            self.observacao_erro_atual = 'A observação excedeu o limite de leitura.'
            self.consulta_observacao.kill()
            return
        self.observacao_saida.extend(saida)
        self.observacao_diagnostico.extend(erro[:max(0, 500 - len(self.observacao_diagnostico))])

    def observacao_fim(self, codigo, tipo):
        self.observacao_limite.stop()
        self.observacao_ler()
        if self.observacao_erro_atual:
            self.observacao_erro_texto(self.observacao_erro_atual)
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            detalhe = self.observacao_diagnostico.decode('utf-8', 'replace')
            self.observacao_erro_texto('Não foi possível consultar os caminhos de observação. ' + detalhe)
        else:
            try:
                caminhos = set(ler_observacao(self.observacao_saida.decode('utf-8')))
            except (UnicodeDecodeError, ValueError) as erro:
                self.observacao_erro_texto(str(erro))
            else:
                atuais = set(self.observador.directories() + self.observador.files())
                novos = caminhos - atuais
                recusados = self.observador.addPaths(sorted(novos)) if novos else []
                if atuais - caminhos:
                    self.observador.removePaths(sorted(atuais - caminhos))
                if recusados:
                    self.observacao_erro_texto('Alguns caminhos mudaram durante a observação; nova consulta agendada.')
                    if not self.observacao_retentativa:
                        self.observacao_retentativa = True
                        self.observacao_repetir.start()
                else:
                    falha_anterior = self.observacao_falha
                    self.observacao_falha = ''
                    self.observacao_erro_atual = ''
                    self.observacao_retentativa = False
                    if falha_anterior:
                        self.status.setText('Observação restabelecida.')
        if self.observacao_pendente and not self.fechando:
            self.observar_estado()

    def observacao_erro_texto(self, mensagem):
        self.observacao_falha = mensagem.strip() or 'Consulta de observação inválida.'
        self.status.setText(self.observacao_falha + ' Atualização periódica mantida.')

    def observacao_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.observacao_limite.stop()
            self.observacao_erro_texto('Não foi possível iniciar a consulta de observação. Atualização periódica mantida.')

    def observacao_expirar(self):
        self.observacao_erro_atual = 'Tempo da consulta de observação esgotado.'
        self.consulta_observacao.kill()

    def mudanca_estado(self, *_):
        self.atualizacao_pendente = True
        if not self.limite_evento.isActive():
            self.limite_evento.start()
        self.evento_estado.start()

    def avancar(self):
        self.passo += 1
        self.atualizar()

    def atualizar(self):
        self.evento_estado.stop()
        self.limite_evento.stop()
        self.operacional.atualizar()
        self.coordenadores.atualizar()
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
            self.consulta_saida.clear()
            self.consulta_diagnostico.clear()
            self.consulta_total = 0
            self.consulta_falha = ''
            self.iniciar(self.consulta, ['--lista-json'])
            self.espera.start(10000)

    def consulta_ler(self):
        saida = bytes(self.consulta.readAllStandardOutput())
        erro = bytes(self.consulta.readAllStandardError())
        self.consulta_total += len(saida) + len(erro)
        if self.consulta_total > LIMITE:
            self.consulta_falha = 'A listagem excedeu o limite de leitura.'
            self.consulta.kill()
            return
        self.consulta_saida.extend(saida)
        self.consulta_diagnostico.extend(erro[:max(0, 500 - len(self.consulta_diagnostico))])

    def consulta_fim(self, codigo, tipo):
        self.espera.stop()
        if self.atualizacao_pendente and not self.fechando:
            self.evento_estado.start()
        if self.fechando:
            return
        self.consulta_ler()
        saida = self.consulta_saida
        erro = self.consulta_diagnostico.decode('utf-8', 'replace')
        if self.consulta_falha:
            self.falha(self.consulta_falha)
            return
        if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.falha('Não foi possível consultar as sessões. ' + erro)
            return
        if len(saida) > LIMITE:
            self.falha('A listagem excedeu o limite de leitura.')
            return
        try:
            sessoes = sem_coordenadores(ler_lista(saida.decode('utf-8')))
        except ValueError as exc:
            self.falha(str(exc))
            return
        self.status.setText('Atualizado às ' + datetime.now().strftime('%H:%M:%S') if sessoes else 'Nenhuma sessão disponível. Abra um agente pelo jangada.')
        if self.observacao_falha:
            self.status.setText(self.status.text() + ' ' + self.observacao_falha + ' Atualização periódica mantida.')
        self.mostrar(sessoes)

    def falha(self, mensagem):
        self.dados_validos = False
        self.selecionar()
        texto = mensagem + ' Últimos dados preservados; ações indisponíveis até atualizar.'
        if self.observacao_falha:
            texto += ' ' + self.observacao_falha + ' Atualização periódica mantida.'
        self.status.setText(texto)

    def consulta_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.espera.stop()
            self.falha('Não foi possível iniciar jangada-agentes. Confira o caminho em --jangada.')

    def expirar(self):
        self.consulta_falha = 'Tempo de consulta esgotado.'
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
        pergunta.setText('Rodar testes/verificar.sh e integrar esta entrega por avanço rápido? A sessão fica aberta.')
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
                resolver_comando('jangada-agente-fim', self.jangada)[0], *argumentos])
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

    def confirmar_encerramento(self, nome):
        pergunta = QMessageBox(self)
        pergunta.setWindowTitle('Encerrar sem integrar')
        pergunta.setTextFormat(Qt.TextFormat.PlainText)
        pergunta.setText(f'Encerrar a sessão {nome} sem integrar as alterações ao projeto?\n'
                         'O terminal mantém as conferências e a confirmação de descarte do Core.')
        pergunta.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        pergunta.setDefaultButton(QMessageBox.StandardButton.No)
        return pergunta.exec() == QMessageBox.StandardButton.Yes.value

    def finalizar(self, integrar):
        nome = self.selecionada()
        if not self.dados_validos or nome not in self.sessoes or not NOME.fullmatch(nome) or nome.startswith('-'):
            return
        if (self.confirmando_encerramento or self.acao.state() != QProcess.ProcessState.NotRunning
                or self.integracao_etapa is not None
                or self.finalizacao_pendente(nome)):
            return
        acao = 'integrar e encerrar' if integrar else 'encerrar sem integrar'
        if not self.real:
            self.status.setText(f'Simulação: solicitaria {acao} a sessão {nome}. Nenhum comando foi executado.')
            return
        if not integrar:
            sessao = self.sessoes[nome]
            self.confirmando_encerramento = True
            try:
                confirmado = self.confirmar_encerramento(nome)
            finally:
                self.confirmando_encerramento = False
            # O diálogo modal processa consultas e mudanças de seleção.
            if not confirmado:
                return
            if (self.fechando or not self.dados_validos or nome != self.selecionada()
                    or self.sessoes.get(nome) != sessao or self.integracao_etapa is not None
                    or self.acao.state() != QProcess.ProcessState.NotRunning or self.finalizacao_pendente(nome)):
                self.status.setText('A sessão mudou durante a confirmação; nada foi encerrado. Confira e tente de novo.')
                return
        comando = [resolver_comando('jangada-agente-fim', self.jangada)[0]]
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
        self.operacional.fechar()
        self.indicadores.fechar()
        self.rodadas.fechar()
        self.coordenadores.fechar()
        self.cotas.fechar()
        for conferencia in self.conferencias:
            conferencia.fechar()
        for nome in list(self.aberturas):
            self.encerrar_abertura(nome)
        for timer in (self.timer, self.evento_estado, self.limite_evento, self.observacao_limite,
                      self.observacao_repetir, self.espera,
                      self.tempo_acao, self.tempo_previa, self.tempo_finalizacao):
            timer.stop()
        for processo in (self.consulta, self.consulta_observacao, self.acao, self.previa, self.integracao):
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
                processo.waitForFinished(1000)
        self.finalizando.clear()
        evento.accept()
