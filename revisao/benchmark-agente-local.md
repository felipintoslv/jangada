# Agente local no jangada: comparação com projetos semelhantes

Documento de consulta, feito em 29/09/2026. Complementa
`benchmark-agentes.md` com uma pergunta só: como os projetos parecidos com o
jangada incorporam um modelo de linguagem rodando na própria máquina.

Fonte: busca na API do GitHub (`search/repositories`, ordenada por estrelas)
com os termos "claude code worktree tmux ollama", "tmux worktree agents
ollama", "claude code ollama subagent", "hyprland ollama agent", "claude code
router", "agent orchestrator worktree local llm" e "ollama delegate claude";
a lista [awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators)
(223 projetos); o README de 12 projetos; e o issue
[anthropics/claude-code#38698](https://github.com/anthropics/claude-code/issues/38698).
Estrelas e datas do último envio são as do dia da consulta. Os ganhos citados
são os declarados pelos autores, não medidos aqui.

## 1. Resumo

Nenhum projeto encontrado junta o que o jangada já tem (sessão Hyprland,
worktree e tmux por tarefa, revisão cruzada entre Claude e agy, delegação com
controle de cota) a um modelo local. Os projetos se dividem em cinco famílias,
e cada uma resolve um pedaço:

1. Orquestradores de worktree e tmux que usam o modelo local só para resumir
   sessões.
2. Distribuições Arch e Hyprland que oferecem o modelo local como atalho de
   conversa.
3. Pontes de delegação que mandam trabalho do Claude a um modelo local.
4. Esteiras inteiramente locais, com implementador e revisores em modelos
   próprios.
5. Roteadores que trocam o provedor da sessão inteira.

A conclusão prática é que o formato já adotado pelo `jangada-delegar`
(comando de terminal, o script lê os arquivos, o modelo recebe só texto e
devolve relatório curto) é o mesmo dos projetos que declaram maior economia.
O formato de agente completo com modelo local só aparece com modelos de 14B a
35B, fora do alcance de uma placa de 8 GB.

## 2. Projetos

### 2.1 Orquestradores com modelo local auxiliar

| Projeto | Estrelas | Último envio | Uso do modelo local |
|---|---|---|---|
| [nixfred/infomarchy](https://github.com/nixfred/infomarchy) | 121 | 26/09/2026 | Plugin do Omarchy. Painel com um cartão por agente (Claude, Codex, Gemini, Ollama), lido de `/proc`. O modelo local só refina o resumo da sessão se já estiver carregado; o painel nunca carrega modelo sozinho. Mostra a memória de vídeo de cada modelo e tem botões de carregar e descarregar, com confirmação para modelos acima de 8 GiB. |
| [khodaei/hive](https://github.com/khodaei/hive) | 0 | 24/04/2026 | Sessões Claude em worktree e tmux, estado em SQLite. O Ollama (`llama3.2:3b`) resume cada sessão em objetivo, progresso e próximo passo. Se o Ollama cair, mostra o último resumo guardado; nada no caminho principal espera o modelo. |
| [astoreyai/goblin-forge](https://github.com/astoreyai/goblin-forge) | 2 | 12/06/2026 | Worktree e tmux para Claude, Aider e Codex em paralelo, com painel em Bubble Tea e voz via Whisper. O modelo local entra como mais um agente, sem papel próprio. |

### 2.2 Distribuições Arch e Hyprland

| Projeto | Estrelas | Último envio | Uso do modelo local |
|---|---|---|---|
| [vinpatel/vinos](https://github.com/vinpatel/vinos) | 4 | 28/08/2026 | Arch com Hyprland, instalável por cima de um Arch existente em `~/.local/share/vinos` (mesmo arranjo do jangada). `Super+A` abre conversa com o Ollama e `Super+Shift+A` abre o Claude Code no projeto. O pacote `ai` instala ollama, claude-code, open-webui e llm. Promete "80% do trabalho de agente na sua GPU", sem medição publicada. |

### 2.3 Pontes de delegação do Claude para o modelo local

| Projeto | Estrelas | Último envio | Formato | O que vale copiar |
|---|---|---|---|---|
| [imkunal007219/claude-coworker-model](https://github.com/imkunal007219/claude-coworker-model) | 172 | 26/06/2026 | Comandos de terminal (`ask-kimi --paths ... --question ...`) sobre qualquer API compatível com OpenAI, Ollama incluído. Regras de quando delegar ficam no CLAUDE.md. | É o formato do `jangada-delegar`. Relato do autor: o limite semanal do plano Pro deixou de estourar e a leitura de arquivos caiu de 80% para 20% dos tokens. |
| [houtini-ai/houtini-lm](https://github.com/houtini-ai/houtini-lm) | 120 | 24/09/2026 | Servidor MCP. O próprio servidor lê os arquivos e os manda ao modelo, então o conteúdo nunca entra no contexto do Claude. | Única medição publicada: economia de 86% a 95% em quatro tarefas de leitura (revisão de 581 a 2.022 linhas), perto de zero em tarefa curta, porque a chamada custa uns 250 tokens. Modelo local de 3 a 30 vezes mais lento. |
| [aplaceforallmystuff/mcp-local-llm](https://github.com/aplaceforallmystuff/mcp-local-llm) | 13 | 22/09/2026 | Servidor MCP com ferramentas fechadas: resumir, rascunhar, classificar, extrair e transformar texto. | Ferramentas de entrada e saída de texto, sem uso de ferramentas pelo modelo, cabem num modelo pequeno. |
| [fegone/claude-code-delegate-local](https://github.com/fegone/claude-code-delegate-local) | 10 | 28/09/2026 | Servidor MCP que roda a definição de um subagente (`.claude/agents/NOME.md`) num modelo local, com ferramentas de ler, escrever e executar. | Duas regras: modelo local **nunca** passa para a nuvem quando falha, para dado sigiloso não sair sem aviso; vagas por modelo controladas por `flock` em arquivo, compartilhadas entre sessões (2 para modelo local). Limite de 15 turnos para modelo local contra 25 na nuvem. |
| [PratikHotchandani22/claude-ollama-agents](https://github.com/PratikHotchandani22/claude-ollama-agents) | 6 | 05/04/2026 | Subagentes do Claude que chamam um script do Ollama e depois gravam o resultado. | Contraexemplo: o subagente continua sendo o Claude, lê os arquivos e revisa a saída, então parte da economia se perde. Usa modelos de 32B a 35B. |

### 2.4 Esteiras inteiramente locais

| Projeto | Estrelas | Último envio | Arranjo |
|---|---|---|---|
| [romkravets/llm-server-orchestrator](https://github.com/romkravets/llm-server-orchestrator) | 0 | 05/09/2026 | Implementador `qwen2.5-coder:14b`, revisor `deepseek-r1:14b` e verificador de segurança `qwen2.5-coder:7b`, cada um num modelo diferente para ninguém revisar o próprio trabalho. Worktree descartável e aprovação humana diante do `git diff` real. O implementador só pode encerrar depois de gravar arquivo de fato. |
| [redevops-io/sidekick](https://github.com/redevops-io/sidekick) | 10 | 27/09/2026 | Divide a tarefa em subtarefas, uma worktree por subtarefa, testes de aceitação e junção dos ramos aprovados. Qualquer modelo via LiteLLM; o padrão é modelo local em CPU. |

### 2.5 Roteadores e situação no Claude Code

| Projeto | Estrelas | Último envio | Papel |
|---|---|---|---|
| [musistudio/claude-code-router](https://github.com/musistudio/claude-code-router) | 37.481 | 26/09/2026 | Ponto de acesso local único que encaminha as chamadas do Claude Code, Codex e outros a qualquer provedor, com registro de custo e troca automática. Troca o modelo da sessão toda, não de um subagente. |

O Claude Code não permite apontar um subagente para outro provedor: o
`ANTHROPIC_BASE_URL` vale para a sessão inteira. O pedido está aberto desde
25/03/2026 no issue #38698, com 11 comentários. Por isso todos os projetos da
seção 2.3 contornam o problema com servidor MCP ou comando de terminal.

## 3. O que isso diz para o jangada

| # | Lição | De onde vem | Como aplicar |
|---|---|---|---|
| A | Delegar leitura por comando de terminal, com o script lendo os arquivos, é o formato de maior economia declarada. | houtini-lm, claude-coworker-model | Destino `local` no `jangada-delegar`, sem subagente do Claude no meio (evitar o formato de claude-ollama-agents). |
| B | Modelo local nunca cai para a nuvem sem aviso. | claude-code-delegate-local | Se o destino `local` falhar, recusar com código 4. Não reencaminhar ao agy, porque o motivo da escolha pode ter sido sigilo. |
| C | Nunca carregar modelo por conta própria nem esperar por ele no caminho principal. | infomarchy, hive | Checar jogo aberto (`reaper SteamLaunch`) e memória de vídeo livre antes de carregar; `OLLAMA_KEEP_ALIVE` curto. |
| D | Vagas por modelo com `flock`, compartilhadas entre sessões. | claude-code-delegate-local | Uma vaga só: com 8 GB, dois pedidos simultâneos ao modelo local disputam a mesma memória. |
| E | Resumo de sessão é o uso de menor risco para modelo pequeno. | hive, infomarchy | Primeiro passo possível: resumo de cada sessão no painel do `jangada-agentes`, com o último resumo guardado se o Ollama estiver parado. |
| F | Ferramentas fechadas de texto (resumir, classificar, extrair) funcionam em modelo pequeno; agente completo pede de 14B para cima. | mcp-local-llm, llm-server-orchestrator, claude-ollama-agents | Limitar o destino `local` aos papéis leitor e redator. Nenhum projeto roda implementador local útil com menos de 14B. |
| G | Revisão por modelo diferente do que implementou. | llm-server-orchestrator | O jangada já faz isso entre Claude e agy. Um modelo local de 8B como terceiro revisor acrescentaria pouco. |
| H | Medir tokens lidos direto contra tokens delegados. | houtini-lm (`scripts/benchmark.mjs`) | Registrar no `delegacoes.jsonl` o tamanho do texto enviado ao modelo local, para estimar os tokens do Claude poupados, que é a métrica central do benchmark de 26/09. |

## 4. Limites desta comparação

1. Quase todos os projetos têm menos de 200 estrelas; só o
   claude-code-router passa de mil, e ele resolve outro problema.
2. Os ganhos são declarados pelos autores. Só o houtini-lm publica o método e
   o script para repetir a medição.
3. Os projetos que usam agente local completo rodam modelos de 14B a 35B, ou
   máquinas Mac com memória unificada. A RTX 4060 desta máquina, com uns
   5,7 GB livres depois da área de trabalho, comporta modelos de 7B a 8B com
   contexto de 16 mil a 32 mil tokens.
4. A busca foi pelo nome e pela descrição dos repositórios; projetos que usam
   modelo local sem citar isso na descrição ficaram de fora.

## 5. Verificação

Em 29/09/2026 um subagente pesquisador (Haiku) conferiu dez grupos de
afirmações contra a API do GitHub e os READMEs. Estrelas, datas e os itens
de hive, infomarchy, vinOS, llm-server-orchestrator, claude-coworker-model e
do issue #38698 saíram confirmados. Os três pontos que ele não achou ou deu
como divergentes foram conferidos no texto dos READMEs e estão corretos:

1. houtini-lm: a tabela traz 86% a 95%, e o texto traz "around 250 tokens" e
   "3-30x slower".
2. claude-code-delegate-local: o padrão é "a pool of six" vagas por modelo,
   mas o grupo `local-` tem 2, com `flock` em
   `~/.cache/claude-delegate-local/slots/`; `max_turns` automático de 15 para
   local e 25 para nuvem.
3. claude-ollama-agents: a tabela de agentes lista `qwen3.5:35b-a3b` e
   `qwen2.5-coder:32b` como modelos padrão.

A tentativa anterior pelo `jangada-delegar` (agy Flash, papel pesquisador)
foi recusada porque o agy não tem `ReadUrlContent` em `permissions.allow`.
