#!/usr/bin/python3
"""Agy real com HOME sintético e proxy efêmero de chaveiro somente leitura."""
import argparse,json,os,re,select,shutil,signal,subprocess,time
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
SERVICO='org.freedesktop.secrets';BASE='/org/freedesktop/secrets'

def main():
 parser=argparse.ArgumentParser();parser.add_argument('raiz',type=Path);args=parser.parse_args()
 raiz=args.raiz.resolve();reg=OUT/'evidencias'/raiz.name
 if args.raiz.is_symlink() or raiz.parent!=Path('/tmp') or not raiz.name.startswith('jreal-'):raise ValueError('Raiz sintética inválida')
 anterior=json.loads((reg/'resumo.json').read_text())
 if anterior['raiz_sintetica']!=str(raiz) or not any(c['provedor']=='codex' and c['resposta_conferida'] for c in anterior['chamadas']):raise ValueError('Conectividade Codex não comprovada nesta raiz')
 env=json.loads((raiz/'ambiente.json').read_text())
 for k in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_RUNTIME_DIR','TMPDIR','TMUX_TMPDIR','JANGADA_PATH'):
  if not Path(env[k]).resolve().is_relative_to(raiz):raise ValueError('Caminho externo')
 resultado={'raiz_sintetica':str(raiz),'revisor':'agy','autorizacao':'Usuário solicitou use o agy','chaveiro_global_alterado':False,'chamada_real':False,'pronto_para_preparar_tarefa':False}
 def gravar():
  (reg/'agy-resumo.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2));print(json.dumps(resultado,ensure_ascii=False,indent=2))
 def bloquear(motivo):resultado.update(classificacao='BLOQUEADO',motivo=motivo);gravar();return 2
 endereco=os.environ.get('DBUS_SESSION_BUS_ADDRESS')
 if not endereco:return bloquear('D-Bus da sessão não disponível; não copiar segredos nem configurar login')
 exe=shutil.which('agy');proxyexe=shutil.which('xdg-dbus-proxy');gdbus=shutil.which('gdbus')
 if not all((exe,proxyexe,gdbus)):return bloquear('Dependência existente ausente; nenhuma instalação automática')
 destino=raiz/'bin/agy'
 if not destino.exists():shutil.copy2(Path(exe).resolve(),destino)
 casa=Path(env['HOME']);agy=casa/'.gemini/antigravity-cli';agy.mkdir(parents=True,exist_ok=True,mode=0o700)
 agente=casa/'.gemini/config/agents/revisor'
 if not agente.exists():shutil.copytree(raiz/'codigo/default/agy/agents/revisor',agente)
 original=Path.home()/'.gemini/antigravity-cli/installation_id'
 if original.is_file() and not original.is_symlink() and not (agy/'installation_id').exists():
  fd=os.open(agy/'installation_id',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(original.read_bytes())
 # Consultar somente atributos dos itens; nunca GetSecret fora do provedor isolado.
 hostenv=dict(env,DBUS_SESSION_BUS_ADDRESS=endereco)
 def consulta(objeto,metodo,*valores):
  r=subprocess.run([gdbus,'call','--session','--dest',SERVICO,'--object-path',objeto,'--method',metodo,*valores],env=hostenv,capture_output=True,text=True,timeout=10)
  if r.returncode:raise RuntimeError('Consulta de metadados do chaveiro indisponível')
  return r.stdout
 try:
  busca=consulta(BASE,'org.freedesktop.Secret.Service.SearchItems','@a{ss} {}')
  itens=sorted(set(re.findall(r'/org/freedesktop/secrets/collection/[A-Za-z0-9_]+/[A-Za-z0-9_]+',busca)))
  selecionados=[];servicos=set()
  for item in itens:
   atributos=consulta(item,'org.freedesktop.DBus.Properties.Get','org.freedesktop.Secret.Item','Attributes')
   dados=dict(re.findall(r"'([^']+)': '([^']*)'",atributos))
   servico=dados.get('service','')
   if re.fullmatch(r'[A-Za-z0-9_.:@/+-]+',servico) and re.search(r'(?i)antigravity|(?:^|[-_.])agy(?:$|[-_.])',servico):
    selecionados.append(item);servicos.add(servico)
 except (RuntimeError,subprocess.TimeoutExpired):return bloquear('Não foi possível selecionar credenciais por metadados com segurança')
 if not selecionados:return bloquear('Nenhum item do chaveiro identificado como agy/Antigravity; atributos não publicados. Não liberar chaveiro inteiro')
 if len(servicos)!=1:return bloquear('Mais de um serviço de autenticação candidato; seleção ambígua')
 sock=raiz/'runtime/agy-auth-ro.sock'
 if sock.exists():return bloquear('Socket de ensaio já existe; não sobrescrever')
 argumentos=[proxyexe,endereco,str(sock),'--filter','--fd=1','--see='+SERVICO]
 for metodo,objeto in [('org.freedesktop.Secret.Service.OpenSession',BASE),('org.freedesktop.Secret.Service.ReadAlias',BASE),('org.freedesktop.Secret.Service.SearchItems',BASE),('org.freedesktop.DBus.Properties.Get',BASE),('org.freedesktop.Secret.Session.Close',BASE+'/session/*')]:argumentos+=['--call='+SERVICO+'='+metodo+'@'+objeto]
 for colecao in {BASE+'/aliases/default',BASE+'/collection/login',*(x.rsplit('/',1)[0] for x in selecionados)}:
  argumentos+=['--call='+SERVICO+'=org.freedesktop.Secret.Collection.SearchItems@'+colecao]
 for item in selecionados:
  argumentos+=['--call='+SERVICO+'=org.freedesktop.Secret.Item.GetSecret@'+item,'--call='+SERVICO+'=org.freedesktop.DBus.Properties.Get@'+item]
 proxy=subprocess.Popen(argumentos,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 try:
  if not select.select([proxy.stdout],[],[],8)[0] or len(os.read(proxy.stdout.fileno(),1))!=1:return bloquear('Proxy de chaveiro somente leitura não iniciou')
  env.update(DBUS_SESSION_BUS_ADDRESS='unix:path='+str(sock),JANGADA_ISOLAR_KEYRING_ITEM='service='+next(iter(servicos)))
  projeto=raiz/'projetos/conectividade';isolar=str(raiz/'codigo/bin/jangada-isolar')
  r=subprocess.run([isolar,'--','agy','agents'],cwd=projeto,env=env,capture_output=True,text=True,timeout=60)
  if r.returncode or 'revisor' not in r.stdout.splitlines():return bloquear('Agente revisor não registrado no HOME sintético; nenhuma chamada de análise')
  cmd=[isolar,'--','agy','-p','Teste sintético de conectividade. Responda somente JANGADA_P1_AGY_OK. Não leia arquivos ou use ferramentas.','--agent','revisor','--sandbox','--output-format','json','--add-dir',str(projeto),'--effort','high']
  inicio=time.monotonic();p=subprocess.Popen(cmd,cwd=projeto,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
  try:stdout,stderr=p.communicate(timeout=180)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate();stderr+='\nPrazo excedido.'
  # Aplicar mesma proteção de registros usada no preparador, sem imprimir o HOME.
  import preparar_modelos_reais as preparador
  (reg/'agy.stdout.log').write_text(preparador.limpar(stdout));(reg/'agy.stderr.log').write_text(preparador.limpar(stderr))
  try:doc=json.loads(stdout)
  except ValueError:doc={}
  sucesso=p.returncode==0 and doc.get('status')=='SUCCESS' and doc.get('response','').strip()=='JANGADA_P1_AGY_OK'
  resultado.update(chamada_real=True,codigo=p.returncode,segundos=round(time.monotonic()-inicio,3),resposta_conferida=sucesso,classificacao='PASSOU' if sucesso else 'REQUER_ANALISE',itens_de_autenticacao_selecionados=len(selecionados),pronto_para_preparar_tarefa=sucesso,limite='Conectividade não é revisão da atividade; renovação de token e escritas no chaveiro são bloqueadas')
  if sucesso:
   anterior.update(revisor_autorizado='agy',pronto_para_preparar_tarefa=True)
   (reg/'resumo.json').write_text(json.dumps(anterior,ensure_ascii=False,indent=2))
   conf=raiz/'config/jangada/jangada.conf'
   with conf.open('a') as f:f.write('\nJANGADA_VALIDAR_REVISOR=agy\n')
   # Dados públicos necessários para reproduzir a seleção, sem metadados pessoais.
   (raiz/'agy-servico.json').write_text(json.dumps({'service':next(iter(servicos))}))
  gravar();return 0 if sucesso else 1
 finally:
  proxy.terminate()
  try:proxy.wait(timeout=5)
  except subprocess.TimeoutExpired:proxy.kill();proxy.wait(timeout=5)
if __name__=='__main__':raise SystemExit(main())
