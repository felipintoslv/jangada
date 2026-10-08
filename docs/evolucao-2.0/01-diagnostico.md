# Diagnóstico do jangada para a evolução 2.0

Base analisada: commit `9dcb640` do ramo `agente/tarefa-ab47cef8d325`, em
07/10/2026. São 302 arquivos versionados.

Convenção de certeza usada neste documento:

- **F** (fato): lido no código, com caminho e linha.
- **I** (inferência): conclusão tirada de fatos, sem execução que a confirme.
- **N** (não verificado): arquivo não lido por inteiro ou comportamento não
  executado.

Documentação existente só foi usada como pista. Toda afirmação marcada F foi
conferida no código.

## 1. Inventário

### 1.1 Diretórios de primeiro nível

| Caminho | Arquivos | Conteúdo | Papel na 2.0 |
|---|---|---|---|
| `bin/` | 58 | Comandos `jangada-*` em Bash e o despachante `bin/jangada` | Núcleo operacional; ponto principal de mudança |
| `default/` | 108 | Padrões do sistema: agentes, orquestração, painel, Central, tema, barra, hooks, skills | Onde ficam perfis, fila, painel e identidade |
| `config/` | 4 | `jangada.conf` e modelos do usuário para o Hyprland | Recebe as novas chaves de provedor |
| `testes/` | 49 | Suíte em Bash, Python, R e Lua, com `verificar.sh` como entrada | Base para os testes com serviços falsos |
| `docs/` | 10 | Documentação por tema (ciclo, isolamento, painel, registros, delegação) | Referência, a confrontar com o código |
| `install/` e `install.sh` | 12 e 1 | Instalação em etapas numeradas (`00` a `90`) e listas de pacotes | Ponto de entrada de dependências novas |
| `migrations/` | 24 | Migrações datadas para cópias já instaladas | Obrigatórias para mudar comportamento instalado (regra 5) |
| `shell/` | 2 | `jangada.sh` e `jangada-shell.sh` | Sem mudança prevista |
| `revisao/` | 23 | Pareceres antigos, pendências e roteiros de auditoria | Histórico |
| `estudos/` | 1 | `auditoria-as-is-2026-10-03.md` (516 linhas) | Diagnóstico anterior, reaproveitado com conferência |
| `benchmarking/` | 1 | Comparação de módulos de barra | Sem relação direta |
| `.github/` | 1 | `workflows/verificar.yml` | Integração contínua |
| raiz | 8 | `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md`, `CHANGELOG.md`, `LICENSE`, `.gitignore`, `JANGADA_V2_INSTRUCOES.md` | Regras e roteiro anterior |

`desac.md` não está no repositório nem no histórico do git. A única cópia
achada está em `~/Downloads/desac.md` (38 linhas), fora do projeto. A
classificação da seção 7 usa essa cópia.

### 1.2 Pontos de entrada

| Entrada | Arquivo | Função |
|---|---|---|
| Despachante | `bin/jangada` | Encaminha `jangada <comando>` para `bin/jangada-<comando>` |
| Abrir sessão | `bin/jangada-agente` (480 linhas) | Cria worktree, ramo, sessão tmux e estado |
| Validar entrega | `bin/jangada-validar` (1083) | Verificação local e revisão por outro modelo |
| Encerrar e integrar | `bin/jangada-agente-fim` (503) | Mescla sob trava e remove o worktree |
| Listar sessões | `bin/jangada-agentes` (797) | Seletor, barra, restauração |
| Delegar | `bin/jangada-delegar` (995) | Subagentes em `local`, `agy` e `codex-economico` |
| Fila | `bin/jangada-fila`, `-executar`, `-retomar`, `-task`, `-router`, `-provedor` | Todos chamam `default/orquestracao/cli.py` |
| Central de Atividades | `bin/jangada-tarefas` | Abre `default/tarefas/central.py` (Qt) |
| Painel | `bin/jangada-painel` (212) | Coleta e sobe o Shiny em `127.0.0.1` |
| Conversa | `bin/jangada-conversa` | Janela Qt que fala com o Ollama |
| Isolamento | `bin/jangada-isolar` (614) | Monta o bubblewrap |
| Verificação | `testes/verificar.sh` | Suíte completa |

## 2. Arquitetura atual

O sistema tem dois fluxos de trabalho que quase não se tocam, e um painel que
só lê.

```
(A) Sessão interativa
    Central Qt ou terminal
      -> jangada-agente -> worktree + tmux + isolamento -> CLI (claude | codex)
      -> hooks gravam agentes/SESSAO.json
      -> jangada-validar (verificação local + revisor claude | agy | codex)
      -> jangada-agente-fim --integrar (merge sob trava)

(B) Fila de automação
    PLANO.json -> jangada-fila --importar -> SQLite por projeto
      -> jangada-executar -> jangada-delegar (local | agy | codex-economico)
      -> REVIEW_REQUIRED -> jangada-task ID revisar

(C) Painel Shiny: lê jsonl, SQLite e conversas; não cria nem altera nada.
```

O único elo entre A e B é `jangada-delegar`, chamado pelos dois (F:
`default/orquestracao/executor.py:118`).

### 2.1 Componentes

Estado: **I** implementado, **P** parcial, **A** ausente, **N** não verificável.

| Componente | Responsabilidade | Arquivos e funções | Entradas | Saídas | Estado | Reutilização | Risco principal |
|---|---|---|---|---|---|---|---|
| Painel | Indicadores de consumo, fila, revisão e autonomia | `default/painel/app.R:110-304` (navegação), `indicadores.R`, `coletor.py`, `metricas.py`, `orquestracao.py` | `validar.jsonl`, `delegacoes.jsonl`, `eventos-agentes.jsonl`, conversas do Claude, `tarefas.sqlite` em leitura | Página web local com token (`app.R:308-309`), atualização a cada 3 s (`app.R:371`) | I, só leitura | Alta para indicadores; nula para ações | Não há camada de serviço: o R lê arquivos direto |
| Central de Atividades | Criar, acompanhar e integrar sessões | `default/tarefas/janela.py` (`NovaTarefa.criar` 186-231, `Janela.finalizar` 866), `dados.py`, `central.py` | `agentes/SESSAO.json`, `jangada-agente --capacidades-json` | Chamadas a `jangada-agente` e `jangada-agente-fim` | I para sessões; A para a fila | Média: lógica de dados separada da gráfica em `dados.py` | Catálogo fixo `("claude", "codex")` em `janela.py:24`; cores fixas |
| Projetos | Identificar o projeto de uma tarefa | `cli.py` (pasta de estado por `sha256` do caminho), `JANGADA_PROJETOS` em `config/jangada.conf` | Caminho de pasta | Pasta `agentes/projetos/<sha256>/` | P: projeto é só um caminho | Baixa | Renomear a pasta perde o vínculo com a fila |
| Tarefas | Especificação imutável e ciclo de vida | `default/orquestracao/estado.py:19-25` (estados), `tarefa_valida`, `Estado.importar:162`, `reservar:233`, `finalizar:323`, `alterar:424` | `PLANO.json` | Linhas em `tarefas` e `eventos` (`estado.py:130-136`) | I | Alta | Papéis e capacidades restritos (seção 2.2) |
| Filas | Reserva, dependências, prioridade, tentativas | `estado.py:233-305`, `executor.py:316` | Tarefas `QUEUED` | Transições com evento | I | Alta | Um processo por execução; paralelo de 2 a 4 (`cli.py:108`) |
| Sessões | Trabalho interativo de um agente | `bin/jangada-agente`, `bin/jangada-agentes`, hooks em `bin/jangada-hook-*` | Pedido, perfil, pasta | `agentes/SESSAO.json`, ramo `agente/NOME` | I | Alta | Estados diferentes dos da fila |
| Delegação | Subagente somente leitura | `bin/jangada-delegar` (Ollama em 478, 513, 675-678) | Papel e pedido | Relatório e linha em `delegacoes.jsonl` | I | Média: três destinos no mesmo arquivo | Acrescentar destino exige editar o arquivo de 995 linhas |
| Roteamento | Escolher destino por capacidade | `default/delegacao/roteamento.json`, `jangada_candidatos` (`jangada-config:227`), `preferencias_delegacao` e `candidatos_elegiveis` (`saude.py:232-266`) | Capacidade, perfil, saúde | Lista ordenada de destinos | P: só 3 capacidades e 3 destinos | Média | Listas fechadas em dois idiomas (Bash e Python) |
| Agentes | Executor principal de uma sessão | `default/agentes/*.conf`, `jangada_perfil` (`jangada-config:175`) | Perfil `CHAVE=valor` | Comando da sessão | P: só `claude` e `codex` (`jangada-agente:45`) | Alta: o formato de perfil já existe | Protocolo só chega a esses dois (`jangada-agente:411,422`) |
| Modelos | Escolher o modelo de cada função | `JANGADA_VALIDAR_MODELO`, `JANGADA_LOCAL_MODELO`, `JANGADA_DELEGAR_MODELOS`, `JANGADA_CODEX_*_MODELO` | Variáveis | Argumento do CLI | P: sem catálogo | Baixa | Nomes espalhados por variáveis |
| Provedores | Saúde, cota, pausa e espera | `default/orquestracao/saude.py:16-150` | Resultado das delegações, `agy /usage`, cota do Codex | Tabelas `provedores` e `eventos_provedores` | P: nomes fixos `local`, `agy`, `codex` (`saude.py:75,108,125`) | Alta: é o embrião do registro | Identificador de provedor não é dado, é código |
| Revisores | Parecer independente sobre o diff | `jangada-validar`: `nomear_revisor:253`, `revisar_claude:911`, `revisar_codex:924`, `revisar_agy:947`, `revisar:992` | Diff congelado e pedido de `montar_pedido:533` | `STATUS: APROVADO` ou `REVISAR`, marca em `revisoes/` | I para três CLIs; A para HTTP | Alta | Linha 284 exige binário com o nome do revisor |
| Logs | Registro de eventos | `jangada_anexar_linha:288`, `jangada_registrar_evento:300`, `registrar` em `jangada-validar:115` | Eventos | `validar.jsonl`, `delegacoes.jsonl`, `eventos-agentes.jsonl`, tabela `eventos` | I | Alta | Três formatos sem identificador comum de execução |
| Monitoramento | Recursos da máquina | `bin/jangada-monitor` (abre btop ou htop), conferência de memória no destino local do `jangada-delegar`, `bin/jangada-consumo` | Processos | Terminal | P: sem série histórica nem GPU no painel | Baixa | Modelos locais concorrem por memória sem visão central |
| Persistência | Guardar estado | JSON por sessão, jsonl de registro, SQLite WAL da fila, Parquet do painel | | `~/.local/state/jangada` | I, em quatro formatos | Média | Sem esquema versionado comum |
| Segurança | Conter agente possivelmente hostil | `bin/jangada-isolar`, `revisoes/` fora do isolamento, `jangada_git_blindar:337`, gitleaks em `verificar_local:646` | | | I | Alta | Credenciais de API ainda não têm lugar definido (seção 9) |
| Testes | Verificação estática e funcional | `testes/verificar.sh`, `.github/workflows/verificar.yml` | | "tudo certo" ou contagem de falhas | I | Alta: já usam executores falsos | Abertura de sessão sem teste próprio (I, da auditoria de 03/10) |

### 2.2 Limites fixos no código

Estes pontos impedem hoje um provedor novo sem edição de código. Todos F.

| Onde | O que está fixo |
|---|---|
| `bin/jangada-validar:253-260` | Revisores aceitos: `claude`, `agy`, `codex` |
| `bin/jangada-validar:284` | Revisor precisa ser um executável no `PATH` |
| `bin/jangada-validar:992` | Ordem de reserva entre os mesmos três |
| `bin/jangada-agente:45` | Agentes principais: `claude` e `codex` |
| `bin/jangada-agente:411,422` | Protocolo entregue só por `jangada-codex` ou `--append-system-prompt` |
| `bin/jangada-config:206-251` | `jangada_delegacao`, `jangada_candidatos` e `jangada_revisor` validam contra listas |
| `default/orquestracao/saude.py:75,108,125,239` | Provedores `local`, `agy`, `codex`; destinos `local`, `agy`, `codex-economico` |
| `default/orquestracao/estado.py:280` | Executor principal: `claude` ou `codex` |
| `default/orquestracao/cli.py:131` | `--executor` com as mesmas duas opções |
| `default/orquestracao/executor.py:21` | Capacidades: `leitura_documental`, `resumo_curto`, `analise_documental` |
| `default/orquestracao/executor.py:167,169` | "capacidade ainda sem adaptador de execução" e "executor principal ainda não integrado" |
| `default/tarefas/janela.py:24` | Catálogo de reserva `("claude", "codex")` |
| `bin/jangada-delegar:478-678` | Chamada HTTP só à API própria do Ollama (`/api/chat`), não a `/chat/completions` |

Não existe no repositório nenhuma chamada a `/chat/completions`, nem cliente
da API da OpenAI, da Anthropic, da Moonshot ou do OpenRouter (F: busca por
esses termos em `bin/` e `default/`).

## 3. Fluxos operacionais

### 3.1 Sessão interativa

1. `NovaTarefa.criar` (`janela.py:186`) ou o terminal chamam `jangada-agente`
   com `--projeto`, `--nome`, `--perfil` ou `--agente` e `--prompt`.
2. `jangada-agente` cria o worktree e o ramo, monta o protocolo, grava
   `agentes/SESSAO.json` com `estado: "iniciado"` e uma cópia em `revisoes/`.
3. O agente roda dentro do `jangada-isolar`. Os hooks trocam o estado para
   `ativo`, `aguardando` ou `concluido` e registram a mudança em
   `eventos-agentes.jsonl` (`bin/jangada-hook-claude`).
4. `jangada-validar` congela a entrega, roda `verificar_local` e envia o
   diff ao revisor. Até 3 rodadas, 540 s por rodada.
5. `jangada-agente-fim --integrar` reconfere a aprovação gravada fora do
   isolamento e mescla com `--no-ff`.

### 3.2 Fila

1. `jangada-fila --importar PLANO.json` valida e grava as tarefas. Tarefa
   importada é imutável.
2. `jangada-executar` reserva (`QUEUED` para `RUNNING`), consulta a saúde dos
   provedores e chama `jangada-delegar --json`.
3. Falhas viram `WAITING_QUOTA`, `WAITING_PROVIDER` ou `REVISION_REQUIRED`.
   Sucesso vira `REVIEW_REQUIRED`: a fila nunca se aprova sozinha.
4. `COMPLETED` exige conferência determinística, supervisão independente ou
   revisão humana (`jangada-task ID revisar`).

### 3.3 Estados persistidos

| Origem | Estados |
|---|---|
| Sessão (`dados.py:14-21`) | `iniciado`, `ativo`, `aguardando`, `concluido`, `interrompido` |
| Fila (`estado.py:19-23`) | `QUEUED`, `RUNNING`, `COMPLETED`, `REVIEW_REQUIRED`, `REVISION_REQUIRED`, `WAITING_PROVIDER`, `WAITING_QUOTA`, `WAITING_REVIEWER`, `FAILED`, `CANCELLED`, `PAUSED`, `BLOCKED` |
| Provedor (`saude.py:16`) | `AVAILABLE`, `DEGRADED`, `UNKNOWN`, `UNAVAILABLE`, `COOLDOWN`, `QUOTA_LOW`, `QUOTA_EXHAUSTED`, `AUTH_ERROR`, `RATE_LIMITED`, `NETWORK_ERROR` |

## 4. Modelo conceitual

Entidades pedidas, confrontadas com o que existe.

| Entidade | Existe hoje | Onde | Lacuna |
|---|---|---|---|
| Projeto | Parcial | Caminho de pasta; `sha256` do caminho como chave | Sem registro, nome, metas ou configuração própria |
| Atividade | Ausente | A Central chama de "tarefa" uma sessão | Falta o agrupador de tarefas com objetivo e critério de aceite |
| Tarefa | Sim | Tabela `tarefas` | Não se liga a uma sessão interativa |
| Agente | Parcial | Papéis em `default/claude/agents` e perfis `.conf` | Papel e executor se confundem no nome do perfil |
| Modelo | Parcial | Variáveis de ambiente | Sem catálogo com contexto, custo e capacidades |
| Provedor | Parcial | Tabela `provedores` | Identificadores fixos; sem URL, tipo ou credencial |
| Executor | Parcial | `claude`, `codex`, `agy`, Ollama | Sem contrato comum; CLI e API não são distinguidos |
| Sessão | Sim | `agentes/SESSAO.json` e tmux | Só existe para CLI |
| Execução | Parcial | Tentativa da tarefa, linha de `delegacoes.jsonl`, rodada do validar | Três registros sem identificador comum |
| Revisor | Sim | `jangada-validar` | Só CLI |
| Artefato | Sim | `artefatos/<sha256>.txt` e diff congelado | Só texto na fila |
| Roteador | Parcial | `roteamento.json` e `candidatos_elegiveis` | Só papel leitor, risco até 2, qualidade baixa ou média |

Modelo proposto (I, a validar na Fase 2):

```
Projeto 1-N Atividade 1-N Tarefa 1-N Execução N-1 Executor
                                       |             |
                                       N-1 Sessão    +-- CLI  (claude, codex, agy)
                                       1-N Artefato  +-- API  (Modelo N-1 Provedor)
Tarefa 1-N Revisão N-1 Revisor (Executor em função de revisão)
Roteador: (Tarefa, saúde, política) -> Executor candidato
```

Distinção central: **Executor CLI** recebe uma pasta, usa ferramentas próprias
e altera arquivos; **Executor API** recebe texto e devolve texto, sem acesso a
arquivos. O segundo não substitui o primeiro em tarefas que editam código, e
isso deve ser uma capacidade declarada, não uma suposição.

## 5. Arquitetura multiprovedor proposta

Proposta para discussão. Nada abaixo está implementado.

1. **Registro de provedores em dados.** Arquivo por provedor em
   `default/provedores/` com substituição em `~/.config/jangada/provedores/`,
   no formato `CHAVE=valor` que `jangada_perfil` já lê sem executar. Campos:
   `TIPO` (`cli`, `openai-compat`, `anthropic`, `ollama`), `URL`,
   `CREDENCIAL` (nome de variável ou item do keyring, nunca o valor),
   `MODELOS`, `CAPACIDADES`.
2. **Adaptadores por tipo de protocolo.** Um adaptador por `TIPO`, não por
   marca. OpenAI, Moonshot, OpenRouter e Ollama em `/v1` entram por
   `openai-compat` só depois de teste de contrato; a API da Anthropic tem
   formato próprio e ganha adaptador separado. Compatibilidade é declarada
   por teste, não presumida.
3. **Capacidades declaradas.** `edita_arquivos`, `usa_ferramentas`,
   `saida_estruturada`, `contexto_maximo`, `dados_saem_da_maquina`. O
   roteador filtra por elas.
4. **Sem provedor obrigatório.** As listas fixas da seção 2.2 passam a
   consultar o registro. O padrão continua sendo o que está instalado.
5. **Saúde reaproveitada.** `saude.py` já tem os estados certos; a mudança é
   trocar os conjuntos fixos por leitura do registro.
6. **Roteamento em três modos.** Manual (o usuário escolhe), assistido (o
   sistema sugere e explica), automático supervisionado (o sistema escolhe
   dentro de limites de risco, custo e saída de dados, com registro do
   motivo). Mantêm-se os princípios de `JANGADA_V2_INSTRUCOES.md`: cota
   desconhecida não é cota disponível e não há subida automática para modelo
   mais caro.

## 6. Mapa de estados

| Estado 2.0 | Fila | Sessão | Observação |
|---|---|---|---|
| Planejada | sem equivalente | sem equivalente | Hoje a tarefa só existe depois de importada |
| Pronta | `QUEUED` | sem equivalente | |
| Executando | `RUNNING` | `iniciado`, `ativo` | |
| Em revisão | `REVIEW_REQUIRED`, `WAITING_REVIEWER` | `concluido` sem aprovação | Segunda coluna é I: depende de ler `revisoes/` |
| Concluída | `COMPLETED` | sessão integrada e removida | |
| Bloqueada | `BLOCKED`, `PAUSED`, `WAITING_PROVIDER`, `WAITING_QUOTA` | `aguardando` | O motivo precisa aparecer como subestado |
| Falhou | `FAILED` | `interrompido` | `interrompido` é recuperável; equivalência parcial |
| Cancelada | `CANCELLED` | encerrada sem integrar | |

`REVISION_REQUIRED` não tem estado próprio na lista 2.0: é retorno de "Em
revisão" para "Pronta", com o parecer anexado. Recomenda-se manter os estados
persistidos e criar o mapa como camada de apresentação, sem migração de dados.

## 7. Requisitos de `desac.md`

Fonte: `~/Downloads/desac.md`, fora do repositório.

Decisão posterior do usuário (T9 em `09-decisoes.md`): o Ollama fica como
está. Dos itens abaixo, saem do plano o revisor `ollama` em
`nomear_revisor` e o perfil `default/agentes/local.conf`. O revisor HTTP
genérico (`api`) e o teste com serviço falso foram adiados (T12).

| Requisito | Estado | Evidência |
|---|---|---|
| `revisar_api` ou `revisar_http` em `bin/jangada-validar`, com `/chat/completions` | Ausente | Só existem `revisar_claude`, `revisar_codex`, `revisar_agy` (911, 924, 947) |
| `JANGADA_VALIDAR_API_URL` e `JANGADA_VALIDAR_API_KEY` | Ausente | Sem ocorrência no repositório |
| `JANGADA_VALIDAR_MODELO` e `--modelo` | Implementado | `jangada-validar:15,46` |
| Revisores `ollama` e `api` em `nomear_revisor` | Ausente | `jangada-validar:253-260` |
| `bin/jangada-agente` aceita qualquer perfil com `COMANDO` executável | Parcial | Perfis já são lidos como dados, mas `principais=(claude codex)` (linha 45) filtra o catálogo e o protocolo só chega a dois CLIs |
| `default/agentes/local.conf` | Ausente | Arquivo não existe |
| Teste com serviço falso em `testes/` | Ausente | `testes/validar.sh` usa CLIs falsos, não HTTP |
| `testes/verificar.sh` sem falhas | Ver `10-progresso.md` | Resultado da execução desta fase |

### Plano de implementação (fase posterior)

1. `revisar_http` em `jangada-validar`: corpo JSON montado com `jq` (mensagem
   de sistema e o pedido de `montar_pedido`), enviado com `curl` a
   `$JANGADA_VALIDAR_API_URL/chat/completions`, resposta em `$saida.tmp`.
   A chave vai por arquivo de cabeçalho de modo `0600` ou por entrada padrão
   do `curl`, nunca na linha de comando, que aparece em `ps`.
2. Erros tratados um a um: URL ausente, conexão recusada, tempo esgotado
   (reusa `JANGADA_VALIDAR_PRAZO`), HTTP 401 e 403, 429, 5xx, corpo que não é
   JSON, `choices` vazio, texto sem linha `STATUS:`. Nenhum deles vira
   aprovação: falha do revisor mantém o código de saída 4 atual.
3. `nomear_revisor` aceita `api`. O atalho `ollama` saiu do plano (T9).
   A conferência da linha 284 passa a valer só para revisor CLI.
4. A marca `.aprovado` já registra `reviewer`, `model` e `independent`
   (`jangada-validar:1069-1080`). Revisor HTTP com o mesmo modelo do autor
   continua não independente.
5. `jangada-agente`: trocar a lista `principais` por "todo perfil cujo
   `COMANDO` existe". Isso não inclui `ollama run`: ele não lê o protocolo nem
   edita arquivos, e o Ollama não vira agente de sessão (T9).
6. `default/agentes/local.conf`: saiu do plano (T9).
7. `testes/revisor-http.sh`: servidor falso em Python (`http.server`, porta
   efêmera em `127.0.0.1`) com respostas de sucesso, 401, 500, corpo inválido
   e atraso; entra em `testes/verificar.sh`.

Ressalva de segurança (I): o diff sai da máquina quando a URL não é local. O
padrão `http://localhost:11434/v1` é seguro; URL remota deve exigir
consentimento explícito na configuração, e o registro deve dizer para onde o
diff foi.

## 8. Painel 2.0

| Seção pedida | Fonte de dados que já existe | Lacuna |
|---|---|---|
| Visão Geral | Aba "Hoje" (`app.R:114`, `hoje.R`) | Juntar sessões e fila |
| Projetos | Pastas em `agentes/projetos/`, `JANGADA_PROJETOS` | Entidade Projeto |
| Central de Atividades | Central Qt (sessões) e aba "Fila e provedores" (`app.R:118`) | Unificar; ações de escrita |
| Central de Agentes | `jangada-agente --capacidades-json`, perfis | Catálogo com capacidades |
| Modelos e Provedores | Tabela `provedores`, aba "Consumo de modelos" (`app.R:171`) | Registro de provedores e preços |
| Central de Revisão | `validar.jsonl`, `revisoes/`, aba "Revisão e síntese" (`app.R:147`) | Ler pareceres e decidir pela interface |
| Monitoramento | `jangada-monitor`, memória no destino local | Coletor de CPU, memória e GPU |
| Histórico e Artefatos | `eventos`, `artefatos/`, `eventos-agentes.jsonl` | Navegação por tarefa |
| Configurações | `config/jangada.conf` | Edição validada, sem expor chave |

O painel atual não executa ações. Qualquer ação de escrita pela web amplia a
superfície de ataque: hoje o token protege leitura; passará a proteger
abertura de agentes e integração de código. A Central Qt já faz essas ações
por chamada direta a `bin/`, com confirmação por SHA (`jangada-agente-fim
--confirmacao`).

### 8.1 Comparação preliminar de interface

Pesos e notas são I. Nota de 1 a 5. Esta é a comparação preliminar; a
revista, com a decisão, está em `04-interface.md`.

| Critério | Peso | Shiny evoluído | Híbrido | React | Vue |
|---|---|---|---|---|---|
| Reuso dos indicadores em R (cerca de 1.760 linhas) | 20 | 5 | 4 | 1 | 1 |
| Ações com estado e atualização ao vivo | 20 | 2 | 4 | 5 | 5 |
| Instalação repetível por `pacman`, sem etapa de compilação web | 15 | 5 | 4 | 2 | 3 |
| Manutenção por uma pessoa, em linguagens já do projeto | 15 | 4 | 4 | 2 | 3 |
| Superfície de ataque e cadeia de dependências | 15 | 4 | 4 | 2 | 2 |
| Acessibilidade e tema claro e escuro | 10 | 3 | 4 | 4 | 4 |
| Testes automáticos na suíte atual | 5 | 3 | 4 | 3 | 3 |
| **Total ponderado (máximo 500)** | 100 | **380** | **400** | **265** | **295** |

"Híbrido" aqui: serviço local em Python que expõe estado e ações, Shiny
mantido para os indicadores, e telas de operação em HTML servido pelo mesmo
serviço. A Central Qt é uma quinta opção de fato para as telas de operação e
deve entrar na comparação da Fase 2.

## 9. Segurança

Fatos:

- Isolamento contra escrita com bubblewrap; rede e leitura permitidas por
  padrão (`jangada-isolar:21-22`).
- Variáveis de credencial conhecidas são removidas do ambiente
  (`jangada-isolar:507-527`).
- Perfil `verificacao` roda sem rede e sem credenciais de provedor
  (`jangada-isolar:39-42`).
- Aprovação que vale fica em `revisoes/`, oculta ao agente.
- Token do painel fica oculto ao agente.
- `verificar_local` procura segredos com gitleaks.

Lacunas para a 2.0 (I):

1. Chaves de API não têm lugar definido. Proposta: keyring, ou arquivo `0600`
   em `~/.config/jangada/` incluído em `JANGADA_ISOLAR_OCULTAR`; no perfil
   guarda-se só o nome da referência.
2. `JANGADA_VALIDAR_API_KEY` precisa entrar na lista de variáveis removidas
   pelo isolamento, para o agente autor não ler a chave do revisor.
3. Revisor HTTP roda fora do isolamento do autor; a chamada não pode ser
   feita de dentro da sessão isolada com a chave à mostra.
4. Saída de dados: todo executor remoto recebe diff ou documento. Falta um
   campo `dados_saem_da_maquina` e uma política por projeto.
5. Painel com ações precisa de proteção contra requisição forjada além do
   token na URL.

## 10. Testes

- `testes/verificar.sh` roda sintaxe Bash, shellcheck, Lua, JSON, TOML, QML,
  regra 1 e 40 roteiros funcionais.
- A integração contínua usa contêiner Arch em dois ambientes (fixo por digest
  e atual) e um segundo trabalho com R e lintr
  (`.github/workflows/verificar.yml`).
- Os testes de revisão e delegação usam executores falsos, sem chamada paga.
- Não há teste de cliente HTTP genérico, de interface web com ações, nem de
  acessibilidade.

O resultado da execução feita nesta fase está em `10-progresso.md`.

## 11. Projetos complexos

Hoje (F): dependências entre tarefas com detecção de ciclo
(`Estado.importar`), prioridade em cinco níveis com propagação, paralelismo
de 2 a 4, limite de tentativas e de tempo por tarefa. Falta (I): decomposição
de uma atividade em tarefas pela interface, tarefas que editam código na
fila (linha 169 do executor), orçamento por projeto, e visão de grafo. O
painel já usa `visNetwork` e `igraph`, que servem para o grafo.

## 12. Riscos

| Nº | Risco | Prioridade | Mitigação |
|---|---|---|---|
| R1 | Tratar toda API HTTP como compatível com `/chat/completions` | Alta | Adaptador por tipo e teste de contrato por provedor |
| R2 | Chave de API em registro, `ps`, diff ou ambiente do agente | Alta | Referência em vez de valor; cabeçalho por arquivo; variável removida no isolamento |
| R3 | Diff enviado a serviço remoto sem consentimento | Alta | Padrão local; consentimento por provedor; destino no registro |
| R4 | Executor de API escalado para tarefa que edita arquivos | Alta | Capacidade `edita_arquivos` obrigatória no roteador |
| R5 | Ações de escrita no painel web | Eliminado | Decisão T10: o painel é só Shiny e só lê |
| R6 | Regressão nos três revisores atuais ao generalizar | Média | Manter `testes/validar.sh` inteiro; trocar listas por registro em passos separados |
| R7 | Dois modelos de estado (sessão e fila) divergirem mais | Média | Mapa de apresentação antes de qualquer unificação de dados |
| R8 | Cópias instaladas quebrarem sem migração | Média | Uma migração por mudança de comportamento (regra 5) |
| R9 | Revisor local fraco aprovar entrega ruim | Média | Registrar modelo na marca; política mínima de revisor por risco |
| R10 | Cadeia de dependências web contrariar a regra 2 | Média | Preferir o que o `pacman` instala; decidir na Fase 2 |
| R11 | Perda da identidade ao trocar de interface | Baixa | Fichas de `03-identidade-visual.md` como contrato |

## 13. Plano em sete fases

Fases como definidas no pedido. Revisto na Fase 2: a primeira versão desta
tabela usava uma divisão diferente.

| Fase | Entrega | Depende de | Critério de aceite | Risco | Reversão |
|---|---|---|---|---|---|
| 1 Diagnóstico | Documentos 00, 01, 03, 09, 10 | | Aprovação do usuário | | Apagar `docs/evolucao-2.0/` |
| 2 Proposta arquitetural e decisão de interface | `02-arquitetura.md`, `04-interface.md` | 1 | Decisões de `09-decisoes.md` confirmadas | R1, R10 | Só documentos |
| 3 Desacoplamento e adaptadores | Registro de provedores com os quatro atuais e adaptador `cli`. Provedores por API e revisor HTTP adiados (T12) | 2 | Provedor de linha de comando novo sem editar código; `testes/verificar.sh` sem falhas; revisores atuais intactos | R1, R2, R3, R6, R8 | Registro padrão reproduz o comportamento atual; reverter os commits |
| 4 Modelo operacional | Projeto, Atividade, Execução, política por projeto, núcleo de ações, roteamento em três modos | 3 | Sessão e fila na mesma consulta; toda ação passa pelos comandos de `bin/` | R4, R7, R9 | Tabelas e arquivos novos, sem migrar os antigos |
| 5 Reformulação visual | Abas novas no Shiny (só leitura), fichas de cor no painel e na Central Qt | 4 | Critérios da seção 6 de `04-interface.md` | R11 | Painel atual e Central mantidos |
| 6 Integração e monitoramento | Coletor de recursos, Central Qt sobre o núcleo, indicadores com `execucoes` | 5 | Medição separada de estimativa; coleta só sob demanda | R7 | Desligar o coletor; indicadores antigos seguem |
| 7 Testes e validação | Testes de contrato com os provedores atuais (T11), de somente leitura do painel e de ponta a ponta; migrações conferidas | 3 a 6 | Suíte e integração contínua sem falhas; roteiro completo pela Central Qt e pelo terminal | R6, R8 | Não altera comportamento |

Cada fase traz seus próprios testes; a Fase 7 fecha o que cruza fases.

## 14. Limitações desta análise

- N: `default/orquestracao/principal.py`, `supervisao.py`, `cota_codex.py`,
  `acompanhamento.py`, `metricas_projeto.py` e `default/painel/subagentes.py`
  foram lidos só em estrutura.
- N: `install/`, `migrations/`, `shell/` e os hooks do agy e do Codex foram
  apenas listados.
- N: painel e Central não foram abertos em tela; a descrição vem do código.
- N: nenhum provedor externo foi chamado; capacidades de APIs de terceiros
  não foram testadas.
- Contagens de uso citadas em `estudos/auditoria-as-is-2026-10-03.md` não
  foram refeitas.
