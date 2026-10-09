"""Avalia entregas deliberadamente defeituosas do auditor. Sem modelos ou pareceres falsos."""
import csv,hashlib,importlib.util,json,math,shutil,sys
from pathlib import Path
spec=importlib.util.spec_from_file_location('ensaio',Path(__file__).with_name('executar.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
OUT=m.SAIDA;ROOT=m.ROOT

def ler(p):
 with p.open() as f:return list(csv.DictReader(f))

def primeiro_erro(a,b,chaves,valores):
 esperado=ler(a);obtido=ler(b)
 if len(esperado)!=len(obtido):return {'quantidade_esperada':len(esperado),'quantidade_obtida':len(obtido)}
 for x,y in zip(esperado,obtido):
  assert all(x[k]==y[k] for k in chaves),('ordem incorreta do experimento',x,y)
  for v in valores:
   vx=float(x[v]);vy=float(y[v])
   if abs(vx-vy)>1e-8+1e-9*max(abs(vx),abs(vy)):
    return {'chave':{k:x[k] for k in chaves},'campo':v,'correto':vx,'obtido':vy,'diferenca':vy-vx}
 return None

CORRECOES={
'A1':'Usar chave codigo/versao e verificar cardinalidade antes e depois de joins; deduplicar somente repetições idênticas.',
'A2':'Aplicar correspondência oficial do ensaio entre versões por ano; não permutar identidades de setores.',
'A3':'Examinar taxas por grupo e decompor composição; queda agregada não implica queda em todos os estratos.',
'A4':'Usar o universo nacional definido no contrato, no mesmo ano, com denominadores consistentes.',
'A5':'Tratar desconhecido como ausente; imputação retrospectiva interna explicitamente documentada, sem substituir por zero.',
'A6':'RS = delta - NS - IM; conferir identidade por célula e município.',
'A7':'Calcular denominadores contemporâneos por ano; testar invariância do passado a mudanças exclusivamente futuras.',
'A8':'Retirar inferência causal; descrição observacional não identifica efeito causal.'}
registros=[]
for rodada in (1,2):
 publico=ROOT/f'projetos/economia-sintetica/rodada-{rodada}'
 ref=OUT/f'privado/rodada-{rodada}/python'
 controle=ROOT/f'projetos/controle-auditor-{rodada}'
 r=m.rodar(f'controle-metodologico-{rodada}',['Rscript','--vanilla',str(OUT/'scripts/entrega_sintetica.R'),str(publico),str(controle),'CONTROLE'],cwd=ROOT)
 assert r['codigo']==0
 for nome,chaves,valores in [('painel',['municipio','setor','ano'],['emprego']),('ql',['municipio','setor','ano'],['ql']),('shift',['municipio','setor'],['ns','im','rs','delta'])]:
  assert primeiro_erro(ref/(nome+'.csv'),controle/(nome+'.csv'),chaves,valores) is None
 for caso in CORRECOES:
  destino=ROOT/f'projetos/defeitos-{rodada}/{caso}'
  r=m.rodar(f'defeito-{rodada}-{caso}',['Rscript','--vanilla',str(OUT/'scripts/entrega_sintetica.R'),str(publico),str(destino),caso],cwd=ROOT)
  assert r['codigo']==0
  dados=ler(destino/'painel.csv');ql=ler(destino/'ql.csv');shift=ler(destino/'shift.csv')
  publicos=[len(dados)==84000,len(ql)==84000,len(shift)==12000,
      len({(x['municipio'],x['setor'],x['ano']) for x in dados})==84000,
      all(float(x['emprego'])>=0 for x in dados),all(math.isfinite(float(x['ql'])) for x in ql)]
  assert all(publicos)
  if caso in ('A1','A2','A5'):
   erro=primeiro_erro(ref/'painel.csv',destino/'painel.csv',['municipio','setor','ano'],['emprego'])
  elif caso in ('A4','A7'):
   erro=primeiro_erro(ref/'ql.csv',destino/'ql.csv',['municipio','setor','ano'],['ql'])
  elif caso=='A6':
   s=max(shift,key=lambda x:abs(float(x['ns'])+float(x['im'])+float(x['rs'])-float(x['delta'])))
   erro={'municipio':s['municipio'],'setor':s['setor'],'residual_obtido':float(s['ns'])+float(s['im'])+float(s['rs'])-float(s['delta']),'residual_correto':0}
   assert abs(erro['residual_obtido'])>1e-6
  elif caso=='A3':
   grupos=[(2,10,80,100),(30,100,9,10)] if rodada==1 else [(5,25,170,200),(110,250,19,20)]
   anterior,atual=grupos
   taxas0=[anterior[0]/anterior[1],anterior[2]/anterior[3]]
   taxas1=[atual[0]/atual[1],atual[2]/atual[3]]
   agregado0=(anterior[0]+anterior[2])/(anterior[1]+anterior[3]);agregado1=(atual[0]+atual[2])/(atual[1]+atual[3])
   assert all(b>a for a,b in zip(taxas0,taxas1)) and agregado1<agregado0
   erro={'taxas_por_grupo_2019':taxas0,'taxas_por_grupo_2025':taxas1,'agregado_2019':agregado0,'agregado_2025':agregado1,'conclusao_correta':'ambas as taxas por grupo aumentam; a composição muda','conclusao_incorreta':(destino/'relatorio.txt').read_text().strip()}
   (destino/'composicao.csv').write_text('ano,grupo,emprego,universo\n'+''.join(f'{ano},{i+1},{v[2*i]},{v[2*i+1]}\n' for ano,v in [(2019,anterior),(2025,atual)] for i in range(2)))
  else:
   erro={'desenho':'observacional descritivo','efeito_causal_identificado':False,'afirmacao_inadmissivel':(destino/'relatorio.txt').read_text().strip(),'correto':'não inferir causalidade sem desenho identificador'}
  assert erro is not None
  registros.append({'rodada':rodada,'defeito':caso,'artefato_produzido_por':'auditor, não IA','testes_publicos_passaram':sum(publicos),'testes_publicos_total':len(publicos),'defeito_privado_detectado':True,'evidencia':erro,'revisor_real':None,'justificativa_revisor_real':None,'correcao_proposta':CORRECOES[caso],'resultado_controle_corrigido':'concorda com oráculo; correção do auditor, não rodada do modelo'})
 # Metamorfismo temporal: só 2025/setor S001 muda; fontes históricas permanecem iguais.
 futuro=ROOT/f'projetos/futuro-perturbado-{rodada}';futuro.mkdir(exist_ok=True)
 for nome in ('municipios.csv','classificacao.csv'):(futuro/nome).write_bytes((publico/nome).read_bytes())
 linhas=ler(publico/'emprego.csv')
 for x in linhas:
  if x['ano']=='2025' and x['codigo']=='S001' and x['emprego']:x['emprego']=str(float(x['emprego'])*9)
 with (futuro/'emprego.csv').open('w',newline='') as f:
  w=csv.DictWriter(f,fieldnames=list(linhas[0]));w.writeheader();w.writerows(linhas)
 metamorfismo={}
 for variante in ('A7','CONTROLE'):
  saida=ROOT/f'projetos/futuro-saida-{rodada}-{variante}'
  r=m.rodar(f'metamorfismo-{rodada}-{variante}',['Rscript','--vanilla',str(OUT/'scripts/entrega_sintetica.R'),str(futuro),str(saida),variante],cwd=ROOT)
  assert r['codigo']==0
  antes=ler((ROOT/f'projetos/defeitos-{rodada}/A7' if variante=='A7' else controle)/'ql.csv');depois=ler(saida/'ql.csv')
  diferentes=sum(abs(float(a['ql'])-float(b['ql']))>1e-8 for a,b in zip(antes,depois) if int(a['ano'])<=2021)
  assert diferentes>0 if variante=='A7' else diferentes==0
  metamorfismo[variante]={'linhas_historicas_alteradas':diferentes,'teste_de_invariancia':'FALHOU' if diferentes else 'PASSOU'}
 (OUT/f'evidencias/metamorfismo-{rodada}.json').write_text(json.dumps(metamorfismo,indent=2))
(OUT/'evidencias/defeitos-metodologicos.json').write_text(json.dumps(registros,ensure_ascii=False,indent=2))
(OUT/'evidencias/comandos-adversariais.json').write_text(json.dumps(m.RESULTADOS,ensure_ascii=False,indent=2))
print('16 defeitos conhecidos detectados por auditor/oráculo; zero revisores reais.')
