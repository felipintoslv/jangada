"""Projetos e fila: consultas assíncronas e ações pelo backend existente."""
import json
from pathlib import Path

from PyQt6.QtCore import QProcess, QTimer, Qt
from PyQt6.QtGui import QKeySequence, QShortcut, QTextCursor
from PyQt6.QtWidgets import (QFileDialog, QGridLayout, QInputDialog, QLabel, QMessageBox,
                            QLineEdit, QPlainTextEdit, QPushButton, QScrollArea, QSplitter, QTreeWidget, QTreeWidgetItem,
                            QVBoxLayout, QWidget)
from aparencia import definir_tipo
from dados import resolver_comando
from visual.fichas import ICONES


def comando(shell, acao, argumentos, confirmar=False):
    comandos = {'iniciar': 'jangada-agente', 'importar': 'jangada-fila', 'tarefa': 'jangada-task',
                'executar': 'jangada-executar', 'provedor': 'jangada-provedor',
                'integrar': 'jangada-agente-fim', 'encerrar': 'jangada-agente-fim',
                'projeto': 'jangada-projeto'}
    if acao not in comandos or not isinstance(argumentos, list) or any(not isinstance(a, str) for a in argumentos):
        raise ValueError('ação ou argumentos inválidos')
    if (acao in {'integrar', 'encerrar'} or acao == 'tarefa' and 'cancelar' in argumentos) and not confirmar:
        raise ValueError('ação exige confirmação explícita')
    if acao == 'integrar':
        if '--confirmacao' not in argumentos:
            raise ValueError('integração exige os SHA completos confirmados')
        argumentos = ['--integrar', *argumentos]
    return [resolver_comando(comandos[acao], shell)[0], *argumentos]


class Operacional(QWidget):
    def __init__(self, janela):
        super().__init__(janela)
        self.janela = janela
        self.dados = {}
        self.registros = {}
        self.validos = False
        self.fechando = False
        externo = QVBoxLayout(self)
        rolagem = QScrollArea()
        rolagem.setWidgetResizable(True)
        rolagem.setFrameShape(QScrollArea.Shape.NoFrame)
        corpo = QWidget()
        layout = QVBoxLayout(corpo)
        rolagem.setWidget(corpo)
        externo.addWidget(rolagem)
        topo = QGridLayout()
        self.botoes_projeto = {}
        self.motivos = {}
        for i, (titulo, metodo) in enumerate([('Cadastrar projeto', self.cadastrar), ('Nova atividade', self.atividade),
                                             ('Importar plano', self.importar), ('Atualizar', self.atualizar)]):
            botao = QPushButton(titulo)
            botao.clicked.connect(metodo)
            self.botoes_projeto[titulo] = botao
            topo.addWidget(self.com_motivo(titulo, botao), i // 2, i % 2)
        layout.addLayout(topo)
        divisor = QSplitter()
        self.lista = QTreeWidget()
        self.lista.setMinimumHeight(150)
        self.lista.setHeaderLabels(['Projeto, atividade ou tarefa', 'Estado'])
        self.lista.currentItemChanged.connect(self.selecionar)
        divisor.addWidget(self.lista)
        self.detalhes = QPlainTextEdit()
        self.detalhes.setReadOnly(True)
        divisor.addWidget(self.detalhes)
        layout.addWidget(divisor, 1)
        self.busca = QLineEdit()
        self.busca.setPlaceholderText('Buscar nos detalhes; Enter avança à próxima ocorrência')
        self.busca.returnPressed.connect(self.buscar)
        layout.addWidget(self.busca)
        atalho = QShortcut(QKeySequence('Ctrl+F'), self)
        atalho.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        atalho.activated.connect(self.busca.setFocus)
        linha = QGridLayout()
        self.botoes = {}
        for i, acao in enumerate(('pausar', 'retomar', 'cancelar', 'repetir')):
            botao = QPushButton(acao.capitalize())
            botao.clicked.connect(lambda _, a=acao: self.agir(a))
            self.botoes[acao] = definir_tipo(botao, 'perigo') if acao == 'cancelar' else botao
            linha.addWidget(self.com_motivo(acao, botao), i // 3, i % 3)
        self.revisar = QPushButton('Instruções de revisão')
        self.revisar.clicked.connect(self.revisao)
        linha.addWidget(self.com_motivo('revisar', self.revisar), 1, 1)
        self.sessao = QPushButton('Acompanhar sessão')
        self.sessao.clicked.connect(self.acompanhar)
        linha.addWidget(self.com_motivo('sessao', self.sessao), 1, 2)
        layout.addLayout(linha)
        self.status = QLabel('Simulação: consultas e ações não são executadas.' if not janela.real else 'Consultando o núcleo.')
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.ver_erros = QPushButton('Detalhes dos erros')
        self.ver_erros.clicked.connect(self.mostrar_erros)
        self.ver_erros.hide()
        layout.addWidget(self.ver_erros)
        self.dialogo_erros = QMessageBox(self)
        self.dialogo_erros.setWindowTitle('Erros da consulta')
        self.dialogo_erros.setTextFormat(Qt.TextFormat.PlainText)
        self.dialogo_erros.setStandardButtons(QMessageBox.StandardButton.Ok)
        self.consulta = QProcess(self)
        self.consulta.finished.connect(self.consulta_fim)
        self.consulta.errorOccurred.connect(self.consulta_erro)
        self.acao = QProcess(self)
        self.acao.finished.connect(self.acao_fim)
        self.acao.errorOccurred.connect(self.acao_erro)
        self.prazo = QTimer(self)
        self.prazo.setSingleShot(True)
        self.prazo.timeout.connect(self.consulta.kill)
        self.prazo_acao = QTimer(self)
        self.prazo_acao.setSingleShot(True)
        self.prazo_acao.timeout.connect(self.acao.kill)
        self.selecionar()

    def com_motivo(self, chave, botao):
        celula = QWidget()
        layout = QVBoxLayout(celula)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(botao)
        motivo = QLabel()
        motivo.setObjectName('motivo_acao')
        motivo.setWordWrap(True)
        motivo.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(motivo)
        self.motivos[chave] = motivo
        return celula

    def chave(self):
        item = self.lista.currentItem()
        return item.data(0, Qt.ItemDataRole.UserRole) if item else None

    def atualizar(self):
        if self.fechando or not self.janela.real or self.consulta.state() != QProcess.ProcessState.NotRunning:
            return
        self.janela.preparar(self.consulta, ['consultar', '--todos', '--sem-catalogos'], 'jangada-projeto')
        self.consulta.start()
        self.prazo.start(10000)

    def consulta_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo.stop()
            self.falhar('Núcleo indisponível. Dados anteriores desatualizados; ações bloqueadas.')

    def falhar(self, mensagem):
        self.validos = False
        self.ver_erros.hide()
        self.dialogo_erros.hide()
        self.status.setText(mensagem)
        self.selecionar()

    def consulta_fim(self, codigo, tipo):
        self.prazo.stop()
        if self.fechando:
            return
        try:
            bruto = bytes(self.consulta.readAllStandardOutput())
            if codigo != 0 or tipo != QProcess.ExitStatus.NormalExit or len(bruto) > 1024 * 1024:
                raise ValueError('consulta falhou ou excedeu 1 MiB')
            dados = json.loads(bruto)
            for campo in ('projetos', 'atividades', 'tarefas', 'sessoes', 'execucoes', 'revisoes', 'eventos', 'erros'):
                if not isinstance(dados.get(campo), list) or campo != 'erros' and any(not isinstance(r, dict) for r in dados[campo]):
                    raise ValueError('registro operacional inválido')
            self.mostrar(dados)
        except (ValueError, TypeError, KeyError):
            self.falhar('Consulta inválida. Dados anteriores desatualizados; ações bloqueadas.')

    def mostrar(self, dados):
        anterior = self.chave()
        registros = {}
        projetos = {}
        atividades = {}
        for p in dados['projetos']:
            if not isinstance(p.get('id'), str):
                raise ValueError('projeto sem identificador')
            projetos[p['id']] = p
            registros[('projeto', p['id'], p['id'])] = p
        for tipo, campo in [('atividade', 'atividades'), ('tarefa', 'tarefas'), ('sessao', 'sessoes')]:
            for r in dados[campo]:
                identificador = r.get('sessao') if tipo == 'sessao' else r.get('id')
                if not isinstance(identificador, str) or r.get('projeto') not in projetos:
                    raise ValueError('vínculo operacional inválido')
                registros[(tipo, r['projeto'], identificador)] = r
        self.lista.blockSignals(True)
        self.lista.clear()
        itens = {}
        for chave, r in registros.items():
            tipo, projeto, identificador = chave
            titulo = r.get('nome') if tipo == 'projeto' else r.get('titulo') if tipo == 'atividade' else identificador
            estado = r.get('estado', 'Planejada')
            item = QTreeWidgetItem([str(titulo or identificador), ICONES.get(estado, '?') + ' ' + estado])
            item.setData(0, Qt.ItemDataRole.UserRole, chave)
            itens[chave] = item
            if tipo == 'projeto':
                self.lista.addTopLevelItem(item)
            else:
                vinculo = r.get('atividade')
                pai = atividades.get((projeto, vinculo), itens[('projeto', projeto, projeto)])
                pai.addChild(item)
                if tipo == 'atividade':
                    atividades[(projeto, identificador)] = item
        self.dados, self.registros = dados, registros
        self.validos = not dados['erros']
        self.lista.expandAll()
        if anterior in itens:
            self.lista.setCurrentItem(itens[anterior])
        self.lista.blockSignals(False)
        erros = dados['erros']
        self.ver_erros.setVisible(bool(erros))
        self.status.setText((f'{len(erros)} ' + ('erro' if len(erros) == 1 else 'erros')
                             + ' na consulta. Ações bloqueadas.') if erros else
                            'Retrato atualizado do núcleo. Consumo ausente permanece desconhecido.')
        if erros:
            self.dialogo_erros.setText(self.status.text())
            detalhe = '\n'.join(str(e) for e in erros)
            if self.dialogo_erros.detailedText() != detalhe:
                self.dialogo_erros.setDetailedText(detalhe)
        else:
            self.dialogo_erros.hide()
        self.selecionar()

    def mostrar_erros(self):
        erros = self.dados.get('erros', [])
        if not erros or self.ver_erros.isHidden():
            return
        self.dialogo_erros.exec()

    def selecionar(self, *_):
        chave = self.chave()
        r = self.registros.get(chave)
        ocupado = self.acao.state() != QProcess.ProcessState.NotRunning if hasattr(self, 'acao') else False
        projeto = self.projeto()
        caminho_valido = bool(projeto and isinstance(projeto.get('caminho'), str)
                              and projeto['caminho'].strip() and Path(projeto['caminho']).is_absolute())
        permitido = self.janela.real and self.validos and not ocupado and chave is not None and caminho_valido
        self.botoes_projeto['Cadastrar projeto'].setEnabled(bool(self.janela.real and not ocupado))
        for titulo in ('Nova atividade', 'Importar plano'):
            self.botoes_projeto[titulo].setEnabled(bool(permitido))
        status = r.get('status') if r else None
        for acao, botao in self.botoes.items():
            estados = {'pausar': {'QUEUED', 'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER'},
                       'retomar': {'PAUSED', 'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER'},
                       'cancelar': {'QUEUED', 'PAUSED', 'WAITING_PROVIDER', 'WAITING_QUOTA', 'WAITING_REVIEWER', 'REVIEW_REQUIRED', 'REVISION_REQUIRED'},
                       'repetir': {'REVISION_REQUIRED'}}
            botao.setEnabled(bool(permitido and chave[0] == 'tarefa' and status in estados[acao]))
        self.revisar.setEnabled(bool(permitido and chave[0] == 'tarefa' and status == 'REVIEW_REQUIRED'))
        self.sessao.setEnabled(bool(permitido and chave[0] == 'sessao'))
        comum = ('Simulação: ações não executadas.' if not self.janela.real else
                 'Uma ação está em andamento.' if ocupado else
                 'Atualize a consulta sem erros.' if not self.validos else
                 'Selecione um item com projeto e pasta válidos.' if not permitido else '')
        for nome, botao in {**self.botoes, **self.botoes_projeto,
                            'revisar': self.revisar, 'sessao': self.sessao}.items():
            motivo = '' if botao.isEnabled() else comum or (
                'Selecione uma sessão vinculada.' if nome == 'sessao' else
                'Disponível para tarefa que aguarda revisão.' if nome == 'revisar' else
                'Selecione uma tarefa.' if not chave or chave[0] != 'tarefa' else
                'O estado atual da tarefa não permite esta ação.')
            self.motivos[nome].setText(motivo)
            self.motivos[nome].setVisible(bool(motivo))
            botao.setAccessibleDescription(motivo)
        if r:
            tipo, projeto, identificador = chave
            relacionados = {campo: [e for e in self.dados[campo] if e.get('projeto') == projeto
                and (tipo == 'projeto' or e.get('tarefa') == identificador or e.get('sessao') == identificador
                     or tipo == 'atividade' and e.get('atividade') == identificador)]
                for campo in ('atividades', 'tarefas', 'sessoes', 'execucoes', 'revisoes', 'eventos')}
            self.detalhes.setPlainText(json.dumps({'item': r, **relacionados}, ensure_ascii=False, indent=2))
        else:
            self.detalhes.clear()

    def projeto(self):
        chave = self.chave()
        return next((p for p in self.dados.get('projetos', []) if chave and p['id'] == chave[1]), None)

    def buscar(self):
        texto = self.busca.text()
        if not texto or self.detalhes.find(texto):
            return
        cursor = self.detalhes.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        self.detalhes.setTextCursor(cursor)
        self.detalhes.find(texto)

    def executar(self, acao, argumentos, confirmar=False):
        if self.fechando or not self.janela.real or self.acao.state() != QProcess.ProcessState.NotRunning:
            return
        try:
            vetor = comando(self.janela.jangada, acao, argumentos, confirmar)
        except ValueError as erro:
            self.status.setText('Ação recusada: ' + str(erro))
            return
        self.janela.preparar(self.acao, vetor[1:], Path(vetor[0]).name)
        self.acao.start()
        self.prazo_acao.start(30000)
        self.selecionar()

    def agir(self, acao):
        chave, projeto = self.chave(), self.projeto()
        if not projeto or not self.validos or not self.botoes[acao].isEnabled():
            return
        confirmado = True
        if acao == 'cancelar':
            pergunta = QMessageBox(self)
            pergunta.setWindowTitle('Cancelar tarefa')
            pergunta.setTextFormat(Qt.TextFormat.PlainText)
            pergunta.setText(f'Cancelar {chave[2]} em {projeto["caminho"]}?')
            pergunta.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            pergunta.setDefaultButton(QMessageBox.StandardButton.No)
            confirmado = pergunta.exec() == QMessageBox.StandardButton.Yes.value
        if confirmado:
            self.executar('tarefa', ['--projeto', projeto['caminho'], chave[2], acao], confirmar=acao == 'cancelar')

    def cadastrar(self):
        if not self.botoes_projeto['Cadastrar projeto'].isEnabled():
            return
        pasta = QFileDialog.getExistingDirectory(self, 'Pasta do projeto')
        if pasta:
            self.executar('projeto', ['--projeto', pasta, 'cadastrar'])

    def atividade(self):
        projeto = self.projeto()
        if not self.botoes_projeto['Nova atividade'].isEnabled():
            return
        titulo, ok = QInputDialog.getText(self, 'Nova atividade', 'Título')
        if not ok or not titulo.strip():
            return
        objetivo, ok = QInputDialog.getMultiLineText(self, 'Nova atividade', 'Objetivo')
        if not ok or not objetivo.strip():
            return
        criterios, ok = QInputDialog.getMultiLineText(self, 'Nova atividade', 'Critérios de aceite, um por linha')
        if ok and criterios.strip():
            argumentos = ['--projeto', projeto['caminho'], 'atividade', '--titulo', titulo, '--objetivo', objetivo]
            for criterio in criterios.splitlines():
                if criterio.strip():
                    argumentos += ['--criterio', criterio.strip()]
            self.executar('projeto', argumentos)

    def importar(self):
        projeto = self.projeto()
        if not self.botoes_projeto['Importar plano'].isEnabled():
            return
        arquivo, _ = QFileDialog.getOpenFileName(self, 'Plano de tarefas', '', 'JSON (*.json)')
        if arquivo:
            self.executar('importar', ['--projeto', projeto['caminho'], '--importar', arquivo])

    def revisao(self):
        if not self.revisar.isEnabled():
            return
        chave, projeto = self.chave(), self.projeto()
        texto = (f'Tarefa: {chave[2]}\nProjeto: {projeto["caminho"]}\n'
                 'Conferir o artefato e todos os critérios. O parecer com critérios identifica tarefa e SHA.\n'
                 'No terminal, fora do isolamento, consulte jangada-task --help e use revisar '
                 'com --parecer, --aprovar ou --reprovar e a identidade do revisor.\n'
                 'Esta consulta não aprova a tarefa nem a integração.')
        aviso = QMessageBox(QMessageBox.Icon.Information, 'Revisão da fila', texto, parent=self)
        aviso.setTextFormat(Qt.TextFormat.PlainText)
        aviso.exec()

    def acompanhar(self):
        if not self.sessao.isEnabled():
            return
        nome = self.chave()[2]
        item = self.janela.itens.get(nome)
        if item:
            self.janela.centrais.setCurrentIndex(0)
            self.janela.selecionar_nome(nome)

    def acao_fim(self, codigo, tipo):
        self.prazo_acao.stop()
        if self.fechando:
            return
        erro = bytes(self.acao.readAllStandardError()).decode('utf-8', 'replace')[:4000]
        self.status.setText('Ação concluída pelo backend.' if codigo == 0 and tipo == QProcess.ExitStatus.NormalExit else 'Ação recusada pelo backend. ' + erro)
        self.selecionar()
        self.atualizar()

    def acao_erro(self, erro):
        if erro == QProcess.ProcessError.FailedToStart:
            self.prazo_acao.stop()
            self.status.setText('Comando do backend indisponível.')
            self.selecionar()

    def fechar(self):
        self.fechando = True
        self.prazo.stop()
        self.prazo_acao.stop()
        for processo in (self.consulta, self.acao):
            if processo.state() != QProcess.ProcessState.NotRunning:
                processo.kill()
                processo.waitForFinished(1000)
