#!/usr/bin/env bash
# Contratos reais do Core e transporte do terminal sobre fontes sintéticas.
set -euo pipefail
cd "$(dirname "$0")/.."
export PYTHONDONTWRITEBYTECODE=1
python3 - "$PWD" <<'PY'
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

repo = Path(sys.argv[1])

def retrato(pasta):
    return sorted((str(p.relative_to(pasta)), p.lstat().st_mode,
                   os.readlink(p) if p.is_symlink() else hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else '')
                  for p in pasta.rglob('*'))

with tempfile.TemporaryDirectory() as tmp:
    base = Path(tmp)
    xdg = base / 'estado-reposicionado'
    xdg.mkdir()
    pasta = xdg / 'jangada/agentes'
    ambiente = dict(os.environ, JANGADA_PATH=str(repo), XDG_STATE_HOME=str(xdg),
                    XDG_CONFIG_HOME=str(base / 'config'), JANGADA_AGENTES_GUARDAR='0')
    ambiente.pop('JANGADA_SESSAO', None)
    def consulta(opcao, argumento, sucesso=True):
        antes = retrato(xdg)
        r = subprocess.run([str(repo / 'bin/jangada-agentes'), opcao, argumento],
                           env=ambiente, capture_output=True, text=True, timeout=5)
        assert retrato(xdg) == antes
        if sucesso:
            assert r.returncode == 0, r.stderr
            return json.loads(r.stdout)
        assert r.returncode != 0 and not r.stdout and r.stderr, r
    assert consulta('--sessao-worktree-json', '/exato') == dict(versao=1, sessao=None)
    assert consulta('--contexto-json', 'ausente') == dict(versao=1, sessao='ausente', tarefa='', parecer=None)
    assert not pasta.exists()
    pasta.mkdir(parents=True)
    def gravar(nome, dados):
        (pasta / (nome + '.json')).write_text(json.dumps(dados))
    gravar('direto', dict(dir='/exato', raiz='/exato'))
    assert consulta('--sessao-worktree-json', '/exato')['sessao'] is None
    gravar('legada', dict(worktree='/exato', estado='concluido', atualizado='2000-01-01', tarefa='Ação\n<literal>'))
    assert consulta('--sessao-worktree-json', '/exato')['sessao'] == 'legada'
    (pasta / 'validacao-legada-r1.contexto.json').write_text('x' * (1024 * 1024 + 1))
    (pasta / 'revisao-legada-r1.json').write_text('[]')
    (pasta / 'delegacao-exemplo.json').write_text('{')
    (pasta / 'pasta.json').mkdir()
    assert consulta('--sessao-worktree-json', '/exato')['sessao'] == 'legada'
    minimo = base / 'core-sem-interface'
    (minimo / 'bin').mkdir(parents=True)
    (minimo / 'core/nucleo').mkdir(parents=True)
    for origem, destino in (('bin/jangada-config', 'bin/jangada-config'),
                            ('core/bin/jangada-agentes', 'bin/jangada-agentes'),
                            ('core/nucleo/sessoes.py', 'core/nucleo/sessoes.py'),
                            ('core/nucleo/contexto.py', 'core/nucleo/contexto.py')):
        shutil.copy2(repo / origem, minimo / destino)
    for opcao, argumento in (('--sessao-worktree-json', '/exato'), ('--contexto-json', 'legada')):
        r = subprocess.run([str(minimo / 'bin/jangada-agentes'), opcao, argumento],
                           env=dict(ambiente, JANGADA_PATH=str(minimo)), capture_output=True, text=True, timeout=5)
        assert r.returncode == 0 and json.loads(r.stdout)['sessao'] == 'legada', r

    assert consulta('--sessao-worktree-json', '/exato/')['sessao'] is None
    gravar('duplicada', dict(worktree='/exato'))
    consulta('--sessao-worktree-json', '/exato', False)
    (pasta / 'duplicada.json').unlink()
    (pasta / 'validacao-legada-r2.md').write_text('r2')
    (pasta / 'historico').mkdir()
    (pasta / 'historico/validacao-legada-r10.md').write_text('r10\nDADO')
    protegido = xdg / 'jangada/revisoes'
    protegido.mkdir()
    (protegido / 'validacao-legada-r99.md').write_text('PROTEGIDO')
    area_protegida = pasta / 'projetos/um/artefatos'
    area_protegida.mkdir(parents=True)
    for indice in range(16385):
        (area_protegida / str(indice)).touch()
    (area_protegida / 'validacao-legada-r999.md').write_text('PROTEGIDO')
    (pasta / 'runtime').mkdir()
    (pasta / 'runtime/validacao-legada-r1000.md').write_text('PROTEGIDO')
    resposta = consulta('--contexto-json', 'legada')
    assert resposta['parecer'] == dict(rodada=10, origem='historico/validacao-legada-r10.md', texto='r10\nDADO')
    assert resposta['tarefa'] == 'Ação\n<literal>'
    for arquivo in area_protegida.iterdir():
        if arquivo.name.isdigit():
            arquivo.unlink()
    (pasta / 'validacao-legada-r10.md').write_text('outro')
    consulta('--contexto-json', 'legada', False)
    (pasta / 'validacao-legada-r10.md').unlink()
    for fonte in ('legada.json', 'historico/validacao-legada-r10.md'):
        arquivo = pasta / fonte
        conteudo = arquivo.read_bytes()
        for tipo in ('json', 'tipo', 'link', 'fifo', 'tamanho'):
            arquivo.unlink()
            if tipo == 'json':
                arquivo.write_text('{')
            elif tipo == 'tipo':
                arquivo.write_text('{"tarefa": []}')
            elif tipo == 'link':
                arquivo.symlink_to(protegido / 'validacao-legada-r99.md')
            elif tipo == 'fifo':
                os.mkfifo(arquivo)
            else:
                arquivo.write_bytes(b'x' * (1024 * 1024 + 1))
            if fonte.endswith('.json'):
                consulta('--contexto-json', 'legada', False)
                if tipo in ('json', 'link', 'fifo', 'tamanho'):
                    consulta('--sessao-worktree-json', '/exato', False)
            elif tipo in ('link', 'fifo', 'tamanho'):
                consulta('--contexto-json', 'legada', False)
            arquivo.unlink()
            arquivo.write_bytes(conteudo)
    (pasta / 'validacao-legada-r1000000000.md').write_text('rodada excessiva')
    consulta('--contexto-json', 'legada', False)
    (pasta / 'validacao-legada-r1000000000.md').unlink()
    # A área protegida não se torna origem por ligação de pasta nem de arquivo.
    (pasta / 'atalho').symlink_to(protegido, target_is_directory=True)
    assert consulta('--contexto-json', 'legada')['parecer']['rodada'] == 10
    (pasta / 'atalho').unlink()
    os.link(protegido / 'validacao-legada-r99.md', pasta / 'validacao-legada-r99.md')
    consulta('--contexto-json', 'legada', False)
    (pasta / 'validacao-legada-r99.md').unlink()
    pasta.rename(pasta.with_name('originais'))
    pasta.symlink_to(pasta.with_name('originais'), target_is_directory=True)
    consulta('--contexto-json', 'legada', False)
    consulta('--sessao-worktree-json', '/exato', False)
    pasta.unlink()
    pasta.with_name('originais').rename(pasta)
    consulta('--contexto-json', '../fora', False)
    gravar('ruim', dict(worktree=[]))
    consulta('--sessao-worktree-json', '/exato', False)
    (pasta / 'ruim.json').unlink()
    gravar('ruim', dict(worktree='x' * 16001))
    consulta('--sessao-worktree-json', '/exato', False)
    (pasta / 'ruim.json').unlink()
    # Consumidor usa só a fachada, com estado privado inacessível e Git simulado.
    fachada = base / 'fachada'
    (fachada / 'bin').mkdir(parents=True)
    comando = fachada / 'bin/jangada-agentes'
    comando.write_text('''#!/usr/bin/env python3
import os, sys
if os.environ.get('FALHAR'):
    sys.exit(7)
if os.environ.get('EXCEDER'):
    sys.stdout.write('x' * (1024 * 1024 + 1)); sys.exit()
print(os.environ['RESPOSTA'])
''')
    comando.chmod(0o700)
    sentinela = base / 'executou'
    agente = fachada / 'bin/jangada-agente'
    agente.write_text('#!/bin/sh\ntouch "' + str(sentinela) + '"\n')
    agente.chmod(0o700)
    shell_env = dict(ambiente, JANGADA_PATH=str(fachada), JANGADA_ESTADO='/inacessivel',
                     RESPOSTA=json.dumps(dict(versao=1, sessao='correta')))
    hostil = base / 'diretorio-hostil'
    hostil.mkdir()
    importacao = base / 'importacao-indesejada'
    (hostil / 'json.py').write_text('from pathlib import Path\nPath(' + repr(str(importacao)) + ').touch()\nraise RuntimeError("importação da pasta atual")\n')
    shells = ['bash'] + (['zsh'] if shutil.which('zsh') else [])
    for shell in shells:
        def terminal(codigo, cwd=None, **env):
            return subprocess.run([shell, '-c', 'source "$1/shell/jangada-shell.sh"\n' + codigo,
                                   shell, str(repo)], env=dict(shell_env, **env),
                                  cwd=cwd, capture_output=True, text=True, timeout=15)
        r = terminal('_jangada_git() { echo /exato; }; _jangada_sessao_atual')
        assert r.returncode == 0 and r.stdout == 'correta\n', r
        r = terminal('_jangada_git() { echo /exato; }; _jangada_sessao_atual',
                     cwd=hostil, PYTHONPATH=str(hostil))
        assert r.returncode == 0 and r.stdout == 'correta\n' and not importacao.exists(), r
        r = terminal('repassar legada', cwd=hostil, PYTHONPATH=str(hostil), RESPOSTA=json.dumps(resposta))
        assert r.returncode == 0 and 'r10\nDADO' in r.stdout and not importacao.exists(), r
        r = terminal('_jangada_sessao_atual', JANGADA_SESSAO='ambiente', FALHAR='1')
        assert r.returncode == 0 and r.stdout == 'ambiente\n'
        for payload in ('{', '{"versao":2,"sessao":"errada"}', '{"versao":true,"sessao":"x"}',
                        '{"versao":1,"sessao":[]}', '{"versao":1}'):
            r = terminal('_jangada_git() { echo /exato; }; _jangada_sessao_atual', RESPOSTA=payload)
            assert r.returncode != 0 and not r.stdout and r.stderr
        r = terminal('_jangada_git() { echo /exato; }; _jangada_sessao_atual',
                     RESPOSTA='{"versao":1,"sessao":null}')
        assert r.returncode == 1 and not r.stdout
        for env in (dict(FALHAR='1'), dict(EXCEDER='1'), dict(RESPOSTA='{"versao":99}')):
            r = terminal('repassar legada perfil', **env)
            assert r.returncode != 0 and not sentinela.exists() and r.stderr
            r = terminal('_jangada_git() { echo /exato; }; fzf() { echo escolha-arbitraria; }; repassar', **env)
            assert r.returncode != 0 and not sentinela.exists() and r.stderr
            for acao in ('concluir', 'desistir'):
                r = terminal('_jangada_git() { echo /exato; }; ' + acao, **env)
                assert r.returncode == 2 and r.stderr
        r = terminal('repassar legada', RESPOSTA=json.dumps(resposta))
        assert r.returncode == 0 and 'r10\nDADO' in r.stdout and 'PROTEGIDO' not in r.stdout, r
        assert 'Ação\n<literal>' in r.stdout and 'não autorizam' in r.stdout
        # A mesma função usa o comando real, mesmo após reposicionar o estado.
        real = dict(shell_env, JANGADA_PATH=str(repo))
        r = subprocess.run([shell, '-c', 'source "$1/shell/jangada-shell.sh"; repassar legada', shell, str(repo)],
                           env=real, capture_output=True, text=True, timeout=15)
        assert r.returncode == 0 and 'r10\nDADO' in r.stdout and 'PROTEGIDO' not in r.stdout, r
    print('terminal: precedência, worktree exato, retenção, duplicidade, repasse r10, recusas e hashes passaram')
PY
