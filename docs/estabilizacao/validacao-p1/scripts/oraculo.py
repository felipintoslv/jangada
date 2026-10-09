"""Oráculo de auditoria, inacessível aos modelos. Não é implementação do executor."""
import csv,hashlib,json,math,random,subprocess,sys,time
from pathlib import Path

SAIDA=Path(__file__).resolve().parents[1]
ROOT=Path(json.loads((SAIDA/'evidencias/origem-ensaio.json').read_text())['raiz_sintetica'])
PROJETO=ROOT/'projetos/economia-sintetica'
PROJETO.mkdir(exist_ok=True)
PRIVADO=SAIDA/'privado'
SEMENTES=(6184937,9302711)
ANOS=range(2019,2026)
MUNICIPIOS=[f'900{i:04d}' for i in range(1,151)]
SETORES=[f'S{i:03d}' for i in range(1,81)]

def gravar(p,cols,linhas):
    p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',newline='') as f:
        w=csv.writer(f);w.writerow(cols);w.writerows(linhas)

def ler(p):
    with p.open() as f:return list(csv.DictReader(f))

def gerar(rodada,semente):
    rng=random.Random(semente);publico=PROJETO/f'rodada-{rodada}';publico.mkdir(exist_ok=True)
    dados=[]
    for i,m in enumerate(MUNICIPIOS):
        tamanho=rng.uniform(25,250)*(1.3 if rodada==2 else 1)
        foco=(i*(7 if rodada==1 else 11))%80
        for j,s in enumerate(SETORES):
            distancia=min((j-foco)%80,(foco-j)%80)
            base=max(1,int(tamanho*(1+6*math.exp(-distancia/(3 if rodada==1 else 5)))))
            for ano in ANOS:
                t=ano-2019
                tendencia=(j%10-3)*0.025 + (0.018 if rodada==2 else 0)
                local=((i%9)-4)*0.012
                estrutural=(1+max(t-2,0)*(0.10 if (j+i)%13<3 else -0.025))
                emprego=max(1,round(base*math.exp((tendencia+local)*t)*estrutural*(1+rng.uniform(-0.02,0.02))))
                versao='antiga' if ano<=2021 else 'nova'
                codigo=s if versao=='antiga' or j<60 else 'N'+s[1:]
                dados.append([m,codigo,versao,ano,emprego])
    interiores=[k for k,r in enumerate(dados) if 2020<=r[3]<=2024]
    faltas=rng.sample(interiores,100 if rodada==1 else 240)
    for k in faltas:dados[k][4]=''
    duplicadas=rng.sample([r for r in dados if r[4]!=''],8 if rodada==1 else 15)
    irregular=[['MUNICIPIO_INVALIDO','S001','antiga',2020,100],
                ['9000001','SETOR_INVALIDO','antiga',2020,100],
                ['9000001','S001','antiga',2018,100],
                ['9000001','S001','nova',2026,100],
                ['9000001','S001','antiga',2020,-100],
                ['9000001','S001','antiga',2022,100]]
    rng.shuffle(dados)
    gravar(publico/'emprego.csv',['municipio','codigo','versao','ano','emprego'],dados+duplicadas+irregular)
    gravar(publico/'municipios.csv',['municipio','nome','regiao','perfil'],[[m,f'Municipio sintetico {i+1}',f'R{i%5+1}',f'P{i%6+1}'] for i,m in enumerate(MUNICIPIOS)])
    gravar(publico/'classificacao.csv',['codigo','versao','setor'],[[s,'antiga',s] for s in SETORES]+[[s if j<60 else 'N'+s[1:],'nova',s] for j,s in enumerate(SETORES)])
    (publico/'LEIA-ME.md').write_text('''# Dados inteiramente sintéticos

150 municípios fictícios, 80 atividades em classificação CNAE simulada, 2019 a 2025. IDs não são códigos oficiais IBGE; classes S/N não são códigos oficiais CNAE. Não inferir resultados sobre municípios reais. Duas versões anuais devem ser compatibilizadas com classificacao.csv, chave (codigo, versao). Nenhum dado observado real foi usado.

Contrato público fixado antes de modelos: excluir IDs/anos/classificações/emprego negativo inválidos; colapsar duplicatas idênticas por município/setor/ano, e bloquear conflitos não explicados. Ausências são desconhecidas, não zero. Para este ensaio, interpolar linearmente somente lacunas internas na mesma série e reportar imputações. Nunca usar futuro em indicadores contemporâneos com corte temporal, exceto interpolação retrospectiva explicitamente indicada. Bases 2019/2025 não podem ser imputadas.

QL nacional por ano: (e_ij/E_i)/(E_j/E); HHI soma p_j²; Shannon menos soma p_j log(p_j); número efetivo exp(Shannon). Emprego total e crescimento 2025/2019 menos 1. Shift-share clássico 2019 a 2025: NS=e0*G, IM=e0*(g_j-G), RS=e1-e0*(1+g_j). A soma deve igualar e1-e0 por célula e município. Não produzir inferências causais com esta descrição observacional.

Executar análise R, tabelas, gráficos e Shiny, com documentação de escolhas, cobertura, irregularidades, versões e limites. Gabarito e testes privados não estão neste projeto.
''')
    manifesto={'rodada':rodada,'semente_privada':semente,'ausencias':len(faltas),'duplicatas_identicas':len(duplicadas),'invalidos':len(irregular),'linhas_brutas':len(dados)+len(duplicadas)+len(irregular),'celulas_painel':84000,'synthetic':True}
    return publico,manifesto

def calcular_python(publico,destino):
    mapping={(r['codigo'],r['versao']):r['setor'] for r in ler(publico/'classificacao.csv')}
    painel={};invalidos=dups=0
    for r in ler(publico/'emprego.csv'):
        ano=int(r['ano']);s=mapping.get((r['codigo'],r['versao']));v=None if not r['emprego'] else float(r['emprego'])
        if r['municipio'] not in MUNICIPIOS or ano not in ANOS or s is None or (v is not None and v<0) or r['versao']!=('antiga' if ano<=2021 else 'nova'):
            invalidos+=1;continue
        key=(r['municipio'],s,ano)
        if key in painel:
            if painel[key]!=v:raise ValueError('duplicata conflitante')
            dups+=1
        painel[key]=v
    assert len(painel)==84000
    imputadas=0
    for m in MUNICIPIOS:
        for s in SETORES:
            observados={a:painel[m,s,a] for a in ANOS if painel[m,s,a] is not None}
            for ano in ANOS:
                if painel[m,s,ano] is None:
                    antes=max(a for a in observados if a<ano)
                    depois=min(a for a in observados if a>ano)
                    painel[m,s,ano]=observados[antes]+(observados[depois]-observados[antes])*(ano-antes)/(depois-antes)
                    imputadas+=1
    mi={(m,a):sum(painel[m,s,a] for s in SETORES) for m in MUNICIPIOS for a in ANOS}
    sj={(s,a):sum(painel[m,s,a] for m in MUNICIPIOS) for s in SETORES for a in ANOS}
    nacional={a:sum(mi[m,a] for m in MUNICIPIOS) for a in ANOS}
    gravar(destino/'painel.csv',['municipio','setor','ano','emprego'],[(m,s,a,painel[m,s,a]) for m in MUNICIPIOS for s in SETORES for a in ANOS])
    gravar(destino/'ql.csv',['municipio','setor','ano','ql'],[(m,s,a,(painel[m,s,a]/mi[m,a])/(sj[s,a]/nacional[a])) for m in MUNICIPIOS for s in SETORES for a in ANOS])
    indicadores=[]
    for m in MUNICIPIOS:
        for a in ANOS:
            props=[painel[m,s,a]/mi[m,a] for s in SETORES]
            hhi=sum(p*p for p in props);sh=-sum(p*math.log(p) for p in props if p>0)
            indicadores.append([m,a,mi[m,a],mi[m,a]/mi[m,2019]-1,hhi,1-hhi,sh,math.exp(sh)])
    gravar(destino/'indicadores.csv',['municipio','ano','emprego','crescimento_base','hhi','diversidade','shannon','efetivos'],indicadores)
    G=nacional[2025]/nacional[2019]-1;shift=[];residual=0
    for m in MUNICIPIOS:
        for s in SETORES:
            e0=painel[m,s,2019];e1=painel[m,s,2025];g=sj[s,2025]/sj[s,2019]-1
            ns=e0*G;im=e0*(g-G);rs=e1-e0*(1+g)
            residual=max(residual,abs((ns+im+rs)-(e1-e0)))
            shift.append([m,s,e0,e1,ns,im,rs,e1-e0])
    gravar(destino/'shift.csv',['municipio','setor','e0','e1','ns','im','rs','delta'],shift)
    assert residual<1e-8
    assert all(abs(sum(painel[m,s,a]/mi[m,a] for s in SETORES)-1)<1e-12 for m in MUNICIPIOS for a in ANOS)
    assert all(abs(sum(mi[m,a] for m in MUNICIPIOS)-sum(sj[s,a] for s in SETORES))<1e-7 for a in ANOS)
    (destino/'qualidade.json').write_text(json.dumps({'invalidos':invalidos,'duplicatas':dups,'imputadas':imputadas,'residual_shift_max':residual,'totais':nacional},indent=2))

if __name__=='__main__':
    for rodada,semente in enumerate(SEMENTES,1):
        inicio=time.monotonic();publico,manifesto=gerar(rodada,semente)
        destino=PRIVADO/f'rodada-{rodada}';destino.mkdir(exist_ok=True)
        (destino/'geracao.json').write_text(json.dumps(manifesto,indent=2))
        calcular_python(publico,destino/'python')
        print(json.dumps({'rodada':rodada,'linhas':manifesto['linhas_brutas'],'segundos':time.monotonic()-inicio}))
