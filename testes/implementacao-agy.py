#!/usr/bin/env python3
"""Percurso sintético completo, sem modelos remotos, e negativos do contrato."""

import importlib.util
import fcntl
import json
import os
from pathlib import Path
import subprocess
import signal
import tempfile
import unittest

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("implementacao", REPO / "core/delegacao/implementacao.py")
modulo = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modulo)


class Implementacao(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.raiz = self.tmp / "projeto"
        self.raiz.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.casa = self.tmp / "casa"
        cfg = self.casa / ".gemini/config"
        cfg.mkdir(parents=True)
        cli = self.casa / ".gemini/antigravity-cli"
        cli.mkdir()
        agentes = self.tmp / "agentes/implementador"
        agentes.mkdir(parents=True)
        (agentes / "agent.md").write_text((REPO / "core/agentes/agy/agents/implementador/agent.md").read_text())
        (cfg / "agents.json").write_text(json.dumps({"entries": [{"path": str(agentes.parent)}]}))
        (cli / "settings.json").write_text(json.dumps({"trustedWorkspaces": [str(self.raiz)]}))
        (self.raiz / "dados.txt").write_text("valor=1\n")
        (self.raiz / "fonte.txt").write_text("Critério: valor deve ser 2\n")
        self.git("init", "-q")
        self.git("add", "dados.txt", "fonte.txt")
        self.git("-c", "user.name=Teste", "-c", "user.email=t@t", "commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.env = {k: v for k, v in os.environ.items() if not k.startswith(("JANGADA_", "XDG_"))}
        self.env.pop("DBUS_SESSION_BUS_ADDRESS", None)
        self.env.update(HOME=str(self.casa), PATH=str(self.bin) + ":/usr/bin:/bin", JANGADA_PATH=str(REPO),
                        XDG_STATE_HOME=str(self.tmp / "estado"), XDG_CONFIG_HOME=str(self.tmp / "config"),
                        XDG_CACHE_HOME=str(self.tmp / "cache"), JANGADA_SESSAO="sintetica")
        self.script("agy", '''import json,sys
if sys.argv[1:] == ["agents"]: print("implementador"); sys.exit()
if "/usage" in sys.argv:
 print(json.dumps({"command":{"data":{"groups":[{"buckets":[{"id":"gemini-weekly","remaining_fraction":0.9}]}]}}})); sys.exit()
print(json.dumps({"status":"SUCCESS","response":"dados.txt:1 valor atualizado","conversation_id":"sintetica"}))
''')
        # Imita apenas o cliente e a montagem. O teste de kernel é separado.
        self.script("bwrap", '''import json,os,sys,time
from pathlib import Path
args=sys.argv[1:]
alvos=[(Path(args[i+1]),args[i+2]) for i,x in enumerate(args) if x=="--bind"]
assert len(alvos) in (1,2), args
assert all("/arquivos/" in str(a) for a,b in alvos), args
assert not any(x in str(a) for a,b in alvos for x in ("/.git/","/agentes/"))
pasta=alvos[0][0].parent
modo=os.environ.get("FALSO_MODO","")
if modo=="prazo": time.sleep(4)
if modo=="falha": sys.exit(7)
if modo=="cota":
 sys.stderr.write("x"*1000000+"RESOURCE_EXHAUSTED"); sys.exit(7)
alvos[0][0].write_text("valor=2\\n")
if modo=="fora": (pasta/"indevido.txt").write_text("fora")
if modo=="link":
 alvos[0][0].unlink(); alvos[0][0].symlink_to(pasta/"fonte.txt")
if modo=="hardlink":
 alvos[0][0].unlink(); os.link(pasta/"fonte.txt", alvos[0][0])
print(json.dumps({"status":"SUCCESS","response":"dados.txt:1 valor atualizado","conversation_id":"sintetica"}))
''')

    def script(self, nome, codigo):
        p = self.bin / nome
        p.write_text("#!/usr/bin/python3\n" + codigo)
        p.chmod(0o755)

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.raiz), *args], text=True)

    def chamar(self, *args, sucesso=True):
        p = subprocess.run([str(REPO / "bin/jangada-delegar"), *args], cwd=self.raiz,
                           env=self.env, capture_output=True, text=True, timeout=20)
        if sucesso:
            self.assertEqual(p.returncode, 0, p.stderr + p.stdout)
        else:
            self.assertNotEqual(p.returncode, 0, p.stdout)
        return p

    def executar(self, *extras, sucesso=True):
        return self.chamar("implementador", "Mudar valor para 2", "--permitir-remoto", "--base", self.base,
                           "--arquivos", "fonte.txt", "--permitidos", "dados.txt", "--criterio",
                           "O teste do autor exige valor=2", *extras, sucesso=sucesso)

    def test_percurso_autor_executor_aceite_teste(self):
        resultado = json.loads(self.executar().stdout)
        self.assertEqual(resultado["estado"], "aguarda_autor")
        self.assertEqual((self.raiz / "dados.txt").read_text(), "valor=1\n")
        pasta = Path(resultado["pasta"])
        self.assertEqual((pasta / "arquivos/dados.txt").read_text(), "valor=2\n")
        contrato = json.loads((pasta / "contrato.json").read_text())
        self.assertEqual(contrato["base"], self.base)
        self.assertEqual(contrato["modelo"], modulo.MODELO)
        aceite = self.chamar("--aceitar", resultado["id"], "--base", self.base, "--entrega", resultado["entrega"])
        self.assertEqual(json.loads(aceite.stdout)["estado"], "aceita_pelo_autor")
        teste = subprocess.run(["python3", "-c", "from pathlib import Path; assert Path('dados.txt').read_text()=='valor=2\\n'"],
                               cwd=self.raiz, capture_output=True)
        self.assertEqual(teste.returncode, 0)
        self.assertEqual(self.git("diff", "--name-only").strip(), "dados.txt")
        self.assertFalse((pasta / ".aprovado").exists())
        global_md = (self.tmp / "agentes/implementador/agent.md").read_text()
        privado_md = (pasta / "runtime/agentes/implementador/agent.md").read_text()
        for ferramenta in ("write_to_file", "replace_file_content", "multi_replace_file_content"):
            self.assertNotIn("  - " + ferramenta, global_md)
            self.assertIn("  - " + ferramenta, privado_md)
        self.assertIn("subagent: true", global_md)
        self.assertIn("subagent: false", privado_md)

    def test_resultado_alterado_nao_aceito(self):
        r = json.loads(self.executar().stdout)
        (Path(r["pasta"]) / "arquivos/dados.txt").write_text("alterado")
        self.chamar("--aceitar", r["id"], "--base", self.base, "--entrega", r["entrega"], sucesso=False)
        self.assertEqual((self.raiz / "dados.txt").read_text(), "valor=1\n")

    def test_base_divergente_e_arquivo_do_autor_alterado(self):
        r = json.loads(self.executar().stdout)
        self.chamar("--aceitar", r["id"], "--base", "0" * 40, "--entrega", r["entrega"], sucesso=False)
        (self.raiz / "dados.txt").write_text("edição concorrente")
        self.chamar("--aceitar", r["id"], "--base", self.base, "--entrega", r["entrega"], sucesso=False)
        self.assertEqual((self.raiz / "dados.txt").read_text(), "edição concorrente")

    def test_negativos_da_entrega(self):
        for modo in ("fora", "link", "hardlink", "falha", "prazo"):
            with self.subTest(modo=modo):
                self.env["FALSO_MODO"] = modo
                p = self.executar("--prazo", "1", sucesso=False)
                resultado = json.loads(p.stdout)
                self.assertIn(resultado["estado"], ("falhou", "interrompida"))
                self.assertNotIn("entrega", resultado)
                self.assertEqual((self.raiz / "dados.txt").read_text(), "valor=1\n")

    def test_caminhos_modelo_e_concorrencia_recusados(self):
        for nome in ("/tmp/fora", "../fora", "x/../../fora", ".git/config", "x//y"):
            self.executar("--permitidos", nome, sucesso=False)
        self.executar("--modelo", "gemini-outro", sucesso=False)
        pasta = modulo.pasta_execucoes(self.raiz)
        fd = modulo.trava(pasta)
        try:
            self.executar(sucesso=False)
        finally:
            os.close(fd)

    def test_trava_global_cota_desconhecida_e_papel_ausente(self):
        estado = self.tmp / "estado/jangada/agentes"
        estado.mkdir(parents=True)
        with (estado / ".agy-execucao.lock").open("w") as arq:
            fcntl.flock(arq, fcntl.LOCK_EX | fcntl.LOCK_NB)
            p = self.executar(sucesso=False)
            self.assertEqual(json.loads(p.stdout)["motivo_codigo"], "execucao_ocupada")
        self.script("agy", 'import sys; print("implementador" if sys.argv[1:]==["agents"] else "{}")')
        p = self.executar(sucesso=False)
        self.assertEqual(json.loads(p.stdout)["motivo_codigo"], "cota_desconhecida")
        self.script("agy", 'print("leitor")')
        p = self.executar(sucesso=False)
        self.assertEqual(json.loads(p.stdout)["motivo_codigo"], "capacidade_incompativel")

    def test_arquivo_novo_escopo_exato(self):
        r = json.loads(self.executar("--permitidos", "dados.txt", "novo.txt", "--novos", "novo.txt").stdout)
        self.chamar("--aceitar", r["id"], "--base", self.base, "--entrega", r["entrega"])
        self.assertTrue((self.raiz / "novo.txt").is_file())
        self.assertEqual(self.git("status", "--short", "dados.txt", "novo.txt").splitlines(),
                         [" M dados.txt", "?? novo.txt"])

    def test_erro_do_executor_aguarda_captura_e_preserva_cota(self):
        self.env["FALSO_MODO"] = "cota"
        p = self.executar(sucesso=False)
        self.assertEqual(json.loads(p.stdout)["motivo_codigo"], "cota_insuficiente")

    def test_filho_do_catalogo_nao_herda_trava(self):
        pid_arquivo = self.tmp / "filho.pid"
        original = (self.bin / "agy").read_text().split("\n", 1)[1]
        prefixo = ("import subprocess,sys\nfrom pathlib import Path\n"
                   "if sys.argv[1:] == ['agents']:\n"
                   " filho=subprocess.Popen(['sleep','5'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
                   " Path(" + repr(str(pid_arquivo)) + ").write_text(str(filho.pid))\n")
        self.script("agy", prefixo + original)
        try:
            self.executar()
            with (self.tmp / "estado/jangada/agentes/.agy-execucao.lock").open() as arq:
                fcntl.flock(arq, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            if pid_arquivo.exists():
                try:
                    os.kill(int(pid_arquivo.read_text()), signal.SIGTERM)
                except ProcessLookupError:
                    pass

    def test_submodulo_e_link_na_base_recusados(self):
        self.git("update-index", "--add", "--cacheinfo", "160000," + self.base + ",modulo")
        (self.raiz / "atalho").symlink_to("fonte.txt")
        self.git("add", "atalho")
        self.git("-c", "user.name=Teste", "-c", "user.email=t@t", "commit", "-qm", "links")
        self.base = self.git("rev-parse", "HEAD").strip()
        self.executar("--permitidos", "modulo/novo.txt", "--novos", "modulo/novo.txt", sucesso=False)
        self.executar("--arquivos", "atalho", sucesso=False)

    def test_devolver_preserva_artefato(self):
        r = json.loads(self.executar().stdout)
        p = self.chamar("--devolver", r["id"], "--base", self.base, "--motivo", "critério incompleto")
        self.assertEqual(json.loads(p.stdout)["estado"], "devolvida")
        self.assertTrue((Path(r["pasta"]) / "arquivos/dados.txt").exists())

    def test_fronteira_real_sem_modelo_remoto(self):
        capacidade = subprocess.run(["/usr/bin/bwrap", "--ro-bind", "/", "/", "--unshare-pid", "true"],
                                    capture_output=True)
        if capacidade.returncode:
            self.skipTest("Bubblewrap indisponível: " + capacidade.stderr.decode()[:200])
        (self.bin / "bwrap").unlink()
        self.script("agy", '''import json,sys
from pathlib import Path
if sys.argv[1:] == ["agents"]: print("implementador"); sys.exit()
if "/usage" in sys.argv:
 print(json.dumps({"command":{"data":{"groups":[{"buckets":[{"id":"gemini-weekly","remaining_fraction":0.9}]}]}}})); sys.exit()
Path("dados.txt").write_text("valor=2\\n")
for alvo in ("fonte.txt", "indevido.txt", "../outra-tarefa.txt", ".git/config"):
 try: Path(alvo).write_text("indevido")
 except OSError: pass
 else: raise AssertionError("fronteira liberou " + alvo)
assert not Path(".git").exists()
print(json.dumps({"status":"SUCCESS","response":"dados.txt:1; fronteiras conferidas sem modelo remoto"}))
''')
        resultado = json.loads(self.executar().stdout)
        self.assertEqual(resultado["estado"], "aguarda_autor")
        self.assertEqual((self.raiz / "dados.txt").read_text(), "valor=1\n")
        self.assertEqual((Path(resultado["pasta"]) / "arquivos/dados.txt").read_text(), "valor=2\n")
        self.script("agy", '''import json,os,sys
if sys.argv[1:] == ["agents"]:
 print("leitor" if os.environ.get("JANGADA_ISOLADO") else "implementador"); sys.exit()
if "/usage" in sys.argv:
 print(json.dumps({"command":{"data":{"groups":[{"buckets":[{"id":"gemini-weekly","remaining_fraction":0.9}]}]}}})); sys.exit()
raise AssertionError("modelo chamado sem papel privado")
''')
        falha = json.loads(self.executar(sucesso=False).stdout)
        self.assertEqual(falha["estado"], "falhou")
        self.assertEqual((Path(falha["pasta"]) / "arquivos/dados.txt").read_text(), "valor=1\n")


if __name__ == "__main__":
    unittest.main()
