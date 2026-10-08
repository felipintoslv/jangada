# Proposta de arquitetura

Fase 2. Proposta para aprovação; nada aqui está implementado. Parte do
diagnóstico em `01-diagnostico.md` e usa a mesma marcação: **F** fato lido no
código, **I** inferência, **N** não verificado.

## 1. Princípios

1. **Aditivo.** Nenhuma tabela, arquivo de estado ou comando atual muda de
   formato. O que é novo entra ao lado, com `CREATE TABLE IF NOT EXISTS`,
   como `estado.py:130` já faz.
2. **Dados no lugar de listas.** Os 13 pontos fixos da seção 2.2 do
   diagnóstico passam a consultar um registro.
3. **Uma porta para ações.** Terminal e Central Qt chamam o mesmo núcleo. A
   interface não tem regra própria. O painel Shiny só lê.
4. **Compatibilidade é provada.** Um provedor só é tratado como compatível
   com um protocolo depois de passar no teste de contrato desse protocolo.
5. **Padrão local.** Sem configuração, nada sai da máquina além do que já
   sai hoje.
6. **Quem executa não aprova.** Regra já vigente na fila (`executor.py`
   termina em `REVIEW_REQUIRED`) e no `jangada-validar` (campo
   `independent` da marca).
7. **O Ollama fica como está.** Decisão do usuário em 07/10/2026 (T9 em
   `09-decisoes.md`): nem mais nem menos do que o configurado hoje.

### 1.1 O que "como está" quer dizer para o Ollama

Usos que existem hoje e continuam, com o mesmo código:

| Uso | Onde | Como |
|---|---|---|
| Delegação local, papéis leitor e redator | `bin/jangada-delegar:166,477-678` | `/api/tags`, `/api/ps` e `/api/chat`; fatiamento, conferência de memória e temperatura zero no leitor |
| Conversa de Pescador | `bin/jangada-conversa`, `default/conversa/janela.py` | Janela Qt com `/api/chat` |
| Saúde do provedor | `default/orquestracao/saude.py:156-163` | `/api/tags` e presença do modelo |
| Avaliação do modelo local | `bin/jangada-avaliar-ollama`, `default/delegacao/avaliar_ollama.py` | Sob pedido |

Configuração que continua valendo, sem chave nova: `JANGADA_LOCAL_MODELO`
(`qwen3:4b`), `JANGADA_LOCAL_CTX`, `JANGADA_LOCAL_VRAM_MIN`,
`JANGADA_LOCAL_KEEP_ALIVE`, `JANGADA_LOCAL_ESPERA`,
`JANGADA_LOCAL_FATIAS_MAX`, `JANGADA_OLLAMA_URL` e `JANGADA_CONVERSA_CTX`
(`bin/jangada-config:59-66,80`).

O que a 2.0 não dá ao Ollama:

- Não vira agente de sessão: não há perfil `local.conf` com `ollama run`.
- Não vira revisor do `jangada-validar`: não há atalho `ollama` em
  `nomear_revisor`.
- Não emite parecer de supervisão, o que o protocolo já proíbe
  (`default/agentes/protocolo-delegar-codex.md:16`).
- Não entra em roteamento automático para papéis além de leitor e redator.

O registro de provedores descreve o Ollama para as telas, só para leitura.
O código da delegação local não é extraído nem reescrito.

### 1.2 Escopo decidido pelo usuário

Decisões T10 a T13 de `09-decisoes.md`, de 07/10/2026:

| Parte desta proposta | Situação |
|---|---|
| Registro de provedores com `claude`, `codex`, `agy` e `ollama` | Entra na Fase 3 |
| Adaptador `cli` | Entra na Fase 3 |
| Adaptadores `openai-compat` e `anthropic`, revisor HTTP | Adiados, sem data |
| Credenciais de API e `CONSENTIMENTO` para URL remota | Adiados com os adaptadores |
| Serviço web | Descartado: o painel é só Shiny e só lê |

O texto das seções 4 a 7 e 11 sobre provedor por API fica como referência
de desenho. Nada dele é implementado sem nova decisão.

## 2. Camadas

```
Interfaces      terminal (bin/jangada-*)   Central Qt        painel Shiny
                        |                      |                  |
Núcleo          ações e consultas (Python, default/nucleo/)   | só consultas
                        |
Domínio         fila (estado.py)  sessões (jangada-agente)  revisão (jangada-validar)
                        |
Roteador        capacidades + saúde + política -> executor candidato
                        |
Adaptadores     cli        ollama        openai-compat        anthropic
                        |
Registro        provedores/*.conf   modelos.json   precos.json   agentes/*.conf
```

O núcleo é novo. As demais camadas existem e são reorganizadas, não
reescritas.

## 3. Entidades e contratos

| Entidade | Identificador | Onde persiste | Novo ou existente |
|---|---|---|---|
| Projeto | `sha256` do caminho resolvido (já usado em `cli.py`) | `agentes/projetos/<sha>/projeto.json` | Arquivo novo; chave existente |
| Atividade | `atv-` mais 12 hexadecimais | Tabela nova `atividades` no `tarefas.sqlite` do projeto | Nova |
| Tarefa | Campo `id` da especificação | Tabela `tarefas` | Existente |
| Agente | Nome do perfil | `default/agentes/*.conf` e `~/.config/jangada/agentes/*.conf` | Existente, com chaves novas opcionais |
| Modelo | `provedor/modelo` | `modelos.json` | Novo |
| Provedor | Nome do arquivo, `[a-z0-9][a-z0-9-]{0,31}` | `default/provedores/*.conf` e `~/.config/jangada/provedores/*.conf` | Novo |
| Executor | `provedor` mais tipo de adaptador | Derivado do registro | Novo como conceito |
| Sessão | Nome da sessão tmux | `agentes/SESSAO.json` | Existente |
| Execução | `exe-` mais 16 hexadecimais | Tabela nova `execucoes` | Nova; hoje são três registros soltos |
| Revisor | Agente em função de revisão | Marca em `revisoes/` e `validar.jsonl` | Existente |
| Artefato | `sha256` do conteúdo | `artefatos/<sha>.txt` | Existente |
| Roteador | Sem estado próprio | Decisão gravada na Execução | Existente em parte |

Não se cria entidade para "fila" nem para "instância de agente": a fila é
a tabela `tarefas` e a instância é a Sessão ou a Execução.

### 3.1 Projeto

`projeto.json`: `id`, `caminho`, `nome`, `criado`, `politica` (ver 7.3).
Resolve o risco de perder o vínculo ao renomear a pasta: um comando de
reassociação troca `caminho` e move a pasta de estado. Sem o arquivo, o
projeto continua valendo pelo caminho, como hoje.

### 3.2 Atividade

Tabela `atividades(id, titulo, objetivo, criterios, criado, atualizado)`.
A ligação com a tarefa vai num campo opcional `atividade` da especificação.
`tarefa_valida` não recusa campos a mais (F: `estado.py:31-82` só confere os
que conhece), então tarefas antigas e novas convivem. A Sessão ganha a chave
opcional `atividade` no JSON.

O estado da Atividade é calculado a partir das tarefas e sessões, não
gravado.

### 3.3 Tarefa

Campos novos, todos opcionais: `atividade`, `criterios_aceite` (lista de
frases conferíveis), `entradas`, `saidas`, `contexto` (caminhos mínimos a
ler). `requisitos` e `fontes` continuam como estão. A tarefa continua
imutável depois de importada.

### 3.4 Agente, modelo e provedor

Hoje o perfil junta tudo: `COMANDO` é o executor, e o nome do arquivo
(`claude-agy`) carrega o revisor. A proposta separa em quatro coisas:

| Conceito | O que define | Exemplo |
|---|---|---|
| Perfil de agente | Função, permissões, ferramentas, protocolo | "revisor", somente leitura |
| Modelo | Quem processa | `ollama/qwen3:4b` |
| Provedor | Quem entrega o modelo | `ollama` em `localhost` |
| Instância | Uma Sessão ou Execução com as três escolhas resolvidas | `exe-…` |

Chaves novas e opcionais no perfil: `FUNCAO`, `EXECUTOR`, `MODELO`,
`PERMISSOES`. As atuais (`COMANDO`, `ARGS`, `DESCRICAO`,
`JANGADA_VALIDAR_REVISOR`, `JANGADA_DELEGAR`) continuam valendo, e um perfil
sem as novas se comporta como hoje.

Atenção (F): `jangada_perfil` põe toda chave desconhecida no ambiente do
agente (`jangada-config:187-191`, `PERFIL_AMBIENTE`). Uma chave de API
escrita num perfil chegaria ao agente. Por isso credencial nunca vai no
perfil, e o registro de provedores tem leitor próprio.

### 3.5 Execução

Tabela `execucoes`, uma linha por tentativa:

| Campo | Origem |
|---|---|
| `id` | Gerado na reserva |
| `tarefa`, `sessao`, `atividade` | Um dos dois primeiros é obrigatório |
| `funcao` | `execucao`, `revisao`, `supervisao`, `delegacao` |
| `agente`, `provedor`, `modelo` | Resolvidos pelo roteador |
| `inicio`, `fim`, `status` | |
| `chamadas`, `tokens_entrada`, `tokens_saida`, `segundos` | Medidos; `NULL` quando não medidos |
| `motivo_codigo` | Mesmo vocabulário do `jangada-delegar` |
| `roteamento` | Candidatos considerados e motivo da escolha |
| `destino_dados` | `local` ou a URL de destino, sem credencial |

Os três registros atuais (`eventos`, `delegacoes.jsonl`, `validar.jsonl`)
continuam sendo gravados e ganham o campo `execucao` com esse identificador.
O `jangada-delegar` já gera `id` e `roteamento_id` por pedido (F: argumentos
do `jq` em `registrar`, `jangada-delegar:173`).

### 3.6 Contrato do executor

Generaliza o que `default/delegacao/codex.py` já devolve a
`executar_principal` (F: `principal.py`, conferência do registro devolvido).

Entrada: `pedido`, `sistema`, `fontes`, `tempo`, `modelo`, `execucao`.

Saída, em JSON:

```json
{"execucao": "exe-…", "provedor": "…", "modelo": "…",
 "chamadas": 1, "tokens_entrada": null, "tokens_saida": null,
 "segundos": 12, "motivo_codigo": "", "texto": "…"}
```

Regras, já praticadas no código atual:

- Número não medido é `null`, nunca zero.
- `motivo_codigo` preenchido significa recusa ou falha; nesse caso `texto`
  não é usado.
- O executor não escreve estado. Quem grava é o núcleo.

Capacidades declaradas por executor:

| Capacidade | CLI (`claude`, `codex`) | `ollama`, `openai-compat`, `anthropic` |
|---|---|---|
| `edita_arquivos` | sim | não |
| `usa_ferramentas` | sim | não, nesta proposta |
| `le_pasta` | sim | não: recebe só o texto enviado |
| `sessao_interativa` | sim | não |
| `dados_saem_da_maquina` | sim | depende da URL |

Consequência: executor de API serve para revisão, supervisão, leitura
documental e síntese. Tarefa que edita código exige CLI. O roteador recusa a
combinação, em vez de tentar.

## 4. Registro de provedores

Um arquivo por provedor, formato `CHAVE=valor`, lido sem executar, por uma
função nova `jangada_provedor` que não exporta nada para o ambiente.

| Chave | Valores | Observação |
|---|---|---|
| `TIPO` | `cli`, `ollama`, `openai-compat`, `anthropic` | Escolhe o adaptador |
| `EXECUCAO` | `cli`, `local`, `remota` | Diferencia os três modos pedidos |
| `URL` | Endereço base | Vazio para `cli` |
| `COMANDO` | Executável | Só para `cli` |
| `AUTENTICACAO` | `nenhuma`, `keyring:ATRIBUTOS`, `arquivo:CAMINHO` | Nunca o valor da chave |
| `MODELOS` | Lista ou `descobrir` | `descobrir` consulta o provedor |
| `LIMITE_CONTEXTO`, `LIMITE_SAIDA`, `PRAZO` | Números | Declarados pelo usuário |
| `CONSENTIMENTO` | `nao`, `sim` | Obrigatório `sim` quando `EXECUCAO=remota` |
| `CONTRATO` | Data e resultado do último teste de contrato | Gravado pelo teste, não pelo usuário |

Provedores que vêm no repositório: `claude`, `codex`, `agy` (tipo `cli`) e
`ollama` (tipo `ollama`). Eles reproduzem o comportamento atual; o do
Ollama é só descritivo (seção 1.1). OpenAI,
Anthropic por API, Moonshot e OpenRouter não vêm cadastrados: o usuário
cria o arquivo. Nenhum é obrigatório, inclusive os quatro padrão.

### 4.1 Modelos

`modelos.json`, por `provedor/modelo`: `contexto`, `saida_maxima`,
`ferramentas`, `modalidades`, `origem` de cada dado (`declarado`,
`descoberto`, `medido`). Custo continua em `~/.config/jangada/precos.json`,
no formato que `ler_precos` já valida (F: `metricas_projeto.py:33-52`):
sem o arquivo, nenhum custo é estimado.

Não se versiona tabela de preços nem de capacidades de terceiros: esses
dados mudam e não são verificáveis a partir do repositório.

### 4.2 Disponibilidade configurada e verificada

| Nível | Significado | Fonte |
|---|---|---|
| Configurado | Existe arquivo de provedor válido | Registro |
| Alcançável | Respondeu ao teste de conectividade | `saude.py`, com validade |
| Autenticado | A credencial foi aceita | Idem; falha vira `AUTH_ERROR` |
| Contrato válido | Passou no teste de contrato do tipo | Campo `CONTRATO` |
| Com cota | Cota lida e acima do mínimo | `saude.py`; desconhecida vira `UNKNOWN` |

Os estados de `saude.py:16` já cobrem os quatro últimos níveis. A mudança é
trocar os conjuntos fixos (`saude.py:75,108,125,239`) pela lista do
registro.

### 4.3 Teste de conectividade

Sem conteúdo do usuário em nenhum caso:

| Tipo | Teste | Situação |
|---|---|---|
| `cli` | Executável existe e responde à opção de versão | Já feito por `command -v` |
| `ollama` | `GET /api/tags` | Já feito em `jangada-delegar:478` |
| `openai-compat` | Listagem de modelos | N: caminho e formato a confirmar por provedor |
| `anthropic` | Listagem de modelos | N: idem |

O teste de contrato vai além: envia um pedido fixo e sintético ("responda
com a palavra pronto") e confere a forma da resposta. O texto é constante
do repositório, portanto não transmite dado sensível. Consome uma chamada
paga em provedor remoto e só roda a pedido.

## 5. Adaptadores

Um módulo por tipo em `default/adaptadores/`, com a mesma função de entrada
e o contrato da seção 3.6. Em Python, com `urllib` da biblioteca padrão,
sem dependência nova.

| Adaptador | Origem do código | Observação |
|---|---|---|
| `cli` | Extraído de `revisar_claude`, `revisar_codex`, `revisar_agy` e do `jangada-delegar` | Cada CLI mantém seus argumentos num arquivo de dados |
| `ollama` | Fica em `jangada-delegar:477-678`, sem extração | O tipo existe no registro para descrever o provedor; não há módulo novo (seção 1.1) |
| `openai-compat` | Novo | `/chat/completions` |
| `anthropic` | Novo | Formato próprio de mensagens |

O Bash chama o adaptador como hoje chama `default/delegacao/codex.py`: um
processo, pedido pela entrada padrão, JSON na saída.

A credencial é resolvida dentro do adaptador, depois de ele iniciar, e vai
no cabeçalho da requisição. Não passa por argumento, variável exportada nem
registro. O adaptador nunca imprime cabeçalhos nem o corpo de erro inteiro:
só o código HTTP e um `motivo_codigo`.

Erros mapeados para o vocabulário do `jangada-delegar`. Dois códigos são
novos; os demais já existem:

| Situação | `motivo_codigo` | Estado do provedor |
|---|---|---|
| Conexão recusada, DNS | `indisponivel` | `NETWORK_ERROR` |
| Tempo esgotado | `limite_tempo` | `DEGRADED` |
| 401, 403 | `autenticacao` (novo) | `AUTH_ERROR` |
| 429 | `limite_taxa` (novo) | `RATE_LIMITED` |
| 5xx | `indisponivel` | `UNAVAILABLE` |
| Corpo que não é JSON, sem texto | `saida_invalida` | `DEGRADED` |

Três falhas seguidas já levam a `COOLDOWN` por 900 s (F: `saude.observar`).

## 6. Revisão

O `jangada-validar` mantém tudo o que protege a entrega: foto congelada,
`verificar_local`, limite de rodadas, marca fora do isolamento. Mudam dois
pontos:

1. `revisar()` deixa de ter três funções fixas e chama o adaptador do
   provedor do revisor. `revisar_http` de `desac.md` é o caminho
   `openai-compat`. O Ollama não é revisor (seção 1.1).
2. `nomear_revisor` aceita qualquer provedor do registro que declare a
   função de revisão. O provedor `ollama` não declara.

Regras que continuam:

- Revisor com o mesmo modelo do autor grava `independent: false`.
- Falha do revisor nunca vira aprovação.
- A ordem de reserva só inclui provedores com `CONSENTIMENTO=sim` quando
  remotos, e nunca sobe de custo sem pedido (ver 7.2).

Revisor por API não lê o repositório: recebe o diff e o pedido de
`montar_pedido`. Hoje `revisar_claude` tem `Read`, `Grep` e `Glob`. Essa
diferença é registrada na marca como `contexto: "diff"` ou
`contexto: "repositorio"`, para a política de revisão poder exigir um ou
outro por nível de risco.

Parecer estruturado: a fila já valida um parecer em JSON com critérios,
resultado e justificativa (F: `supervisao.py`, `parecer_valido`). A proposta
é usar a mesma forma para a revisão de tarefas da fila, com um critério por
item de `criterios_aceite`.

## 7. Roteamento

### 7.1 Entradas da decisão

| Fator | Fonte | Situação |
|---|---|---|
| Capacidades e ferramentas | Registro e seção 3.6 | Declarado |
| Risco e qualidade | Especificação da tarefa | Existe |
| Disponibilidade e cota | `saude.py` | Existe |
| Latência | Mediana de `segundos` em `execucoes` | Medida, por provedor e modelo |
| Custo | `precos.json` vezes tokens medidos | Estimativa; ausente sem o arquivo |
| Memória e GPU | Conferência do destino local | Existe só para o Ollama |
| Limite de contexto | `modelos.json` | Declarado |
| Confidencialidade | Política do projeto | Nova |
| Histórico | Taxa de aprovação em primeira rodada por modelo e tipo de tarefa | Medida; exibida com tamanho da amostra |

Não há nota fixa de modelo. A ordem entre candidatos elegíveis vem de
`roteamento.json`, que já é configurável, e de medidas com amostra visível.

### 7.2 Modos

| Modo | Quem escolhe | Limites |
|---|---|---|
| Manual | O usuário | Só a conferência de capacidades |
| Assistido | O sistema lista os candidatos elegíveis com o motivo; o usuário confirma | Idem |
| Automático supervisionado | O sistema, dentro da política | Só para risco e qualidade que a política liberar; hoje risco até 2 e qualidade baixa ou média (F: `candidatos_elegiveis`, `saude.py:247`) |

O padrão é manual para sessões e o comportamento atual para a fila.

Reserva entre provedores só acontece quando o outro candidato: declara as
mesmas capacidades, tem consentimento se for remoto, não custa mais que o
primeiro, e cabe no orçamento. Falha local não envia à nuvem, como hoje.

### 7.3 Política por projeto

Em `projeto.json`:

- `dados`: `local` (nada sai) ou `remoto_permitido` com a lista de
  provedores aceitos.
- `orcamento`: teto de chamadas e de custo estimado por período.
- `revisao_minima`: por faixa de risco, se o revisor precisa ser
  independente e se precisa ler o repositório.

Sem política, vale `dados: local` para provedores de API e o comportamento
atual para os CLIs já configurados.

### 7.4 Fluxo com vários agentes

Planejamento, execução, testes, revisão e documentação são tarefas com
`dependencias`, cada uma com seu agente. A fila já ordena por dependência e
detecta ciclo. Cada etapa grava artefato e Execução. A revisão é uma tarefa
cujo agente não pode ter o mesmo modelo do autor da tarefa revisada.

## 8. Estados

Os persistidos não mudam. Os oito estados da 2.0 são uma visão calculada
(mapa na seção 6 do diagnóstico). Transições válidas, todas já impostas
pelo código (F: `estado.py:424-442`, `reservar`, `finalizar`):

| De | Para | Como |
|---|---|---|
| Planejada | Pronta | Importar o plano |
| Pronta | Executando | Reserva |
| Executando | Em revisão | Fim com sucesso |
| Executando | Bloqueada | Cota, provedor ou revisor indisponível |
| Executando | Em revisão, com pendência | Falha ou reserva vencida vira `REVISION_REQUIRED` |
| Executando | Falhou | Limite de tentativas |
| Em revisão | Concluída | Parecer de aprovação |
| Em revisão | Pronta | `repetir`, só a partir de `REVISION_REQUIRED` |
| Bloqueada | Pronta | `retomar` |
| Pronta, Bloqueada | Cancelada | `cancelar` |

Regras que a interface herda e não pode contornar: não se cancela nem se
pausa tarefa em execução; não se pausa tarefa à espera de conferência;
estado final não muda.

"Planejada" é o único estado sem persistência: fica no arquivo de plano da
Atividade até ser importado.

## 9. Núcleo de ações

Biblioteca Python em `default/nucleo/`, com duas faces:

- **Consultas:** projetos, atividades, tarefas, sessões, execuções,
  provedores, revisões. Leem SQLite em modo somente leitura e os JSON de
  sessão, como `default/painel/orquestracao.py` e `default/tarefas/dados.py`
  já fazem.
- **Ações:** uma função por ação, e cada uma chama o comando de `bin/` que
  já existe (`jangada-agente`, `jangada-task`, `jangada-agente-fim`,
  `jangada-provedor`). O núcleo não reimplementa regra.

Ações que integram, encerram ou cancelam exigem a mesma confirmação que
`jangada-agente-fim --confirmacao BASE CANDIDATO` já exige: os dois SHA
completos, reconferidos sob trava.

Não há serviço web: o painel Shiny usa só as consultas (ver
`04-interface.md`).

## 10. Monitoramento

| Medida | Fonte | Tipo |
|---|---|---|
| CPU, memória | `/proc` | Medição |
| GPU e memória de vídeo | Ferramenta do fabricante, quando instalada | Medição; ausente sem a ferramenta |
| Modelos carregados | `GET /api/ps` do Ollama (já em `jangada-delegar:513`) | Medição |
| Tempo por execução | `execucoes.segundos` | Medição |
| Tokens | Resposta do provedor | Medição quando informada; `NULL` se não |
| Custo | `precos.json` | Estimativa, sempre rotulada |
| Erros | `motivo_codigo` e estados de provedor | Medição |

Coleta sob demanda: só quando a tela de monitoramento está aberta ou uma
execução local está ativa, com intervalo mínimo de 5 s. Sem serviço
permanente.

## 11. Segurança

| Tema | Decisão proposta |
|---|---|
| Credenciais | Keyring ou arquivo `0600` fora do repositório, em pasta incluída em `JANGADA_ISOLAR_OCULTAR`. Registro guarda só a referência |
| Ambiente do agente | Variáveis de chave de provedor entram na lista removida pelo `jangada-isolar` (`jangada-isolar:507-527`) |
| Onde roda o adaptador remoto | A credencial fica oculta dentro do isolamento, então a chamada a provedor de API com chave só funciona fora dele. A aprovação que vale já é a feita fora (`jangada-validar:38,71`; `jangada-agente-fim`) |
| Registros | Sem cabeçalhos, sem chave, sem corpo de erro bruto; `destino_dados` sem credencial |
| Saída de dados | `CONSENTIMENTO=sim` por provedor mais política do projeto. Sem os dois, recusa |
| Isolamento entre projetos | Estado por `sha256` do caminho, como hoje; o núcleo recebe o projeto e não aceita caminho de artefato vindo da interface |
| Concorrência | Travas atuais (`jangada_com_trava_dir`, reserva com dono e prazo) |
| Reversão | Ramo `agente/NOME` mantido após encerrar; função `reverter` de `shell/jangada-shell.sh` |
| Operações destrutivas | Confirmação por SHA; nunca por um clique só |

## 12. Projetos complexos

Uma Atividade de auditoria, refatoração ou análise vira um plano de tarefas
com `objetivo`, `contexto` (caminhos mínimos), `entradas`, `saidas`,
`dependencias`, `criterios_aceite` e agente. Para não reler o repositório:

- cada tarefa declara `fontes` e `contexto`; o executor recebe só isso;
- o resultado de uma tarefa entra como fonte da seguinte pelo artefato, não
  pela conversa (a fila já faz isso em `contexto_principal`);
- `jangada-mapa` dá a estrutura sem leitura integral;
- o estado da Atividade em `docs/` ou no artefato final permite retomar em
  outra sessão.

## 13. O que cada fase seguinte implementa

| Fase | Parte desta proposta |
|---|---|
| 3 | Seções 4, 5 e 6; itens de `desac.md` |
| 4 | Seções 3, 7, 8 e 9 |
| 5 | `04-interface.md` e `03-identidade-visual.md` |
| 6 | Seção 10 e a ligação do painel ao núcleo |
| 7 | Testes de contrato, de segurança e de ponta a ponta |

## 14. Pontos não verificados

- N: formato exato da listagem de modelos e das respostas de erro de cada
  provedor remoto. A proposta trata isso com teste de contrato, não com
  suposição.
- N: se o keyring atende ao uso sem sessão gráfica.
- N: desempenho do SQLite com a tabela `execucoes` em uso paralelo; o banco
  já roda em modo WAL.
- I: a extração do adaptador `cli` do Bash para Python é a
  mudança de maior risco de regressão; deve ser feita com os testes atuais
  intactos, um provedor por vez.
