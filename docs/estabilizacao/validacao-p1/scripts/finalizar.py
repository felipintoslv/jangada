"""Consolida evidências locais, sem modificar a versão avaliada."""
import hashlib,io,json,re,shutil,subprocess,tarfile
from pathlib import Path
OUT=Path(__file__).resolve().parents[1];EV=OUT/'evidencias';DOC=OUT/'relatorios'
ROOT=Path(json.loads((EV/'origem-ensaio.json').read_text())['raiz_sintetica'])
# Preservar somente dados e artefatos públicos regulares, nunca dereferenciar alias.
for n in (1,2):
 for origem,destino in [(ROOT/f'projetos/economia-sintetica/rodada-{n}',OUT/f'artefatos/dados-{n}'),(ROOT/f'projetos/defeitos-{n}',OUT/f'artefatos/defeitos-{n}'),(ROOT/f'projetos/controle-auditor-{n}',OUT/f'artefatos/controle-{n}')]:
  if origem.exists():shutil.copytree(origem,destino,dirs_exist_ok=True,symlinks=True)
# Consolidar comandos sem perder o registro da execução inicial.
reg=[]
for f in [Path('/tmp/jangada-p1-execucao.log'),Path('/tmp/jangada-p1-adversarial.log'),Path('/tmp/jangada-p1-backend.log')]:
 if f.exists():
  (EV/f.name).write_bytes(f.read_bytes())
  for linha in f.read_text().splitlines():
   try:v=json.loads(linha)
   except ValueError:continue
   if isinstance(v,dict) and 'caso' in v:reg.append(v)
for f in [EV/'comandos.json',EV/'comandos-adversariais.json',EV/'comandos-backend.json']:
 if f.exists():
  for v in json.loads(f.read_text()):
   if v not in reg:reg.append(v)
for v in reg:
 if v['caso'] in ('perfil-sem-rede','interface-67'):v['classificacao_auditoria']='BLOQUEADO';v['motivo']='Restrição de sockets do ambiente; código bruto preservado'
(EV/'comandos-consolidados.json').write_text(json.dumps(reg,ensure_ascii=False,indent=2))
# Confirmar integridade de todas as versões, e bytes da cópia de produção.
repos=['jangada','jangada-baseline-2026-10','jangada-confianca-p0'];estados={}
for r in repos:
 p=Path('/home/felipinto/Projetos')/r
 estados[r]={'commit':subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip(),'status':subprocess.check_output(['git','-C',str(p),'status','--short','--branch'],text=True)}
commit='17178ded546642e3246bfe3bd5c33df8da821874'
bruto=subprocess.check_output(['git','-C','/home/felipinto/Projetos/jangada-confianca-p0','archive',commit]);checados=0
with tarfile.open(fileobj=io.BytesIO(bruto)) as tf:
 for membro in tf:
  if membro.isfile():
   assert tf.extractfile(membro).read()==(ROOT/'codigo'/membro.name).read_bytes(),membro.name;checados+=1
(EV/'integridade-final.json').write_text(json.dumps({'worktrees':estados,'arquivos_codigo_comparados':checados,'codigo_copia_identico':True},ensure_ascii=False,indent=2))
common='\n\nVersão avaliada: `17178ded546642e3246bfe3bd5c33df8da821874`. Resultados externos às três worktrees. Não houve execução de modelos reais, chamadas externas, mudanças de produção, merge, push ou tags.\n'
docs={
'AMBIENTE_ISOLADO.md':'''# Ambiente isolado

PASSOU: cópia via `git archive`, estado sintético separado em `/tmp/jangada-p1-342gtope`, com HOME, quatro XDG, TMPDIR, TMUX_TMPDIR, banco, sockets, sessões, logs, projetos e worktrees próprios. Configuração desativa acesso remoto e exige isolamento. Guardas recusam operações Git proibidas e comandos administrativos; não substituem Bubblewrap.

`evidencias/configuracao-efetiva.json`, `isolamento-preventivo.json`, `oraculo-inacessivel.stdout.log` demonstram ocultação de `/home/felipinto`, recusa de escrita autoritativa e impossibilidade de ler o gabarito por caminho direto, symlink ou `/proc/self/root`. Nenhum socket de consulta ao oráculo foi exposto. Testes P0 verificam descritores adicionais e padrão, links e interfaces. A semente e referências ficam em `privado/`, fora da montagem dos processos de ensaio.

Modelos não foram iniciados. Credenciais não foram copiadas nem configurações globais alteradas. Pacotes R foram apenas consultados por metadados, sem instalação. R base executou o oráculo; Shiny instalado não comprova aplicação funcional. Bloqueios: socket INET EPERM, bind UNIX EPERM e perfil sem rede Bubblewrap com NETLINK_ROUTE EPERM. Evidências nos logs correspondentes.

Reprodução deve usar uma nova raiz sintética e atualizar `origem-ensaio.json`/ambiente; nunca apontar esses scripts ao estado ativo. Os relatórios conservam comandos e caminhos do ensaio efetivamente executado. `integridade-final.json` comprova bytes da cópia e estados Git finais.''',
'ORACULO_INDEPENDENTE.md':'''# Oráculo independente

PASSOU: `scripts/oraculo.py` e `scripts/oraculo.R` implementam separadamente importação, classificação por versão, deduplicação idêntica, interpolação interna e indicadores. Duas sementes protegidas em `privado/rodada-N/geracao.json`; referências Python e R em pastas distintas. Comparações completas em `evidencias/oraculos-comparacao-N.json`.

Cada rodada contém 150 municípios fictícios, 80 códigos de atividade simulados e sete anos, totalizando 84.000 células válidas. Os códigos não são CNAE oficial nem municípios reais. Rodada 1: 100 ausências, oito duplicatas, seis inválidos; rodada 2: 240 ausências, 15 duplicatas, seis inválidos. Não representam evidência empírica sobre o Brasil.

Critérios: referência nacional anual para QL; HHI, 1-HHI, Shannon e diversidade efetiva; crescimento municipal desde 2019; shift-share clássico NS=e0*G, IM=e0*(gj-G), RS=e1-e0*(1+gj). Soma dos três efeitos deve igualar a variação. Imputação é retrospectiva, usa âncoras observadas e não serve para previsão. Conflitos de chave devem bloquear, duplicatas idênticas são colapsadas e ausências não viram zero.

Python/R concordam em 181.050 linhas de quatro tabelas por rodada, tolerância absoluta 1e-8 mais relativa 1e-9. Agregações, participações, residual shift-share e irregularidades foram conferidos antes de qualquer modelo. Não houve modelo posterior.

Comandos efetivos: `python3 scripts/oraculo.py`; `Rscript --vanilla scripts/oraculo.R DIRETORIO_DADOS DIRETORIO_PRIVADO_R`; `python3 -B scripts/executar.py`. Consultar logs de comandos para argumentos completos. Não reexecutar no estado existente sem preparar outro ensaio.''',
'EXECUCAO_MODELOS.md':'''# Execução dos modelos

BLOQUEADO: fluxo real, revisão por segunda família, terceira revisão adversarial, confrontação cega dos pareceres, correção e nova revisão. Nenhum modelo executor ou revisor foi chamado. Executáveis encontrados não foram tratados como prova de disponibilidade. Não foram copiadas credenciais ou sondadas APIs autenticadas. Acesso remoto não foi previamente autorizado para este ensaio e a infraestrutura local de sockets é restrita.

CONFIRMADO no backend: cadastro de projeto sintético, criação de atividade com oito critérios explícitos e importação da tarefa ECON-P1. `evidencias/backend-cadastro.json` registra atividade, especificação, status QUEUED, zero tentativas, zero execuções e ausência de artefato. Não se atribuiu identidade inventada a uma execução.

Protocolos de execução, supervisão, reservas e retomada passaram nas suítes locais com fixtures. Provedores falsos nesses testes são explicitamente simulações. Eles não validam execução multimodelo real. R econômico e controles foram escritos pelo auditor, não pelo executor. Gráficos, aplicação Shiny e documentação produzidos por IA não foram realizados.

O ciclo de 15 etapas não foi completado: cadastro observado; execução, revisão, correção, aprovação e histórico de atividade econômica real estão bloqueados. Encerramento e recuperação foram testados separadamente com sessões sintéticas.''',
'REVISAO_ADVERSARIAL.md':'''# Revisão adversarial

Foram executadas 16 entregas R deliberadamente defeituosas, oito classes em cada rodada. Autoria: auditor, sem IA. Evidência individual com valor correto, observado, consequência e correção proposta: `evidencias/defeitos-metodologicos.json`; código: `scripts/entrega_sintetica.R` e `metodologia_adversarial.py`.

| Classe | Mecanismo observado |
| --- | --- |
| A1 | Junção sem versão duplica valores, detectada contra painel privado. |
| A2 | Correspondência setorial adulterada altera agregações. |
| A3 | Contraexemplo de composição refuta inferência sobre grupos a partir do agregado. |
| A4 | Denominador regional diverge do QL nacional exigido. |
| A5 | Ausência tratada como zero diverge da política predefinida. |
| A6 | Sinal de IM no residual viola identidade shift-share. |
| A7 | Uso de dados futuros altera QL histórico. |
| A8 | Conclusão causal sem identificação viola critério metodológico. |

Os 96 testes públicos estruturais passaram nas entregas defeituosas. Seis classes numéricas por rodada foram detectadas pelo gabarito, A3 pelo contraexemplo e A8 por critério de admissibilidade metodológica. A8 não constitui prova matemática de causalidade nem detector automático de linguagem. A1 pode conter efeitos adicionais da junção defeituosa; não atribuir isolamento perfeito de um único erro.

Revisor real, justificativa de IA, falsos positivos de IA e resultado após correção por modelo: NÃO EXECUTADOS. O controle correto do auditor concordou com referências nas duas rodadas; isso não equivale a rodada de correção do executor.''',
'RESULTADOS_ECONOMICOS.md':'''# Resultados econômicos

CONFIRMADO: cálculo reprodutível das quatro tabelas de referência nas duas implementações e sementes. Dados públicos e entregas sintéticas preservados em `artefatos/`; referências em `privado/`. Não há análise de municípios brasileiros reais ou resultados empíricos.

A mudança apenas de 2025 no setor S001 alterou 36.000 QLs históricos na solução A7 em cada rodada, enquanto o controle correto alterou zero. Evidências `metamorfismo-1.json` e `metamorfismo-2.json`. Demonstra vazamento temporal das entregas artificiais.

Todos os defeitos artificiais conservam plausibilidade estrutural suficiente para passar nos testes públicos. A concordância formal ou a ausência de erro R não estabelece validade metodológica. `referencias-formais.json` mostra aceitação de oito referências textuais ao LEIA-ME, sem comprovar suas conclusões. O verificador nativo de referências não substitui o oráculo ou julgamento metodológico autorizado.

Segunda rodada determinística: PASSOU sob os mesmos critérios. Segunda rodada cega com modelos reais: BLOQUEADO. Generalização da solução de IA não foi avaliada. Aplicação Shiny, visualizações e entrega final aprovada por modelos: BLOQUEADO.''',
'SEGURANCA_APROVACAO.md':'''# Segurança da aprovação

PASSOU: 32 cenários em `testes/confianca-p0.py`, com isolamento Bubblewrap real nos ataques de montagem. Incluem escrita SQLite, links, FD herdado, interfaces com variável removida, COMPLETED forjado, revisão JSON inventada, artefato alterado, aprovação de outra tarefa, autoria ausente e rótulo sem revisão executada. Conferem estado persistente ou decisão protegida, não somente mensagem de erro. Logs completos e `ataques-bubblewrap.jsonl` preservados.

Três ensaios complementares passaram: novo commit não reutiliza aprovação anterior na prévia backend; autoria operacional adulterada não supera autoria protegida; aprovação sem parecer protegido bloqueia arquivamento e preserva originais. Provedores são simulados nesses ensaios, sem alegação de independência real de IA.

A marca de aprovação anterior pode permanecer após uma nova versão ser reprovada. O teste observou candidato diferente e `marca_atual=false` na prévia. Ela não constitui aprovação da versão nova. Evidência `aprovacao-commit-posterior.json`. Registro de exploratórios preservado: uma expectativa incorreta de exclusão física e depois fixture incompleta produziram falhas do experimento, corrigidas sem mudar produção. Não se ocultaram esses logs nem se classificou existência de arquivo como aprovação válida.

Autoridade: controlador host verifica decisão protegida vinculada à tarefa e digest; pareceres protegidos vinculam candidato Git, árvore, base e autoria. Campos fornecidos pelo executor não bastam. Modelo de ameaça não protege contra usuário com domínio irrestrito da conta/host.

Integração automática permanece bloqueada, comprovada pelo teste L. Nenhuma falsificação aceita nos cenários executados. Isso não certifica todos os ataques possíveis nem substitui o ciclo real de aprovação econômica.''',
'RASTREABILIDADE.md':'''# Rastreabilidade

PASSOU em sessão sintética: reconstrução utilizando apenas `evidencias/arquivo-sintetico.json`, sem consultar arquivos transitórios. `reconstrucao-somente-historico.json` recupera oito documentos completos, verifica base64 e SHA-256 e relaciona candidato do parecer à marca histórica. Inclui parecer integral, contexto, metadados, prompts e marca arquivada.

As suítes P0 conferem reprovações, rodadas intermediárias, snapshot de prompt inicial, falhas fsync/publicação, contexto ausente, links perigosos e repetição idempotente do arquivo. Falhas de arquivamento preservaram os documentos originais nos cenários executados. Evidências protegidas resistiram à escrita no isolamento real.

Limite: esta recuperação pertence a fixture com provedor simulado. Não demonstra histórico integral de atividade econômica executada por IA real. Executor/revisor real, correções, divergências reais e decisão autorizada do experimento econômico não existem para recuperar. Não foram preenchidos retrospectivamente ou inventados.

Quem produziu as entregas adversariais: auditor. Qual versão: arquivos e hashes preservados no manifesto. Quem revisou: nenhum modelo real. Aprovação da atividade ECON-P1: nenhuma. Eventos de encerramento reais dessa atividade: não executados. Concluir o ciclo e reconstruir sua história é requisito pendente.''',
'TESTES_INTERFACE.md':'''# Interface e comunicação

A suíte `testes/tarefas.py` executou 67 casos: 63 passaram e quatro falharam nas condições de comunicação local. Os quatro são classificados BLOQUEADO para a auditoria operacional, com resultado bruto FALHOU preservado em `interface-67.stderr.log`. AF_UNIX bind e AF_INET socket produzem EPERM nas sondagens independentes. Não se removeram proteções para contornar o ambiente.

Suítes backend passaram: orquestração 30, executor 42, supervisão 26, operacional 36, determinístico 26, acompanhamento 12 e painel-orquestração três. Cadastro/atividade real no backend sintético também observado. Isso não comprova atualização completa da Central, comunicação local ou recuperação gráfica integrada.

`testes/fim.sh` e `testes/restaurar.sh` passaram. Sessões, tmux e provedores são fixtures nesses testes. Qt offscreen não substitui experiência gráfica real. A versão avaliada mantém os bloqueios ambientais anteriores; nenhuma regressão crítica foi confirmada por esta amostra.''',
'METRICAS.md':'''# Métricas

| Métrica | Resultado e escopo |
| --- | --- |
| Modelos reais / revisões reais | 0 / 0; fluxo BLOQUEADO |
| Testes Python de regressão e P0 | 274 executados, 270 passaram, quatro bloqueados por sockets |
| Ensaios complementares finais | 3/3 passaram |
| Entregas deliberadamente defeituosas | 16, duas sementes |
| Testes públicos nessas entregas | 96/96 passaram; não prova correção |
| Classes numéricas detectadas pelo auditor | 12 ocorrências em seis classes |
| Casos metodológicos adjudicados | 4, composição e causalidade |
| Erros identificados por revisor real | Não mensurável: nenhum revisor executado |
| Falsos positivos de revisor real | Não mensurável |
| Comparações Python/R | 181.050 linhas por rodada, duas rodadas PASSOU |
| Controles corretos do auditor | Dois, conferidos contra referência |
| Documentos históricos recuperados | 8/8, conteúdo completo e SHA-256 |
| Falsificações aceitas | 0 nos cenários executados; alcance limitado às fixtures |
| Rodadas de correção por IA | 0; não executadas |
| Intervenções humanas no fluxo IA | Não mensurável: fluxo não iniciado |

Tempo dos subprocessos: `comandos-consolidados.json` registra segundos por execução; somar subprocessos não representa duração total humana, revisão ou geração completa. Tempo de execução/revisão de modelos reais é indisponível. Falhas exploratórias dos testes complementares constam separadamente e não se contam como regressões do produto.

Sem estimativa estatística de confiabilidade geral. Testes privados de uma entrega final de IA não têm taxa calculável porque essa entrega não existe. Infraestrutura, experimento e erros do modelo permanecem separados.''',
'RELATORIO_FINAL.md':'''# Relatório final P1

**P1 INCONCLUSIVA.** Todos os ensaios seguros deste plano executáveis no ambiente foram concluídos; a missão não demonstrou o fluxo com modelos reais nem a comunicação integrada. Não há evidência suficiente para aprovar 30 dias de utilização experimental ou congelamento.

## A. Integridade da plataforma

32 testes P0 passaram, incluindo Bubblewrap real, e três testes complementares passaram. Não houve falsificação aceita na amostra. Oito documentos foram reconstruídos integralmente apenas do arquivo histórico, com hashes verificados. Integração automática continua bloqueada. As três worktrees e os bytes do código exportado permanecem preservados, conforme `integridade-final.json`.

A marca de uma aprovação antiga permanece possível, mas o backend distingue sua versão da nova reprovada (`marca_atual=false`). Isso não foi classificado como ataque aceito. Não foram inventadas identidades ou decisões reais a partir de mocks.

## B. Funcionamento operacional

Cadastro e atividade sintéticos confirmados; tarefa ECON-P1 permanece QUEUED sem execução. Suítes de protocolos, supervisão, reservas, retomada e encerramento passaram. 63/67 testes Qt passaram; quatro ficaram bloqueados por sockets, com falhas brutas conservadas. Não houve execução de modelos, revisão independente real, reprovação/correção real, Shiny ou fluxo completo da Central. Acesso externo não previamente autorizado e restrições de sockets impediram os requisitos essenciais.

## C. Qualidade analítica

Oráculo independente Python/R concordou nas duas sementes. Foram executadas 16 entregas R artificiais com oito classes de defeitos, todas aprovadas pelos testes estruturais públicos e confrontadas com controles privados. Detecções pertencem ao auditor, não aos modelos. Segunda rodada determinística passou; segunda rodada cega de IA não foi executada. Referências textuais e código executável não comprovam validade metodológica ou corroboram resultados empíricos.

## O que permanece pendente

Modelos reais de famílias distintas com acesso previamente autorizado; tarefa econômica completa com gráficos e Shiny; pareceres cegos, divergências, correções e nova revisão; testes privados da entrega final; aprovação protegida e recuperação do histórico integral dessa atividade; comunicação e interface em ambiente compatível. A solução avaliada não pode ser declarada capaz de distinguir erros semânticos de revisores apenas pelos resultados deste ensaio.

## Próxima etapa

Repetir o ciclo real em ambiente com isolamento preservado e sockets permitidos, credenciais de teste autorizadas e duas famílias de modelos. Conservar critérios e gabarito privados, executar a segunda rodada cega e recuperar as evidências após encerramento. Não modificar produção para favorecer aprovação. Não iniciar o período de 30 dias como versão validada antes dessa verificação.

Os onze relatórios, scripts, dados artificiais e logs estão fora da versão avaliada. Nenhum commit de produção, push, merge ou tag foi produzido nesta missão.''' }
for nome,texto in docs.items():(DOC/nome).write_text(texto+common)
# Manifesto inclui resultados, scripts, dados e referências privadas; não é montado para agentes.
linhas=[]
for f in sorted(OUT.rglob('*')):
 if f.is_file() and not f.is_symlink() and f.name!='SHA256SUMS':linhas.append(hashlib.sha256(f.read_bytes()).hexdigest()+'  '+str(f.relative_to(OUT)))
(OUT/'SHA256SUMS').write_text('\n'.join(linhas)+'\n')
print(json.dumps({'relatorios':len(list(DOC.glob('*.md'))),'codigo_comparado':checados,'arquivos_manifesto':len(linhas),'resultado':'P1 INCONCLUSIVA'},ensure_ascii=False))
