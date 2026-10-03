"""Leitura de sessões e contadores, sem dependência gráfica."""
from dataclasses import dataclass
from datetime import datetime
import html
import json
import os
from pathlib import Path
import re
import stat
import subprocess

NOME = re.compile(r"[A-Za-z0-9_.-]+")
LIMITE = 1024 * 1024
CORES = {"aguardando": "#f2c66d", "trabalhando": "#85baff",
         "concluido": "#96d6a8", "interrompido": "#f09d93"}
ROTULOS = {"aguardando": "Precisa de você", "trabalhando": "Em andamento",
           "concluido": "Turno encerrado", "interrompido": "Interrompida"}
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
    for estado, rotulo in (('trabalhando', 'em andamento'), ('aguardando', 'precisam de você'), ('interrompido', 'interrompidas')):
        if contagem[estado]:
            if estado == 'aguardando' and contagem[estado] == 1:
                rotulo = 'precisa de você'
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


def texto(valor):
    return valor[:16000] if isinstance(valor, str) else ''


def registro(pasta, nome):
    try:
        fd = os.open(pasta / (nome + ".json"), os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, "rb") as arquivo:
            if not stat.S_ISREG(os.fstat(arquivo.fileno()).st_mode):
                return {}
            bruto = arquivo.read(LIMITE + 1)
        if len(bruto) > LIMITE:
            return {}
        dados = json.loads(bruto)
        return dados if isinstance(dados, dict) else {}
    except (OSError, ValueError, UnicodeError):
        return {}


def ler_lista(saida, pasta):
    sessoes = {}
    for linha in saida.splitlines():
        campos = linha.split('\t')
        if len(campos) != 6:
            raise ValueError('A listagem recebida não tem os seis campos esperados.')
        estado, nome, diretorio, atualizado, ramo, tarefa = campos
        if not NOME.fullmatch(nome) or nome in ('.', '..'):
            raise ValueError('A listagem contém um nome de sessão inválido.')
        dados = registro(pasta, nome)
        raiz = texto(dados.get('raiz')) or diretorio
        inicio = texto(dados.get('desde'))
        sessoes[nome] = Sessao(nome, estado, diretorio, atualizado, html.unescape(ramo), texto(dados.get('tarefa')) or html.unescape(tarefa), texto(dados.get('agente')) or 'Não informado', Path(raiz).name or 'Sem projeto', texto(dados.get('mensagem')), inicio, raiz)
    return sessoes


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
    estado = Path(args.estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser()
    try:
        ambiente = dict(os.environ, JANGADA_PATH=str(jangada),
                        XDG_STATE_HOME=str(estado.parent.parent))
        resposta = subprocess.run([str(jangada / 'bin/jangada-agentes'), '--lista'], capture_output=True, timeout=10, env=ambiente, check=True)
        if len(resposta.stdout) > LIMITE:
            raise ValueError('A listagem excedeu o limite de leitura.')
        return resumo_barra(ler_lista(resposta.stdout.decode('utf-8', 'replace'), estado))
    except (OSError, ValueError, subprocess.SubprocessError):
        return {'text': 'Tarefas · erro', 'class': 'erro', 'tooltip': 'Não foi possível consultar sessões. Clique para abrir a central e conferir o erro.'}
