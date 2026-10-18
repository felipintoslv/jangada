# Jangada Vigia

O Jangada Vigia é a ferramenta do Jangada Shell voltada a acompanhar a
manutenção do sistema, conversar sobre o estado da máquina e do fluxo de
trabalho e criar peças para a barra e para a sessão gráfica em linguagem
natural, sempre sob supervisão e dentro do isolamento do jangada.
No planejamento, o nome era Inspector.

Os contratos detalhados da primeira versão estão em:

- [Contrato do diagnóstico](diagnostico.md): coletores, caminhos lidos,
  limites, mascaramento, formato do retrato JSON e retenção.
- [Riscos e contenção](riscos.md): proteção contra vazamento de dados pessoais,
  injeção de instruções por logs ou títulos de janela, comandos fora da lista
  e escritas fora de `~/.local/state/jangada`.

## Princípios

> Diagnosticar não autoriza modificar; gerar código não autoriza executá-lo na
> sessão ativa; aprovar uma alteração não autoriza outras.

- **Leitura e escrita separadas:** o diagnóstico opera somente em leitura, com
  lista fechada de comandos e caminhos, sem terminal livre para modelos e sem
  aplicar correções por conta própria.
- **Texto de registro é dado:** saídas de logs, erros de configuração e
  relatórios de falha nunca são tratados como instrução. Caracteres de controle
  são removidos, dados pessoais são mascarados e os blocos são demarcados como
  dados.
- **Fato separado de hipótese:** relatórios e comparações distinguem o que foi
  medido pelos coletores do que é hipótese ou proposta de mudança.
- **Subordinação às políticas do Core:** o Vigia segue o isolamento e o
  ciclo de revisão existentes do jangada e não cria outro orquestrador.
- **Permissão por peça:** peças parecidas não dividem permissão por
  conveniência. O nome ou a finalidade de uma peça não concede capacidade além
  do que o contrato declara.

## Decisões do projeto (I1 a I6)

| Código | Decisão |
|---|---|
| I1 | Não mexe no sistema operacional: não instala nem remove pacotes, não troca drivers, não reinicia serviços e não pede senha de administrador (`sudo`, `pkexec`). |
| I2 | Roda só quando pedido. Não há coleta periódica em segundo plano pelo diagnóstico nem retenção de histórico sem comando do usuário. |
| I3 | Foco em acompanhar a manutenção e criar aditivos para a barra e para o Jangada Shell por linguagem natural. |
| I4 | Agente inspetor dedicado no `agy` para conversa sobre o sistema e o fluxo de trabalho, condicionado ao teste prático da fase 2b. |
| I5 | Controle pelo celular descartado. |
| I6 | Ordem de execução: modularização 3.0 fechada, M3-19, período de uso e só então o Vigia, começando pelo planejamento. |

### Ajustes decorrentes de I1 e I2

- **Peças que exibem estado:** monitores de energia e de atualização apenas
  mostram dados e avisos; nunca trocam perfil de energia nem executam
  atualização. O modo de foco usa somente controles que o Shell já oferece
  (silenciar notificações e temporizador), sem bloquear processos.
- **Atualização da barra:** um módulo instalado na Waybar lê contadores locais
  a cada poucos segundos pela própria natureza da barra. Isso não é coleta do
  Vigia, e sim execução de uma peça aprovada pelo usuário com fonte e
  intervalo declarados no contrato. O diagnóstico do Vigia continua
  exclusivamente sob pedido.

## Frentes de atuação

1. **Diagnóstico e comparação:** coleta determinística sobre serviços,
   recursos, sessão gráfica, barra, instalação do jangada e erros da partida
   atual, gerando um retrato JSON e um relatório em Markdown em
   `~/.local/state/jangada/vigia/`. Na última fase, compara dois retratos
   para responder por que o sistema mudou.
2. **Conversa sobre o sistema e o fluxo de trabalho:** sessão interativa com o
   agente inspetor lendo o retrato gerado pelo diagnóstico, sem terminal livre
   e sem alterar arquivos, encerrando com uma proposta textual curta (o que
   mudar, por quê, o que testar e como desfazer).
3. **Oficina de peças:** geração, ensaio e instalação supervisionada de peças
   para a Waybar e o Jangada Shell. Toda peça nasce em pasta separada, passa
   por análise e testes dentro do `jangada-isolar`, é exibida em sessão
   Hyprland aninhada com a barra ativa e só é instalada em
   `~/.config/jangada` após aprovação específica do usuário, com contrato de
   12 campos (`id`, `versao`, `descricao`, `fontes_de_dados`, `permissoes`,
   `dependencias`, `limites_de_recursos`, `comandos_permitidos`,
   `arquivos_alterados`, `testes`, `desinstalacao`, `reversao`).

## Catálogo de peças (descontando o que a barra já tem)

A barra do Shell (`waybar/config.jsonc`) já possui módulos para processador,
memória, disco, rede, temperatura, mídia (`mpris`), privacidade, atualizações,
unidades do systemd com falha e agentes. O trabalho previsto para cada item do
catálogo concentra-se apenas no que falta:

| Ordem | Peça | Já existe na barra | O que falta |
|---:|---|---|---|
| 1 | Monitor de rede passivo | Nome da rede, sinal e dica com vazão | Taxa na barra e histórico curto ao clicar, usando apenas `/sys/class/net` |
| 2 | Saúde do sistema | Processador, memória, disco e temperatura | Janela de detalhe e alertas com evidência |
| 3 | Monitor de GPU | Não | Uso, memória e temperatura da NVIDIA por `nvidia-smi`, somente leitura |
| 4 | Modo de foco | Inibidor de repouso | Temporizador local e silenciamento de notificações |
| 5 | Monitor de energia | Temperatura e bateria | Painel de sensores (`lm_sensors`), somente exibição |
| 6 | Consulta de snapshots | `jangada-snapshot` | Lista de consulta na interface, sem restauração |
| 7 | Inspetor de atualizações | Módulo de atualizações | Avisos de compatibilidade de kernel e driver, somente listagem |
| 8 | Monitor de Docker | Não | Estado dos contêineres por coletor restrito de leitura, sem expor o soquete Docker e fora de escopo até desenho próprio para proteger bancos de pesquisa |
| 9 | Controle de mídia | Módulo `mpris` com `playerctl` | Botões visíveis de pausa e avanço, sem credenciais e sem acesso ao áudio |
| 10 | Visualizador de áudio | Não (`cava` instalado) | Barras de frequência em saída escolhida explicitamente, nunca no microfone |
| 11 | Teste ativo de velocidade | Não | Medição sob comando manual, avisando destino e exposição de IP |
| 12 | Guarda da área de transferência | Não | Limpeza voluntária, sem ler, gravar nem enviar o conteúdo copiado |
| 13 | Guarda de privacidade | Módulo `privacy` | Avaliar se resta lacuna em relação ao módulo nativo |

O acompanhamento de agentes previsto no estudo original fica de fora, pois
a Waybar e a Central de Tarefas já mostram tarefas e indicadores.

## Fases e ordem de execução

| Fase | Entrega | Critério de conclusão |
|---:|---|---|
| 0 | Base 3.0 estável, M3-19 e período de uso | Suíte passando, sem regressão conhecida |
| 1 | Planejamento | Documentos em `docs/vigia/` aprovados pelo Felipe |
| 2 | Diagnóstico, primeira versão | Comando `jangada-vigia` sob pedido, retrato JSON e relatório de fatos em `~/.local/state/jangada/vigia/`, nenhuma escrita fora |
| 2b | Conversa sobre o sistema e o fluxo de trabalho | Skill do `agy`, abertura da conversa lendo o retrato do diagnóstico e saída em proposta escrita |
| 3 | Contrato das peças | Manifesto de 12 campos, instalação, desinstalação e reversão testados com peça de exemplo |
| 4 | Três peças feitas à mão (rede passiva, saúde do sistema e GPU) | Funcionam sem chamada externa e sem processos órfãos; servem de molde para a oficina |
| 5 | Oficina supervisionada | Gera, isola com `jangada-isolar`, mostra no Hyprland aninhado com barra, revisa e instala peça nova |
| 6 | Peças de risco médio (atualizações, controle de mídia, foco, energia, snapshots e, após desenho próprio, Docker) | Uma por vez, cada uma com contrato e testes |
| 7 | Peças de privacidade (visualizador de áudio, teste ativo de velocidade, área de transferência) | Consentimento específico por peça e testes de privacidade |
| 8 | Comparador de diagnósticos | Diferenças reproduzíveis entre dois retratos, separando fatos medidos de hipóteses |
