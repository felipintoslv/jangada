"""Cotas dos provedores: leitura do cotas.json versão 1 do Core e consulta em segundo plano.

`jangada-router cotas` só lê o que o Core já tem em disco. A Central nunca roda
`--atualizar` nem `--permitir-remoto`: quem renova a medição é o dono, no terminal.
Todo número vem do JSON e passa por `numero_de_fora`; nada é estimado.
"""
from dataclasses import dataclass
from datetime import datetime
import html
import json
import math
import re

from PyQt6.QtCore import QObject, QProcess, QRect, QTimer, Qt
from PyQt6.QtWidgets import QLabel
from dados import LIMITE, NOME, comando_disponivel
from visual.fichas import ICONES

ROTEADOR = 'jangada-router'
ATUALIZAR_COTA = 'Para atualizar, rode no terminal: jangada-router cotas --atualizar --permitir-remoto'
GRUPO_ARGON = 'gemini-argon-wtu'
COTA_MINIMA = 20
PRAZO_MS = 30000
INTERVALO_MS = 60000
SIMULACAO = 'a simulação não consulta o Core'
IDENTIFICADOR = re.compile(r'[a-z0-9_-]{1,64}')
# Acima deste número de provedores, a faixa pula as formas resumidas por provedor.
PROVEDORES_EXIBIDOS = 12
NOMES_GRUPO = {GRUPO_ARGON: 'Argon', 'gemini': 'Gemini'}
MOTIVOS = {'sem_cache': 'sem cache', 'cache_vencido': 'cache vencido',
           'consulta_falhou': 'consulta falhou', 'conta_sem_confianca': 'conta sem confiança'}
NAO_MEDIDO = 'nao_medido_por_este_provedor'
ALERTA = ICONES['Bloqueada']


@dataclass(frozen=True)
class Grupo:
    grupo: str
    percentual: float | int | None
    renova_em: str | None = None
    motivo: str | None = None
    ultimo: tuple | None = None  # (percentual, medido_em) da última medida, já vencida; só informa


@dataclass(frozen=True)
class Entrada:
    provedor: str
    conta: str | None
    motivo: str | None
    grupos: tuple


@dataclass(frozen=True)
class Cotas:
    gerado: str | None
    entradas: tuple


def numero_de_fora(valor, minimo=0, maximo=100):
    """Número de um JSON de fora dentro de [minimo, maximo], ou None; nunca lança.

    Só int e float entram (bool não). O intervalo é conferido antes de qualquer
    conversão: um inteiro de 400 dígitos não cabe num float.
    """
    try:
        if type(valor) not in (int, float) or not minimo <= valor <= maximo:
            return None
        return valor if math.isfinite(valor) else None
    except Exception:
        return None


def texto_percentual(valor):
    return f'{abs(valor):.2f}'.rstrip('0').rstrip('.').replace('.', ',')


def instante(valor):
    """Data ISO com fuso de um JSON de fora, ou None; nunca lança."""
    if not isinstance(valor, str) or len(valor) > 64:
        return None
    try:
        quando = datetime.fromisoformat(valor)
        if quando.tzinfo is None:
            return None
        quando.astimezone()
        return quando
    except (ValueError, OverflowError, OSError):
        return None


def hora_curta(valor, com_data=True):
    """Horário local curto ('25/10 03:00', ou '03:00' sem a data), ou None."""
    quando = instante(valor)
    if quando is None:
        return None
    try:
        return quando.astimezone().strftime('%d/%m %H:%M' if com_data else '%H:%M')
    except (OverflowError, OSError, ValueError):
        return None


def hora_antiga(valor):
    """'às 16:27' (hoje) ou '24/10 às 16:27' no horário local, ou None; nunca lança."""
    quando = instante(valor)
    if quando is None:
        return None
    try:
        local = quando.astimezone()
        hoje = datetime.now().astimezone().date()
        return f'{"" if local.date() == hoje else local.strftime("%d/%m ")}às {local:%H:%M}'
    except (OverflowError, OSError, ValueError):
        return None


def _ultimo(valor):
    """(percentual, medido_em) do campo `ultimo` do Core, ou None se faltar algo ou não for válido."""
    if not isinstance(valor, dict):
        return None
    percentual = numero_de_fora(valor.get('percentual'))
    medido = valor.get('medido_em')
    if percentual is None or hora_antiga(medido) is None:
        return None
    return percentual, medido


def _identificador(valor):
    return valor if isinstance(valor, str) and IDENTIFICADOR.fullmatch(valor) else None


def _grupo(g):
    if not isinstance(g, dict):
        return None
    nome = _identificador(g.get('grupo'))
    if nome is None:
        return None
    percentual = numero_de_fora(g.get('percentual'))
    renova = None
    janelas = g.get('janelas')
    if percentual is not None and isinstance(janelas, list):
        for janela in janelas:
            if (isinstance(janela, dict) and numero_de_fora(janela.get('percentual')) == percentual
                    and instante(janela.get('renova_em')) is not None):
                renova = janela['renova_em']
                break
    ultimo = _ultimo(g.get('ultimo')) if percentual is None else None
    return Grupo(nome, percentual, renova, _identificador(g.get('motivo')), ultimo)


def _entrada(e):
    if not isinstance(e, dict):
        return None
    provedor = _identificador(e.get('provedor'))
    if provedor is None:
        return None
    conta = e.get('conta')
    grupos = e.get('grupos')
    grupos = tuple(g for g in map(_grupo, grupos) if g is not None) if isinstance(grupos, list) else ()
    return Entrada(provedor, conta if isinstance(conta, str) and NOME.fullmatch(conta) and len(conta) <= 40 else None,
                   _identificador(e.get('motivo')), grupos)


def ler_cotas(bruto):
    """Lê o JSON de `jangada-router cotas`, versão 1; lança ValueError com o motivo curto."""
    if len(bruto) > LIMITE:
        raise ValueError('saída grande demais')

    def recusar(constante):
        raise ValueError('Número fora do JSON.')
    try:
        dados = json.loads(bruto, parse_constant=recusar)
    except (ValueError, RecursionError) as erro:
        raise ValueError('saída não é JSON válido') from erro
    if not isinstance(dados, dict) or dados.get('versao') != 1 or type(dados.get('versao')) is not int:
        raise ValueError('versão do cotas.json não lida')
    lista = dados.get('provedores')
    if not isinstance(lista, list):
        raise ValueError('saída sem a lista de provedores')
    gerado = dados.get('gerado')
    return Cotas(gerado if instante(gerado) is not None else None,
                 tuple(e for e in map(_entrada, lista) if e is not None))


def cota_argon(cotas):
    """(percentual, renova_em) do Argon ou (None, None).

    A conta `principal` é a do coordenador: se existe, só ela vale, e sem o grupo
    Argon nela o resultado é sem dado. Sem `principal`, vale a única conta do
    agy; com mais de uma, sem dado.
    """
    agy = [e for e in cotas.entradas if e.provedor == 'agy']
    principal = [e for e in agy if e.conta == 'principal']
    if principal:
        entrada = principal[0]
    elif len(agy) == 1:
        entrada = agy[0]
    else:
        return None, None
    grupo = next((g for g in entrada.grupos if g.grupo == GRUPO_ARGON), None)
    if grupo is None or grupo.percentual is None:
        return None, None
    return grupo.percentual, grupo.renova_em


def ler_cota_argon(bruto):
    """Lê o JSON de `jangada-router cotas`; devolve (percentual, renova_em) do Argon ou (None, None)."""
    return cota_argon(ler_cotas(bruto))


# Texto da faixa --------------------------------------------------------------
# Uma peça é (texto, alerta). A cor do alerta nunca vai sem o glifo e o texto.

def nome_do_provedor(e):
    base = e.provedor if e.provedor == 'agy' else e.provedor.capitalize()
    return f'{base} {e.conta}' if e.conta else base


def _sem_dado(motivo):
    legivel = MOTIVOS.get(motivo)
    return 'sem dado' + (f' ({legivel})' if legivel else '')


def _grupo_pecas(g, rotulo, renova):
    nome = f'{rotulo} ' if rotulo else ''
    if g.percentual is None:
        if g.ultimo:
            return [(f'{nome}{texto_percentual(g.ultimo[0])}% ({hora_antiga(g.ultimo[1])})', False)]
        return [(nome + _sem_dado(g.motivo), False)]
    pecas = [(f'{nome}{texto_percentual(g.percentual)}%', False)]
    if g.percentual < COTA_MINIMA:
        pecas += _alerta()
    if renova:
        pecas.append((f' (renova {renova})', False))
    return pecas


def _juntar(listas, separador):
    pecas = []
    for i, lista in enumerate(listas):
        if i:
            pecas.append((separador, False))
        pecas += lista
    return pecas


def _entrada_pecas(e, resumo):
    nome = nome_do_provedor(e)
    if not e.grupos:
        texto = 'não medido aqui' if e.motivo == NAO_MEDIDO else _sem_dado(e.motivo)
        return [(f'{nome}: {texto}', False)]
    medidos = [g for g in e.grupos if g.percentual is not None]
    menor = min(medidos, key=lambda g: g.percentual) if medidos else None
    antigos = [g for g in e.grupos if g.ultimo]
    base = min(antigos, key=lambda g: g.ultimo[0]) if antigos else e.grupos[0]
    escolhidos = [menor or base] if resumo else list(e.grupos)
    unico = len(e.grupos) == 1 and e.grupos[0].grupo == e.provedor
    grupos = [_grupo_pecas(g, '' if unico else NOMES_GRUPO.get(g.grupo, g.grupo),
                           hora_curta(g.renova_em) if g is menor else None) for g in escolhidos]
    return [(f'{nome}: ', False)] + _juntar(grupos, ', ')


def _falta_dado(e):
    if not e.grupos:
        return e.motivo != NAO_MEDIDO
    return any(g.percentual is None for g in e.grupos)


def _menor(entradas):
    medidos = [(g, e) for e in entradas for g in e.grupos if g.percentual is not None]
    return min(medidos, key=lambda par: par[0].percentual) if medidos else None


def _alerta():
    return [(' ', False), (f'{ALERTA} abaixo de {COTA_MINIMA}%', True)]


def _sem_cotas(motivo, vazia):
    """Faixa sem leitura: 'sem dado' com o motivo e, fora da simulação, o comando para o terminal."""
    base = 'Cotas: sem dado' + (f' ({motivo})' if motivo else ' (saída sem provedores)' if vazia else '')
    if motivo == SIMULACAO:
        return [[(base, False)]]
    return [[(f'{base}. {ATUALIZAR_COTA}', False)], [(f'{base}. Atualizar: veja a dica.', False)]]


def variantes(cotas, motivo='', consultando=False):
    """Textos da faixa, do mais completo ao mais curto; o primeiro vai inteiro na dica."""
    entradas = cotas.entradas if cotas else ()
    if not entradas:
        if consultando and not motivo:
            return [[('Cotas: consultando', False)]]
        return _sem_cotas(motivo, cotas is not None)
    sem_dado = any(_falta_dado(e) for e in entradas)
    hora = hora_curta(cotas.gerado, False)
    lido = [[(f'lido às {hora}', False)]] if hora else []
    comando = [[(ATUALIZAR_COTA, False)]] if sem_dado else []
    ponteiro = [[('atualizar: veja a dica', False)]] if sem_dado else []
    completa = [_entrada_pecas(e, False) for e in entradas]
    resumo = [_entrada_pecas(e, True) for e in entradas] if len(entradas) <= PROVEDORES_EXIBIDOS else None
    menor = _menor(entradas)
    if menor:
        g, e = menor
        minimo = [(f'menor {texto_percentual(g.percentual)}% ({NOMES_GRUPO.get(g.grupo, nome_do_provedor(e))})', False)]
        if g.percentual < COTA_MINIMA:
            minimo += _alerta()
    else:
        antigos = [(g, e) for e in entradas for g in e.grupos if g.ultimo]
        if antigos:
            g, e = min(antigos, key=lambda par: par[0].ultimo[0])
            minimo = [(f'último menor {texto_percentual(g.ultimo[0])}% '
                       f'({NOMES_GRUPO.get(g.grupo, nome_do_provedor(e))}, {hora_antiga(g.ultimo[1])})', False)]
        else:
            minimo = [('sem dado', False)]
    faltam = sum(g.percentual is None for e in entradas for g in e.grupos) \
        + sum(not e.grupos and e.motivo != NAO_MEDIDO for e in entradas)
    breve = [minimo] + ([[(f'{faltam} sem dado', False)]] if faltam else []) + lido + [[('detalhes na dica', False)]]
    inicio = [('Cotas: ', False)]
    formas = [completa + lido + comando]
    if resumo is not None:
        formas += [resumo + lido + comando, resumo + lido + ponteiro]
    formas.append(breve)
    candidatas = [inicio + _juntar(partes, ' · ') for partes in formas]
    vistas, resultado = set(), []
    for pecas in candidatas:
        plano = plano_de(pecas)
        if plano not in vistas:
            vistas.add(plano)
            resultado.append(pecas)
    return resultado


def plano_de(pecas):
    return ''.join(texto for texto, _ in pecas)


def html_de(pecas, cor):
    partes = []
    for texto, alerta in pecas:
        seguro = html.escape(texto)
        partes.append(f'<span style="color:{cor}; font-weight:600; white-space:nowrap;">{seguro}</span>'
                      if alerta and cor else seguro)
    return ''.join(partes)


class FaixaCotas(QLabel):
    """Linha fixa com as cotas; escolhe o texto mais completo que cabe em duas linhas."""

    PADDING = 28  # padding horizontal e borda esquerda do estilo

    def __init__(self):
        super().__init__()
        self.setObjectName('faixa_cotas')
        self.setTextFormat(Qt.TextFormat.RichText)
        self.setWordWrap(True)
        self.setAccessibleName('Cotas dos provedores')
        self.opcoes = [[('Cotas: consultando', False)]]
        self.cor = None
        self.indice = None
        self.setText('Cotas: consultando')

    def mostrar(self, opcoes):
        self.opcoes = opcoes
        self.ajustar(True)

    def pintar(self, cor):
        self.cor = cor
        self.ajustar(True)

    def escolher(self):
        metrica = self.fontMetrics()
        largura = int((max(self.width(), 1) - self.PADDING) * .95)
        for i, pecas in enumerate(self.opcoes):
            caixa = metrica.boundingRect(QRect(0, 0, largura, 100000), Qt.TextFlag.TextWordWrap, plano_de(pecas))
            if caixa.height() <= 2 * metrica.lineSpacing() + 1:
                return i
        return len(self.opcoes) - 1

    def ajustar(self, forcar=False):
        indice = self.escolher()
        if indice == self.indice and not forcar:
            return
        self.indice = indice
        escolhida = self.opcoes[indice]
        self.setText(html_de(escolhida, self.cor))
        self.setToolTip(plano_de(self.opcoes[0]))
        self.setAccessibleDescription(plano_de(escolhida))

    def resizeEvent(self, evento):
        super().resizeEvent(evento)
        self.ajustar()

    def texto_visivel(self):
        return plano_de(self.opcoes[self.indice or 0])


class ConsultaCotas(QObject):
    """Roda `jangada-router cotas` sem shell, sem rede e sem --atualizar, com prazo e limite de saída.

    Uma consulta por vez. O estado é 'consultando', 'ok' ou 'sem_dado'; durante uma
    nova consulta `cotas` guarda a leitura anterior. Qualquer falha vira 'sem_dado'
    com o motivo curto em `motivo`.
    """

    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.ouvintes = []
        self.prazo_ms = PRAZO_MS
        self.estado = 'sem_dado'
        self.cotas = None
        self.motivo = ''
        self.excedeu = False
        self.expirou = False
        self.bruto = b''
        self.processo = QProcess(self)
        self.processo.setStandardInputFile(QProcess.nullDevice())
        self.processo.setStandardErrorFile(QProcess.nullDevice())
        self.processo.readyReadStandardOutput.connect(self.ler)
        self.processo.finished.connect(self.fim)
        self.processo.errorOccurred.connect(self.erro)
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.expirar)
        self.repeticao = QTimer(self)
        self.repeticao.setInterval(INTERVALO_MS)
        self.repeticao.timeout.connect(self.consultar)

    def ouvir(self, funcao):
        self.ouvintes.append(funcao)

    def ocupada(self):
        return self.processo.state() != QProcess.ProcessState.NotRunning

    def iniciar(self):
        """Consulta agora e a cada 60 segundos."""
        self.repeticao.start()
        self.consultar()

    def consultar(self):
        if self.ocupada():
            return
        if not comando_disponivel(ROTEADOR, self.janela.jangada):
            self.definir('sem_dado', None, 'Core sem o comando jangada-router')
            return
        self.bruto = b''
        self.excedeu = self.expirou = False
        self.janela.preparar(self.processo, ['cotas'], ROTEADOR)
        self.definir('consultando', self.cotas, self.motivo)
        self.processo.start()
        self.prazo.start(self.prazo_ms)

    def ler(self):
        self.bruto += bytes(self.processo.readAllStandardOutput())
        if len(self.bruto) > LIMITE and not self.excedeu:
            self.excedeu = True
            self.processo.kill()

    def expirar(self):
        self.expirou = True
        self.processo.kill()

    def erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo.stop()
            self.definir('sem_dado', None, 'não foi possível executar o comando')

    def fim(self, codigo, tipo):
        self.prazo.stop()
        self.ler()
        if self.expirou:
            self.definir('sem_dado', None, 'prazo esgotado')
        elif self.excedeu:
            self.definir('sem_dado', None, 'saída grande demais')
        elif codigo != 0 or tipo != QProcess.ExitStatus.NormalExit:
            self.definir('sem_dado', None, 'o comando terminou com erro')
        else:
            try:
                self.definir('ok', ler_cotas(self.bruto))
            except ValueError as erro:
                self.definir('sem_dado', None, str(erro))
            except Exception:
                self.definir('sem_dado', None, 'saída não lida')

    def definir(self, estado, cotas=None, motivo=''):
        self.estado, self.cotas, self.motivo = estado, cotas, motivo
        for funcao in list(self.ouvintes):
            funcao()

    def variantes(self):
        return variantes(self.cotas, self.motivo, self.estado == 'consultando')

    def parar_repeticao(self):
        self.repeticao.stop()

    def fechar(self):
        self.prazo.stop()
        self.repeticao.stop()
        if self.ocupada():
            self.processo.blockSignals(True)
            self.processo.kill()
            self.processo.waitForFinished(1000)
