#!/usr/bin/env python3
"""Testa o contrato K7 (docs/modularizacao-3.0/03-contratos.md): o formato dos
registros das seções 1, 2, 4, 8 e 9 de docs/registros.md.

Os registros são gerados pelos comandos do jangada numa pasta temporária, com
HOME, XDG_* e PATH próprios e um tmux falso; nada vem do estado da instalação
nem do tmux da máquina. Cada registro é conferido contra a tabela
testes/contratos/registros.json (nome, tipo e obrigatoriedade de cada campo),
e cada campo da tabela precisa estar citado na seção do documento.

O jangada-projeto é trocado por um falso: registrar a execução da sessão exige
controlador fora do isolamento, e o teste precisa dar o mesmo resultado dentro
e fora dele. Pelo mesmo motivo o código de saída do jangada-agente não é
conferido: o SESSAO.json já está gravado quando a preservação do pedido, que
vem depois, recusa dentro do isolamento.

Uso: testes/contratos-registros.py
"""

import copy
import json
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
RAIZ = pathlib.Path(__file__).resolve().parents[1]
TABELA = RAIZ / 'testes/contratos/registros.json'
DOCUMENTO = RAIZ / 'docs/registros.md'
SESSAO = 'projeto--tarefa'
MARCA = '/tmp/.jangada-isolado'
DATA = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$')
TIPOS = {
    'texto': lambda v: isinstance(v, str),
    'data': lambda v: isinstance(v, str) and bool(DATA.match(v)),
    'inteiro': lambda v: isinstance(v, int) and not isinstance(v, bool),
    'numero': lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    'booleano': lambda v: isinstance(v, bool),
    'objeto': lambda v: isinstance(v, dict),
    'lista': lambda v: isinstance(v, list),
    'nulo': lambda v: v is None,
}
# Um campo renomeado em cada ponto do código que grava: (arquivo, de, para,
# registro, campo que some, campo que aparece).
TROCAS = [
    ('bin/jangada-validar', 'itens: $itens,', 'apontamentos: $itens,',
     'validar.jsonl', 'itens', 'apontamentos'),
    ('bin/jangada-validar', 'candidate_sha: $candidato,', 'candidato: $candidato,',
     'validacao-SESSAO.aprovado', 'candidate_sha', 'candidato'),
    ('bin/jangada-agente', 'desde:$agora,', 'criado:$agora,', 'SESSAO.json', 'desde', 'criado'),
    ('bin/jangada-config', 'estado: $e,', 'situacao: $e,', 'eventos-agentes.jsonl', 'estado', 'situacao'),
    ('bin/jangada-delegar', 'papel: $papel,', 'funcao: $papel,', 'delegacoes.jsonl', 'papel', 'funcao'),
]

FALSOS = {
    # Só conhece a sessão que o new-session criou.
    'tmux': '''#!/bin/sh
case " $* " in
  *" new-session "*) : >"$FALSO_DIR/tmux.sessao" ;;
  *" has-session "*) [ -e "$FALSO_DIR/tmux.sessao" ] || exit 1 ;;
esac
exit 0
''',
    # Responde à lista de agentes, à cota e ao pedido (revisão ou delegação).
    'agy': '''#!/usr/bin/env bash
if [[ "$1" == agents ]]; then
  printf '%s\\n' explorador leitor pesquisador verificador auditor arquiteto otimizador redator revisor
  exit 0
fi
if [[ "$2" == /usage ]]; then
  printf '{"status":"SUCCESS","response":"","command":{"name":"usage","data":{"groups":[{"name":"Gemini Models","buckets":[{"id":"gemini-weekly","remaining_fraction":0.9},{"id":"gemini-5h","remaining_fraction":%s}]}]}}}\\n' "$FALSO_COTA"
  exit 0
fi
jq -n --arg r "$(printf '%b' "$FALSO_RESPOSTA")" \\
  '{conversation_id: "c1", status: "SUCCESS", response: $r, denied_actions: []}'
''',
    'jangada-projeto': '''#!/bin/sh
case " $* " in *" sessao-iniciar "*) echo '{"execucao":"exe-0123456789abcdef"}' ;; esac
exit 0
''',
}

falhas = 0


def conferir(descricao, certo, detalhe=()):
    global falhas
    print(('ok    ' if certo else 'FALHA ') + descricao)
    if not certo:
        falhas += 1
        for linha in detalhe:
            print('      ' + str(linha))


def problemas(nome, registro, campos):
    """Um problema por linha; lista vazia quando o registro cumpre a tabela."""
    if not isinstance(registro, dict):
        return [f'{nome}: o registro não é um objeto JSON']
    achados = []
    for campo, regra in campos.items():
        if campo not in registro:
            if regra['obrigatorio']:
                achados.append(f'{nome}: falta o campo obrigatório {campo}')
        elif not any(TIPOS[t](registro[campo]) for t in regra['tipo']):
            achados.append(f'{nome}: {campo} devia ser {" ou ".join(regra["tipo"])}, '
                           f'veio {json.dumps(registro[campo], ensure_ascii=False)[:60]}')
    achados += [f'{nome}: campo fora da tabela: {campo}' for campo in registro if campo not in campos]
    return achados


def secao_do_documento(numero):
    texto = DOCUMENTO.read_text(encoding='utf-8')
    achado = re.search(rf'^## {re.escape(numero)}\. .*?(?=^## |\Z)', texto, re.M | re.S)
    return achado.group(0) if achado else ''


def executavel(caminho, conteudo):
    caminho.write_text(conteudo, encoding='utf-8')
    caminho.chmod(0o755)


class Gerador:
    """Gera os registros numa pasta temporária, com o código de RAIZ ou com
    cópias alteradas dos arquivos de `trocas`."""

    def __init__(self, tmp, trocas=()):
        self.tmp = tmp
        self.arvore = tmp / 'jangada'
        self.falso = tmp / 'falso'
        self.casa = tmp / 'casa'
        self.projeto = tmp / 'projeto'
        self.estado = tmp / 'estado/jangada'
        self.worktree = tmp / 'worktrees/projeto/tarefa'
        for pasta in (self.arvore / 'bin', self.falso, self.projeto, self.estado, tmp / 'bin',
                      tmp / 'config/jangada', tmp / 'cache', tmp / 'run',
                      self.casa / '.gemini/antigravity-cli/log', self.casa / '.gemini/config'):
            pasta.mkdir(parents=True)
        for origem in RAIZ.iterdir():
            if origem.name != 'bin' and not origem.name.startswith('.'):
                (self.arvore / origem.name).symlink_to(origem)
        for origem in (RAIZ / 'bin').iterdir():
            if origem.name != 'jangada-projeto':
                (self.arvore / 'bin' / origem.name).symlink_to(origem)
        for arquivo, de, para in trocas:
            destino = self.arvore / arquivo
            texto = destino.read_text(encoding='utf-8')
            if de not in texto:
                raise SystemExit(f'{arquivo} não tem mais o trecho "{de}"; atualize TROCAS')
            destino.unlink()
            executavel(destino, texto.replace(de, para))
        executavel(self.arvore / 'bin/jangada-projeto', FALSOS['jangada-projeto'])
        for nome in ('tmux', 'agy'):
            executavel(tmp / 'bin' / nome, FALSOS[nome])
        for nome in ('claude', 'notify-send', 'setsid', 'pkill'):
            executavel(tmp / 'bin' / nome, '#!/bin/sh\nexit 0\n')
        (tmp / 'config/jangada/jangada.conf').write_text(f'JANGADA_WORKTREES={tmp}/worktrees\n')
        (self.casa / '.gemini/antigravity-cli/settings.json').write_text(
            json.dumps({'trustedWorkspaces': [str(self.projeto.resolve())]}))
        hooks = (RAIZ / 'default/agy/hooks.json').read_text(encoding='utf-8')
        (self.casa / '.gemini/config/hooks.json').write_text(hooks.replace('@JANGADA_PATH@', str(self.arvore)))
        # Ambiente montado do zero: nenhuma variável JANGADA_*, TMUX ou XDG_* da
        # sessão que roda o teste chega aos comandos.
        self.ambiente = {
            'PATH': f'{tmp}/bin:/usr/local/sbin:/usr/local/bin:/usr/bin:/bin',
            'HOME': str(self.casa), 'LANG': 'C.UTF-8',
            'XDG_STATE_HOME': str(tmp / 'estado'), 'XDG_CONFIG_HOME': str(tmp / 'config'),
            'XDG_CACHE_HOME': str(tmp / 'cache'), 'XDG_RUNTIME_DIR': str(tmp / 'run'),
            'TMUX_TMPDIR': str(tmp / 'run'), 'GIT_CONFIG_GLOBAL': '/dev/null', 'GIT_CONFIG_NOSYSTEM': '1',
            'JANGADA_PATH': str(self.arvore), 'FALSO_DIR': str(self.falso),
            'JANGADA_ISOLAR_ESCRITA': str(self.falso), 'FALSO_COTA': '0.9', 'FALSO_RESPOSTA': '',
        }
        if 'TMPDIR' in os.environ:
            self.ambiente['TMPDIR'] = os.environ['TMPDIR']
        if not shutil.which('gitleaks', path=self.ambiente['PATH']):
            self.ambiente['JANGADA_VALIDAR_SEM_GITLEAKS'] = '1'
        self.git('init', '-q', '-b', 'main', pasta=self.projeto)
        self.git('commit', '-q', '--allow-empty', '-m', 'inicio', pasta=self.projeto)

    def rodar(self, *comando, pasta=None, entrada=None, **variaveis):
        return subprocess.run([str(c) for c in comando], cwd=pasta or self.tmp, env={**self.ambiente, **variaveis},
                              input=entrada, stdin=None if entrada is not None else subprocess.DEVNULL,
                              capture_output=True, text=True, timeout=300)

    def como_agente(self, *comando, **argumentos):
        """Roda como o agente chama: com JANGADA_ISOLADO e a marca do isolamento
        montada. Dentro de uma sessão a marca já existe; fora, o bwrap monta só
        ela, como faz o testes/validar.sh."""
        prefixo, variaveis = [], {'JANGADA_ISOLADO': '1', 'JANGADA_SESSAO': SESSAO}
        montagens = pathlib.Path('/proc/self/mountinfo').read_text().splitlines()
        if not any(linha.split()[4] == MARCA for linha in montagens):
            marca = self.tmp / 'marca'
            marca.touch()
            prefixo = ['bwrap', '--dev-bind', '/', '/', '--ro-bind', '/dev/null', marca, '--']
            variaveis['JANGADA_MARCA_ISOLADO'] = str(marca)
        return self.rodar(*prefixo, *comando, **variaveis, **argumentos)

    def git(self, *argumentos, pasta):
        feito = self.rodar('git', '-c', 'user.name=t', '-c', 'user.email=t@t', *argumentos, pasta=pasta)
        if feito.returncode:
            raise SystemExit(f'git {" ".join(argumentos)}: {feito.stderr}')

    def comando(self, nome):
        return self.arvore / 'bin' / nome

    def linhas(self, nome):
        arquivo = self.estado / nome
        if not arquivo.is_file():
            return []
        return [json.loads(linha) for linha in arquivo.read_text(encoding='utf-8').splitlines() if linha]

    def sessao(self):
        arquivo = self.estado / 'agentes' / f'{SESSAO}.json'
        return json.loads(arquivo.read_text(encoding='utf-8')) if arquivo.is_file() else None

    def abrir_sessao(self):
        """SESSAO.json criado pelo jangada-agente (seção 4)."""
        self.rodar(self.comando('jangada-agente'), '--agente', 'claude', '--revisor', 'agy',
                   '--projeto', self.projeto, '--nome', 'tarefa', '--prompt', 'tarefa de teste')
        return self.sessao()

    def hooks(self):
        """eventos-agentes.jsonl (seção 8) e os campos que os hooks põem no SESSAO.json."""
        eventos = [
            ('inicio', {'session_id': '11111111-2222-3333-4444-555555555555', 'cwd': str(self.worktree)}),
            ('trabalhando', {'prompt': 'faça'}),
            ('subagente-inicio', {'session_id': 'c1', 'agent_id': 'a1', 'agent_type': 'explorador'}),
            ('subagente-fim', {'session_id': 'c1', 'agent_id': 'a1', 'agent_type': 'explorador'}),
            ('aguardando', {'message': 'permissão', 'notification_type': 'permission_prompt'}),
        ]
        for evento, dados in eventos:
            self.rodar(self.comando('jangada-hook-claude'), evento, entrada=json.dumps(dados), JANGADA_SESSAO=SESSAO)
        self.rodar(self.comando('jangada-agentes'), '--focar', SESSAO)
        return self.linhas('eventos-agentes.jsonl')

    def validar(self):
        """validar.jsonl (seção 1), pareceres e marca de aprovação (seção 2): uma
        rodada REVISAR e outra APROVADO, com o agy falso de revisor."""
        (self.worktree / 'arquivo.txt').write_text('linha 1\n')
        self.git('add', 'arquivo.txt', pasta=self.worktree)
        self.git('commit', '-q', '-m', 'commit 1', pasta=self.worktree)
        codigos = []
        for resposta, extra in (('STATUS: REVISAR\\n1. arquivo.txt:1: problema', []),
                                ('STATUS: APROVADO\\ntudo certo', ['--resposta', '1 rejeitado: motivo'])):
            feito = self.como_agente(self.comando('jangada-validar'), *extra, self.worktree,
                                     FALSO_RESPOSTA=resposta)
            codigos.append(feito.returncode)
        return codigos

    def delegar(self):
        """delegacoes.jsonl (seção 9): uma delegação atendida e uma recusada por cota."""
        codigos = []
        for cota in ('0.9', '0.1'):
            feito = self.como_agente(self.comando('jangada-delegar'), 'explorador', 'mapeie', pasta=self.projeto,
                                     FALSO_COTA=cota, FALSO_RESPOSTA='relatorio em a.sh:1',
                                     JANGADA_DELEGAR_CACHE='0')
            codigos.append(feito.returncode)
        return codigos

    def tudo(self):
        """Todos os registros, por nome da tabela: lista de (rótulo, registro)."""
        registros = {nome: [] for nome in ('validar.jsonl', 'validacao-SESSAO.aprovado', 'SESSAO.json',
                                           'eventos-agentes.jsonl', 'delegacoes.jsonl')}
        pareceres = self.estado / 'agentes'
        momentos = [('criado', self.abrir_sessao())]
        registros['eventos-agentes.jsonl'] = list(enumerate(self.hooks(), 1))
        momentos.append(('depois dos hooks', self.sessao()))
        self.codigos_validar = self.validar()
        momentos.append(('depois do validar', self.sessao()))
        registros['SESSAO.json'] = momentos
        registros['validar.jsonl'] = list(enumerate(self.linhas('validar.jsonl'), 1))
        marca = pareceres / f'validacao-{SESSAO}.aprovado'
        if marca.is_file():
            registros['validacao-SESSAO.aprovado'] = [('marca', json.loads(marca.read_text(encoding='utf-8')))]
        self.pareceres = sorted(pareceres.glob(f'validacao-{SESSAO}-r*.md'))
        self.codigos_delegar = self.delegar()
        registros['delegacoes.jsonl'] = list(enumerate(self.linhas('delegacoes.jsonl'), 1))
        return registros


def achados_de(tabela, registros):
    return {nome: [p for rotulo, registro in registros[nome]
                   for p in problemas(f'{nome} ({rotulo})', registro, tabela[nome]['campos'])]
            for nome in registros}


def main():
    tabela = json.loads(TABELA.read_text(encoding='utf-8'))
    parecer = tabela.pop('validacao-SESSAO-rN.md')

    # Todo campo da tabela está no documento, entre crases no texto ou entre
    # aspas num exemplo.
    for nome, descricao in {**tabela, 'validacao-SESSAO-rN.md': parecer}.items():
        secao = secao_do_documento(descricao['secao'])
        conferir(f'{nome}: a seção {descricao["secao"]} existe em docs/registros.md', bool(secao))
        faltam = [campo for campo in descricao.get('campos', {})
                  if f'`{campo}`' not in secao and f'"{campo}"' not in secao]
        conferir(f'{nome}: todo campo da tabela está citado na seção {descricao["secao"]}', not faltam,
                 [f'sem citação: {campo}' for campo in faltam])

    with tempfile.TemporaryDirectory() as pasta:
        gerador = Gerador(pathlib.Path(pasta).resolve())
        registros = gerador.tudo()
        achados = achados_de(tabela, registros)

        conferir('o jangada-agente grava o SESSAO.json', registros['SESSAO.json'][0][1] is not None)
        conferir('os hooks e a troca de foco gravam seis eventos',
                 [e.get('estado') for _, e in registros['eventos-agentes.jsonl']]
                 == ['inicio', 'trabalhando', 'subagente-inicio', 'subagente-fim', 'aguardando', 'foco'],
                 [e for _, e in registros['eventos-agentes.jsonl']])
        conferir('o hook grava estado, mensagem e conversa no SESSAO.json',
                 all(campo in (registros['SESSAO.json'][1][1] or {}) for campo in ('conversa', 'mensagem'))
                 and (registros['SESSAO.json'][1][1] or {}).get('estado') == 'aguardando')
        conferir('o jangada-validar sai com 3 no REVISAR e 0 no APROVADO', gerador.codigos_validar == [3, 0],
                 [gerador.codigos_validar])
        conferir('o jangada-validar grava a validação no SESSAO.json',
                 (registros['SESSAO.json'][2][1] or {}).get('validacao') == 'r2: APROVADO (agy)')
        conferir('o validar.jsonl tem uma linha por rodada',
                 [(r.get('rodada'), r.get('resultado')) for _, r in registros['validar.jsonl']]
                 == [(1, 'revisar'), (2, 'aprovado')])
        conferir('cada rodada grava um parecer validacao-SESSAO-rN.md',
                 [p.name for p in gerador.pareceres] == [f'validacao-{SESSAO}-r{n}.md' for n in (1, 2)])
        primeiras = [next((linha for linha in p.read_text(encoding='utf-8').splitlines() if linha.strip()), '')
                     for p in gerador.pareceres]
        conferir('a primeira linha com texto de cada parecer é o STATUS',
                 bool(primeiras) and all(re.match(parecer['primeira_linha'], linha) for linha in primeiras),
                 primeiras)
        conferir('o APROVADO grava a marca validacao-SESSAO.aprovado', bool(registros['validacao-SESSAO.aprovado']))
        conferir('o jangada-delegar sai com 0 na delegação atendida e 4 na recusada',
                 gerador.codigos_delegar == [0, 4], [gerador.codigos_delegar])
        conferir('o delegacoes.jsonl tem uma linha atendida e uma recusada',
                 [d.get('recusa') for _, d in registros['delegacoes.jsonl']] == [False, True])
        for nome in tabela:
            conferir(f'{nome}: campos e tipos conforme a tabela', not achados[nome], achados[nome])
            presentes = {campo for _, registro in registros[nome] if isinstance(registro, dict) for campo in registro}
            ausentes = [campo for campo in tabela[nome]['campos'] if campo not in presentes]
            ausentes = sorted(set(ausentes) - set(tabela[nome].get('sem_exemplo', [])))
            conferir(f'{nome}: todo campo da tabela aparece em algum registro gerado, salvo os de "sem_exemplo"',
                     not ausentes, [f'ausentes: {ausentes}'])

        # O teste precisa falhar quando um campo muda de nome. Primeiro numa
        # cópia do registro, depois numa cópia do código que grava.
        for nome in tabela:
            campo = next(c for c, regra in tabela[nome]['campos'].items() if regra['obrigatorio'])
            alterado = copy.deepcopy(registros[nome][-1][1]) if registros[nome] else {}
            if isinstance(alterado, dict):
                alterado[f'{campo}_novo'] = alterado.pop(campo, None)
            achado = problemas(nome, alterado, tabela[nome]['campos'])
            conferir(f'{nome}: campo {campo} renomeado numa cópia do registro é apontado',
                     f'{nome}: falta o campo obrigatório {campo}' in achado
                     and f'{nome}: campo fora da tabela: {campo}_novo' in achado, achado)
        errado = copy.deepcopy(registros['validar.jsonl'][-1][1]) if registros['validar.jsonl'] else {}
        errado['rodada'] = '2'
        conferir('validar.jsonl: campo com o tipo trocado numa cópia do registro é apontado',
                 any('rodada devia ser inteiro' in p for p in problemas('validar.jsonl', errado,
                                                                        tabela['validar.jsonl']['campos'])))

    with tempfile.TemporaryDirectory() as pasta:
        gerador = Gerador(pathlib.Path(pasta).resolve(), [troca[:3] for troca in TROCAS])
        achados = achados_de(tabela, gerador.tudo())
        for arquivo, _, _, nome, some, aparece in TROCAS:
            texto = '\n'.join(achados[nome])
            conferir(f'{nome}: {some} renomeado numa cópia de {arquivo} é apontado',
                     f'falta o campo obrigatório {some}' in texto and f'campo fora da tabela: {aparece}' in texto,
                     achados[nome])

    if falhas:
        print(f'{falhas} falha(s)')
        return 1
    print('todos os testes do contrato de registros passaram')
    return 0


if __name__ == '__main__':
    sys.exit(main())
