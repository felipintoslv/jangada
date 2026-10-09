#!/usr/bin/env python3
"""Reproduz verificação com estado descartável e limites da missão P0.

Não chama provedores reais. Grupos com comandos Git proibidos ou caminhos
fixos de limpeza são recusados, não aprovados. Os demais continuam.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import tempfile
import time
import unittest

sys.dont_write_bytecode = True
OUT = Path(__file__).resolve().parent
REPO = OUT.parents[3]
resultados = json.loads((OUT / 'resultados.json').read_text()) if '--alterados' in sys.argv else []


with tempfile.TemporaryDirectory(prefix='jangada-p0-verificacao-') as temporario:
    raiz = Path(temporario)
    casa = raiz / 'casa'
    casa.mkdir()
    guardas = raiz / 'guardas'
    guardas.mkdir()
    # BASH_ENV é lido antes do corpo de scripts bash não interativos.
    politica = raiz / 'limites.sh'
    politica.write_text('''case "$0" in
  testes/isolar.sh|*/testes/isolar.sh|testes/update.sh|*/testes/update.sh|testes/versao.sh|*/testes/versao.sh|testes/validar.sh|*/testes/validar.sh)
    echo "BLOQUEADO pela missão P0: grupo contém limpeza fixa, merge, reset, rebase ou tag" >&2
    exit 125;;
esac
''')
    (guardas / 'git').write_text('''#!/usr/bin/env python3
import os,sys
if any(a in {'merge','reset','clean','push','rebase','tag'} for a in sys.argv[1:]):
    print('BLOQUEADO pela missão P0: operação Git proibida',file=sys.stderr);sys.exit(125)
os.execv('/usr/bin/git',['git',*sys.argv[1:]])
''')
    (guardas / 'python3').write_text('''#!/usr/bin/env python3
import os,sys
if any(a.endswith('/baseline.py') for a in sys.argv[1:]):
    print('BLOQUEADO pela missão P0: baseline integral contém merge e reset',file=sys.stderr);sys.exit(125)
os.execv('/usr/bin/python3',['python3',*sys.argv[1:]])
''')
    # A linha shebang usa python absoluto para não chamar o próprio guarda.
    for caminho in guardas.iterdir():
        caminho.write_text(caminho.read_text().replace('#!/usr/bin/env python3', '#!/usr/bin/python3'))
        caminho.chmod(0o700)
    for nome in ('pgrep', 'pkill', 'inotifywait', 'nvidia-smi', 'sudo', 'systemctl', 'pacman', 'paru', 'yay'):
        caminho = guardas / nome
        caminho.write_text('#!/bin/sh\nexit 125\n')
        caminho.chmod(0o700)
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'LANG', 'LC_ALL', 'TZ', 'TERM')}
    env.update(HOME=str(casa), XDG_STATE_HOME=str(raiz / 'estado'),
               XDG_CONFIG_HOME=str(raiz / 'config'), XDG_DATA_HOME=str(raiz / 'dados'),
               XDG_CACHE_HOME=str(raiz / 'cache'), XDG_RUNTIME_DIR=str(raiz / 'runtime'),
               JANGADA_PATH=str(REPO), PYTHONDONTWRITEBYTECODE='1',
               JANGADA_P0_EVIDENCIAS=str(OUT),
               GIT_CONFIG_GLOBAL='/dev/null', GIT_CONFIG_NOSYSTEM='1',
               QT_QPA_PLATFORM='offscreen', BASH_ENV=str(politica),
               PATH=str(guardas) + ':/usr/bin:/bin',
               R_LIBS_USER='/home/felipinto/R/x86_64-pc-linux-gnu-library/4.6')
    (OUT / 'ataques-bubblewrap.jsonl').write_text('')

    def rodar(nome, comando, prazo=240):
        if '--alterados' in sys.argv and nome not in {'confianca-p0', 'baseline-segura', 'shellcheck-alterados', 'diff-check'}:
            return
        inicio = time.monotonic()
        processo = subprocess.Popen(comando, env=env, cwd=REPO, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, start_new_session=True)
        try:
            stdout, stderr = processo.communicate(timeout=prazo)
            codigo, saida = processo.returncode, stdout + stderr
        except subprocess.TimeoutExpired:
            os.killpg(processo.pid, signal.SIGKILL)
            stdout, stderr = processo.communicate()
            codigo, saida = 124, stdout + stderr + '\nBLOQUEADO por prazo do ensaio; grupo encerrado\n'
        (OUT / (nome + '.log')).write_text(saida)
        item = dict(nome=nome, comando=comando, codigo=codigo,
                    segundos=round(time.monotonic() - inicio, 3),
                    classificacao='PASSOU' if codigo == 0 else 'BLOQUEADO' if codigo in (124, 125) else 'FALHOU')
        resultados[:] = [r for r in resultados if r['nome'] != nome]
        resultados.append(item)
        (OUT / 'resultados.json').write_text(json.dumps(resultados, ensure_ascii=False, indent=2))
        print(json.dumps(item, ensure_ascii=False), flush=True)

    for nome in ('confianca-p0', 'orquestracao', 'executor', 'supervisao', 'operacional',
                 'deterministico', 'delegacao', 'acompanhamento', 'metricas-projeto', 'painel-orquestracao', 'tarefas'):
        rodar(nome, ['/usr/bin/python3', 'testes/' + nome + '.py'])
    for nome in ('fim', 'restaurar'):
        rodar(nome, ['/usr/bin/bash', 'testes/' + nome + '.sh'])
    # As duas reproduções destrutivas de baseline ficam excluídas explicitamente.
    comando = '''import importlib.util,unittest
s=importlib.util.spec_from_file_location('baseline','testes/baseline.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
nomes=[n for n in unittest.defaultTestLoader.getTestCaseNames(m.Baseline) if n not in ('test_rollback_antigo_perde_edicao_concorrente','test_bloqueio_preserva_conflito_e_publicacao_anterior')]
r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(m.Baseline(n) for n in nomes));raise SystemExit(not r.wasSuccessful())'''
    rodar('baseline-segura', ['/usr/bin/python3', '-B', '-c', comando])
    rodar('verificar-com-limites', ['/usr/bin/bash', 'testes/verificar.sh'], prazo=90)
    rodar('shellcheck-alterados', ['shellcheck', '-S', 'warning', 'bin/jangada-isolar',
                                 'bin/jangada-validar', 'bin/jangada-agente-fim',
                                 'bin/jangada-agente', 'bin/jangada-agentes', 'bin/jangada-delegar'])
    rodar('diff-check', ['/usr/bin/git', 'diff', '--check'])

manifesto = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in OUT.iterdir()
             if p.is_file() and p.name != 'MANIFESTO.json'}
(OUT / 'MANIFESTO.json').write_text(json.dumps(manifesto, sort_keys=True, indent=2))
