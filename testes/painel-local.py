#!/usr/bin/env python3
"""Métricas locais com respostas sintéticas, sem rede ou execução de modelos."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

RAIZ = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("subagentes", RAIZ / "default/painel/subagentes.py")
sub = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sub)


class PainelLocal(unittest.TestCase):
    def test_destinos_e_compatibilidade(self):
        registros = [sub.delegacao_limpa(dict(destino="local", papel="leitor", recusa=False,
                     pasta="/projeto", sessao="s", tokens_local_entrada=120,
                     tokens_local_saida=45, sem_fonte=1))]
        with patch.object(sub, "claude", return_value=[]), patch.object(sub, "agy", return_value=[]), \
             patch.object(sub, "delegacoes", return_value=registros), \
             patch.object(sub, "entregas_aprovadas", return_value=[]):
            ind = sub.indicadores()
        self.assertEqual(ind["fracao_agy"]["por_papel"]["leitor"], {"claude": 0, "agy": 0, "local": 1})
        self.assertEqual(ind["local"]["tokens_entrada"], 120)
        self.assertEqual(ind["arvore"][0]["filhos"][0]["tokens"], 165)
        self.assertEqual(ind["qualidade"]["por_destino"]["local"]["total"], 1)
        self.assertEqual(ind["qualidade"]["delegacoes"]["total"], 1)

    def test_ausencia_zero_e_validacao(self):
        d = sub.delegacao_limpa({"destino": "local", "tokens_local_entrada": True,
             "tokens_local_saida": float("nan"), "segundos": float("inf"),
             "chamadas_local": [{"tokens_entrada": 0, "tokens_saida": -2,
                                "tempos_ms": {"total": float("nan")}}]})
        self.assertIsNone(d["tokens_local_entrada"])
        self.assertIsNone(d["tokens_local_saida"])
        self.assertIsNone(d["segundos"])
        self.assertEqual(sub.uso_local(d, "tokens_local_entrada"), 0)
        self.assertIsNone(sub.uso_local(d, "tokens_local_saida"))
        self.assertIsNone(d["chamadas_local"][0]["tempos_ms"]["total"])
        self.assertIsNone(sub.resumo_local([])["tokens_entrada"])
        self.assertFalse(sub.numero_valido(10 ** 1000))

    def test_chamadas_prevalecem_e_falha_conta_consumo(self):
        d = {"destino": "local", "recusa": True, "tokens_local_entrada": 999,
             "chamadas_local": [{"tokens_entrada": 120, "tokens_saida": 45},
                                {"tokens_entrada": None, "tokens_saida": None}]}
        self.assertEqual(sub.resumo_local([d])["tokens_entrada"], 120)
        self.assertEqual(sub.resumo_local([d])["recusas"], 1)
        self.assertIsNone(sub.uso_local({"chamadas_local": [], "tokens_local_entrada": 999}, "tokens_local_entrada"))

    def executar(self, modo):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            falsos = raiz / "bin"
            falsos.mkdir()
            for nome, corpo in {
                "pgrep": "#!/bin/sh\nexit 1\n",
                "nvidia-smi": "#!/bin/sh\necho 8000\n",
                "curl": '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
args = sys.argv[1:]
if args[-1].endswith('/api/tags'):
 print(json.dumps({'models':[{'name':'qwen3:4b'}]}))
elif args[-1].endswith('/api/ps'):
 print(json.dumps({'models':[]}))
else:
 p = json.loads(args[args.index('-d')+1])
 assert 'tools' not in p
 count = Path(os.environ['CONTADOR'])
 n = int(count.read_text())+1 if count.exists() else 1
 count.write_text(str(n))
 if os.environ['MODO'] == 'parcial' and n == 2:
  sys.exit(28)
 if os.environ['MODO'] == 'invalido':
  print('resposta ilegível')
  sys.exit(0)
 if os.environ['MODO'] == 'sem_medida':
  print(json.dumps({'message':{'content':'doc.txt:1: relatório sintético'}}))
 else:
  print(json.dumps({'message':{'content':'doc.txt:1: relatório sintético'},
   'prompt_eval_count':120,'eval_count':45,'total_duration':1000000000,
   'load_duration':100000000,'prompt_eval_duration':200000000,'eval_duration':700000000}))
''',
            }.items():
                caminho = falsos / nome
                caminho.write_text(corpo)
                caminho.chmod(0o755)
            doc = raiz / "doc.txt"
            doc.write_text(("x" * 100 + "\n") * 8 if modo in ("parcial", "fatias") else "conteúdo sintético\n")
            env = dict(os.environ, HOME=str(raiz), XDG_CONFIG_HOME=str(raiz / "config"),
                       XDG_STATE_HOME=str(raiz / "state"), JANGADA_PATH=str(RAIZ),
                       JANGADA_DELEGAR="local", JANGADA_LOCAL_CTX="2100" if modo in ("parcial", "fatias") else "8192",
                       JANGADA_LOCAL_FATIAS_MAX="10", PATH=str(falsos) + ":" + os.environ["PATH"],
                       CONTADOR=str(raiz / "contador"), MODO=modo)
            p = subprocess.run([str(RAIZ / "bin/jangada-delegar"), "leitor", "resuma",
                                "--arquivos", str(doc)], cwd=raiz, env=env, capture_output=True, text=True)
            registro = json.loads((raiz / "state/jangada/delegacoes.jsonl").read_text().splitlines()[-1])
            return p.returncode, registro

    def test_registro_tempos_e_sem_ferramentas(self):
        codigo, d = self.executar("normal")
        self.assertEqual(codigo, 0)
        self.assertFalse(d["ferramentas_disponiveis"])
        self.assertEqual(len(d["delegacao_id"]), 36)
        c = d["chamadas_local"][0]
        self.assertEqual(c["fase"], "documento")
        self.assertEqual(c["tempos_ms"]["total"], 1000)
        self.assertEqual(c["tempos_ms"]["geracao"], 700)
        self.assertIsNone(c["cache_lido"])
        self.assertEqual(d["tokens_local_entrada"], 120)
        self.assertGreater(d["documento_chars"], 0)
        self.assertGreater(d["retorno_chars"], 0)

    def test_falha_parcial_registrada(self):
        codigo, d = self.executar("parcial")
        self.assertEqual(codigo, 4)
        self.assertTrue(d["recusa"])
        self.assertEqual(len(d["chamadas_local"]), 2)
        self.assertEqual(d["chamadas_local"][0]["fase"], "fatia")
        self.assertEqual(d["chamadas_local"][1]["codigo_transporte"], 28)
        self.assertIsNone(d["chamadas_local"][1]["tokens_entrada"])
        self.assertEqual(d["tokens_local_entrada"], 120)

    def test_sem_medidas_nao_inventa_zero(self):
        codigo, d = self.executar("sem_medida")
        self.assertEqual(codigo, 0)
        self.assertIsNone(d["tokens_local_entrada"])
        self.assertIsNone(d["tokens_local_saida"])
        self.assertIsNone(d["chamadas_local"][0]["tempos_ms"]["total"])

    def test_fatias_consolidacao_sem_dupla_contagem(self):
        codigo, d = self.executar("fatias")
        self.assertEqual(codigo, 0)
        chamadas = d["chamadas_local"]
        self.assertGreater(len(chamadas), 2)
        self.assertEqual(chamadas[-1]["fase"], "consolidacao")
        self.assertEqual(len({c["id"] for c in chamadas}), len(chamadas))
        self.assertEqual(d["tokens_local_entrada"], 120 * len(chamadas))
        self.assertEqual(sub.uso_local(d, "tokens_local_entrada"), 120 * len(chamadas))

    def test_json_invalido_registra_recusa_sem_medidas(self):
        codigo, d = self.executar("invalido")
        self.assertEqual(codigo, 4)
        self.assertTrue(d["recusa"])
        self.assertEqual(len(d["chamadas_local"]), 1)
        self.assertIsNone(d["chamadas_local"][0]["tokens_entrada"])


if __name__ == "__main__":
    unittest.main()
