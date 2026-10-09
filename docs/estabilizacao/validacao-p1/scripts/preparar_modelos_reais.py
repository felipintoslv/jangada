#!/usr/bin/python3
"""Prepara HOME sintético e testa Codex/Claude reais no isolamento nativo."""
import argparse,hashlib,io,json,os,re,shutil,signal,subprocess,tarfile,tempfile,time,tomllib
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
REPO=Path('/home/felipinto/Projetos/jangada-confianca-p0')
VERSAO='17178ded546642e3246bfe3bd5c33df8da821874'

def copiar_credencial(origem,destino):
 if origem.is_symlink():raise ValueError('Credencial com link exige inspeção específica; não copiar automaticamente')
 if origem.is_file():
  destino.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
  fd=os.open(destino,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
  with os.fdopen(fd,'wb') as f:f.write(origem.read_bytes())
  return True
 return False

def limpar(texto):
 texto=re.sub(r'(?i)(bearer\s+)[A-Za-z0-9._~+/-]+',r'\1[OCULTO]',texto)
 texto=re.sub(r'\b(?:sk-[A-Za-z0-9_-]{12,}|eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+)\b','[OCULTO]',texto)
 return re.sub(r'[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}','[EMAIL_OCULTO]',texto)

def main():
 parser=argparse.ArgumentParser();parser.add_argument('--chamar-provedores',action='store_true',help='Executa duas chamadas curtas autorizadas. Sem opção, somente prepara.')
 args=parser.parse_args()
 raiz=Path(tempfile.mkdtemp(prefix='jreal-'));raiz.chmod(0o700)
 registro=OUT/'evidencias'/raiz.name;registro.mkdir(mode=0o700)
 casa_real=Path.home();casa=raiz/'home'
 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8','TERM':'xterm-256color','SHELL':'/bin/bash','USER':os.environ.get('USER',''),'PYTHONDONTWRITEBYTECODE':'1','GIT_CONFIG_GLOBAL':'/dev/null','GIT_CONFIG_NOSYSTEM':'1','R_PROFILE_USER':'/dev/null','R_ENVIRON_USER':'/dev/null'}
 for chave,pasta in [('HOME','home'),('XDG_CONFIG_HOME','config'),('XDG_DATA_HOME','dados'),('XDG_STATE_HOME','estado'),('XDG_CACHE_HOME','cache'),('XDG_RUNTIME_DIR','runtime'),('TMPDIR','tmp'),('TMUX_TMPDIR','runtime')]:
  p=raiz/pasta;p.mkdir(exist_ok=True,mode=0o700);env[chave]=str(p)
 for pasta in ('codigo','projetos','worktrees','bin','aplicativos'):(raiz/pasta).mkdir(mode=0o700)
 bruto=subprocess.check_output(['/usr/bin/git','-C',str(REPO),'archive',VERSAO],env=env,timeout=30)
 with tarfile.open(fileobj=io.BytesIO(bruto)) as arq:arq.extractall(raiz/'codigo',filter='data')
 # Copiar somente aplicações instaladas, sem perfil, histórico ou extensões pessoais.
 pacote=casa_real/'.local/lib/node_modules/@openai/codex'
 if not (pacote/'bin/codex.js').is_file():raise RuntimeError('Instalação Codex não corresponde ao pacote inspecionado')
 shutil.copytree(pacote,raiz/'aplicativos/codex',symlinks=False)
 codex=raiz/'bin/codex';codex.symlink_to(raiz/'aplicativos/codex/bin/codex.js')
 claude_exe=shutil.which('claude')
 if not claude_exe:raise RuntimeError('Claude não encontrado')
 origem=Path(claude_exe).resolve()
 if not origem.is_file():raise RuntimeError('Executável Claude inválido')
 shutil.copy2(origem,raiz/'bin/claude')
 # Nenhuma configuração global de hooks/MCP/plugins é copiada.
 for pasta in ('.codex','.claude'):(casa/pasta).mkdir(mode=0o700)
 credenciais={'codex_auth_json':copiar_credencial(casa_real/'.codex/auth.json',casa/'.codex/auth.json'),'claude_credentials_json':copiar_credencial(casa_real/'.claude/.credentials.json',casa/'.claude/.credentials.json')}
 modelo=None
 config_codex=casa_real/'.codex/config.toml'
 if config_codex.is_file():
  config=tomllib.loads(config_codex.read_text())
  if config.get('model_provider','openai')!='openai':raise RuntimeError('Provedor Codex personalizado requer inspeção; não fazer chamada com configuração presumida')
  modelo=config.get('model')
 if modelo is not None and not re.fullmatch(r'[A-Za-z0-9_.-]{1,128}',modelo):raise RuntimeError('Modelo inválido')
 (casa/'.codex/config.toml').write_text(('model = '+json.dumps(modelo)+'\n') if modelo else '')
 (casa/'.claude/settings.json').write_text('{}\n')
 (casa/'.claude.json').write_text('{"hasCompletedOnboarding":true}\n')
 (raiz/'config/jangada').mkdir()
 (raiz/'config/jangada/jangada.conf').write_text(f'JANGADA_PROJETOS={raiz}/projetos\nJANGADA_WORKTREES={raiz}/worktrees\nJANGADA_AGENTE_ISOLAR=1\nJANGADA_ISOLAR_CASA=minima\nJANGADA_ISOLAR_AMBIENTE=minimo\nJANGADA_ISOLAR_CASA_LER={raiz}/aplicativos\nJANGADA_ISOLAR_OCULTAR_EXTRA={casa_real}\nJANGADA_VALIDAR_REVISOR=claude\n')
 env.update(PATH=f'{raiz}/bin:{raiz}/codigo/bin:/usr/bin:/bin',JANGADA_PATH=str(raiz/'codigo'),JANGADA_ISOLAR_CASA_LER=str(raiz/'aplicativos'),JANGADA_ISOLAR_OCULTAR_EXTRA=str(casa_real),JANGADA_SESSAO='p1-conectividade')
 # Variáveis de autenticação autorizadas ficam somente em memória, não no JSON ou comandos.
 nomes=('OPENAI_API_KEY','ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN')
 autorizadas={k:os.environ[k] for k in nomes if os.environ.get(k)}
 (raiz/'ambiente.json').write_text(json.dumps(env,indent=2))
 projeto=raiz/'projetos/conectividade';projeto.mkdir()
 # Antes de qualquer chamada externa, conferir o isolamento efetivo.
 payload="import os,pathlib,json; assert pathlib.Path('/tmp/.jangada-sem-autoridade').exists(); assert not list(pathlib.Path("+repr(str(casa_real))+ ").iterdir()); print(json.dumps({'casa_real_oculta':True,'marca_fisica':True}))"
 s=subprocess.run([str(raiz/'codigo/bin/jangada-isolar'),'--','/usr/bin/python3','-c',payload],cwd=projeto,env=env,capture_output=True,text=True,timeout=45)
 (registro/'isolamento.stdout.log').write_text(limpar(s.stdout));(registro/'isolamento.stderr.log').write_text(limpar(s.stderr))
 if s.returncode:raise RuntimeError('Isolamento não confirmado; nenhum provedor será chamado. Consulte '+str(registro))
 resultado={'commit':VERSAO,'raiz_sintetica':str(raiz),'registro':str(registro),'credenciais_presentes':credenciais,'codex_modelo_configurado':modelo,'claude_modelo_solicitado':'sonnet','autorizacao_usuario':'Codex executor e Claude revisor, somente dados sintéticos','chamadas':[],'limite':'Prova de conectividade, não execução/revisão da atividade econômica. Credenciais temporárias não pertencem às evidências.'}
 env.update(autorizadas)
 if args.chamar_provedores:
  comandos=[('codex',[str(raiz/'codigo/bin/jangada-isolar'),'--',str(raiz/'codigo/bin/jangada-codex'),'--revisar','--','codex','--output-last-message',str(projeto/'codex-resposta.txt'),'--json'],'JANGADA_P1_CODEX_OK'),('claude',[str(raiz/'codigo/bin/jangada-isolar'),'--','claude','-p','--model','sonnet','--setting-sources','user','--tools','','--output-format','json'],'JANGADA_P1_CLAUDE_OK')]
  for nome,cmd,esperado in comandos:
   inicio=time.monotonic();prompt='Teste sintético de conectividade. Responda somente '+esperado+'. Não leia arquivos nem utilize ferramentas.'
   p=subprocess.Popen(cmd,cwd=projeto,env=env,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
   try:stdout,stderr=p.communicate(prompt,timeout=180)
   except subprocess.TimeoutExpired:
    os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate();stderr+='\nPrazo de 180 segundos excedido.'
   (registro/(nome+'.stdout.log')).write_text(limpar(stdout));(registro/(nome+'.stderr.log')).write_text(limpar(stderr))
   if nome=='codex':resposta=(projeto/'codex-resposta.txt').read_text() if (projeto/'codex-resposta.txt').is_file() else ''
   else:
    try:resposta=json.loads(stdout).get('result','')
    except (ValueError,AttributeError):resposta=''
   sucesso=p.returncode==0 and resposta.strip()==esperado
   resultado['chamadas'].append({'provedor':nome,'codigo':p.returncode,'resposta_esperada':esperado,'resposta_conferida':sucesso,'segundos':round(time.monotonic()-inicio,3),'classificacao':'PASSOU' if sucesso else 'REQUER_ANALISE'})
   (registro/'resumo.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2))
 resultado['pronto_para_preparar_tarefa']=len(resultado['chamadas'])==2 and all(x['resposta_conferida'] for x in resultado['chamadas'])
 (registro/'resumo.json').write_text(json.dumps(resultado,ensure_ascii=False,indent=2))
 print(json.dumps(resultado,ensure_ascii=False,indent=2))
 print('Não compartilhe o HOME sintético: contém credenciais. Envie somente este resumo.')
 return 0 if resultado['pronto_para_preparar_tarefa'] or not args.chamar_provedores else 1
if __name__=='__main__':raise SystemExit(main())
