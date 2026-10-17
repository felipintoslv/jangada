"""Indicadores: lê jangada-indicadores --json e mostra, sem calcular sobre os registros."""
import json
import re
import statistics

from PyQt6.QtCore import QProcess, QSize, QTimer, Qt
from PyQt6.QtWidgets import (QButtonGroup, QHBoxLayout, QLabel, QPushButton, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)
from dados import LIMITE, comando_disponivel

COMANDO = 'jangada-indicadores'
SEM_DADO = 'sem dado'
CONTROLE = re.compile('[\x00-\x1f\x7f-\x9f‎‏‪-‮⁦-⁩]')
LISTAS = ('tarefas', 'revisores', 'local_vs_agy')
ORIGENS = {'sessao': 'registro do agente', 'protegida': 'registro protegido'}
COLUNAS = {
    'tarefas': ['Sessão', 'Autor', 'Modelo', 'Tokens de entrada', 'Tokens de saída', 'Cache lido',
                'Rodadas protegidas', 'Rodadas do agente', 'Último resultado', 'Tempo de revisão',
                'Delegações', 'Motivo sem consumo'],
    'revisores': ['Revisor', 'Modelo', 'Registro', 'Pareceres', 'Apontamentos', 'Procedentes',
                  'Rejeitados', 'Sem classificação', 'Taxa de procedência'],
    'local_vs_agy': ['Papel', 'Destino', 'Registro', 'Chamadas', 'Sucesso', 'Recusas',
                     'Tempo mediano', 'Tokens de entrada', 'Tokens de saída', 'Mudanças do local'],
}
TITULOS = {'tarefas': 'Custo por tarefa', 'revisores': 'Acerto dos revisores',
           'local_vs_agy': 'Local e agy'}


def texto(valor, limite=200):
    if not isinstance(valor, str) or not valor:
        return SEM_DADO
    limpo = CONTROLE.sub('', valor)[:limite]
    return limpo or SEM_DADO


def numero(valor):
    return valor if isinstance(valor, (int, float)) and not isinstance(valor, bool) and valor >= 0 else None


def inteiro(valor):
    n = numero(valor)
    return SEM_DADO if n is None else f'{round(n):,}'.replace(',', '.')


def porcentagem(fracao, casos=None):
    n = numero(fracao)
    if n is None or n > 1:
        return SEM_DADO
    rotulo = f'{round(n * 100)}%'
    if casos is not None:
        rotulo += f' ({inteiro(casos)} ' + ('caso)' if casos == 1 else 'casos)')
    return rotulo


def tempo(segundos):
    s = numero(segundos)
    if s is None:
        return SEM_DADO
    if s < 60:
        return f'{s:.1f} s'.replace('.', ',') if s < 10 and s != int(s) else f'{round(s)} s'
    minutos, resto = divmod(round(s), 60)
    if minutos < 60:
        return f'{minutos} min' + (f' {resto} s' if resto else '')
    horas, minutos = divmod(minutos, 60)
    return f'{horas} h' + (f' {minutos} min' if minutos else '')


def origem(valor):
    return ORIGENS.get(valor, SEM_DADO)


def ler(bruto):
    """Valida o contrato da versão 1; devolve as três listas de objetos."""
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
    for campo in LISTAS:
        lista = dados.get(campo)
        if not isinstance(lista, list) or len(lista) > 4096 or any(not isinstance(r, dict) for r in lista):
            raise ValueError('A saída não traz as listas esperadas.')
    return {campo: dados[campo] for campo in LISTAS}


def tokens_da_tarefa(tarefa):
    t = tarefa.get('tokens') if isinstance(tarefa.get('tokens'), dict) else {}
    return t, numero(t.get('entrada')), numero(t.get('saida'))


def linhas(campo, lista):
    if campo == 'tarefas':
        resultado = []
        for r in lista:
            t, entrada, saida = tokens_da_tarefa(r)
            delegacoes = r.get('delegacoes')
            resultado.append([texto(r.get('sessao')), texto(r.get('autor')), texto(t.get('modelo')),
                              inteiro(entrada), inteiro(saida), inteiro(t.get('cache_lido')),
                              inteiro(r.get('rodadas')), inteiro(r.get('rodadas_sessao')),
                              texto(r.get('ultimo_resultado')), tempo(r.get('segundos_revisao')),
                              inteiro(len(delegacoes)) if isinstance(delegacoes, list) else SEM_DADO,
                              texto(t.get('motivo')) if entrada is None or saida is None else ''])
        return resultado
    if campo == 'revisores':
        return [[texto(r.get('revisor')), texto(r.get('modelo')), origem(r.get('origem')),
                 inteiro(r.get('pareceres')), inteiro(r.get('apontamentos')), inteiro(r.get('procedentes')),
                 inteiro(r.get('rejeitados')), inteiro(r.get('sem_classificacao')),
                 porcentagem(r.get('taxa_procedencia'), numero(r.get('casos_taxa')))] for r in lista]
    return [[texto(r.get('papel')), texto(r.get('destino')), origem(r.get('origem')),
             inteiro(r.get('chamadas')), inteiro(r.get('sucesso')), inteiro(r.get('recusas')),
             tempo(r.get('segundos_medianos')), inteiro(r.get('tokens_entrada')),
             inteiro(r.get('tokens_saida')), inteiro(r.get('mudancas_local'))] for r in lista]


def resumo(campo, lista):
    """Número em destaque, linha de apoio e rodapé do cartão."""
    if not lista:
        return SEM_DADO, 'Ainda não há dados.', '0 casos'
    if campo == 'tarefas':
        medidas = [e + s for _, e, s in map(tokens_da_tarefa, lista) if e is not None and s is not None]
        destaque = inteiro(statistics.median(medidas)) + ' tokens' if medidas else SEM_DADO
        apoio = 'mediana de entrada e saída por tarefa' if medidas else 'consumo ainda não medido'
        return destaque, apoio, f'{len(medidas)} de {len(lista)} tarefas com consumo medido'
    if campo == 'revisores':
        classificados = [r for r in lista if numero(r.get('taxa_procedencia')) is not None
                         and numero(r.get('casos_taxa'))]
        casos = sum(numero(r.get('casos_taxa')) or 0 for r in lista)
        rodape = f'{inteiro(casos)} apontamentos classificados em {len(lista)} grupos'
        if not classificados:
            return SEM_DADO, 'nenhum apontamento classificado', rodape
        maior = max(classificados, key=lambda r: (r['taxa_procedencia'], r['casos_taxa']))
        apoio = (f'maior taxa: {texto(maior.get("revisor"))}, {texto(maior.get("modelo"))}, '
                 f'{origem(maior.get("origem"))}, {inteiro(maior["casos_taxa"])} casos')
        return porcentagem(maior['taxa_procedencia']), apoio, rodape
    soma = {}
    for r in lista:
        if r.get('destino') in ('local', 'agy'):
            g = soma.setdefault(r['destino'], [0, 0, 0])
            for i, chave in enumerate(('chamadas', 'sucesso', 'recusas')):
                g[i] += numero(r.get(chave)) or 0
    partes = []
    for destino in ('local', 'agy'):
        chamadas, sucesso, _ = soma.get(destino, (0, 0, 0))
        partes.append(f'{destino} ' + (porcentagem(sucesso / chamadas) if chamadas else SEM_DADO))
    recusas = ', '.join(f'{d} {inteiro(soma.get(d, (0, 0, 0))[2])}' for d in ('local', 'agy'))
    rodape = ', '.join(f'{inteiro(soma.get(d, (0, 0, 0))[0])} chamadas no {d}' for d in ('local', 'agy'))
    return ' · '.join(partes), f'sucesso por chamada; recusas: {recusas}', rodape


class Cartao(QPushButton):
    """Botão checável com rótulos; o tamanho segue o conteúdo, não o texto do botão."""

    def __init__(self, titulo):
        super().__init__()
        self.setObjectName('cartao')
        self.setCheckable(True)
        self.titulo = titulo
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(4)
        self.rotulos = {}
        for nome in ('titulo', 'numero', 'apoio', 'rodape'):
            rotulo = QLabel()
            rotulo.setObjectName('cartao_' + nome)
            rotulo.setTextFormat(Qt.TextFormat.PlainText)
            rotulo.setWordWrap(nome in ('apoio', 'rodape'))
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(rotulo)
            self.rotulos[nome] = rotulo
        self.rotulos['titulo'].setText(titulo)
        self.mostrar(SEM_DADO, '', '')

    def mostrar(self, destaque, apoio, rodape):
        for nome, valor in (('numero', destaque), ('apoio', apoio), ('rodape', rodape)):
            self.rotulos[nome].setText(valor)
        self.setAccessibleName(self.titulo)
        self.setAccessibleDescription('. '.join(v for v in (destaque, apoio, rodape) if v))
        self.updateGeometry()

    def sizeHint(self):
        dica = self.layout().sizeHint()
        return QSize(max(dica.width(), 220), dica.height())

    def minimumSizeHint(self):
        return QSize(160, self.layout().minimumSize().height())


class Indicadores(QWidget):
    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.dados = None
        self.fechando = False
        self.prazo_ms = 15000
        layout = QVBoxLayout(self)
        linha = QHBoxLayout()
        self.grupo = QButtonGroup(self)
        self.grupo.setExclusive(True)
        self.cartoes = {}
        for campo in LISTAS:
            cartao = Cartao(TITULOS[campo])
            cartao.toggled.connect(lambda marcado, c=campo: marcado and self.escolher(c))
            self.grupo.addButton(cartao)
            self.cartoes[campo] = cartao
            linha.addWidget(cartao, 1)
        layout.addLayout(linha)
        acoes = QHBoxLayout()
        self.atualizar_botao = QPushButton('Atualizar')
        self.atualizar_botao.clicked.connect(self.atualizar)
        acoes.addWidget(self.atualizar_botao)
        self.status = QLabel()
        self.status.setObjectName('indicadores_status')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        acoes.addWidget(self.status, 1)
        layout.addLayout(acoes)
        self.detalhe = QLabel()
        self.detalhe.setObjectName('indicadores_detalhe')
        self.detalhe.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.detalhe)
        self.tabela = QTreeWidget()
        self.tabela.setRootIsDecorated(False)
        self.tabela.setAllColumnsShowFocus(True)
        layout.addWidget(self.tabela, 1)
        self.vazio = QLabel()
        self.vazio.setTextFormat(Qt.TextFormat.PlainText)
        self.vazio.setWordWrap(True)
        self.vazio.hide()
        layout.addWidget(self.vazio)
        ordem = [*self.cartoes.values(), self.atualizar_botao, self.tabela]
        for antes, depois in zip(ordem, ordem[1:]):
            QWidget.setTabOrder(antes, depois)
        self.consulta = QProcess(self)
        self.consulta.finished.connect(self.consulta_fim)
        self.consulta.errorOccurred.connect(self.consulta_erro)
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.expirar)
        self.expirou = False
        self.cartoes['tarefas'].setChecked(True)
        if not janela.real:
            self.atualizar_botao.setEnabled(False)
            self.avisar('Simulação: os indicadores não são consultados.')

    def avisar(self, mensagem, falha=False):
        self.status.setText(mensagem)
        if self.status.property('falha') != falha:
            self.status.setProperty('falha', falha)
            self.status.style().unpolish(self.status)
            self.status.style().polish(self.status)

    def atualizar(self):
        if self.fechando or not self.janela.real or self.consulta.state() != QProcess.ProcessState.NotRunning:
            return
        if not comando_disponivel(COMANDO, self.janela.jangada):
            self.falhar(f'Comando {COMANDO} não encontrado. Instale ou atualize o jangada-core, que traz esse comando.')
            return
        self.expirou = False
        self.janela.preparar(self.consulta, ['--json'], COMANDO)
        self.avisar('Carregando os indicadores.')
        self.consulta.start()
        self.prazo.start(self.prazo_ms)

    def falhar(self, mensagem):
        if self.dados is not None:
            mensagem += ' A tela mostra a leitura anterior.'
        self.avisar(mensagem, falha=True)

    def expirar(self):
        self.expirou = True
        self.consulta.kill()

    def consulta_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo.stop()
            self.falhar(f'Não foi possível executar {COMANDO}.')

    def consulta_fim(self, codigo, tipo):
        self.prazo.stop()
        bruto = bytes(self.consulta.readAllStandardOutput())
        self.consulta.readAllStandardError()
        if self.fechando:
            return
        if self.expirou:
            self.falhar(f'Tempo esgotado ao consultar {COMANDO}.')
            return
        if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.falhar(f'{COMANDO} terminou com erro.')
            return
        try:
            dados = ler(bruto)
        except ValueError as erro:
            self.falhar(str(erro))
            return
        self.mostrar(dados)

    def mostrar(self, dados):
        self.dados = dados
        for campo, cartao in self.cartoes.items():
            cartao.mostrar(*resumo(campo, dados[campo]))
        if any(dados.values()):
            self.avisar('Indicadores lidos de jangada-indicadores. Clique num cartão ou use as setas para trocar o detalhe.')
        else:
            self.avisar('Ainda não há dados de indicadores. Eles aparecem depois das primeiras tarefas registradas.')
        self.escolher(self.escolhido())

    def escolhido(self):
        return next(c for c, cartao in self.cartoes.items() if cartao.isChecked())

    def escolher(self, campo):
        self.detalhe.setText('Detalhe: ' + TITULOS[campo])
        self.tabela.clear()
        self.tabela.setHeaderLabels(COLUNAS[campo])
        lista = self.dados[campo] if self.dados else []
        self.tabela.addTopLevelItems([QTreeWidgetItem(linha) for linha in linhas(campo, lista)])
        for coluna in range(self.tabela.columnCount()):
            self.tabela.resizeColumnToContents(coluna)
        vazio = self.dados is not None and not lista
        self.vazio.setText('Ainda não há dados para esta pergunta.' if vazio else '')
        self.vazio.setVisible(vazio)

    def fechar(self):
        self.fechando = True
        self.prazo.stop()
        if self.consulta.state() != QProcess.ProcessState.NotRunning:
            self.consulta.kill()
            self.consulta.waitForFinished(1000)
