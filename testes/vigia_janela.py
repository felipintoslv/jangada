#!/usr/bin/env python3
"""Testa a janela Qt da conversa do Vigia fora da tela, com agy e jangada-vigia falsos."""
import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
repo = Path(__file__).resolve().parents[1]
pasta_vigia = repo / 'menus/vigia' if (repo / 'menus/vigia').exists() else repo / 'shell/menus/vigia'
sys.path.insert(0, str(pasta_vigia))
try:
    import PyQt6  # noqa: F401
except ImportError:
    print('PyQt6 ausente; testes da janela do vigia ignorados')
    sys.exit(1 if os.environ.get('CI') else 0)
from PyQt6.QtCore import QTimer, Qt  # noqa: E402
from PyQt6.QtTest import QTest  # noqa: E402
from PyQt6.QtWidgets import QApplication, QPlainTextEdit  # noqa: E402
import janela as modulo  # noqa: E402

AGY_FALSO = r'''#!@PYTHON@
import json, os, sys, time
log = os.environ["AGY_FALSO_LOG"]
try:
    with open(log) as f:
        n = sum(1 for _ in f)
except FileNotFoundError:
    n = 0
modos = os.environ.get("AGY_FALSO_MODOS", "ok").split(",")
modo = modos[min(n, len(modos) - 1)]
with open(log, "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "cwd": os.getcwd(), "pid": os.getpid()}) + "\n")
if modo == "falha":
    sys.stderr.write("sem login\x1b[2J no agy\n")
    sys.exit(3)
if modo == "lento":
    time.sleep(30)
if modo == "orfao":
    import subprocess
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    with open(log, "a") as f:
        f.write(json.dumps({"filho": filho.pid}) + "\n")
    sys.exit(0)
resposta = f"resposta {n + 1}"
if modo == "html":
    resposta = "<b>negrito</b> <img src='file:///etc/passwd'> \x1b[31mvermelho\x1b[0m \x1b]0;titulo\x07fim"
print(json.dumps({"conversation_id": "conv-abc123", "status": "SUCCESS", "response": resposta}))
'''

VIGIA_FALSO = r'''#!@PYTHON@
import json, os, sys, time
pasta = os.path.dirname(os.path.abspath(__file__))
with open(os.path.join(pasta, "vigia.log"), "a") as f:
    f.write(json.dumps({"argv": sys.argv[1:], "pid": os.getpid()}) + "\n")
modo = os.environ.get("VIGIA_FALSO_MODO", "ok")
if modo == "falha":
    sys.stderr.write("erro: retrato JSON não encontrado\x1b[2J\n")
    sys.exit(1)
if modo == "lento":
    time.sleep(30)
if modo == "orfao":
    import subprocess
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    with open(os.path.join(pasta, "vigia.log"), "a") as f:
        f.write(json.dumps({"filho": filho.pid}) + "\n")
    sys.exit(0)
if modo == "teimoso":
    import signal, subprocess
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    filho = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    with open(os.path.join(pasta, "vigia.log"), "a") as f:
        f.write(json.dumps({"filho": filho.pid, "grupo": os.getpgid(0)}) + "\n")
    time.sleep(60)
print(json.dumps({"versao": 1, "gerado_em": "2026-10-26T10:00:00-03:00", "servicos": {"falhas": "nenhuma"}}))
'''

# Abre a janela em processo próprio, espera o retrato deixar o filho,
# opcionalmente clica em Cancelar e fecha; o processo sai em seguida.
MOTORISTA = r'''
import os, sys, time
from pathlib import Path
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, sys.argv[1])
from PyQt6.QtWidgets import QApplication
app = QApplication([])
import janela
vigia, estado, log, modo = sys.argv[2:6]
j = janela.Janela(vigia, estado)
j.show()
limite = time.monotonic() + 20
while time.monotonic() < limite and not (Path(log).exists() and '"filho"' in Path(log).read_text()):
    app.processEvents()
    time.sleep(0.01)
if modo == "cancelar":
    j.cancelar_botao.click()
j.close()
'''

falhas = 0
APP = QApplication([])


def conferir(descricao, condicao):
    global falhas
    if condicao:
        print(f'ok    {descricao}')
    else:
        print(f'FALHA {descricao}')
        falhas += 1


def aguardar(condicao, prazo=15):
    limite = time.monotonic() + prazo
    while not condicao() and time.monotonic() < limite:
        APP.processEvents()
        time.sleep(0.01)
    APP.processEvents()
    return condicao()


def membros_do_grupo(grupo):
    """Processos vivos (não zumbis) cujo grupo é o indicado."""
    membros = []
    for entrada in Path('/proc').iterdir():
        if not entrada.name.isdigit():
            continue
        try:
            campos = (entrada / 'stat').read_text().split(')')[-1].split()
        except OSError:
            continue
        if campos[0] != 'Z' and int(campos[2]) == grupo:
            membros.append(int(entrada.name))
    return membros


def vivo(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    # Zumbi ainda responde ao kill 0; conta como encerrado.
    try:
        with open(f'/proc/{pid}/stat') as arq:
            return arq.read().split(')')[-1].split()[0] != 'Z'
    except OSError:
        return False


with tempfile.TemporaryDirectory() as pasta:
    tmp = Path(pasta)
    bin_falso = tmp / 'bin'
    bin_falso.mkdir()
    agy = bin_falso / 'agy'
    agy.write_text(AGY_FALSO.replace('@PYTHON@', sys.executable))
    agy.chmod(0o755)
    vigia = bin_falso / 'jangada-vigia'
    vigia.write_text(VIGIA_FALSO.replace('@PYTHON@', sys.executable))
    vigia.chmod(0o755)
    log_agy = tmp / 'agy.log'
    log_vigia = bin_falso / 'vigia.log'
    estado = tmp / 'estado/jangada/vigia'
    estado.mkdir(parents=True)
    conversas = estado / 'conversas'
    propostas = estado / 'propostas'
    os.environ['XDG_CONFIG_HOME'] = str(tmp / 'config')

    def chamadas(log=log_agy):
        try:
            return [json.loads(linha) for linha in log.read_text().splitlines()]
        except FileNotFoundError:
            return []

    def nova(modos='ok', modo_vigia='ok', retrato=None):
        log_agy.unlink(missing_ok=True)
        log_vigia.unlink(missing_ok=True)
        os.environ['VIGIA_FALSO_MODO'] = modo_vigia
        ambiente = dict(os.environ, PATH=f'{bin_falso}:/usr/bin:/bin', AGY_FALSO_LOG=str(log_agy),
                        AGY_FALSO_MODOS=modos)
        j = modulo.Janela(vigia, estado, retrato, ambiente=ambiente)
        j.show()
        return j

    def conversa_vazia():
        return not conversas.exists() or list(conversas.iterdir()) == []

    def texto(j):
        return j.historico.toPlainText()

    # Abre, mostra a espera e a primeira resposta
    j = nova()
    conferir('ao abrir mostra "Gerando o retrato do sistema..."',
             j.situacao.text().startswith('Gerando o retrato do sistema'))
    conferir('ao abrir, Cancelar visível e Enviar desligado',
             not j.cancelar_botao.isHidden() and not j.enviar_botao.isEnabled())
    conferir('primeira resposta aparece no histórico', aguardar(lambda: 'resposta 1' in texto(j)))
    conferir('cabeçalho com título Vigia e logo', j.cabecalho.titulo.text() == 'Vigia'
             and not j.cabecalho.marca.pixmap().isNull())
    conferir('aviso fixo do que sai da máquina, com link para riscos.md',
             'agy' in j.aviso.text() and 'retrato' in j.aviso.text()
             and modulo.RISCOS == repo / 'docs/vigia/riscos.md' and modulo.RISCOS.exists())
    conferir('retrato pedido ao jangada-vigia com argumentos em lista',
             chamadas(log_vigia)[0]['argv'] == ['retrato-conversa'])
    conferir('depois da resposta, Enviar ligado e Cancelar escondido',
             j.enviar_botao.isEnabled() and j.cancelar_botao.isHidden())
    conferir('Salvar proposta desligado sem proposta, com o motivo ao lado',
             not j.salvar_botao.isEnabled() and j.salvar_motivo.motivo.text() == modulo.SEM_PROPOSTA)

    # Pergunta por Ctrl+Enter, numa linha de trabalho
    linhas = []
    chamar = j.tentativa.conversa._chamar

    def registrar(argumento):
        linhas.append(threading.current_thread() is threading.main_thread())
        return chamar(argumento)
    j.tentativa.conversa._chamar = registrar
    j.pergunta.setPlainText('Por que a barra falhou?')
    j.pergunta.setFocus()
    QTest.keyClick(j.pergunta, Qt.Key.Key_Return, Qt.KeyboardModifier.ControlModifier)
    conferir('Ctrl+Enter envia a pergunta', aguardar(lambda: 'resposta 2' in texto(j)))
    conferir('pergunta aparece no histórico e o campo esvazia',
             'Você:\nPor que a barra falhou?' in texto(j) and j.pergunta.toPlainText() == '')
    conferir('chamada ao motor fora da linha principal', linhas == [False])
    conferir('pergunta segue com --conversation', '--conversation' in chamadas()[-1]['argv'])

    # Salvar só grava quando clicado, dentro de vigia/propostas
    conferir('nenhuma proposta gravada antes de pedir', not propostas.exists() or not list(propostas.iterdir()))
    j.proposta_botao.click()
    conferir('proposta aparece no histórico', aguardar(lambda: 'resposta 3' in texto(j)))
    conferir('Salvar proposta liga depois da proposta', j.salvar_botao.isEnabled()
             and j.salvar_motivo.motivo.isHidden())
    conferir('pedir a proposta não grava nada', not propostas.exists() or not list(propostas.iterdir()))
    j.salvar_botao.click()
    salvas = list(propostas.iterdir()) if propostas.exists() else []
    conferir('Salvar grava um arquivo em $JANGADA_ESTADO/vigia/propostas',
             len(salvas) == 1 and salvas[0].parent == propostas and 'resposta 3' in salvas[0].read_text())
    conferir('caminho da proposta salva aparece no histórico', str(salvas[0]) in texto(j) if salvas else False)
    pasta_conversa = chamadas()[0]['cwd']
    conferir('pasta temporária existe durante a conversa', os.path.isdir(pasta_conversa))
    j.fechar_botao.click()
    conferir('Fechar apaga a pasta temporária', not os.path.exists(pasta_conversa) and conversa_vazia())
    conferir('Fechar fecha a janela', not j.isVisible())

    # A interface responde enquanto o agy demora; Cancelar mata o agy e apaga a pasta
    j = nova('ok,lento')
    aguardar(lambda: 'resposta 1' in texto(j))
    j.pergunta.setPlainText('pergunta demorada')
    j.enviar_botao.click()
    conferir('agy lento foi chamado', aguardar(lambda: len(chamadas()) == 2))
    disparou = []
    QTimer.singleShot(50, lambda: disparou.append(True))
    inicio = time.monotonic()
    conferir('relógio da interface dispara enquanto o agy demora',
             aguardar(lambda: disparou, 2) and time.monotonic() - inicio < 1.5 and j.linha is not None)
    conferir('contador de espera avança', aguardar(lambda: j.situacao.text().endswith(' 1 s'), 3))
    conferir('espera mostra Cancelar e desliga Enviar e Pedir proposta',
             not j.cancelar_botao.isHidden() and not j.enviar_botao.isEnabled()
             and not j.proposta_botao.isEnabled())
    pid = chamadas()[-1]['pid']
    pasta_conversa = chamadas()[-1]['cwd']
    j.cancelar_botao.click()
    conferir('Cancelar apaga a pasta temporária', not os.path.exists(pasta_conversa) and conversa_vazia())
    conferir('Cancelar encerra o agy', aguardar(lambda: not vivo(pid), 5))
    conferir('depois de Cancelar, Nova conversa visível e Enviar desligado',
             not j.recomecar_botao.isHidden() and not j.enviar_botao.isEnabled())
    aguardar(lambda: False, 0.3)
    conferir('resposta cancelada não aparece depois', 'Erro' not in j.erro.text() and 'resposta 2' not in texto(j))
    j.close()

    # Cancelar durante o retrato
    j = nova(modo_vigia='lento')
    conferir('retrato lento foi pedido', aguardar(lambda: chamadas(log_vigia)))
    pid_vigia = chamadas(log_vigia)[0]['pid']
    j.cancelar_botao.click()
    conferir('Cancelar no retrato encerra o jangada-vigia', aguardar(lambda: not vivo(pid_vigia), 5))
    aguardar(lambda: j.tentativa.conversa.pasta is not None, 0.5)
    conferir('Cancelar no retrato não chama o agy nem deixa pasta', chamadas() == [] and conversa_vazia())
    j.close()

    # Pai que sai deixando um filho com a saída aberta: Cancelar mata o grupo
    j = nova('ok,orfao')
    aguardar(lambda: 'resposta 1' in texto(j))
    j.pergunta.setPlainText('pergunta com filho')
    j.enviar_botao.click()
    conferir('agy que deixa filho foi chamado', aguardar(lambda: len(chamadas()) == 3))
    pid, filho = chamadas()[1]['pid'], chamadas()[2]['filho']
    pasta_conversa = chamadas()[1]['cwd']
    conferir('agy sai e o filho segura a espera',
             aguardar(lambda: not vivo(pid), 5) and vivo(filho) and j.linha is not None)
    j.cancelar_botao.click()
    conferir('Cancelar com o agy já encerrado mata o filho', aguardar(lambda: not vivo(filho), 5))
    conferir('Cancelar com filho apaga a pasta temporária', not os.path.exists(pasta_conversa) and conversa_vazia())
    j.close()

    j = nova(modo_vigia='orfao')
    conferir('retrato que deixa filho foi pedido', aguardar(lambda: len(chamadas(log_vigia)) == 2))
    pid_vigia, filho = chamadas(log_vigia)[0]['pid'], chamadas(log_vigia)[1]['filho']
    conferir('retrato sai e o filho segura a espera',
             aguardar(lambda: not vivo(pid_vigia), 5) and vivo(filho) and j.linha is not None)
    j.cancelar_botao.click()
    conferir('Cancelar com o retrato já encerrado mata o filho', aguardar(lambda: not vivo(filho), 5))
    aguardar(lambda: j.linha is None, 5)
    conferir('Cancelar no retrato com filho não chama o agy nem deixa pasta', chamadas() == [] and conversa_vazia())
    j.close()

    # Fechar durante a espera do agy
    j = nova('lento')
    conferir('abertura lenta chamou o agy', aguardar(lambda: chamadas()))
    pid = chamadas()[0]['pid']
    pasta_conversa = chamadas()[0]['cwd']
    j.close()
    conferir('Fechar na espera apaga a pasta e encerra o agy',
             not os.path.exists(pasta_conversa) and conversa_vazia() and aguardar(lambda: not vivo(pid), 5))

    # HTML e sequência de controle aparecem como texto
    j = nova('html')
    conferir('resposta com HTML chega', aguardar(lambda: 'negrito' in texto(j)))
    conferir('histórico é texto simples', isinstance(j.historico, QPlainTextEdit))
    conferir('HTML aparece literal', "<b>negrito</b> <img src='file:///etc/passwd'>" in texto(j))
    conferir('sequência de controle removida', '\x1b' not in texto(j) and '\x07' not in texto(j)
             and 'vermelho' in texto(j))
    conferir('rótulos de situação e erro em texto simples',
             j.situacao.textFormat() == Qt.TextFormat.PlainText and j.erro.textFormat() == Qt.TextFormat.PlainText)
    j.close()

    # Erro do agy aparece na janela, sem fechar
    j = nova('falha')
    conferir('erro do agy na abertura aparece na janela',
             aguardar(lambda: 'código 3' in j.erro.text()) and j.isVisible() and not j.erro.isHidden())
    conferir('erro sem sequência de controle', '\x1b' not in j.erro.text())
    conferir('erro na abertura apaga a pasta e oferece Nova conversa',
             conversa_vazia() and not j.recomecar_botao.isHidden())
    os.environ['VIGIA_FALSO_MODO'] = 'ok'
    j.ambiente['AGY_FALSO_MODOS'] = 'ok'
    log_agy.unlink()
    j.recomecar_botao.click()
    conferir('Nova conversa abre outra conversa', aguardar(lambda: 'resposta 1' in texto(j))
             and j.erro.isHidden() and j.enviar_botao.isEnabled())
    j.close()

    j = nova('ok,falha')
    aguardar(lambda: 'resposta 1' in texto(j))
    j.pergunta.setPlainText('outra')
    j.enviar_botao.click()
    conferir('erro numa pergunta aparece e a conversa continua',
             aguardar(lambda: 'código 3' in j.erro.text()) and j.enviar_botao.isEnabled()
             and os.path.isdir(chamadas()[0]['cwd']))
    j.close()

    j = nova(modo_vigia='falha')
    conferir('erro do retrato aparece na janela',
             aguardar(lambda: 'não foi possível gerar o retrato' in j.erro.text())
             and '\x1b' not in j.erro.text() and chamadas() == [])
    j.close()

    j = nova(retrato='retrato-20261026-100000-abc.json')
    aguardar(lambda: 'resposta 1' in texto(j))
    conferir('--retrato segue para o retrato-conversa',
             chamadas(log_vigia)[0]['argv'] == ['retrato-conversa', '--retrato', 'retrato-20261026-100000-abc.json'])
    j.close()

    # Retrato que ignora TERM e deixa um filho: depois que o processo da
    # janela sai, nada do grupo segue vivo, com ou sem Cancelar antes
    for acao in ('cancelar', 'fechar'):
        log_vigia.unlink(missing_ok=True)
        motorista = subprocess.run(
            [sys.executable, '-I', '-c', MOTORISTA, str(pasta_vigia), str(vigia), str(estado), str(log_vigia), acao],
            env=dict(os.environ, PATH=f'{bin_falso}:/usr/bin:/bin', VIGIA_FALSO_MODO='teimoso'),
            capture_output=True, text=True, timeout=60)
        registros = chamadas(log_vigia)
        if len(registros) < 2:
            conferir(f'retrato teimoso começou ({acao})', False)
            continue
        pid_vigia, filho, grupo = registros[0]['pid'], registros[1]['filho'], registros[1]['grupo']
        conferir(f'janela sai sem erro depois de {acao} com retrato teimoso',
                 motorista.returncode == 0 and 'Traceback' not in motorista.stderr)
        conferir(f'{acao} com retrato teimoso: pai e filho encerrados ao sair',
                 not vivo(pid_vigia) and not vivo(filho))
        conferir(f'{acao} com retrato teimoso: nenhum processo do grupo segue vivo',
                 grupo == pid_vigia and membros_do_grupo(grupo) == [])
        for pid in (pid_vigia, filho):
            if vivo(pid):
                os.kill(pid, signal.SIGKILL)
        conferir(f'{acao} com retrato teimoso não deixa pasta', conversa_vazia())

    # Uma segunda janela não abre: a trava avisa e a primeira continua
    ambiente = dict(os.environ, PATH=f'{bin_falso}:{os.environ["PATH"]}', AGY_FALSO_LOG=str(log_agy),
                    AGY_FALSO_MODOS='ok', VIGIA_FALSO_MODO='lento')
    ambiente.pop('HYPRLAND_INSTANCE_SIGNATURE', None)
    log_vigia.unlink(missing_ok=True)
    comando = [sys.executable, '-I', str(pasta_vigia / 'janela.py'), '--vigia', str(vigia), '--pasta', str(estado)]
    primeira = subprocess.Popen(comando, env=ambiente, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

    def travada():
        try:
            with open(estado / 'janela.trava') as arq:
                fcntl.flock(arq, fcntl.LOCK_EX | fcntl.LOCK_NB)
                return False
        except BlockingIOError:
            return True
        except FileNotFoundError:
            return False
    conferir('primeira janela segura a trava', aguardar(lambda: travada() and chamadas(log_vigia), 20))
    log_hyprctl = tmp / 'hyprctl.log'
    hyprctl = bin_falso / 'hyprctl'
    hyprctl.write_text('#!/usr/bin/env python3\nimport json, os, sys\n'
                       'with open(os.environ["HYPRCTL_FALSO_LOG"], "a") as arq:\n'
                       '    arq.write(json.dumps(sys.argv[1:]) + "\\n")\n')
    hyprctl.chmod(0o755)
    segunda = subprocess.run(comando, env=dict(ambiente, HYPRLAND_INSTANCE_SIGNATURE='teste',
                                               HYPRCTL_FALSO_LOG=str(log_hyprctl)),
                             capture_output=True, text=True, timeout=20)
    conferir('segunda chamada não abre outra janela e avisa',
             segunda.returncode == 0 and 'já está aberto' in segunda.stderr and primeira.poll() is None)
    expressao = 'hl.dsp.focus({ window = "class:^(org\\\\.jangada\\\\.vigia)$" })'
    conferir('segunda chamada traz a janela por expressão Lua do hyprctl',
             chamadas(log_hyprctl) == [['dispatch', expressao]])
    lua = shutil.which('lua5.4') or shutil.which('lua')
    if lua:
        foco = subprocess.run([lua, '-e', 'hl = { dsp = { focus = function(t) io.write(t.window) end } }; '
                               + expressao], capture_output=True, text=True, timeout=10)
        conferir('expressão de foco é Lua válida e chega com a classe escapada',
                 foco.returncode == 0 and foco.stdout == 'class:^(org\\.jangada\\.vigia)$')
    pid_vigia = chamadas(log_vigia)[0]['pid']
    primeira.send_signal(signal.SIGTERM)
    try:
        _, erros = primeira.communicate(timeout=20)
    except subprocess.TimeoutExpired:
        primeira.kill()
        _, erros = primeira.communicate()
    conferir('SIGTERM fecha a janela sem traceback', primeira.returncode == 0 and 'Traceback' not in erros.decode())
    conferir('SIGTERM encerra o retrato em curso', aguardar(lambda: not vivo(pid_vigia), 10))
    conferir('trava liberada ao fechar', not travada())
    conferir('nenhuma pasta de conversa sobrou', conversa_vazia())

    # retrato-conversa: o mesmo mascaramento da conversa no terminal
    casa = tmp / 'casa'
    real = dict(os.environ, HOME=str(casa), XDG_STATE_HOME=str(tmp / 'estado-real'), JANGADA_PATH=str(repo))
    pasta_real = tmp / 'estado-real/jangada/vigia'
    pasta_real.mkdir(parents=True)
    (pasta_real / 'retrato-20261026-100000-abc.json').write_text(json.dumps(
        {'versao': 1, 'log': f'falha em {casa}/.config/x'}))
    r = subprocess.run([str(repo / 'bin/jangada-vigia'), 'retrato-conversa', '--retrato',
                        'retrato-20261026-100000-abc.json'], capture_output=True, text=True, env=real)
    conferir('retrato-conversa imprime o retrato mascarado',
             r.returncode == 0 and json.loads(r.stdout)['log'].startswith('falha em ~/.config/x')
             and str(casa) not in r.stdout)
    r = subprocess.run([str(repo / 'bin/jangada-vigia'), 'retrato-conversa', '--retrato', '../retrato-x.json'],
                       capture_output=True, text=True, env=real)
    conferir('retrato-conversa recusa caminho fora da pasta do Vigia', r.returncode == 1 and r.stdout == '')
    r = subprocess.run([str(repo / 'bin/jangada-vigia'), 'janela', '--x'], capture_output=True, text=True, env=real)
    conferir('jangada-vigia janela recusa argumento inesperado', r.returncode == 1 and 'inesperado' in r.stderr)

if falhas:
    print(f'{falhas} teste(s) da janela do vigia falharam')
    sys.exit(1)
print('todos os testes da janela do vigia passaram')
