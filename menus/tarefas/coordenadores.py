"""Coluna de coordenadores: lista de jangada-agentes --coordenadores-json, painel e caixa de texto.

A caixa não envia nada ao coordenador: copia o texto para a área de
transferência e foca a janela, e o dono cola no terminal. Um envio pelo tmux
podia responder uma permissão aberta no lugar dele.
"""
import json
from pathlib import Path

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QColor, QGuiApplication, QKeySequence, QShortcut
from PyQt6.QtWidgets import (QComboBox, QDialog, QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit,
                             QMessageBox, QPushButton, QScrollArea, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from dados import LIMITE, NOME, ROTULOS, comando_disponivel, estado_exibido
from indicadores import SEM_DADO
from rodadas import CONTROLE, Consulta, data
from visual.fichas import ESTADOS, ICONES

AGENTES = 'jangada-agentes'
COORDENADOR = 'jangada-coordenador'
SUFIXO = '--coordenador'
MENSAGEM_MAX = 8 * 1024
LINHA_MAX = 200
LISTA_MAX = 4096
PROVEDORES = ('claude', 'codex')
SEM_CORE = 'Coordenadores ainda não disponíveis no Core instalado.'
SEM_CICLO = ('Este registro não informa o ciclo da atuação. Retomar e Finalizar atuação '
             'não estão disponíveis neste registro; as ações anteriores continuam disponíveis.')
SEM_RETOMADA = 'O Core informa que a retomada está indisponível neste momento.'
FAIXA = ('Só você faz: sem dado. O Core ainda não informa os commits locais não enviados '
         'dos projetos cadastrados.')
# Estado mostrado: ficha de cor, glifo e texto. Cor sempre vem com texto e glifo.
ESTADOS_COORD = {'aguardando': ('Bloqueada', ICONES['Bloqueada'], 'esperando você'),
                 'trabalhando': ('Executando', ICONES['Executando'], 'trabalhando'),
                 'concluido': ('Concluída', ICONES['Concluída'], 'resposta pronta'),
                 'retomada': (None, ICONES['Planejada'], 'aguardando retomada'),
                 'encerrada': (None, ICONES['Cancelada'], 'atuação encerrada'),
                 'parado': (None, ICONES['Planejada'], 'parado'),
                 'sem': (None, '?', 'estado sem dado')}
AVISOS = {'aguardando': 'O coordenador espera resposta no terminal.',
          'trabalhando': 'O coordenador está trabalhando.',
          'concluido': 'O coordenador terminou a resposta.',
          'retomada': 'A atuação continua aberta. Retome para continuar o trabalho e as tarefas pendentes.',
          'encerrada': 'A atuação foi encerrada explicitamente. Novo coordenador inicia outra atuação.',
          'parado': 'O coordenador está parado. Ir para a janela fica desligado; '
                    'consulte Novo coordenador para abrir no projeto.',
          'sem': 'O Core não informou o estado do coordenador.'}


def linha_limpa(valor, maximo=LINHA_MAX):
    """Texto de uma linha, sem caracteres de controle nem troca de direção."""
    if not isinstance(valor, str):
        return ''
    return ' '.join(CONTROLE.sub('', valor.replace('\t', ' ').replace('\n', ' ')).split())[:maximo]


def texto_curto(valor, maximo):
    return isinstance(valor, str) and len(valor) <= maximo


def ler_coordenadores(bruto):
    """Valida jangada-agentes --coordenadores-json versão 1; devolve a lista de coordenadores."""
    if len(bruto) > LIMITE:
        raise ValueError('A saída excedeu o limite de leitura.')
    try:
        dados = json.loads(bruto)
    except (ValueError, RecursionError) as erro:
        raise ValueError('A saída não é JSON válido.') from erro
    if not isinstance(dados, dict) or type(dados.get('versao')) is not int:
        raise ValueError('A saída não traz a versão do contrato.')
    if dados['versao'] != 1:
        raise ValueError(f'Versão {dados["versao"]} do contrato não é lida por esta Central.')
    lista = dados.get('coordenadores')
    if not isinstance(lista, list) or len(lista) > LISTA_MAX:
        raise ValueError('A saída não traz a lista de coordenadores.')
    vistos = set()
    for c in lista:
        if not isinstance(c, dict):
            raise ValueError('Coordenador em formato inesperado.')
        sessao = c.get('sessao')
        if (not isinstance(sessao, str) or not NOME.fullmatch(sessao) or len(sessao) > 255
                or not sessao.endswith(SUFIXO) or sessao in vistos):
            raise ValueError('A lista traz um nome de coordenador inválido ou repetido.')
        vistos.add(sessao)
        if c.get('projeto') is not None and not (texto_curto(c['projeto'], 4096)
                                                 and c['projeto'].startswith('/') and '\x00' not in c['projeto']):
            raise ValueError('Projeto do coordenador em formato inesperado.')
        if c.get('provedor') is not None and c['provedor'] not in PROVEDORES:
            raise ValueError('Provedor do coordenador em formato inesperado.')
        for campo, maximo in (('estado', 64), ('ultima_linha', 16000), ('atualizado', 64)):
            if c.get(campo) is not None and not texto_curto(c[campo], maximo):
                raise ValueError(f'Campo {campo} do coordenador em formato inesperado.')
        if type(c.get('viva')) is not bool:
            raise ValueError('Campo viva do coordenador em formato inesperado.')
        if 'ciclo' in c and (not isinstance(c['ciclo'], str) or c['ciclo'] not in ('aberta', 'encerrada')):
            raise ValueError('Campo ciclo do coordenador em formato inesperado.')
        if 'atuacao_id' in c and c['atuacao_id'] is not None and not (
                texto_curto(c['atuacao_id'], 4096) and c['atuacao_id']):
            raise ValueError('Campo atuacao_id do coordenador em formato inesperado.')
        if 'retomavel' in c and type(c['retomavel']) is not bool:
            raise ValueError('Campo retomavel do coordenador em formato inesperado.')
        tarefas = c.get('tarefas')
        if not isinstance(tarefas, list) or len(tarefas) > LISTA_MAX or any(
                not isinstance(t, dict) or not isinstance(t.get('sessao'), str)
                or not NOME.fullmatch(t['sessao']) or type(t.get('viva')) is not bool for t in tarefas):
            raise ValueError('Tarefas do coordenador em formato inesperado.')
    return lista


def tem_ciclo(c):
    return all(campo in c for campo in ('ciclo', 'atuacao_id', 'retomavel'))


def estado_coordenador(c):
    """Chave de ESTADOS_COORD para um coordenador validado."""
    if tem_ciclo(c):
        if c['ciclo'] == 'encerrada':
            return 'encerrada'
        if not c['viva']:
            return 'retomada'
    if not c['viva'] or (not tem_ciclo(c) and c.get('estado') == 'encerrado'):
        return 'parado'
    estado = c.get('estado')
    if estado in ('trabalhando', 'iniciado'):
        return 'trabalhando'
    return estado if estado in ('aguardando', 'concluido') else 'sem'


def nome_projeto(c):
    if c.get('projeto'):
        return linha_limpa(Path(c['projeto']).name, 255) or c['sessao']
    return c['sessao'][:-len(SUFIXO)]


def provedor(c):
    return c['provedor'].capitalize() if c.get('provedor') else 'provedor sem dado'


class NovoCoordenador(QDialog):
    """Projeto e provedor; o Core decide entre criar e retomar a atuação."""

    def __init__(self, coluna):
        super().__init__(coluna)
        self.coluna = coluna
        self.setWindowTitle('Novo coordenador' + ('' if coluna.janela.real else ' · Simulação'))
        layout = QVBoxLayout(self)
        formulario = QFormLayout()
        self.projeto = QComboBox()
        self.projeto.setAccessibleName('Projeto do coordenador')
        formulario.addRow('Projeto', self.projeto)
        self.provedor = QComboBox()
        self.provedor.addItems(PROVEDORES)
        self.provedor.setAccessibleName('Provedor do coordenador')
        self.projeto_anterior = None
        formulario.addRow('Provedor', self.provedor)
        layout.addLayout(formulario)
        self.aviso = QLabel()
        self.aviso.setTextFormat(Qt.TextFormat.PlainText)
        self.aviso.setWordWrap(True)
        layout.addWidget(self.aviso)
        botoes = QHBoxLayout()
        fechar = QPushButton('Fechar')
        fechar.clicked.connect(self.hide)
        self.abrir = QPushButton('Abrir coordenador')
        self.abrir.clicked.connect(self.confirmar)
        botoes.addWidget(fechar)
        botoes.addStretch()
        botoes.addWidget(self.abrir)
        layout.addLayout(botoes)
        self.projeto.currentIndexChanged.connect(self.conferir)
        self.carregar()

    def carregar(self):
        self.projeto.clear()
        for nome, caminho in self.coluna.projetos():
            self.projeto.addItem(f'{nome} · {caminho}', caminho)
        self.conferir()

    def conferir(self, *_):
        caminho = self.projeto.currentData()
        if caminho is None:
            self.aviso.setText('Nenhum projeto cadastrado. Cadastre o projeto na aba Projetos e fila.')
            self.abrir.setEnabled(False)
            return
        self.abrir.setEnabled(not self.coluna.ocupada())
        existente = self.coluna.coordenador_do_projeto(caminho)
        if caminho != self.projeto_anterior:
            self.projeto_anterior = caminho
            if existente and existente.get('provedor') in PROVEDORES:
                self.provedor.setCurrentText(existente['provedor'])
        self.provedor.setEnabled(not (existente and existente['viva']))
        self.abrir.setText('Abrir coordenador')
        if existente and existente['viva']:
            self.aviso.setText(f'Este projeto já tem coordenador: {existente["sessao"]}. '
                               'Abrir coordenador leva a ele.')
        elif existente and tem_ciclo(existente) and existente['ciclo'] == 'aberta':
            self.abrir.setText('Retomar atuação')
            self.aviso.setText('Este projeto tem atuação aberta, aguardando retomada. '
                               'Retoma a mesma atuação e preserva suas tarefas. Você pode escolher '
                               'outro provedor após ter saído voluntariamente do anterior.')
            if not existente['retomavel']:
                self.abrir.setEnabled(False)
                self.aviso.setText(SEM_RETOMADA)
        elif existente and not tem_ciclo(existente):
            self.aviso.setText(SEM_CICLO + ' Abrir coordenador usa a ação anterior do Core.')
        else:
            self.aviso.setText('Abre o coordenador numa janela de terminal, na pasta do projeto, '
                               'sem isolamento.')

    def confirmar(self):
        caminho = self.projeto.currentData()
        if caminho is None:
            return
        if self.coluna.abrir_coordenador(caminho, self.provedor.currentText()):
            self.hide()


class Coordenadores(QWidget):

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.lista = []
        self.itens = {}
        self.rascunhos = {}
        self.atual = None
        self.disponivel = False
        self.pendente = False
        self.fechando = False
        self.dialogo = None
        self.pedido = None
        self.prazo_acao_ms = 30000
        self.expirou_acao = False
        self.aviso_saida = None
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 12, 0)
        topo = QHBoxLayout()
        titulo = self.rotulo('coord_titulo')
        titulo.setText('Coordenadores')
        topo.addWidget(titulo, 1)
        self.novo = QPushButton('Novo coordenador')
        self.novo.setToolTip('Escolhe projeto e provedor e abre o coordenador. Atalho: Ctrl+N.')
        self.novo.clicked.connect(self.novo_coordenador)
        topo.addWidget(self.novo)
        layout.addLayout(topo)
        self.status = self.rotulo('coord_status')
        layout.addWidget(self.status)
        self.arvore = QTreeWidget()
        self.arvore.setHeaderLabels(['Coordenador e tarefas', 'Estado'])
        self.arvore.setColumnWidth(0, 260)
        self.arvore.setColumnWidth(1, 240)
        self.arvore.setMinimumHeight(190)
        self.arvore.setAccessibleName('Coordenadores e as tarefas de cada um')
        self.arvore.currentItemChanged.connect(self.escolher)
        self.arvore.itemActivated.connect(self.ativar)
        self.arvore.itemClicked.connect(self.ativar)
        layout.addWidget(self.arvore, 1)
        self.escolha = self.rotulo()
        self.escolha.setText('Escolha um coordenador na lista.')
        layout.addWidget(self.escolha)
        self.painel = QWidget()
        painel = QVBoxLayout(self.painel)
        painel.setContentsMargins(0, 8, 0, 0)
        self.nome = self.rotulo('coord_nome')
        painel.addWidget(self.nome)
        self.situacao = self.rotulo()
        painel.addWidget(self.situacao)
        self.ultima = self.rotulo('coord_linha')
        self.ultima.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse
                                            | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        # Depois das flags, que deixam o rótulo só com foco por clique e o tiram do Tab.
        self.ultima.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.ultima.setAccessibleName('Última linha do coordenador')
        painel.addWidget(self.ultima)
        self.atualizado = self.rotulo('coord_hora')
        painel.addWidget(self.atualizado)
        self.aviso = self.rotulo('coord_aviso')
        painel.addWidget(self.aviso)
        self.caixa = QPlainTextEdit()
        self.caixa.setTabChangesFocus(True)
        self.caixa.setAccessibleName('Mensagem para o coordenador')
        painel.addWidget(QLabel('Mensagem para o coordenador'))
        self.caixa.setPlaceholderText('Escreva com calma. Ctrl+Enter copia o texto e leva à janela; '
                                      'lá você cola e aperta Enter.')
        self.caixa.setMaximumHeight(140)
        self.caixa.textChanged.connect(self.editar)
        painel.addWidget(self.caixa)
        botoes = QVBoxLayout()
        self.copiar = QPushButton('Copiar e ir para a janela')
        self.copiar.setToolTip('Põe o texto na área de transferência e foca a janela. Nada é enviado. '
                               'Atalho: Ctrl+Enter na caixa.')
        self.copiar.clicked.connect(self.copiar_e_ir)
        botoes.addWidget(self.copiar)
        self.ir = QPushButton('Ir para a janela')
        self.ir.setToolTip('Foca a janela do coordenador. Atalho: Alt+J.')
        self.ir.clicked.connect(self.ir_para_janela)
        botoes.addWidget(self.ir)
        painel.addLayout(botoes)
        ciclo = QHBoxLayout()
        self.retomar = QPushButton('Retomar')
        self.retomar.setAccessibleName('Retomar atuação do coordenador')
        self.retomar.clicked.connect(self.retomar_atuacao)
        ciclo.addWidget(self.retomar)
        self.finalizar = QPushButton('Finalizar atuação')
        self.finalizar.clicked.connect(self.finalizar_atuacao)
        ciclo.addWidget(self.finalizar)
        painel.addLayout(ciclo)
        self.copia = self.rotulo('coord_copia')
        painel.addWidget(self.copia)
        self.resultado = self.rotulo('coord_aviso')
        layout.addWidget(self.resultado)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        rolagem.setWidget(self.painel)
        self.rolagem_painel = rolagem
        layout.addWidget(rolagem, 2)
        QWidget.setTabOrder(self.novo, self.arvore)
        QWidget.setTabOrder(self.arvore, self.ultima)
        QWidget.setTabOrder(self.ultima, self.caixa)
        QWidget.setTabOrder(self.caixa, self.copiar)
        QWidget.setTabOrder(self.copiar, self.ir)
        QWidget.setTabOrder(self.ir, self.retomar)
        QWidget.setTabOrder(self.retomar, self.finalizar)
        for tecla in ('Ctrl+Return', 'Ctrl+Enter'):
            atalho = QShortcut(QKeySequence(tecla), self.caixa)
            atalho.setContext(Qt.ShortcutContext.WidgetShortcut)
            atalho.activated.connect(self.copiar_e_ir)
        for tecla, acao in (('Alt+1', self.focar_lista), ('Alt+M', self.focar_caixa),
                            ('Alt+J', self.ir_para_janela), ('Ctrl+N', self.novo_coordenador)):
            QShortcut(QKeySequence(tecla), janela).activated.connect(acao)
        self.consulta = Consulta(janela, AGENTES, self.consulta_fim, prazo_ms=10000)
        self.reconferencia = Consulta(janela, AGENTES, self.reconferencia_fim, prazo_ms=10000)
        self.acao = QProcess(self)
        self.acao.finished.connect(self.acao_fim)
        self.acao.errorOccurred.connect(self.acao_erro)
        self.acao.readyReadStandardOutput.connect(self.ler_saida_acao)
        self.acao.readyReadStandardError.connect(self.ler_saida_acao)
        self.saida_acao = b''
        self.prazo_acao = QTimer(self)
        self.prazo_acao.setSingleShot(True)
        self.prazo_acao.timeout.connect(self.expirar_acao)
        self.foco = QProcess(self)
        self.foco.finished.connect(self.foco_fim)
        self.foco.errorOccurred.connect(self.foco_erro)
        self.prazo_foco = QTimer(self)
        self.prazo_foco.setSingleShot(True)
        self.prazo_foco.timeout.connect(self.foco.kill)
        self.avisar(self.status, 'Simulação: coordenadores não são consultados.' if not janela.real
                    else 'Consultando os coordenadores.')
        self.mostrar_painel()

    def rotulo(self, nome=''):
        rotulo = QLabel()
        if nome:
            rotulo.setObjectName(nome)
        rotulo.setTextFormat(Qt.TextFormat.PlainText)
        rotulo.setWordWrap(True)
        return rotulo

    def avisar(self, rotulo, mensagem, falha=False):
        if rotulo is self.resultado:
            self.aviso_saida = None
        rotulo.setText(mensagem)
        if rotulo.property('falha') != falha:
            rotulo.setProperty('falha', falha)
            rotulo.style().unpolish(rotulo)
            rotulo.style().polish(rotulo)

    # Consulta ---------------------------------------------------------------

    def atualizar(self):
        if self.fechando or not self.janela.real:
            self.novo.setEnabled(False)
            return
        self.disponivel = comando_disponivel(COORDENADOR, self.janela.jangada)
        self.novo.setEnabled(self.disponivel and not self.ocupada())
        if not self.disponivel:
            self.sem_core()
            return
        if self.consulta.ocupada():
            self.pendente = True
            return
        self.pendente = False
        falha = self.consulta.iniciar(['--coordenadores-json'], None)
        if falha:
            self.avisar(self.status, falha, True)

    def sem_core(self):
        self.disponivel = False
        self.novo.setEnabled(False)
        self.mostrar_lista([])
        self.avisar(self.status, SEM_CORE)

    def consulta_fim(self, _alvo, falha, bruto):
        if self.fechando:
            return
        if self.consulta.desconhecida:
            self.sem_core()
        elif falha:
            self.avisar(self.status, falha + ' Últimos dados preservados.', True)
        else:
            try:
                lista = ler_coordenadores(bruto)
            except ValueError as erro:
                self.avisar(self.status, f'Saída inválida. {erro} Últimos dados preservados.', True)
            else:
                self.mostrar_lista(lista)
                self.avisar(self.status, f'{len(lista)} ' + ('coordenador' if len(lista) == 1
                            else 'coordenadores') + '. Linhas lidas do registro, mostradas como dado.'
                            if lista else 'Nenhum coordenador aberto. Use Novo coordenador.')
        if self.pendente:
            self.atualizar()

    # Lista ------------------------------------------------------------------

    def mostrar_lista(self, lista):
        anterior = self.chave()
        self.lista = lista
        self.arvore.blockSignals(True)
        self.arvore.clear()
        self.itens = {}
        for c in lista:
            chave = estado_coordenador(c)
            _, glifo, rotulo = ESTADOS_COORD[chave]
            item = QTreeWidgetItem(self.arvore, [f'{nome_projeto(c)} · {provedor(c)}', f'{glifo} {rotulo}'])
            item.setData(0, Qt.ItemDataRole.UserRole, ('coord', c['sessao']))
            item.setData(1, Qt.ItemDataRole.UserRole, chave)
            self.itens[('coord', c['sessao'])] = item
            for t in c['tarefas']:
                filho = QTreeWidgetItem(item, [t['sessao'], self.estado_tarefa(t)])
                filho.setData(0, Qt.ItemDataRole.UserRole, ('tarefa', t['sessao'], c['sessao']))
                self.itens[('tarefa', t['sessao'], c['sessao'])] = filho
            item.setExpanded(True)
        self.pintar()
        if anterior in self.itens:
            self.arvore.setCurrentItem(self.itens[anterior])
        self.arvore.blockSignals(False)
        self.escolher()

    def estado_tarefa(self, t):
        s = self.janela.sessoes.get(t['sessao'])
        if not t['viva']:
            texto = f'{ICONES["Planejada"]} Sem sessão ativa'
            if s:
                texto += ' · Último estado: ' + ROTULOS.get(estado_exibido(s), estado_exibido(s))
            return texto
        return ROTULOS.get(estado_exibido(s), estado_exibido(s)) if s else SEM_DADO

    def estados_das_tarefas(self):
        """Refaz o estado das tarefas penduradas quando a lista de sessões muda."""
        for c in self.lista:
            for t in c['tarefas']:
                item = self.itens.get(('tarefa', t['sessao'], c['sessao']))
                if item is not None:
                    item.setText(1, self.estado_tarefa(t))

    def pintar(self):
        modo = 'light' if self.janela.modo.currentIndex() == 1 else 'dark'
        suave = self.janela.fichas[modo]['texto_suave']
        for chave, item in self.itens.items():
            if chave[0] != 'coord':
                continue
            ficha = ESTADOS_COORD[item.data(1, Qt.ItemDataRole.UserRole)][0]
            item.setForeground(1, QColor(ESTADOS[modo][ficha] if ficha else suave))

    def chave(self):
        item = self.arvore.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def coordenador(self, sessao):
        return next((c for c in self.lista if c['sessao'] == sessao), None)

    def coordenador_do_projeto(self, caminho):
        try:
            alvo = Path(caminho).resolve()
        except (OSError, ValueError):
            return None
        candidatos = [c for c in self.lista if c.get('projeto') and Path(c['projeto']) == alvo]
        return next((c for c in candidatos if c['viva'] or c.get('ciclo') == 'aberta'),
                    next(iter(candidatos), None))

    def projetos(self):
        """Projetos cadastrados, da consulta de Projetos e fila: nome e caminho absoluto."""
        lista = []
        for p in self.janela.operacional.dados.get('projetos', []):
            caminho = p.get('caminho') if isinstance(p, dict) else None
            if isinstance(caminho, str) and caminho.startswith('/') and not any(c in caminho for c in ('\n', '\x00')):
                nome = p.get('nome') if isinstance(p.get('nome'), str) else Path(caminho).name
                lista.append((linha_limpa(nome, 255) or Path(caminho).name, caminho))
        return lista

    def escolher(self, *_):
        chave = self.chave()
        if chave is not None:
            sessao = chave[1] if chave[0] == 'coord' else chave[2]
            if sessao != self.atual:
                self.atual = sessao
                self.caixa.blockSignals(True)
                self.caixa.setPlainText(self.rascunhos.get(sessao, ''))
                self.caixa.blockSignals(False)
                self.copia.clear()
        elif self.atual is not None and self.coordenador(self.atual) is None:
            self.atual = None
        self.mostrar_painel()

    def ativar(self, item, *_):
        chave = item.data(0, Qt.ItemDataRole.UserRole) if item else None
        if not chave or chave[0] != 'tarefa':
            return
        nome = chave[1]
        alvo = self.janela.itens.get(nome)
        if alvo is None or nome not in self.janela.sessoes:
            self.avisar(self.status, f'A tarefa {nome} não está na lista de sessões.')
            return
        self.janela.centrais.setCurrentIndex(0)
        self.janela.encerrada = None
        self.janela.lista.setCurrentItem(alvo)
        self.janela.lista.scrollToItem(alvo)
        self.janela.lista.setFocus()

    # Painel -----------------------------------------------------------------

    def mostrar_painel(self):
        c = self.coordenador(self.atual) if self.atual else None
        self.painel.setVisible(c is not None)
        self.rolagem_painel.setVisible(c is not None)
        self.escolha.setVisible(c is None)
        if self.aviso_saida is not None and (c is None or not c['viva'] or c.get('ciclo') != 'aberta'
                or self.aviso_saida != (c['sessao'], c.get('atuacao_id'))):
            self.avisar(self.resultado, '')
        if c is None:
            self.nome.setText('Escolha um coordenador na lista.')
            for rotulo in (self.situacao, self.ultima, self.atualizado, self.aviso):
                rotulo.clear()
            self.caixa.setEnabled(False)
            self.copiar.setEnabled(False)
            self.ir.setEnabled(False)
            self.retomar.setEnabled(False)
            self.finalizar.setEnabled(False)
            return
        chave = estado_coordenador(c)
        _, glifo, rotulo = ESTADOS_COORD[chave]
        self.nome.setText(f'{nome_projeto(c)} · {provedor(c)}')
        projeto = linha_limpa(c.get('projeto'), 4096) or SEM_DADO
        self.situacao.setText(f'{glifo} {rotulo} · sessão {c["sessao"]}\nProjeto: {projeto}')
        self.ultima.setText('Última linha: ' + (linha_limpa(c.get('ultima_linha')) or SEM_DADO))
        self.atualizado.setText('Atualizado em ' + data(c.get('atualizado')))
        self.avisar(self.aviso, AVISOS[chave])
        self.caixa.setEnabled(True)
        ocupado = self.foco.state() != QProcess.ProcessState.NotRunning or self.ocupada()
        self.copiar.setEnabled(c['viva'] and not ocupado)
        self.ir.setEnabled(c['viva'] and not ocupado)
        aberta = tem_ciclo(c) and c['ciclo'] == 'aberta'
        if aberta and not c['viva'] and not c['retomavel']:
            self.avisar(self.aviso, AVISOS[chave] + ' ' + SEM_RETOMADA)
        if not tem_ciclo(c):
            self.avisar(self.aviso, AVISOS[chave] + ' ' + SEM_CICLO)
        permitido = self.janela.real and self.disponivel and not ocupado
        self.retomar.setEnabled(permitido and aberta and not c['viva'] and c['retomavel']
                                and bool(c.get('projeto')) and c.get('provedor') in PROVEDORES)
        self.finalizar.setEnabled(permitido and aberta)

    def editar(self):
        if self.atual:
            self.rascunhos[self.atual] = self.caixa.toPlainText()
        self.copia.clear()

    def focar_lista(self):
        self.janela.mostrar_coordenadores()
        self.arvore.setFocus()
        if self.arvore.currentItem() is None and self.arvore.topLevelItemCount():
            self.arvore.setCurrentItem(self.arvore.topLevelItem(0))

    def focar_caixa(self):
        self.janela.mostrar_coordenadores()
        if self.caixa.isEnabled():
            self.caixa.setFocus()
        else:
            self.escolha.setText('Escolha um coordenador antes de escrever.')
            self.avisar(self.copia, 'Escolha um coordenador antes de escrever.')

    def ir_para_janela(self):
        c = self.coordenador(self.atual) if self.atual else None
        if c is None or not self.ir.isEnabled():
            return False
        sessao = c['sessao']
        if not NOME.fullmatch(sessao) or not sessao.endswith(SUFIXO) or sessao.startswith('-'):
            return False
        if not self.janela.real:
            self.avisar(self.copia, f'Simulação: iria para a janela de {sessao}.')
            return True
        self.janela.preparar(self.foco, ['--focar', sessao], AGENTES)
        self.foco.start()
        self.prazo_foco.start(30000)
        self.mostrar_painel()
        return True

    def copiar_e_ir(self):
        c = self.coordenador(self.atual) if self.atual else None
        if c is None or not self.copiar.isEnabled():
            return
        texto = self.caixa.toPlainText()
        if not texto.strip():
            self.avisar(self.copia, 'Escreva a mensagem antes de copiar.', True)
            return
        if len(texto.encode('utf-8')) > MENSAGEM_MAX:
            self.avisar(self.copia, 'A mensagem passa de 8 KiB. Encurte o texto antes de copiar.', True)
            return
        QGuiApplication.clipboard().setText(texto)
        if self.ir_para_janela():
            self.avisar(self.copia, 'Copiado; cole no terminal do coordenador.')
        else:
            self.avisar(self.copia, 'Copiado; a janela não pôde ser focada. Cole no terminal do coordenador.')

    def foco_fim(self, codigo, tipo):
        self.prazo_foco.stop()
        erro = bytes(self.foco.readAllStandardError()).decode('utf-8', 'replace')[:500]
        self.foco.readAllStandardOutput()
        if self.fechando:
            return
        if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.avisar(self.copia, 'Não foi possível focar a janela. ' + linha_limpa(erro, 500), True)
        self.mostrar_painel()

    def foco_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo_foco.stop()
            self.avisar(self.copia, f'Não foi possível executar {AGENTES}.', True)
            self.mostrar_painel()

    # Novo coordenador -------------------------------------------------------

    def novo_coordenador(self):
        if not self.novo.isEnabled():
            if self.janela.real and not self.ocupada():
                self.avisar(self.status, SEM_CORE)
            return
        if self.dialogo is None:
            self.dialogo = NovoCoordenador(self)
        else:
            self.dialogo.carregar()
        self.dialogo.show()
        self.dialogo.raise_()
        self.dialogo.activateWindow()

    def selecionar(self, sessao):
        item = self.itens.get(('coord', sessao))
        if item is not None:
            self.arvore.setCurrentItem(item)

    def abrir_coordenador(self, caminho, escolhido):
        """Reconsulta antes de focar, criar ou retomar; não envia texto ao cliente."""
        if (escolhido not in PROVEDORES or not isinstance(caminho, str) or not caminho.startswith('/')
                or '\x00' in caminho):
            return False
        return self.pedir_acao(dict(tipo='abrir', caminho=caminho, provedor=escolhido))

    def ocupada(self):
        return self.pedido is not None

    def controles_acao(self):
        self.novo.setEnabled(self.janela.real and self.disponivel and not self.ocupada())
        self.mostrar_painel()
        if self.dialogo is not None:
            self.dialogo.conferir()

    def pedir_acao(self, pedido):
        if self.fechando or not self.janela.real or not self.disponivel or self.ocupada():
            return False
        self.pedido = pedido
        self.controles_acao()
        self.avisar(self.resultado, 'Reconferindo a atuação no Core.')
        falha = self.reconferencia.iniciar(['--coordenadores-json'], None)
        if falha:
            self.terminar_acao(falha, True)
            return False
        return True

    def retomar_atuacao(self):
        c = self.coordenador(self.atual) if self.atual else None
        if c is not None and self.retomar.isEnabled():
            self.pedir_acao(dict(tipo='retomar', caminho=c['projeto'], provedor=c['provedor'],
                                sessao=c['sessao'], atuacao_id=c['atuacao_id']))

    def finalizar_atuacao(self):
        c = self.coordenador(self.atual) if self.atual else None
        if c is None or not self.finalizar.isEnabled():
            return
        if c['viva']:
            self.orientar_saida(c)
            return
        pedido = dict(tipo='finalizar', sessao=c['sessao'], atuacao_id=c['atuacao_id'])
        # O diálogo modal processa eventos; reserve a ação antes da confirmação.
        self.pedido = pedido
        self.controles_acao()
        confirmacao = QMessageBox(self)
        confirmacao.setWindowTitle('Finalizar atuação')
        confirmacao.setTextFormat(Qt.TextFormat.PlainText)
        confirmacao.setText(f'Finalizar a atuação de {nome_projeto(c)}?\n'
                             'Confirme que salvou o estado e o diário e saiu voluntariamente. '
                             'As tarefas pendentes serão preservadas e o checkpoint será arquivado pelo Core.')
        confirmacao.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel)
        confirmacao.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirmacao.button(QMessageBox.StandardButton.Yes).setText('Finalizar atuação')
        confirmacao.button(QMessageBox.StandardButton.Cancel).setText('Cancelar')
        resposta = confirmacao.exec()
        self.pedido = None
        self.controles_acao()
        if resposta == QMessageBox.StandardButton.Yes:
            self.pedir_acao(pedido)

    def orientar_saida(self, c):
        self.selecionar(c['sessao'])
        self.avisar(self.resultado, 'A sessão está viva. Salve o estado e o diário e saia voluntariamente. '
                    'Use Ir para a janela; depois, finalize a atuação.', True)
        self.aviso_saida = (c['sessao'], c.get('atuacao_id'))

    def reconferencia_fim(self, _alvo, falha, bruto):
        if self.fechando or self.pedido is None:
            return
        if falha:
            self.terminar_acao('Não foi possível reconferir a atuação. ' + falha, True)
            return
        try:
            lista = ler_coordenadores(bruto)
        except ValueError as erro:
            self.terminar_acao(f'Não foi possível reconferir a atuação. {erro}', True)
            return
        pedido = self.pedido
        self.mostrar_lista(lista)
        if pedido['tipo'] == 'abrir':
            c = self.coordenador_do_projeto(pedido['caminho'])
        else:
            c = self.coordenador(pedido['sessao'])
            if (c is None or not tem_ciclo(c) or c['ciclo'] != 'aberta'
                    or c['atuacao_id'] != pedido['atuacao_id']):
                self.terminar_acao('A atuação mudou. Confira os dados atualizados e tente novamente.', True)
                return
            if pedido['tipo'] == 'retomar' and (c.get('projeto') != pedido['caminho']
                                                or c.get('provedor') != pedido['provedor']):
                self.terminar_acao('O projeto ou provedor mudou. Confira a atuação e tente novamente.', True)
                return
        if c and c['viva']:
            self.terminar_acao('A sessão já está viva.')
            self.selecionar(c['sessao'])
            if pedido['tipo'] == 'finalizar':
                self.orientar_saida(c)
            else:
                self.ir_para_janela()
            return
        if pedido['tipo'] != 'finalizar':
            if c and tem_ciclo(c) and c['ciclo'] == 'aberta' and not c['retomavel']:
                self.terminar_acao(SEM_RETOMADA, True)
                return
            self.abrir_janela(pedido)
            return
        self.expirou_acao = False
        self.saida_acao = b''
        self.janela.preparar(self.acao, ['--finalizar', c['sessao']], COORDENADOR)
        self.acao.start()
        self.prazo_acao.start(self.prazo_acao_ms)
        self.avisar(self.resultado, 'Aguardando o resultado do Core.')

    def abrir_janela(self, pedido):
        # --janela pode manter o terminal em primeiro plano; seus canais não pertencem à Central.
        processo = QProcess(self)
        self.janela.preparar(processo, ['--projeto', pedido['caminho'], '--provedor', pedido['provedor'],
                                      '--janela'], COORDENADOR)
        processo.setStandardInputFile(QProcess.nullDevice())
        processo.setStandardOutputFile(QProcess.nullDevice())
        processo.setStandardErrorFile(QProcess.nullDevice())
        iniciado, _pid = processo.startDetached()
        processo.deleteLater()
        self.terminar_acao('Abertura ou retomada solicitada. Confira o resultado na janela.' if iniciado
                            else f'Não foi possível executar {COORDENADOR}.', not iniciado)
        if iniciado:
            self.atualizar()

    def ler_saida_acao(self):
        for canal in (self.acao.readAllStandardError, self.acao.readAllStandardOutput):
            trecho = bytes(canal())
            self.saida_acao = (self.saida_acao + trecho)[-8192:]

    def expirar_acao(self):
        self.expirou_acao = True
        self.acao.kill()

    def acao_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo_acao.stop()
            self.terminar_acao(f'Não foi possível executar {COORDENADOR}.', True)

    def acao_fim(self, codigo, tipo):
        self.prazo_acao.stop()
        self.ler_saida_acao()
        if self.fechando or self.pedido is None:
            return
        detalhe = linha_limpa(self.saida_acao.decode('utf-8', 'replace'), 2000)
        if self.expirou_acao:
            self.terminar_acao('Tempo esgotado. Confira o estado no Core antes de tentar novamente. ' + detalhe, True)
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.terminar_acao('O Core recusou ou falhou na ação. ' + detalhe, True)
        else:
            self.terminar_acao('Atuação finalizada pelo Core. ' + detalhe)
            self.atualizar()

    def terminar_acao(self, mensagem, falha=False):
        self.pedido = None
        self.avisar(self.resultado, mensagem, falha)
        self.controles_acao()

    def fechar(self):
        self.fechando = True
        self.consulta.fechar()
        self.reconferencia.fechar()
        self.prazo_acao.stop()
        if self.acao.state() != QProcess.ProcessState.NotRunning:
            self.acao.blockSignals(True)
            self.acao.kill()
            self.acao.waitForFinished(1000)
        self.prazo_foco.stop()
        if self.foco.state() != QProcess.ProcessState.NotRunning:
            self.foco.blockSignals(True)
            self.foco.kill()
            self.foco.waitForFinished(1000)
