# Central de tarefas · prévia v2

Evolução visual da Central atual para avaliação do dono. Preserva cabeçalho,
resumo operacional, abas principais, lista à esquerda e detalhe à direita.
A referência visual é a captura sintética [`../ponto-de-partida/central-atual-simulada.png`](../ponto-de-partida/central-atual-simulada.png).
A v1 foi preservada pelo coordenador; esta evolução não altera sua cópia.

Abra [index.html](index.html) diretamente no navegador, com `file://`.
CSS, JavaScript e logos estão incorporados. Não exige servidor, instalação,
pacotes, fontes externas ou conexão de rede.

## Alcance e navegação

**Sessões** apresenta oito tarefas demonstrativas em dois projetos, agrupadas
nos quatro estados operacionais da Central: Precisa de sua resposta,
Em execução, Interrompidas e Pronto para conferir. As colunas preservam
Tarefa, Projeto, Estado e Atualização. Cada grupo pode ser recolhido.

O resumo filtra por estado; clicar novamente desfaz essa seleção.
Busca, projeto e estado podem ser combinados. “Limpar filtros” recupera
a lista. Os números do resumo representam o conjunto demonstrativo completo.
A seleção da tarefa atualiza seu acompanhamento e os destinos das ações.

O detalhe preserva quatro abas:

- **Acompanhamento:** última mensagem, ação esperada e linha do tempo sintética.
- **Saída do agente:** excerto fictício delimitado, sem transcrição real.
- **Detalhes:** coordenador, autor, revisor, projeto, conversa, sessão,
  objetivo, ramo, pasta e critérios; acesso à prévia do destino da conversa.
- **Entrega:** revisão independente, verificações e objeto exato em blocos
  próprios; etapas e próximo passo em uma seção recolhida.

As ações Abrir/retomar terminal, Integrar pelo terminal, Conferir e integrar
e Encerrar sem integrar permanecem em posição consistente. A ação principal
muda conforme o cenário. Revisão pendente impede Conferir e integrar e
mostra o motivo ao lado. O acesso pelo terminal também informa a pendência.
A representação do M1 tem ações bloqueadas e motivo explícito.

A integração demonstrativa tem três momentos: prévia do objeto; confirmação
separada com reconhecimento explícito; mensagem de que nenhuma integração
foi realizada. Objeto, base, candidato, arquivos e revisor permanecem
vinculados ao cenário selecionado. Nenhum estado da tarefa muda.
Os identificadores `demo-*` não são hashes Git ou provas de aprovação.

**Projetos e fila** preserva a hierarquia projeto, atividade, tarefa e
sessão vinculada, com seis tarefas demonstrativas. A busca filtra a árvore.
Selecionar um item mostra seus atributos e relações. Pausar, Retomar,
Cancelar e Repetir ficam disponíveis conforme os estados representados em
`operacional.py`; a demonstração só mostra alvo e instrução, sem transição.
Instruções de revisão identifica tarefa e objeto. Acompanhar sessão leva
à seleção correspondente em Sessões, sem abrir terminal.

Nova tarefa, Cadastrar projeto, Nova atividade e Importar plano abrem
formulários demonstrativos. O pedido pode ser conferido, mas não cria ou
importa registros. Texto digitado é escapado antes da apresentação.
Nova tarefa oferece os perfis existentes `codex-claude` e `claude-codex`.
Conversa de Pescador e Painel de indicadores mostram somente prévias dos
aplicativos existentes, com destino identificado. Atualizar preserva os
dados fixos e informa que a consulta é simulada.

Em desktop, lista e conteúdo do detalhe têm rolagem própria; as ações ficam
fora dessas áreas. Em 390 px, selecionar uma sessão abre seu detalhe.
“Voltar às sessões” recupera a lista e o foco na mesma tarefa.
Tema, filtros e seleção ficam apenas na memória da página; recarregar
restaura o cenário inicial.

## Matriz: ponto da Central atual → componente v2

A correspondência foi conferida no código autorizado e na captura sintética.
Os nomes abaixo também identificam os componentes no HTML.

| Ponto da Central atual | Fonte | Componente v2 |
|---|---|---|
| Logo, título e comandos de cabeçalho | `shell/menus/tarefas/janela.py:274` | `.brand`, Atualizar, Nova tarefa, Conversa de Pescador e Painel de indicadores |
| Resumo operacional | `shell/menus/tarefas/janela.py:308`; captura fornecida | `#summary`: quatro estados, contagens e seleção para filtrar |
| Abas Sessões e Projetos e fila | `shell/menus/tarefas/janela.py:390` | `#main-tabs`, `#sessions-view`, `#queue-view` |
| Lista agrupada e quatro colunas | `shell/menus/tarefas/janela.py:317`; captura fornecida | `#session-rows`, `GROUPS`, `renderSessions`; filtros discretos |
| Nome, situação e próxima ação da seleção | `shell/menus/tarefas/janela.py:582` | `renderInspector`, `.situation`, mensagem de ação esperada |
| Última atividade e mudanças observadas | `shell/menus/tarefas/janela.py:341` | Acompanhamento: atividade e linha do tempo delimitada ao cenário |
| Saída recente do agente | `shell/menus/tarefas/janela.py:604` | Saída do agente: excerto sintético identificado |
| Atributos da sessão | `shell/menus/tarefas/janela.py:606` | Detalhes: projeto, coordenador, conversa, autor, revisor, sessão, ramo e pasta |
| Entrega consultável antes da confirmação | `shell/menus/tarefas/janela.py:354` | Entrega: revisão, verificações, objeto e etapas recolhidas |
| Abertura e retomada no terminal | `shell/menus/tarefas/janela.py:601` | `sessionAction`: destino explícito, somente prévia |
| Integração pelo terminal e pela interface | `shell/menus/tarefas/janela.py:362` | Botões preservados; prévia exata e confirmação demonstrativa em passo separado |
| Atalho Alt+I e encerramento separado | `shell/menus/tarefas/janela.py:367` | Alt+I abre a prévia quando cabível; Encerrar sem integrar tem posição secundária; Ctrl+X fora de campos de texto |
| Cadastro, atividade, importação e atualização | `shell/menus/tarefas/operacional.py:25` | Barra de Projetos e fila e formulários `showForm` |
| Árvore e detalhes relacionados | `shell/menus/tarefas/operacional.py:117` | `renderQueue`, `renderQueueDetail`, projeto/atividade/tarefa/sessão e relações |
| Pausar, Retomar, Cancelar e Repetir | `shell/menus/tarefas/operacional.py:172` | `ALLOWED`: mesmos conjuntos de estados; indisponibilidade explícita; M1 protegido |
| Instruções de revisão | `shell/menus/tarefas/operacional.py:265` | Prévia com tarefa, projeto, objeto e limite de autoridade |
| Acompanhar sessão vinculada | `shell/menus/tarefas/operacional.py:278` | Seleção do mesmo vínculo na aba Sessões |
| Modo de cor e cores de estado | `shell/menus/tarefas/janela.py:655` | Reserva oficial, amostra Cordel e estados sem paleta por provedor |

A busca na árvore e os formulários ensaiam a apresentação; não reproduzem
o backend. A adaptação estreita troca a composição simultânea por acesso
à lista e ao detalhe, preservando a seleção.

## Identidade e fluxo documentados

A seção 4 de `docs/evolucao-2.0/03-identidade-visual.md` distingue a
implementação do levantamento histórico. Fichas, fontes, estados e medidas
foram reaproveitados; a arquitetura Qt/Shiny de `04-interface.md` permanece
fora do alcance de alteração desta prévia.

O PNG de `shell/temas/logo/jangada.png` mantém seus bytes originais e a cor
creme `#e6d9be`, exibido em 40 × 40 px na amostra Cordel escura.
O modo claro e a reserva escura usam a geometria oficial de
`jangada-symbolic.svg`, recolorida por `currentColor`.
Não há recursos visuais gerados, emojis substitutos ou referências a outro projeto.

Cordel abre como amostra documentada, sem leitura de configuração pessoal:
superfície `#141311`, texto `#e6e2de`, primária `#e6d9be`, texto primário
`#37301d` e atenção `#dbd8e9`. A superfície elevada `#211f1d` corresponde aos
canais RGB da caixa SDDM `#f2211f1d`, usada aqui opaca. Texto suave vem da
reserva escura. Cordel claro usa integralmente a reserva clara oficial.

Reserva oficial mantém os sete valores de cada modo em
`default/visual/padrao.json`. `ESTADOS` e `ICONES` de
`default/visual/fichas.py:11` fornecem as cores e os símbolos.
As sessões seguem o mapeamento de `janela.py:655`: aguardando usa Bloqueada,
trabalhando usa Executando, turno finalizado usa Em revisão e interrupção
usa Falhou. A fila apresenta os nomes de estado próprios, separados dos
estados da sessão. Nenhum fim de turno é rotulado como tarefa concluída.
Primária indica ação ou seleção; cor nunca aparece como único sinal de estado.

Texto usa `Inter, "Noto Sans", system-ui, sans-serif`; identificadores usam
`"JetBrains Mono", monospace`. Inter está ausente neste ambiente, com
reserva explícita na nota da interface. Não há instalação ou download de fonte.
Corpo de 14 px, mínimo de 13 px, escala de 4 px e raio de 8 px foram mantidos.

O percurso de `docs/coordenacao-central/03-central-ux.md:71` aparece em
Entrega: explorar; decidir/autorizar; escopo e critérios; autor e apoio;
revisão independente; verificações; integrar por gesto separado; encerrar.
Coordenador, conversa e tarefa continuam distintos, conforme o documento 02,
nos pontos de navegação e autoridade. Não existe campo de chat embutido ou
botão que conceda autorização real.

A política posterior do dono prevalece sobre o texto antigo de agy exclusivo:
leitor/redator locais nos casos validados; demais papéis com destino agy
explícito e autorizado, sem alternativa automática. Nada nesta prévia muda
ou implementa a política. Apoio por Claude, agy ou Ollama: **não executado**.
Os nomes de autores e revisores da tela são dados fictícios.

## Cenários para avaliação

1. Selecione um estado no resumo, combine busca e projeto e use Limpar filtros.
   Recolha e expanda um grupo; confira a seleção e as quatro colunas.
2. Abra as quatro abas de uma sessão. Compare a última mensagem, a saída
   delimitada, os atributos e a entrega. Examine o próximo passo recolhido.
3. Selecione “Conferir o roteiro de navegação por teclado”. A revisão pendente
   impede integração. Compare com “Conferir as referências da síntese”, cujo
   cenário fictício permite percorrer prévia e confirmação separadas.
4. Abra as prévias de terminal e encerramento. Confira seus destinos e volte
   com Escape. Nenhuma sessão deve desaparecer ou mudar de estado.
5. Em Projetos e fila, selecione projeto, atividade, tarefa e sessão.
   Compare ações em fila, pausa, revisão e repetição; use Acompanhar sessão.
6. Confira o formulário de Nova tarefa com os dois perfis. Texto digitado,
   inclusive caracteres de HTML, deve aparecer como texto no resumo do pedido.
7. Compare Cordel, reserva escura e claro. Em 390 px, abra uma tarefa e use
   Voltar às sessões. A seleção e os filtros devem permanecer reconhecíveis.
8. Use Tab e Shift+Tab nos controles; setas, Home e End nas abas; setas
   verticais na lista de sessões; Escape nos modais. Ctrl+F foca a busca.
   Ctrl+X dentro de campo de texto conserva a função de recortar.

## Conferências executadas na v2

A quebra literal inicialmente encontrada em uma string de saída foi
corrigida antes do ensaio válido. O script extraído passou em `node --check`.
O ensaio do autor em Chromium headless passou em **66 conferências da v2**,
sem exceções JavaScript nem requisições externas. Incluiu seleção, resumo,
filtros, recolhimento, quatro abas, teclado, temas, formulários com texto
escapado, estados da fila, M1 bloqueado e confirmação demonstrativa separada.
O sandbox do Chromium permaneceu ativo.

Foram renderizadas e examinadas capturas em 1200 × 780, 1440 × 900,
1600 × 1000 e 390 × 844. O ensaio verificou ações de sessão visíveis nas
três dimensões de desktop e ausência de transbordamento horizontal nas
larguras ensaiadas. Em tela estreita, conferiu abertura de detalhe, retorno
à seleção e modal dentro da largura disponível. A preferência por menos
movimento também foi conferida.

A conferência determinística da v2 confirmou PNG com bytes idênticos,
SVG com geometria idêntica, reserva oficial exata e contraste da amostra
Cordel aceito pela função `validar` de `fichas.py`. Os menores contrastes
medidos foram 7,78:1 em Cordel escuro, 7,72:1 na reserva escura e 5,53:1
na reserva clara. Incluem texto, texto suave, primária, atenção e estados
sobre ambas as superfícies, além de texto primário sobre primária.
Isso não representa certificação completa de acessibilidade.

O coordenador conferiu externamente **29 itens da v2**, com resultado `ok`
e nenhuma exceção JavaScript. Seu relatório está em
`.jangada/conferencia-coordenador-browser-v2.json`, na raiz deste worktree.
Inclui árvore, formulários, texto escapado, prévia exata, confirmação separada,
filtros, temas e Escape com retorno de foco. O coordenador informou inspeção
visual em 1200 × 780 e 390 px, com ações essenciais visíveis.
Essa conferência é específica da prévia e não constitui revisão independente.
As contagens da v1 não foram reaproveitadas como evidência da v2.

Capturas e roteiros do autor estão temporariamente em
`/tmp/jangada-mockup-v2-*.png` e `/tmp/jangada-v2-*`.
Não são dependências do HTML nem arquivos adicionais desta entrega.

## Limites

Só `index.html` e este README foram alterados para a prévia.
Dados, horários, pastas, ramos, objetos, pareceres e verificações exibidos
são sintéticos. O M1 real continua parado e preservado; seus arquivos e
registros não foram consultados. M3 não foi implementado ou concluído.
A cópia da v1 preservada pelo coordenador não foi apagada ou modificada.

Não há `fetch`, rede, armazenamento persistente, leitura de histórico ou
configuração pessoal, backend, comando, Core ou Qt executado pela página.
A política de conteúdo bloqueia conexões. Formulários não criam registros;
a confirmação demonstrativa não integra, aprova, assina, publica, instala
ou atualiza. Fechar o HTML não altera tarefas reais.

A prévia permanece sem commit e sem integração. A suíte completa e a revisão
formal não fazem parte desta rodada. Consolidação futura continua sujeita
à autorização, revisão independente e aos portões de validação existentes.
