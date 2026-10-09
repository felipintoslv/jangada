#!/usr/bin/python3
"""Reexecuta Qt e P0 em nova cópia e novo estado; não chama modelos reais."""
import argparse,hashlib,io,json,os,signal,subprocess,tarfile,tempfile,time
from pathlib import Path
VERSAO='17178ded546642e3246bfe3bd5c33df8da821874'
REPO=Path('/home/felipinto/Projetos/jangada-confianca-p0')
OUT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--somente-interface',action='store_true');args=parser.parse_args()
 raiz=Path(tempfile.mkdtemp(prefix='jp1-'))
 registro=OUT/'evidencias'/raiz.name;registro.mkdir()
 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','PYTHONDONTWRITEBYTECODE':'1','QT_QPA_PLATFORM':'offscreen','CI':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','R_PROFILE_USER':'/dev/null','R_ENVIRON_USER':'/dev/null'}
 for chave,nome in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','dados'),('XDG_STATE_HOME','estado'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime'),('TMPDIR','tmp'),('TMUX_TMPDIR','runtime')]:
  pasta=raiz/nome;pasta.mkdir(mode=0o700,exist_ok=True);env[chave]=str(pasta)
 codigo=raiz/'codigo';codigo.mkdir()
 bruto=subprocess.check_output(['/usr/bin/git','-C',str(REPO),'archive',VERSAO],env=env,timeout=30)
 with tarfile.open(fileobj=io.BytesIO(bruto)) as arq:arq.extractall(codigo,filter='data')
 guardas=raiz/'guardas';guardas.mkdir()
 git=guardas/'git';git.write_text("#!/usr/bin/python3\nimport os,sys\nif any(a in {'merge','reset','clean','push','rebase','tag'} for a in sys.argv[1:]):sys.exit(125)\nos.execv('/usr/bin/git',['git',*sys.argv[1:]])\n");git.chmod(0o700)
 for nome in ('sudo','systemctl','pacman','paru','yay','pkill','killall'):
  f=guardas/nome;f.write_text('#!/bin/sh\nexit 125\n');f.chmod(0o700)
 env.update(PATH=str(guardas)+':/usr/bin:/bin',JANGADA_PATH=str(codigo),JANGADA_ESTADO=str(raiz/'estado/jangada'),JANGADA_CONFIG=str(raiz/'config/jangada'),JANGADA_P0_EVIDENCIAS=str(registro),JANGADA_ISOLAR_OCULTAR_EXTRA='/home/felipinto')
 config=raiz/'config/jangada';config.mkdir()
 for nome in ('projetos','worktrees'):(raiz/nome).mkdir()
 (config/'jangada.conf').write_text(f'JANGADA_PROJETOS={raiz}/projetos\nJANGADA_WORKTREES={raiz}/worktrees\nJANGADA_AGENTE_ISOLAR=1\nJANGADA_ISOLAR_CASA=minima\nJANGADA_ISOLAR_AMBIENTE=minimo\nJANGADA_ISOLAR_OCULTAR_EXTRA=/home/felipinto\n')

 resultado_sonda=subprocess.run(['/usr/bin/python3','-B',str(OUT/'scripts/sondar_socket_qt.py')],cwd=raiz,env=env,capture_output=True,text=True,timeout=15)
 (registro/'sonda-qt.stdout.log').write_text(resultado_sonda.stdout)
 (registro/'sonda-qt.stderr.log').write_text(resultado_sonda.stderr)
 print('Sonda de tamanho do socket Qt:',resultado_sonda.stdout or resultado_sonda.stderr,flush=True)
 (registro/'sonda-qt.resultado.json').write_text(json.dumps({'codigo':resultado_sonda.returncode,'classificacao':'EXECUTADO' if resultado_sonda.returncode==0 else 'FALHOU'}))
 resultados=[]
 for nome,teste in ([('interface','tarefas.py')] if args.somente_interface else [('interface','tarefas.py'),('p0','confianca-p0.py')]):
  inicio=time.monotonic();cmd=['/usr/bin/python3','-B',str(codigo/'testes'/teste)]
  p=subprocess.Popen(cmd,cwd=codigo,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:stdout,stderr=p.communicate(timeout=180)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate()
  (registro/(nome+'.stdout.log')).write_text(stdout);(registro/(nome+'.stderr.log')).write_text(stderr)
  print(stderr,flush=True)
  resultados.append({'suite':nome,'comando':cmd,'codigo':p.returncode,'segundos':round(time.monotonic()-inicio,3),'classificacao':'PASSOU' if p.returncode==0 else 'REQUER_ANALISE'})
 manifesto={str(f.relative_to(registro)):hashlib.sha256(f.read_bytes()).hexdigest() for f in registro.rglob('*') if f.is_file()}
 resumo={'commit':VERSAO,'raiz_sintetica':str(raiz),'registro':str(registro),'modelos_reais_executados':False,'resultados':resultados,'hashes':manifesto}
 (registro/'resumo.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2))
 print(json.dumps(resumo,ensure_ascii=False,indent=2))
 print('Estado sintético preservado. Nenhuma configuração ativa foi reutilizada.')
 return int(any(r['codigo']!=0 for r in resultados))
if __name__=='__main__':raise SystemExit(main())
