# Prévia navegável da Central de Trabalho

Protótipo visual para o dono avaliar identidade, densidade e navegação.
Abra [index.html](index.html) diretamente pelo navegador, com `file://`.
CSS, JavaScript e logos estão incorporados. Não precisa de servidor,
instalação, pacotes ou acesso à rede.

## Alcance

A tela apresenta dois projetos demonstrativos, cada um com um coordenador
identificado e três conversas: Planejamento, Implementação e Testes.
A seleção delimita as tarefas e atualiza o destino textual da sessão.
Objetivo, etapas, próxima ação e abas pertencem à tarefa selecionada.

Busca por título ou identificador e filtro por estado funcionam juntos,
somente na conversa selecionada. Trocar projeto ou conversa limpa esses
filtros. A troca de tema preserva projeto, conversa, tarefa, aba e filtros.
As seleções ficam na memória da página e reiniciam ao recarregar.

O bloco “Precisa de você” leva à tarefa da decisão pendente. Não registra
decisão nem concede autorização. “Abrir sessão” mostra apenas “Abriria a
sessão ...”, com projeto, coordenador e conversa explícitos.

Na aba Entrega, as prévias de entrega e integração são separadas.
A integração mostra exatamente objeto, base, candidato, arquivos e revisor
do cenário selecionado. Seus identificadores não são hashes Git.
Cada modal oferece somente “Fechar prévia”. Escape fecha e devolve o foco.

## Identidade e fontes

O PNG incorporado tem os bytes originais de
`shell/temas/logo/jangada.png`, sem redesenho ou recoloração. Aparece com
48 × 48 px no modo escuro. O modo claro usa a geometria original de
`shell/temas/logo/jangada-symbolic.svg`, recolorida por `currentColor`.
Não há imagens geradas, emojis substitutos ou recursos de outro projeto.

Cordel abre como **amostra do tema documentado**, não como configuração
atual. Mantém superfície `#141311`, texto `#e6e2de`, primária `#e6d9be`,
texto primário `#37301d` e atenção `#dbd8e9`.
A superfície elevada `#211f1d` vem dos canais RGB da caixa SDDM
`#f2211f1d`, usada aqui opaca. Texto suave vem da reserva escura.
O modo claro de Cordel utiliza integralmente a reserva clara oficial;
não foi inventada uma variante clara Cordel.

A opção Reserva oficial conserva os sete valores de cada modo de
`default/visual/padrao.json`. Cores e símbolos de estado reproduzem
`ESTADOS` e `ICONES` de `default/visual/fichas.py`.
Primária indica seleção ou ação; estado combina cor, símbolo e rótulo.
Não há paletas por modelo.

Inter é prevista e não está instalada neste ambiente. A pilha CSS é
`Inter, "Noto Sans", system-ui, sans-serif`. Identificadores usam
`"JetBrains Mono", monospace`. Nenhuma fonte é baixada.
Corpo de 14 px, mínimo de 13 px, espaçamento em múltiplos de 4 px e raio
de 8 px seguem as fichas. Há foco visível e preferência por menos movimento.

## Matriz de correspondência conferida

As linhas abaixo indicam a fonte e o componente correspondente em
[index.html](index.html). O levantamento histórico do documento 03 foi
lido junto à seção 4, que registra a implementação em 08/10/2026.

| Padrão ou fluxo | Fonte no repositório | Componente da prévia |
|---|---|---|
| Geometria oficial preservada | `shell/temas/logo/jangada.png`; `jangada-symbolic.svg:1` | `.brand`: PNG original incorporado e SVG com os mesmos caminhos e retângulos |
| Fichas implementadas, dois modos | `docs/evolucao-2.0/03-identidade-visual.md:151`; `default/visual/padrao.json:1` | `PADRAO`, `applyTheme`, seletores Paleta e Modo |
| Cordel documentado como amostra | `docs/evolucao-2.0/03-identidade-visual.md:29`; `shell/temas/sddm/jangada/theme.conf:14` | `CORDEL`, nota em Identidade e limites |
| Estados fixos, símbolo e nome | `default/visual/fichas.py:11`; `default/visual/fichas.py:16` | `ESTADOS`, `ICONES`, `badge` e filtro Estado |
| Fonte, medidas e acessibilidade | `docs/evolucao-2.0/03-identidade-visual.md:122`; `:129`; `:151` | CSS, foco, atalho para tarefas, abas por teclado e preferência por menos movimento |
| Lista, critérios e entrega selecionável | `docs/evolucao-2.0/04-interface.md:106`; `:128` | `renderList`, `renderDetail`, abas Pedido, Entrega, Revisão e Verificações |
| Um coordenador por projeto | `docs/coordenacao-central/02-coordenador-contextos.md:45` | `projects`, identificação do coordenador e seleção de projeto |
| Projeto, conversa e sessão explícitos | `docs/coordenacao-central/03-central-ux.md:29`; `:105` | `renderContext`, `#destination`, modal de sessão |
| Explorar antes de decidir e executar | `docs/coordenacao-central/03-central-ux.md:71` | “Precisa de você”, alternativas no Pedido e etapas 1 a 4 |
| Autoridade continua fora da proposta | `docs/coordenacao-central/02-coordenador-contextos.md:14` | Decisão apenas examinável; nenhum botão de autorização |
| Revisão, verificações e gesto separado | `docs/coordenacao-central/03-central-ux.md:167` | Etapas 5 a 8, aba Revisão e modal separado de integração |
| Turno finalizado difere de tarefa concluída | `docs/coordenacao-central/03-central-ux.md:167` | Nota sob a lista e atividade da sessão no detalhe |

A política posterior do dono prevalece sobre os trechos antigos de
agy exclusivo: leitor/redator locais nos casos validados; demais papéis
com destino agy explícito e autorizado, sem alternativa automática.
Esta prévia não altera nem implementa política de delegação.

## Cenários para discussão

1. Em Jangada / Planejamento, examine a decisão sobre o alcance da busca.
   Selecione as outras tarefas e compare objetivo, etapa e próximo passo.
2. Pesquise “identificada”, combine com um estado e observe o resultado
   vazio. Limpar filtros recupera as tarefas da conversa.
3. Em Implementação, selecione “Documentar a retomada sem reenviar mensagens”.
   Abra Entrega e compare as duas prévias. Nenhuma executa ações reais.
4. Examine a representação do M1 parado. Ela não consulta nem altera M1.
5. Troque para Demanda de pesquisa e abra a prévia da sessão de Testes.
   Confira projeto, coordenador, conversa e identificador de destino.
6. Alterne os modos e a reserva oficial. Use Tab e Shift+Tab para percorrer
   controles; setas, Home e End nas abas; Enter ou Espaço nos botões;
   Escape para fechar o modal e recuperar o foco de origem.

## Conferências desta prévia

O ensaio do autor em Chromium headless passou em 53 conferências de
seleção, busca, estado vazio, filtros, temas, abas, teclado, prévias e foco.
Nenhuma exceção JavaScript ou requisição externa foi observada.
O navegador manteve seu isolamento; não foi usada a opção `--no-sandbox`.

Capturas de 1440 px, 1600 px e 390 px foram renderizadas. A composição
foi examinada em desktop e tela estreita, nos modos claro e escuro.
Não houve transbordamento horizontal nas larguras ensaiadas.
As capturas e o roteiro temporário ficam em `/tmp/jangada-mockup-*`,
fora dos dois arquivos da prévia; não são dependências do HTML.

A conferência determinística confirmou bytes idênticos do PNG, geometria
idêntica do SVG e os seguintes contrastes mínimos:

| Esquema | Menor contraste medido |
|---|---:|
| Cordel escuro, amostra | 7,78:1 |
| Reserva escura | 7,72:1 |
| Reserva clara, também usada em Cordel claro | 5,53:1 |

A medida inclui texto, texto suave, primária, atenção e estados sobre ambas
as superfícies, além de texto primário sobre primária. Não equivale a uma
certificação completa de acessibilidade.

O coordenador também conferiu externamente 16 itens por CDP Chromium,
com resultado `ok`, sem exceções JavaScript. O registro fornecido está em
`.jangada/conferencia-coordenador-browser.json`, na raiz deste worktree.
Ele inclui Escape real com retorno de foco, troca de projeto, conversa,
filtros, tema, candidato na prévia e 390 px sem transbordamento.
Essa conferência não constitui revisão independente da entrega.

Apoio por Claude, agy ou Ollama: **não executado nesta prévia**.
A matriz foi conferida pelo autor nas fontes autorizadas.
O relatório agy exibido na tarefa `central-fluxo` é explicitamente fictício.

## Limites

Todos os projetos, tarefas, sessões, entregas, pareceres e evidências da
tela são sintéticos. O M1 real permanece parado e preservado; nenhum
registro ou arquivo dele foi consultado. Não há leitura de configurações
pessoais, históricos ou estado operacional real.

O HTML não usa `fetch`, rede, armazenamento persistente, comandos,
serviços ou integração com Core/Qt. A política de conteúdo bloqueia conexões
na própria página. Só os dados fixos incorporados alimentam a apresentação.

A decisão histórica de manter o painel Shiny permanece válida.
Este HTML é um artefato de discussão autorizado, não um novo painel
instalável nem uma substituição da Central Qt. M3 não foi implementado ou
concluído. Fechar a página não altera tarefas reais.

A prévia permanece sem commit, integração, publicação, assinatura ou
instalação. Revisão formal e validação de consolidação ficam pendentes para
uma etapa futura. As conferências descritas são específicas do protótipo.
