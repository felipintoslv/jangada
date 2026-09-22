# Revisão do benchmarking de waybar (Claude)

Revisão do `benchmarking/README.md` feito pelo agy no ramo
`agente/benchmarking-agy`. Conferi as afirmações contra os clones em
`referencia/` (dados de estrelas, licença e último envio em
`referencia/meta.json`) e contra o código do jangada. O que segue são pontos
que o README ainda precisa resolver ou que você precisa decidir.

## Como a sessão andou

- O agy clonou 31 repositórios em `referencia/` e escreveu o README.
- As correções do primeiro parecer estão no commit ae6fef1.
- A segunda rodada do `jangada-validar` ficou esperando a sua aprovação na
  janela do agy: a regra de permissão da minha sessão bloqueia aprovar um
  comando que abre outro agente (`claude -p`). Ao aprovar, o agy segue sozinho.
- O primeiro parecer do `jangada-validar`
  (`~/.local/state/jangada/agentes/validacao-jangada--benchmarking-agy-r1.md`)
  pediu três correções: fonte inventada do `custom/cliphist` (citava o
  JaKooLit, que não tem esse módulo; o arquivo real é
  `referencia/hyprdots/Configs/.config/waybar/modules/cliphist.jsonc`), nome do
  dono do `waybar-screenrecorder` (`raffaem`, não `raffaelemancuso`) e o
  `CLAUDE.md` de terceiros trazido pelos clones.
- Sobre o último ponto: cinco clones trazem `CLAUDE.md` (ai-usagebar,
  claudebar, waybar-ai-usage, waybar-claude-code, tomat) e quatro traziam
  `AGENTS.md`. O Claude Code carrega esses arquivos como instrução do projeto
  quando roda naquele worktree, e o `jangada-validar` roda o `claude -p` lá.
  O agy apagou os `AGENTS.md` com um `find ... -o ... -delete` que, pela
  precedência do `find`, não pegou os `CLAUDE.md`. Renomeei os cinco para
  `CLAUDE.md.terceiro`. A resposta que o agy passou ao `jangada-validar`
  diz que os `CLAUDE.md` foram removidos; foram renomeados por mim. Vale
  registrar na skill (regra 8 do AGENTS.md): clone de referência dentro do
  worktree vira instrução para o agente revisor.

## Conflitos com o benchmark anterior

`revisao/benchmark-waybar-omarchy.md` já decidiu pontos que o README reabre
sem dizer por quê:

1. Recomendação 9 (banda no rótulo do `network`): já proposta na tabela da
   parte 1, linha 40 ("Banda instantânea no rótulo e na dica"). Repetição.
2. Recomendação 8 (VPN, apoiada em `waybar-tailscale`): a parte 5, seção
   "Tailscale, Dropbox e teste de velocidade de disco", descartou Tailscale
   porque o jangada não instala. A parte com `nmcli` (VPN do NetworkManager)
   é nova e cabe; a parte Tailscale contradiz a decisão.
3. Recomendação 4 ("porcentagem de cota" na dica do `custom/agentes`): a parte
   5, "Medir cota de assinatura de agente", descartou cota por depender de API
   de terceiro. A outra metade, tempo até a renovação do bloco de 5 horas, sai
   de dado local que o `bin/jangada-consumo` já lê e não conflita.
4. Descarte 5 (clima): já descartado em "Clima na barra". Repetição, sem dano.

## Afirmações que não conferem com o jangada

1. Recomendação 5 (`custom/cliphist`): o jangada já tem histórico de área de
   transferência. `default/hypr/inicio.lua:9-10` grava com `cliphist store` e
   `bin/jangada-menu:15` abre `cliphist list` no fuzzel. O módulo seria só um
   segundo ponto de entrada; o README não diz isso.
2. Recomendação 7 (`hyprland/submap`): nenhum arquivo em `default/hypr/` define
   submap (`grep -rn submap default/hypr` vazio). O módulo ficaria sempre
   oculto até alguém criar um submap.
3. Descarte 3 chama `bin/jangada-atualizacoes` de "script shell de 20 linhas";
   o arquivo tem 57.
4. Recomendação 3 manda o clique do `disk` abrir `bin/jangada-monitor`, que é
   o btop/htop (`bin/jangada-monitor:2`), não um visor de disco. Funciona, mas
   o texto sugere outra coisa.

## Critério dos 12 meses

O prompt pedia repositórios com commits nos últimos 12 meses (desde
22/09/2025). Pelo `referencia/meta.json`, cinco estão fora:
Klafyvel/wireguard-manager (2023-02-02), raffaem/waybar-screenrecorder
(2024-02-19), prasanthrangan/hyprdots (2025-03-23),
kagetora66/waybar-internet-widget (2025-07-27) e sameemul-haque/dotfiles
(2025-08-20). Dois deles sustentam recomendações: o hyprdots (fonte do
cliphist e do exemplo de GPU) e o waybar-screenrecorder (modelo da
recomendação 6). O README não marca a data. Sem os cinco, restam 25, o
mínimo pedido.

## Lacunas de cobertura

- Snapshots: pedido na categoria c e ausente. O jangada tem
  `bin/jangada-snapshot` e `install/pacotes/snapshots.txt` (snapper).
- GPU NVIDIA: o README descarta o polling de `nvidia-smi` e não oferece
  alternativa entre as 10. A afirmação de que `nvidia-smi` a cada 5 s impede o
  D3cold não tem fonte; o intervalo de 5 s confere
  (`referencia/hyprdots/Configs/.config/waybar/modules/gpuinfo.jsonc:6`).
- Gemini e Ollama: nenhum candidato para sessão do Gemini ou do agy. Existe
  `referencia/waybar-ollama` clonado e não citado no README.
- Notificações com mako: o jangada usa mako (`install/pacotes/interface.txt:10`),
  e o README só avalia SwayNC. Um contador do `makoctl` por sinal não foi
  considerado.

## Texto

- Sem travessões.
- Adjetivação que a regra 7 do AGENTS.md pede para tirar, com linha:
  48 ("integração profunda"), 95 ("muito compatível"), 112 ("muito
  estruturada"), 135 ("achado de alto valor"), 137 ("100% invisível"), 138
  ("lacuna evidente", "velozmente"), 142 ("drenagem severa"), 160 ("excelente
  modelo arquitetural"), 163 ("perfeitamente"), 164 ("muito eficiente"), 182
  ("solidez"), 206 ("imediata"), 253 ("essencial"), 344 ("harmonia visual"),
  353 ("ótimo protocolo"), 356 ("extremamente leve"), e "alta utilidade
  prática" na recomendação 5. Números de linha do commit ae6fef1.
- Títulos em caixa alta a cada palavra ("Avaliação por Categoria"), fora do
  padrão dos outros documentos do repositório.
- Mensagem de commit no formato `docs(waybar): ...`; o histórico usa
  `assunto: descrição`.

## O que eu faria

A ordem das recomendações 1 a 3 (`systemd-failed-units`, `privacy`, `disk`)
se sustenta: são módulos nativos, orientados a evento ou com intervalo longo,
e conferem com o código em `referencia/Waybar/src/modules/`
(`systemd_failed_units.cpp` escuta `PropertiesChanged` no DBus, linha 96). Da
4 em diante eu revisaria antes de usar como plano: tirar a 9 (repetida),
reduzir a 8 ao NetworkManager, tirar a cota da 4, rebaixar a 5 e a 7, e
completar snapshots, GPU e mako.
