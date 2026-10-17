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
  (`docs/historico/coordenacao-central/mockup-central/v2/README.md`), mas não na Central.

## Abas

| Aba | Onde | Situação | O que mostra ou faz |
|---|---|---|---|
| Sessões | `menus/tarefas/janela.py:409` | Real; simulado sem `--real` | Lista das sessões de `jangada-agentes --lista-json`, agrupada por estado. Sessões terminadas em `--coordenador` ficam fora (`menus/tarefas/dados.py:137`, `menus/tarefas/janela.py:971`) |
| Sessões > Acompanhamento | `menus/tarefas/janela.py:369` | Leitura | Última mensagem e mudanças vistas nesta janela |
| Sessões > Saída do agente | `menus/tarefas/janela.py:370` | Leitura | Prévia de `jangada-agentes --previa`; na simulação, a mensagem fictícia |
| Sessões > Detalhes | `menus/tarefas/janela.py:371` | Leitura | Estado, autor, revisor, tarefa, ramo e pasta. Sessão encerrada: dados de `jangada-indicadores --json` |
| Sessões > Rodadas | `menus/tarefas/janela.py:373`, `menus/tarefas/rodadas.py:165` | Leitura; simulação não consulta | Contagem de rodadas, último resultado, lista de rodadas de `jangada-agentes --rodadas-json` (rodada, origem, resultado, revisor, modelo, data, tempo e apontamentos) e último parecer, como dado. Com Core sem a consulta, avisa que a lista ainda não está disponível |
| Sessões > Entrega | `menus/tarefas/janela.py:378` | Leitura | Prévia de `--integracao-json` antes da confirmação |
| Projetos e fila | `menus/tarefas/janela.py:411`, `menus/tarefas/operacional.py:30` | Real; simulação não consulta | Projetos, atividades e tarefas da fila persistente |
| Indicadores | `menus/tarefas/janela.py:413`, `menus/tarefas/indicadores.py:263` | Leitura; simulação não consulta | Custo por tarefa, procedência dos revisores e local contra agy |
| Coluna de coordenadores | `menus/tarefas/janela.py:317`, `menus/tarefas/coordenadores.py:178` | Leitura; simulação não consulta | À esquerda das abas, sempre à vista. Lista de `jangada-agentes --coordenadores-json` (`menus/tarefas/coordenadores.py:292`), com projeto, provedor e estado: trabalhando, esperando você (cor de Bloqueada e glifo Ⅱ), pronto ou parado. As tarefas de cada um ficam embaixo; Enter ou clique leva à sessão na aba Sessões (`menus/tarefas/coordenadores.py:422`). Sem a consulta no Core, ou sem `jangada-coordenador`, avisa que os coordenadores ainda não estão disponíveis (`menus/tarefas/coordenadores.py:309`) |
| Painel do coordenador | `menus/tarefas/coordenadores.py:439` | Leitura | Última linha como texto puro, sem caracteres de controle (`menus/tarefas/coordenadores.py:43`), hora da atualização e aviso pelo estado (`menus/tarefas/coordenadores.py:35`) |
| Faixa "Só você faz" | `menus/tarefas/janela.py:313`, `menus/tarefas/coordenadores.py:27` | Leitura | Mostra "sem dado": o Core não informa os commits não enviados |
| Indicadores > Custo por tarefa | `menus/tarefas/indicadores.py:359` | Leitura | Enter ou clique duplo leva à sessão na aba Sessões |

## Botões e atalhos

| Botão ou atalho | Onde | Situação | Efeito |
|---|---|---|---|
| Atualizar | `menus/tarefas/janela.py:303` | Real | Refaz a consulta das sessões |
| Avançar simulação | `menus/tarefas/janela.py:303`, `menus/tarefas/janela.py:914` | Simulado | Passa ao próximo dos quatro cenários fictícios |
| Nova tarefa | `menus/tarefas/janela.py:306` | Real; simulado sem `--real` (`janela.py:221`) | Abre o formulário de nova tarefa |
| Nova tarefa > Escolher pasta | `menus/tarefas/janela.py:59` | Real | Escolhe a pasta do projeto |
| Nova tarefa > Nova pasta | `menus/tarefas/janela.py:65` | Real; desligado na simulação | Cria a pasta de um projeto novo |
| Nova tarefa > Opções avançadas | `menus/tarefas/janela.py:84` | Real | Mostra executor, revisor, segurança e delegação |
| Nova tarefa > Iniciar tarefa | `menus/tarefas/janela.py:113` | Real; "Criar tarefa simulada" na simulação | Abre a sessão pelo Core |
| Painel de indicadores | `menus/tarefas/janela.py:309`, `menus/tarefas/janela.py:506` | Leitura | Vai à aba Indicadores |
| Abrir terminal / Retomar no terminal | `menus/tarefas/janela.py:380`, `menus/tarefas/janela.py:1249` | Real; simulado | `jangada-agentes --focar` |
| Integrar pelo terminal | `menus/tarefas/janela.py:395`, `menus/tarefas/janela.py:1168` | Real; simulado | `jangada-agente-fim --integrar` no terminal |
| Conferir e integrar (Alt+I) | `menus/tarefas/janela.py:384`, `menus/tarefas/janela.py:1086` | Real; simulado | Mostra a entrega, pede confirmação e integra |
| Encerrar sem integrar (Ctrl+X) | `menus/tarefas/janela.py:385`, `menus/tarefas/janela.py:1168` | Real; simulado | `jangada-agente-fim` sem integrar |
| Alt+2 a Alt+5 | `menus/tarefas/janela.py:427` | Leitura | Vai à aba de detalhe de mesmo número, com foco na barra de abas. Acompanhamento ficou sem atalho: Alt+1 é da coluna de coordenadores |
| Alt+1 | `menus/tarefas/coordenadores.py:261`, `menus/tarefas/coordenadores.py:467` | Leitura | Foco na lista de coordenadores |
| Alt+M | `menus/tarefas/coordenadores.py:261`, `menus/tarefas/coordenadores.py:472` | Leitura | Foco na caixa de texto do coordenador |
| Ir para a janela (Alt+J) | `menus/tarefas/coordenadores.py:244`, `menus/tarefas/coordenadores.py:478` | Real; simulado | `jangada-agentes --focar` com a sessão do coordenador; desligado com o coordenador parado |
| Copiar e ir para a janela (Ctrl+Enter na caixa) | `menus/tarefas/coordenadores.py:239`, `menus/tarefas/coordenadores.py:257`, `menus/tarefas/coordenadores.py:494` | Real; simulado | Põe o texto na área de transferência e foca a janela; nada é colado nem enviado. Caixa de até 8 KiB, ligada em qualquer estado |
| Novo coordenador (Ctrl+N) | `menus/tarefas/coordenadores.py:116`, `menus/tarefas/coordenadores.py:529`, `menus/tarefas/coordenadores.py:547` | Real; desligado na simulação | Escolhe projeto cadastrado e provedor e roda `jangada-coordenador --projeto PASTA --provedor P --janela`. Projeto com coordenador vivo leva a ele |
| Atualizar rodadas | `menus/tarefas/rodadas.py:178` | Leitura; desligado na simulação | Refaz as três consultas da aba Rodadas |
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

- pareceres de rodadas antigas (`jangada-agentes --contexto-json` traz só o
  último, e `parecer_origem` de `--rodadas-json` é sempre nulo na versão 1);
- um campo que separe execuções de mesmo nome em `jangada-indicadores --json`.
  Com mais de um registro da sessão, a aba mostra o último da lista e avisa.

A faixa "Só você faz" mostra "sem dado". Falta uma consulta que diga, por
projeto cadastrado, quantos commits locais não foram enviados ao remoto e qual
comando faz o envio.
