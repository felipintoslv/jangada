---
name: jangada
description: >
  Use ao mexer na sessão jangada (Arch + Hyprland em Lua + camada de agentes):
  arquivos em ~/.config/jangada, ~/.local/share/jangada, ~/Projetos/jangada ou
  ~/.local/state/jangada; comandos jangada-*; atalhos, regras de janela,
  monitores, barra (waybar), tema (matugen), bloqueio (hyprlock, hypridle),
  tela de login (SDDM); sessões de agentes em tmux -L jangada, worktrees em
  ~/.local/share/jangada-worktrees, hooks do Claude Code e a revisão cruzada com o
  Antigravity (agy). Não use para configurar o niri, o Plasma ou ~/.config/hypr.
---

# jangada

Camada de configuração do Arch Linux com Hyprland (configuração em Lua) e uma
camada para lançar, acompanhar e encerrar agentes de IA. Cada assunto tem um
guia próprio nesta pasta; leia o que corresponde à tarefa antes de alterar
qualquer coisa:

| Assunto | Guia |
|---|---|
| Configuração Lua, `hyprctl`, atalhos, monitores, GPU, testar sem sair da sessão | [hyprland.md](hyprland.md) |
| Barra, tema e papel de parede, bloqueio, tela de login, escala | [interface.md](interface.md) |
| Sessões de agentes, estado, hooks, worktrees, `jangada-validar` e agy | [agentes.md](agentes.md) |

## Onde cada coisa fica

| Papel | Caminho |
|---|---|
| Repositório de trabalho (editar e fazer commit aqui) | `~/Projetos/jangada` |
| Cópia instalada (só `jangada-update`, nunca editar) | `~/.local/share/jangada` (`$JANGADA_PATH` na sessão) |
| Ajustes do usuário, carregados depois dos padrões | `~/.config/jangada` (`jangada.conf`, `hypr/hyprland.lua`, `hypr/usuario.lua`, `hypr/monitores.lua`) |
| Estado (sessões de agentes, pareceres) | `~/.local/state/jangada` |

Dentro do repositório, desde a modularização 3.0, cada arquivo mora na pasta
do seu módulo. Os caminhos antigos são links de compatibilidade versionados
e continuam sendo a forma de uso nos comandos, nos arquivos do usuário e
nestes guias.

| Módulo | Onde mora | Caminho antigo (link) |
|---|---|---|
| Core: sessões, isolamento, validação, delegação, fila, provedores | `core/bin`, `core/nucleo`, `core/orquestracao`, `core/delegacao`, `core/provedores`, `core/agentes` (`perfis`, `claude`, `agy`, `tmux`) | `bin/jangada-*`, `default/nucleo`, `default/orquestracao`, `default/delegacao`, `default/provedores`, `default/agentes`, `default/claude`, `default/agy`, `default/tmux` |
| Shell: área de trabalho e integração com bash e zsh | `shell/bin`, `shell/hyprland`, `shell/waybar`, `shell/temas`, `shell/menus`, `shell/integracoes`, `shell/jangada.sh`, `shell/jangada-shell.sh` | `bin/jangada-*`, `default/hypr`, `default/hypridle`, `default/waybar`, `default/matugen`, `default/sddm`, `default/logo`, `default/fastfetch`, `default/tarefas`, `default/conversa`, `default/snapper`, `default/r` |
| Monitor: painel, consumo, subagentes, diagnóstico | `monitor/bin`, `monitor/painel` | `bin/jangada-*`, `default/painel` |
| Compartilhado | `bin/jangada`, `bin/jangada-config`, `bin/jangada-gancho`, `bin/jangada-update`, `bin/jangada-migrar`, `bin/jangada-versao`, `bin/jangada-assinar`, `default/visual` | não mudou |

Pegadinhas dos links:

- Comando chamado pelo caminho real (`core/bin/jangada-fila`, por exemplo) não acha o
  `jangada-config`, que é procurado ao lado do próprio arquivo. Chame sempre
  por `bin/`. Pelo mesmo motivo, não passe `realpath` em caminho de comando.
- `Path(__file__).resolve()` no Python e `getwd()` no R devolvem a pasta
  física (`monitor/painel`, `shell/menus/tarefas`), não a de `default/`.
  Para achar a raiz, use `JANGADA_PATH`; para importar o núcleo,
  `JANGADA_CORE_PY`.
- Cópia de só uma parte do repositório (`cp -a bin`) leva links quebrados.
  Um teste que monta árvore temporária copia também `core/`, `shell/` e
  `monitor/`.
- No `git diff --stat -M`, mover um arquivo e deixar link no lugar aparece
  como mudança de modo; a renomeação aparece com `-M -B`.

O `jangada-update` busca a origem, mostra os commits novos e só aplica
(`--ff-only`) depois de o usuário confirmar num terminal; ele se recusa a rodar
com alterações locais na cópia instalada: por isso a edição acontece na cópia
de trabalho. Com `~/.config/jangada/allowed_signers`, só aplica commits
assinados; os do agente saem sem assinatura, e o usuário os assina com
`jangada-assinar` num terminal comum. O `jangada-agente-fim --integrar` não assina nem atualiza a cópia
instalada, só avisa para rodar o `jangada-update`. Git sobre pasta que um
agente pode ter gravado roda com `jangada_git_seguro` (`bin/jangada-config`),
que desliga fsmonitor, hooks, pager e `sshCommand` do repositório.

## Regras que não mudam

1. **Isolamento.** Nada do jangada escreve em `~/.config/hypr`, na
   configuração do niri ou em outra sessão. Padrões são lidos por `default/`
   (links para `core/`, `shell/` e `monitor/`), ajustes do usuário em
   `~/.config/jangada`.
2. **Padrão no repositório, ajuste no usuário.** Um gosto pessoal (atalho,
   teclado, monitor) vai para `~/.config/jangada/hypr/usuario.lua`, não para
   `default/hypr/`.
3. **Mudança que exige ajuste numa instalação existente** ganha uma migração
   em `migrations/AAAAMMDDHHMM-descricao.sh` (ver `migrations/README.md`).
4. **Antes de concluir**, rode `testes/verificar.sh` na cópia de trabalho.
5. **Testar a cópia de trabalho:** o shell da sessão herda `JANGADA_PATH`
   apontando para a cópia instalada. Rode com `JANGADA_PATH=$PWD bin/...`.
6. **Textos** em português, sem travessões, sem adjetivação desnecessária.
7. **Commits** sem linha `Co-Authored-By`.

## Diagnóstico rápido

- `jangada-verificar`: pacotes, snapshots, sessão, GPU escolhida e
  `hyprctl configerrors`.
- `jangada-atalhos --lista`: todos os atalhos ativos, lidos do compositor.
- Sessão que não sobe: `~/.cache/hyprland/hyprlandCrashReport*.txt`, não o
  journal.
