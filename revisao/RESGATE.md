# Resgate das personalizações do Noctalia

Roteiro para levar ao jangada o que foi personalizado no Noctalia. Usa o
inventário gerado por `jangada-mapear` no desktop.

## Passo 1: gerar o mapa

```sh
~/.local/share/jangada/bin/jangada-mapear
```

O resultado fica em `mapeamento/<máquina>-<data>/`. Os arquivos principais são
`MAPA.md`, `noctalia/diferencas-do-padrao.txt` (opções alteradas),
`noctalia/qml-alteracoes.diff` (código QML alterado, se houver) e
`hyprland/atalhos.tsv` (atalhos ativos).

## Passo 2: decidir o destino de cada personalização

Há dois caminhos, que podem ser combinados:

1. **Manter o Noctalia dentro da sessão jangada** (`JANGADA_INTERFACE=noctalia`
   em `~/.config/jangada/jangada.conf`). As personalizações continuam valendo
   sem nenhuma conversão, e o jangada contribui com atalhos, agentes,
   snapshots e atualização. É o caminho sem perda e serve de ponto de partida.
2. **Converter para os componentes do jangada** (waybar, fuzzel, mako,
   hyprlock, matugen), item por item, quando houver vantagem clara.

## Passo 3: tabela de equivalências

Preencher com o agente, a partir do mapa:

| Personalização no Noctalia | Arquivo de origem | Destino no jangada | Decisão |
|---|---|---|---|
| módulos e ordem da barra | settings.json (bar) | default/waybar/config.jsonc ou manter Noctalia | |
| lançador (aparência, atalhos) | settings.json | fuzzel (modelo em default/matugen/modelos) | |
| notificações | settings.json | mako (modelo em default/matugen/modelos) | |
| tela de bloqueio | settings.json | hyprlock | |
| papel de parede e esquema de cores | settings.json, colors.json | jangada-tema com matugen | |
| atalhos do compositor | ~/.config/hypr | ~/.config/jangada/hypr/usuario.lua | |
| widgets ou QML alterados | qml-alteracoes.diff | etapa 2 (barra em Quickshell) | |
| plugins | ~/.config/noctalia/plugins | etapa 2 | |

## Passo 4: atalhos

A configuração atual está em hyprlang (`.conf`) ou em Lua? Se estiver em
`.conf`, cada atalho de `hyprland/atalhos.tsv` precisa ser reescrito na forma
`j.atalho("SUPER + X", "descrição", ação)` em `usuario.lua`. Conferir conflitos
com os atalhos padrão do jangada em `default/hypr/atalhos.lua`.
