# Benchmarking de módulos e repositórios de Waybar para o jangada

Documento de consulta técnica com análise comparativa de repositórios do GitHub
voltados ao Waybar, visando identificar módulos, padrões de implementação e
aplicações que podem ser adotados pelo jangada.

## 1. Contexto e critérios de análise

O jangada é uma configuração de Arch Linux com Hyprland (configuração em Lua)
organizada para desenvolvimento com agentes de IA. No modo de interface
"componentes", utiliza a Waybar organizada em ilhas flutuantes com paleta de
cores gerada pelo Matugen a partir do papel de parede (`cores.css`), sem escrita
em `~/.config/hypr`.

A barra do jangada já conta com os seguintes módulos:
- Esquerda: `hyprland/workspaces`, `custom/agentes` (gerenciado por
  `bin/jangada-agentes`), `hyprland/window`.
- Centro: `clock`.
- Direita: `mpris`, `tray`, `custom/atualizacoes` (atualizado por sinal 8),
  `idle_inhibitor`, `cpu`, `memory`, `temperature`, `network`, `bluetooth`,
  `pulseaudio`, `pulseaudio#microfone`, `battery`.

Critérios adotados na avaliação dos candidatos:
1. Impacto em CPU e bateria: módulos com polling curto em scripts shell foram
   penalizados. Prioridade para módulos nativos em C++, escuta de eventos via
   DBus/sockets ou atualização disparada por sinal (como o sinal 8 já usado no
   jangada).
2. Integração com o Matugen: capacidade de receber estilos via classes CSS que
   consomem os tokens `@superficie`, `@texto`, `@texto_suave`, `@primaria`,
   `@texto_primario` e `@atencao`. Scripts que forçam cores literais em
   hexadecimal no JSON foram classificados negativamente.
3. Compatibilidade de dependências: pacotes oficiais do Arch Linux ou do AUR
   mantidos, sem bibliotecas órfãs ou sobreposição de funções.
4. Isolamento: respeito à estrutura de diretórios do jangada, sem gravação fora
   de `~/.config/jangada`, `~/.local/share/jangada` e `~/.local/state/jangada`.

## 2. Repositórios pesquisados

A varredura cobriu 30 repositórios no GitHub. O critério de atividade recente
(últimos 12 meses, considerando a data de referência de 22/09/2026) foi atendido
por 25 dos 30 repositórios; cinco foram mantidos para análise por conterem
padrões técnicos de interesse:

| Repositório | URL | Estrelas | Licença | Último envio | Foco principal |
|---|---|---|---|---|---|
| Alexays/Waybar | https://github.com/Alexays/Waybar | 11.976 | MIT | 2026-09-21 | Repositório oficial e módulos nativos |
| prasanthrangan/hyprdots | https://github.com/prasanthrangan/hyprdots | 8.497 | GPL-3.0 | 2025-03-23 | Dotfiles com scripts de hardware e cliphist |
| JaKooLit/Hyprland-Dots | https://github.com/JaKooLit/Hyprland-Dots | 3.565 | GPL-3.0 | 2026-02-22 | Dotfiles com módulos modulares e disco |
| dusklinux/dusky | https://github.com/dusklinux/dusky | 2.389 | MIT | 2026-09-21 | Dotfiles com integração ao Matugen |
| ErikReider/SwayNotificationCenter | https://github.com/ErikReider/SwayNotificationCenter | 2.585 | GPL-3.0 | 2026-09-18 | Daemon e widget de notificações (SwayNC) |
| flickowoa/dotfiles | https://github.com/flickowoa/dotfiles | 1.990 | Sem licença | 2026-06-15 | Dotfiles com Waybar e temas dinâmicos |
| gvolpe/nix-config | https://github.com/gvolpe/nix-config | 1.112 | Apache-2.0 | 2026-09-21 | Dotfiles Nix com Waybar customizada |
| XNM1/linux-nixos-hyprland-config-dotfiles | https://github.com/XNM1/linux-nixos-hyprland-config-dotfiles | 942 | MIT | 2026-09-16 | Dotfiles com Hyprland e módulos de sistema |
| sameemul-haque/dotfiles | https://github.com/sameemul-haque/dotfiles | 899 | Unlicense | 2025-08-20 | Dotfiles com Waybar |
| Matt-FTW/dotfiles | https://github.com/Matt-FTW/dotfiles | 777 | GPL-3.0 | 2026-09-12 | Dotfiles com Waybar e scripts auxiliares |
| Axenide/Dotfiles | https://github.com/Axenide/Dotfiles | 637 | Sem licença | 2026-08-31 | Dotfiles com scripts Matugen |
| akitaonrails/ai-usagebar | https://github.com/akitaonrails/ai-usagebar | 535 | MIT | 2026-09-20 | Monitor de cotas de IA (Claude, Ollama, OpenAI) |
| vyrx-dev/symphony | https://github.com/vyrx-dev/symphony.git | 505 | MIT | 2026-05-15 | Dotfiles modulares com recarga por sinal |
| bjesus/wttrbar | https://github.com/bjesus/wttrbar | 368 | MIT | 2026-09-19 | Módulo climático em Rust para Waybar |
| atif-1402/minimal-waybar-themes | https://github.com/atif-1402/minimal-waybar-themes | 241 | MIT | 2026-04-01 | Coleção de barras minimalistas |
| Andeskjerf/waybar-module-pomodoro | https://github.com/Andeskjerf/waybar-module-pomodoro | 128 | Unlicense | 2025-09-29 | Temporizador Pomodoro em Rust |
| coffebar/waybar-module-pacman-updates | https://github.com/coffebar/waybar-module-pacman-updates | 115 | GPL-3.0 | 2026-07-30 | Verificador de pacotes pacman/AUR em Rust |
| niraletter/waybar-pomodoro-timer | https://github.com/niraletter/waybar-pomodoro-timer | 79 | MIT | 2026-04-04 | Temporizador Pomodoro em script Bash |
| jolars/tomat | https://github.com/jolars/tomat | 64 | MIT | 2026-09-22 | Daemon Pomodoro em Rust com suporte Waybar |
| chmouel/nextmeeting | https://github.com/chmouel/nextmeeting | 59 | Apache-2.0 | 2026-09-09 | Notificador de reuniões Google Agenda/CalDAV |
| mryll/claudebar | https://github.com/mryll/claudebar | 57 | MIT | 2026-09-18 | Monitor de limites e janelas do Claude Code |
| NihilDigit/waybar-ai-usage | https://github.com/NihilDigit/waybar-ai-usage | 53 | MIT | 2026-09-10 | Extensão para Claude Code e OpenAI Codex |
| federicovolponi/waybar-tailscale | https://github.com/federicovolponi/waybar-tailscale | 34 | MIT | 2026-07-30 | Widget de status e controle do Tailscale |
| Klafyvel/wireguard-manager | https://github.com/Klafyvel/wireguard-manager | 34 | MIT | 2023-02-02 | Gerenciador de conexão WireGuard para barra |
| hxreborn/waybar-claude-code | https://github.com/hxreborn/waybar-claude-code | 19 | MIT | 2026-08-15 | Monitor de Claude Code em Go |
| SirAllap/waybar-scripts-collection | https://github.com/SirAllap/waybar-scripts-collection | 17 | Sem licença | 2026-09-15 | Scripts de uso de Claude, GPU e calendário |
| Marouan-chak/codexbar-waybar | https://github.com/Marouan-chak/codexbar-waybar | 12 | MIT | 2026-09-14 | Ponte Waybar para CLI CodexBar com popover GTK4 |
| raffaem/waybar-screenrecorder | https://github.com/raffaem/waybar-screenrecorder | 12 | MIT | 2024-02-19 | Indicador de gravação de tela com sinais |
| kagetora66/waybar-internet-widget | https://github.com/kagetora66/waybar-internet-widget | 0 | Sem licença | 2025-07-27 | Script de latência e ping contínuo |
| nicolasacchi/waybar-vpn-modules | https://github.com/nicolasacchi/waybar-vpn-modules | 0 | MIT | 2026-06-13 | Módulos para Proton VPN e Tailscale |

## 3. Avaliação por categoria

### 3.1. Rede (Velocidade em tempo real, VPN e latência)

| Candidato | Fonte (Repositório e arquivo) | O que faz | Dependências | Custo de CPU e rede | Licença |
|---|---|---|---|---|---|
| Módulo nativo `network` (Waybar) | Alexays/Waybar (`src/modules/network.cpp`, `man/waybar-network.5.scd`) | Taxa de download e upload instantânea (`bandwidthDownBytes`, `bandwidthUpBytes`), SSID, sinal e IP | `waybar`, `libnl` | Mínimo. Código C++ nativo que lê netlink socket do kernel | MIT |
| `waybar-vpn-modules` | nicolasacchi/waybar-vpn-modules (`scripts/vpn.sh`) | Detecta VPN ativa no NetworkManager (`nmcli`) e exibe servidor Proton VPN/WireGuard conectado | `networkmanager` (`nmcli`) | Baixo. Consulta por DBus ao NetworkManager | MIT |
| `wireguard-manager` | Klafyvel/wireguard-manager (`wireguard-manager.sh`) | Indicador de túnel WireGuard (`wg-quick@wg0`) e controle liga/desliga com elevação via sudo | `wireguard-tools`, `systemd`, `rofi`, `sudo` | Baixo com intervalo regular. Faz chamada a `systemctl is-active` | MIT |
| `waybar-tailscale` | federicovolponi/waybar-tailscale (`waybar-tailscale.sh`) | Mostra status da VPN Tailscale, IP atribuído, exit node atual e menu para alternar conexões | `tailscale`, `jq`, menu (`walker` ou `rofi`) | Baixo com intervalo de 10s a 30s. Faz chamada a `tailscale status --json` | MIT |
| `waybar-internet-widget` | kagetora66/waybar-internet-widget (`internet_status.py`) | Exibe ping em milissegundos para 8.8.8.8 continuamente | `python`, `iputils` (`ping`) | Alto. Loop de 1 segundo executando `ping -c1`, mantendo a CPU acordada | Sem licença |

Observações sobre rede:
- A Waybar calcula taxas de transferência internamente no módulo nativo
  `network`. No jangada, o tráfego instantâneo no formato do rótulo foi registrado
  como pendência na comparação com o Omarchy (`revisao/benchmark-waybar-omarchy.md:40`).
  Essa configuração pode ser feita nos campos `format-wifi` e `format-ethernet`.
- Para VPN, a abordagem de `nicolasacchi/waybar-vpn-modules` via `nmcli` se
  alinha ao jangada, que já gerencia rede pelo NetworkManager (`bin/jangada-rede`).
  Serviços proprietários de terceiros foram descartados anteriormente.
- Scripts com loop contínuo de ping a cada segundo aumentam consumo de energia
  sem necessidade.

### 3.2. Agentes e inteligência artificial

| Candidato | Fonte (Repositório e arquivo) | O que faz | Dependências | Custo de CPU e rede | Licença |
|---|---|---|---|---|---|
| `ai-usagebar` | akitaonrails/ai-usagebar (`src/waybar.rs`, `src/widget/cli.rs`) | Monitora limites de planos de Claude, OpenAI, Ollama local e OpenRouter. Atualiza via sinal 13 | Binário compilado em Rust | Mínimo. Execução em Rust e atualização reativa por sinal | MIT |
| `claudebar` | mryll/claudebar (`claudebar`) | Exibe tempo até a renovação da janela de 5 horas e limites do Claude Code | `bash`, `curl`, `jq` | Baixo com cache local (evita chamadas redundantes à API) | MIT |
| `waybar-claude-fetch` | SirAllap/waybar-scripts-collection (`waybar-claude-usage.py`, `waybar-claude-fetch.py`) | Coleta dados de `/usage` do Claude Code via pseudo-terminal (`pty`) em segundo plano e expõe cache JSON | `python`, `claude` CLI | Zero na leitura da barra. Custo pontual a cada 15-30 minutos no coletor em segundo plano | Sem licença |
| `waybar-ai-usage` | NihilDigit/waybar-ai-usage (`waybar_ai_usage.py`) | Gera e mantém módulos Waybar para Claude Code e OpenAI Codex a partir de tokens locais | `python`, `json5` | Baixo. Leitura periódica de arquivos locais de credenciais | MIT |
| `waybar-claude-code` | hxreborn/waybar-claude-code (`cmd/waybar-claude-code/main.go`) | Widget em Go para contagem de tokens e custos de sessões do Claude Code | Binário Go | Baixo. Processo em Go | MIT |
| `codexbar-waybar` | Marouan-chak/codexbar-waybar (`README.md`, scripts de integração) | Ponte entre o CLI `codexbar` (Claude/OpenAI/Gemini) e a Waybar, adicionando popover GTK4 | CLI `codexbar`, GTK4 | Médio. Depende da execução do binário externo `codexbar` | MIT |

Observações sobre agentes e IA:
- O jangada possui o módulo `custom/agentes` (`bin/jangada-agentes`), que conta
  sessões tmux ativas, classifica estados (`trabalhando`, `aguardando`,
  `concluido`) e integra com `bin/jangada-consumo` para estimar tokens em
  janelas de 5 horas a partir dos arquivos locais em `~/.claude/projects/`.
- A técnica útil observada em `claudebar` e `SirAllap` é a exibição do tempo
  restante para o reset da janela de 5 horas. Esse cálculo pode ser absorvido
  pelo `bin/jangada-consumo` local sem criar um módulo extra na barra.
- A medição de cotas contratuais de assinatura via APIs de terceiros continua
  descartada, conforme definido no benchmark anterior
  (`revisao/benchmark-waybar-omarchy.md:452-462`), por fragilidade de contrato.

### 3.3. Sistema (GPU NVIDIA, disco, snapshots, atualizações e systemd)

| Candidato | Fonte (Repositório e arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Módulo nativo `systemd-failed-units` (Waybar) | Alexays/Waybar (`src/modules/systemd_failed_units.cpp`, `man/waybar-systemd-failed-units.5.scd`) | Monitora serviços com falha no systemd (sistema e usuário). Oculto quando não há falhas (`hide-on-ok: true`) | `waybar`, `libsystemd` | Mínimo. Escuta eventos via DBus em C++, sem polling | MIT |
| Módulo nativo `disk` (Waybar) | Alexays/Waybar (`src/modules/disk.cpp`, `man/waybar-disk.5.scd`) | Mostra porcentagem de uso e espaço livre da partição raiz ou `/home`, com limiares de aviso | `waybar`, C libc (`statvfs`) | Praticamente nulo. Uma syscall direta a cada 30 ou 60 segundos | MIT |
| `custom/gpuinfo` | prasanthrangan/hyprdots (`Configs/.config/waybar/modules/gpuinfo.jsonc`, `gpuinfo.sh`) | Exibe uso, VRAM e temperatura de GPU NVIDIA/AMD/Intel com alternância | `nvidia-utils` (`nvidia-smi`), `pciutils` | Moderado a alto no caso NVIDIA. Chamar `nvidia-smi` a cada 5 segundos impede suspensão D3cold | GPL-3.0 |
| `waybar-module-pacman-updates` | coffebar/waybar-module-pacman-updates (`src/main.rs`, `src/checkupdates_lock.rs`) | Conta atualizações do Arch e AUR com controle de trava concorrente | `pacman-contrib`, binário Rust | Baixo. Polling longo e bloqueio durante operações de instalação | GPL-3.0 |
| Módulos de sistema do JaKooLit | JaKooLit/Hyprland-Dots (`config/waybar/Modules`) | Agrupamento de disco (`disk`), memória, processador e temperatura | Módulos nativos | Quase nulo | GPL-3.0 |

Observações sobre sistema:
- O módulo nativo `systemd-failed-units` atua de forma preventiva. Por usar DBus
  e `hide-on-ok`, não gera ruído visual nem gasta ciclos de CPU em repouso.
- O módulo nativo `disk` alerta sobre saturação de partição decorrente de
  worktrees de Git e modelos locais de IA.
- Snapshots: o jangada possui suporte a snapshots com snapper
  (`bin/jangada-snapshot` e `install/pacotes/snapshots.txt`). Nenhum dos 30
  repositórios apresentou módulo pronto para snapper que não fizesse chamadas
  pesadas a `snapper list`. A abordagem adequada para o jangada é um módulo
  customizado que lê um arquivo de contagem atualizado pelo próprio
  `bin/jangada-snapshot`.
- Polling curto com `nvidia-smi`: a execução de `nvidia-smi` a cada 5 segundos
  (como em `Configs/.config/waybar/modules/gpuinfo.jsonc:6` do Hyprdots) acorda a
  GPU dedicada do estado de economia D3cold em notebooks com placas híbridas,
  elevando a temperatura e o consumo de bateria.

### 3.4. Produtividade (Pomodoro, calendário, notificações, clipboard e gravação)

| Candidato | Fonte (Repositório e arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Widget SwayNC (`custom/notification`) | ErikReider/SwayNotificationCenter (`swaync-client`) | Indicador de notificações pendentes, modo Não Perturbe e painel de controle | `sway-notification-center` | Mínimo. Cliente persistente orientado a eventos (`swaync-client -swb`) | GPL-3.0 |
| `tomat` | jolars/tomat (`docs/src/guide/integration/status-bars/waybar.md`, `examples/waybar-config.json`) | Temporizador Pomodoro em Rust com integração completa para Waybar (trabalho, descanso e pausa) | Binário `tomat` (Rust) | Baixo em binário compilado, mas usa polling de 1s para o contador visual | MIT |
| `waybar-module-pomodoro` | Andeskjerf/waybar-module-pomodoro (`src/main.rs`) | Pomodoro simples com 4 ciclos e intervalos em binário Rust | Binário Rust | Baixo | Unlicense |
| `waybar-pomodoro-timer` | niraletter/waybar-pomodoro-timer (`timer.sh`) | Cronômetro e Pomodoro em Bash puro com sons de alerta e ícones | `bash`, tocador de áudio (`mpv`) | Médio. Múltiplos processos de bash por segundo durante contagem | MIT |
| `waybar-screenrecorder` | raffaem/waybar-screenrecorder (`screenrecorder`) | Indicador de gravação de tela com `wf-recorder`, com status na dica e controle por sinal | `wf-recorder`, `ffmpeg` | Zero quando inativo. Atualiza por sinal `pkill -RTMIN+1 waybar` | MIT |
| `custom/cliphist` | prasanthrangan/hyprdots (`Configs/.config/waybar/modules/cliphist.jsonc`) | Botão de área de transferência na barra que aciona o seletor de histórico | `cliphist`, `wl-clipboard`, seletor dmenu | Zero em repouso. Módulo estático que executa sob demanda | GPL-3.0 |
| `nextmeeting` | chmouel/nextmeeting (`README.md`) | Próxima reunião do Google Agenda/CalDAV com contagem regressiva | `python`, `gcalcli` | Baixo com cache de 5 a 15 minutos | Apache-2.0 |

Observações sobre produtividade:
- O módulo de gravação de tela por sinal (`waybar-screenrecorder`) é adequado:
  sem gravação ativa, o módulo tem texto vazio e a Waybar recolhe o espaço.
- Área de transferência: o jangada já grava cópias (`default/hypr/inicio.lua:9-10`,
  com `wl-paste --watch cliphist store`) e já disponibiliza consulta via
  `bin/jangada-menu:15` (`cliphist list | menu | cliphist decode | wl-copy`).
  Um módulo na barra constituiria um ponto de acesso adicional para uso com
  mouse, não o primeiro canal.
- Notificações: o jangada utiliza o Mako (`install/pacotes/interface.txt:10`).
  A adoção do SwayNC exigiria a troca do daemon de notificações. Uma alternativa
  alinhada ao jangada é inspecionar o estado do Mako via `makoctl mode` para
  oferecer alternância do modo Não Perturbe.

### 3.5. Outros módulos e técnicas de destaque

| Candidato | Fonte (Repositório e arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Módulo nativo `privacy` (Waybar) | Alexays/Waybar (`src/modules/privacy/privacy.cpp`, `man/waybar-privacy.5.scd`) | Indicador nativo de captura de áudio (microfone em uso por aplicativo) e compartilhamento de tela | `waybar`, `pipewire`, `wireplumber` | Mínimo. Reativo a fluxos do PipeWire em C++, zero polling | MIT |
| Módulo nativo `hyprland/submap` (Waybar) | Alexays/Waybar (`src/modules/hyprland/submap.cpp`, `man/waybar-hyprland-submap.5.scd`) | Exibe o submap (modo modal) atual do Hyprland e oculta no modo normal | `waybar`, Hyprland IPC | Zero em repouso. Escuta o socket UNIX do Hyprland | MIT |
| Módulo nativo `gamemode` (Waybar) | Alexays/Waybar (`src/modules/gamemode.cpp`, `man/waybar-gamemode.5.scd`) | Mostra quando o daemon Feral GameMode está ativo otimizando processos | `waybar`, `gamemode` | Mínimo. Consulta ao DBus do GameMode | MIT |
| Temas dinâmicos do Dusky | dusklinux/dusky (`.config/matugen/generated_fresh/waybar-colors.css`) | Arquitetura de estilização da Waybar baseada em variáveis geradas pelo Matugen (`@define-color`) | `matugen`, `waybar` | Zero em execução | MIT |
| `wttrbar` | bjesus/wttrbar (`src/main.rs`) | Informações climáticas e previsão meteorológica detalhada com gráficos na dica | `wttrbar` (AUR) | Baixo em CPU, depende de rede externa e serviço wttr.in | MIT |

Observações sobre outros módulos:
- O módulo nativo `privacy` atende à questão de visibilidade sobre uso do
  microfone e compartilhamento de tela sem scripts adicionais, utilizando a
  infraestrutura WirePlumber do sistema.
- O repositório `dusky` adota abordagem idêntica à do jangada para integração
  com o Matugen: variáveis `@define-color` no CSS separadas das regras de
  posicionamento e medidas.

## 4. As 10 melhores recomendações para o jangada

Abaixo estão 10 propostas de módulos e aprimoramentos para a barra do jangada,
ordenadas por relevância técnica, alinhamento com as regras do projeto e
eficiência de recursos.

### 1. Módulo nativo `systemd-failed-units`
- Motivo: Monitoramento preventivo de integridade. Com a opção `"hide-on-ok":
  true`, o módulo permanece oculto durante a operação normal e não ocupa espaço
  na barra. Quando qualquer serviço de sistema ou de usuário falha, o ícone surge
  em destaque. O módulo opera em C++ escutando sinais do systemd via DBus, sem
  processos em segundo plano.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo da Waybar inserido no array `modules-right` de
  `default/waybar/config.jsonc`, com estilo em `default/waybar/base.css` usando a
  classe `#systemd-failed-units.degraded` com a cor `@atencao`.

### 2. Módulo nativo `privacy` (Aviso de microfone ativo e captura de tela)
- Motivo: Segurança visual. Avisa quando um aplicativo em segundo plano está
  capturando áudio do microfone ou gravando a tela. Reativo por eventos do
  PipeWire, sem necessidade de consultas periódicas. Atende à necessidade de
  aviso visual de microfone em uso por aplicativo terceiro.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo da Waybar (`privacy`) em `config.jsonc` com
  configuração para `screenshare` e `audio-in`. Estilização em `base.css` sob a
  classe `#privacy-item` com cor `@atencao`.

### 3. Módulo nativo `disk` (Espaço em disco com limiares de alerta)
- Motivo: Prevenção contra partição cheia decorrente de worktrees de Git,
  imagens de contêineres e modelos de IA. A leitura usa `statvfs()` a cada 60
  segundos sem custo de subprocessos. Permite configurar limiares de aviso
  (`states`: aviso em 80% e crítico em 90%). O clique pode abrir um terminal
  executando `df -h` ou o monitor geral `bin/jangada-monitor` (btop).
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo `disk` em `default/waybar/config.jsonc` com
  formato compacto (ex: `󰋊 {percentage_used}%`), tooltip completo com espaço
  livre e total, e regra em `default/waybar/base.css`.

### 4. Enriquecimento da janela de 5 horas no `custom/agentes`
- Motivo: Evitar a criação de módulos concorrentes na barra (como `claudebar` e
  `ai-usagebar`). O jangada já calcula o consumo de tokens em 5 horas no
  `bin/jangada-consumo`. Calcular e exibir o tempo restante para a renovação da
  janela de 5 horas diretamente na dica de `bin/jangada-agentes` atende à
  demanda sem abrir consultas a APIs externas e sem ocupar espaço horizontal na
  barra.
- Esforço estimado: Médio.
- Como encaixaria: Ajuste no script `bin/jangada-consumo` e no campo `tooltip` de
  `bin/jangada-agentes --waybar`, mantendo inalterada a lista de módulos da
  Waybar.

### 5. Indicador de gravação de tela acionado por sinal (`custom/gravacao`)
- Motivo: Confirmação visual durante gravações de tela. Inspirado em
  `raffaem/waybar-screenrecorder`, o módulo emite texto vazio (`{"text": ""}`)
  quando inativo, recolhendo o espaço na Waybar. Ao iniciar ou encerrar a
  gravação com `wl-screenrec` ou `wf-recorder`, o utilitário envia sinal em tempo
  real para a barra, exibindo status ativo e tempo.
- Esforço estimado: Médio.
- Como encaixaria: Módulo `custom/gravacao` em `config.jsonc` com escuta de sinal
  dedicado (o 8 e o 9 já são do custom/atualizacoes e do custom/indicadores; seria o
  10), controlado por `bin/jangada-gravar` (a criar) e atalho
  em `default/hypr/atalhos.lua`.

### 6. Indicador de snapshots do Snapper (`custom/snapshots`)
- Motivo: Visibilidade sobre cópias de segurança do sistema de arquivos Btrfs.
  O jangada possui `bin/jangada-snapshot` e inclui `snapper` nos pacotes do
  instalador. Para evitar chamadas repetidas a `snapper list` (que exigem privilégio
  ou sobrecarga de I/O), o script `bin/jangada-snapshot` pode gravar a contagem
  em arquivo de estado e emitir sinal para a Waybar atualizar o módulo.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo `custom/snapshots` em `config.jsonc` com leitura rápida
  de cache em `~/.local/state/jangada/` e clique abrindo menu de snapshots.

### 7. Gerenciador de VPN via NetworkManager (`custom/vpn`)
- Motivo: Controle rápido de conexões VPN configuradas no sistema (WireGuard ou
  OpenVPN). Inspirado em `nicolasacchi/waybar-vpn-modules`, consulta o estado de
  conexões do tipo VPN via `nmcli -t -f NAME,TYPE,DEVICE connection show --active`.
  Um clique esquerdo abre o menu `fuzzel` com os perfis de conexão do sistema para
  ativar ou desativar túneis.
- Esforço estimado: Médio.
- Como encaixaria: Módulo `custom/vpn` em `config.jsonc` apoiado por novo script
  `bin/jangada-vpn`, reutilizando a interface de `fuzzel` já empregada em
  `bin/jangada-rede`.

### 8. Alternador do modo Não Perturbe do Mako (`custom/notificacoes`)
- Motivo: Controle visual de silenciamento de avisos. O jangada utiliza o Mako
  como daemon de notificações. Em vez de substituir o daemon pelo SwayNC, um
  módulo customizado pode consultar `makoctl mode` e alternar o modo entre
  padrão e silencioso (`makoctl mode -s do-not-disturb`), exibindo ícone de sino
  ou sino riscado.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo `custom/notificacoes` em `config.jsonc` com comando
  de alternância via `makoctl mode` e atualização por sinal.

### 9. Botão complementar de histórico de área de transferência (`custom/cliphist`)
- Motivo: Acesso com mouse ao histórico de cópias. O jangada já grava o
  histórico via `wl-paste --watch cliphist store` (`default/hypr/inicio.lua:9-10`)
  e já permite consulta via teclado no menu do sistema (`bin/jangada-menu:15`).
  Inspirado no módulo `custom/cliphist` do Hyprdots
  (`Configs/.config/waybar/modules/cliphist.jsonc`), a barra ganha um ícone
  estático que aciona `cliphist list | fuzzel -d | cliphist decode | wl-copy` no
  clique.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo estático `custom/cliphist` em `default/waybar/config.jsonc`
  sem script de polling em segundo plano.

### 10. Módulo nativo `hyprland/submap`
- Motivo: O Hyprland permite a criação de modos modais (submaps) para operações
  como redimensionamento de janelas ou captura exclusiva de teclas. O módulo
  nativo escuta o socket IPC do Hyprland e só fica visível quando um submap está
  ativo. Observação: sua ativação depende da inclusão prévia de atalhos com
  submap em `default/hypr/atalhos.lua`, caso contrário permanece sempre oculto.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo `hyprland/submap` em `default/waybar/config.jsonc`
  em `modules-left`, estilizado em `default/waybar/base.css` com a cor `@atencao`.

## 5. O que foi descartado e motivos

1. Polling frequente de GPU via `nvidia-smi` (Hyprdots e SirAllap-scripts):
   - Motivo: A execução de `nvidia-smi` em intervalos curtos (ex: 5 segundos em
     `Configs/.config/waybar/modules/gpuinfo.jsonc:6`) acorda a placa NVIDIA
     dedicada de estados de suspensão profunda (D3cold), causando aquecimento e
     drenagem de bateria em laptops híbridos. O monitoramento de GPU deve ocorrer
     sob demanda através do monitor de processos ou ferramentas com suporte a
     NVML.

2. Medição de cota de assinatura de agentes de IA:
   - Motivo: Módulos que tentam obter limites de plano e créditos contratuais
     dependem de chamadas a endpoints privados que mudam sem aviso. A decisão
     do benchmark anterior (`revisao/benchmark-waybar-omarchy.md:452-462`)
     permanece válida: dados locais de contagem de tokens e estimativa de tempo
     são mantidos, enquanto cotas de assinatura ficam fora da barra.

3. Tailscale e serviços de VPN proprietários de terceiros:
   - Motivo: Conforme registrado no benchmark anterior
     (`revisao/benchmark-waybar-omarchy.md:436-443`), o jangada não instala
     Tailscale nem depende de serviços externos fechados. O controle de VPN
     deve apoiar-se no NetworkManager e WireGuard padrão.

4. Módulos de latência e ping contínuo a cada segundo (`waybar-internet-widget`):
   - Motivo: Manter um loop contínuo disparando `ping` a cada 1 segundo acorda o
     processador e gera tráfego redundante de rede. Testes de conectividade devem
     ser reativos ou manuais.

5. Verificadores de atualizações em Rust concorrentes com o pacman
   (`waybar-module-pacman-updates`):
   - Motivo: O jangada já dispõe de `custom/atualizacoes` (`bin/jangada-atualizacoes`,
     57 linhas em bash), que utiliza `checkupdates` do pacote oficial
     `pacman-contrib`, roda a cada hora e atualiza imediatamente por sinal 8 após
     o `jangada-update`. Adicionar um binário compilado em Rust traz complexidade
     sem vantagem operacional.

6. Troca do daemon de notificações Mako pelo SwayNC:
   - Motivo: Substituir o Mako apenas para obter o painel visual do SwayNC
     aumentaria o consumo de memória e a base de código do sistema. O Mako é
     leve e cumpre seu papel; o controle de Não Perturbe pode ser feito via
     `makoctl mode`.

7. Previsão do tempo na barra (`wttrbar` e scripts de clima):
   - Motivo: Dependência de requisições a serviços web sujeitos a bloqueio de
     taxa e falhas de conexão. A informação meteorológica não faz parte do
     gerenciamento de sistema e ocupa espaço útil na barra.

8. Scripts com cores hexadecimais fixas no payload JSON:
   - Motivo: Injetar códigos como `{"color": "#FF0000"}` no retorno do módulo
     quebra a derivação dinâmica de cores do Matugen (`cores.css`). Todos os
     módulos devem emitir apenas classes semânticas (`degraded`, `warning`,
     `active`), delegando as cores para o CSS.

## 6. Mapeamento de fontes e arquivos

Todas as informações técnicas apresentadas foram extraídas diretamente dos
arquivos clonados nos repositórios de referência:

- Módulos nativos da Waybar:
  - Repositório: https://github.com/Alexays/Waybar
  - Arquivos: `src/modules/systemd_failed_units.cpp`,
    `src/modules/privacy/privacy.cpp`, `src/modules/disk.cpp`,
    `src/modules/hyprland/submap.cpp`, `src/modules/network.cpp`,
    `man/waybar-systemd-failed-units.5.scd`, `man/waybar-privacy.5.scd`,
    `man/waybar-disk.5.scd`.
- Scripts de hardware e cliphist do Hyprdots:
  - Repositório: https://github.com/prasanthrangan/hyprdots
  - Arquivos: `Configs/.config/waybar/modules/gpuinfo.jsonc`,
    `Configs/.local/share/bin/gpuinfo.sh`,
    `Configs/.config/waybar/modules/cliphist.jsonc`.
- Módulos modulares do JaKooLit:
  - Repositório: https://github.com/JaKooLit/Hyprland-Dots
  - Arquivos: `config/waybar/Modules`, `config/waybar/ModulesCustom`.
- Integração de temas com Matugen:
  - Repositório: https://github.com/dusklinux/dusky
  - Arquivos: `.config/matugen/generated_fresh/waybar-colors.css`,
    `.config/waybar/01_mechabar_h/config.jsonc`.
- Ferramentas de IA e agentes:
  - `ai-usagebar`: https://github.com/akitaonrails/ai-usagebar (`src/waybar.rs`,
    `src/widget/cli.rs`).
  - `claudebar`: https://github.com/mryll/claudebar (`claudebar`).
  - `codexbar-waybar`: https://github.com/Marouan-chak/codexbar-waybar (`README.md`).
  - `waybar-ai-usage`: https://github.com/NihilDigit/waybar-ai-usage (`waybar_ai_usage.py`).
  - `waybar-claude-code`: https://github.com/hxreborn/waybar-claude-code (`cmd/waybar-claude-code/main.go`).
  - `waybar-scripts-collection`: https://github.com/SirAllap/waybar-scripts-collection
    (`waybar-claude-usage.py`, `waybar-claude-fetch.py`).
- Módulos de rede e VPN:
  - `waybar-vpn-modules`: https://github.com/nicolasacchi/waybar-vpn-modules
    (`scripts/vpn.sh`, `scripts/tailscale.sh`).
  - `wireguard-manager`: https://github.com/Klafyvel/wireguard-manager (`wireguard-manager.sh`).
  - `waybar-tailscale`: https://github.com/federicovolponi/waybar-tailscale (`waybar-tailscale.sh`).
  - `waybar-internet-widget`: https://github.com/kagetora66/waybar-internet-widget (`internet_status.py`).
- Módulos de produtividade e notificações:
  - `waybar-screenrecorder`: https://github.com/raffaem/waybar-screenrecorder (`screenrecorder`).
  - `SwayNotificationCenter`: https://github.com/ErikReider/SwayNotificationCenter (`README.md`).
  - `tomat`: https://github.com/jolars/tomat (`docs/src/guide/integration/status-bars/waybar.md`).
  - `waybar-module-pomodoro`: https://github.com/Andeskjerf/waybar-module-pomodoro (`src/main.rs`).
  - `waybar-pomodoro-timer`: https://github.com/niraletter/waybar-pomodoro-timer (`timer.sh`).
  - `nextmeeting`: https://github.com/chmouel/nextmeeting (`README.md`).
  - `waybar-module-pacman-updates`: https://github.com/coffebar/waybar-module-pacman-updates (`src/main.rs`).
