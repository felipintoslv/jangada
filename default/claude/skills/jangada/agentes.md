# Camada de agentes

## Codex

O `account/rateLimits/read` separa limites por grupo de consumo. Para a cota
Codex, use `rateLimitsByLimitId.codex` quando o mapa estiver presente;
`rateLimits` é a forma antiga. Considere a janela com menor saldo, não
presuma renovação quando `resetsAt` passar nem cota separada por modelo.
`jangada-router status --atualizar-codex --permitir-remoto` consulta esses
metadados sem iniciar conversa; exige autenticação existente e não habilita
delegação ao Codex.

O Codex CLI 0.159.3 dispara `SessionStart` no primeiro turno, não apenas em
`thread/start`. Os testes com o CLI real usam um provedor restrito a
localhost para iniciar o turno sem consumir tokens externos. A confiança
dos hooks preserva `enabled=false`: aprovar um hook não deve reativá-lo.

A aprovação dos hooks no `/hooks` tenta gravar `config.toml`, que está
somente leitura. O adaptador consulta os hashes das definições em
`hooks/list`, pede autorização dos oito hooks da Jangada no início e
guarda a escolha em `jangada-hooks-confianca.json`. A tabela `hooks.state`
vai na chamada; outros hooks mantêm a própria verificação de confiança.
O sinal à Waybar precisa vir de fora do namespace de PID: o
`jangada-isolar` observa o arquivo da sessão com `inotifywait` e sinaliza
a barra no host. O `pkill` executado dentro do isolamento não a enxerga.

A confiança da pasta precisa ser resolvida antes de abrir o CLI: ele tenta
salvá-la em `config.toml`, que o isolamento monta somente leitura.
O adaptador pergunta no início e salva a escolha em
`jangada-confianca.json` nos dados da sessão. A entrada de confiança vai
como argumento TOML, sem alterar a configuração global. Retomar a mesma
pasta reaproveita a escolha; trocar de pasta exige nova confirmação.
O parser de `-c` do Codex separa a chave por pontos sem interpretar aspas:
`projects."CAMINHO".trust_level` não funciona. Passe a tabela inteira no
valor de `projects`, com o caminho como chave TOML entre aspas. Confira
o resultado por `config/read` no CLI real; tomllib sozinho não detecta isso.

Os perfis `codex` e `codex-codex` usam o mesmo ciclo de sessões. O adaptador
`jangada-codex` exige `--no-daemon`, injeta o protocolo por
`developer_instructions` e passa hooks sem alterar a configuração global.
Os hooks precisam de conferência pelo `/hooks` do CLI; não dispense a
confiança dos hooks para fazer a barra funcionar.

O Codex sempre exige isolamento, inclusive com `--sem-isolar` e
`JANGADA_AGENTE_ISOLAR=0`. A chamada direta ao adaptador é recusada.

Dentro do bubblewrap, dados próprios em `$JANGADA_ESTADO/codex/SESSAO`
ocupam a pasta do Codex. O login e as configurações do host ficam somente
leitura. A pasta original não pode ficar gravável: seus hooks, regras e
plugins seriam executados fora do isolamento. `CODEX_SQLITE_HOME` aponta
para a pasta montada, sem mudar `CODEX_HOME`.

Na restauração, UUID vai por `resume UUID`. Sem UUID, `resume --last` só
vale no worktree próprio; direto no projeto abre conversa nova.
O revisor Codex recebe só o pedido completo numa pasta vazia, sem terminal,
hooks ou ferramentas externas. Mais detalhes em `docs/codex.md`.

## Peças

O `jangada-delegar --capacidade` seleciona destinos para leitura documental.
O envio ao agy exige autorização da tarefa (`--permitir-remoto`) e do perfil.
Uma falha do Ollama não autoriza esse envio. Veja os limites e capacidades
em `docs/subagentes-e-delegacao.md`.

No teste real, o qwen3:4b consumiu milhares de tokens de raciocínio para
devolver apenas localizadores. Com capacidade, o delegador usa `think: false` e
`num_predict: 1024`; recusa saída cortada pelo limite. O template local
antigo abre `<think>` mesmo com a opção desligada. Para Qwen3, a mensagem
termina também em `/no_think`, conforme o [controle do Qwen3](https://qwen.readthedocs.io/en/stable/getting_started/quickstart.html).
O modelo de 4 bilhões disponível continuou raciocinando mesmo com ambos
os controles. Não presuma suporte: saída limitada deve ser recusada.
Nos testes sintéticos, uma estrutura JSON obrigatória eliminou o estouro;
`format: "json"` sozinho deixou campos e citações incorretos.
Para extração, use `--destino local --capacidade leitura_documental` e
`--extrair campo:tipo`, com `texto`, `inteiro` ou `booleano`.
Campos ausentes no trecho usam valor e referência nulos. A conferência
valida os tipos e a presença da posição citada naquele trecho, sem avaliar o sentido.
A consolidação por modelo chegou a apagar a responsável encontrada na última
parte. A extração une partes de forma determinística: valores presentes
substituem ausências, `false` e zero são preservados, conflitos recusam.
Essa união não consome chamada; textos livres ainda usam consolidação pelo modelo.
Use requisitos explícitos (`--requisito`) para exigir explicações em cada seção, além
das referências. Essa conferência estrutural não aprova o sentido.
Documentos divididos exigem orçamento para todas as partes e consolidação
antes da primeira chamada.

Limites internos do agy usam `--foreground` nas seleções por capacidade
para manter os filhos no grupo do limite global.

Uma consulta de cota que falha não pode reutilizar o valor expirado.
Uma resposta parcial de `/usage` não torna todos os grupos inválidos.
Validar o cache somente pelo primeiro modelo bloqueava outro grupo com cota válida.
O delegador aceita cache atual com algum grupo configurado válido; cada modelo
continua exigindo a cota do próprio grupo. O indicador de disponibilidade segue essa regra.
Cota desconhecida impede a chamada ao modelo daquele grupo.
Consumo de tokens do Claude não comprova cota restante.

Se testes de sinais passam isolados, mas falham na suíte, compare com
`env --default-signal=INT,QUIT testes/verificar.sh`. Essa chamada reinicializa
os sinais herdados e mantém todas as verificações. Investigue qualquer
falha que persistir.

Ao conferir `/proc/PID/stat` depois de cancelar um processo, a leitura pode
levantar `FileNotFoundError` ou `ProcessLookupError`. Ambos indicam que o
processo desapareceu. O teste deve aceitar esses dois erros, mantendo a
conferência de processo zumbi e o prazo; outros erros continuam sendo falhas.

| Peça | Papel |
|---|---|
| `jangada-agente` | escolhe projeto, cria worktree `agente/<nome>` e abre o agente numa sessão `tmux -L jangada`; `--prompt`/`--prompt-arquivo` já entregam a tarefa, `--perfil` escolhe o agente, `--sem-isolar` abre fora do bubblewrap |
| `jangada-isolar` | roda o agente no bubblewrap: sistema somente leitura, pasta da tarefa gravável; `--mostrar` imprime a chamada ao `bwrap` |
| `jangada-worktree-preparar` | copia para o worktree novo os ignorados do `.worktreeinclude`, liga o que está em `.jangada/links` e roda `.jangada/preparar.sh` |
| `jangada-hook-claude` | chamado pelos hooks do Claude Code; grava o estado e notifica |
| `jangada-hook-agy` | o mesmo para o agy, pelo `~/.gemini/config/hooks.json` (PreInvocation e Stop) |
| `jangada-hook-leitor` | PreToolUse do leitor: só comandos de leitura no terminal; no Claude pelo frontmatter do agente, no agy (`--agy`) pelo `PreToolUse` do `run_command` no `~/.gemini/config/hooks.json` |
| `jangada-filtrar` | condensa saídas longas de comandos no terminal para poupar tokens; atalho `resumir` no jangada shell |
| `jangada-mapa` | extrai a estrutura de arquivos e assinaturas em Markdown; atalho `mapa` no jangada shell |
| `jangada-validar` | revisão do diff por outro modelo ou pelo mesmo modelo isolado (claude ou agy), só leitura, chamada pelo agente antes de entregar; executa portão determinístico local antes (conflitos, script com byte nulo, sintaxe, lintr, gitleaks nas linhas acrescentadas; sem gitleaks reprova, salvo `JANGADA_VALIDAR_SEM_GITLEAKS=1`; `.gitleaks.toml`, `.gitleaksignore`, `AGENTS.md` e `CLAUDE.md` valem da base, e `.lintr` também quando a base tem um); só a primeira linha não vazia do parecer decide o status; pareceres em `validacao-<sessao>-rN.md`; a primeira linha tem de ser exatamente `STATUS: APROVADO` ou `STATUS: REVISAR`, e a aprovação pelo modelo do autor sai como `APROVADO_AUTORREVISAO`; a revisão lê uma foto congelada da entrega, não o worktree vivo; depois de um APROVADO, `validacao-<sessao>.aprovado` (JSON) guarda commit, árvore, base e revisor, e a próxima entrega parte dele com as rodadas zeradas; cada rodada vira uma linha em `~/.local/state/jangada/validar.jsonl`, resumida por `--metricas` |
| `jangada-agentes` | seletor, painel, módulo da barra, `--focar`, `--proximo`, `--anterior`, `--restaurar` |
| `jangada-agente-fim` | encerra a sessão e remove o worktree (mantém o ramo); `--integrar` exige aprovação independente feita fora do isolamento (`revisoes/`: commit e árvore atuais do ramo, worktree limpo, base na mesma ponta da revisão), roda o `jangada-validar` fora se não houver e, sem APROVADO ou só com autorrevisão, pede confirmação (`--sem-revisao` pula a revisão); sob a trava do repositório (`revisoes/travas/`), reconfere ramo, base e objetos contra o espelho e faz o merge na base, avisa para rodar o `jangada-update` se for o repositório do jangada, apaga o ramo e, nesse repositório e com `allowed_signers`, chama o `jangada-assinar` |
| `jangada-consumo` | tokens do Claude no bloco de 5 horas, lidos de `~/.claude/projects` |
| `jangada-painel` | indicadores num app Shiny em 127.0.0.1; `default/painel/coletor.py` grava o cache em Parquet (`~/.local/state/jangada/painel`), `default/painel/app.R` só lê o cache |
| `jangada-gancho` | roda os ganchos do usuário em `~/.config/jangada/ganchos/` |

## Isolamento (`jangada-isolar`)

O agente aberto pelo `jangada-agente` roda no bubblewrap, com
`JANGADA_ISOLADO=1` no ambiente. De dentro:

- Grava só na pasta da tarefa (worktree, ou o repositório com `--direto`), em
  `~/.claude`, `~/.gemini/antigravity-cli`, `~/.local/state/jangada/agentes`,
  no `validar.jsonl`, no `eventos-agentes.jsonl`, no `delegacoes.jsonl` e no
  que estiver em `JANGADA_ISOLAR_ESCRITA`. O resto é somente leitura,
  inclusive `~/.claude.json`, `~/.local/share/claude`, `~/.gemini/config` e o
  resto de `~/.local/state/jangada`: escrever em `~/.config`, instalar pacote
  do R na biblioteca do usuário ou rodar `pip install --user` falha com
  "Read-only file system".
- O `~/.cache`, `~/.claude/shell-snapshots`, `~/.claude/session-env` e
  `~/.claude/ide` aceitam escrita, mas ela fica numa camada em memória que
  some no fim (sobreposição do bwrap). Cache grande de compilação ocupa RAM
  enquanto a sessão dura. `~/.cache/yay` e `~/.cache/paru` são somente
  leitura, e `~/.cache/cliphist` (histórico da área de transferência) fica
  oculto.
- Em `~/.claude` são somente leitura `settings.json`, `settings.local.json`,
  `CLAUDE.md`, `commands`, `agents`, `skills`, `hooks`, `plugins`,
  `output-styles`, `backups` e os scripts soltos. `/model` ou `/config` de
  dentro não persistem.
- Git num worktree: o `.git` comum é somente leitura, menos `objects`,
  `refs`, `logs`, `rr-cache`, `reftable` e a pasta do próprio worktree (sem
  o `commondir`, o `gitdir` e o `config.worktree`). Commit, ramo, `checkout -b`, `reset` e `stash` funcionam; apagar
  ramo ou tag e `git gc` falham (regravam o `packed-refs` da raiz). Com
  `--direto`, a raiz do `.git` segue gravável, menos `config`, `hooks`,
  `worktrees`, `modules` e `commondir`; o `jangada-isolar` cria um
  `commondir` com `.` quando falta, porque um bind sobre arquivo ausente
  deixaria no disco um arquivo vazio, e commondir vazio quebra o git.
  `git config` e mudança em `.git/hooks` falham nos dois modos.
- O `/tmp` é próprio da sessão e some quando ela acaba. Não deixe nele nada
  que o usuário ou outra sessão precise ler; use a pasta da tarefa.
- Sem tmux: o socket fica no `/tmp` de fora, e `TMUX` e `TMUX_PANE` saem do
  ambiente. Não há como comandar outra sessão, e a notificação sai sem o botão
  Abrir.
- O `XDG_RUNTIME_DIR` é próprio: sem Hyprland (`hyprctl` falha), Wayland, X,
  gpg-agent e systemd do usuário. O D-Bus da sessão vem pelo
  `xdg-dbus-proxy`, que só fala com `org.freedesktop.Notifications` e, com
  o agy instalado, `org.freedesktop.secrets` (inteiro, ou só os itens de
  `JANGADA_ISOLAR_KEYRING_ITEM`); o proxy vive enquanto o bwrap guarda o
  cano de sincronização (`--sync-fd`). Esse cano é aberto com
  `exec {fd}< <(...)`, e não com `coproc`: o bash fecha os descritores do
  coproc no `exec bwrap`, e o proxy morreria antes de o agente abrir. O D-Bus do sistema e o Docker ficam
  ocultos, e o namespace de PID é próprio: `kill` e `ps` só alcançam os
  processos da sessão, e um pid gravado de dentro não vale fora.
- `~/.ssh`, `~/.gnupg`, `~/.git-credentials`, `~/.config/gh`, os chaveiros e
  os perfis de navegador aparecem vazios, e `SSH_AUTH_SOCK` sai do ambiente.
  `git push` por ssh ou com credencial guardada não funciona: o push é do
  usuário, fora da sessão.
- `jangada-isolar` chamado de dentro roda o comando direto, sem aninhar,
  desde que `JANGADA_ISOLADO` venha com a marca `/tmp/.jangada-isolado`
  montada pelo bwrap (conferida em `/proc/self/mountinfo`); só a variável
  não basta. O `jangada-validar` chamado pelo agente roda, portanto, com as
  mesmas regras;
  `revisar` no jangada shell e o `.jangada/preparar.sh` também passam pelo
  `jangada-isolar`. Pelo mesmo motivo, o `testes/isolar.sh` falha inteiro
  dentro de uma sessão isolada (`JANGADA_ISOLADO=1`): rode
  `env -u JANGADA_ISOLADO testes/verificar.sh`, e apague o `/tmp/isolar-teste`
  que uma rodada sem isso deixa, ou o caso do `/tmp` próprio falha depois.
- Se a tarefa precisa gravar fora dessas pastas, pare e peça ao usuário:
  acrescentar a pasta em `JANGADA_ISOLAR_ESCRITA` no `jangada.conf` ou reabrir
  com `jangada-agente --sem-isolar`. Não contorne o isolamento.

O isolamento fecha os caminhos conhecidos para rodar código fora do bwrap
(estado executado na restauração, configuração do git, hooks do Claude,
sockets do Hyprland e do sistema), mas não é uma barreira completa: o
chaveiro inteiro é legível pelo D-Bus filtrado, `~/.claude/projects` e o
`settings.json` do agy seguem graváveis, e repositórios aninhados no índice
só ficam protegidos quando o git de fora passa por `jangada_git_seguro`.
`JANGADA_AGENTE_ISOLAR=0` desliga (no `jangada.conf` ou num perfil), e
`JANGADA_ISOLAR_OCULTAR` substitui a lista de ocultos, e
`JANGADA_ISOLAR_OCULTAR_EXTRA` acrescenta a ela. `JANGADA_ISOLAR_PERFIL=verificacao`
(usado pelo `jangada-validar` no `lintr` e no `.jangada/validar.sh`) corta a
rede e oculta os logins e as chaves dos provedores. Repositório em reftable
é recusado. O `/sys` é o do host mesmo sem rede: para conferir a rede de
dentro, leia `/proc/net/dev`. O estado guarda
`comando` e `isolar` só para consulta: o `--restaurar` recompõe o comando e
volta isolado, a menos que `JANGADA_AGENTE_ISOLAR=0` esteja no `jangada.conf`
ou no ambiente (perfil e `--sem-isolar` não contam). Sem o `bwrap`, o
`jangada-isolar` sai com erro e o agente não abre: reabrir com
`jangada-agente --sem-isolar` ou pôr `JANGADA_AGENTE_ISOLAR=0` no
`jangada.conf`.

## Contrato de estado

Um JSON por sessão em `~/.local/state/jangada/agentes/<sessao>.json`, com
`sessao`, `dir`, `raiz`, `worktree`, `ramo`, `base`, `agente`, `revisor`, `estado`,
`mensagem`, `desde`, `atualizado`, `comando`, `isolar`, `perfil`, `tarefa`, `conversa`
(id da conversa, gravado pelo hook), `inicio` (HEAD na criação),
`delegar` (destino dos subagentes) e `validacao` (última rodada do
`jangada-validar`, com o revisor). `comando` e `isolar` são só para consulta:
o estado é gravável de dentro do isolamento, e nada dele é executado como
texto.
Estados: `iniciado`, `trabalhando`, `aguardando`, `concluido`, `interrompido`.

`interrompido` é a sessão cujo tmux sumiu (reinício, queda do servidor) com
worktree ainda presente. Ela fica guardada por 168 horas; `--restaurar` (ou o
`--focar` nela) recria a sessão tmux e retoma a conversa com
`claude --resume <conversa>`; sem o id, `--continue` num worktree e conversa
nova direto no repositório. O comando sai de campos conferidos (agente
`claude` ou `agy`, conversa em formato uuid, pasta dentro de
`JANGADA_WORKTREES` ou `JANGADA_PROJETOS`, revisor) e da configuração; estado
que não passa na conferência é recusado. O ambiente de um perfil é relido de
`~/.config/jangada/agentes/NOME.conf` na restauração, nunca guardado no
estado.

Cada mudança de estado vira também uma linha em
`~/.local/state/jangada/eventos-agentes.jsonl`, com `data`, `sessao`,
`projeto` (nome da pasta da raiz), `agente` e `estado`. Além dos estados
acima, o arquivo tem `inicio` e `fim` (SessionStart e SessionEnd do Claude),
`foco` (cada `--focar` numa sessão viva) e `subagente-inicio` e
`subagente-fim` (com `subagente_id`, `subagente_tipo` e `conversa`). Só
gravam o histórico os hooks e o `jangada-agentes`, por
`jangada_registrar_evento` (`bin/jangada-config`), que nunca falha: um erro ao gravar não pode derrubar o hook. A linha entra por
`jangada_anexar_linha`, sob `flock` no próprio arquivo: o `printf` do bash
divide uma linha grande em várias escritas, e duas sessões anexando ao mesmo
tempo misturavam os pedaços. O `delegacoes.jsonl` usa a mesma função. Em
teste, linha grande se gera com `printf`, não com `jq --arg` (300 KB estouram
o limite de argumentos). O histórico só
cresce; o mapa de todos os registros usados pelo painel de indicadores está
em `docs/registros.md`.

## Hooks do Claude Code

`default/claude/hooks.json` é mesclado em `~/.claude/settings.json` pela
instalação e pela migração, por evento, sem duplicar (a chave é o comando sem
o caminho até `/bin/`). Eventos: `UserPromptSubmit` e `PostToolUse` (trabalhando),
`Notification` (aguardando; `auth_success` é ignorado e `idle_prompt` vira
concluído sem aviso), `Stop` (concluído), `SessionStart` (iniciado) e
`SessionEnd` (concluído; `reason=clear` não muda o estado). Todo evento grava
`conversa` com o `session_id`. `SubagentStart` e `SubagentStop` (Claude Code
2.1.283 confirmado) trazem `agent_id` e `agent_type`, e o Stop traz também
`agent_transcript_path` e `last_assistant_message`. Eles só gravam uma linha
no histórico: não mexem no estado nem na barra, porque o agente principal
segue trabalhando. O `Stop` comum não dispara no fim de um subagente. Quem
lê o histórico e mede tempo por estado deve pular os estados `subagente-*`,
como já pula o `foco`. `jangada-verificar` confere cada evento.
A `mensagem` vem de `.message` (Notification), `.last_assistant_message`
(Stop) ou `.prompt` (UserPromptSubmit), primeira linha; o `PostToolUse`
mantém a anterior. Toda alteração do arquivo passa por
`jangada_alterar_estado` (`bin/jangada-config`), que usa `flock` na própria
pasta `agentes/`, aberta só para leitura: os hooks rodam em paralelo. Não
volte a um arquivo de trava aberto com `>`: o agente troca o arquivo por um
link, e o `jangada-agentes` ou o `jangada-validar` de fora truncariam o alvo.

`aguardando` e `concluido` são resultado, não processo: continuam no painel
depois de o processo sair, até o `Ctrl+X` do seletor ou até vencer
`JANGADA_AGENTES_GUARDAR` horas. O `jangada-agente-fim` não mata o pid
guardado de um estado final, porque o número pode ter sido reaproveitado.

A variável `JANGADA_SESSAO` da sessão tmux é o que liga o hook ao arquivo;
agente aberto fora do `jangada-agente` só gera notificação. O título da janela
do terminal é o nome da sessão (`set-titles-string "#S"`), e é por ele que o
`--focar` encontra a janela.

Os hooks rodam dentro do isolamento do agente. Arquivo novo que um hook
precise gravar fora de `agentes/` tem de entrar como gravável no
`jangada-isolar` (e existir antes do bind); sem isso a escrita falha calada,
porque o hook engole o erro.

Registro novo que o painel precise ler entra no `coletor.py`, nunca no
`app.R`. O coletor lê cada jsonl do Claude a partir da posição salva em
`posicoes.json` e só faz `json.loads` nas linhas com `"usage"`,
`"tool_use"` ou `"tool_result"`. Reler `~/.claude/projects` inteiro custa
~280 MB por clique, e o Claude apaga conversas com mais de 30 dias: o
histórico existe só no cache. Resposta do Claude conta uma vez por
`message.id` e `requestId`, com o maior `output_tokens`.

Arquivo parcial do cache leva ponto inicial (`coletor.temporario`): o arrow,
no Python e no R, ignora esses arquivos ao ler a pasta, e um `.tmp` sem ponto
deixado por uma coleta interrompida quebra toda leitura com ArrowInvalid.
Texto que vem de registro (pasta, sessão, arquivo, ferramenta) passa por
`esc()` antes de ir para o `title` de um nó: o visNetwork põe o `title` em
innerHTML, e os registros são gravados pelo agente isolado.

Os grafos da aba Redes usam igraph para as métricas e visNetwork para
desenhar. Poda sempre antes de desenhar (cerca de 40 nós, com o controle no
painel): com mais nós o grafo vira bola. A física do visNetwork roda só até
estabilizar e desliga, senão o grafo não para de tremer. No igraph 2.x use
`get_edge_ids`; `union` de grafos com peso renomeia o atributo `weight`.
O `validar.jsonl` não guarda quais arquivos a entrega mudou: os arquivos
com REVISAR saem dos itens dos pareceres (`apontamentos.parquet`).

O módulo `custom/indicadores` da barra roda `jangada-painel --waybar`, que
só lê o cache. Nunca ponha a coleta no `exec`: ela leva segundos e a waybar
a repete a cada intervalo. O `on-click` usa `setsid -f`; sem ele, a waybar
espera o R subir. O sinal 9 é só dele.

O `setsid -f` passa ao filho os descritores abertos. O R sobe com `8>&-`,
senão herda a trava da coleta e o segundo clique espera até o app fechar; e a
trava é solta antes do `xdg-open`, que também a passaria ao navegador.

## Scripts bash deste repositório

- Trap só em `EXIT`. Um trap em `INT`/`TERM` não encerra o script: o bash roda
  o handler e segue na linha seguinte.
- Funções de `shell/jangada-shell.sh` rodam em bash e zsh: nada de
  `read -p` nem `${var,,}`.
- O fzf roda a prévia com o `$SHELL` do usuário; no zsh uma palavra começando
  com `=` (como `-t =sessao:` do tmux) é expandida. Chame o próprio script
  (`--previa`) em vez de montar o comando na string.
- Em sessões diretas no repositório (sem ramo nem worktree), `jangada-agente-fim`
  com `--integrar` não deve falhar: avisa que não há ramo a integrar e encerra a
  sessão normalmente.
- `read -p` só mostra o texto quando a entrada é um terminal. Aviso que um
  teste precisa ver (ou quem responde por cano) sai num `echo` antes da
  pergunta.

## Avaliação local (`jangada-avaliar-ollama`)

Na avaliação pelo `jangada-avaliar-ollama`, o estado das delegações fica
separado, mas as marcas de jogos e memória de vídeo apontam para o estado
original, e cada repetição adquire a trava compartilhada do Ollama. Uma
pasta de estado vazia perde essas marcas e causa recusa por
memória não verificável no isolamento; essa recusa não avalia o modelo.

## Revisão cruzada (`jangada-validar`)

O `jangada-par` (Claude implementando em lote, agy revisando) saiu em
22/09/2026: o agente interativo com o protocolo faz o mesmo sem uma segunda
porta de entrada. O que se aprendeu com ele vale para o revisor agy:

- Por padrão, Codex revisa Claude e Claude revisa Codex. Fora de sessão e
  nas sessões antigas do agy, Claude revisa.
  Com `--revisor mesmo` ou no perfil `claude-claude`, o mesmo
  modelo revisa em processo isolado.
- Revisor que falha (agy sem cota, por exemplo) passa a vez: outros modelos
  na ordem `claude`, `agy`, `codex`, e por último o do autor. Não passa com
  `--revisor` nem com o prazo vencido. O estado e o `validar.jsonl` dizem
  quem deu o parecer.
- Sem terminal, o agy não tem como pedir permissão: comando ou escrita é
  recusado e ele devolve `status: SUCCESS` com `response` vazio. O pedido
  manda **não executar comandos** e ler com a ferramenta de leitura.
  `--dangerously-skip-permissions` foi recusado de propósito.
- A ferramenta de leitura carrega o arquivo inteiro: um PDF ou planilha grande
  estoura o limite de 1.048.576 tokens. O pedido proíbe binários, e o diff tem
  teto (`JANGADA_VALIDAR_DIFF_MAX`).
- Às vezes sai com código 0 sem escrever nada. Repetir resolve; o
  `jangada-validar` tenta duas vezes.
- A saída do agy é lida por cano, não por arquivo: ele reabre o próprio
  descritor, e com redirecionamento o JSON já foi parar num arquivo sem nome.
- O pedido vai como argumento, e o Linux limita um argumento a 128 KiB
  (`MAX_ARG_STRLEN`). Acima de 126000 bytes o diff sai do pedido e vai para
  `validacao-<sessao>-rN.md.diff`, que o agy lê pela pasta liberada em
  `--add-dir`.
- A revisão pelo agy leva minutos; o protocolo manda dar 10 minutos de tempo
  limite à ferramenta de comando.
- O revisor erra sobre `set -e`: falha dentro de uma lista `a && b && c`, fora
  do último comando, não encerra o script. Teste com `bash -c` antes de aceitar.
- Dentro do isolamento, parecer, `.aprovado` e `validar.jsonl` ficam onde o
  agente grava e não provam revisão. Fora dele (`JANGADA_ISOLADO` vazio), o
  `jangada-validar` grava em `revisoes/`, oculta pelo `jangada-isolar`, e lê
  base, tarefa e revisor da cópia `revisoes/SESSAO.json`. Os testes que
  chamam o `jangada-validar` sem querer esse modo passam `JANGADA_ISOLADO=1`.
- Prefira fazer o commit antes de `jangada-validar`, para revisar uma entrega
  limpa. O comando também aceita alterações sem commit; nesse caso, registra
  a aprovação com `limpo` falso. Veja o [ciclo da tarefa](../../../../docs/ciclo-da-tarefa.md).
- `.aprovado` com `limpo` falso (worktree com alteração sem commit) não move o ponto
  de comparação: com o commit igual ao `HEAD`, a próxima rodada daria "nada a
  revisar" sem ninguém ter visto o commit sozinho.
- O git não reconfere o hash de um objeto solto ao ler: um blob trocado em
  `.git/objects` passa pelo `cat-file`, pelo `diff` e pelo `merge` com o nome
  do original. Quem recalcula é o `git fetch` para outro repositório, e ele
  não precisa de `fetch.fsckObjects`. Por isso o `jangada-validar` e o
  `--integrar` buscam a entrega num espelho em `revisoes/espelhos/` e comparam
  o `cat-file --batch` dos dois lados antes do merge.
  O merge ainda lê os objetos depois dessa comparação, então o `--integrar`
  refaz a mescla no espelho (`git merge-tree --write-tree`), exige a mesma
  árvore e relê os arquivos escritos (`update-index --really-refresh` e
  `diff-index`); diferença desfaz o merge. Não serve `git diff --quiet HEAD`:
  ele compara o arquivo com o conteúdo do objeto forjado e não vê diferença.
  O que isso não cobre: o agente segue gravando em `.git/objects` depois da
  integração, e um objeto trocado mais tarde só aparece no `git fsck`.
- Uma marca `.aprovado` que não vale para o merge (base andou, árvore
  trocada, formato antigo) tem de sair antes de revisar de novo: com ela, o
  `jangada-validar` parte do commit aprovado e responde "nada a revisar".
- `read -p` só mostra a pergunta com a entrada num terminal. Teste que
  responde pela entrada padrão confere a mensagem anterior à pergunta, não a
  pergunta.
- O `jangada-validar` executa uma checagem determinística local antes do revisor por IA (marcadores de conflito do Git, sintaxe de scripts alterados e `.jangada/validar.sh`). Se falhar, grava `STATUS: REVISAR (local)` sem acionar a API externa, economizando tokens. A opção `--pular-local` ignora o portão local.
- Um comentário de shell que começa pela palavra `shellcheck` vira diretiva e
  quebra a análise do arquivo inteiro (SC1073). Reescreva a frase.
- O `gitleaks dir` lê sozinho o `.gitleaks.toml` e o `.gitleaksignore` da
  pasta examinada. O espelho das linhas novas não copia esses dois arquivos;
  as regras vão por `--config` e `--gitleaks-ignore-path`, tiradas da base.
- Se o limite de rodadas for atingido, a opção `--reverter-se-limite` (ou o comando `reverter` no jangada shell) restaura o worktree para o ponto inicial limpo da tarefa. O `reverter` do shell mostra antes da confirmação os commits, as alterações e os arquivos não rastreados que se perdem, e guarda o HEAD anterior num ramo `backup/reverter-<data>-<pid>`, cujo nome informa ao terminar.

Depois de integrar uma mudança no próprio jangada, confira e
atualize a cópia instalada com `jangada-update`.

## agy como suporte

- O agy não abre sessão principal desde 03/10/2026: o `jangada-agente`
  recusa `--agente agy` e perfil com `COMANDO=agy`. Ele atende o
  `jangada-delegar` e a revisão do `jangada-validar`. Sessão antiga do agy
  aberta sem perfil ainda é restaurada pelo `jangada-agentes`.
- O seletor do `jangada-agente` oferece o padrão e os perfis, cada um com a
  descrição calculada entre parênteses. Os perfis de `default/agentes/`
  (`claude-claude.conf`, `codex*.conf`) perdem para perfis de mesmo nome em
  `~/.config/jangada/agentes`.
- O protocolo é `default/agentes/protocolo.md`. No Claude vai por
  `--append-system-prompt` e no Codex pelo `jangada-codex`; na restauração o
  `jangada-agentes` monta o protocolo de novo (`refazer_protocolo`), sem ler o
  `comando` guardado.
- Hooks do agy: só o global `~/.gemini/config/hooks.json` foi carregado pelo
  CLI nos testes de 22/09/2026. O `.agents/hooks.json` do projeto deu "loaded 0
  named hooks" no log (`~/.gemini/antigravity-cli/log/`). O hook roda com a
  pasta do `hooks.json` como diretório atual e herda o ambiente, inclusive
  `JANGADA_SESSAO`.
- Skills do agy: a raiz global é `~/.gemini/config/skills/<nome>/SKILL.md`
  (teste de 26/09/2026). Não é `~/.gemini/antigravity/skills` nem
  `~/.gemini/antigravity-cli`, como sugerem textos da web. O agy segue link
  simbólico e aceita o frontmatter do Claude Code (`name`, `description` com
  `>`). A referência oficial vem no próprio CLI, em
  `~/.gemini/antigravity-cli/builtin/skills/agy-customizations/docs/`.
- Antes de cada comando, o agy regrava `~/.gemini/antigravity-cli/bin/agentapi`
  (teste de 28/09/2026). Com a pasta somente leitura, todo comando falha com
  "failed to write agentapi script: read-only file system"; por isso o
  `jangada-isolar` a monta em camada temporária.
- **Não registre `PreToolUse` respondendo `{}`**: o agy trata como recusa e a
  ferramenta é negada ("tool call denied by pre-tool hook").
- O Stop traz `fullyIdle`, `terminationReason` e `error`; não traz a última
  resposta. No jq, `.fullyIdle // true` dá `true` mesmo com `false`.
- **Arquivo de configuração vazio passa calado pelo jq**: `jq FILTRO arq` com
  `arq` de 0 bytes não devolve nada e sai com 0. Uma conferência que espera
  saída vazia para "nada falta" dava os hooks por instalados, e a mescla os
  dava por já instalados sem gravar. Leia com `jq -n '(first(inputs) // {})'`
  ou confira antes com `jq -e 'type == "object"'`. Em 28/09/2026 o
  `~/.claude/settings.json` real apareceu com 0 bytes, sem causa achada, e o
  `jangada-verificar` dizia que estava tudo certo.
- Chamadas auxiliares desligam os hooks da sessão: o `jangada-validar` chama
  o revisor com `env -u JANGADA_SESSAO JANGADA_HOOK_DESLIGADO=1`, que os dois
  hooks respeitam.
- A confiança do agy na pasta é por caminho exato (`trustedWorkspaces` em
  `~/.gemini/antigravity-cli/settings.json`; confiar em `~` não cobre as
  subpastas). Só o `jangada-worktree-preparar` e o fim da sessão mexem
  nela; o `jangada-delegar` recusa pasta sem confiança em vez de confiar,
  porque a confiança libera agentes, regras e MCP da própria pasta. O
  worktree só herda a confiança da raiz: se o usuário não confiou no
  repositório principal, o `jangada-worktree-preparar` não confia no
  worktree, e o agy abre com a pergunta "Do you trust the contents of this
  project?", que o usuário responde na janela.
  A pasta `~/.gemini/antigravity-cli` é gravável pelo agente isolado, e o
  fim da sessão regrava o `settings.json` de fora do isolamento: se o arquivo
  virou link simbólico, o jangada não mexe nele, e a troca é por rename
  (`jangada_gravar_atomico`), que não segue link.
- Para testar hooks sem tocar no estado real, mude `XDG_STATE_HOME`; o
  `jangada-config` recalcula `JANGADA_ESTADO` a partir dele.
- Clones de referência em subpastas (como `referencia/`): se contiverem
  `CLAUDE.md` ou `AGENTS.md`, o harness do Claude ou do agy pode carregar os
  arquivos de terceiros como se fossem regras do projeto. Apague esses arquivos
  de dentro de `referencia/` logo após clonar.

## Subagentes do agy

Hooks do agy, testados em 28/09/2026:

- `~/.gemini/config/hooks.json` agrupa por nome (`{"jangada": {EVENTO:
  [...]}}`). `PreInvocation` e `Stop` levam os comandos direto na lista;
  `PreToolUse` leva `{"matcher": "run_command", "hooks": [{"command": ...}]}`.
- O `PreToolUse` recebe JSON em camelCase (`conversationId`,
  `toolCall.name`, `toolCall.args.CommandLine`) e precisa responder JSON:
  `{"decision": "allow|deny|ask|force_ask", "reason": ...}`. `{}` conta como
  recusa, e saída inválida dá erro na ferramenta. Por isso o
  `jangada-hook-leitor --agy` responde `deny` também quando o Python falha.
- O hook global dispara para todos os agentes, também para subagentes. O
  `conversationId` é o do subagente, e o tipo dele está em
  `brain/MAE/.system_generated/subagents/CONVERSA.json`
  (`subagentDescriptor.typeName`). No `agy -p --agent PAPEL` não há esse
  arquivo: o papel vem da variável `JANGADA_AGY_PAPEL`.
- Sem terminal, `allow` e `ask` só deixam passar o que está em
  `permissions.allow`; `ask` é a resposta neutra.
- Para testar um hook que recusa, peça um comando que o modelo ache de
  leitura e que esteja no `permissions.allow` (como `sort`). Com `cp`, o
  próprio leitor recusa pelo texto do papel, e o hook nem é chamado.

Agentes personalizados:

Testes de 27/09/2026, agy 1.2.12:

- Agente personalizado em `agent.md` (frontmatter YAML, prompt depois de um
  título H1), numa pasta listada em `~/.gemini/config/agents.json`
  (`{"entries": [{"path": PASTA}]}`, lida um nível abaixo). A pasta
  `~/.gemini/config/agents/` sozinha não é lida.
- `model:` aceita só `flash`, `pro` ou `inherit`. Com o nome completo
  (`gemini-3.8-flash-low`) o agente some sem aviso. O esforço vai na
  chamada: `agy -p ... --agent PAPEL --model gemini-3.8-flash-low`.
- **`--agent` com nome desconhecido não falha**: cai no agente padrão, com
  todas as ferramentas. Só o log diz (`Agent "x" not found, falling back to
  default`). Confira com `agy agents` antes da chamada, como fazem o
  `jangada-delegar` e o `jangada-validar`: falha fechada, não aberta.
- `tools:` restringe de fato; `manage_task` e `send_message` vêm sempre.
- No `-p`, `run_command` é negado sem regra em `permissions.allow`
  (`denied_actions` no JSON e `response` vazio).
- O JSON do `-p` traz `usage` (`input_tokens`, `output_tokens`,
  `total_tokens`) e `duration_seconds`.
- `agy -p "/usage" --output-format json` responde em uns 3 segundos, sem
  gastar cota: a fração restante fica em
  `.command.data.groups[].buckets[]` com `id` `gemini-5h`, `gemini-weekly`,
  `3p-5h` e `3p-weekly` (`remaining_fraction`, de 0 a 1).
- **O limite de 5 horas sozinho engana**: com a semanal zerada, o `/usage`
  devolve `gemini-weekly` em 0 e `gemini-5h` em 0,99 com `"disabled": true`,
  e toda chamada falha com 429 (`RESOURCE_EXHAUSTED`). Em 03/10/2026 o
  `jangada-delegar` lia só o `gemini-5h` e mandava ao agy sem cota. A cota de
  um grupo é a menor fração entre os buckets sem `disabled`.
- Flash e Pro dividem o grupo `gemini-*`; trocar entre eles não rende cota.
  Os modelos Claude e GPT do agy usam o grupo `3p-*`. Por isso
  `JANGADA_DELEGAR_MODELOS` põe depois do Flash modelos do outro grupo.
- `agy agents` lista um nome por linha só dos agentes que carregaram (um
  `model:` inválido some da lista). Em 27/09/2026, com a saída num cano ou
  num arquivo e sem terminal (`setsid`, `</dev/null`), a lista saiu inteira.
- Agente com `subagent: false` e `model: inherit` carrega e atende ao
  `--agent` com `--model` na chamada (testado em 27/09/2026 com o `revisor`
  do `jangada-validar`, que negou criar arquivo e rodar comando).
- `--sandbox` restringe só o terminal. Leitura sem escrita vem do `tools:`
  do agente.
- `--dangerously-skip-permissions` não serve para delegar: libera escrita.
  O `jangada-delegar` usa `--sandbox` e depende do `permissions.allow`.

Pegadinhas da delegação local:

Testes de 29/09/2026, Ollama 0.34.4:

- **Isolamento e checagens do sistema**: dentro do `jangada-isolar` (`bwrap` com
  `--unshare-pid` e sem nós `/dev/nvidia*`), `pgrep` não enxerga processos do
  host (como Steam) e `nvidia-smi` não consegue comunicar com o driver. O host
  grava marcas em `$JANGADA_ESTADO/marcas/vram-livre` e `$JANGADA_ESTADO/marcas/jogo-ativo`
  antes de isolar e as renova conforme `JANGADA_MONITOR_INTERVALO` (padrão de
  30 segundos; valores perto ou acima de 120 s causam recusa por expiração no
  delegar), e o script consulta `/api/ps` no Ollama.
  O `nvidia-smi` pode escrever uma falha na saída padrão dentro do isolamento.
  Descarte qualquer saída que não seja numérica antes de consultar a marca
  de memória livre gravada pelo host; texto de erro não é medição.
- **Memória de vídeo com modelo residente**: com `keep_alive` ativo, o modelo
  permanece na memória de vídeo após a primeira chamada. A memória livre cai
  e pode barrar chamadas seguintes; é preciso consultar `/api/ps` e somar a
  memória do modelo já residente à memória livre.
- **Opção num_ctx obrigatória**: sem definir explicitamente `options.num_ctx`
  no `/api/chat`, o Ollama assume o padrão de 2048 tokens mesmo para modelos que
  suportam janelas muito maiores.
- **Truncamento de contexto**: se a entrada ultrapassar `num_ctx`, o Ollama
  trunca o texto sem emitir erro na resposta. Como `prompt_eval_count` pode
  reportar apenas o valor truncado (`tent >= ctx` não é garantia se o servidor
  já truncou a entrada), a proteção efetiva depende da checagem prévia do
  tamanho estimado do texto antes do envio.

## Perfis e ganchos

- Perfil: `~/.config/jangada/agentes/NOME.conf` com `COMANDO=`, `ARGS=`,
  `DESCRICAO=` e
  outras chaves em maiúsculas, que viram ambiente só daquela sessão (exemplo
  em `default/agentes/exemplo.conf`). O arquivo é lido, não executado.
  `JANGADA_AGENTE_ISOLAR=0` no perfil abre aquele agente fora do bubblewrap.
  Use para outra conta, outro modelo ou outro agente.
- Ganchos: executável `~/.config/jangada/ganchos/EVENTO` ou arquivos em
  `EVENTO.d/`. Eventos: `pos-tema`, `pos-agente-fim` (sessão, raiz, integrado),
  `pos-validar`, `pos-update`. Falha de gancho gera só aviso.

## Executor do Conversa de Pescador

O agy aceita nomes desconhecidos em `--agent` e pode usar o agente padrão, com ferramentas. O executor confere `agy agents` antes de usar `pescador`, definido sem ferramentas e sem MCP. Claude fornece eventos parciais com `--output-format stream-json --verbose --include-partial-messages`; eventos `assistant` e `result` repetem o texto e não devem ser concatenados aos trechos recebidos. O pedido entra por stdin. `jangada-pescador-modelo` exige a marca real do bubblewrap, mesmo quando o isolamento geral está desligado.
