#!/usr/bin/python3
"""Prepara projeto público novo; não chama modelos nem toca sessões existentes."""
import argparse,json,subprocess
from pathlib import Path
OUT=Path(__file__).resolve().parents[1]
FONTE=Path('/home/felipinto/Projetos/par-cobaia')
BASE='0331e4a4daafc20a1b1ba5767f0e825fbf0a9b03'

def main():
 p=argparse.ArgumentParser();p.add_argument('raiz',type=Path);a=p.parse_args();raiz=a.raiz.resolve()
 if a.raiz.is_symlink() or raiz.parent!=Path('/tmp') or not raiz.name.startswith('jreal-'):raise ValueError('Raiz não corresponde ao ambiente sintético')
 env=json.loads((raiz/'ambiente.json').read_text());env.pop('JANGADA_SESSAO',None)
 for chave in ('HOME','XDG_CONFIG_HOME','XDG_STATE_HOME','XDG_RUNTIME_DIR','TMPDIR','TMUX_TMPDIR','JANGADA_PATH'):
  if not Path(env[chave]).resolve().is_relative_to(raiz):raise ValueError('Caminho real em '+chave)
 projeto=raiz/'projetos/mini-p0'
 if projeto.exists():raise ValueError('Projeto já existe; não sobrescrever ou limpar')
 arquivos=subprocess.check_output(['/usr/bin/git','-C',str(FONTE),'ls-tree','-r','--name-only',BASE],env=env,text=True).splitlines()
 permitidos=[n for n in arquivos if n in ('AGENTS.md','README.md') or n.startswith(('R/','scripts/','testes/'))]
 projeto.mkdir(mode=0o700)
 for nome in permitidos:
  if '..' in Path(nome).parts:raise ValueError('Caminho não permitido')
  alvo=projeto/nome;alvo.parent.mkdir(parents=True,exist_ok=True)
  alvo.write_bytes(subprocess.check_output(['/usr/bin/git','-C',str(FONTE),'show',BASE+':'+nome],env=env))
 # Sem história Git do original, .Renviron, gabarito, links ou hooks copiados.
 (projeto/'.gitignore').write_text('dados/brutos/\nsaidas/\n.Rhistory\n.RData\n')
 (projeto/'.jangada').mkdir();validar=projeto/'.jangada/validar.sh'
 validar.write_text('#!/bin/sh\nset -eu\nRscript testes/rodar.R\n');validar.chmod(0o700)
 env.update(GIT_AUTHOR_NAME='Ensaio sintetico',GIT_AUTHOR_EMAIL='ensaio@example.invalid',GIT_COMMITTER_NAME='Ensaio sintetico',GIT_COMMITTER_EMAIL='ensaio@example.invalid')
 for cmd in (['init','-q','-b','ensaio'],['add','.'],['-c','core.hooksPath=/dev/null','commit','-qm','Base pública independente do ensaio mínimo']):
  subprocess.run(['/usr/bin/git','-C',str(projeto),*cmd],env=env,check=True,capture_output=True)
 pedido=raiz/'pedido-mini-p0.md';pedido.write_text('''Leia AGENTS.md. Gere a base fictícia com scripts/gerar_dados.R dentro desta cópia, sem instalar pacotes. Implemente resumo_uf(base) em R/indicadores.R com totais de empregos e número de municípios distintos por UF e ano. Cada ano possui denominador próprio. Municípios repetidos por setor contam uma vez. Ausências propagam como desconhecido; não substituir por zero. Preserve funções existentes. Acrescente testes públicos a testes/rodar.R e execute-os. Registre os comandos e faça commits pequenos. Não declare aprovação autorizada, não integre, não encerre e não leia credenciais ou projetos externos. Deixe a revisão independente para o controlador.\n''')
 reg=OUT/'evidencias'/raiz.name
 resumo={'projeto':str(projeto),'codigo_p0':str(raiz/'codigo'),'base_fonte':BASE,'sem_historico_original':True,'sem_links_de_dados':True,'sem_gabarito':True,'chamadas_modelos':0,'executor':'codex','revisor':'agy','pedido':str(pedido),'fase':'PREPARADA, autenticação isolada agy ainda necessária'}
 (reg/'mini-p0-preparacao.json').write_text(json.dumps(resumo,ensure_ascii=False,indent=2));print(json.dumps(resumo,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
