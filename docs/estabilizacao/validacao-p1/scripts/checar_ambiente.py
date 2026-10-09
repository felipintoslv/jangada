#!/usr/bin/python3
"""Sonda local sem provedores, credenciais ou alterações na instalação."""
import json, os, shutil, socket, subprocess, tempfile
from pathlib import Path

def main():
 resultado={'chamadas_externas':False,'credenciais_acessadas':False,'sondas':{}}
 with tempfile.TemporaryDirectory(prefix='jangada-preflight-') as raiz:
  raiz=Path(raiz)
  for nome,familia in [('socket_rede',socket.AF_INET),('socket_local',socket.AF_UNIX)]:
   s=None
   try:
    s=socket.socket(familia,socket.SOCK_STREAM)
    s.bind(('127.0.0.1',0) if familia==socket.AF_INET else str(raiz/'sonda.sock'))
    resultado['sondas'][nome]={'estado':'PASSOU'}
   except OSError as e:resultado['sondas'][nome]={'estado':'BLOQUEADO','errno':e.errno,'erro':str(e)}
   finally:
    if s:s.close()
  env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','HOME':str(raiz/'home')}
  for chave,pasta in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','dados'),('XDG_STATE_HOME','estado'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime'),('TMPDIR','tmp')]:
   p=raiz/pasta;p.mkdir(exist_ok=True,mode=0o700);env[chave]=str(p)
  comando=['/usr/bin/bwrap','--unshare-all','--die-with-parent','--new-session','--ro-bind','/usr','/usr','--symlink','usr/bin','/bin','--symlink','usr/lib','/lib','--symlink','usr/lib','/lib64','--proc','/proc','--dev','/dev','--tmpfs','/tmp','--','/usr/bin/true']
  try:
   p=subprocess.run(comando,env=env,cwd=raiz,capture_output=True,text=True,timeout=15)
   resultado['sondas']['bubblewrap']={'estado':'PASSOU' if p.returncode==0 else 'BLOQUEADO','codigo':p.returncode,'erro':p.stderr.strip()}
  except (OSError,subprocess.TimeoutExpired) as e:resultado['sondas']['bubblewrap']={'estado':'BLOQUEADO','erro':str(e)}
  for ferramenta in ('Rscript','tmux','ollama','codex','claude','agy'):
   resultado['sondas']['executavel_'+ferramenta]={'presente':shutil.which(ferramenta) is not None,'modelo_real_verificado':False}
 resultado['comunicacao_e_isolamento_disponiveis']=all(resultado['sondas'][n]['estado']=='PASSOU' for n in ('socket_rede','socket_local','bubblewrap'))
 resultado['limite']='Não verifica autenticação, execução de modelos, Qt ou o ciclo Jangada. Somente comunicação local e isolamento mínimo.'
 print(json.dumps(resultado,ensure_ascii=False,indent=2))
 return 0 if resultado['comunicacao_e_isolamento_disponiveis'] else 2

if __name__=='__main__':raise SystemExit(main())
