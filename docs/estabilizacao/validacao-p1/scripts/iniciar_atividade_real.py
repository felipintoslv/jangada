#!/usr/bin/python3
"""Abre atividade econômica sintética pelo Jangada original, em tmux próprio."""
import argparse,json,os,subprocess,sys
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]

def main():
 parser=argparse.ArgumentParser();parser.add_argument('raiz',type=Path,help='Raiz /tmp/jreal-* registrada pelo preparador');args=parser.parse_args()
 raiz=args.raiz.resolve();registro=OUT/'evidencias'/raiz.name
 if args.raiz.is_symlink() or raiz.parent!=Path('/tmp') or not raiz.name.startswith('jreal-'):raise ValueError('Raiz não corresponde ao ensaio')
 resumo=json.loads((registro/'resumo.json').read_text())
 if resumo['raiz_sintetica']!=str(raiz) or not resumo.get('pronto_para_preparar_tarefa'):raise ValueError('Dois provedores reais precisam passar na prova de conectividade antes da atividade')
 revisor=resumo.get('revisor_autorizado','claude')
 env=json.loads((raiz/'ambiente.json').read_text());env.pop('JANGADA_SESSAO',None)
 for k in ('HOME','XDG_CONFIG_HOME','XDG_DATA_HOME','XDG_STATE_HOME','XDG_CACHE_HOME','XDG_RUNTIME_DIR','TMPDIR','TMUX_TMPDIR','JANGADA_PATH'):
  if not Path(env[k]).resolve().is_relative_to(raiz):raise ValueError('Caminho externo em '+k)
 for k in ('OPENAI_API_KEY','ANTHROPIC_API_KEY','CLAUDE_CODE_OAUTH_TOKEN'):
  if os.environ.get(k):env[k]=os.environ[k]
 env.update(GIT_AUTHOR_NAME='Experimento sintetico Jangada',GIT_AUTHOR_EMAIL='ensaio@example.invalid',GIT_COMMITTER_NAME='Experimento sintetico Jangada',GIT_COMMITTER_EMAIL='ensaio@example.invalid')
 projeto=raiz/'projetos/economia';code=raiz/'codigo'
 if projeto.exists():raise ValueError('Atividade já preparada; não sobrescrever. Consulte atividade-real.json')
 projeto.mkdir()
 import shutil
 # Somente a primeira rodada é entregue ao executor. A segunda e o gabarito ficam privados.
 shutil.copytree(OUT/'artefatos/dados-1',projeto/'dados',symlinks=False)
 (projeto/'AGENTS.md').write_text('''# Ensaio sintético de confiabilidade\n\nTrabalhe somente neste repositório. Dados artificiais, sem inferências sobre municípios reais. Não instale dependências, não altere estados do Jangada ou configuração de provedores. Não leia credenciais ou projetos externos. Não faça merge, push, reset, clean, rebase ou tag. Faça commits pequenos e execute testes. Nunca declare aprovação autorizada ou conclusão da fila. A revisão protegida e a conferência privada pertencem ao controlador.\n''')
 (projeto/'analise.R').write_text('# Entrada inicial do experimento. Implementação a cargo do executor.\n')
 (projeto/'.gitignore').write_text('resultados/\n.Rhistory\n.RData\n')
 def rodar(nome,cmd,prazo=60):
  r=subprocess.run(cmd,cwd=projeto,env=env,capture_output=True,text=True,timeout=prazo)
  (registro/(nome+'.stdout.log')).write_text(r.stdout);(registro/(nome+'.stderr.log')).write_text(r.stderr)
  if r.returncode:raise RuntimeError(nome+' falhou. Consulte os logs sintéticos.')
  return r.stdout
 rodar('economia-git-init',['/usr/bin/git','init','-q','-b','ensaio'])
 rodar('economia-git-add',['/usr/bin/git','add','.'])
 rodar('economia-git-commit',['/usr/bin/git','-c','core.hooksPath=/dev/null','commit','-qm','Dados sintéticos e contrato público do experimento'])
 politica=raiz/'politica-economia.json';politica.write_text(json.dumps({'dados':'remoto_permitido','revisao_minima':{'3':{'independente':True,'contexto':'repositorio'}}}))
 cli=str(code/'bin/jangada-projeto')
 rodar('economia-cadastro',[cli,'--projeto',str(projeto),'cadastrar','--politica',str(politica)])
 criterios=['Dados artificiais, cardinalidade e irregularidades explícitas','QL nacional anual com denominadores conferidos','HHI Shannon e número efetivo de setores','Shift-share clássico com identidade aditiva','Ausências não são zero, sem vazamento temporal','Nenhuma conclusão causal sem identificação','R reproduzível, tabelas, gráficos, Shiny e documentação','Parecer independente, versão e verificações determinísticas separados']
 cmd=[cli,'--projeto',str(projeto),'atividade','--titulo','Economia municipal sintética 2019 a 2025','--objetivo','Produzir artefato R verificável para revisão independente']
 for c in criterios:cmd+=['--criterio',c]
 atividade=json.loads(rodar('economia-atividade',cmd))['atividade']
 prompt=raiz/'pedido-economia.md'
 prompt.write_text('''Implemente a análise econômica pedida em dados/LEIA-ME.md. Leia AGENTS.md. Crie analise.R executável com Rscript analise.R DIRETORIO_DADOS DIRETORIO_SAIDA e app.R Shiny, testes públicos e metodologia.md com reprodução, critérios e limites. Não instale pacotes. Use R base quando suficiente. A saída deve incluir painel.csv (municipio,setor,ano,emprego), ql.csv (municipio,setor,ano,ql), indicadores.csv (municipio,ano,emprego,crescimento_base,hhi,diversidade,shannon,efetivos) e shift.csv (municipio,setor,e0,e1,ns,im,rs,delta). Ordene por municipio/setor/ano, ou municipio/ano nos indicadores. Crescimento é proporcional à base 2019. Gere tabelas e visualizações, identifique os dados como sintéticos e descreva duplicatas, inválidos e imputações. Não conclua causalidade. Não copie resultados de referência; o auditor os conferirá fora do isolamento. Faça commits da implementação e dos testes, sem dados/saídas geradas. Não integre ou encerre a sessão; deixe a entrega para revisão independente protegida pelo controlador. Declare comandos executados, problemas e limitações. Aprovação textual do executor não é aprovação autorizada.\n''')
 dados={'raiz_sintetica':str(raiz),'projeto':str(projeto),'atividade':atividade,'sessao':'economia--execucao','worktree_esperada':str(raiz/'worktrees/economia/execucao'),'executor':'codex','revisor':revisor,'modelo_executor_configurado':resumo['codex_modelo_configurado'],'modelo_revisor_solicitado':('sonnet' if revisor=='claude' else None),'criterios':criterios,'fase':'PREPARADA'}
 (registro/'atividade-real.json').write_text(json.dumps(dados,ensure_ascii=False,indent=2))
 print(json.dumps(dados,ensure_ascii=False,indent=2),flush=True)
 print('Abrindo Jangada no tmux sintético. Não confirme integração. Após o executor parar, desanexe com Ctrl-b d; a sessão e o trabalho permanecem preservados.',flush=True)
 if not sys.stdin.isatty():raise RuntimeError('Abra em terminal interativo para confiança e supervisão; atividade preservada')
 comando=[str(code/'bin/jangada-agente'),'--projeto',str(projeto),'--nome','execucao','--agente','codex','--revisor',revisor,'--atividade',atividade,'--prompt-arquivo',str(prompt)]
 r=subprocess.run(comando,cwd=projeto,env=env)
 print('Jangada retornou com código',r.returncode,'; nenhum encerramento ou integração foi realizado.')
 print('Registro:',registro)
 return r.returncode
if __name__=='__main__':raise SystemExit(main())
