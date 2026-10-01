"""Execução cancelável e eventos do CLI, sem acesso a ferramentas dos modelos."""
import codecs
import contextvars
import json
import os
from pathlib import Path
import selectors
import signal
import subprocess
import tempfile
import threading
import time

CONTEXTO = contextvars.ContextVar("pescador_contexto", default=None)


class ConsultaCancelada(Exception):
    pass


class Contexto:
    def __init__(self, callback=None, cancelar=None):
        self.callback = callback or (lambda evento: None)
        self.cancelar = cancelar or threading.Event()
        self.metricas = []
        self.rascunho = ""
        self.trava = threading.Lock()

    def conferir(self):
        if self.cancelar.is_set():
            raise ConsultaCancelada()

    def emitir(self, tipo, **dados):
        self.conferir()
        with self.trava:
            self.callback({"tipo": tipo, **dados})


def encerrar(proc):
    # O grupo inclui o launcher e o bubblewrap; mate também descendentes.
    try:
        os.killpg(proc.pid, signal.SIGTERM)
        proc.wait(timeout=2)
    except subprocess.TimeoutExpired:
        pass
    except ProcessLookupError:
        proc.wait()
    finally:
        # O launcher pode sair antes de um filho que ignore SIGTERM.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()


def executar(motor, exe, pedido, transmitir=False):
    ctx = CONTEXTO.get() or Contexto()
    ctx.conferir()
    raiz = Path(os.environ.get("JANGADA_PATH", Path(__file__).resolve().parents[2]))
    launcher = raiz / "bin/jangada-pescador-modelo"
    estado = Path(os.environ.get("JANGADA_ESTADO", Path.home() / ".local/state/jangada"))
    pasta = estado / "pescador/execucoes"
    if pasta.is_symlink() or pasta.parent.is_symlink():
        return False, "A pasta de execução não pode ser um link simbólico."
    pasta.mkdir(parents=True, exist_ok=True, mode=0o700)
    if transmitir:
        ctx.rascunho = ""
    inicio = time.monotonic()
    primeiro = None
    resposta = ""
    erro = ""
    parcial = False
    final = None
    falhou = False
    pendente = ""
    total = 0
    proc = None

    def evento(linha):
        nonlocal resposta, parcial, final, falhou, primeiro
        try:
            obj = json.loads(linha)
        except ValueError:
            return
        if not isinstance(obj, dict):
            return
        delta = obj.get("event", {}).get("delta", {}) if isinstance(obj.get("event"), dict) else {}
        trecho = delta.get("text", "") if delta.get("type") == "text_delta" else ""
        if trecho:
            parcial = True
        elif obj.get("type") == "assistant" and not parcial:
            mensagem = obj.get("message") or {}
            conteudo = mensagem.get("content", []) if isinstance(mensagem, dict) else []
            trecho = "".join(c.get("text", "") for c in conteudo if isinstance(c, dict) and c.get("type") == "text")
        if isinstance(trecho, str) and trecho:
            resposta += trecho
            primeiro = primeiro or round(time.monotonic() - inicio, 3)
            if transmitir:
                ctx.rascunho = resposta
                ctx.emitir("trecho", texto=trecho)
        if obj.get("type") == "result":
            falhou = bool(obj.get("is_error")) or obj.get("subtype", "success") not in ("success", "")
            final = obj.get("result")

    try:
        with tempfile.TemporaryDirectory(prefix="consulta-", dir=pasta) as cwd, tempfile.TemporaryFile() as entrada:
            entrada.write(pedido.encode()); entrada.seek(0)
            env = dict(os.environ, JANGADA_HOOK_DESLIGADO="1")
            env.pop("JANGADA_SESSAO", None)
            proc = subprocess.Popen([str(launcher), motor, exe], cwd=cwd, env=env,
                                    stdin=entrada, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    start_new_session=True)
            with selectors.DefaultSelector() as seletor:
                seletor.register(proc.stdout, selectors.EVENT_READ, "saida")
                seletor.register(proc.stderr, selectors.EVENT_READ, "erro")
                decoder = codecs.getincrementaldecoder("utf-8")("replace")
                while seletor.get_map():
                    ctx.conferir()
                    if time.monotonic() - inicio > 180:
                        raise TimeoutError("O modelo não respondeu em 180 segundos.")
                    for chave, _ in seletor.select(0.1):
                        dados = os.read(chave.fileobj.fileno(), 65536)
                        if not dados:
                            seletor.unregister(chave.fileobj)
                            continue
                        if chave.data == "erro":
                            erro = (erro + dados.decode("utf-8", "replace"))[-4000:]
                            continue
                        total += len(dados)
                        if total > 4_000_000:
                            raise ValueError("Resposta acima do limite de tamanho.")
                        pendente += decoder.decode(dados)
                        while "\n" in pendente:
                            linha, pendente = pendente.split("\n", 1)
                            evento(linha)
                pendente += decoder.decode(b"", final=True)
                if pendente.strip():
                    evento(pendente)
            while proc.poll() is None:
                ctx.conferir()
                if time.monotonic() - inicio > 180:
                    raise TimeoutError("O modelo não terminou em 180 segundos.")
                ctx.cancelar.wait(0.1)
            ctx.conferir()
            if proc.returncode or falhou:
                return False, "Falha do modelo: " + (erro.strip()[-500:] or str(final or "resposta recusada"))
            if isinstance(final, str) and final.strip():
                resposta = final.strip()
            return bool(resposta.strip()), resposta.strip() or "O modelo não produziu uma resposta."
    except ConsultaCancelada:
        raise
    except (OSError, ValueError, TimeoutError) as exc:
        return False, str(exc)
    finally:
        if proc is not None:
            # Também quando o launcher saiu mas deixou descendentes no grupo.
            encerrar(proc)
            proc.stdout.close(); proc.stderr.close()
        with ctx.trava:
            ctx.metricas.append({"motor": motor, "segundos": round(time.monotonic() - inicio, 3),
                                 "primeiro_texto_segundos": primeiro})
