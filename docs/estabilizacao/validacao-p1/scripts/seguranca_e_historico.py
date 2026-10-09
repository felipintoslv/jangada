"""Ensaios complementares P0. Provedor/tmux simulados, Git/Bubblewrap reais."""
import base64,hashlib,importlib.util,json,os,sys,unittest,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
ROOT=Path(json.loads((OUT/'evidencias/origem-ensaio.json').read_text())['raiz_sintetica'])
CODE=ROOT/'codigo'
sys.path.insert(0,str(CODE/'default/orquestracao'))
from confianca import arquivar
s=importlib.util.spec_from_file_location('base',CODE/'testes/baseline.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)

class Complementar(b.Baseline):
 def test_commit_posterior_nao_reutiliza_marca(self):
  for pasta in ('agentes','revisoes'):
   meta=self.estado/pasta/'teste.json';dados=json.loads(meta.read_text());dados.update(raiz=str(self.projeto),ramo='agente/teste');meta.write_text(json.dumps(dados))
  self.mudar();self.assertEqual(self.validar().returncode,0)
  arq=self.estado/'revisoes/validacao-teste.aprovado';antigo=json.loads(arq.read_text())
  self.mudar('posterior.txt','alteração posterior\n')
  novo=self.git('rev-parse','HEAD');self.assertNotEqual(novo,antigo['candidate_sha'])
  self.executavel('claude','#!/bin/sh\ncat >/dev/null\nprintf "STATUS: REVISAR\\nCOMMIT-NOVO-NAO-APROVADO\\n"\n')
  r=self.validar();self.assertEqual(r.returncode,3,r.stderr)
  self.assertEqual(json.loads(arq.read_text()),antigo)
  previa=subprocess.run([str(CODE/'bin/jangada-agentes'),'--integracao-json','teste'],env=self.env,capture_output=True,text=True,timeout=20)
  self.assertEqual(previa.returncode,0,previa.stderr)
  dados=json.loads(previa.stdout);self.assertFalse(dados['marca_atual']);self.assertEqual(dados['candidate_sha'],novo)
  self.assertTrue((self.estado/'revisoes/teste.json').exists())
  self.assertEqual(self.git('rev-parse','HEAD'),novo)
  (OUT/'evidencias/aprovacao-commit-posterior.json').write_text(json.dumps({'candidate_anterior':antigo['candidate_sha'],'HEAD_posterior':novo,'marca_operacional_existe':arq.exists(),'marca_atual':dados['marca_atual'],'previa':dados,'metadados_preservados':True,'codigo':r.returncode,'revisor_simulado':True},indent=2))

 def test_autoria_local_adulterada_nao_supera_protegida(self):
  self.metadados('claude');self.mudar()
  local=self.estado/'agentes/teste.json';v=json.loads(local.read_text());v['agente']='codex';local.write_text(json.dumps(v))
  protegido=(self.estado/'revisoes/teste.json').read_bytes()
  r=self.validar();self.assertEqual(r.returncode,3,r.stderr)
  self.assertFalse((self.estado/'revisoes/validacao-teste.aprovado').exists())
  self.assertEqual((self.estado/'revisoes/teste.json').read_bytes(),protegido)

 def test_aprovacao_sem_parecer_bloqueia_arquivo(self):
  self.mudar();self.assertEqual(self.validar().returncode,0)
  parecer=self.estado/'revisoes/validacao-teste-r1.md'
  retido=self.raiz/'parecer-retido-pelo-auditor.md';parecer.rename(retido)
  marca=self.estado/'revisoes/validacao-teste.aprovado';original=marca.read_bytes()
  with self.assertRaises(ValueError):arquivar(self.estado,'teste')
  self.assertEqual(marca.read_bytes(),original);self.assertTrue((self.estado/'agentes/teste.json').exists());self.assertTrue(retido.is_file())

# Seleção explícita: não executar os dois casos herdados proibidos (merge/reset).
if __name__=='__main__':
 nomes=['test_commit_posterior_nao_reutiliza_marca','test_autoria_local_adulterada_nao_supera_protegida','test_aprovacao_sem_parecer_bloqueia_arquivo']
 r=unittest.TextTestRunner(verbosity=2).run(unittest.TestSuite(Complementar(n) for n in nomes))
 # Reconstruir a partir do arquivo histórico gerado pela suite P0, sem estado transitório.
 arq=OUT/'evidencias/arquivo-sintetico.json'
 doc=json.loads(arq.read_bytes());recuperados={}
 for nome,item in doc['documentos'].items():
  bruto=base64.b64decode(item['conteudo_base64'],validate=True)
  assert hashlib.sha256(bruto).hexdigest()==item['sha256']
  recuperados[nome]={'sha256':item['sha256'],'bytes':len(bruto)}
 contexto=json.loads(base64.b64decode(doc['documentos']['revisoes/validacao-teste-r1.contexto.json']['conteudo_base64']))
 marca=json.loads(base64.b64decode(doc['documentos']['revisoes/validacao-teste.aprovado']['conteudo_base64']))
 assert contexto['candidate_sha']==marca['candidate_sha']
 parecer=base64.b64decode(doc['documentos']['revisoes/validacao-teste-r1.md']['conteudo_base64']).decode()
 assert 'PARECER-INTEGRAL-SINTETICO' in parecer
 (OUT/'evidencias/reconstrucao-somente-historico.json').write_text(json.dumps({'fonte_unica':str(arq),'documentos_recuperados':recuperados,'sessao':doc['sessao'],'contexto':contexto,'marca_historica':marca,'parecer_integral':parecer,'provedor_simulado':True,'modelo_real_comprovado':False,'limitacao':'A amostra do teste não contém execução de modelo real; registros ausentes não são inventados.'},ensure_ascii=False,indent=2))
 raise SystemExit(not r.wasSuccessful())
