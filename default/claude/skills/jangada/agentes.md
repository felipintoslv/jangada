# Camada de agentes

## Peças

| Peça | Papel |
|---|---|
| `jangada-agente` | escolhe projeto, cria worktree `agente/<nome>` e abre o agente numa sessão `tmux -L jangada`; `--prompt`/`--prompt-arquivo` já entregam a tarefa, `--perfil` escolhe o agente, `--sem-isolar` abre fora do bubblewrap |
| `jangada-isolar` | roda o agente no bubblewrap: sistema somente leitura, pasta da tarefa gravável; `--mostrar` imprime a chamada ao `bwrap` |
| `jangada-worktree-preparar` | copia para o worktree novo os ignorados do `.worktreeinclude`, liga o que está em `.jangada/links` e roda `.jangada/preparar.sh` |
| `jangada-hook-claude` | chamado pelos hooks do Claude Code; grava o estado e notifica |
| `jangada-hook-agy` | o mesmo para o agy, pelo `~/.gemini/config/hooks.json` (PreInvocation e Stop) |
| `jangada-filtrar` | condensa saídas longas de comandos no terminal para poupar tokens; atalho `resumir` no jangada shell |
| `jangada-mapa` | extrai a estrutura de arquivos e assinaturas em Markdown; atalho `mapa` no jangada shell |
| `jangada-validar` | revisão do diff por outro modelo ou pelo mesmo modelo isolado (claude ou agy), só leitura, chamada pelo agente antes de entregar; executa portão determinístico local antes (conflitos, script com byte nulo, sintaxe, lintr, gitleaks nas linhas acrescentadas; sem gitleaks reprova, salvo `JANGADA_VALIDAR_SEM_GITLEAKS=1`; `.gitleaks.toml`, `.gitleaksignore`, `AGENTS.md` e `CLAUDE.md` valem da base, e `.lintr` também quando a base tem um); só a primeira linha não vazia do parecer decide o status; pareceres em `validacao-<sessao>-rN.md`; depois de um APROVADO, `validacao-<sessao>.aprovado` guarda o commit, e a próxima entrega parte dele com as rodadas zeradas; cada rodada vira uma linha em `~/.local/state/jangada/validar.jsonl`, resumida por `--metricas` |
| `jangada-agentes` | seletor, painel, módulo da barra, `--focar`, `--proximo`, `--anterior`, `--restaurar` |
| `jangada-agente-fim` | encerra a sessão e remove o worktree (mantém o ramo); `--integrar` faz o merge na base, atualiza a cópia instalada se for o repositório do jangada e apaga o ramo |
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
  `xdg-dbus-proxy`, que só fala com `org.freedesktop.secrets` e
  `org.freedesktop.Notifications`; o proxy vive enquanto o bwrap guarda o
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
`JANGADA_ISOLAR_OCULTAR` substitui a lista de ocultos. O estado guarda
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
`jangada_registrar_evento` (`bin/jangada-config`), que nunca falha: um erro ao gravar não pode derrubar o hook. O histórico só
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

## Revisão cruzada (`jangada-validar`)

O `jangada-par` (Claude implementando em lote, agy revisando) saiu em
22/09/2026: o agente interativo com o protocolo faz o mesmo sem uma segunda
porta de entrada. O que se aprendeu com ele vale para o revisor agy:

- O revisor padrão é o oposto do `.agente` da sessão; fora de sessão, Claude.
  Com `--revisor mesmo` ou nos perfis `claude-claude` e `agy-agy`, o mesmo
  modelo revisa em processo isolado.
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
- O `jangada-validar` executa uma checagem determinística local antes do revisor por IA (marcadores de conflito do Git, sintaxe de scripts alterados e `.jangada/validar.sh`). Se falhar, grava `STATUS: REVISAR (local)` sem acionar a API externa, economizando tokens. A opção `--pular-local` ignora o portão local.
- Um comentário de shell que começa pela palavra `shellcheck` vira diretiva e
  quebra a análise do arquivo inteiro (SC1073). Reescreva a frase.
- O `gitleaks dir` lê sozinho o `.gitleaks.toml` e o `.gitleaksignore` da
  pasta examinada. O espelho das linhas novas não copia esses dois arquivos;
  as regras vão por `--config` e `--gitleaks-ignore-path`, tiradas da base.
- Se o limite de rodadas for atingido, a opção `--reverter-se-limite` (ou o comando `reverter` no jangada shell) restaura o worktree para o ponto inicial limpo da tarefa. O `reverter` do shell mostra antes da confirmação os commits, as alterações e os arquivos não rastreados que se perdem, e guarda o HEAD anterior num ramo `backup/reverter-<data>-<pid>`, cujo nome informa ao terminar.

Depois de integrar uma mudança no próprio jangada, confira a cópia
instalada: `git -C ~/.local/share/jangada pull --ff-only` e
`jangada-migrar`.

## agy como agente da sessão

- O seletor do `jangada-agente` oferece o padrão e os perfis, cada um com a
  descrição entre parênteses (`DESCRICAO=` do perfil). Os perfis
  `default/agentes/agy.conf`, `agy-agy.conf` e `claude-claude.conf` vêm no
  repositório e perdem para perfis de mesmo nome em `~/.config/jangada/agentes`.
- O protocolo é `default/agentes/protocolo.md`. No agy a tarefa vai por `-i`,
  precedida dele; sem tarefa, vai só o protocolo. O agy não aceita a tarefa
  como argumento solto. No Claude vai por `--append-system-prompt`; na restauração o
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
- **Não registre `PreToolUse` respondendo `{}`**: o agy trata como recusa e a
  ferramenta é negada ("tool call denied by pre-tool hook").
- O Stop traz `fullyIdle`, `terminationReason` e `error`; não traz a última
  resposta. No jq, `.fullyIdle // true` dá `true` mesmo com `false`.
- Chamadas auxiliares desligam os hooks da sessão: o `jangada-validar` chama
  o revisor com `env -u JANGADA_SESSAO JANGADA_HOOK_DESLIGADO=1`, que os dois
  hooks respeitam.
- A confiança do agy na pasta é por caminho exato (`trustedWorkspaces` em
  `~/.gemini/antigravity-cli/settings.json`; confiar em `~` não cobre as
  subpastas). Todo worktree novo abre com a pergunta "Do you trust the
  contents of this project?", que o usuário responde na janela.
- Para testar hooks sem tocar no estado real, mude `XDG_STATE_HOME`; o
  `jangada-config` recalcula `JANGADA_ESTADO` a partir dele.
- Clones de referência em subpastas (como `referencia/`): se contiverem
  `CLAUDE.md` ou `AGENTS.md`, o harness do Claude ou do agy pode carregar os
  arquivos de terceiros como se fossem regras do projeto. Apague esses arquivos
  de dentro de `referencia/` logo após clonar.

## Subagentes do agy

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
  default`). Confira o log antes de confiar numa delegação.
- `tools:` restringe de fato; `manage_task` e `send_message` vêm sempre.
- No `-p`, `run_command` é negado sem regra em `permissions.allow`
  (`denied_actions` no JSON e `response` vazio).
- O JSON do `-p` traz `usage` (`input_tokens`, `output_tokens`,
  `total_tokens`) e `duration_seconds`.
- `agy -p "/usage" --output-format json` responde em uns 3 segundos, sem
  gastar cota: a fração restante fica em
  `.command.data.groups[].buckets[]` com `id` `gemini-5h`, `gemini-weekly`,
  `3p-5h` e `3p-weekly` (`remaining_fraction`, de 0 a 1).
- `agy agents` sem terminal não imprime nada. Para saber se o agente
  carregou, rode um `-p` curto com `--agent` e procure o "not found" no log.
- `--dangerously-skip-permissions` não serve para delegar: libera escrita.
  O `jangada-delegar` usa `--sandbox` e depende do `permissions.allow`.

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
