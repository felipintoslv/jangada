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
| Cópia instalada (só `git pull`, nunca editar) | `~/.local/share/jangada` (`$JANGADA_PATH` na sessão) |
| Ajustes do usuário, carregados depois dos padrões | `~/.config/jangada` (`jangada.conf`, `hypr/hyprland.lua`, `hypr/usuario.lua`, `hypr/monitores.lua`) |
| Estado (sessões de agentes, pareceres) | `~/.local/state/jangada` |

O `jangada-update` faz `git pull --ff-only` na cópia instalada e se recusa a
rodar com alterações locais: por isso a edição acontece na cópia de trabalho.

## Regras que não mudam

1. **Isolamento.** Nada do jangada escreve em `~/.config/hypr`, na
   configuração do niri ou em outra sessão. Padrões vão em `default/`, ajustes
   do usuário em `~/.config/jangada`.
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
