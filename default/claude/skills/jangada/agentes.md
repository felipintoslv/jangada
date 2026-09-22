# Camada de agentes

## Peças

| Peça | Papel |
|---|---|
| `jangada-agente` | escolhe projeto, cria worktree `agente/<nome>` e abre o agente numa sessão `tmux -L jangada`; `--prompt`/`--prompt-arquivo` já entregam a tarefa, `--perfil` escolhe o agente |
| `jangada-worktree-preparar` | copia para o worktree novo os ignorados do `.worktreeinclude`, liga o que está em `.jangada/links` e roda `.jangada/preparar.sh` |
| `jangada-hook-claude` | chamado pelos hooks do Claude Code; grava o estado e notifica |
| `jangada-hook-agy` | o mesmo para o agy, pelo `~/.gemini/config/hooks.json` (PreInvocation e Stop) |
| `jangada-validar` | revisão do diff pelo `claude -p` (só leitura), chamada pelo agy antes de entregar; pareceres em `validacao-<sessao>-rN.md` |
| `jangada-agentes` | seletor, painel, módulo da barra, `--focar`, `--proximo`, `--anterior`, `--restaurar` |
| `jangada-agente-fim` | encerra a sessão e remove o worktree (mantém o ramo); `--integrar` faz o merge na base e apaga o ramo |
| `jangada-par` | Claude implementa, agy revisa, Claude avalia cada apontamento e aplica o que aceitar, em rodadas |
| `jangada-consumo` | tokens do Claude no bloco de 5 horas, lidos de `~/.claude/projects` |
| `jangada-gancho` | roda os ganchos do usuário em `~/.config/jangada/ganchos/` |

## Contrato de estado

Um JSON por sessão em `~/.local/state/jangada/agentes/<sessao>.json`, com
`sessao`, `dir`, `raiz`, `worktree`, `ramo`, `base`, `agente`, `estado`,
`mensagem`, `desde`, `atualizado`, `comando`, `perfil`, `tarefa`, `conversa`
(id da conversa do Claude, gravado pelo hook) e `pid` no `jangada-par`.
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

## Antigravity (`agy`) em modo não interativo

- Sem terminal, o agy não tem como pedir permissão: comando ou escrita é
  recusado e ele devolve `status: SUCCESS` com `response` vazio. O prompt do
  revisor manda **não executar comandos** e ler com a ferramenta de leitura.
  `--dangerously-skip-permissions` foi recusado de propósito.
- A ferramenta de leitura carrega o arquivo inteiro: um PDF ou planilha grande
  estoura o limite de 1.048.576 tokens. O prompt lista os arquivos alterados e
  proíbe binários; o diff tem teto (`DIFF_MAX`).
- Às vezes sai com código 0 sem escrever nada. Repetir resolve; o
  `jangada-par` tenta duas vezes.
- O prompt vai como argumento, e o Linux limita um argumento a 128 KiB
  (`MAX_ARG_STRLEN`). Acima de `PROMPT_BYTES_MAX` (126000 bytes) o diff vai
  cortado no prompt e inteiro num arquivo que o agy lê pela pasta liberada em
  `--add-dir`.
- A avaliação anterior também tem teto (`AVALIACAO_MAX`, 30000 bytes), com
  a íntegra liberada do mesmo jeito.
- O JSON bruto do agy (`revisao-<sessao>-rN.json`) fica na pasta de estado
  quando a chamada falha. `jangada-agentes` ignora `revisao-*` na lista e na
  limpeza de órfãos; antes a barra o apagava segundos depois.
- O revisor erra sobre `set -e`: falha dentro de uma lista `a && b && c`, fora
  do último comando, não encerra o script. Teste com `bash -c` antes de aceitar.

## Fluxo do `jangada-par`

1. Claude implementa e faz commit.
2. agy revisa o diff desde o início do ciclo (merge-base no worktree, HEAD
   inicial no modo direto) até a árvore de trabalho, com o que ficou sem
   commit listado, e responde `STATUS: APROVADO` ou `STATUS: REVISAR` com
   apontamentos numerados; o parecer fica em `parecer-<sessao>-rN.md`.
3. Com REVISAR, o Claude **avalia** cada apontamento (verifica no código,
   testa quando dá) e responde com uma tabela: ACEITO, ACEITO EM PARTE ou
   REJEITADO, com justificativa. Implementa só o aceito e faz commit. A tabela
   fica em `avaliacao-<sessao>-rN.md`.
4. Na rodada seguinte o agy recebe a avaliação e não repete o que foi
   rejeitado com justificativa verificada.
5. No limite de rodadas com REVISAR, há uma avaliação final sem nova revisão,
   e o estado fica `aguardando` com essa mensagem.
6. O resumo final sugere `jangada-agente-fim --integrar SESSAO` e roda o
   gancho `pos-par`.

Depois de integrar uma mudança no próprio jangada, confira a cópia
instalada: `git -C ~/.local/share/jangada pull --ff-only` e
`jangada-migrar`.

## agy como agente da sessão

- O seletor do `jangada-agente` oferece o padrão e os perfis; o
  `default/agentes/agy.conf` vem no repositório e perde para um perfil de
  mesmo nome em `~/.config/jangada/agentes`.
- A tarefa vai por `-i`, precedida de `default/agy/protocolo.md`. Sem tarefa,
  vai só o protocolo. O agy não aceita a tarefa como argumento solto.
- Hooks do agy: só o global `~/.gemini/config/hooks.json` foi carregado pelo
  CLI nos testes de 22/09/2026. O `.agents/hooks.json` do projeto deu "loaded 0
  named hooks" no log (`~/.gemini/antigravity-cli/log/`). O hook roda com a
  pasta do `hooks.json` como diretório atual e herda o ambiente, inclusive
  `JANGADA_SESSAO`.
- **Não registre `PreToolUse` respondendo `{}`**: o agy trata como recusa e a
  ferramenta é negada ("tool call denied by pre-tool hook").
- O Stop traz `fullyIdle`, `terminationReason` e `error`; não traz a última
  resposta. No jq, `.fullyIdle // true` dá `true` mesmo com `false`.
- Chamadas auxiliares desligam os hooks da sessão: o `jangada-par` chama o agy
  com `env -u JANGADA_SESSAO`, e o `jangada-validar` chama o Claude com
  `JANGADA_HOOK_DESLIGADO=1`, que o `jangada-hook-claude` respeita.
- A confiança do agy na pasta é por caminho exato (`trustedWorkspaces` em
  `~/.gemini/antigravity-cli/settings.json`; confiar em `~` não cobre as
  subpastas). Todo worktree novo abre com a pergunta "Do you trust the
  contents of this project?", que o usuário responde na janela.
- Para testar hooks sem tocar no estado real, mude `XDG_STATE_HOME`; o
  `jangada-config` recalcula `JANGADA_ESTADO` a partir dele.

## Perfis e ganchos

- Perfil: `~/.config/jangada/agentes/NOME.conf` com `COMANDO=`, `ARGS=` e
  outras chaves em maiúsculas, que viram ambiente só daquela sessão (exemplo
  em `default/agentes/exemplo.conf`). O arquivo é lido, não executado.
  Use para outra conta, outro modelo ou outro agente.
- Ganchos: executável `~/.config/jangada/ganchos/EVENTO` ou arquivos em
  `EVENTO.d/`. Eventos: `pos-tema`, `pos-agente-fim`, `pos-par`,
  `pos-update`. Falha de gancho gera só aviso.
