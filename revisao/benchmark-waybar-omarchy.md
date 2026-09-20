# Comparação entre a barra do jangada e a do Omarchy

Documento de consulta. Nada aqui foi aplicado.

Lado jangada: `default/waybar/config.jsonc`, `default/waybar/base.css`,
`default/waybar/style.css.modelo`, `default/matugen/`, `bin/jangada-*`,
`install/pacotes/`.

Lado Omarchy: clone raso em `referencia/omarchy`, versão `4.0.0.alpha`
(`referencia/omarchy/version`). A pasta `referencia/` está no `.gitignore` e
não entra no commit.

## Aviso sobre o que é o "arquivo equivalente"

O Omarchy 4 não usa mais waybar. A barra dele é um conjunto de componentes
QML carregados pelo Quickshell: o motor está em
`referencia/omarchy/shell/plugins/bar/Bar.qml` e a lista de módulos fica em
`referencia/omarchy/config/omarchy/shell.json` (linhas 7 a 67), que é o
equivalente funcional do `default/waybar/config.jsonc`. A única menção a
waybar que sobrou é o formato de saída aceito por módulos de usuário
(`referencia/omarchy/shell/plugins/bar/README.md`, linhas 102 a 106) e o
caminho de migração em `referencia/omarchy/bin/omarchy-upgrade-to-quattro`.

Isso muda o peso da comparação: o que dá para copiar é a lista de recursos e
o desenho de interação, não o arquivo de configuração.

## 1. Tabela módulo a módulo

Coluna "jangada" cita `default/waybar/config.jsonc`. Coluna "Omarchy" cita o
caminho dentro de `referencia/omarchy`.

| Assunto | jangada hoje | Omarchy hoje | Falta no jangada | Falta no Omarchy |
|---|---|---|---|---|
| Áreas de trabalho | `hyprland/workspaces`, linhas 21 a 26: `{name}`, clique ativa, mostra especiais visíveis | `omarchy.workspaces` em `config/omarchy/shell.json:17`; `shell/plugins/bar/widgets/Workspaces.qml:20-31` sempre desenha 1 a 5 e acrescenta as ocupadas até 10; clique chama `hl.dsp.focus` (linhas 33 a 36) | Piso fixo de áreas visíveis mesmo vazias | Áreas especiais (`show-special`, linha 24) |
| Agentes | `custom/agentes`, linhas 28 a 36: `bin/jangada-agentes --waybar` a cada 3s, clique abre a lista, clique direito abre o painel | `omarchy.agents` em `config/omarchy/shell.json:48`; `shell/plugins/agents/README.md:1-8` e `manifest.json:20-31` (intervalo padrão 900s, três coletores) | Limites de cota, gasto por dia e por modelo; o módulo sumir sozinho quando não há nada a dizer (`shell/plugins/agents/README.md:28-37`) | Sessões de agente vivas na máquina, com estado `aguardando`/`trabalhando` (`bin/jangada-agentes:149-157`) |
| Relógio | `clock`, linhas 38 a 43: `{:%a %d/%m  %H:%M}`, dica com calendário, `locale` `pt_BR.UTF-8`, clique abre `bin/jangada-calendario` | `omarchy.clock` em `config/omarchy/shell.json:28-32` com `format`, `formatAlt` e `verticalFormat`; painel em `shell/plugins/panels/clock/Panel.qml` com grade do mês, semana ISO e passo de mês (linhas 337, 549, 598, 743, 754) | Alternar formato no clique direito; seletor de fuso no clique do meio (`shell/plugins/bar/README.md:59`) | Locale explícito no arquivo de configuração |
| Processador | `cpu`, linhas 45 a 50: `{usage}%` a cada 2s, clique abre `bin/jangada-monitor` | Não existe. Nenhum arquivo em `shell/` cita `cpu` | Nada | Uso de processador na barra |
| Memória | `memory`, linhas 52 a 57 | Não existe | Nada | Uso de memória na barra |
| Temperatura | `temperature`, linhas 59 a 74: lista fixa de seis caminhos `hwmon`, limite 80 graus | Não existe. Nenhum arquivo em `shell/` cita `hwmon`, `thermal` ou `temperatureC` | Nada | Temperatura na barra |
| Rede | `network`, linhas 76 a 84: ícone e nome da rede, banda na dica, clique abre `bin/jangada-rede` (fuzzel), clique direito abre o monitor | `omarchy.network` em `config/omarchy/shell.json:54`; `shell/plugins/panels/network/manifest.json:3-7`; painel com varredura de Wi-Fi, sinal, conexão, escolha de DNS (`shell/plugins/panels/network/Panel.qml:1543-1567`), QR do Wi-Fi (linha 1196), teste de velocidade (linha 1212) e portal cativo (linha 1317) | Escolha de DNS, QR do Wi-Fi, teste de velocidade | Banda instantânea no rótulo e na dica |
| Bluetooth | `bluetooth`, linhas 86 a 95: ícone, contagem de conectados, dica com os aparelhos, clique abre `bin/jangada-bluetooth`, clique direito abre o menu | `omarchy.bluetooth` em `config/omarchy/shell.json:51`; `shell/plugins/panels/bluetooth/manifest.json:3-7`; clique esquerdo abre painel e direito liga ou desliga o rádio (`shell/plugins/bar/README.md:72`) | Ligar e desligar o rádio direto do clique direito; bateria do aparelho no painel (`shell/plugins/bar/README.md:72`) | Nada de relevante |
| Áudio, saída | `pulseaudio`, linhas 97 a 110: ícone e volume, rolagem de 5 em 5, clique muda mudo, clique direito escolhe o dispositivo com fuzzel | `omarchy.audio` em `config/omarchy/shell.json:57`; `shell/plugins/panels/audio/manifest.json:3-7`: controle deslizante, escolha de saída e mesa por programa; clique abre painel, direito muda mudo, rolagem muda volume (`shell/plugins/bar/README.md:67`) | Volume por programa; painel no lugar do menu de linha | Nada de relevante |
| Áudio, microfone | `pulseaudio#microfone`, linhas 112 a 120: volume da fonte, rolagem de 5 em 5, clique muda mudo, clique direito escolhe a entrada | `omarchy.microphone`, `shell/plugins/bar/widgets/Microphone.qml:41-52`: ícone muda com o mudo, `active` quando há captura em curso (linha 25), clique do meio abre o painel de áudio, rolagem de 5% | Aviso visual de microfone em uso por algum programa (`Microphone.qml:16-25`) | Escolher a entrada pelo clique direito |
| Bateria | `battery`, linhas 122 a 126: ícone e porcentagem, estados `aviso` 25 e `critico` 10, sem ação de clique | `omarchy.power` em `config/omarchy/shell.json:63`; `shell/plugins/panels/power/manifest.json:3-7`: bateria, perfil de energia e dados do sistema; clique abre painel, direito alterna a porcentagem | Qualquer ação de clique; perfil de energia | Nada de relevante |
| Bandeja | `tray`, linha 128: só `spacing: 8` | `omarchy.tray` em `config/omarchy/shell.json:45`; `shell/plugins/bar/widgets/Tray.qml:821-846`: esquerdo ativa, meio ativa o secundário, direito abre o menu do programa, rolagem repassa o evento; gaveta que abre ao passar o ponteiro | Menu secundário, rolagem e gaveta | Nada de relevante |
| Janela em foco | Não existe | `omarchy.active-window`, `shell/plugins/bar/widgets/ActiveWindow.manifest.json:3`, com os três botões tratados em `ActiveWindow.qml:48-51` | Módulo inteiro | Nada |
| Tocador de mídia | Não existe. `playerctl` está instalado (`install/pacotes/interface.txt:18`) e só é usado nos atalhos (`default/hypr/atalhos.lua:77-80`) | `omarchy.media`, `shell/plugins/services/media/manifest.json:3`; rótulo rolante, capa no painel, clique toca e pausa, meio avança, rolagem troca faixa (`shell/plugins/bar/README.md:60`) | Módulo inteiro | Nada |
| Atualizações | Não existe. `checkupdates` já entra pelo `pacman-contrib` (`install/pacotes/base.txt:6`) | `omarchy.system-update`, `shell/plugins/bar/widgets/SystemUpdate.qml:39-50`: roda `omarchy-update-available` a cada 6 horas e só aparece quando há o que atualizar | Módulo inteiro | Nada |
| Disposição do teclado | Não existe | `omarchy.keyboard-layout` em `config/omarchy/shell.json:34`; `shell/plugins/bar/widgets/KeyboardLayout.qml:26-29` só aparece com duas ou mais disposições | Módulo inteiro | Nada |
| Indicadores de estado | Não existe | `omarchy.indicators` em `config/omarchy/shell.json:22`; `shell/plugins/bar/indicators/` traz `Dnd.qml`, `NightLight.qml`, `ScreenRecording.qml`, `StayAwake.qml`, `Dictation.qml` e `Reminder.qml` | Não perturbe, luz noturna, inibidor de repouso e aviso de gravação | Nada |
| Menu do sistema | Não existe na barra. `jangada-menu` só é alcançado por atalho (`default/hypr/atalhos.lua:16`) | `omarchy.menu` em `config/omarchy/shell.json:14`; esquerdo abre o menu, direito abre o terminal (`shell/plugins/bar/README.md:57`) | Ponto de entrada do menu na barra | Nada |
| Brilho e telas | Não existe. `brightnessctl` está instalado (`install/pacotes/interface.txt:17`) | `omarchy.monitor` em `config/omarchy/shell.json:60`; `shell/plugins/panels/monitor/Panel.qml:474` com rolagem de brilho e escala por tela (linha 849) | Controle de brilho na barra | Nada |
| Tempo, clima | Não existe | `omarchy.weather` em `config/omarchy/shell.json:37`; `shell/plugins/panels/weather/manifest.json` | Módulo inteiro | Nada |
| Tailscale, Dropbox, teste de disco | Não existem | `shell/plugins/panels/tailscale/`, `shell/plugins/panels/dropbox/`, `shell/plugins/panels/disk-speedtest/` | Nada que caiba (ver parte 5) | Nada |
| Espaçador | `spacing: 6` global (linha 6) | `omarchy.spacer` com `size` por instância (`shell/plugins/bar/README.md:35`, `widgets/Spacer.manifest.json:3`) | Espaçamento por posição | Nada |

### Classe sem estilo

`bin/jangada-agentes:149` emite a classe `ativo` quando há sessão viva sem
ninguém esperando, mas `default/waybar/base.css` só tem regra para
`aguardando` (linha 29), `trabalhando` (linha 34), `concluido` (linha 41) e
`vazio` (linha 46). O estado `ativo` cai no texto padrão da barra.

O mesmo vale para `battery`: `config.jsonc:125` declara o estado `aviso`, mas
`base.css` só pinta `#battery.critico` (linha 60).

## 2. Estilo: `base.css` contra o estilo do Omarchy

### Como o jangada recebe as cores

1. `default/matugen/config.toml:14-16` manda o matugen gerar
   `~/.config/jangada/waybar/cores.css` a partir de
   `default/matugen/modelos/waybar.css`.
2. Esse modelo define seis nomes de cor (linhas 2 a 7): `superficie`, `texto`,
   `texto_suave`, `primaria`, `texto_primario` e `atencao`, todos vindos dos
   papéis do Material You (`surface`, `on_surface`, `on_surface_variant`,
   `primary`, `on_primary`, `tertiary`).
3. `default/waybar/style.css.modelo:3-4` importa `cores.css` e depois
   `base.css`. `install/40-interface.sh:12-20` copia esse modelo para
   `~/.config/jangada/waybar/style.css` uma única vez, trocando
   `@JANGADA_PATH@`, e nunca mais mexe nele.
4. `bin/jangada-tema:34` manda `SIGUSR2` na waybar a cada troca de papel de
   parede, que é o sinal de recarregar estilo.
5. `bin/jangada-barra:8-14` usa `$JANGADA_CONFIG/waybar/style.css` quando
   existe e cai para a configuração sem estilo quando não existe.

O resultado é que `base.css` nunca escreve um valor de cor literal: tudo é
`@nome` do `cores.css` (linhas 9, 10, 15, 20, 21, 30, 31, 35, 42, 43, 47, 55,
61). O comentário em `base.css:38-40` registra a razão de não inventar nome
novo: um `cores.css` antigo não teria o nome, e a regra ficaria sem cor.

### Como o Omarchy recebe as cores

1. Não existe matugen em lugar nenhum do clone. As cores vêm de temas fixos em
   `referencia/omarchy/themes/`, vinte e dois deles, cada um com um
   `colors.toml` (por exemplo `themes/tokyo-night/colors.toml`).
2. `shell/Commons/Color.qml:226` lê
   `~/.local/state/omarchy/current/theme/colors.toml` e
   `shell/Commons/Color.qml:135-165` extrai quatro cores de base:
   `foreground`, `background`, `accent` e `urgent`, com recuo para `color0`,
   `color4`, `color7` e `color8` quando o tema não declara os nomes.
3. Os papéis por superfície vêm de um segundo arquivo, `shell.toml`
   (`Color.qml:233`), gerado de `default/themed/shell.toml.tpl`. A seção
   `[bar]` desse modelo (linhas 5 a 17) define `background`,
   `background-alpha`, `text`, `active`, `scale-with-font`, `size-horizontal`
   e `size-vertical`.
4. `Color.qml:73-77` expõe isso como `Color.bar.background`, `Color.bar.text`
   e `Color.bar.active`, com recuo para as cores de base quando a chave não
   existe. É o mesmo cuidado do comentário de `base.css:38-40`, feito em
   código em vez de em comentário.

### Diferenças de estilo propriamente dito

| Ponto | jangada | Omarchy |
|---|---|---|
| Linguagem | CSS do GTK, 62 linhas em `default/waybar/base.css` | QML mais um dicionário TOML; `shell/Commons/Style.qml` tem 515 linhas |
| Fonte | fixa em `base.css:3`: `"JetBrainsMono Nerd Font", sans-serif`, 13px em `base.css:4` | `Style.qml:269` usa o apelido `monospace` do fontconfig, e `Style.qml:279` guarda `fontBaseSize` 12, ajustável pelo tema |
| Escala tipográfica | um tamanho só | oito degraus nomeados em `Style.qml:327-334`, de `caption` a `displayLarge`, todos múltiplos de `fontBaseSize` |
| Altura da barra | fixa, `config.jsonc:5`, 28px | `Style.qml:341-347`: 26 na horizontal, 28 na vertical, e `barToken` (linhas 296 a 303) multiplica pela escala da fonte quando `scale-with-font` está ligado |
| Espaçamento | um `spacing: 6` global (`config.jsonc:6`) mais `padding: 0 8px` (`base.css:51`) e `0 10px` para agentes (`base.css:25`) | dez degraus nomeados em `Style.qml:234-243`, mais dezesseis medidas de componente (linhas 245 a 260) |
| Cantos | `border-radius: 6px` em dois lugares (`base.css:16`, `base.css:26`) | tokens de controle em `default/themed/shell.toml.tpl:26-66`, com estados `normal`, `hover-cursor`, `focus` e `selected` |
| Transparência | fixa, `alpha(@superficie, 0.92)` em `base.css:9` | `background-alpha` no tema (`shell.toml.tpl:8`) e um modo transparente que o usuário liga na hora (`Bar.qml:847-858`) |
| Cor de alerta | `@atencao`, usada para microfone mudo, temperatura crítica e bateria crítica (`base.css:58-61`) | `bar.active` para "módulo pedindo atenção" (`shell.toml.tpl:12-13`) e `urgent` separado |
| Personalização do usuário | editar `~/.config/jangada/waybar/style.css`, que só importa os dois arquivos | `~/.config/omarchy/shell.toml` sobrepõe o do tema, com mescla (`Color.qml:204-220`) |

O ponto forte do jangada aqui é que as cores acompanham o papel de parede,
coisa que o Omarchy não faz. O ponto fraco é que não há escala: cada medida é
um número solto no arquivo.

## 3. Interação: clique, clique direito e rolagem

### jangada

| Módulo | Esquerdo | Direito | Rolagem | Para onde leva |
|---|---|---|---|---|
| `hyprland/workspaces` | `activate` (`config.jsonc:23`) | nada | nada | troca de área |
| `custom/agentes` | `jangada-agentes --janela` (linha 33) | `jangada-agentes --painel` (linha 34) | nada | terminal com a lista (`bin/jangada-agentes:163`); painel na área especial `agentes` (`bin/jangada-agentes:166-171`) |
| `clock` | `jangada-calendario` (linha 42) | nada | nada | janela Qt do calendário (`bin/jangada-calendario:9-22`) |
| `cpu` | `jangada-monitor` (linha 49) | nada | nada | btop ou htop em janela flutuante (`bin/jangada-monitor:9-16`) |
| `memory` | `jangada-monitor` (linha 56) | nada | nada | o mesmo |
| `temperature` | `jangada-monitor` (linha 73) | nada | nada | o mesmo |
| `network` | `jangada-rede` (linha 82) | `jangada-monitor` (linha 83) | nada | menu fuzzel de redes (`bin/jangada-rede:43-95`); monitor |
| `bluetooth` | `jangada-bluetooth` (linha 93) | `jangada-bluetooth menu` (linha 94) | nada | menu fuzzel de aparelhos (`bin/jangada-bluetooth:33-48`) |
| `pulseaudio` | `wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle` (linha 107) | `jangada-audio saida` (linha 108) | volume, passo 5 (linha 106) | menu fuzzel de saídas (`bin/jangada-audio:68-80`) |
| `pulseaudio#microfone` | mudo da fonte (linha 116) | `jangada-audio entrada` (linha 117) | volume, passo 5 (linha 118) | menu fuzzel de entradas (`bin/jangada-audio:88-100`) |
| `battery` | nada | nada | nada | nada |
| `tray` | padrão da waybar | padrão da waybar | padrão da waybar | o programa da bandeja |

Três observações. Primeira: o clique direito do `network` leva ao monitor de
sistema, que não tem relação com rede; é o único lugar onde o botão direito
abre algo de outro assunto. Segunda: `battery` é o único módulo sem nenhuma
ação. Terceira: rolagem só existe nos dois módulos de áudio.

### Omarchy

Catálogo em `referencia/omarchy/shell/plugins/bar/README.md:55-74`, com os
pontos confirmados no código onde citado.

| Módulo | Esquerdo | Direito | Meio | Rolagem |
|---|---|---|---|---|
| `omarchy.menu` | menu | terminal | nada | nada |
| `omarchy.workspaces` | foca a área (`widgets/Workspaces.qml:33-36`) | nada | nada | nada |
| `omarchy.clock` | painel | alterna o formato | seletor de fuso | passo de mês dentro do painel (`panels/clock/Panel.qml:549`) |
| `omarchy.media` | toca ou pausa | painel | próxima | faixa anterior e próxima |
| `omarchy.tray` | ativa (`widgets/Tray.qml:838-841`) | menu do programa (`Tray.qml:826-829`) | ação secundária (`Tray.qml:836`) | repassa ao programa (`Tray.qml:843-845`) |
| `omarchy.microphone` | muda o mudo (`widgets/Microphone.qml:46`) | nada | painel de áudio (`Microphone.qml:45`) | volume da fonte, passo 5% (`Microphone.qml:48-52`) |
| `omarchy.audio` | painel | mudo | painel | volume |
| `omarchy.network` | painel | nada | nada | nada |
| `omarchy.bluetooth` | painel | liga ou desliga o rádio | nada | nada |
| `omarchy.power` | painel | alterna a porcentagem | nada | nada |
| `omarchy.monitor` | painel | nada | nada | brilho (`panels/monitor/Panel.qml:474`) |
| `omarchy.agents` | painel | lança o agente | próxima assinatura | nada |
| `omarchy.system-update` | atualiza (`widgets/SystemUpdate.qml:20-22`) | nada | nada | nada |

Além dos módulos, a própria barra responde a gestos, em `Bar.qml`:

- Arrastar espaço vazio, ou segurar 200ms e arrastar, move a barra para a
  borda mais próxima da tela (`Bar.qml:1648-1656`, `1665-1670`, `1672-1683`,
  `finishBarMove` em `487-514`).
- Dois cliques esquerdos no espaço vazio do centro ligam e desligam a
  transparência (`Bar.qml:1707-1714`, `toggleTransparency` em `847-858`).
- Arrastar um módulo reordena a barra, e a nova ordem é gravada no
  `shell.json` do usuário (`shell/plugins/bar/README.md:19`).
- A barra vira vertical nas bordas esquerda e direita, e os módulos com texto
  caem para forma só de ícone (`shell/plugins/bar/README.md:79`,
  `Bar.qml:555-556`).

Há também um coordenador de janela flutuante única,
`bar.requestPopout` e `bar.releasePopout`
(`shell/plugins/bar/README.md:166`), para que dois painéis não fiquem abertos
ao mesmo tempo. O jangada não precisa disso porque o fuzzel já é exclusivo.

## 4. Melhorias propostas, da mais barata para a mais cara

### 4.1. Estilizar a classe `ativo` dos agentes

Arquivos: `default/waybar/base.css`.
O que fazer: acrescentar `#custom-agentes.ativo` usando `@primaria` ou
`@texto`, cores que já existem em `default/matugen/modelos/waybar.css:3` e `:5`.
Risco: nenhum. Pacote: nenhum.
Motivo: `bin/jangada-agentes:149` emite essa classe e `base.css` a ignora.

### 4.2. Estilizar o estado `aviso` da bateria

Arquivos: `default/waybar/base.css`.
O que fazer: regra para `#battery.aviso` com `@atencao`, e `#battery.critico`
ganhando `font-weight: bold` para separar dos dois. O estado já está
declarado em `config.jsonc:125`.
Risco: nenhum. Pacote: nenhum.

### 4.3. Dar ação de clique à bateria

Arquivos: `default/waybar/config.jsonc`.
O que fazer: `on-click` para `bin/jangada-monitor`, como já fazem `cpu`,
`memory` e `temperature` (linhas 49, 56 e 73). Alternativa melhor, mas mais
cara, na proposta 4.11.
Risco: nenhum. Pacote: nenhum.

### 4.4. Ajustar o clique direito da rede

Arquivos: `default/waybar/config.jsonc`.
O que fazer: trocar `jangada-monitor` (linha 83) por algo de rede. O
`bin/jangada-rede:95` já sabe abrir o `nmtui` em terminal; seria o destino
natural do botão direito.
Risco: baixo, muda um comportamento que alguém pode ter decorado.
Pacote: `nmtui` vem no mesmo pacote do `nmcli` (ver 4.7).

### 4.5. Completar a bandeja

Arquivos: `default/waybar/config.jsonc` (bloco `tray`, linha 128),
`default/waybar/base.css`.
O que fazer: `icon-size`, `show-passive-items` e `reverse-direction`. O
Omarchy expõe uma gaveta de bandeja inteira (`widgets/Tray.qml`); a waybar não
tem gaveta, mas tem esses três ajustes.
Risco: nenhum. Pacote: nenhum.

### 4.6. Inibidor de repouso na barra

Arquivos: `default/waybar/config.jsonc`, `default/waybar/base.css`.
O que fazer: módulo `idle_inhibitor` da própria waybar, com
`format-icons` e uma regra `#idle_inhibitor.activated` usando `@atencao`.
Equivale ao indicador `StayAwake` do Omarchy
(`shell/plugins/bar/indicators/StayAwake.qml`).
Risco: baixo. Pacote: nenhum, é módulo embutido da waybar. Convive com o
`hypridle` já instalado (`install/pacotes/interface.txt:7`).

### 4.7. Fechar a lista de pacotes

Arquivos: `install/pacotes/interface.txt`.
O que fazer: acrescentar os pacotes apurados na parte 4.13 abaixo.
Risco: médio, porque instalar `networkmanager` numa máquina que usa outro
gerenciador de rede é intrusivo. A regra 1 do `AGENTS.md` fala de arquivos de
configuração, não de pacotes, mas o espírito é o mesmo: o pacote pode entrar,
o serviço não deve ser ligado pelo instalador sem aviso. Proposta concreta:
listar os pacotes e deixar qualquer `systemctl enable` fora do instalador.
Pacote: é a própria proposta.

### 4.8. Módulo de atualizações pendentes

Arquivos: `default/waybar/config.jsonc`, `default/waybar/base.css`,
`bin/jangada-atualizacoes` (novo).
O que fazer: `custom/atualizacoes` com `return-type: json`, intervalo longo
(o Omarchy usa 6 horas, `widgets/SystemUpdate.qml:45-50`), texto vazio quando
não há nada, e clique abrindo `bin/jangada-update` em terminal. O Omarchy
esconde o módulo quando não há atualização (`SystemUpdate.qml:23`); na waybar
isso se faz devolvendo `{"text":""}`.
Risco: baixo. Pacote: nenhum novo, `checkupdates` já vem do `pacman-contrib`
(`install/pacotes/base.txt:6`).

### 4.9. Módulo de mídia

Arquivos: `default/waybar/config.jsonc`, `default/waybar/base.css`.
O que fazer: módulo `mpris` da waybar em `modules-center`, ao lado do relógio,
com `max-length`, clique para tocar e pausar, rolagem para trocar faixa. É o
`omarchy.media` (`shell/plugins/services/media/manifest.json:3`).
Risco: baixo; o `mpris` da waybar fica vazio quando não há tocador.
Pacote: nenhum novo, `playerctl` já está em `install/pacotes/interface.txt:18`.
Confirmar antes que a waybar do Arch traz `mpris` compilado.

### 4.10. Janela em foco

Arquivos: `default/waybar/config.jsonc`, `default/waybar/base.css`.
O que fazer: `hyprland/window` entre `custom/agentes` e o centro, com
`max-length` e `separate-outputs`. É o `omarchy.active-window`
(`widgets/ActiveWindow.manifest.json:3`).
Risco: baixo, mas rouba largura do centro; conferir com a barra de 28px
(`config.jsonc:5`).
Pacote: nenhum.

### 4.11. Menu de energia no clique da bateria

Arquivos: `default/waybar/config.jsonc`, `bin/jangada-energia` (novo).
O que fazer: menu fuzzel com perfil de energia (`powerprofilesctl`), estado da
bateria e ações de sessão, no padrão de `bin/jangada-rede` e
`bin/jangada-bluetooth`. Equivale ao painel `omarchy.power`
(`shell/plugins/panels/power/manifest.json:3-7`).
Risco: médio, é script novo com caminho de erro próprio.
Pacote: `power-profiles-daemon`, que não está em nenhum arquivo de
`install/pacotes/`. O script deve degradar sem ele, como
`bin/jangada-bluetooth:120` faz com o `blueman-manager`.

### 4.12. Temperatura sem número de `hwmon` no arquivo

Arquivos: `default/waybar/config.jsonc` (linhas 59 a 74) e possivelmente
`bin/jangada-barra`.
O que fazer: a lista de `config.jsonc:61-68` fixa `hwmon3`, `hwmon2`,
`hwmon4`, `hwmon5` e `hwmon6` nessa ordem, e a numeração de `hwmon` não é
estável entre partidas. Trocar por `hwmon-path-abs` mais `input-filename`, que
resolve por nome de dispositivo, ou gerar o caminho na partida da barra.
Risco: médio, porque a correção certa depende do equipamento e não dá para
validar sem reiniciar a barra, o que está fora do escopo desta tarefa.
Pacote: nenhum. Migração: pela regra 5 do `AGENTS.md`, quem já tem
`config.jsonc` copiado em `~/.config/jangada` precisa de uma migração em
`migrations/`.

### 4.13. Cobrir o locale `pt_BR.UTF-8`

Arquivos: `install/00-verificacoes.sh` ou etapa nova, `testes/verificar.sh`.
O que fazer: `config.jsonc:41` exige `pt_BR.UTF-8` e nada em `install/` gera
esse locale. Quando falta, a waybar cai para o formato do sistema sem avisar.
Mínimo aceitável: avisar na verificação. Máximo: descomentar a linha em
`/etc/locale.gen` e rodar `locale-gen`, o que exige `copia_seguranca` pela
regra 3 e `como_root` pela regra 2 do `AGENTS.md`.
Risco: alto na versão que escreve em `/etc`; nenhum na versão que só avisa.
Pacote: nenhum, é `glibc`.

### 4.14. Escala de medidas no CSS

Arquivos: `default/matugen/modelos/waybar.css`, `default/waybar/base.css`,
`default/waybar/config.jsonc`.
O que fazer: o Omarchy tira toda medida de tokens nomeados
(`Style.qml:234-243` para espaço, `327-334` para tipografia). O CSS do GTK
usado pela waybar não tem variáveis de tamanho, só `@define-color`, então a
cópia direta não existe. O que dá para fazer é reduzir os números soltos a um
conjunto pequeno e documentado no topo de `base.css`, e alinhar `spacing`
(`config.jsonc:6`), `padding` (`base.css:51`) e `border-radius`
(`base.css:16`) a esse conjunto.
Risco: baixo em função, alto em revisão visual, porque mexe em tudo.
Pacote: nenhum.

### 4.15. Barra vertical e reposicionável

Arquivos: `default/waybar/config.jsonc`, `default/waybar/base.css`,
`bin/jangada-barra`, `default/hypr/atalhos.lua`.
O que fazer: o Omarchy troca de borda por gesto (`Bar.qml:487-514`). A waybar
não tem gesto, mas aceita `"position"` e reinicia rápido; daria para expor
`jangada-barra --posicao esquerda` gravando a escolha em
`~/.config/jangada/jangada.conf`.
Risco: alto. Metade dos módulos tem texto (`config.jsonc:78`, `98`, `123`) e
ficaria ilegível numa barra de 28px de largura; exigiria um segundo conjunto
de formatos só de ícone, como o Omarchy faz
(`shell/plugins/bar/README.md:79`).
Pacote: nenhum.

### Dependências apuradas, arquivo por arquivo

Conferência feita sobre `install/pacotes/base.txt`,
`install/pacotes/ferramentas.txt`, `install/pacotes/interface.txt` e
`install/pacotes/snapshots.txt`, mais `grep` por `networkmanager`, `bluez` e
`pyqt` em todo o `install/`, que não retorna nada.

| Módulo em uso | Precisa de | Está em `install/pacotes/`? |
|---|---|---|
| `network` (linha 76) e `bin/jangada-rede:18,32,43,64` | `nmcli`, ou seja `networkmanager` | Não |
| `network`, clique (linha 82) e `bin/jangada-rede:95` | `nmtui`, mesmo pacote acima | Não |
| `bluetooth` (linha 86) e `bin/jangada-bluetooth:17,35,37` | `bluetoothctl`, ou seja `bluez-utils`, e o serviço `bluez` | Não |
| `clock`, clique (linha 42) e `bin/jangada-calendario:16,21,22` | `python-pyqt6` | Não |
| `clock`, `locale` (linha 41) | locale `pt_BR.UTF-8` gerado | Não é pacote; nada em `install/` gera |
| `cpu`, `memory`, `temperature`, cliques (linhas 49, 56, 73) e `bin/jangada-monitor:10-13` | `btop` ou `htop` | Sim, `btop` em `ferramentas.txt:9` |
| `pulseaudio` e `pulseaudio#microfone` (linhas 107, 116) e `bin/jangada-audio:23,79` | `wpctl`, ou seja `wireplumber` | Sim, `interface.txt:19` |
| `bin/jangada-audio:18` | `python3` | Vem com o sistema; não está listado |
| `custom/agentes` (linha 29) e `bin/jangada-agentes:140,157,166` | `jq` | Sim, `base.txt:3` |
| menus de rede, bluetooth e áudio | `fuzzel` | Sim, `interface.txt:9` |
| avisos dos mesmos scripts | `notify-send`, ou seja `libnotify` | Sim, `base.txt:5` |
| `bin/jangada-bluetooth:120,136` | `blueman-manager` | Não, mas é opcional e o script confere antes |
| `bin/jangada-rede:92` | `nm-connection-editor` | Não, mas é opcional e o script confere antes |

As quatro linhas com "Não" que não são opcionais são
`networkmanager`, `bluez`, `bluez-utils` e `python-pyqt6`. Sem as duas
primeiras, o clique da rede e o do bluetooth não fazem nada; sem a terceira e
a quarta, o clique do relógio não abre nada.

O caso do `bluez` merece nota separada: o módulo `bluetooth` da waybar fala
com o BlueZ por DBus, então sem o serviço no ar o módulo não some, ele fica
parado em `format-disabled` (`config.jsonc:88`), o que é indistinguível de um
rádio desligado de propósito.

## 5. Não adotar

### O Quickshell no lugar da waybar

O Omarchy 4 reescreveu a barra inteira em QML
(`referencia/omarchy/shell/plugins/bar/Bar.qml`, 2076 linhas, mais
`shell/Commons/Style.qml` com 515 e `shell/Ui/` com 35 componentes).
Motivo para não seguir: o jangada já oferece o Noctalia, que é Quickshell,
como o outro modo de interface (`README.md`, seção "Interface"). O modo
`componentes` existe justamente para ser a alternativa leve em waybar. Copiar
a arquitetura do Omarchy 4 apagaria a diferença entre os dois modos.

### O sistema de temas fixos

Vinte e dois temas em `referencia/omarchy/themes/`, cada um com `colors.toml`,
`icons.theme`, `neovim.lua`, `vscode.json` e fundos de tela.
Motivo: o jangada gera cor a partir do papel de parede com o matugen
(`default/matugen/config.toml`, `bin/jangada-tema:59,72`). São modelos opostos
de cor. Trocar um pelo outro seria abandonar o que o `README.md` lista como
uma das três origens do projeto.

### O formato `shell.toml` com papéis por superfície

`referencia/omarchy/default/themed/shell.toml.tpl` tem seções para barra,
janelas flutuantes, dica, notificações, menu, polkit, bloqueio e seletor de
imagem, com companheiro `-alpha` para quase toda cor.
Motivo: a waybar lê CSS do GTK, que já é a linguagem de superfície. Uma camada
TOML por cima só faria sentido se houvesse mais de um programa consumindo os
mesmos papéis, e o `default/matugen/config.toml` já resolve isso gerando seis
saídas de um mesmo conjunto de cores.

### Sistema de extensões com manifesto

`referencia/omarchy/shell/plugins/*/manifest.json`, com `schemaVersion`,
`entryPoints`, `kinds`, `barWidget.schema` e comandos
`omarchy plugin enable/disable/list`
(`shell/plugins/bar/README.md:19`, `176-179`).
Motivo: a waybar já resolve isso com `modules-left`, `modules-center`,
`modules-right` e `custom/*` (`config.jsonc:7-19`). Um registro de extensões
para uma barra de doze módulos é infraestrutura sem demanda.

### Reordenar e mover a barra com o ponteiro

`Bar.qml:1648-1683` e `487-514`.
Motivo: a waybar não expõe evento de arraste e não sabe recarregar posição sem
reiniciar. Seria preciso reescrever a barra para ganhar o gesto, o que recai
no primeiro item desta lista.

### Tailscale, Dropbox e teste de velocidade de disco

`shell/plugins/panels/tailscale/`, `shell/plugins/panels/dropbox/`,
`shell/plugins/panels/disk-speedtest/`.
Motivo: são serviços de terceiros, um deles fechado. O jangada não instala
nenhum deles e nada em `install/pacotes/` sugere que vá instalar. Um módulo de
barra para um serviço ausente é peso morto.

### Sincronizar uso de agentes entre máquinas

`shell/plugins/agents/manifest.json:34-37`: `syncMode`, `syncDir`,
`syncFileName`, `syncDeviceId`, apoiados em Syncthing, Dropbox ou rsync.
Motivo: o `custom/agentes` do jangada conta sessão viva na máquina
(`bin/jangada-agentes:143-152`), não cota de assinatura. Sessão viva em outra
máquina não significa nada para quem olha esta barra.

### Medir cota de assinatura de agente

`shell/plugins/agents/README.md:53-57`: coletores que falam com o endereço de
uso do OAuth da Anthropic, com o servidor do Codex e com a API de cobrança da
Fireworks.
Motivo: isso é útil, mas é um projeto próprio, não uma melhoria de barra. Cada
coletor depende de um contrato de API de terceiro que muda sem aviso, e o
módulo de agentes do jangada responde por outra pergunta, que é o que está
rodando agora. Se um dia entrar, entra como comando `bin/` separado, com o
módulo da barra só lendo o arquivo de estado, como o Omarchy faz
(`shell/plugins/agents/README.md:41-45`).

### Clima na barra

`shell/plugins/panels/weather/`.
Motivo: exige consulta periódica a um serviço na rede a partir de um processo
que a barra reinicia a cada troca de papel de parede (`bin/jangada-tema:34`
manda `SIGUSR2`, o que recarrega o estilo, mas `bin/jangada-barra:10` mata e
reinicia o processo inteiro). Custo de rede e de chave de API para informação
que não é de sistema.
