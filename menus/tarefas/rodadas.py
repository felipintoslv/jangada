"""Rodadas e último parecer de uma sessão, pelas consultas do Core, sem ler o estado direto."""
from datetime import datetime
import json
import re

from PyQt6.QtCore import QObject, QProcess, QTimer, Qt
from PyQt6.QtWidgets import (QFormLayout, QHBoxLayout, QLabel, QPlainTextEdit, QPushButton,
                             QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget)
from dados import LIMITE, NOME, comando_disponivel
import indicadores
from indicadores import SEM_DADO, finito, inteiro, origem, tempo, texto, tokens_da_tarefa

INDICADORES = 'jangada-indicadores'
AGENTES = 'jangada-agentes'
# Tabulação e quebra de linha ficam; o resto do controle e a troca de direção saem.
CONTROLE = re.compile('[\x00-\x08\x0b-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')
PARECER_MAX = 200000
FALTA_NO_CORE = 'Pareceres antigos: sem dado. O Core guarda só o texto do último parecer.'
SEM_LISTA = 'Lista de rodadas ainda não disponível no Core instalado.'
COLUNAS = ['Rodada', 'Origem', 'Resultado', 'Revisor', 'Modelo', 'Data', 'Tempo', 'Apontamentos']
RODADAS_MAX = 4096


def limpar(valor):
    return CONTROLE.sub('', valor)


def registros_da_sessao(bruto, nome):
    """Entradas de tarefas do jangada-indicadores --json com esta sessão."""
    return [r for r in indicadores.ler(bruto)['tarefas'] if r.get('sessao') == nome]


def ler_contexto(bruto, nome):
    """Valida jangada-agentes --contexto-json versão 1; devolve o parecer ou None."""
    if len(bruto) > LIMITE:
        raise ValueError('A saída excedeu o limite de leitura.')
    try:
        dados = json.loads(bruto, parse_constant=indicadores.recusar_constante)
    except (ValueError, RecursionError) as erro:
        raise ValueError('A saída não é JSON válido.') from erro
    if not isinstance(dados, dict) or type(dados.get('versao')) is not int:
        raise ValueError('A saída não traz a versão do contrato.')
    if dados['versao'] != 1:
        raise ValueError(f'Versão {dados["versao"]} do contrato não é lida por esta Central.')
    if dados.get('sessao') != nome:
        raise ValueError('A saída fala de outra sessão.')
    parecer = dados.get('parecer')
    if parecer is None:
        return None
    if (not isinstance(parecer, dict) or type(parecer.get('rodada')) is not int or parecer['rodada'] < 0
            or not isinstance(parecer.get('origem'), str) or not isinstance(parecer.get('texto'), str)):
        raise ValueError('O parecer veio em formato inesperado.')
    return parecer


def ler_rodadas(bruto, nome):
    """Valida jangada-agentes --rodadas-json versão 1; devolve a lista de rodadas."""
    if len(bruto) > LIMITE:
        raise ValueError('A saída excedeu o limite de leitura.')
    try:
        dados = json.loads(bruto, parse_float=finito, parse_constant=indicadores.recusar_constante)
    except (ValueError, RecursionError) as erro:
        raise ValueError('A saída não é JSON válido.') from erro
    if not isinstance(dados, dict) or type(dados.get('versao')) is not int:
        raise ValueError('A saída não traz a versão do contrato.')
    if dados['versao'] != 1:
        raise ValueError(f'Versão {dados["versao"]} do contrato não é lida por esta Central.')
    if dados.get('sessao') != nome:
        raise ValueError('A saída fala de outra sessão.')
    lista = dados.get('rodadas')
    if not isinstance(lista, list) or len(lista) > RODADAS_MAX or any(not isinstance(r, dict) for r in lista):
        raise ValueError('A saída não traz a lista de rodadas.')
    return lista


def data(valor):
    if not isinstance(valor, str) or len(valor) > 64:
        return SEM_DADO
    try:
        quando = datetime.fromisoformat(valor)
    except ValueError:
        return SEM_DADO
    if quando.tzinfo is None:
        return SEM_DADO
    try:
        return quando.astimezone().strftime('%d/%m/%Y %H:%M')
    except (OverflowError, OSError, ValueError):
        return SEM_DADO


def linha_rodada(r):
    """Textos de uma rodada na ordem de COLUNAS; campo ausente ou fora do tipo vira sem dado."""
    quando = next((r[c] for c in ('data', 'fim', 'inicio') if isinstance(r.get(c), str)), None)
    return [inteiro(r.get('rodada')) if type(r.get('rodada')) is int else SEM_DADO,
            origem(r.get('origem')), texto(r.get('resultado')), texto(r.get('revisor'), 128),
            texto(r.get('modelo'), 128), data(quando), tempo(r.get('segundos')),
            inteiro(r.get('apontamentos')) if type(r.get('apontamentos')) is int else SEM_DADO]


class Consulta(QObject):
    """Um comando do Core por vez, com prazo; o resultado volta com o nome da sessão pedida."""

    def __init__(self, janela, comando, ao_terminar, prazo_ms=15000):
        super().__init__(janela)
        self.janela = janela
        self.comando = comando
        self.ao_terminar = ao_terminar
        self.prazo_ms = prazo_ms
        self.alvo = None
        self.expirou = False
        self.desconhecida = False
        self.processo = QProcess(self)
        self.processo.finished.connect(self.fim)
        self.processo.errorOccurred.connect(self.erro)
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.expirar)

    def ocupada(self):
        return self.processo.state() != QProcess.ProcessState.NotRunning

    def iniciar(self, argumentos, alvo):
        """Devolve a mensagem de falha imediata, ou None se a consulta saiu."""
        if not comando_disponivel(self.comando, self.janela.jangada):
            return f'Comando {self.comando} não encontrado. Instale ou atualize o jangada-core.'
        self.alvo = alvo
        self.expirou = False
        self.desconhecida = False
        self.janela.preparar(self.processo, argumentos, self.comando)
        self.processo.start()
        self.prazo.start(self.prazo_ms)
        return None

    def expirar(self):
        self.expirou = True
        self.processo.kill()

    def erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo.stop()
            self.ao_terminar(self.alvo, f'Não foi possível executar {self.comando}.', None)

    def fim(self, codigo, tipo):
        self.prazo.stop()
        bruto = bytes(self.processo.readAllStandardOutput())
        erro = bytes(self.processo.readAllStandardError())[:4096].lower()
        # Core sem a consulta: o atual sai com 2 no uso errado, o antigo com 1 e "opção desconhecida".
        self.desconhecida = (not self.expirou and tipo == QProcess.ExitStatus.NormalExit
                             and (codigo == 2 or (codigo == 1 and 'opção desconhecida'.encode() in erro)))
        if self.expirou:
            self.ao_terminar(self.alvo, f'Tempo esgotado ao consultar {self.comando}.', None)
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.ao_terminar(self.alvo, f'{self.comando} terminou com erro.', None)
        else:
            self.ao_terminar(self.alvo, None, bruto)

    def fechar(self):
        self.prazo.stop()
        if self.ocupada():
            self.processo.blockSignals(True)
            self.processo.kill()
            self.processo.waitForFinished(1000)


class Rodadas(QWidget):
    CAMPOS = (('rodadas', 'Rodadas protegidas'), ('rodadas_sessao', 'Rodadas do agente'),
              ('ultimo_resultado', 'Último resultado'), ('segundos_revisao', 'Tempo de revisão'),
              ('tokens', 'Tokens de entrada e saída'))

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.alvo = None
        self.consultado = None
        self.fechando = False
        layout = QVBoxLayout(self)
        topo = QHBoxLayout()
        self.atualizar_botao = QPushButton('Atualizar rodadas')
        self.atualizar_botao.setToolTip('Consulta de novo as rodadas e o último parecer desta sessão.')
        self.atualizar_botao.clicked.connect(self.atualizar)
        topo.addWidget(self.atualizar_botao)
        self.status = self.rotulo('rodadas_status')
        topo.addWidget(self.status, 1)
        layout.addLayout(topo)
        titulo = self.rotulo('rodadas_titulo')
        titulo.setText('Rodadas')
        layout.addWidget(titulo)
        formulario = QFormLayout()
        self.valores = {}
        for chave, nome in self.CAMPOS:
            self.valores[chave] = self.rotulo()
            formulario.addRow(nome, self.valores[chave])
        layout.addLayout(formulario)
        self.status_rodadas = self.rotulo('rodadas_aviso')
        layout.addWidget(self.status_rodadas)
        self.titulo_lista = self.rotulo('rodadas_titulo')
        self.titulo_lista.setText('Lista de rodadas')
        layout.addWidget(self.titulo_lista)
        self.status_lista = self.rotulo('rodadas_aviso')
        layout.addWidget(self.status_lista)
        self.tabela = QTreeWidget()
        self.tabela.setRootIsDecorated(False)
        self.tabela.setAllColumnsShowFocus(True)
        self.tabela.setColumnCount(len(COLUNAS))
        self.tabela.setHeaderLabels(COLUNAS)
        self.tabela.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.tabela.setAccessibleName('Lista de rodadas da sessão')
        layout.addWidget(self.tabela, 1)
        self.titulo_parecer = self.rotulo('rodadas_titulo')
        layout.addWidget(self.titulo_parecer)
        self.status_parecer = self.rotulo('rodadas_aviso')
        layout.addWidget(self.status_parecer)
        self.parecer = QPlainTextEdit()
        self.parecer.setReadOnly(True)
        self.parecer.setAccessibleName('Texto do último parecer')
        layout.addWidget(self.parecer, 1)
        falta = self.rotulo('rodadas_falta')
        falta.setText(FALTA_NO_CORE)
        layout.addWidget(falta)
        QWidget.setTabOrder(self.atualizar_botao, self.tabela)
        QWidget.setTabOrder(self.tabela, self.parecer)
        self.consulta_indicadores = Consulta(janela, INDICADORES, self.indicadores_fim)
        self.consulta_lista = Consulta(janela, AGENTES, self.lista_fim)
        self.consulta_parecer = Consulta(janela, AGENTES, self.parecer_fim)
        self.consultas = (self.consulta_indicadores, self.consulta_lista, self.consulta_parecer)
        self.limpar()

    def rotulo(self, nome=''):
        rotulo = QLabel()
        if nome:
            rotulo.setObjectName(nome)
        rotulo.setTextFormat(Qt.TextFormat.PlainText)
        rotulo.setWordWrap(True)
        rotulo.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return rotulo

    def valor(self, rotulo, conteudo):
        rotulo.setText(conteudo)
        vazio = conteudo == SEM_DADO
        if rotulo.property('semdado') != vazio:
            rotulo.setProperty('semdado', vazio)
            rotulo.style().unpolish(rotulo)
            rotulo.style().polish(rotulo)

    def avisar(self, rotulo, mensagem, falha=False):
        rotulo.setText(mensagem)
        if rotulo.property('falha') != falha:
            rotulo.setProperty('falha', falha)
            rotulo.style().unpolish(rotulo)
            rotulo.style().polish(rotulo)

    def limpar(self):
        for rotulo in self.valores.values():
            self.valor(rotulo, SEM_DADO)
        self.titulo_parecer.setText('Último parecer')
        self.parecer.setPlainText(SEM_DADO)
        self.tabela.clear()
        self.avisar(self.status_rodadas, '')
        self.avisar(self.status_lista, '')
        self.avisar(self.status_parecer, '')
        if not self.janela.real:
            self.atualizar_botao.setEnabled(False)
            self.avisar(self.status, 'Simulação: rodadas e parecer não são consultados.')
        elif self.alvo is None:
            self.atualizar_botao.setEnabled(False)
            self.avisar(self.status, 'Selecione uma sessão para ver as rodadas.')
        else:
            self.atualizar_botao.setEnabled(True)
            self.avisar(self.status, 'Abra esta aba para consultar as rodadas.')

    def visivel(self):
        return self.janela.abas.currentWidget() is self

    def definir(self, nome):
        """Troca a sessão mostrada; consulta só quando a aba está aberta."""
        if nome is not None and not NOME.fullmatch(nome):
            nome = None
        if nome == self.alvo:
            return
        self.alvo = nome
        self.consultado = None
        self.limpar()
        if self.visivel():
            self.atualizar()

    def aberta(self):
        if self.alvo is not None and self.consultado != self.alvo:
            self.atualizar()

    def atualizar(self):
        if self.fechando or not self.janela.real or self.alvo is None:
            return
        self.consultado = self.alvo
        self.limpar()
        self.avisar(self.status, f'Consultando a sessão {self.alvo}.')
        for consulta, argumentos, rotulo, carregando in (
                (self.consulta_indicadores, ['--json'], self.status_rodadas, 'Carregando as rodadas.'),
                (self.consulta_lista, ['--rodadas-json', self.alvo], self.status_lista,
                 'Carregando a lista de rodadas.'),
                (self.consulta_parecer, ['--contexto-json', self.alvo], self.status_parecer,
                 'Carregando o último parecer.')):
            if consulta.ocupada():
                # O fim da consulta anterior vê o alvo novo e pede outra.
                self.avisar(rotulo, carregando)
                continue
            falha = consulta.iniciar(argumentos, self.alvo)
            self.avisar(rotulo, falha or carregando, falha is not None)
        self.conferir_fim()

    def descartar(self, consulta, alvo, argumentos, rotulo):
        """Resultado de outra sessão ou de antes da troca: some, e a sessão atual é consultada."""
        if self.fechando:
            return True
        if alvo == self.alvo and self.consultado == alvo:
            return False
        if self.alvo is not None and self.consultado == self.alvo:
            falha = consulta.iniciar(argumentos(self.alvo), self.alvo)
            if falha:
                self.avisar(rotulo, falha, True)
        self.conferir_fim()
        return True

    def conferir_fim(self):
        if any(c.ocupada() for c in self.consultas):
            self.atualizar_botao.setEnabled(False)
            return
        self.atualizar_botao.setEnabled(self.janela.real and self.alvo is not None)
        if self.consultado is None or self.consultado != self.alvo:
            return
        falhas = [r.property('falha') for r in (self.status_rodadas, self.status_lista, self.status_parecer)]
        if any(falhas):
            self.avisar(self.status, 'Parte da consulta falhou. Veja os avisos abaixo.', True)
        else:
            self.avisar(self.status, f'Lido do Core para a sessão {self.alvo}. Texto mostrado como dado; '
                        'esta aba não aprova nem executa nada.')

    def indicadores_fim(self, alvo, falha, bruto):
        if self.descartar(self.consulta_indicadores, alvo, lambda _: ['--json'], self.status_rodadas):
            return
        if falha:
            self.avisar(self.status_rodadas, falha, True)
        else:
            try:
                registros = registros_da_sessao(bruto, alvo)
                self.mostrar_rodadas(registros)
            except ValueError as erro:
                self.avisar(self.status_rodadas, str(erro), True)
            except (TypeError, OverflowError):
                self.avisar(self.status_rodadas, 'A saída traz campos em formato inesperado.', True)
        self.conferir_fim()

    def mostrar_rodadas(self, registros):
        if not registros:
            for rotulo in self.valores.values():
                self.valor(rotulo, SEM_DADO)
            self.avisar(self.status_rodadas, 'Os indicadores ainda não têm registro desta sessão.')
            return
        r = registros[-1]
        _, entrada, saida = tokens_da_tarefa(r)
        textos = {'rodadas': inteiro(r.get('rodadas')), 'rodadas_sessao': inteiro(r.get('rodadas_sessao')),
                  'ultimo_resultado': texto(r.get('ultimo_resultado')),
                  'segundos_revisao': tempo(r.get('segundos_revisao')),
                  'tokens': f'{inteiro(entrada)} e {inteiro(saida)}' if entrada is not None or saida is not None
                  else SEM_DADO}
        for chave, valor in textos.items():
            self.valor(self.valores[chave], valor)
        self.avisar(self.status_rodadas, f'{len(registros)} registros desta sessão nos indicadores; '
                    'mostra o último da lista.' if len(registros) > 1 else '')

    def lista_fim(self, alvo, falha, bruto):
        if self.descartar(self.consulta_lista, alvo, lambda nome: ['--rodadas-json', nome], self.status_lista):
            return
        if self.consulta_lista.desconhecida:
            self.avisar(self.status_lista, SEM_LISTA)
        elif falha:
            self.avisar(self.status_lista, falha, True)
        else:
            try:
                self.mostrar_lista(ler_rodadas(bruto, alvo))
            except ValueError as erro:
                self.avisar(self.status_lista, f'Saída inválida. {erro}', True)
            except (TypeError, OverflowError):
                self.tabela.clear()
                self.avisar(self.status_lista, 'Saída inválida. A saída traz campos em formato inesperado.', True)
        self.conferir_fim()

    def mostrar_lista(self, lista):
        itens = [QTreeWidgetItem([limpar(t) for t in linha_rodada(r)]) for r in lista]
        self.tabela.clear()
        self.tabela.addTopLevelItems(itens)
        for coluna in range(len(COLUNAS)):
            self.tabela.resizeColumnToContents(coluna)
        if itens:
            self.tabela.setCurrentItem(itens[-1])
            self.avisar(self.status_lista, f'{len(itens)} ' + ('rodada' if len(itens) == 1 else 'rodadas')
                        + ' desta execução, da mais antiga à mais recente.')
        else:
            self.avisar(self.status_lista, 'Nenhuma rodada registrada para esta sessão.')

    def parecer_fim(self, alvo, falha, bruto):
        if self.descartar(self.consulta_parecer, alvo, lambda nome: ['--contexto-json', nome],
                          self.status_parecer):
            return
        if falha:
            self.avisar(self.status_parecer, falha, True)
        else:
            try:
                parecer = ler_contexto(bruto, alvo)
            except ValueError as erro:
                self.avisar(self.status_parecer, str(erro), True)
            else:
                self.mostrar_parecer(parecer)
        self.conferir_fim()

    def mostrar_parecer(self, parecer):
        if parecer is None:
            self.titulo_parecer.setText('Último parecer')
            self.parecer.setPlainText(SEM_DADO)
            self.avisar(self.status_parecer, 'Nenhum parecer registrado para esta sessão.')
            return
        corpo = limpar(parecer['texto'])
        cortado = len(corpo) > PARECER_MAX
        self.titulo_parecer.setText(f'Último parecer, rodada {parecer["rodada"]}')
        self.parecer.setPlainText(corpo[:PARECER_MAX] or SEM_DADO)
        origem = limpar(parecer['origem'])[:300] or SEM_DADO
        self.avisar(self.status_parecer, f'Arquivo: {origem}.' + (' Texto cortado na tela.' if cortado else ''))

    def fechar(self):
        self.fechando = True
        for consulta in self.consultas:
            consulta.fechar()
