# Camada de agentes

## Peças

| Peça | Papel |
|---|---|
| `jangada-agente` | escolhe projeto, cria worktree `agente/<nome>` e abre o agente numa sessão `tmux -L jangada`; `--prompt`/`--prompt-arquivo` já entregam a tarefa, `--perfil` escolhe o agente |
| `jangada-worktree-preparar` | copia para o worktree novo os ignorados do `.worktreeinclude`, liga o que está em `.jangada/links` e roda `.jangada/preparar.sh` |
| `jangada-hook-claude` | chamado pelos hooks do Claude Code; grava o estado e notifica |
| `jangada-hook-agy` | o mesmo para o agy, pelo `~/.gemini/config/hooks.json` (PreInvocation e Stop) |
| `jangada-validar` | revisão do diff pelo outro modelo (agy revisa o Claude, Claude revisa o agy), só leitura, chamada pelo agente antes de entregar; pareceres em `validacao-<sessao>-rN.md` |
| `jangada-agentes` | seletor, painel, módulo da barra, `--focar`, `--proximo`, `--anterior`, `--restaurar` |
| `jangada-agente-fim` | encerra a sessão e remove o worktree (mantém o ramo); `--integrar` faz o merge na base e apaga o ramo |
| `jangada-consumo` | tokens do Claude no bloco de 5 horas, lidos de `~/.claude/projects` |
| `jangada-gancho` | roda os ganchos do usuário em `~/.config/jangada/ganchos/` |

## Contrato de estado

Um JSON por sessão em `~/.local/state/jangada/agentes/<sessao>.json`, com
`sessao`, `dir`, `raiz`, `worktree`, `ramo`, `base`, `agente`, `estado`,
`mensagem`, `desde`, `atualizado`, `comando`, `perfil`, `tarefa`, `conversa`
(id da conversa, gravado pelo hook), `inicio` (HEAD na criação) e
`validacao` (última rodada do `jangada-validar`, com o revisor).
Estados: `iniciado`, `trabalhando`, `aguardando`, `concluido`, `interrompido`.

`interrompido` é a sessão cujo tmux sumiu (reinício, queda do servidor) com
worktree ainda presente. Ela fica guardada por 168 horas; `--restaurar` (ou o
`--focar` nela) recria a sessão tmux e retoma a conversa com
`claude --resume <conversa>`; sem o id, `--continue` num worktree e conversa
nova direto no repositório. O ambiente de um
perfil é relido de `~/.config/jangada/agentes/NOME.conf` na restauração, nunca
guardado no estado.

## Hooks do Claude Code

`default/claude/hooks.json` é mesclado em `~/.claude/settings.json` pela
instalação e pela migração, por evento, sem duplicar (a chave é o comando sem
o caminho até `/bin/`). Eventos: `UserPromptSubmit` e `PostToolUse` (trabalhando),
`Notification` (aguardando; `auth_success` é ignorado e `idle_prompt` vira
concluído sem aviso), `Stop` (concluído), `SessionStart` (iniciado) e
`SessionEnd` (concluído; `reason=clear` não muda o estado). Todo evento grava
`conversa` com o `session_id`. `jangada-verificar` confere cada evento.
A `mensagem` vem de `.message` (Notification), `.last_assistant_message`
(Stop) ou `.prompt` (UserPromptSubmit), primeira linha; o `PostToolUse`
mantém a anterior. Toda alteração do arquivo passa por
`jangada_alterar_estado` (`bin/jangada-config`), que usa `flock` em
`agentes/.trava`: os hooks rodam em paralelo.

`aguardando` e `concluido` são resultado, não processo: continuam no painel
depois de o processo sair, até o `Ctrl+X` do seletor ou até vencer
`JANGADA_AGENTES_GUARDAR` horas. O `jangada-agente-fim` não mata o pid
guardado de um estado final, porque o número pode ter sido reaproveitado.

A variável `JANGADA_SESSAO` da sessão tmux é o que liga o hook ao arquivo;
agente aberto fora do `jangada-agente` só gera notificação. O título da janela
do terminal é o nome da sessão (`set-titles-string "#S"`), e é por ele que o
`--focar` encontra a janela.

## Scripts bash deste repositório

- Trap só em `EXIT`. Um trap em `INT`/`TERM` não encerra o script: o bash roda
  o handler e segue na linha seguinte.
- Funções de `shell/jangada-shell.sh` rodam em bash e zsh: nada de
  `read -p` nem `${var,,}`.
- O fzf roda a prévia com o `$SHELL` do usuário; no zsh uma palavra começando
  com `=` (como `-t =sessao:` do tmux) é expandida. Chame o próprio script
  (`--previa`) em vez de montar o comando na string.

## Revisão cruzada (`jangada-validar`)

O `jangada-par` (Claude implementando em lote, agy revisando) saiu em
22/09/2026: o agente interativo com o protocolo faz o mesmo sem uma segunda
porta de entrada. O que se aprendeu com ele vale para o revisor agy:

- O revisor padrão é o oposto do `.agente` da sessão; fora de sessão, Claude.
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

Depois de integrar uma mudança no próprio jangada, confira a cópia
instalada: `git -C ~/.local/share/jangada pull --ff-only` e
`jangada-migrar`.

## agy como agente da sessão

- O seletor do `jangada-agente` oferece o padrão e os perfis, cada um com a
  descrição entre parênteses (`DESCRICAO=` do perfil). O
  `default/agentes/agy.conf` vem no repositório e perde para um perfil de
  mesmo nome em `~/.config/jangada/agentes`.
- O protocolo é `default/agentes/protocolo.md`. No agy a tarefa vai por `-i`,
  precedida dele; sem tarefa, vai só o protocolo. O agy não aceita a tarefa
  como argumento solto. No Claude vai por `--append-system-prompt`, dentro do
  `comando` guardado, para valer também na restauração.
- Hooks do agy: só o global `~/.gemini/config/hooks.json` foi carregado pelo
  CLI nos testes de 22/09/2026. O `.agents/hooks.json` do projeto deu "loaded 0
  named hooks" no log (`~/.gemini/antigravity-cli/log/`). O hook roda com a
  pasta do `hooks.json` como diretório atual e herda o ambiente, inclusive
  `JANGADA_SESSAO`.
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

## Perfis e ganchos

- Perfil: `~/.config/jangada/agentes/NOME.conf` com `COMANDO=`, `ARGS=`,
  `DESCRICAO=` e
  outras chaves em maiúsculas, que viram ambiente só daquela sessão (exemplo
  em `default/agentes/exemplo.conf`). O arquivo é lido, não executado.
  Use para outra conta, outro modelo ou outro agente.
- Ganchos: executável `~/.config/jangada/ganchos/EVENTO` ou arquivos em
  `EVENTO.d/`. Eventos: `pos-tema`, `pos-agente-fim`, `pos-validar`,
  `pos-update`. Falha de gancho gera só aviso.
