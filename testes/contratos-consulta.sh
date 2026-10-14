#!/usr/bin/env bash
# Testa o contrato K4 (docs/modularizacao-3.0/03-contratos.md): as consultas
# jangada-agentes --lista, --lista-atualizada e --waybar não gravam nada no
# estado, e só --limpar-orfaos remove as sessões órfãs, com o mesmo critério
# de antes.
#
# Uso: testes/contratos-consulta.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
estado="$tmp/state/jangada/agentes"
mkdir -p "$estado" "$tmp/bin" "$tmp/home" "$tmp/config" "$tmp/pasta"

# O tmux falso só conhece a sessão "viva".
printf '#!/bin/sh\n[ "$*" != "${*#*list-sessions}" ] && echo viva\nexit 0\n' >"$tmp/bin/tmux"
chmod +x "$tmp/bin/tmux"

agora="$(date -Iseconds)"
morto="$(sh -c 'echo $$')"
jq -n --arg a "$agora" '{estado:"trabalhando", atualizado:$a}' >"$estado/viva.json"
jq -n --arg a "$agora" '{estado:"concluido", atualizado:$a}' >"$estado/concluida.json"
jq -n --arg a "$agora" --argjson p "$morto" '{estado:"trabalhando", pid:$p, atualizado:$a}' >"$estado/orfa.json"
jq -n '{estado:"concluido", atualizado:"2000-01-01T00:00:00+00:00"}' >"$estado/vencida.json"
jq -n --arg a "$agora" --arg d "$tmp/pasta" '{estado:"trabalhando", agente:"codex", dir:$d, atualizado:$a}' >"$estado/caida.json"

agentes() {
  env -u TMUX -u JANGADA_ISOLADO -u JANGADA_AGENTES_GUARDAR PATH="$tmp/bin:$PATH" HOME="$tmp/home" \
    XDG_STATE_HOME="$tmp/state" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
    "$repo_jangada/bin/jangada-agentes" "$@"
}

retrato() {
  (cd "$tmp/state" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum && find . | sort)
}

consultas=(--lista --lista-atualizada --waybar)
for opcao in "${consultas[@]}"; do
  antes="$(retrato)"
  agentes "$opcao" >"$tmp/antes$opcao" 2>&1
  conferir "$opcao sai com 0" [ "$?" -eq 0 ]
  conferir "$opcao não grava no estado" [ "$antes" == "$(retrato)" ]
done
conferir "a órfã continua no estado depois das consultas" test -e "$estado/orfa.json"
conferir "--lista mostra a sessão viva" grep -q $'^trabalhando\tviva\t' "$tmp/antes--lista"
conferir "--lista mostra a concluída dentro do prazo" grep -q $'^concluido\tconcluida\t' "$tmp/antes--lista"
conferir "--lista mostra a sessão que dá para restaurar" grep -q $'^interrompido\tcaida\t' "$tmp/antes--lista"
conferir "--lista tem só as três sessões" [ "$(cut -f2 "$tmp/antes--lista" | sort | tr '\n' ' ')" == "caida concluida viva " ]
conferir "--waybar conta as três sessões" \
  jq -e '.text == "󰚩 3  󰑮 1  󰄬 1  󰜺 1" and .class == "trabalhando" and (.tooltip | type) == "string"' "$tmp/antes--waybar" >/dev/null

conferir "--limpar-orfaos sai com 0" agentes --limpar-orfaos
conferir "--limpar-orfaos remove a órfã" test ! -e "$estado/orfa.json"
conferir "--limpar-orfaos remove a concluída vencida" test ! -e "$estado/vencida.json"
conferir "--limpar-orfaos mantém a sessão viva" test -e "$estado/viva.json"
conferir "--limpar-orfaos mantém a concluída dentro do prazo" test -e "$estado/concluida.json"
conferir "--limpar-orfaos marca como interrompida a sessão que dá para restaurar" \
  jq -e '.estado == "interrompido"' "$estado/caida.json" >/dev/null

# A órfã já não aparecia na consulta; sem ela no disco, a saída é a mesma. A
# marcação de interrompida regrava "atualizado", quarto campo da lista.
for opcao in "${consultas[@]}"; do
  agentes "$opcao" >"$tmp/depois$opcao" 2>&1
  conferir "$opcao sai com 0 depois da limpeza" [ "$?" -eq 0 ]
  conferir "$opcao igual antes e depois da limpeza" \
    cmp -s <(cut -f1-3,5- "$tmp/antes$opcao") <(cut -f1-3,5- "$tmp/depois$opcao")
done

python3 - "$repo_jangada" "$tmp" <<'PYTEST' || falhas=$((falhas + 1))
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

repo, tmp = map(Path, sys.argv[1:])
origem = tmp / 'json-state'
pasta = origem / 'jangada/agentes'
ambiente = dict(os.environ, PATH=str(tmp / 'bin') + ':' + os.environ['PATH'],
                HOME=str(tmp / 'home'), XDG_CONFIG_HOME=str(tmp / 'config'),
                XDG_STATE_HOME=str(origem), JANGADA_PATH=str(repo))
for nome in ('JANGADA_ISOLADO', 'TMUX', 'JANGADA_AGENTES_GUARDAR'):
    ambiente.pop(nome, None)


def consultar(opcao='--lista-json'):
    return subprocess.run([str(repo / 'bin/jangada-agentes'), opcao],
                          capture_output=True, env=ambiente, timeout=5)


def retrato():
    return [(str(p.relative_to(origem)), p.lstat().st_mode,
             hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() and not p.is_symlink() else '')
            for p in sorted(origem.rglob('*')) if not p.is_fifo()]


# Estado ausente não recebe diretórios, inclusive nas consultas antigas.
for opcao in ('--lista-json', '--lista', '--lista-atualizada', '--waybar'):
    r = consultar(opcao)
    assert r.returncode == 0, r.stderr
    assert not origem.exists()
assert json.loads(consultar().stdout)['sessoes'][0]['nome'] == 'viva'
tmux = tmp / 'bin/tmux'
original_tmux = tmux.read_text()
tmux.write_text('#!/bin/sh\nexit 0\n')
assert json.loads(consultar().stdout) == {'versao': 1, 'sessoes': []}
assert not origem.exists()
tmux.write_text('#!/bin/sh\necho ../../fora\n')
r = consultar()
assert r.returncode == 1 and not r.stdout and not origem.exists()
tmux.write_text(original_tmux)
pasta.mkdir(parents=True)
agora = subprocess.check_output(['date', '-Iseconds'], text=True).strip()
texto = 'ação\nlinha dois\t雪 &lt;b&gt; <b>literal</b>'
viva = dict(estado='aguardando', dir=str(tmp / 'pasta'), atualizado=agora,
            ramo='agente/<ramo>&lt;', tarefa=texto, agente='codex', raiz='/projeto/raiz',
            mensagem=texto, desde=agora, inicio='a' * 40, coordenador='claude',
            revisor='claude', comando='segredo que não sai', conversa='privada')
(pasta / 'viva.json').write_text(json.dumps(viva))
(pasta / 'retida.json').write_text(json.dumps(dict(estado='concluido', atualizado=agora)))
(pasta / 'interrompida.json').write_text(json.dumps(dict(estado='interrompido', atualizado=agora)))
(pasta / 'restauravel.json').write_text(json.dumps(dict(agente='codex', dir=str(tmp / 'pasta'))))
(pasta / 'expirada.json').write_text(json.dumps(dict(estado='concluido', atualizado='2000-01-01')))
(pasta / 'pid.json').write_text(json.dumps(dict(estado='ativo', pid=os.getpid())))
# Contextos e pareceres não são abertos, mesmo quando não são arquivos regulares.
(pasta / 'revisao-um-r1.json').write_text('não é JSON')
os.mkfifo(pasta / 'validacao-um-r1.contexto.json')
(pasta / 'delegacao-exemplo.json').write_text('não é sessão')
antes = retrato()
r = consultar()
assert r.returncode == 0, r.stderr
resultado = json.loads(r.stdout)
assert resultado['versao'] == 1
sessoes = {s['nome']: s for s in resultado['sessoes']}
assert set(sessoes) == {'viva', 'retida', 'interrompida', 'restauravel', 'pid'}
assert sessoes['restauravel']['estado'] == 'interrompido'
assert sessoes['viva']['tarefa'] == texto == sessoes['viva']['mensagem']
assert sessoes['viva']['desde'] == agora
assert sessoes['viva']['projeto'] == 'raiz'
assert not {'inicio', 'comando', 'conversa', 'pid'} & sessoes['viva'].keys()
assert retrato() == antes
for opcao in ('--lista', '--lista-atualizada'):
    r = consultar(opcao)
    assert r.returncode == 0, r.stderr
    linha = next(l for l in r.stdout.decode().splitlines() if l.split('\t')[1] == 'viva')
    assert linha == '\t'.join(('aguardando', 'viva', str(tmp / 'pasta'), agora,
                               'agente/&lt;ramo&gt;&amp;lt;', 'ação'))
    assert retrato() == antes

# Todo erro recusa a resposta integral; nunca publica uma lista parcial.
ruim = pasta / 'ruim.json'
for conteudo in ('{', '[]', json.dumps(dict(mensagem=[])),
                 json.dumps(dict(tarefa='x' * 16001)), json.dumps(dict(pid=True)),
                 'x' * (1024 * 1024 + 1)):
    ruim.write_text(conteudo)
    antes = retrato()
    r = consultar()
    assert r.returncode == 1 and not r.stdout and r.stderr, (conteudo[:30], r)
    assert retrato() == antes
ruim.unlink()
for tipo in ('link', 'fifo', 'diretorio'):
    if tipo == 'link':
        ruim.symlink_to(pasta / 'viva.json')
    elif tipo == 'fifo':
        os.mkfifo(ruim)
    else:
        ruim.mkdir()
    r = consultar()
    assert r.returncode == 1 and not r.stdout and r.stderr, tipo
    ruim.rmdir() if tipo == 'diretorio' else ruim.unlink()
(pasta / 'nome inválido.json').write_text('{}')
assert consultar().returncode == 1
(pasta / 'nome inválido.json').unlink()
# A pasta de sessões também não pode ser link.
pasta.rename(pasta.with_name('originais'))
pasta.symlink_to(pasta.with_name('originais'), target_is_directory=True)
assert consultar().returncode == 1
pasta.unlink()
pasta.with_name('originais').rename(pasta)
# Resposta agregada limitada, mesmo com cada registro dentro do limite.
for i in range(80):
    (pasta / f'grande-{i}.json').write_text(json.dumps(dict(estado='concluido', atualizado=agora, tarefa='x' * 16000)))
r = consultar()
assert r.returncode == 1 and not r.stdout and b'1 MiB' in r.stderr
for p in pasta.glob('grande-*.json'):
    p.unlink()
# Core e fachada funcionam sem pastas Shell e Monitor.
minimo = tmp / 'core-sem-interface'
(minimo / 'bin').mkdir(parents=True)
(minimo / 'core/nucleo').mkdir(parents=True)
for nome, fonte in (('bin/jangada-config', 'bin/jangada-config'),
                    ('bin/jangada-agentes', 'core/bin/jangada-agentes'),
                    ('core/nucleo/sessoes.py', 'core/nucleo/sessoes.py')):
    shutil.copy2(repo / fonte, minimo / nome)
ambiente['JANGADA_PATH'] = str(minimo)
r = subprocess.run([str(minimo / 'bin/jangada-agentes'), '--lista-json'],
                   env=ambiente, capture_output=True, timeout=5)
assert r.returncode == 0, r.stderr
assert json.loads(r.stdout) == resultado
print('consulta JSON: seleção, TSV, limites, recusas e Core sem interface passaram')
PYTEST

if ((falhas)); then
  echo "$falhas falha(s)"
  exit 1
fi
echo "todos os testes do contrato de consulta passaram"
