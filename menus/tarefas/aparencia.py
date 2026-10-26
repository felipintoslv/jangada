"""Componentes da identidade visual, com cores derivadas das fichas.

Não dependem da Central: outra janela importa este módulo, aplica
`folha_de_estilo` e monta cabeçalho, faixa de resumo, botões e cartões.
As regras estão em docs/identidade-visual.md.
"""
import html

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor, QPainter, QPixmap
from PyQt6.QtSvg import QSvgRenderer
from PyQt6.QtWidgets import (QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QSizePolicy,
                             QTextBrowser, QVBoxLayout, QWidget)
from visual.fichas import ESTADOS, ICONES, contraste

TIPOS = ('principal', 'secundario', 'perigo')
LADO_MARCA = 40


def misturar(fundo, tinta, proporcao):
    a, b = QColor(fundo), QColor(tinta)
    return QColor(*(round(x * (1 - proporcao) + y * proporcao)
                    for x, y in zip(a.getRgb()[:3], b.getRgb()[:3]))).name()


def tingir(fundo, tinta, texto, proporcao):
    # A ficha valida as superfícies originais; uma mistura também precisa passar.
    for passo in range(round(proporcao * 100), -1, -1):
        cor = misturar(fundo, tinta, passo / 100)
        if contraste(texto, cor) >= 4.5:
            return cor
    return fundo


def contorno(c):
    """Borda de controle: a mistura mais leve de texto suave com 3:1 sobre o fundo."""
    for passo in range(40, 101):
        cor = misturar(c['superficie'], c['texto_suave'], passo / 100)
        if contraste(cor, c['superficie']) >= 3:
            return cor
    return c['texto_suave']


def cores_interacao(c, modo):
    falha = ESTADOS[modo]['Falhou']
    hover = tingir(c['primaria'], c['texto_primario'], c['texto_primario'], .08)
    destrutivo = tingir(c['superficie'], falha, falha, .12)
    destrutivo_hover = tingir(c['superficie'], falha, falha, .18)
    selecionado = tingir(c['superficie'], c['superficie_elevada'], c['primaria'], 1)
    return dict(hover=hover, destrutivo=destrutivo, destrutivo_hover=destrutivo_hover,
                selecionado=selecionado, linha=misturar(c['superficie'], c['texto'], .22),
                contorno=contorno(c),
                borda_falha=f'rgba({QColor(falha).red()}, {QColor(falha).green()}, {QColor(falha).blue()}, 100)',
                pares={'principal': (c['texto_primario'], c['primaria']),
                       'principal_hover': (c['texto_primario'], hover),
                       'destrutivo': (falha, destrutivo),
                       'destrutivo_hover': (falha, destrutivo_hover),
                       'perigo': (falha, c['superficie']),
                       'desabilitado': (c['texto_suave'], c['superficie']),
                       'texto': (c['texto'], c['superficie']),
                       'texto_elevado': (c['texto'], c['superficie_elevada']),
                       'suave': (c['texto_suave'], c['superficie']),
                       'suave_elevado': (c['texto_suave'], c['superficie_elevada']),
                       'aba': (c['primaria'], c['superficie']),
                       'selecionado': (c['primaria'], selecionado),
                       **{f'estado_{nome}': (cor, c['superficie_elevada'])
                          for nome, cor in ESTADOS[modo].items()}})


def folha_de_estilo(c, modo):
    """Folha de estilo comum a qualquer janela do jangada, nos dois modos."""
    i = cores_interacao(c, modo)
    falha = ESTADOS[modo]['Falhou']
    return f"""
        QWidget {{ background: {c['superficie']}; color: {c['texto']};
            font-family: Inter; font-size: 14px; selection-background-color: {c['primaria']};
            selection-color: {c['texto_primario']}; }}
        QLabel {{ background: transparent; }}
        QLabel[papel="marca"] {{ font-size: 13px; color: {c['texto_suave']}; }}
        QLabel[papel="titulo"] {{ font-size: 24px; font-weight: 600; }}
        QLabel[papel="subtitulo"] {{ font-size: 18px; font-weight: 600; }}
        QLabel[papel="secao"] {{ font-weight: 600; }}
        QLabel[papel="suave"], QLabel#motivo_acao {{ color: {c['texto_suave']}; font-size: 13px; }}
        QTreeWidget, QPlainTextEdit, QTextBrowser, QLineEdit, QComboBox {{ background: {c['superficie']};
            border: 1px solid {i['contorno']}; border-radius: 8px; padding: 8px; }}
        QPlainTextEdit {{ font-family: 'JetBrains Mono'; font-size: 13px; }}
        QTreeWidget {{ padding: 0; }}
        QTreeWidget::item {{ padding: 8px 4px; border-bottom: 1px solid {i['linha']}; }}
        QTreeWidget::item:hover {{ background: {c['superficie_elevada']}; }}
        QTreeWidget::item:selected {{ background: {i['selecionado']}; color: {c['primaria']}; }}
        QTreeWidget::item:selected:first {{ border-left: 3px solid {c['primaria']}; }}
        QHeaderView::section {{ background: {c['superficie_elevada']}; color: {c['texto_suave']};
            font-size: 13px; padding: 8px; border: none; border-bottom: 1px solid {i['linha']}; }}
        QTabWidget::pane {{ border: none; border-top: 1px solid {i['linha']}; }}
        QTabBar::tab {{ background: {c['superficie']}; color: {c['texto_suave']};
            border: none; border-bottom: 2px solid transparent; padding: 8px 12px; }}
        QTabBar::tab:selected {{ color: {c['primaria']}; border-bottom: 2px solid {c['primaria']}; font-weight: 600; }}
        QTabBar::tab:focus {{ border: 1px dashed {c['primaria']}; border-bottom: 2px solid {c['primaria']}; }}
        QScrollBar:vertical {{ background: {c['superficie']}; width: 8px; margin: 0; }}
        QScrollBar:horizontal {{ background: {c['superficie']}; height: 8px; margin: 0; }}
        QScrollBar::handle {{ background: {c['texto_suave']}; border-radius: 4px; min-height: 24px; min-width: 24px; }}
        QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
        QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
        QPushButton {{ background: {c['superficie_elevada']}; border: 1px solid {i['contorno']};
            border-radius: 8px; padding: 8px 12px; }}
        QPushButton:hover {{ border: 1px solid {c['texto_suave']}; }}
        QPushButton:focus, QComboBox:focus, QLineEdit:focus, QTreeWidget:focus,
        QPlainTextEdit:focus {{ border: 2px solid {c['primaria']}; }}
        QPushButton:disabled {{ color: {c['texto_suave']}; background: {c['superficie']};
            border: 1px dashed {i['contorno']}; }}
        QPushButton[tipo="principal"]:enabled {{ background: {c['primaria']}; color: {c['texto_primario']};
            border: 1px solid {c['primaria']}; font-weight: 600; }}
        QPushButton[tipo="principal"]:enabled:hover {{ background: {i['hover']}; }}
        QPushButton[tipo="principal"]:enabled:focus {{ border: 2px dashed {c['texto_primario']}; }}
        QPushButton[tipo="perigo"]:enabled {{ background: {c['superficie']}; color: {falha};
            border: 1px solid {i['borda_falha']}; }}
        QPushButton[tipo="perigo"]:enabled:hover {{ background: {i['destrutivo_hover']}; }}
        QPushButton[tipo="perigo"]:enabled:focus {{ border: 2px solid {c['primaria']}; }}
        QFrame#cartao_quadro {{ background: {c['superficie']}; border: 1px solid {i['linha']}; border-radius: 8px; }}
        QFrame#cartao_quadro[cheio="true"] {{ background: {c['superficie_elevada']}; border: none; }}
        QFrame#separador {{ background: {i['linha']}; border: none; max-height: 1px; min-height: 1px; }}
        QFrame#faixa_resumo {{ background: {c['superficie_elevada']}; border: 1px solid {i['linha']};
            border-radius: 8px; }}
        QPushButton#resumo_estado {{ background: transparent; text-align: left; padding: 0; border: none;
            border-left: 1px solid {i['linha']}; border-radius: 0; }}
        QPushButton#resumo_estado[primeiro="true"] {{ border-left: none; border-top-left-radius: 8px;
            border-bottom-left-radius: 8px; }}
        QPushButton#resumo_estado:hover {{ background: {c['superficie']}; }}
        QPushButton#resumo_estado:checked {{ background: {c['primaria']}; }}
        QPushButton#resumo_estado:focus {{ border: 2px dashed {c['primaria']}; }}
        QPushButton#resumo_estado:checked:focus {{ border: 2px dashed {c['texto_primario']}; }}
        QPushButton#resumo_estado QLabel {{ background: transparent; border: none; padding: 0; }}
        QPushButton#resumo_estado QLabel[marcado="true"] {{ color: {c['texto_primario']}; }}
        QPushButton#resumo_estado QLabel#resumo_numero {{ font-size: 20px; font-weight: 500; }}
        QPushButton#resumo_estado QLabel#resumo_simbolo {{ font-weight: 600; }}
        QLabel#rotulo_estado {{ font-size: 13px; font-weight: 500; }}
    """


def marca(svg, cor, lado=LADO_MARCA):
    """Logo simbólica recolorida; None quando o SVG ou a imagem falham."""
    renderer = QSvgRenderer(svg.replace(b'#000000', cor.encode()))
    imagem = QPixmap(lado, lado)
    if imagem.isNull() or not renderer.isValid():
        return None
    imagem.fill(Qt.GlobalColor.transparent)
    pincel = QPainter(imagem)
    renderer.render(pincel)
    pincel.end()
    return imagem


def definir_tipo(botao, tipo):
    """Principal, secundário ou perigo; indisponível é o botão desligado, em qualquer tipo."""
    if tipo not in TIPOS:
        raise ValueError(f'tipo de botão desconhecido: {tipo}')
    if botao.property('tipo') != tipo:
        botao.setProperty('tipo', tipo)
        botao.style().unpolish(botao)
        botao.style().polish(botao)
    return botao


def botao(texto, tipo='secundario'):
    return definir_tipo(QPushButton(texto), tipo)


class BotaoComMotivo(QWidget):
    """Botão com o motivo ao lado quando está indisponível."""
    def __init__(self, botao):
        super().__init__()
        self.botao = botao
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(botao, 1)
        self.motivo = QLabel()
        self.motivo.setObjectName('motivo_acao')
        self.motivo.setTextFormat(Qt.TextFormat.PlainText)
        self.motivo.setWordWrap(True)
        self.motivo.hide()
        layout.addWidget(self.motivo, 1)

    def explicar(self, motivo):
        self.motivo.setText(motivo)
        self.motivo.setVisible(bool(motivo))
        self.botao.setAccessibleDescription(motivo)

    def indisponivel(self, motivo):
        self.botao.setEnabled(False)
        self.explicar(motivo)

    def disponivel(self):
        self.botao.setEnabled(True)
        self.explicar('')


class Cartao(QFrame):
    """Moldura de 8 px de raio; cheia usa a superfície elevada sem borda."""
    def __init__(self, cheio=False):
        super().__init__()
        self.setObjectName('cartao_quadro')
        self.setProperty('cheio', cheio)


def separador():
    linha = QFrame()
    linha.setObjectName('separador')
    linha.setFrameShape(QFrame.Shape.NoFrame)
    return linha


def texto_estado(rotulo, ficha):
    return f'{ICONES[ficha]} {rotulo}' if ficha in ICONES else rotulo


def cor_estado(ficha, c, modo):
    """Planejada e Cancelada usam texto suave e Pronta usa texto; os demais têm cor fixa."""
    return ESTADOS[modo].get(ficha) or (c['texto'] if ficha == 'Pronta' else c['texto_suave'])


class RotuloEstado(QLabel):
    """Estado com símbolo, rótulo e cor; a cor nunca vai sozinha."""
    def __init__(self):
        super().__init__()
        self.setObjectName('rotulo_estado')
        self.setTextFormat(Qt.TextFormat.PlainText)

    def mostrar(self, rotulo, ficha, c, modo):
        self.setText(texto_estado(rotulo, ficha))
        self.setStyleSheet(f'color: {cor_estado(ficha, c, modo)};')


class Cabecalho(QWidget):
    """Logo, "Jangada" pequeno e o título da janela; comandos entram em `linha`."""
    def __init__(self, titulo, svg):
        super().__init__()
        self.svg = svg
        self.linha = QHBoxLayout(self)
        self.linha.setContentsMargins(0, 0, 0, 0)
        self.linha.setSpacing(12)
        self.marca = QLabel()
        self.marca.setAccessibleName('Jangada')
        self.marca.setFixedSize(LADO_MARCA, LADO_MARCA)
        self.linha.addWidget(self.marca)
        textos = QVBoxLayout()
        textos.setSpacing(0)
        self.nome = QLabel('Jangada')
        self.nome.setProperty('papel', 'marca')
        self.titulo = QLabel(titulo)
        self.titulo.setProperty('papel', 'titulo')
        self.titulo.setWordWrap(True)
        textos.addWidget(self.nome)
        textos.addWidget(self.titulo)
        self.linha.addLayout(textos)
        self.linha.addStretch()

    def compactar(self, estreito):
        """Em janela estreita, o nome pequeno sai e o título fica; a logo continua."""
        self.nome.setVisible(not estreito)

    def pintar(self, c):
        """Recolore a logo com a primária; sem SVG, some a logo e fica o título."""
        try:
            imagem = marca(self.svg.read_bytes(), c['primaria'])
        except OSError:
            imagem = None
        if imagem is None:
            self.marca.setAccessibleName('')
            self.marca.hide()
        else:
            self.marca.setPixmap(imagem)
            self.marca.setAccessibleName('Jangada')
            self.marca.show()
        return imagem


class CartaoResumo(QPushButton):
    def __init__(self, titulo, simbolo=''):
        super().__init__()
        self.setObjectName('resumo_estado')
        self.setCheckable(True)
        self.setMinimumHeight(72)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 8, 16, 8)
        layout.setSpacing(8)
        self.numero = QLabel('0')
        self.numero.setObjectName('resumo_numero')
        self.simbolo = QLabel(simbolo)
        self.simbolo.setObjectName('resumo_simbolo')
        self.titulo = QLabel(titulo)
        self.titulo.setWordWrap(True)
        self.cor = None
        for rotulo in (self.numero, self.simbolo, self.titulo):
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(rotulo)
        layout.setStretch(2, 1)
        self.simbolo.setVisible(bool(simbolo))
        self.toggled.connect(self.tingir)

    def contar(self, total):
        self.numero.setText(str(total))
        self.setAccessibleName(f'{self.titulo.text()}: {total}. Filtrar sessões')

    def pintar(self, cor):
        self.cor = cor
        self.tingir()

    def tingir(self, *_):
        # A folha não aplica `:checked` do botão aos rótulos filhos; a propriedade faz esse papel.
        # Marcado, o símbolo fica no texto primário: a cor de estado não passa sobre a primária.
        for rotulo in (self.numero, self.simbolo, self.titulo):
            rotulo.setProperty('marcado', self.isChecked())
            rotulo.style().unpolish(rotulo)
            rotulo.style().polish(rotulo)
        self.simbolo.setStyleSheet('' if self.isChecked() or not self.cor else f'color: {self.cor};')


class FaixaResumo(QFrame):
    """Faixa única com contadores; cada um filtra e um segundo clique desfaz."""
    def __init__(self):
        super().__init__()
        self.setObjectName('faixa_resumo')
        self.cartoes = {}
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def adicionar(self, chave, titulo, simbolo=''):
        cartao = CartaoResumo(titulo, simbolo)
        cartao.setProperty('primeiro', not self.cartoes)
        self.layout().addWidget(cartao, 1)
        self.cartoes[chave] = cartao
        return cartao


class LinhaTempo(QTextBrowser):
    def __init__(self):
        super().__init__()
        self.setObjectName('linha_tempo')
        self.setOpenLinks(False)
        self.setAccessibleName('Mudanças acompanhadas nesta janela')

    def clear(self):
        super().clear()
        self.setProperty('conteudo', None)

    def mostrar(self, entradas, c):
        linhas = []
        for entrada in entradas:
            hora, separador, mensagem = entrada.partition(' · ')
            if not separador:
                mensagem, hora = hora, ''
            linhas.append(
                f'<tr><td bgcolor="{c["primaria"]}" width="2"></td><td width="10"></td>'
                f'<td><span style="color:{c["texto_suave"]}">{html.escape(hora)}</span><br>'
                f'{html.escape(mensagem).replace(chr(10), "<br>")}<br><br></td></tr>')
        conteudo = '<table cellspacing="0" cellpadding="0" width="100%">' + ''.join(linhas) + '</table>'
        if self.property('conteudo') != conteudo:
            self.setHtml(conteudo)
            self.setProperty('conteudo', conteudo)
            self.verticalScrollBar().setValue(self.verticalScrollBar().maximum())


class InspetorRolavel(QScrollArea):
    """Mantém ações visíveis no desktop e permite percorrê-las na janela baixa."""
    def setWidget(self, widget):
        super().setWidget(widget)
        for controle in widget.findChildren(QWidget):
            controle.installEventFilter(self)

    def eventFilter(self, objeto, evento):
        if evento.type() == QEvent.Type.FocusIn and isinstance(objeto, QWidget):
            self.ensureWidgetVisible(objeto, 0, 12)
        return super().eventFilter(objeto, evento)

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        if self.widget():
            altura = self.viewport().height()
            self.widget().resize(self.viewport().width(), max(altura, 600 if altura < 400 else 0))
