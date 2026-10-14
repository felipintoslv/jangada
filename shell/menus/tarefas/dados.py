"""Leitura de sessões e contadores, sem dependência gráfica."""
from dataclasses import dataclass
from datetime import datetime
import html
import json
import os
from pathlib import Path
import re
import selectors
import time
import subprocess

NOME = re.compile(r"[A-Za-z0-9_.-]+")
LIMITE = 1024 * 1024
CORES = {"aguardando": "#f2c66d", "trabalhando": "#85baff",
         "concluido": "#96d6a8", "interrompido": "#f09d93"}
ROTULOS = {"aguardando": "Precisa da sua resposta", "trabalhando": "Em execução",
           "concluido": "Pronto para conferir", "interrompido": "Interrompida"}
ORDEM = {"aguardando": 0, "interrompido": 1, "trabalhando": 2, "concluido": 4}

def estado_exibido(sessao):
    return 'trabalhando' if sessao.estado in ('ativo', 'iniciado') else sessao.estado


def idade(atualizado, agora=None):
    try:
        data = datetime.fromisoformat(atualizado)
        agora = agora or datetime.now().astimezone()
        if data.tzinfo is None:
            data = data.astimezone()
        segundos = (agora - data).total_seconds()
        if segundos < -60:
            return 'Horário futuro'
        if segundos < 60:
            return 'Agora'
        minutos = int(segundos // 60)
        if minutos < 60:
            return f'Há {minutos} min'
        horas = minutos // 60
        dias = horas // 24
        return f'Há {horas} h' if horas < 24 else f'Há {dias} ' + ('dia' if dias == 1 else 'dias')
    except (ValueError, TypeError, OverflowError):
        return 'Sem horário'


def resumo_barra(sessoes):
    contagem = {estado: sum((estado_exibido(s) == estado for s in sessoes.values())) for estado in CORES}
    partes = [f'Tarefas {len(sessoes)}']
    for estado, rotulo in (('trabalhando', 'em execução'), ('aguardando', 'precisam da sua resposta'), ('interrompido', 'interrompidas')):
        if contagem[estado]:
            if estado == 'aguardando' and contagem[estado] == 1:
                rotulo = 'precisa da sua resposta'
            if estado == 'interrompido' and contagem[estado] == 1:
                rotulo = 'interrompida'
            partes.append(f'{contagem[estado]} {rotulo}')
    classe = next((e for e in ORDEM if contagem[e]), 'vazio' if not sessoes else 'ativo')
    linhas = [f'{s.projeto} · {(s.tarefa.splitlines()[0] if s.tarefa else s.nome)} [{ROTULOS.get(estado_exibido(s), estado_exibido(s))}]' for s in sorted(sessoes.values(), key=lambda s: (ORDEM.get(estado_exibido(s), 3), s.projeto, s.nome))]
    return {'text': ' · '.join(partes), 'class': classe, 'tooltip': html.escape('\n'.join(linhas + ['Clique: central de tarefas · Clique direito: nova tarefa']))}


@dataclass
class Sessao:
    nome: str
    estado: str
    dir: str
    atualizado: str
    ramo: str
    tarefa: str
    agente: str = 'Não informado'
    projeto: str = 'Sem projeto'
    mensagem: str = ''
    inicio: str = ''
    raiz: str = ''
    coordenador: str = 'dono'
    revisor: str = 'Não informado'


def pasta_sessoes(estado=None):
    """Pasta de sessões: a informada ou a que o jangada-config exporta."""
    estado = estado or os.environ.get('JANGADA_SESSOES')
    if not estado:
        raise ValueError('A pasta de sessões não foi informada: use --estado ou JANGADA_SESSOES.')
    return Path(estado).expanduser()


CAMPOS = ('nome', 'estado', 'dir', 'atualizado', 'ramo', 'tarefa', 'agente',
          'raiz', 'projeto', 'mensagem', 'desde', 'coordenador', 'revisor')


def ler_lista(saida):
    if len(saida.encode('utf-8')) > LIMITE:
        raise ValueError('A listagem excedeu o limite de leitura.')
    try:
        dados = json.loads(saida)
    except (ValueError, RecursionError) as erro:
        raise ValueError('A consulta não contém JSON válido.') from erro
    if not isinstance(dados, dict) or type(dados.get('versao')) is not int or dados['versao'] != 1:
        raise ValueError('Versão da consulta de sessões desconhecida.')
    lista = dados.get('sessoes')
    if not isinstance(lista, list) or len(lista) > 4096:
        raise ValueError('A consulta não contém uma lista de sessões válida.')
    sessoes = {}
    for s in lista:
        if not isinstance(s, dict) or any(c not in s or not isinstance(s[c], str)
                                         or len(s[c]) > 16000 for c in CAMPOS):
            raise ValueError('Sessão incompleta ou campo de apresentação inválido.')
        nome = s['nome']
        if not NOME.fullmatch(nome) or nome in ('.', '..') or len(nome) > 255 or nome in sessoes:
            raise ValueError('A listagem contém um nome de sessão inválido ou repetido.')
        if not s['estado']:
            raise ValueError('A listagem contém estado vazio.')
        sessoes[nome] = Sessao(nome, s['estado'], s['dir'], s['atualizado'], s['ramo'],
                              s['tarefa'], s['agente'], s['projeto'], s['mensagem'],
                              s['desde'], s['raiz'], s['coordenador'], s['revisor'])
    return sessoes


def consultar(comando, ambiente):
    with subprocess.Popen(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          env=ambiente) as processo:
        try:
            saida = bytearray()
            total = 0
            prazo = time.monotonic() + 10
            with selectors.DefaultSelector() as seletor:
                seletor.register(processo.stdout, selectors.EVENT_READ)
                seletor.register(processo.stderr, selectors.EVENT_READ)
                while seletor.get_map():
                    restante = prazo - time.monotonic()
                    if restante <= 0:
                        raise ValueError('Tempo de consulta esgotado.')
                    for chave, _ in seletor.select(restante):
                        bloco = os.read(chave.fileobj.fileno(), 65536)
                        if not bloco:
                            seletor.unregister(chave.fileobj)
                            continue
                        total += len(bloco)
                        if total > LIMITE:
                            raise ValueError('A listagem excedeu o limite de leitura.')
                        if chave.fileobj is processo.stdout:
                            saida.extend(bloco)
            codigo = processo.wait(timeout=max(0.001, prazo - time.monotonic()))
            if codigo != 0:
                raise ValueError('O comando de consulta falhou.')
            return ler_lista(saida.decode('utf-8'))
        finally:
            if processo.poll() is None:
                processo.kill()
                processo.wait()


def simuladas(passo):
    estados = ['aguardando', 'trabalhando', 'concluido', 'interrompido']
    tarefas = ['Conferir a proposta de interface', 'Ajustar o roteamento de tarefas', 'Revisar as referências do artigo', 'Retomar a revisão da instalação']
    resultado = {}
    for i, nome in enumerate(['jangada--interface', 'jangada--router', 'artigo--fontes', 'jangada--instalacao']):
        if passo % 4 == 3 and i == 2:
            continue
        estado = estados[i]
        if i == 1:
            estado = ['trabalhando', 'aguardando', 'concluido', 'trabalhando'][passo % 4]
        projeto = 'artigo' if i == 2 else 'jangada'
        resultado[nome] = Sessao(nome, estado, f'/exemplo/{projeto}', datetime.now().astimezone().isoformat(), 'agente/' + nome.split('--')[1], tarefas[i], ['claude', 'codex', 'agy', 'claude'][i], projeto, ['Podemos começar pelo contador da Waybar?', 'Ajustando o roteamento de tarefas.', 'Referências conferidas. Quer acrescentar alguma fonte?', 'A sessão foi interrompida e pode ser retomada.'][i])
    return resultado


def barra(args):
    if not args.real:
        return resumo_barra(simuladas(0))
    jangada = Path(args.jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
    try:
        estado = pasta_sessoes(args.estado)
        ambiente = dict(os.environ, JANGADA_PATH=str(jangada),
                        XDG_STATE_HOME=str(estado.parent.parent))
        return resumo_barra(consultar([str(jangada / 'bin/jangada-agentes'), '--lista-json'], ambiente))
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'text': 'Tarefas · erro', 'class': 'erro', 'tooltip': 'Não foi possível consultar sessões. Clique para abrir a central e conferir o erro.'}
