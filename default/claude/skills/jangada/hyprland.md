# Hyprland em Lua no jangada

## `hyprctl dispatch` só aceita Lua

Com a configuração em Lua, `hyprctl dispatch exec foo` dá erro de sintaxe. A
forma certa é uma expressão:

```sh
hyprctl dispatch 'hl.dsp.exec_cmd("foo")'
hyprctl dispatch 'hl.dsp.window.close()'
hyprctl dispatch 'hl.dsp.window.float({ action = "toggle" })'
hyprctl dispatch 'hl.dsp.focus({ window = "address:0x..." })'
hyprctl dispatch 'hl.dsp.workspace.toggle_special("agentes")'
hyprctl dispatch 'hl.dsp.exit()'
```

Os dispatchers são agrupados por área (`hl.dsp.window.*`,
`hl.dsp.workspace.*`); nomes soltos como `hl.dsp.togglefloating` não existem.
Um `hl.exec_cmd(...)` fora de `hl.dsp` executa, mas o `hyprctl` responde
"expected a dispatcher".

## Pegadinhas da API

- `hl.dsp.focus({ monitor = ... })` e `hl.dsp.window.move({ monitor = ... })`
  não aceitam letras de direção (`"l"`, `"r"`); só nome da saída, índice ou
  `"+1"`/`"-1"`.
- `"+1"`/`"-1"` de monitor anda pelo **id**, não pela posição na tela. Nesta
  máquina o id 0 é o DP-3, que fica à direita. Use o nome da saída.
- `hl.dsp.window.resize` só aceita `x` e `y` numéricos; porcentagem dá erro.
- Padrões de `class` e `title` em `hl.window_rule` são expressões regulares do
  Hyprland, não padrões do Lua.
- `hl.bind("SUPER + code:49", ...)` passa sem erro, mas o atalho fica com
  `key` vazio e `keycode` 0 e não dispara (0.56.2). Use um keysym que exista
  nos dois layouts em uso (`br` no padrão, `us intl` nesta máquina): a tecla à
  esquerda do 1 é `apostrophe` num e `dead_grave` no outro.
- `hyprctl binds -j` devolve JSON inválido. Use a saída de texto (é o que o
  `jangada-atalhos` faz).
- Atalhos novos usam `j.atalho(teclas, descrição, ação)` de
  `default/hypr/ajudantes.lua`, sempre com descrição: é ela que aparece no
  `SUPER + /`.

## Monitores desta máquina

HDMI-A-2 (2560x1080) à esquerda em x=0; DP-3 (4K, escala 2) à direita em
x=2560. O `position = "auto"` ordena por nome e inverte os dois, então
`~/.config/jangada/hypr/monitores.lua` fixa as posições. Escala inteira: a
fracionária somada a XWayland serrilha o texto. Aplicativo que roda em Wayland
nativo deve rodar assim.

## GPU

As duas telas saem da RTX 4060. O `jangada-sessao` define `AQ_DRM_DEVICES`
antes de o compositor subir, resolvendo `/dev/dri/by-path/...` para
`/dev/dri/cardN`: o aquamarine separa a lista por `:`, e o endereço PCI do
`by-path` também tem `:`. `GBM_BACKEND` fica de fora de propósito.

## Testar sem sair da sessão em uso

Suba um Hyprland aninhado com uma configuração de teste que carregue os
módulos de `default/hypr` **menos** `default.hypr.inicio` (chamado em
`default/hypr/jangada.lua`): ele roda
`dbus-update-activation-environment --systemd --all` e trocaria o ambiente da
sessão em uso. Acrescente `~/.config/jangada/hypr` ao `package.path`:

```sh
env -u HYPRLAND_INSTANCE_SIGNATURE WAYLAND_DISPLAY=wayland-1 \
  XDG_RUNTIME_DIR=/run/user/1000 JANGADA_PATH=$PWD \
  setsid -f Hyprland --config /caminho/teste/hyprland.lua
```

Confira `hyprctl configerrors` e `hyprctl binds`, e encerre com
`hyprctl dispatch 'hl.dsp.exit()'`. Limites: o aninhado usa o backend Wayland
e nunca toca no DRM, então não testa GPU nem `AQ_DRM_DEVICES`; num monitor
aninhado pequeno, janela maior que a tela fica com `x` negativo, e isso é o
centro correto. Para pausar num laço, use `sleep` dentro de
`timeout ... bash -c 'until ...'`, não `read -t`.
