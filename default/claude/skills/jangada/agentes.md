# Camada de agentes

## Peças

| Peça | Papel |
|---|---|
| `jangada-agente` | escolhe projeto, cria worktree `agente/<nome>` e abre o agente numa sessão `tmux -L jangada`; `--prompt`/`--prompt-arquivo` já entregam a tarefa, `--perfil` escolhe o agente |
| `jangada-worktree-preparar` | copia para o worktree novo os ignorados do `.worktreeinclude`, liga o que está em `.jangada/links` e roda `.jangada/preparar.sh` |
| `jangada-hook-claude` | chamado pelos hooks do Claude Code; grava o estado e notifica |
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
`claude --resume <conversa>`, ou `--continue` se o id faltar. O ambiente de um
perfil é relido de `~/.config/jangada/agentes/NOME.conf` na restauração, nunca
guardado no estado.

## Hooks do Claude Code

`default/claude/hooks.json` é mesclado em `~/.claude/settings.json` pela
instalação e pela migração, por evento, sem duplicar (a chave é o comando sem
o caminho até `/bin/`). Eventos: `UserPromptSubmit` (trabalhando),
`Notification` (aguardando; `auth_success` é ignorado e `idle_prompt` vira
concluído sem aviso), `Stop` (concluído), `SessionStart` (iniciado) e
`SessionEnd` (concluído; `reason=clear` não muda o estado). Todo evento grava
`conversa` com o `session_id`. `jangada-verificar` confere cada evento.

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

## Fluxo do `jangada-par`

1. Claude implementa e faz commit.
2. agy revisa o diff e responde `STATUS: APROVADO` ou `STATUS: REVISAR` com
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

## Perfis e ganchos

- Perfil: `~/.config/jangada/agentes/NOME.conf` com `COMANDO=`, `ARGS=` e
  outras chaves em maiúsculas, que viram ambiente só daquela sessão (exemplo
  em `default/agentes/exemplo.conf`). O arquivo é lido, não executado.
  Use para outra conta, outro modelo ou outro agente.
- Ganchos: executável `~/.config/jangada/ganchos/EVENTO` ou arquivos em
  `EVENTO.d/`. Eventos: `pos-tema`, `pos-agente-fim`, `pos-par`,
  `pos-update`. Falha de gancho gera só aviso.
