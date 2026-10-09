"""Executa somente ensaios locais autorizados; nunca inicia provedor real."""
import csv,hashlib,importlib.util,itertools,json,os,signal,subprocess,sys,time
from pathlib import Path
SAIDA=Path(__file__).resolve().parents[1]
ROOT=Path(json.loads((SAIDA/'evidencias/origem-ensaio.json').read_text())['raiz_sintetica'])
CODIGO=ROOT/'codigo'
ENV=json.loads((ROOT/'ambiente.json').read_text())
ENV.update(JANGADA_P0_EVIDENCIAS=str(SAIDA/'evidencias'),JANGADA_ESTADO=str(ROOT/'estado/jangada'),JANGADA_CONFIG=str(ROOT/'config/jangada'),
    PYTHONDONTWRITEBYTECODE='1',R_PROFILE_USER='/dev/null',R_ENVIRON_USER='/dev/null')
RESULTADOS=json.loads((SAIDA/'evidencias/comandos.json').read_text()) if (SAIDA/'evidencias/comandos.json').exists() else []


def dentro(p):
    p=Path(p).resolve()
    if not (p.is_relative_to(ROOT) or p.is_relative_to(SAIDA)):
        raise ValueError('Destino fora do ensaio')
    return p


def rodar(nome,args,prazo=120,cwd=None):
    inicio=time.monotonic()
    processo=subprocess.Popen(args,env=ENV,cwd=cwd or CODIGO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:stdout,stderr=processo.communicate(timeout=prazo);codigo=processo.returncode
    except subprocess.TimeoutExpired:
        os.killpg(processo.pid,signal.SIGKILL);stdout,stderr=processo.communicate();codigo=124
    (SAIDA/'evidencias'/f'{nome}.stdout.log').write_text(stdout)
    (SAIDA/'evidencias'/f'{nome}.stderr.log').write_text(stderr)
    item={'caso':nome,'comando':args,'codigo':codigo,'segundos':round(time.monotonic()-inicio,3),'classificacao':'PASSOU' if codigo==0 else 'BLOQUEADO' if codigo in (124,125) else 'FALHOU'}
    RESULTADOS.append(item);(SAIDA/'evidencias/comandos.json').write_text(json.dumps(RESULTADOS,ensure_ascii=False,indent=2))
    print(json.dumps(item,ensure_ascii=False),flush=True)
    return item


def comparar(rodada):
    base=SAIDA/'privado'/f'rodada-{rodada}'
    registros=[]
    for nome in ('painel','ql','indicadores','shift'):
        tolerancia=1e-8;maximo=0;numero=0
        with (base/'python'/f'{nome}.csv').open() as pf,(base/'R'/f'{nome}.csv').open() as rf:
            a=csv.DictReader(pf);b=csv.DictReader(rf);assert a.fieldnames==b.fieldnames,(nome,a.fieldnames,b.fieldnames)
            for x,y in itertools.zip_longest(a,b):
                assert x is not None and y is not None
                for chave in a.fieldnames:
                    if chave in ('municipio','setor','ano'):assert x[chave]==y[chave],(nome,chave,x,y)
                    else:
                        vx=float(x[chave]);vy=float(y[chave]);d=abs(vx-vy);maximo=max(maximo,d)
                        assert d<=tolerancia+1e-9*max(abs(vx),abs(vy)),(nome,chave,vx,vy)
                numero+=1
        registros.append({'arquivo':nome,'linhas':numero,'diferenca_absoluta_max':maximo,'classificacao':'PASSOU'})
    py=json.loads((base/'python/qualidade.json').read_text())
    with (base/'R/qualidade.csv').open() as f:r=next(csv.DictReader(f))
    assert py['invalidos']==int(r['invalidos']) and py['duplicatas']==int(r['duplicatas']) and py['imputadas']==int(r['imputadas'])
    geracao=json.loads((base/'geracao.json').read_text())
    assert py['invalidos']==geracao['invalidos'] and py['duplicatas']==geracao['duplicatas_identicas'] and py['imputadas']==geracao['ausencias']
    (SAIDA/'evidencias'/f'oraculos-comparacao-{rodada}.json').write_text(json.dumps({'rodada':rodada,'comparacoes':registros,'qualidade_python':py,'qualidade_R':r,'classificacao':'PASSOU'},indent=2))
    print('Comparacao independente:',rodada,'PASSOU',flush=True)


def main():
    # Guardas não substituem isolamento. Impedem operações proibidas nos ensaios.
    g=ROOT/'guardas/git'
    g.write_text('''#!/usr/bin/python3
import os,sys
if any(a in {'merge','reset','clean','push','rebase','tag'} for a in sys.argv[1:]):
 print('BLOQUEADO: operacao Git proibida',file=sys.stderr);sys.exit(125)
os.execv('/usr/bin/git',['git',*sys.argv[1:]])
''');g.chmod(0o700)
    for rodada in (1,2):
        r=rodar(f'oraculo-R-{rodada}',['/usr/bin/Rscript','--vanilla',str(SAIDA/'scripts/oraculo.R'),str(ROOT/f'projetos/economia-sintetica/rodada-{rodada}'),str(SAIDA/f'privado/rodada-{rodada}/R')],prazo=180,cwd=ROOT)
        if r['codigo']!=0:raise RuntimeError('Oraculo R falhou; nao usar gabarito')
        comparar(rodada)
    rodar('p0-32',['/usr/bin/python3','-B','testes/confianca-p0.py'],prazo=180)
    for nome in ('orquestracao','executor','supervisao','operacional','deterministico','acompanhamento','painel-orquestracao'):
        rodar(nome,['/usr/bin/python3','-B','testes/'+nome+'.py'],prazo=180)
    # Os 4 testes de comunicação são reexecutados como parte dos 67 casos Qt.
    rodar('interface-67',['/usr/bin/python3','-B','testes/tarefas.py'],prazo=120)
    rodar('fim',['/usr/bin/bash','testes/fim.sh'])
    rodar('restaurar',['/usr/bin/bash','testes/restaurar.sh'])

if __name__=='__main__':main()
