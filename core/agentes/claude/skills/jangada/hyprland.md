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
- `"+1"`/`"-1"` de monitor anda pelo **id**, não pela posição na tela: o id 0
  pode ser a tela da direita. Use o nome da saída.
- `hl.dsp.window.resize` só aceita `x` e `y` numéricos; porcentagem dá erro.
- Padrões de `class` e `title` em `hl.window_rule` são expressões regulares do
  Hyprland, não padrões do Lua.
- `hl.bind("SUPER + code:49", ...)` passa sem erro, mas o atalho fica com
  `key` vazio e `keycode` 0 e não dispara (0.56.2). Use um keysym que exista
  nos layouts em uso (`br` é o padrão; `us intl` é comum): a tecla à esquerda
  do 1 é `apostrophe` num e `dead_grave` no outro.
- `hyprctl binds -j` devolve JSON inválido. Use a saída de texto (é o que o
  `jangada-atalhos` faz).
- Atalhos novos usam `j.atalho(teclas, descrição, ação)` de
  `default/hypr/ajudantes.lua`, sempre com descrição: é ela que aparece no
  `SUPER + /`.

## Monitores

`position = "auto"` ordena as saídas pelo nome, o que pode inverter a ordem
física. As posições de cada máquina ficam em
`~/.config/jangada/hypr/monitores.lua`, nunca em `default/`. Quem vem do niri
gera um ponto de partida com `jangada-importar` (grava
`monitores.lua.importado`). Prefira escala inteira: a fracionária somada a
XWayland serrilha o texto. Fonte da barra por monitor vai em
`~/.config/jangada/waybar/style.css`, com o seletor `window#waybar.NOME`.

## GPU

Com mais de uma placa, o `jangada-sessao` escolhe a que tem monitor ligado
(ou a de `JANGADA_GPU`) e define `AQ_DRM_DEVICES` antes de o compositor subir,
resolvendo `/dev/dri/by-path/...` para `/dev/dri/cardN`: o aquamarine separa a
lista por `:`, e o endereço PCI do `by-path` também tem `:`. `GBM_BACKEND`
fica de fora de propósito. Na NVIDIA, `jangada-update` confere se o módulo
carregado, `nvidia-utils` e `lib32-nvidia-utils` estão na mesma versão.

## Testar sem sair da sessão em uso

Rode `testes/aninhado.sh` na cópia de trabalho. Ele sobe um Hyprland aninhado
com os módulos de `default/hypr` e os seus ajustes (`--sem-usuario` carrega só
os padrões), confere `hyprctl configerrors` e o número de atalhos e encerra a
instância. Para testar outro `usuario.lua`, aponte `XDG_CONFIG_HOME` para uma
pasta com `jangada/hypr/usuario.lua`.

O teste deixa de fora `default.hypr.inicio`: ele roda
`dbus-update-activation-environment --systemd --all` e trocaria o ambiente da
sessão em uso. Limites: o aninhado usa o backend Wayland e nunca toca no DRM,
então não testa GPU nem `AQ_DRM_DEVICES`; num monitor aninhado pequeno, janela
maior que a tela fica com `x` negativo, e isso é o centro correto. Para
pausar num laço, use `sleep` dentro de `timeout ... bash -c 'until ...'`, não
`read -t`.
