#!/usr/bin/env python3
"""Valores fechados, precedência e recomposição sem comandos do registro."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("modelos", RAIZ / "core/delegacao/modelos.py")
modelos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(modelos)


class Modelos(unittest.TestCase):
    def test_autores_e_revisores(self):
        for autor, modelo, esforco, revisor, forte in (
            ("codex", "gpt-6-luna", "medium", "claude", "opus"),
            ("codex", "gpt-6.1-sol", "high", "claude", "opus"),
            ("claude", "sonnet", "high", "codex", "gpt-6.1-sol"),
            ("claude", "opus", "high", "codex", "gpt-6.1-sol"),
        ):
            selecao = modelos.selecionar(autor, revisor, modelo, esforco)
            self.assertEqual(selecao["revisor"]["modelo"], forte)
            self.assertEqual(modelos.conferir(selecao, autor, revisor), selecao)

    def test_antigos_sem_modelo_preservados(self):
        self.assertEqual(modelos.selecionar("codex", "codex"), {})

    def test_valores_invalidos_e_autorrevisao_recusados(self):
        for a, r, m, e in (("codex", "claude", "opus", "high"),
                            ("codex", "codex", "gpt-6.1-sol", "high"),
                            ("codex", "claude", "gpt-6-luna", "high"),
                            ("codex", "claude", "$(touch /tmp/invadido)", "high")):
            with self.assertRaises(ValueError):
                modelos.selecionar(a, r, m, e)
        with self.assertRaises(ValueError):
            modelos.selecionar("codex", "claude", "gpt-6.1-sol", "high", "sonnet")

    def test_precedencia_e_argumentos(self):
        script = '''source bin/jangada-config
PERFIL_AMBIENTE=(JANGADA_AUTOR_MODELO=gpt-6.1-sol JANGADA_AUTOR_ESFORCO=high)
selecao="$(jangada_modelos_tarefa codex claude gpt-6-luna medium)"
printf '%s\\n' "$selecao"
jangada_modelo_argumentos "$selecao" codex
'''
        p = subprocess.run(["bash", "-c", script], cwd=RAIZ, capture_output=True, text=True,
                           env={**os.environ, "JANGADA_PATH": str(RAIZ)})
        self.assertEqual(p.returncode, 0, p.stderr)
        linhas = p.stdout.splitlines()
        selecao = json.loads(linhas[0])
        self.assertEqual(selecao["autor"]["modelo"], "gpt-6-luna")
        self.assertIn("--model gpt-6-luna", linhas[1])
        self.assertIn("model_reasoning_effort=", linhas[1])

    def test_modelo_explicito_deduz_esforco_sem_herdar_outro_par(self):
        script = '''source bin/jangada-config
PERFIL_AMBIENTE=(JANGADA_AUTOR_MODELO=gpt-6.1-sol JANGADA_AUTOR_ESFORCO=high
                JANGADA_VALIDAR_MODELO=opus JANGADA_VALIDAR_ESFORCO=medium)
jangada_modelos_tarefa codex claude gpt-6-luna '' opus ''
'''
        p = subprocess.run(["bash", "-c", script], cwd=RAIZ, capture_output=True, text=True,
                           env={**os.environ, "JANGADA_PATH": str(RAIZ)})
        self.assertEqual(p.returncode, 0, p.stderr)
        selecao = json.loads(p.stdout)
        self.assertEqual(selecao["autor"]["esforco"], "medium")
        self.assertEqual(selecao["revisor"]["esforco"], "high")

    def test_perfis_legados_aceitam_revisor_e_argumentos_extras(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JANGADA_")}
        with tempfile.TemporaryDirectory() as tmp:
            env.update(JANGADA_PATH=str(RAIZ), XDG_CONFIG_HOME=tmp)
            for extras in (("--revisor", "agy"), ("--revisor", "mesmo"), ("--", "--version")):
                p = subprocess.run([str(RAIZ / "bin/jangada-agente"), "--perfil", "codex-claude",
                                    "--projeto", str(Path(tmp) / "ausente"), *extras],
                                   env=env, capture_output=True, text=True)
                self.assertNotEqual(p.returncode, 0)
                self.assertNotIn("modelos da tarefa:", p.stderr)
                self.assertNotIn("argumentos do autor vazios", p.stderr)

    def test_perfil_invalido_nao_derruba_catalogo_publico(self):
        env = {k: v for k, v in os.environ.items() if not k.startswith("JANGADA_")}
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp) / "jangada/agentes"
            pasta.mkdir(parents=True)
            (pasta / "invalido.conf").write_text("COMANDO=codex\nJANGADA_AUTOR_MODELO=inexistente\n")
            env.update(JANGADA_PATH=str(RAIZ), XDG_CONFIG_HOME=tmp)
            p = subprocess.run([str(RAIZ / "bin/jangada-agente"), "--perfis", "--json"],
                               env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            nomes = {perfil["nome"] for perfil in json.loads(p.stdout)}
            self.assertEqual(nomes, {"claude-codex", "codex-claude"})
            self.assertIn("perfil invalido", p.stderr)

    def test_restauracao_usa_selecao_protegida_e_ignora_comando(self):
        codigo = (RAIZ / "core/bin/jangada-agentes").read_text()
        inicio = codigo.index("restaurar() {")
        fim = codigo.index("\n# Histórico de foco", inicio)
        with tempfile.TemporaryDirectory() as tmp:
            pasta = Path(tmp)
            estado = pasta / "estado/jangada/agentes"
            estado.mkdir(parents=True)
            protegido = pasta / "estado/jangada/revisoes"
            protegido.mkdir()
            selecao = modelos.selecionar("codex", "claude", "gpt-6-luna", "medium")
            gravavel = {"agente": "codex", "dir": str(pasta), "estado": "interrompido",
                        "comando": "touch /tmp/invadido", "modelos_tarefa": {"autor": "injetado"}}
            (estado / "s.json").write_text(json.dumps(gravavel))
            (protegido / "s.json").write_text(json.dumps({"revisor": "claude", "modelos_tarefa": selecao}))
            script = '''set -eu
source bin/jangada-config
estado_dir="$JANGADA_ESTADO/agentes"
restauravel() { return 0; }
pasta_restauravel() { printf '%s\\n' "$1"; }
confianca() { return 0; }
refazer_protocolo() { return 0; }
marcar() { return 0; }
python3() { [[ "$1" == */confianca.py ]] || command python3 "$@"; }
tmux_falso() { printf '%s\\n' "$@" >>"$TESTE_LOG"; [[ "$1" != has-session ]]; }
JANGADA_TMUX=(tmux_falso)
''' + codigo[inicio:fim] + "\nrestaurar s\n"
            env = {**os.environ, "JANGADA_PATH": str(RAIZ), "XDG_STATE_HOME": str(pasta / "estado"),
                   "XDG_CONFIG_HOME": str(pasta / "config"), "TESTE_LOG": str(pasta / "log")}
            env.pop("JANGADA_ISOLADO", None)
            p = subprocess.run(["bash", "-c", script], cwd=RAIZ, env=env, capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            log = (pasta / "log").read_text()
            self.assertIn("--model gpt-6-luna", log)
            self.assertIn("JANGADA_VALIDAR_MODELO=opus", log)
            self.assertIn("model_reasoning_effort=", log)
            self.assertNotIn("touch /tmp/invadido", log)
            self.assertNotIn("injetado", log)
            (pasta / "log").unlink()
            (protegido / "s.json").unlink()
            p = subprocess.run(["bash", "-c", script], cwd=RAIZ, env=env, capture_output=True, text=True)
            self.assertNotEqual(p.returncode, 0)
            self.assertNotIn("send-keys", (pasta / "log").read_text())


if __name__ == "__main__":
    unittest.main()
