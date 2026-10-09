#!/usr/bin/python3
"""Oráculo do controlador: candidato roda sem rede nem acesso ao gabarito."""
import csv,hashlib,json,math,os,random,signal,subprocess,tempfile,time
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
CANDIDATO=Path('/home/felipinto/.local/share/jangada-worktrees/par-cobaia/tarefa-9c1ba243388f')
COMMIT='bb3ad6b4b2bb8f3032e28efb7af5f1a5c4abb9bb'

def referencia(linhas):
 def somar(grupo):return None if any(x['empregos'] is None for x in grupo) else sum(x['empregos'] for x in grupo)
 def dividir(a,b):return None if a is None or b is None or b==0 else a/b
 partes=[];ql=[];hhis={}
 for x in linhas:
  mun=[v for v in linhas if (v['ano'],v['uf'],v['municipio'])==(x['ano'],x['uf'],x['municipio'])]
  setor=[v for v in linhas if (v['ano'],v['setor'])==(x['ano'],x['setor'])]
  ano=[v for v in linhas if v['ano']==x['ano']]
  p=dividir(x['empregos'],somar(mun));partes.append(p);ql.append(dividir(p,dividir(somar(setor),somar(ano))))
  hhis.setdefault((x['ano'],x['uf'],x['municipio']),[]).append(p)
 return partes,ql,{k:None if any(x is None for x in ps) else sum(x*x for x in ps) for k,ps in hhis.items()}

def main():
 raiz=Path(tempfile.mkdtemp(prefix='jctrl-'));raiz.chmod(0o700)
 reg=OUT/'evidencias'/raiz.name;reg.mkdir()
 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(raiz/'home'),'GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1'}
 atual=subprocess.check_output(['/usr/bin/git','-C',str(CANDIDATO),'rev-parse','HEAD'],env=env,text=True).strip()
 if atual!=COMMIT:raise ValueError('Candidato mudou; não avaliar versão diferente silenciosamente')
 fonte=(CANDIDATO/'R/indicadores.R').read_bytes()
 committed=subprocess.check_output(['/usr/bin/git','-C',str(CANDIDATO),'show',COMMIT+':R/indicadores.R'],env=env)
 if fonte!=committed:raise ValueError('Código local difere do commit registrado')
 entradas=raiz/'entradas';entradas.mkdir();saida=raiz/'saida';saida.mkdir();(raiz/'home').mkdir()
 (raiz/'indicadores.R').write_bytes(fonte)
 # Referências Python permanecem fora das montagens. Casos gerados pelo auditor.
 casos={};rng=random.Random(7364921)
 for nome in ('normal','ano_alterado','zero_municipio','zero_setor','ausente','todo_ausente','ordem_invertida'):
  linhas=[dict(ano=a,uf='UF1',municipio=m,setor=s,empregos=rng.randint(1,100)) for a in (2022,2023) for m in ('M1','M2','M3') for s in ('industria','agropecuaria','comercio_servicos')]
  if nome!='normal':linhas=[dict(x) for x in casos['normal']]
  if nome=='ano_alterado':
   for x in linhas:
    if x['ano']==2023:x['empregos']*=17 if x['setor']=='industria' else 3
  if nome=='zero_municipio':
   for x in linhas:
    if x['municipio']=='M1':x['empregos']=0
  if nome=='zero_setor':
   for x in linhas:
    if x['setor']=='industria':x['empregos']=0
  if nome=='ausente':linhas[0]['empregos']=None
  if nome=='todo_ausente':
   for x in linhas:x['empregos']=None
  if nome=='ordem_invertida':linhas.reverse()
  casos[nome]=linhas
  with (entradas/(nome+'.csv')).open('w') as f:
   w=csv.DictWriter(f,fieldnames=['ano','uf','municipio','setor','empregos']);w.writeheader();w.writerows(linhas)
 (raiz/'runner.R').write_text('''source("/work/indicadores.R")
for (arquivo in list.files("/work/entradas", full.names = TRUE)) {
  b <- read.csv(arquivo, stringsAsFactors = FALSE)
  nome <- tools::file_path_sans_ext(basename(arquivo))
  write.csv(participacao(b), paste0("/work/saida/", nome, "-participacao.csv"), row.names = FALSE, na = "NA")
  write.csv(quociente_locacional(b), paste0("/work/saida/", nome, "-ql.csv"), row.names = FALSE, na = "NA")
  write.csv(hhi(b), paste0("/work/saida/", nome, "-hhi.csv"), row.names = FALSE, na = "NA")
}
''')
 cmd=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib','/lib64','--ro-bind','/etc/R','/etc/R','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--dir','/work','--dir','/home','--setenv','HOME','/home','--ro-bind',str(entradas),'/work/entradas','--ro-bind',str(raiz/'indicadores.R'),'/work/indicadores.R','--ro-bind',str(raiz/'runner.R'),'/work/runner.R','--bind',str(saida),'/work/saida','--chdir','/work','--','/usr/bin/Rscript','--vanilla','/work/runner.R']
 inicio=time.monotonic();p=subprocess.Popen(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
 try:stdout,stderr=p.communicate(timeout=60)
 except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate()
 (reg/'stdout.log').write_text(stdout);(reg/'stderr.log').write_text(stderr)
 resultado={'commit':COMMIT,'codigo_sha256':hashlib.sha256(fonte).hexdigest(),'raiz_sintetica':str(raiz),'registro':str(reg),'comando':cmd,'codigo':p.returncode,'segundos':round(time.monotonic()-inicio,3),'casos':[],'nenhuma_chamada_modelo':True,'originais_alterados':False}
 if p.returncode:resultado.update(classificacao='BLOQUEADO' if 'Operation not permitted' in stderr else 'FALHOU',motivo='Consultar stderr; proteção não foi removida')
 else:
  def conferir(a,b):return a in ('','NA','NaN') if b is None else a not in ('','NA','NaN') and math.isclose(float(a),b,rel_tol=1e-10,abs_tol=1e-12)
  for nome,linhas in casos.items():
   ps,qs,hs=referencia(linhas);falhas=[];verificacoes=0
   for indicador,valores,campo in [('participacao',ps,'participacao'),('ql',qs,'ql')]:
    with (saida/(nome+'-'+indicador+'.csv')).open() as f:obtidos=list(csv.DictReader(f))
    if len(obtidos)!=len(linhas):falhas.append('cardinalidade '+indicador)
    for i,(o,x,v) in enumerate(zip(obtidos,linhas,valores)):
     verificacoes+=1
     if any(str(o[k])!=str(x[k]) for k in ('ano','uf','municipio','setor')) or not conferir(o[campo],v):falhas.append(indicador+' linha '+str(i))
   with (saida/(nome+'-hhi.csv')).open() as f:obtidos=list(csv.DictReader(f))
   encontrado={(int(o['ano']),o['uf'],o['municipio']):o['hhi'] for o in obtidos}
   if len(encontrado)!=len(hs) or len(obtidos)!=len(hs):falhas.append('cardinalidade HHI')
   for k,v in hs.items():
    verificacoes+=1
    if k not in encontrado or not conferir(encontrado[k],v):falhas.append('HHI '+str(k))
   resultado['casos'].append({'caso':nome,'verificacoes':verificacoes,'falhas':falhas,'classificacao':'PASSOU' if not falhas else 'FALHOU'})
  resultado['classificacao']='PASSOU' if all(c['classificacao']=='PASSOU' for c in resultado['casos']) else 'FALHOU'
 (reg/'resumo.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2))
 print(json.dumps(resultado,ensure_ascii=False,indent=2));return 0 if resultado['classificacao']=='PASSOU' else 1
if __name__=='__main__':raise SystemExit(main())
