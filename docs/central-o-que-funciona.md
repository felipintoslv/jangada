# Central de Tarefas: o que funciona

Inventário das abas e dos botões da Central em 17/10/2026, com o arquivo e a
linha de cada item. A Central tem dois modos. Com `--real`
(`menus/tarefas/central.py:102`) ela consulta o Core e executa as ações. Sem
`--real` ela roda em simulação: mostra tarefas fictícias e não executa nada.

Legenda:

- **Real**: com `--real`, chama um comando do Core ou do Shell.
- **Simulado**: sem `--real`, só escreve na linha de status o que faria.
- **Leitura**: consulta e mostra; não muda estado.
- **Não existe**: aparece na prévia v2
  (`docs/coordenacao-central/mockup-central/v2/README.md`), mas não na Central.

## Abas

| Aba | Onde | Situação | O que mostra ou faz |
|---|---|---|---|
| Sessões | `menus/tarefas/janela.py:403` | Real; simulado sem `--real` | Lista das sessões de `jangada-agentes --lista-json`, agrupada por estado |
| Sessões > Acompanhamento | `menus/tarefas/janela.py:363` | Leitura | Última mensagem e mudanças vistas nesta janela |
| Sessões > Saída do agente | `menus/tarefas/janela.py:364` | Leitura | Prévia de `jangada-agentes --previa`; na simulação, a mensagem fictícia |
| Sessões > Detalhes | `menus/tarefas/janela.py:365` | Leitura | Estado, autor, revisor, tarefa, ramo e pasta. Sessão encerrada: dados de `jangada-indicadores --json` |
| Sessões > Rodadas | `menus/tarefas/janela.py:367`, `menus/tarefas/rodadas.py:113` | Leitura; simulação não consulta | Contagem de rodadas, último resultado e último parecer, como dado |
| Sessões > Entrega | `menus/tarefas/janela.py:372` | Leitura | Prévia de `--integracao-json` antes da confirmação |
| Projetos e fila | `menus/tarefas/janela.py:405`, `menus/tarefas/operacional.py:30` | Real; simulação não consulta | Projetos, atividades e tarefas da fila persistente |
| Indicadores | `menus/tarefas/janela.py:407`, `menus/tarefas/indicadores.py:263` | Leitura; simulação não consulta | Custo por tarefa, procedência dos revisores e local contra agy |
| Indicadores > Custo por tarefa | `menus/tarefas/indicadores.py:359` | Leitura | Enter ou clique duplo leva à sessão na aba Sessões |

## Botões e atalhos

| Botão ou atalho | Onde | Situação | Efeito |
|---|---|---|---|
| Atualizar | `menus/tarefas/janela.py:302` | Real | Refaz a consulta das sessões |
| Avançar simulação | `menus/tarefas/janela.py:302`, `menus/tarefas/janela.py:889` | Simulado | Passa ao próximo dos quatro cenários fictícios |
| Nova tarefa | `menus/tarefas/janela.py:305` | Real; simulado sem `--real` (`janela.py:220`) | Abre o formulário de nova tarefa |
| Nova tarefa > Escolher pasta | `menus/tarefas/janela.py:58` | Real | Escolhe a pasta do projeto |
| Nova tarefa > Nova pasta | `menus/tarefas/janela.py:64` | Real; desligado na simulação | Cria a pasta de um projeto novo |
| Nova tarefa > Opções avançadas | `menus/tarefas/janela.py:83` | Real | Mostra executor, revisor, segurança e delegação |
| Nova tarefa > Iniciar tarefa | `menus/tarefas/janela.py:112` | Real; "Criar tarefa simulada" na simulação | Abre a sessão pelo Core |
| Painel de indicadores | `menus/tarefas/janela.py:308`, `menus/tarefas/janela.py:493` | Leitura | Vai à aba Indicadores |
| Abrir terminal / Retomar no terminal | `menus/tarefas/janela.py:374`, `menus/tarefas/janela.py:1223` | Real; simulado | `jangada-agentes --focar` |
| Integrar pelo terminal | `menus/tarefas/janela.py:389`, `menus/tarefas/janela.py:1142` | Real; simulado | `jangada-agente-fim --integrar` no terminal |
| Conferir e integrar (Alt+I) | `menus/tarefas/janela.py:378`, `menus/tarefas/janela.py:1060` | Real; simulado | Mostra a entrega, pede confirmação e integra |
| Encerrar sem integrar (Ctrl+X) | `menus/tarefas/janela.py:379`, `menus/tarefas/janela.py:1142` | Real; simulado | `jangada-agente-fim` sem integrar |
| Alt+1 a Alt+5 | `menus/tarefas/janela.py:415` | Leitura | Vai à aba de detalhe de mesmo número, com foco na barra de abas |
| Atualizar rodadas | `menus/tarefas/rodadas.py:126` | Leitura; desligado na simulação | Refaz as duas consultas da aba Rodadas |
| Indicadores > Atualizar | `menus/tarefas/indicadores.py:228` | Leitura | Refaz `jangada-indicadores --json` |
| Indicadores > cartões | `menus/tarefas/indicadores.py:224` | Leitura | Troca a tabela de detalhe |
| Projetos e fila > Cadastrar projeto | `menus/tarefas/operacional.py:41`, `menus/tarefas/operacional.py:248` | Real; desligado na simulação | `jangada-projeto` cadastrar |
| Projetos e fila > Nova atividade | `menus/tarefas/operacional.py:41`, `menus/tarefas/operacional.py:255` | Real; desligado na simulação | Cria atividade no projeto |
| Projetos e fila > Importar plano | `menus/tarefas/operacional.py:41`, `menus/tarefas/operacional.py:273` | Real; desligado na simulação | `jangada-fila --importar` |
| Projetos e fila > Atualizar | `menus/tarefas/operacional.py:41` | Leitura | Refaz a consulta da fila |
| Projetos e fila > Pausar, Retomar, Cancelar, Repetir | `menus/tarefas/operacional.py:66`, `menus/tarefas/operacional.py:232` | Real; desligado na simulação | `jangada-task` com a ação; Cancelar pede confirmação |
| Projetos e fila > Instruções de revisão | `menus/tarefas/operacional.py:71`, `menus/tarefas/operacional.py:281` | Leitura | Mostra como revisar no terminal; não aprova |
| Projetos e fila > Acompanhar sessão | `menus/tarefas/operacional.py:74`, `menus/tarefas/operacional.py:294` | Leitura | Seleciona a sessão ligada à tarefa |
| Projetos e fila > Ctrl+F | `menus/tarefas/operacional.py:61` | Leitura | Busca nos detalhes |
| Filtro por estado no resumo | v2 `README.md:20` | Não existe | |
| Busca e filtro de projeto em Sessões | v2 `README.md:20` | Não existe | |
| Limpar filtros | v2 `README.md:20` | Não existe | |
| Bloqueio de Conferir e integrar com motivo | v2 `README.md:37` | Não existe | A Central só desliga o botão, sem dizer o motivo |
| Prévia do destino da conversa em Detalhes | v2 `README.md:29` | Não existe | |
| Etapas recolhidas na Entrega | v2 `README.md:31` | Não existe | |
| Voltar às sessões | v2 `README.md:63` | Não existe | Só faz sentido em tela estreita |
| Prévia do terminal e do encerramento | v2 `README.md:83` | Não existe | Os botões executam direto, depois da confirmação onde ela já existe |
| Rodar `jangada-validar` | | Não entra | A validação é do autor, dentro do isolamento |

## O que o Core não entrega

A aba Rodadas mostra "sem dado" onde o Core não informa. Faltam:

- rodadas anteriores à última, com resultado, revisor e tempo de cada uma;
- pareceres de rodadas antigas (`jangada-agentes --contexto-json` traz só o
  último);
- um campo que separe execuções de mesmo nome em `jangada-indicadores --json`.
  Com mais de um registro da sessão, a aba mostra o último da lista e avisa.

Uma consulta que cobriria isso: `jangada-agentes --rodadas-json SESSAO`,
versão 1, com `versao`, `sessao`, `execucao` e uma lista `rodadas` em que
cada item traz `rodada`, `origem` (`sessao` ou `protegida`), `resultado`,
`revisor`, `modelo`, `inicio`, `fim`, `segundos`, `apontamentos` e
`parecer_origem`.
