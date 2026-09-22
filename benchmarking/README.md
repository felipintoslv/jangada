# Benchmarking de Módulos e Repositórios de Waybar para o Jangada

Documento de consulta técnica com análise comparativa de repositórios do GitHub
voltados ao Waybar, visando identificar módulos, padrões de implementação e
aplicações que podem ser adotados pelo Jangada.

## 1. Contexto e Critérios de Análise

O Jangada é uma configuração de Arch Linux com Hyprland (configuração em Lua)
organizada para desenvolvimento com agentes de IA. No modo de interface
"componentes", utiliza a Waybar organizada em ilhas flutuantes com paleta de
cores gerada dinamicamente pelo Matugen a partir do papel de parede
(`cores.css`), sem escrita em `~/.config/hypr`.

A barra do Jangada já conta com os seguintes módulos:
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
   Jangada).
2. Integração com o Matugen: capacidade de receber estilos via classes CSS que
   consomem os tokens `@superficie`, `@texto`, `@texto_suave`, `@primaria`,
   `@texto_primario` e `@atencao`. Scripts que forçam cores literais em
   hexadecimal no JSON foram classificados negativamente.
3. Compatibilidade de dependências: pacotes oficiais do Arch Linux ou do AUR
   ativamente mantidos, sem bibliotecas órfãs ou sobreposição desnecessária.
4. Isolamento: respeito estrito à estrutura de diretórios do Jangada, sem
   gravação fora de `~/.config/jangada`, `~/.local/share/jangada` e
   `~/.local/state/jangada`.

## 2. Repositórios Pesquisados

A varredura cobriu 30 repositórios no GitHub, divididos entre repositórios
oficiais, coleções temáticas de dotfiles e módulos especializados:

| Repositório | URL | Estrelas | Licença | Foco principal |
|---|---|---|---|---|
| Alexays/Waybar | https://github.com/Alexays/Waybar | 11.976 | MIT | Repositório oficial e módulos nativos |
| prasanthrangan/hyprdots | https://github.com/prasanthrangan/hyprdots | 8.497 | GPL-3.0 | Dotfiles com scripts de hardware e GPU |
| JaKooLit/Hyprland-Dots | https://github.com/JaKooLit/Hyprland-Dots | 3.565 | GPL-3.0 | Dotfiles com módulos modulares e disco |
| dusklinux/dusky | https://github.com/dusklinux/dusky | 2.389 | MIT | Dotfiles com integração profunda ao Matugen |
| ErikReider/SwayNotificationCenter | https://github.com/ErikReider/SwayNotificationCenter | 2.585 | GPL-3.0 | Daemon e widget de notificações (SwayNC) |
| flickowoa/dotfiles | https://github.com/flickowoa/dotfiles | 1.990 | Sem licença explícita | Dotfiles com Waybar e temas dinâmicos |
| gvolpe/nix-config | https://github.com/gvolpe/nix-config | 1.112 | Apache-2.0 | Dotfiles Nix com Waybar customizada |
| XNM1/linux-nixos-hyprland-config-dotfiles | https://github.com/XNM1/linux-nixos-hyprland-config-dotfiles | 942 | MIT | Dotfiles com Hyprland e módulos de sistema |
| sameemul-haque/dotfiles | https://github.com/sameemul-haque/dotfiles | 899 | Unlicense | Dotfiles minimalistas com Waybar |
| Matt-FTW/dotfiles | https://github.com/Matt-FTW/dotfiles | 777 | GPL-3.0 | Dotfiles com Waybar e scripts auxiliares |
| Axenide/Dotfiles | https://github.com/Axenide/Dotfiles | 637 | Sem licença explícita | Dotfiles com scripts Matugen |
| akitaonrails/ai-usagebar | https://github.com/akitaonrails/ai-usagebar | 535 | MIT | Monitor de cotas de IA (Claude, Ollama, OpenAI) |
| vyrx-dev/symphony | https://github.com/vyrx-dev/symphony.git | 505 | MIT | Dotfiles modulares com recarga por sinal |
| bjesus/wttrbar | https://github.com/bjesus/wttrbar | 368 | MIT | Módulo climático em Rust para Waybar |
| atif-1402/minimal-waybar-themes | https://github.com/atif-1402/minimal-waybar-themes | 241 | MIT | Coleção de barras minimalistas |
| Andeskjerf/waybar-module-pomodoro | https://github.com/Andeskjerf/waybar-module-pomodoro | 128 | Unlicense | Temporizador Pomodoro em Rust |
| coffebar/waybar-module-pacman-updates | https://github.com/coffebar/waybar-module-pacman-updates | 115 | GPL-3.0 | Verificador de pacotes pacman/AUR em Rust |
| niraletter/waybar-pomodoro-timer | https://github.com/niraletter/waybar-pomodoro-timer | 79 | MIT | Temporizador Pomodoro em script Bash |
| jolars/tomat | https://github.com/jolars/tomat | 64 | MIT | Daemon Pomodoro em Rust com suporte Waybar |
| chmouel/nextmeeting | https://github.com/chmouel/nextmeeting | 59 | Apache-2.0 | Notificador de reuniões Google Agenda/CalDAV |
| mryll/claudebar | https://github.com/mryll/claudebar | 57 | MIT | Monitor de limites e janelas do Claude Code |
| NihilDigit/waybar-ai-usage | https://github.com/NihilDigit/waybar-ai-usage | 53 | MIT | Extensão para Claude Code e OpenAI Codex |
| federicovolponi/waybar-tailscale | https://github.com/federicovolponi/waybar-tailscale | 34 | MIT | Widget de status e controle do Tailscale |
| Klafyvel/wireguard-manager | https://github.com/Klafyvel/wireguard-manager | 34 | MIT | Gerenciador de conexão WireGuard para barra |
| hxreborn/waybar-claude-code | https://github.com/hxreborn/waybar-claude-code | 19 | MIT | Monitor de Claude Code em Go |
| SirAllap/waybar-scripts-collection | https://github.com/SirAllap/waybar-scripts-collection | 17 | Sem licença explícita | Scripts de uso de Claude, GPU e calendário |
| Marouan-chak/codexbar-waybar | https://github.com/Marouan-chak/codexbar-waybar | 12 | MIT | Ponte Waybar para CLI CodexBar com popover GTK4 |
| raffaem/waybar-screenrecorder | https://github.com/raffaem/waybar-screenrecorder | 12 | MIT | Indicador de gravação de tela com sinais |
| kagetora66/waybar-internet-widget | https://github.com/kagetora66/waybar-internet-widget | 0 | Sem licença explícita | Script de latência e ping contínuo |
| nicolasacchi/waybar-vpn-modules | https://github.com/nicolasacchi/waybar-vpn-modules | 0 | MIT | Módulos para Proton VPN e Tailscale |

## 3. Avaliação por Categoria

### 3.1. Rede (Velocidade em tempo real, VPN e Latência)

| Candidato | Fonte (Repositório e Arquivo) | O que faz | Dependências | Custo de CPU e Rede | Licença |
|---|---|---|---|---|---|
| Módulo nativo `network` (Waybar) | Alexays/Waybar (`src/modules/network.cpp`, `man/waybar-network.5.scd`) | Taxa de download e upload instantânea (`bandwidthDownBytes`, `bandwidthUpBytes`), SSID, sinal e IP | `waybar`, `libnl` | Mínimo. Código C++ nativo que lê netlink socket do kernel | MIT |
| `waybar-tailscale` | federicovolponi/waybar-tailscale (`waybar-tailscale.sh`) | Mostra status da VPN Tailscale, IP atribuído, exit node atual e menu para alternar conexões | `tailscale`, `jq`, menu (`fuzzel` ou `rofi`) | Baixo com intervalo de 10s a 30s. Faz chamada a subprocesso `tailscale status --json` | MIT |
| `wireguard-manager` | Klafyvel/wireguard-manager (`wireguard-manager.sh`) | Indicador de túnel WireGuard (`wg-quick@wg0`) e controle liga/desliga com elevação via sudo | `wireguard-tools`, `systemd`, `rofi`, `sudo` | Baixo com intervalo regular. Faz chamada a `systemctl is-active` | MIT |
| `waybar-vpn-modules` | nicolasacchi/waybar-vpn-modules (`scripts/vpn.sh`, `scripts/tailscale.sh`) | Detecta VPN ativa no NetworkManager (`nmcli`) e exibe servidor Proton VPN ou nó Tailscale | `networkmanager` (`nmcli`), `tailscale` | Baixo. Consulta rápida por DBus ao NetworkManager | MIT |
| `waybar-internet-widget` | kagetora66/waybar-internet-widget (`internet_status.py`) | Exibe ping em milissegundos para 8.8.8.8 continuamente | `python`, `iputils` (`ping`) | Alto. Loop infinito de 1 segundo executando `ping -c1`, mantendo a CPU acordada | Sem licença explícita |

Observações sobre rede:
- A Waybar já calcula internamente as taxas de transferência no módulo nativo
  `network`. O Jangada atualmente exibe a banda apenas na dica (tooltip) e no
  formato ethernet, mantendo o SSID no formato Wi-Fi. O custo de expor esses
  dados no formato principal ou em modo alternativo (`format-alt`) é nulo em
  processos extras.
- Para VPN, a abordagem de `nicolasacchi/waybar-vpn-modules` usando `nmcli` é
  muito compatível com o Jangada, pois `bin/jangada-rede` já se apoia no
  NetworkManager.
- Scripts de ping contínuo a cada segundo são contraindicados para estações de
  trabalho e notebooks devido ao desperdício energético e tráfego desnecessário.

### 3.2. Agentes e Inteligência Artificial

| Candidato | Fonte (Repositório e Arquivo) | O que faz | Dependências | Custo de CPU e Rede | Licença |
|---|---|---|---|---|---|
| `ai-usagebar` | akitaonrails/ai-usagebar (`src/waybar.rs`, `src/widget/cli.rs`) | Monitora uso e limites de planos de Claude, OpenAI, Ollama local e OpenRouter. Atualiza via sinal 13 | Binário compilado em Rust | Mínimo. Execução rápida em Rust e atualização reativa por sinal | MIT |
| `claudebar` | mryll/claudebar (`claudebar`) | Exibe limites do plano Claude Code (sessão de 5 horas, semanal e por modelo), progresso e tempo para reset | `bash`, `curl`, `jq` | Baixo com cache local (evita chamadas redundantes à API da Anthropic) | MIT |
| `waybar-claude-fetch` | SirAllap/waybar-scripts-collection (`waybar-claude-usage.py`, `waybar-claude-fetch.py`) | Coleta dados de `/usage` do Claude Code via pseudo-terminal (`pty`) em segundo plano e expõe cache JSON | `python`, `claude` CLI | Zero na leitura da barra. Custo moderado a cada 15-30 minutos no coletor em segundo plano | Sem licença explícita |
| `waybar-ai-usage` | NihilDigit/waybar-ai-usage (`waybar_ai_usage.py`) | Gera e mantém módulos Waybar para Claude Code e OpenAI Codex a partir de tokens locais | `python`, `json5` | Baixo. Leitura periódica de arquivos locais de credenciais | MIT |
| `waybar-claude-code` | hxreborn/waybar-claude-code (`cmd/waybar-claude-code/main.go`) | Widget em Go para contagem de tokens e custos de sessões do Claude Code | Binário Go | Baixo. Processo leve em Go | MIT |
| `codexbar-waybar` | Marouan-chak/codexbar-waybar (`README.md`, scripts de integração) | Faz ponte entre o CLI `codexbar` (Claude/OpenAI/Gemini) e a Waybar, adicionando popover GTK4 | CLI `codexbar`, GTK4 | Médio. Depende da execução do binário externo `codexbar` | MIT |

Observações sobre agentes e IA:
- O Jangada já possui uma solução própria muito estruturada: o módulo
  `custom/agentes` (`bin/jangada-agentes`), que conta sessões tmux ativas,
  classifica estados (`trabalhando`, `aguardando`, `concluido`) e integra com
  `bin/jangada-consumo` para estimar tokens em blocos de 5 horas.
- A técnica mais relevante observada em `claudebar` e no coletor do SirAllap é
  a exibição da janela de tempo restante para a renovação da cota de 5 horas do
  Claude Code. Incorporar essa lógica diretamente no `bin/jangada-consumo`
  agrega valor ao Jangada sem a necessidade de um módulo separado na barra.
- A abordagem do `ai-usagebar` em emitir sinais de tempo real (`pkill
  -RTMIN+13 waybar`) segue o padrão que o Jangada já adota para atualizações
  de sistema.

### 3.3. Sistema (GPU NVIDIA, Disco, Snapshots, Atualizações e Systemd)

| Candidato | Fonte (Repositório e Arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Módulo nativo `systemd-failed-units` (Waybar) | Alexays/Waybar (`src/modules/systemd_failed_units.cpp`, `man/waybar-systemd-failed-units.5.scd`) | Monitora serviços de sistema e usuário com falha no systemd. Esconde-se automaticamente quando tudo está saudável (`hide-on-ok: true`) | `waybar`, `libsystemd` | Mínimo. Escuta eventos do systemd via DBus em C++, sem polling externo | MIT |
| Módulo nativo `disk` (Waybar) | Alexays/Waybar (`src/modules/disk.cpp`, `man/waybar-disk.5.scd`) | Mostra porcentagem de uso e espaço livre da partição raiz ou `/home`, com suporte a limiares de aviso | `waybar`, C libc (`statvfs`) | Praticamente nulo. Uma syscall direta a cada 30 ou 60 segundos | MIT |
| `custom/gpuinfo` | prasanthrangan/hyprdots (`Configs/.config/waybar/modules/gpuinfo.jsonc`, `gpuinfo.sh`) | Exibe uso, VRAM e temperatura de GPU NVIDIA/AMD/Intel, com detecção de barramento PCI e alternância | `nvidia-utils` (`nvidia-smi`), `pciutils` | Moderado a alto no caso NVIDIA. Chamar `nvidia-smi` a cada 5 segundos impede a suspensão da placa dedicada | GPL-3.0 |
| `waybar-module-pacman-updates` | coffebar/waybar-module-pacman-updates (`src/main.rs`, `src/checkupdates_lock.rs`) | Conta atualizações do Arch e AUR com controle de trava concorrente | `pacman-contrib`, binário Rust | Baixo. Polling longo e bloqueio durante operações de instalação | GPL-3.0 |
| Módulos de sistema do JaKooLit | JaKooLit/Hyprland-Dots (`config/waybar/Modules`) | Agrupamento de disco (`disk`), memória, processador e temperatura com formatação densa | Módulos nativos | Quase nulo | GPL-3.0 |

Observações sobre sistema:
- O módulo nativo `systemd-failed-units` é um achado de alto valor: permite
  detectar falhas silenciosas de serviços em segundo plano (como syncthing,
  serviços de rede ou agentes) e fica 100% invisível quando não há problemas.
- O módulo nativo `disk` supre uma lacuna evidente: desenvolvimento com
  worktrees de Git, contêineres e modelos de IA preenche discos velozmente.
- O polling curto de `nvidia-smi` em scripts como o do Hyprdots (intervalo de 5
  segundos) acorda a placa NVIDIA dedicada de estados de economia de energia
  (D3cold), causando drenagem severa de bateria em laptops híbridos. Se adotado
  no Jangada, o monitoramento de GPU deve ser sob demanda ou com verificação
  prévia de estado.

### 3.4. Produtividade (Pomodoro, Calendário, Notificações, Clipboard e Gravação)

| Candidato | Fonte (Repositório e Arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Widget SwayNC (`custom/notification`) | ErikReider/SwayNotificationCenter (`swaync-client`) | Indicador de notificações pendentes, modo Não Perturbe e painel de controle interativo | `sway-notification-center` | Mínimo. Cliente persistente orientado a eventos (`swaync-client -swb`), sem polling | GPL-3.0 |
| `tomat` | jolars/tomat (`docs/src/guide/integration/status-bars/waybar.md`, `examples/waybar-config.json`) | Temporizador Pomodoro em Rust com integração completa para Waybar (fases de trabalho, descanso e pausa) | Binário `tomat` (Rust) | Baixo em binário, mas usa polling de 1s para atualizar o contador visual | MIT |
| `waybar-module-pomodoro` | Andeskjerf/waybar-module-pomodoro (`src/main.rs`) | Pomodoro simples com 4 ciclos e intervalos em binário Rust | Binário Rust | Baixo | Unlicense |
| `waybar-pomodoro-timer` | niraletter/waybar-pomodoro-timer (`timer.sh`) | Cronômetro e Pomodoro em Bash puro com sons de alerta e ícones | `bash`, tocador de áudio (`mpv`) | Médio. Múltiplos forks de bash por segundo durante contagem | MIT |
| `waybar-screenrecorder` | raffaem/waybar-screenrecorder (`screenrecorder`) | Indicador de gravação de tela com `wf-recorder`, com status na dica e controle por sinal | `wf-recorder`, `ffmpeg` | Zero quando inativo. Atualiza por sinal `pkill -RTMIN+1 waybar` | MIT |
| `custom/cliphist` | prasanthrangan/hyprdots (`Configs/.config/waybar/modules/cliphist.jsonc`) | Botão de área de transferência na barra que abre histórico no menu seletor | `cliphist`, `wl-clipboard`, `fuzzel` ou `rofi` | Zero. Módulo estático que só executa comando sob o clique | GPL-3.0 |
| `nextmeeting` | chmouel/nextmeeting (`README.md`) | Próxima reunião do Google Agenda/CalDAV com contagem regressiva e links de videoconferência | `python`, `gcalcli` | Baixo com cache de 5 a 15 minutos | Apache-2.0 |

Observações sobre produtividade:
- O módulo de gravação de tela acionado por sinal (`waybar-screenrecorder`) é
  um excelente modelo arquitetural: sem gravação ativa, o módulo consome zero
  ciclos de processamento e mantém a barra limpa.
- O botão de histórico de área de transferência (`cliphist`) com `fuzzel` se
  integra perfeitamente às ferramentas já adotadas pelo Jangada.
- O SwayNC oferece um canal de eventos muito eficiente via DBus (`swaync-client
  -swb`), mas sua adoção depende da escolha entre o Mako (já comum em
  instalações mínimas) e o SwayNC como daemon de notificações.

### 3.5. Outros Módulos e Técnicas de Destaque

| Candidato | Fonte (Repositório e Arquivo) | O que faz | Dependências | Custo de CPU | Licença |
|---|---|---|---|---|---|
| Módulo nativo `privacy` (Waybar) | Alexays/Waybar (`src/modules/privacy/privacy.cpp`, `man/waybar-privacy.5.scd`) | Indicador nativo de captura de áudio (microfone ativo por app) e compartilhamento/gravação de tela | `waybar`, `pipewire`, `wireplumber` | Mínimo. Reativo a nós e streams do PipeWire em C++, zero polling | MIT |
| Módulo nativo `hyprland/submap` (Waybar) | Alexays/Waybar (`src/modules/hyprland/submap.cpp`, `man/waybar-hyprland-submap.5.scd`) | Exibe o submap (modo) atual do Hyprland (ex: resize, passthrough) e some quando no modo padrão | `waybar`, Hyprland IPC | Zero em repouso. Escuta o socket UNIX do Hyprland | MIT |
| Módulo nativo `gamemode` (Waybar) | Alexays/Waybar (`src/modules/gamemode.cpp`, `man/waybar-gamemode.5.scd`) | Mostra quando o daemon Feral GameMode está ativo otimizando processos | `waybar`, `gamemode` | Mínimo. Consulta ao DBus do GameMode | MIT |
| Temas dinâmicos do Dusky | dusklinux/dusky (`.config/matugen/generated_fresh/waybar-colors.css`) | Arquitetura de estilização da Waybar baseada em variáveis geradas pelo Matugen (`@define-color`) | `matugen`, `waybar` | Zero em execução | MIT |
| `wttrbar` | bjesus/wttrbar (`src/main.rs`) | Informações climáticas e previsão meteorológica detalhada com gráficos no tooltip | `wttrbar` (AUR) | Baixo em CPU, depende de rede externa e serviço wttr.in | MIT |

Observações sobre outros módulos:
- O módulo nativo `privacy` atende diretamente ao apontamento do benchmark
  anterior sobre aviso visual quando o microfone está sendo capturado por
  terceiros, aproveitando a infraestrutura WirePlumber já instalada no Jangada.
- O repositório `dusky` confirma a solidez da escolha do Jangada pelo Matugen:
  ambos utilizam variáveis `@define-color` em CSS para desacoplar a geometria
  da barra da geração de temas.

## 4. As 10 Melhores Recomendações para o Jangada

Abaixo estão as 10 melhores propostas de módulos e aprimoramentos para a barra
do Jangada, ordenadas por valor agregado, alinhamento com as regras do projeto
e eficiência operacional.

### 1. Módulo nativo `systemd-failed-units`
- Motivo: Monitoramento preventivo de integridade do sistema operacional. O
  Jangada é uma máquina de trabalho onde rodam múltiplos daemons e serviços de
  usuário. Com a opção `"hide-on-ok": true`, o módulo permanece totalmente
  invisível durante a operação normal, ocupando zero espaço na barra. Quando
  qualquer unidade falha (no sistema ou na sessão do usuário), o ícone aparece
  em destaque. O consumo é desprezível pois é C++ nativo escutando sinais do
  systemd via DBus.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo da Waybar inserido no array `modules-right` de
  `default/waybar/config.jsonc`, com estilização em `default/waybar/base.css`
  usando a classe `#systemd-failed-units.degraded` com a cor `@atencao`.

### 2. Módulo nativo `privacy` (Proteção de microfone e captura de tela)
- Motivo: Segurança visual imediata. Notifica o usuário caso qualquer processo
  em segundo plano esteja capturando o microfone ou gravando a tela.
  Completamente reativo via nós do PipeWire (sem necessidade de scripts ou
  consultas periódicas). Resolve o ponto registrado na comparação anterior
  sobre monitoramento de dispositivos de entrada em uso ativo.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo da Waybar (`privacy`) em `config.jsonc` com
  configuração para `screenshare` e `audio-in`. Estilização em `base.css` sob a
  classe `#privacy-item` com cor de destaque `@atencao`.

### 3. Módulo nativo `disk` (Espaço em disco com limiares de alerta)
- Motivo: O trabalho contínuo com múltiplos agentes de IA, worktrees do Git e
  atualizações de sistema tende a preencher partições rapidamente. O módulo
  nativo usa a syscall `statvfs()` a cada 30 ou 60 segundos, sem custo de
  subprocessos. Permite configurar limiares de aviso (`states`: 80% e 90%),
  mudando de cor e permitindo que o clique abra o `bin/jangada-monitor`.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo `disk` em `default/waybar/config.jsonc` com
  formato compacto (ex: `󰋊 {percentage_used}%`), tooltip completo e regra em
  `default/waybar/base.css`.

### 4. Enriquecimento de cotas e reset do Claude no `custom/agentes`
- Motivo: Em vez de incluir um novo módulo na barra (como fazem `claudebar` e
  `ai-usagebar`), a melhor decisão para o Jangada é enriquecer o módulo
  existente `custom/agentes`. O Jangada já calcula o consumo de tokens em 5
  horas via `bin/jangada-consumo`. Incorporar a estimativa de tempo para a
  renovação da janela de 5 horas e a porcentagem de cota diretamente na dica do
  `bin/jangada-agentes` mantém a barra limpa e centraliza todas as informações
  do agente no mesmo local.
- Esforço estimado: Médio.
- Como encaixaria: Ajuste no script `bin/jangada-consumo` e na montagem do campo
  `tooltip` em `bin/jangada-agentes --waybar`, sem alterar a lista de módulos da
  Waybar.

### 5. Botão de histórico de área de transferência (`custom/cliphist`)
- Motivo: Recurso de alta utilidade prática no dia a dia de código. Inspirado
  no módulo `custom/cliphist` do Hyprdots
  (`Configs/.config/waybar/modules/cliphist.jsonc`), é um módulo estático que
  não roda nenhum script em segundo plano (zero polling). O clique com o botão
  esquerdo abre o menu seletor de histórico do `cliphist` formatado no `fuzzel`
  (já integrado ao tema do Jangada), e o clique com botão direito permite limpar
  o histórico.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo `custom/cliphist` em `default/waybar/config.jsonc`
  apontando o `on-click` para comando com `cliphist`, `fuzzel` e `wl-copy`.

### 6. Indicador de gravação de tela acionado por sinal (`custom/gravacao`)
- Motivo: Feedback essencial durante gravações de demonstração e registros de
  bugs. Inspirado na implementação de `waybar-screenrecorder`, o módulo
  permanece com texto vazio (`{text: ""}`) quando inativo, sendo recolhido pela
  Waybar. Ao acionar o script de gravação (apoiado em `wf-recorder` ou
  `wl-screenrec`), o script dispara um sinal de atualização em tempo real para a
  Waybar, exibindo o ponto vermelho de gravação e a duração.
- Esforço estimado: Médio.
- Como encaixaria: Módulo `custom/gravacao` em `config.jsonc` com escuta de sinal
  dedicado (ex: sinal 9), controlado por novo utilitário em `bin/jangada-gravar`
  e atalho correspondente em `default/hypr/atalhos.lua`.

### 7. Módulo nativo `hyprland/submap`
- Motivo: O Hyprland permite criação de submaps (modos específicos para atalhos
  modais, redimensionamento de janelas ou passthrough para máquinas virtuais).
  O módulo nativo `hyprland/submap` escuta o socket IPC do Hyprland por
  eventos, ficando invisível no modo padrão e exibindo o nome do modo ativo com
  destaque visual imediato quando ativado.
- Esforço estimado: Baixo.
- Como encaixaria: Módulo nativo `hyprland/submap` em `default/waybar/config.jsonc`
  posicionado em `modules-left` ao lado de `hyprland/window`, estilizado em
  `default/waybar/base.css` com borda `@atencao`.

### 8. Gerenciador de VPN com seleção via `fuzzel` (`custom/vpn`)
- Motivo: Conectar e desconectar VPNs (WireGuard, Tailscale ou OpenVPN) sem abrir
  terminal. Tomando como base a integração de `nicolasacchi/waybar-vpn-modules` e
  `federicovolponi/waybar-tailscale`, um script leve pode consultar o
  NetworkManager (`nmcli connection show --active`) ou `tailscale status`,
  exibindo ícone de escudo na barra e abrindo um menu `fuzzel` no clique para
  escolher o túnel ou nó de saída.
- Esforço estimado: Médio.
- Como encaixaria: Módulo `custom/vpn` em `config.jsonc` apoiado por novo script
  `bin/jangada-vpn`, com intervalo longo (30s) ou recarregado via sinal.

### 9. Alternância de exibição de banda no módulo `network` existente
- Motivo: Acompanhar velocidade real de download e upload sem depender de abrir
  o `btop` ou terminal. O módulo nativo `network` já calcula internamente esses
  valores através do kernel (`libnl`). A barra do Jangada já possui o módulo,
  mas exibe o SSID no Wi-Fi e reserva a banda para a dica. Configurar o
  `format-alt` nativo permite alternar com um clique entre o nome da rede e as
  taxas instantâneas de transferência em KB/s ou MB/s.
- Esforço estimado: Baixo.
- Como encaixaria: Ajuste direto nas propriedades `"format-wifi"`,
  `"format-ethernet"` e `"format-alt"` do bloco `"network"` em
  `default/waybar/config.jsonc`.

### 10. Temporizador Pomodoro discreto com controle de foco (`custom/pomodoro`)
- Motivo: Gestão de pausas e foco contínuo para longas sessões de desenvolvimento.
  Soluções como `tomat` ou temporizadores em script mostram utilidade para
  ritmo de trabalho. A implementação recomendada evita polling contínuo de 1
  segundo quando ocioso, exibindo o tempo apenas quando o ciclo de foco é
  iniciado pelo usuário via atalho ou clique.
- Esforço estimado: Médio.
- Como encaixaria: Módulo custom `custom/pomodoro` em `config.jsonc` acionado
  por script auxiliar em `bin/jangada-pomodoro`, com estados `.foco` e `.pausa`
  estilizados no CSS.

## 5. O que foi Descartado e por Quê

Durante a análise dos 30 repositórios, diversas soluções populares no
ecossistema de ricing foram descartadas por incompatibilidade com os princípios
do Jangada:

1. Polling frequente de GPU via `nvidia-smi` (Hyprdots e SirAllap-scripts):
   - Motivo: O script `gpuinfo.sh` do Hyprdots executa `nvidia-smi` a cada 5
     segundos. Em computadores portáteis com placas híbridas (NVIDIA Optimus),
     consultas repetidas impedem que a placa de vídeo permaneça no estado de
     repouso profundo (D3cold), resultando em alto consumo de energia e
     aquecimento. O monitoramento de GPU deve ocorrer sob demanda (ao abrir o
     monitor de sistema) ou através de bibliotecas diretas como NVML em
     intervalos muito mais espaçados.

2. Módulos de latência e ping a cada segundo (`waybar-internet-widget`):
   - Motivo: Executar um loop em Python com subprocesso `ping` a cada 1 segundo
     gera desperdício contínuo de ciclos de CPU, mantém o rádio sem fio ativo e
     polui a rede local. Testes de conectividade devem ser reativos ao estado da
     interface ou disparados manualmente.

3. Verificadores de atualizações em Rust concorrentes com o pacman
   (`waybar-module-pacman-updates`):
   - Motivo: O Jangada já possui uma solução minimalista e eficiente:
     `custom/atualizacoes` (`bin/jangada-atualizacoes`), que usa `checkupdates`
     (do pacote oficial `pacman-contrib`) em intervalo de 1 hora e conta com
     atualização instantânea via sinal 8 após a conclusão do `jangada-update`.
     Substituir um script shell de 20 linhas por um binário externo em Rust com
     threads e chamadas de rede ao AUR adicionaria sobrecarga sem ganho prático.

4. Módulos com cores fixas em código hexadecimal:
   - Motivo: Múltiplos scripts analisados injetam valores como `"color":
     "#FF0000"` diretamente no payload JSON retornado à Waybar. No Jangada,
     todas as cores são derivadas dinamicamente do papel de parede via Matugen
     e importadas de `cores.css`. Módulos com cores travadas no backend quebram
     a harmonia visual e impedem a troca de tema sem edição de código.

5. Widgets de clima e previsão do tempo remota (`wttrbar` e scripts do SirAllap):
   - Motivo: Requerem chamadas periódicas a APIs de terceiros (como `wttr.in`),
     que sofrem de instabilidade, limitação de taxa e falhas frequentes com
     bloqueio do módulo. Informações meteorológicas não compõem a operação do
     sistema e competem por espaço útil na barra de ferramentas.

6. Sobreposição de daemons de notificação pesados (SwayNC em substituição ao Mako):
   - Motivo: Embora o cliente `swaync-client` ofereça um ótimo protocolo de
     comunicação contínua, substituir o daemon de notificações Mako pelo SwayNC
     exigiria trocar todo o subsistema de avisos do Jangada apenas para exibir
     um ícone de sino na barra. O Mako é extremamente leve, rápido e atende ao
     escopo do projeto sem complexidade adicional.

7. Multiplicidade de módulos de cotas de IA concorrentes na barra:
   - Motivo: Adotar separadamente `claudebar`, `waybar-claude-code` e
     `codexbar-waybar` criaria fragmentação na barra. Como o Jangada já possui
     um ecossistema focado em sessões de agentes (`bin/jangada-agentes`), a
     duplicação de ícones na barra polui a interface visual.

## 6. Mapeamento de Fontes e Arquivos

Todas as análises e constatações apresentadas neste documento foram verificadas
diretamente nos arquivos dos repositórios de referência clonados:

- Módulos nativos da Waybar:
  - Repositório: https://github.com/Alexays/Waybar
  - Arquivos: `src/modules/systemd_failed_units.cpp`, `src/modules/privacy/privacy.cpp`,
    `src/modules/disk.cpp`, `src/modules/hyprland/submap.cpp`,
    `src/modules/network.cpp`, `man/waybar-systemd-failed-units.5.scd`,
    `man/waybar-privacy.5.scd`, `man/waybar-disk.5.scd`.
- Scripts de hardware e GPU do Hyprdots:
  - Repositório: https://github.com/prasanthrangan/hyprdots
  - Arquivos: `Configs/.config/waybar/modules/gpuinfo.jsonc`,
    `Configs/.local/share/bin/gpuinfo.sh`.
- Módulos modulares do JaKooLit:
  - Repositório: https://github.com/JaKooLit/Hyprland-Dots
  - Arquivos: `config/waybar/Modules`, `config/waybar/ModulesCustom`.
- Integração de temas com Matugen:
  - Repositório: https://github.com/dusklinux/dusky
  - Arquivos: `.config/matugen/generated_fresh/waybar-colors.css`,
    `.config/waybar/01_mechabar_h/config.jsonc`.
- Ferramentas de IA e agentes:
  - `ai-usagebar`: https://github.com/akitaonrails/ai-usagebar (`src/waybar.rs`, `src/widget/cli.rs`).
  - `claudebar`: https://github.com/mryll/claudebar (`claudebar`).
  - `codexbar-waybar`: https://github.com/Marouan-chak/codexbar-waybar (`README.md`).
  - `waybar-ai-usage`: https://github.com/NihilDigit/waybar-ai-usage (`waybar_ai_usage.py`).
  - `waybar-claude-code`: https://github.com/hxreborn/waybar-claude-code (`cmd/waybar-claude-code/main.go`).
  - `waybar-scripts-collection`: https://github.com/SirAllap/waybar-scripts-collection (`waybar-claude-usage.py`, `waybar-claude-fetch.py`).
- Módulos de rede e VPN:
  - `waybar-tailscale`: https://github.com/federicovolponi/waybar-tailscale (`waybar-tailscale.sh`).
  - `wireguard-manager`: https://github.com/Klafyvel/wireguard-manager (`wireguard-manager.sh`).
  - `waybar-vpn-modules`: https://github.com/nicolasacchi/waybar-vpn-modules (`scripts/vpn.sh`, `scripts/tailscale.sh`).
  - `waybar-internet-widget`: https://github.com/kagetora66/waybar-internet-widget (`internet_status.py`).
- Módulos de produtividade e notificações:
  - `custom/cliphist`: https://github.com/prasanthrangan/hyprdots (`Configs/.config/waybar/modules/cliphist.jsonc`).
  - `SwayNotificationCenter`: https://github.com/ErikReider/SwayNotificationCenter (`README.md`).
  - `tomat`: https://github.com/jolars/tomat (`docs/src/guide/integration/status-bars/waybar.md`).
  - `waybar-module-pomodoro`: https://github.com/Andeskjerf/waybar-module-pomodoro (`src/main.rs`).
  - `waybar-pomodoro-timer`: https://github.com/niraletter/waybar-pomodoro-timer (`timer.sh`).
  - `waybar-screenrecorder`: https://github.com/raffaem/waybar-screenrecorder (`screenrecorder`).
  - `nextmeeting`: https://github.com/chmouel/nextmeeting (`README.md`).
  - `waybar-module-pacman-updates`: https://github.com/coffebar/waybar-module-pacman-updates (`src/main.rs`).
