# Central de Tarefas: o que funciona

Inventário das abas e dos botões da Central, atualizado em 23/10/2026,
com referências aos arquivos e funções. A Central tem dois modos. Com `--real`
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
| Sessões | `menus/tarefas/janela.py, Janela.__init__` | Real; simulado sem `--real` | Lista das sessões de `jangada-agentes --lista-json`, agrupada por estado. Sessões terminadas em `--coordenador` ficam fora (`menus/tarefas/dados.py:137`, `menus/tarefas/janela.py, atualizar`) |
| Sessões > Acompanhamento | `menus/tarefas/janela.py, Janela.__init__` | Leitura | Última mensagem e mudanças vistas nesta janela |
| Sessões > Saída do agente | `menus/tarefas/janela.py, Janela.__init__` | Leitura | Prévia de `jangada-agentes --previa`; na simulação, a mensagem fictícia |
| Sessões > Detalhes | `menus/tarefas/janela.py, Janela.__init__` | Leitura | Estado, autor, revisor, tarefa, ramo e pasta. Sessão encerrada: dados de `jangada-indicadores --json` |
| Sessões > Rodadas | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/rodadas.py:165` | Leitura; simulação não consulta | Contagem de rodadas, último resultado, lista de rodadas de `jangada-agentes --rodadas-json` (rodada, origem, resultado, revisor, modelo, data, tempo e apontamentos) e último parecer, como dado. Com Core sem a consulta, avisa que a lista ainda não está disponível |
| Sessões > Entrega | `menus/tarefas/janela.py, Janela.__init__` | Leitura | Prévia de `--integracao-json` antes da confirmação |
| Projetos e fila | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/operacional.py, Operacional.__init__` | Real; simulação não consulta | Projetos, atividades e tarefas da fila persistente |
| Indicadores | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/indicadores.py:263` | Leitura; simulação não consulta | Custo por tarefa, procedência dos revisores e local contra agy |
| Coluna de coordenadores | `menus/tarefas/coordenadores.py`, `ler_coordenadores`, `estado_coordenador` e `mostrar_lista` | Leitura; simulação não consulta | Consulta versão 1 de `jangada-agentes --coordenadores-json`. Distingue trabalhando, esperando você, resposta pronta, aguardando retomada e atuação encerrada. Preserva as tarefas recebidas, inclusive após interrupção ou hook concluído. A ausência dos campos de ciclo é indicada só no registro afetado; ações anteriores continuam úteis |
| Painel do coordenador | `menus/tarefas/coordenadores.py`, `mostrar_painel` | Leitura | Última linha como texto puro, sem caracteres de controle, hora da atualização e aviso pelo estado. Ciclo da atuação e sessão runtime são independentes |
| Faixa "Só você faz" | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/coordenadores.py:27` | Leitura | Mostra "sem dado": o Core não informa os commits não enviados |
| Indicadores > Custo por tarefa | `menus/tarefas/indicadores.py:359` | Leitura | Enter ou clique duplo leva à sessão na aba Sessões |

## Botões e atalhos

| Botão ou atalho | Onde | Situação | Efeito |
|---|---|---|---|
| Atualizar | `menus/tarefas/janela.py, Janela.__init__` | Real | Refaz a consulta das sessões |
| Avançar simulação | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/janela.py, avancar` | Simulado | Passa ao próximo dos quatro cenários fictícios |
| Nova tarefa | `menus/tarefas/janela.py, Janela.__init__` | Real; simulado sem `--real` (`janela.py, NovaTarefa.criar`) | Abre o formulário de nova tarefa |
| Nova tarefa > Escolher pasta | `menus/tarefas/janela.py, NovaTarefa.__init__` | Real | Escolhe a pasta do projeto |
| Nova tarefa > Nova pasta | `menus/tarefas/janela.py, NovaTarefa.__init__` | Real; desligado na simulação | Cria a pasta de um projeto novo |
| Nova tarefa > Opções avançadas | `menus/tarefas/janela.py, NovaTarefa.__init__` | Real | Mostra executor, revisor, segurança e delegação |
| Nova tarefa > Iniciar tarefa | `menus/tarefas/janela.py, NovaTarefa.__init__` | Real; "Criar tarefa simulada" na simulação | Abre a sessão pelo Core |
| Painel de indicadores | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/janela.py, abrir_indicadores` | Leitura | Vai à aba Indicadores |
| Abrir terminal / Retomar no terminal | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/janela.py, focar` | Real; simulado | `jangada-agentes --focar` |
| Integrar pelo terminal | `menus/tarefas/janela.py, Janela.__init__`, `menus/tarefas/janela.py, finalizar` | Real; simulado | `jangada-agente-fim --integrar` no terminal |
| Conferir e integrar (Alt+I) | `menus/tarefas/janela.py`, `confirmar_entrega` e `integrar_interface` | Real; simulado | Mostra a entrega, pede confirmação e integra. A sessão permanece aberta, conforme a dica e o diálogo |
| Encerrar sem integrar (Ctrl+Shift+E) | `menus/tarefas/janela.py`, `confirmar_encerramento` e `finalizar` | Real; simulado | Pede confirmação com Não como padrão; chama `jangada-agente-fim` sem integrar. Na simulação, só informa a ação |
| Alt+2 a Alt+5 | `menus/tarefas/janela.py, Janela.__init__` | Leitura | Vai à aba de detalhe de mesmo número, com foco na barra de abas. Acompanhamento ficou sem atalho: Alt+1 é da coluna de coordenadores |
| Alt+1 | `menus/tarefas/coordenadores.py`, `focar_lista` | Leitura | Foco na lista de coordenadores |
| Alt+M | `menus/tarefas/coordenadores.py`, `focar_caixa` | Leitura | Foco na caixa de texto do coordenador |
| Ir para a janela (Alt+J) | `menus/tarefas/coordenadores.py`, `ir_para_janela` | Real; simulado | `jangada-agentes --focar` com a sessão do coordenador; disponível com sessão viva |
| Copiar e ir para a janela (Ctrl+Enter na caixa) | `menus/tarefas/coordenadores.py`, `copiar_e_ir` | Real; simulado | Copia e foca a janela; nada é colado nem enviado. Caixa de até 8 KiB, editável em qualquer estado; copiar exige sessão viva |
| Novo coordenador (Ctrl+N) | `menus/tarefas/coordenadores.py`, `NovoCoordenador` e `abrir_coordenador` | Real; desligado na simulação | Escolhe projeto cadastrado e provedor: claude, codex ou agy (Argon High). Reconfere os dados por nova consulta e roda `jangada-coordenador --projeto PASTA --provedor P --janela`. Lança a janela por `startDetached`, com canais independentes; Core cria ou retoma. Sessão viva recebe somente foco. Atuação aberta sem processo mostra Retomar atuação e permite escolher o provedor |
| Faixa de cotas | `menus/tarefas/cotas.py`, `FaixaCotas` e `ConsultaCotas`; `menus/tarefas/janela.py`, `mostrar_cotas` | Real; leitura; na simulação mostra "Cotas: sem dado" e não consulta o Core | Linha fixa acima dos cartões, em todas as abas. Roda `jangada-router cotas` (sem `--atualizar`, sem `--permitir-remoto`) ao abrir e a cada 60 segundos, uma consulta por vez. Mostra o percentual de cada grupo por conta do agy, do Codex e "Claude: não medido aqui", o `renova_em` do menor percentual de cada provedor e "lido às HH:MM". Abaixo de 20% mostra texto, glifo Ⅱ e a cor de alerta das fichas. Grupo nulo mostra "sem dado" com o motivo (sem cache, cache vencido, consulta falhou, conta sem confiança). Core sem o comando, erro, prazo, saída grande ou JSON inválido mostram "Cotas: sem dado" e o motivo, sem diálogo. O comando de atualização aparece só como texto para o terminal. Em janela pequena usa até duas linhas, com formas resumidas e o texto inteiro na dica |
| Novo coordenador > cota do Argon | `menus/tarefas/coordenadores.py`, `CotaArgon` sobre a consulta de `cotas.py` (`ler_cota_argon`) | Real; leitura | Ao abrir o diálogo, usa a consulta única `jangada-router cotas` (sem `--atualizar`, sem `--permitir-remoto`, prazo de 30 segundos, saída de até 1 MiB) e lê o grupo `gemini-argon-wtu` da conta `principal` (sem ela, da única conta do agy; sem o grupo, sem dado). Todo número do `cotas.json` passa por `numero_de_fora`, que aceita só int ou float de 0 a 100. De 20% em diante, a opção agy mostra o percentual. Abaixo de 20%, fica desligada com "Cota do Argon abaixo de 20%" e `renova_em`. Sem dado (grupo ausente, `percentual` nulo, comando ausente, erro, prazo ou JSON inválido), a opção continua disponível com "Cota do Argon sem dado: o Core confere antes de abrir" e o comando de atualização como texto para o terminal |
| Novo coordenador > abertura sem sessão | `menus/tarefas/coordenadores.py`, `abrir_janela` e `conferir_abertura` | Real | Depois de "Abertura ou retomada solicitada", reconsulta a lista a cada segundo. Sem coordenador vivo do projeto e provedor em 20 segundos, troca o aviso por "O Core não abriu o coordenador", com a causa provável do provedor e o comando para rodar no terminal. O prazo é só do relógio e vence aos 20 segundos mesmo com consulta em curso; sem lista válida lida depois do pedido, o aviso diz que não foi possível conferir. Consulta que termina depois do vencimento não muda o aviso. Não captura a saída da janela |
| Retomar | `menus/tarefas/coordenadores.py`, `retomar_atuacao` | Real; desligado na simulação e no registro sem campos de ciclo | Exige atuação aberta, sem sessão e com disponibilidade `retomavel=True`. Reconfere identidade, ciclo, disponibilidade e sessão; lança a janela separada da Central, com projeto e provedor registrados |
| Finalizar atuação | `menus/tarefas/coordenadores.py`, `finalizar_atuacao` e `reconferencia_fim` | Real; desligado na simulação e no registro sem campos de ciclo | Sem sessão viva, pede confirmação de estado/diário salvo e saída voluntária. Reconfere os dados e executa `jangada-coordenador --finalizar SESSAO`; acompanha o resultado em QProcess, com prazo de 30 segundos. Preserva pendências e informa o resultado do Core. Com sessão viva, orienta salvar/sair e usar Ir para a janela |
| Atualizar rodadas | `menus/tarefas/rodadas.py:178` | Leitura; desligado na simulação | Refaz as três consultas da aba Rodadas |
| Indicadores > Atualizar | `menus/tarefas/indicadores.py:228` | Leitura | Refaz `jangada-indicadores --json` |
| Indicadores > cartões | `menus/tarefas/indicadores.py:224` | Leitura | Troca a tabela de detalhe |
| Projetos e fila > Cadastrar projeto | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, cadastrar` | Real; desligado na simulação | `jangada-projeto` cadastrar |
| Projetos e fila > Nova atividade | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, atividade` | Real; desligado na simulação | Cria atividade no projeto |
| Projetos e fila > Importar plano | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, importar` | Real; desligado na simulação | `jangada-fila --importar` |
| Projetos e fila > Atualizar | `menus/tarefas/operacional.py, Operacional.__init__` | Leitura | Refaz a consulta da fila |
| Projetos e fila > Pausar, Retomar, Cancelar, Repetir | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, agir` | Real; desligado na simulação | `jangada-task` com a ação; Cancelar pede confirmação |
| Projetos e fila > Instruções de revisão | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, revisao` | Leitura | Mostra como revisar no terminal; não aprova |
| Projetos e fila > Acompanhar sessão | `menus/tarefas/operacional.py, Operacional.__init__`, `menus/tarefas/operacional.py, acompanhar` | Leitura | Seleciona a sessão ligada à tarefa |
| Projetos e fila > Ctrl+F | `menus/tarefas/operacional.py, Operacional.__init__` | Leitura | Busca nos detalhes |
| Filtro por estado no resumo | `menus/tarefas/janela.py`, `filtrar_estado` | Leitura | Quatro cartões com contagens globais. Clicar novamente desfaz o filtro |
| Busca e filtro de projeto em Sessões | v2 `README.md:20` | Não existe | |
| Limpar filtros | `menus/tarefas/janela.py`, `limpar_busca` | Leitura | Recupera todos os grupos |
| Ação indisponível com motivo | `menus/tarefas/janela.py` e `operacional.py`, `selecionar` | Leitura | Motivo junto aos botões e na descrição acessível. As recusas permanecem as mesmas |
| Prévia do destino da conversa em Detalhes | v2 `README.md:29` | Não existe | |
| Etapas recolhidas na Entrega | v2 `README.md:31` | Não existe | |
| Voltar às sessões | `menus/tarefas/janela.py`, `exibir_detalhe` | Leitura | Abaixo de 940 pixels, volta à lista com foco e seleção preservados |
| Prévia do terminal e do encerramento | v2 `README.md:83` | Não existe | Encerrar pede confirmação; a prévia do comando não existe |
| Rodar `jangada-validar` | | Não entra | A validação é do autor, dentro do isolamento |

Na coluna de coordenadores, o provedor `agy` aparece como "agy (Argon High)".
Um provedor que a Central não conhece aparece como "provedor não reconhecido
por esta Central" e desliga Retomar e Finalizar atuação, com o motivo no painel
(`menus/tarefas/coordenadores.py`, `provedor_desconhecido` e `mostrar_painel`).
A Central não mostra o modelo registrado, que o Core não exporta.

Na coluna de coordenadores, uma tarefa com `viva=False` aparece como
**Sem sessão ativa** (`menus/tarefas/coordenadores.py`, `estado_tarefa`).
Isso não indica conclusão. O vínculo é preservado; quando a lista de sessões
traz um estado, ele aparece como **Último estado**, inclusive pendências.
Sem informação da sessão, a Central não acrescenta um estado de tarefa.
Finalizar a atuação preserva as tarefas pendentes.

A orientação para sair de uma sessão viva vale para a atuação selecionada
(`menus/tarefas/coordenadores.py`, `orientar_saida` e `mostrar_painel`).
Ela some ao trocar de registro ou quando uma consulta válida mostra ausência
do processo, troca da atuação ou encerramento do ciclo. Falhas de consulta
preservam a orientação. Outros resultados de ações continuam disponíveis.
O aviso de ciclo ausente fica apenas no painel do registro sem esses campos;
ele não pede atualização do Core para os demais registros.

## Uso em janela reduzida

A janela tem mínimo de 700×460.
Abaixo de 1360 pixels de largura, os coordenadores ficam numa aba;
Alt+1 e Alt+M levam até ela. Projeto e atualização saem das colunas de
Sessões e continuam no detalhe. A coluna Estado reserva espaço para o texto.
Abaixo de 940 pixels, Ver acompanhamento da seleção alterna lista e detalhe.
Voltar às sessões recupera o foco na mesma seleção. Na janela baixa, o
detalhe inteiro permite rolagem; o foco traz a ação para a área visível.
O painel de sessão e a aba Rodadas permitem rolagem sem comprimir o conteúdo.
Encerrar fica separado das ações de integração e Ctrl+X permanece disponível
para recortar texto nos campos editáveis.

A lista de coordenadores reserva pelo menos 190 pixels de altura.
O painel tem rolagem e identifica a mensagem com um rótulo. Sem seleção,
mostra apenas a orientação para escolher um coordenador, sem a caixa vazia.

Em Projetos e fila, erros da consulta aparecem numa linha com a contagem.
Detalhes dos erros abre o diálogo com o texto completo sob demanda.
As ações continuam bloqueadas enquanto houver erros.

## Correspondência com a prévia v2

A Central continua em Qt, usando as fichas pessoais validadas e a reserva
do mesmo modo quando necessário. Nenhuma consulta ou autorização nova do
Core foi acrescentada. As contagens vêm das sessões consultadas.

| Elemento da prévia | Central após T3b | Fonte da implementação |
|---|---|---|
| Logo, título e comandos | Logo oficial; Nova tarefa cheia; comandos preservados, em duas linhas na janela estreita | `menus/tarefas/janela.py`, `Janela.__init__` e `resizeEvent` |
| Quatro cartões de resumo | Contagem global por estado; clique filtra e segundo clique desfaz; foco pelo teclado | `menus/tarefas/aparencia.py`, `CartaoResumo`; `janela.py`, `filtrar_estado` |
| Contagem por grupo | Total visível no título, sem perder o recolhimento quando o total muda | `menus/tarefas/janela.py`, `mostrar` e `filtrar_sessoes` |
| Busca e filtro de projeto | Permanecem ausentes em Sessões; a busca dos detalhes da fila foi preservada | `menus/tarefas/operacional.py`, `buscar` |
| Limpar filtros | Recupera a lista; vazio filtrado oferece o mesmo comando | `menus/tarefas/janela.py`, `limpar_busca` |
| Abas principais e de detalhe | Sublinhado de 2 px na primária; Qt conserva navegação e foco. Rodadas e Indicadores continuam disponíveis | `menus/tarefas/janela.py`, `aplicar_tema` e `ir_para_aba` |
| Lista e tabela compacta | Quatro colunas; cabeçalho elevado sem bordas; linhas com 4 px de preenchimento; rolagem de 8 px | `menus/tarefas/janela.py`, `aplicar_tema` |
| Seleção, situação e próxima ação | Mantidas; navegação da fila, dos indicadores e do coordenador limpa o filtro que esconderia o destino | `menus/tarefas/janela.py`, `selecionar` e `selecionar_nome` |
| Acompanhamento e linha do tempo | Última mensagem e eventos observados nesta janela, com hora e linha vertical. Até 50 eventos, sem inventar histórico anterior | `menus/tarefas/aparencia.py`, `LinhaTempo`; `janela.py`, `acompanhar_mudancas` |
| Saída do agente | Prévia existente preservada, com seleção de texto e posição da leitura | `menus/tarefas/janela.py`, `exibir_atividade` e `previa_fim` |
| Detalhes e destino da conversa | Atributos existentes preservados; prévia de destino e critérios adicionais do HTML permanecem ausentes | `menus/tarefas/janela.py`, `selecionar` |
| Entrega | Prévia, revisão, verificações e SHA continuam no texto conferido antes da confirmação; etapas recolhidas permanecem ausentes | `menus/tarefas/janela.py`, `confirmar_entrega` e `integracao_fim` |
| Ação principal cheia | Nova tarefa; Abrir/Retomar terminal ou Conferir e integrar conforme a seleção. Destaque não certifica aprovação | `menus/tarefas/janela.py`, `selecionar` e `aplicar_tema` |
| Motivo de indisponibilidade | Texto junto a cada ação de sessão e da fila, também na descrição acessível. Reflete seleção, erro, concorrência, finalização ou estado já conferidos | `menus/tarefas/janela.py` e `operacional.py`, `selecionar` |
| Terminal e integração | Mesmos comandos, prévia exata, confirmação separada, travas e recusas. Revisão continua conferida pelo Core na ação, sem nova consulta antecipada | `menus/tarefas/janela.py`, `focar`, `integrar_interface` e `finalizar` |
| Encerramento separado | Tom de Falhou misturado à superfície, borda translúcida e orientação entre integração e encerramento; Ctrl+Shift+E preservado | `menus/tarefas/aparencia.py`, `cores_interacao`; `janela.py`, `confirmar_encerramento` |
| Cartão de vazio | Logo oficial, borda tracejada, título, orientação e Nova tarefa ou Limpar filtros | `menus/tarefas/janela.py`, `Janela.__init__` e `filtrar_sessoes` |
| Projetos e fila | Hierarquia, formulários, relações, revisão e estados permitidos preservados; comandos em grade com motivos visíveis e rolagem | `menus/tarefas/operacional.py`, `Operacional` |
| Navegação estreita | Lista e detalhe alternados em 700×460; retorno mantém seleção e foco. Ações e conteúdo acessíveis por rolagem | `menus/tarefas/janela.py`, `exibir_detalhe`; `aparencia.py`, `InspetorRolavel` |
| Cores, fontes e estados | Fichas por modo; misturas de interação conferidas em 4,5:1. Inter e JetBrains Mono locais, corpo de 14 px e rótulos de 13 px | `menus/tarefas/aparencia.py`, `cores_interacao`; `janela.py`, `aplicar_tema` |

A suíte Qt confere 1440×900, 1200×780 e 700×460 nos dois modos de cor,
ações visíveis no desktop, foco na janela baixa, seleção após atualização,
grupos recolhidos e motivos de recusa. O menor contraste medido foi 5,07:1,
incluindo as misturas de interação, acima do mínimo exigido de 4,5:1.

## O que o Core não entrega

A aba Rodadas mostra "sem dado" onde o Core não informa. Faltam:

- pareceres de rodadas antigas (`jangada-agentes --contexto-json` traz só o
  último, e `parecer_origem` de `--rodadas-json` é sempre nulo na versão 1);
- um campo que separe execuções de mesmo nome em `jangada-indicadores --json`.
  Com mais de um registro da sessão, a aba mostra o último da lista e avisa.

A faixa "Só você faz" mostra "sem dado". Falta uma consulta que diga, por
projeto cadastrado, quantos commits locais não foram enviados ao remoto e qual
comando faz o envio.
