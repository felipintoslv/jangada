"""Componentes da Central e cores de interação derivadas das fichas."""
import html

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QLabel, QPushButton, QScrollArea, QTextBrowser, QVBoxLayout, QWidget
from visual.fichas import ESTADOS, contraste


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


def cores_interacao(c, modo):
    falha = ESTADOS[modo]['Falhou']
    hover = tingir(c['primaria'], c['texto_primario'], c['texto_primario'], .08)
    destrutivo = tingir(c['superficie'], falha, falha, .12)
    destrutivo_hover = tingir(c['superficie'], falha, falha, .18)
    return dict(hover=hover, destrutivo=destrutivo, destrutivo_hover=destrutivo_hover,
                borda_falha=f'rgba({QColor(falha).red()}, {QColor(falha).green()}, {QColor(falha).blue()}, 100)',
                pares={'principal': (c['texto_primario'], c['primaria']),
                       'principal_hover': (c['texto_primario'], hover),
                       'destrutivo': (falha, destrutivo),
                       'destrutivo_hover': (falha, destrutivo_hover),
                       'desabilitado': (c['texto_suave'], c['superficie_elevada']),
                       'texto': (c['texto'], c['superficie']),
                       'texto_elevado': (c['texto'], c['superficie_elevada']),
                       'suave': (c['texto_suave'], c['superficie']),
                       'suave_elevado': (c['texto_suave'], c['superficie_elevada']),
                       'aba': (c['primaria'], c['superficie']),
                       **{f'estado_{nome}': (cor, c['superficie_elevada'])
                          for nome, cor in ESTADOS[modo].items()}})


class CartaoResumo(QPushButton):
    def __init__(self, titulo):
        super().__init__()
        self.setObjectName('resumo_estado')
        self.setCheckable(True)
        self.setMinimumHeight(72)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 6, 12, 6)
        layout.setSpacing(2)
        self.numero = QLabel('0')
        self.numero.setObjectName('resumo_numero')
        self.titulo = QLabel(titulo)
        self.titulo.setWordWrap(True)
        for rotulo in (self.numero, self.titulo):
            rotulo.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
            layout.addWidget(rotulo)

    def contar(self, total):
        self.numero.setText(str(total))
        self.setAccessibleName(f'{self.titulo.text()}: {total}. Filtrar sessões')


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
