# jangada

[![verificar](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml/badge.svg)](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml)

Camada de configuração para Arch Linux com Hyprland puro, organizada para o trabalho com agentes de IA. Reúne a estrutura de repositório e de atualização do Omarchy, a geração de cores a partir do papel de parede usada pelo Noctalia e uma camada própria para lançar, acompanhar e encerrar sessões de agentes.

## Princípios

1. **Isolamento.** O jangada roda numa sessão própria (`jangada` no gerenciador de login) e guarda tudo em `~/.config/jangada` e `~/.local/share/jangada`. A configuração atual do Hyprland em `~/.config/hypr`, o Noctalia e qualquer outra sessão continuam intactos e disponíveis como alternativa.
2. **Nada é sobrescrito sem cópia.** Os arquivos de usuário são criados só quando ainda não existem. Arquivos de sistema alterados (`/etc/...`) recebem cópia de segurança com data antes da mudança.
3. **Tudo pode ser repetido.** Cada etapa de instalação pode rodar de novo sem efeito colateral.
4. **Simulação antes de aplicar.** `JANGADA_SIMULAR=1 ./install.sh` mostra cada comando que seria executado, sem executar.
5. **Padrões no repositório, ajustes no usuário.** Os padrões ficam em `default/` e são atualizados com `git pull`. Os ajustes pessoais ficam em `~/.config/jangada` e são carregados depois dos padrões.

## Estrutura

```
jangada/
├── install.sh             ponto de entrada da instalação
├── install/               etapas numeradas, executadas em ordem
│   └── pacotes/           listas de pacotes por grupo
├── bin/                   comandos jangada-* (entram no PATH)
├── default/               padrões atualizáveis (hypr em Lua, waybar, matugen, tmux, hooks e skills dos agentes)
├── config/                modelos copiados uma única vez para ~/.config/jangada
├── shell/                 integração com bash e zsh
├── migrations/            ajustes aplicados em ordem a cada atualização
├── docs/                  processos com fluxogramas, registros e boas práticas
├── testes/                verificar.sh (estático + os demais testes) e aninhado.sh
├── mapeamento/            inventários do jangada-mapear (fora do git)
└── revisao/               pareceres, avaliações e comparações; índice em revisao/README.md
```

## Documentação dos processos

Cada processo tem um documento em `docs/`, com fluxograma, passos por
arquivo e função, falhas e os testes que o cobrem:

| Documento | Processo |
|---|---|
| [docs/ciclo-da-tarefa.md](docs/ciclo-da-tarefa.md) | abertura da sessão, `jangada-validar` e `jangada-agente-fim` |
| [docs/isolamento.md](docs/isolamento.md) | o que o `jangada-isolar` deixa gravável, somente leitura e oculto, e a restauração |
| [docs/subagentes-e-delegacao.md](docs/subagentes-e-delegacao.md) | papéis, destino da delegação e `jangada-delegar` |
| [docs/atualizacao-e-migracoes.md](docs/atualizacao-e-migracoes.md) | instalação, `jangada-update` e `jangada-migrar` |
| [docs/painel.md](docs/painel.md) | coletor, cache, app e módulo da barra |
| [docs/registros.md](docs/registros.md) | campos de cada registro usado pelo painel |
| [docs/boas-praticas.md](docs/boas-praticas.md) | regras de código, testes, textos e commits |

## Antes de instalar: mapear a máquina

Em cada máquina, rode primeiro `bin/jangada-mapear`. Ele registra a configuração atual, inclusive as personalizações do Noctalia, em `mapeamento/` (fora do git). Chaves, tokens, senhas, blocos de chave privada e senhas em URL são mascarados nas cópias; `bin/jangada-mapear --mascarar <arquivo` aplica a mesma máscara a qualquer texto, para conferir antes de compartilhar. O roteiro de resgate está em `revisao/RESGATE.md`.

Quem vem do niri converte a configuração com `jangada-importar`, que lê `~/.config/niri/config.kdl` (ou uma pasta de mapeamento) e grava, sem sobrescrever nada:

| Arquivo gerado | Conteúdo |
|---|---|
| `~/.config/jangada/hypr/usuario.lua.importado` | teclado, variáveis de ambiente, programas ao iniciar e atalhos; os que batem com um padrão do jangada saem comentados, e as ações sem equivalente (colunas, overview) ficam listadas |
| `~/.config/jangada/hypr/monitores.lua.importado` | nome, modo, posição, escala e rotação de cada tela |
| `~/.config/jangada/jangada.conf.importado` | o terminal do `Mod+Return` |

Compare com `diff -u` e copie o que quiser para os arquivos sem a extensão.

## Interface

Em `~/.config/jangada/jangada.conf`, `JANGADA_INTERFACE=componentes` usa waybar, fuzzel e mako com cores do matugen; `JANGADA_INTERFACE=noctalia` usa o Noctalia já instalado dentro da sessão jangada, preservando as personalizações dele.

## Instalação

```sh
git clone <url> ~/.local/share/jangada
cd ~/.local/share/jangada
JANGADA_SIMULAR=1 ./install.sh   # confere o que será feito
./install.sh                     # aplica
```

O `install.sh` recusa rodar da cópia de trabalho (`JANGADA_REPO`), de um
worktree ou de `JANGADA_WORKTREES`: essas pastas são graváveis de dentro do
isolamento, e a pasta da instalação vira o `JANGADA_PATH` dos hooks e da
sessão. Nelas só a simulação roda.

Depois, encerre a sessão atual e escolha **jangada** no gerenciador de login.

### Máquinas com duas GPUs

O `jangada-sessao` define `AQ_DRM_DEVICES` antes de o compositor subir, escolhendo a placa que tem monitor ligado. Sem isso, o aquamarine pode pegar a outra e a sessão sobe sem imagem, sem terminal para consertar. Quando a placa escolhida é NVIDIA, a sessão também define `LIBVA_DRIVER_NAME`, `__GLX_VENDOR_LIBRARY_NAME` e `NVD_BACKEND`; `GBM_BACKEND` fica de fora de propósito, porque quebra Firefox e Electron. Para forçar outra placa, preencha `JANGADA_GPU` no `jangada.conf` com um caminho de `/dev/dri/by-path`. O caminho escolhido é sempre resolvido para o `/dev/dri/cardN` correspondente antes de virar `AQ_DRM_DEVICES`: o aquamarine separa essa lista por `:`, e o endereço PCI de `/dev/dri/by-path` também tem `:`, então o caminho cru vira três caminhos inválidos e o compositor aborta antes de abrir a tela. O `jangada-verificar` mostra qual placa foi escolhida, o valor resolvido e reclama se ela não tiver monitor ligado.

## Cores e papel de parede

`jangada-tema imagem` gera com o matugen as cores de bordas de janela, barra, notificações, menu, bloqueio, terminal e tela de login. A cor-fonte é escolhida pelo `prefer` do `default/matugen/config.toml`, e o esquema vem de `JANGADA_TEMA_ESQUEMA` (padrão `scheme-fidelity`, que mantém a cor da imagem; o `scheme-tonal-spot` do matugen satura imagens quase monocromáticas até virarem outra cor).

O papel de parede aparece inteiro em todas as telas. Numa tela de proporção diferente da imagem, como um monitor 21:9 com uma figura 16:9, o `jangada-tema` gera uma versão com as medidas da tela (em `~/.cache/jangada/papel`) e a entrega ao swaybg e ao hyprlock; o tema de login faz a mesma conta em cada tela. `JANGADA_PAPEL_AJUSTE` escolhe como completar o espaço que sobra: `espelho` (padrão, reflete a borda da figura), `desfoque`, `cor` ou `cobrir` (o comportamento antigo, que corta a figura).

## Tela de login (SDDM)

`jangada-sddm aplicar` instala o tema `jangada` em `/usr/share/sddm/themes/jangada` e faz o SDDM ler as sessões de `/usr/local/share/jangada/sessoes`, que só contém o jangada. Os arquivos de sessão dos outros pacotes (Hyprland, niri, Plasma) não são movidos nem apagados; `jangada-sddm restaurar` remove `/etc/sddm.conf.d/zz-jangada.conf` e todas voltam a aparecer. O prefixo `zz-` faz o arquivo ser lido depois do `kde_settings.conf`, que de outro modo imporia o tema escolhido no Plasma.

O tema imita o menu do `SUPER + Esc`: caixa centralizada com as mesmas medidas do fuzzel, linhas `usuário >` e `senha >` e a lista **Entrar**, **Suspender**, **Reiniciar** e **Desligar**. Setas escolhem a ação e Enter executa; digitar a senha volta a seleção para Entrar. As cores vêm de um modelo próprio do matugen (`default/matugen/modelos/sddm.conf`, gerado em `~/.config/jangada/sddm/theme.conf.user`), com os mesmos papéis de cor do fuzzel, e o fundo é o papel de parede atual, copiados no momento do `aplicar`. O SDDM fica numa pasta do sistema, então o `jangada-tema` não consegue atualizá-lo sozinho: quando as cores ou o papel de parede mudam, ele avisa que é preciso rodar `jangada-sddm aplicar` de novo. `jangada-sddm testar` abre o tema numa janela, sem alterar o sistema.

A instalação pergunta se deve aplicar a exclusividade; a resposta padrão é não.

## Comandos

| Comando | Função |
|---|---|
| `jangada-update` | busca o ramo de `JANGADA_CANAL`, mostra os commits novos, o resumo por arquivo e um aviso quando mudam `migrations/`, `install/` ou `bin/`, e só os aplica se a resposta for `s` (sem terminal não aplica); mostra se o conjunto do Hyprland mudou, atualiza o sistema, aplica migrações, confere initramfs e driver NVIDIA e roda o gancho `pos-update`. Se o pacman ou o AUR falhar, a conferência da imagem de boot roda mesmo assim, e as migrações e a recarga do Hyprland ficam para depois do conserto |
| `jangada-verificar` | confere pacotes, snapshots, sessão, hooks e erros de configuração do Hyprland; `--diagnostico` grava um relatório e `--agente` abre um agente com ele no repositório do jangada; do `hyprland.log` entram só erros e avisos, e o log e o relatório de falha vão marcados como dados |
| `jangada-versao` | mostra a versão da cópia (`0.1.0`, ou `0.1.0-3-gabc1234` com commits depois da tag); `--novidades [DE [ATE]]` lista as mudanças, `--registro` imprime o registro completo e `--lancar X.Y.Z` grava o `CHANGELOG.md`, faz o commit e cria a tag `vX.Y.Z` (sem push); `-C DIR` opera em outro repositório |
| `jangada-migrar` | aplica as migrações pendentes (o `jangada-update` já chama) |
| `jangada-snapshot "descrição"` | cria um snapshot manual do sistema; com `--agente`, o do `jangada-agente --snapshot`, fora da limpeza do snapper e limitado aos `JANGADA_SNAPSHOTS_AGENTE` mais recentes |
| `jangada-tema [imagem]` | gera as cores a partir de um papel de parede e recarrega a interface |
| `jangada-agente` | escolhe o agente (Claude ou agy), o projeto e cria um worktree, e abre o agente numa sessão tmux, isolado pelo `jangada-isolar` (`--prompt`, `--prompt-arquivo`, `--perfil`, `--sem-isolar`) |
| `jangada-isolar` | roda um comando no bubblewrap, com o sistema somente leitura e a pasta atual gravável; `--mostrar` imprime a chamada ao `bwrap` |
| `jangada-delegar PAPEL "pedido"` | manda leitura, pesquisa ou verificação a um agente Flash do agy e devolve um relatório curto; recusa com código 4 quando a cota está baixa (ver [Subagentes](#subagentes)) |
| `jangada-subagentes` | indicadores de subagentes e delegações (`--json`), o resumo de uma entrega (`--entrega PASTA`) e os registros por subagente (`--registros`) |
| `jangada-filtrar` | roda um comando e condensa a saída para o agente (`-m`, `-e`, `-p`); prefira `jangada-filtrar -- COMANDO` ao modo cano, que não vê o código de saída |
| `jangada-mapa [PASTA]` | mapa compacto do repositório (arquivos e assinaturas de funções) para dar contexto a um agente |
| `jangada-worktree-preparar` | leva para um worktree novo os arquivos ignorados que o projeto precisa (chamado pelo `jangada-agente`) |
| `jangada-validar` | manda o diff do worktree para o outro modelo revisar (o agy revisa o Claude, o Claude revisa o agy) e devolve `STATUS: APROVADO` ou `REVISAR`; o agente chama antes de entregar |
| `jangada-shell` | inicia subshell enriquecida com comandos diretos de agentes e projetos |
| `jangada-agentes` | lista as sessões de agentes, com estado, e permite abrir, integrar ou encerrar (`--proximo`, `--anterior`, `--restaurar`) |
| `jangada-agente-fim` | encerra uma sessão e remove o worktree, com conferência de alterações pendentes; `--integrar` faz antes o merge na base e apaga o ramo; no repositório do jangada, avisa para rodar `jangada-update`, que atualiza a cópia instalada |
| `jangada-consumo` | tokens do Claude Code no bloco de 5 horas em andamento (também no tooltip da barra) |
| `jangada-painel` | painel de indicadores do uso de IA num app Shiny local; `--json` imprime os do dia, `--parar` encerra o app, `--conferir` lista o que falta |
| `jangada-gancho` | roda os ganchos do usuário de um evento (chamado pelos outros comandos) |
| `jangada-importar` | converte a configuração do niri em arquivos `.importado` |
| `jangada-atalhos` | mostra todos os atalhos ativos, lidos do próprio Hyprland (`--lista` para o terminal) |
| `jangada-sddm aplicar` | deixa o jangada como única sessão no SDDM, com o tema de login do jangada (`restaurar`, `status`, `testar`) |
| `jangada-barra` | sobe ou reinicia a waybar do jangada; `--posicao topo\|base\|esquerda\|direita\|ciclo` troca a borda |
| `jangada-recarregar` | recarrega o Hyprland e mostra os erros de configuração |
| `jangada-rede`, `jangada-bluetooth`, `jangada-audio`, `jangada-energia` | menus no fuzzel para Wi-Fi e cabo, dispositivos Bluetooth, saída e entrada de áudio, e perfil de energia e bateria (abertos pela barra) |
| `jangada-calendario`, `jangada-captura`, `jangada-monitor`, `jangada-atualizacoes` | calendário com eventos, captura de tela (`regiao\|tela`), monitor do sistema e atualizações pendentes (abertos pela barra e pelos atalhos) |
| `jangada-menu` | menu central com as ações acima, mais bloquear, suspender, reiniciar, desligar e sair |
| `jangada-logo` | mostra o símbolo do jangada com as informações do sistema (fastfetch; neofetch como alternativa) |
| `jangada-mapear` | inventário da configuração atual da máquina (Hyprland, Noctalia, terminal, agentes), sem alterar nada |

## Atalhos principais

| Atalho | Ação |
|---|---|
| `SUPER + Enter` | terminal |
| `SUPER + Espaço` | lançador de aplicativos |
| `SUPER + A` | novo agente |
| `SUPER + SHIFT + A` | lista de agentes |
| `SUPER + CTRL + A` | painel de agentes (workspace especial) |
| `SUPER + N` | próximo agente que espera resposta; repetir percorre a fila |
| `SUPER + SHIFT + N` | volta ao agente focado antes do atual |
| `SUPER + Esc` | menu jangada |
| `SUPER + CTRL + R` | recarregar e mostrar erros de configuração |
| `SUPER + /` | mostra todos os atalhos ativos, pesquisáveis |

A lista completa aparece no `SUPER + /`, que lê os atalhos do próprio Hyprland
e por isso inclui também os que você definiu em
`~/.config/jangada/hypr/usuario.lua`. Os padrões estão em
`default/hypr/atalhos.lua`.

## Worktrees dos agentes

O `jangada-agente` cria cada worktree a partir do último
commit, então arquivos fora do git (`.Renviron`, `.env`, dados locais) ficam
para trás. Ao criar um worktree novo, o `jangada-worktree-preparar` lê três
arquivos opcionais na raiz do projeto:

| Arquivo | Efeito |
|---|---|
| `.worktreeinclude` | padrões no formato do `.gitignore`; o que casar e for ignorado pelo git é copiado (mesmo formato do `--worktree` do Claude Code) |
| `.jangada/links` | um caminho por linha; vira link simbólico para a pasta da raiz, sem cópia |
| `.jangada/preparar.sh` | roda dentro do worktree por último, com `JANGADA_RAIZ` e `JANGADA_WORKTREE` no ambiente |

A cópia usa `--reflink=auto`: em btrfs, na mesma partição, não ocupa espaço.
Fora disso, uma cópia maior que `JANGADA_WORKTREE_COPIA_MAX` megabytes (padrão
500) é recusada com aviso. Um link só é mantido se o git do worktree o ignorar;
para pastas, escreva `/dados` no `.gitignore`, sem a barra final, porque o
padrão `dados/` não cobre um link. Um worktree reaproveitado não é preparado de
novo.

## Skills do Claude Code e do agy

A etapa de agentes liga cada pasta de `default/claude/skills` em
`~/.claude/skills/<nome>` e, se o agy estiver instalado, em
`~/.gemini/config/skills/<nome>`. Os dois agentes carregam a skill quando a
tarefa combina com a descrição dela, mesmo abertos em outro projeto:

- `jangada`: regras do projeto e pegadinhas já resolvidas (`hyprctl dispatch`
  só com Lua, hypridle que ignora `-c`, on-click da waybar com `setsid -f`,
  agy sem terminal).
- `relatorio-tecnico`: investigação, postmortem, RFC, ADR e relatório formal
  (NBR 10719), com a estrutura de cada tipo e o checklist de entrega.
- `relatorio-academico`: artigo, monografia e tese, com o que levantar antes
  de redigir, `[FALTA: ...]` no lugar de dado ou citação sem origem e o
  checklist de entrega.

O agy lê o mesmo `SKILL.md`, sem ajuste no frontmatter. Uma pasta ou link
alheio com o mesmo nome nas duas pastas fica como está, com aviso.

## Ciclo de uma tarefa com agentes

O fluxo completo, com fluxogramas, está em
[docs/ciclo-da-tarefa.md](docs/ciclo-da-tarefa.md).

1. `SUPER + A` (ou `jangada-agente --prompt "..."`) pergunta o agente e abre
   num worktree `agente/<nome>`. Cada opção diz entre parênteses quem
   implementa, quem revisa e qual economiza mais tokens do Claude.
2. O estado aparece na barra e no painel (`SUPER + CTRL + A`) pelos hooks do
   Claude Code: trabalhando, aguardando (notificação com botão que foca a
   janela) ou concluído. `SUPER + N` pula para quem espera.
3. Antes de entregar, o agente roda `jangada-validar` e o outro modelo revisa
   o diff (veja abaixo). O último parecer aparece na prévia do seletor.
4. Para fechar: `jangada-agente-fim --integrar SESSAO` (ou `Alt+I` no seletor)
   faz o merge na base, remove o worktree e apaga o ramo. `Ctrl+X` encerra sem
   integrar e mantém o ramo.
5. Depois de reiniciar, as sessões que ficaram sem tmux aparecem como
   interrompidas: `Enter` no seletor ou `jangada-agentes --restaurar` reabre
   cada uma na mesma pasta e na mesma conversa (`claude --resume`). Sem o id
   da conversa, o worktree usa `--continue`; direto no repositório abre uma
   conversa nova, porque a mais recente da pasta pode ser de outro agente. O
   comando é recomposto de campos conferidos (agente, pasta, perfil, conversa
   e revisor) e da configuração atual, nunca copiado do estado, que o agente
   isolado consegue gravar.

### Quem implementa e quem revisa

| No seletor | Implementa | Revisa | Tokens do Claude |
|---|---|---|---|
| `claude` | Claude | agy | gasta mais: o Claude faz o trabalho todo |
| `agy` | agy | Claude, só o diff | economiza mais: o Claude só lê o diff |
| `claude-claude` | Claude | Claude | usa apenas o Claude |
| `agy-agy` | agy | agy | não gasta tokens do Claude |

1. O agente abre interativo, no worktree, com o protocolo de
   `default/agentes/protocolo.md` (trabalhar só no worktree, commits sem
   `Co-Authored-By`, validar antes de entregar, regras de escrita). Num
   projeto com arquivos R até dois níveis abaixo da raiz, vão também as
   regras de `default/agentes/protocolo-r.md` (sem `cat()` como mensagem,
   sem código comentado, `seq_along()`). No Claude ele vai por
   `--append-system-prompt`; no agy, por `-i` junto com a tarefa.
   `JANGADA_AGENTE_PROTOCOLO=0` desliga. Sem o revisor instalado, o agente abre
   sem o protocolo, porque não haveria quem revisasse.
2. Antes de entregar, o agente roda `jangada-validar`. O revisor recebe o diff
   desde a base, lê o que precisar, sem alterar nada, e responde. Com
   `REVISAR`, o agente confere cada apontamento, corrige o que proceder e roda
   de novo com `--resposta`, até 3 rodadas (`JANGADA_VALIDAR_RODADAS`) por
   entrega. Depois de um `APROVADO`, a próxima chamada revisa só o que veio
   depois do commit aprovado e recomeça a contagem.
   `--revisor` escolhe o revisor à mão. O Claude revisa com o Sonnet
   (`JANGADA_VALIDAR_MODELO`), só com Read, Grep e Glob; o agy revisa com o
   agente `revisor` (`default/agy/agents/revisor`), só com ferramentas de
   leitura e em `--sandbox`. Sem esse agente no agy, a validação para.
   Antes do revisor, uma verificação local procura conflitos do git, reprova
   script com byte nulo (o revisor o receberia como binário), confere
   a sintaxe de shell e Lua e roda o `lintr` nos arquivos R, só nas linhas
   que o agente alterou (`cat()` e `print()` fora de métodos `print`, código
   comentado, `1:length()`, variável sem uso dentro de função). Do
   `object_usage_linter` só vale a variável sem uso; o aviso de variável
   global, que dispara em toda coluna do dplyr, é descartado. Com `.lintr` na base do projeto, um
   achado reprova sem chamar o revisor; sem ele, vale `default/r/lintr` e o
   achado só aparece como aviso. Sem R ou sem o pacote `lintr`, a etapa é
   pulada. O `gitleaks` procura segredos nas linhas acrescentadas; um achado
   reprova sem mostrar o segredo no parecer, e `gitleaks:allow` num comentário
   da linha libera um falso positivo. Sem o `gitleaks`, ou com ele falhando,
   a entrega reprova; `JANGADA_VALIDAR_SEM_GITLEAKS=1` aceita o risco e só
   avisa. O `.gitleaks.toml` e o `.gitleaksignore` valem como estão na base,
   e não como a entrega os deixou; o `.lintr` também, e um que só a entrega
   traz não é lido. O R roda sem o `.Rprofile` e o `.Renviron` do worktree:
   os três são código do repositório avaliado, e o `jangada-validar` também
   roda fora do isolamento. O `AGENTS.md` e o `CLAUDE.md` vão ao revisor lidos da base,
   e uma entrega que muda o `.jangada/validar.sh` pede ao revisor que confira
   se a validação ficou mais fraca. Commit com `Co-Authored-By` gera aviso.
   Na escrita, o revisor aponta só casos objetivos nas linhas novas: código
   comentado, comentário que narra a mudança, repete o código ou fala com o
   revisor, enchimento ("vale ressaltar", "basicamente"), documentação que
   contradiz o código, arquivo de resumo que ninguém pediu e corpo de commit
   que repete o diff em vez de dar o porquê.
3. Os pareceres ficam em `~/.local/state/jangada/agentes/validacao-*`. O
   jangada-validar roda no processo do agente, que pode gravar nessa pasta;
   por isso a prévia do `jangada-agentes` avisa que o parecer foi gravado pela
   própria sessão, e não serve de prova de revisão. No
   jangada shell, `revisar` roda o mesmo comando no diretório atual. Cada
   rodada acrescenta uma linha a `~/.local/state/jangada/validar.jsonl`
   (resultado, etapa, revisor, rodada, linhas alteradas, apontamentos e
   segundos), e `jangada-validar --metricas` resume por projeto e revisor:
   quantas rodadas uma entrega leva até o `APROVADO` e quanto cada revisor
   aprova.
4. Cada mudança de estado de uma sessão (início, trabalhando, aguardando,
   concluído, fim e cada foco pelo jangada) vira uma linha em
   `~/.local/state/jangada/eventos-agentes.jsonl`. É o histórico de onde saem
   o tempo em espera e as sessões simultâneas; `docs/registros.md` descreve
   este e os outros registros.
5. A barra acompanha o agy pelo hook `jangada-hook-agy`, instalado em
   `~/.gemini/config/hooks.json`: trabalhando e concluído. O agy não tem
   evento de pedido de permissão, então não há "aguardando". `Enter` restaura
   com `agy --conversation`.
6. Em cada worktree novo o agy pergunta se confia na pasta; responda na
   janela. A confiança é por caminho exato. O `jangada-worktree-preparar`
   confia no worktree que cria só se você já confiou no repositório
   principal, e o fim da sessão tira; a primeira alteração guarda o original
   em `settings.json.jangada-orig`.

Detalhes que valem para o dia a dia:

- O `--integrar` recusa mesclar se o repositório principal tiver alterações
  sem commit.
- Os arquivos de estado são alterados sob uma trava (`flock` na própria pasta
  `~/.local/state/jangada/agentes`, aberta só para leitura), porque os hooks
  do Claude Code rodam em paralelo. Um arquivo de trava aberto para escrita
  seguiria um link posto pelo agente e truncaria o alvo fora do isolamento.
- O `jangada-agente` sem terminal exige `--nome`, `--prompt` ou `--direto`.

Perfis de agente (outra conta, outro modelo, outro programa) ficam em
`~/.config/jangada/agentes/NOME.conf`; veja `default/agentes/exemplo.conf`.
A chave `DESCRICAO=` é o texto entre parênteses no seletor.
Ganchos do usuário ficam em `~/.config/jangada/ganchos/EVENTO` ou
`EVENTO.d/`, para os eventos `pos-update`, `pos-tema`, `pos-agente-fim`
(recebe sessão, raiz e se houve integração) e `pos-validar` (sessão e status). Um exemplo útil: `pos-tema` rodando `jangada-sddm aplicar`.

### Subagentes

Fluxogramas em
[docs/subagentes-e-delegacao.md](docs/subagentes-e-delegacao.md).

Oito papéis, com o mesmo nome e o mesmo texto no Claude Code
(`default/claude/agents/`, ligados em `~/.claude/agents/`) e no agy
(`default/agy/agents/`, registrados em `~/.gemini/config/agents.json`). Nenhum
edita arquivos, e todos citam caminho e linha, página, célula ou URL em cada
afirmação. O explorador, o pesquisador, o auditor, o arquiteto, o otimizador e o
redator não têm terminal; o leitor e o verificador têm, e o "só leitura" deles
vale pela instrução e, no agy, pelo `permissions.allow`.

| Papel | Faz | Claude | agy |
|---|---|---|---|
| `explorador` | mapeia código, dados e registros; até ~300 palavras | haiku | flash (low) |
| `leitor` | trechos pedidos de PDF, planilha ou relatório | haiku | flash (medium) |
| `pesquisador` | documentação, normas e dados públicos na web | haiku | flash (medium) |
| `verificador` | testes, lint e regras do AGENTS.md antes do `jangada-validar` | sonnet | flash (high) |
| `auditor` | auditoria de segurança (injeções, caminhos, permissões, CWEs) | sonnet | flash (high) |
| `arquiteto` | estrutura de módulos, contratos de API e impacto de mudanças | sonnet | flash (high) |
| `otimizador` | gargalos de desempenho, complexidade e uso de memória | sonnet | flash (medium) |
| `redator` | conformidade textual, clareza e regras de escrita do AGENTS.md | haiku | flash (low) |

O item 8 do protocolo diz a quem delegar, conforme `JANGADA_DELEGAR` do
perfil (ou global), e o seletor mostra o destino:

| `JANGADA_DELEGAR` | Perfis | Efeito |
|---|---|---|
| `agy` | `claude` (padrão do Claude) | `jangada-delegar PAPEL` manda ao agy Flash; o subagente do Claude só se ele recusar |
| `claude` | `claude-claude` | subagentes do Claude dos papéis, nunca `general-purpose` |
| `nativo` | `agy`, `agy-agy` (padrão do agy) | subagentes do próprio agy (`invoke_subagent`) |

`jangada-delegar PAPEL "pedido" [--arquivo SAIDA]` roda o agente do papel
no agy (Flash low no explorador e no redator, medium no leitor, no pesquisador e
no otimizador, high no verificador, no auditor e no arquiteto), com `--sandbox`,
na raiz do repositório atual, e imprime só o relatório. A pasta precisa ser confiável para o agy (o worktree da sessão
é, e as outras só se você já respondeu à pergunta do agy nelas): o
`jangada-delegar` não confia por conta própria, porque a confiança libera
agentes, regras e MCP da própria pasta. Acima de 600 palavras
(`JANGADA_DELEGAR_PALAVRAS`), o relatório sai cortado, com o caminho do
texto completo. Antes, lê a cota do agy
(`agy -p /usage`, guardada por 5 minutos) e recusa, com código 4 e uma
linha indicando o subagente do Claude do mesmo papel, quando o limite de 5
horas do Gemini está abaixo de 20% (`JANGADA_DELEGAR_COTA_MIN`), quando a
pasta não é confiável, quando o `agy agents` não lista o papel, quando o
agy falha ou passa de 300 segundos (`JANGADA_DELEGAR_TEMPO`) e quando o
perfil não delega ao agy. Sem terminal, o agy só roda os comandos listados
em `permissions.allow` de `~/.gemini/antigravity-cli/settings.json`; os
outros ele nega, e o `jangada-delegar` mostra quais. Cada chamada,
atendida ou recusada, vira uma linha de `delegacoes.jsonl`, com tempo,
tamanho do retorno, passos do agy e a cota antes e depois.

`jangada-subagentes --entrega PASTA` resume os subagentes do Claude, os do
agy e as delegações que rodaram na pasta: quantos, tokens, tamanho do
retorno, edições e autorrevisões. O `jangada-validar` grava esse resumo no
campo `subagentes` do `validar.jsonl`; se a leitura falhar, grava o motivo
em `subagentes_erro` e avisa. Os registros estão em `docs/registros.md`.

`jangada-subagentes [--json]` calcula os indicadores: tokens do Claude por
entrega aprovada com e sem agy (por tamanho do diff), fração ao agy e
recusas, compressão, cota gasta, aprovação na primeira rodada com e sem
verificador, afirmações sem fonte, desvios do protocolo e a árvore de
subagentes. A aba Subagentes do painel mostra os mesmos números; um `*`
marca grupo com menos de 15 entregas.

Regras de decisão:

- Depois de 30 entregas com delegação ao agy, se os tokens do Claude por
  entrega aprovada não caírem, sai a preferência pelo agy no protocolo.
- Se a aprovação na primeira rodada cair nas entregas com delegação, os
  papéis são revistos.
- Se o verificador não subir a aprovação na primeira rodada em 30
  entregas, ele sai.

Sem o agy instalado, `agy` vira `claude`. Subagente não revisa a entrega: o
`verificador` confere regras e testes, não o mérito, e o `jangada-validar`
continua com o revisor de sempre.

### Isolamento

Fluxogramas e a tabela das camadas em
[docs/isolamento.md](docs/isolamento.md).

O agente roda no bubblewrap, pelo `jangada-isolar`. Ele grava só na pasta da
tarefa (o worktree, ou o repositório com `--direto`), em `~/.claude`, em
`~/.gemini/antigravity-cli`, em `~/.local/state/jangada/agentes`, no
`validar.jsonl`, no `eventos-agentes.jsonl` e no `delegacoes.jsonl`. O resto
do sistema e da pasta pessoal fica somente leitura, inclusive `~/.claude.json`
(perdê-lo só perde contadores), `~/.local/share/claude` (o Claude não se
atualiza de dentro), os hooks do agy em `~/.gemini/config` e o resto do estado
do jangada (barra, migrações), que alimenta código que roda fora.

O que o git, o Claude ou o agy leem como configuração, e que valeria fora do
isolamento, fica somente leitura mesmo dentro dos graváveis:

- Git, num worktree: o `.git` comum inteiro, menos `objects`, `refs`, `logs`
  e a pasta do próprio worktree em `worktrees/`, cujos `commondir` e `gitdir`
  também ficam somente leitura. Commit, ramo novo, `checkout -b`, `reset` e
  `stash` funcionam; apagar ramo ou tag e `git gc` falham, porque regravam o
  `packed-refs` na raiz do `.git`.
- Git, com `--direto`: a raiz do `.git` segue gravável (o `HEAD` e o `index`
  ficam nela), menos `config`, `hooks`, `worktrees`, `modules` e `commondir`.
  Como um bind sobre arquivo ausente criaria um arquivo vazio, o
  `jangada-isolar` cria antes um `commondir` com `.` (o próprio `.git`), que o
  git trata como se não existisse. O arquivo `.git` do worktree também é
  somente leitura.
- Claude: `settings.json`, `settings.local.json`, `CLAUDE.md`, `commands`,
  `agents`, `skills`, `hooks`, `plugins`, `output-styles`, `backups` e os
  scripts soltos em `~/.claude`. Os ausentes são criados vazios (`{}` nos
  JSON). Mudar configuração de dentro (`/model`, `/config`) não persiste.
- agy: os executáveis em `~/.gemini/antigravity-cli/bin`.

O `~/.cache`, os retratos do shell (`~/.claude/shell-snapshots`), o ambiente
das sessões (`~/.claude/session-env`) e `~/.claude/ide` aparecem com o
conteúdo de fora, mas o que o agente grava neles fica numa camada em memória
que some no fim: o `~/.cache` guarda os clones do AUR que o `yay` compila com
sudo, e os retratos são carregados antes de cada comando de toda sessão do
Claude, inclusive das abertas fora. Os clones do yay e do paru ficam, além
disso, somente leitura.

O `/tmp` e o `XDG_RUNTIME_DIR` são próprios da sessão e somem no fim; com
eles ficam de fora os sockets do tmux, do Hyprland, do Wayland, do gpg-agent
e do systemd do usuário, e `TMUX`, `TMUX_PANE`, `SSH_AUTH_SOCK`,
`HYPRLAND_INSTANCE_SIGNATURE`, `WAYLAND_DISPLAY` e `DISPLAY` saem do
ambiente. Colar imagem no Claude isolado não funciona. O D-Bus da sessão
passa pelo `xdg-dbus-proxy`, que só deixa falar com `org.freedesktop.secrets`
(o agy lê o login do chaveiro) e `org.freedesktop.Notifications` (os avisos
dos hooks); sem o proxy, o agente fica sem D-Bus. O D-Bus do sistema e os
sockets do Docker, do containerd, do podman e do tailscale ficam ocultos, e o
agente tem namespace de PID próprio: não vê nem mata os processos de fora. A
notificação de uma sessão isolada vem sem o botão Abrir. Ficam ocultos
`~/.ssh`, `~/.gnupg`, `~/.password-store`, `~/.aws`, `~/.azure`, `~/.kube`,
`~/.docker`, `~/.netrc`, `~/.git-credentials`, `~/.config/gh`,
`~/.config/rclone`, os perfis do Chromium, do Chrome e do Firefox,
`~/.local/share/keyrings` e o histórico da área de transferência
(`~/.cache/cliphist`, que guarda as 100 últimas cópias, senhas inclusive);
por isso o `git push` fica com o usuário, fora da sessão. Dentro dela,
`JANGADA_ISOLADO=1`, e um `jangada-isolar` chamado ali roda o comando direto,
sem aninhar. A variável sozinha não basta: vale só com a marca
`/tmp/.jangada-isolado` montada pelo bwrap, que um processo de fora cria
como arquivo mas não como ponto de montagem. A função `revisar` do jangada shell e o
`.jangada/preparar.sh` do worktree também rodam isolados.

Limites conhecidos: o agente lê todo o chaveiro pelo D-Bus; as conversas e a
memória de outros projetos em `~/.claude/projects` e o `settings.json` do agy
(permissões e pastas confiáveis) seguem graváveis; e um repositório aninhado
criado no worktree e registrado no índice leva sua própria configuração, que
um `git status` de fora carregaria. Por isso os scripts do jangada rodam o
git sobre pastas de agentes com `jangada_git_seguro`.

`JANGADA_ISOLAR_ESCRITA` no `jangada.conf` acrescenta pastas graváveis,
separadas por `:` (`~/dados:~/R`). `JANGADA_ISOLAR_OCULTAR` substitui a lista
de ocultos, com caminhos relativos à pasta pessoal ou absolutos; definida
vazia, não oculta nada. Para desligar: `jangada-agente --sem-isolar` numa
sessão, `JANGADA_AGENTE_ISOLAR=0` num perfil ou no `jangada.conf` para todas.
O estado guarda o comando e o campo `isolar` só para consulta: a restauração
ignora os dois e volta sempre isolada, a menos que `JANGADA_AGENTE_ISOLAR=0`
esteja no `jangada.conf` ou no ambiente. Uma sessão aberta com `--sem-isolar`
ou com um perfil que desliga o isolamento volta, portanto, isolada. Sem o
pacote `bubblewrap`, o `jangada-isolar` recusa e o agente não abre; a
mensagem fica no terminal da sessão e indica o `--sem-isolar` ou o
`JANGADA_AGENTE_ISOLAR=0`.

## Painel de indicadores

O funcionamento de cada peça está em [docs/painel.md](docs/painel.md).

O `jangada-painel` junta os registros dos agentes num cache e abre um app
Shiny em `127.0.0.1:8765` (`JANGADA_PAINEL_PORTA`). O app só existe enquanto
está aberto: `jangada-painel --parar` libera a memória do R. Precisa de R com
shiny, bslib, bsicons, plotly, visNetwork, igraph, DT, arrow, jsonlite e
htmltools, e do `python-pyarrow`; a instalação só avisa o que falta. O app só abre sessão
para `127.0.0.1` ou `localhost` na porta dele: uma página de fora, aberta no
mesmo navegador, não lê os indicadores.

Cada chamada roda o coletor (`default/painel/coletor.py`). Ele lê as
conversas do Claude Code a partir de onde parou, então só a primeira coleta
lê os ~280 MB de `~/.claude/projects`. O cache fica em
`~/.local/state/jangada/painel`, em Parquet, e guarda o que o Claude Code já
apagou (ele apaga conversas com mais de 30 dias). O mapa de cada registro,
com campos e lacunas, está em `docs/registros.md`.

Definições:

- **Entrega**: as rodadas do `jangada-validar` num mesmo rótulo até um
  APROVADO. Antes do `validar.jsonl` (26/09/2026) as rodadas vêm dos
  pareceres guardados em `agentes/`.
- **Aprovação na 1ª rodada**: entregas aprovadas sem nenhum REVISAR antes,
  sobre as entregas aprovadas.
- **No limite**: entregas que chegaram a `JANGADA_VALIDAR_RODADAS` sem
  aprovação. Indica tarefa ambígua ou modelos em desacordo.
- **Tokens**: só do Claude Code; o agy não grava contagem legível. Saída,
  raciocínio (parte da saída) e cache criado aparecem separados; o cache lido
  é barato e fica num gráfico à parte. Cada resposta conta uma vez.
- **Bloco de 5 horas**: a regra do `jangada-consumo`. Os registros não trazem
  o limite do plano; "perto do limite" é um bloco com 80% ou mais da saída do
  maior bloco observado.
- **Tokens por entrega**: as respostas da sessão da entrega entre o fim da
  entrega anterior do mesmo rótulo (ou 24 horas antes da 1ª rodada) e a
  aprovação.
- **Tempo em aguardando** e **sessões simultâneas**: saem do
  `eventos-agentes.jsonl`, que começou em 26/09/2026. O agy não tem estado
  aguardando.

- **Ciclo de retrabalho**: editar um arquivo (Edit ou Write), os testes
  falharem e editar o mesmo arquivo de novo, na mesma conversa. Um teste que
  passa zera a conta. Edição por comando (sed, python) não entra, porque o
  registro não diz o arquivo.
- **Pontos quentes**: arquivos editados em mais de uma sessão, com o número
  de itens REVISAR que os citam. O `validar.jsonl` não guarda os arquivos da
  entrega; eles saem dos itens dos pareceres.
- **Espaço de ferramentas** (exploratório): como o Product Space. Um projeto
  tem vantagem numa capacidade (ferramenta, skill, subagente, servidor MCP ou
  tipo de comando) quando a usa mais que a média; duas capacidades são
  próximas quando os mesmos projetos têm vantagem nas duas. O grafo mostra a
  árvore geradora máxima e as arestas acima do limiar.

As redes cobrem só o Claude Code e mostram no máximo 40 nós por padrão; o
painel tem controles para afrouxar a poda.

Cada gráfico mostra o período e o número de observações coberto, com o aviso
"pouco dado" abaixo de 10.

Na barra, o módulo `custom/indicadores` fica ao lado do de agentes. O clique
atualiza o cache e abre o painel; o botão direito encerra o app. A dica
mostra os indicadores do dia. O módulo só lê o cache e é avisado pelo sinal
9 (`pkill -RTMIN+9 -x waybar`), que fica reservado a ele.

## Várias máquinas

O repositório é o mesmo em todas as máquinas; o que muda de uma para outra
fica só em `~/.config/jangada`. Nenhum arquivo de `default/` cita monitor,
placa de vídeo, usuário ou caminho de uma máquina específica.

| O que muda por máquina | Onde fica |
|---|---|
| Posição, escala e modo dos monitores | `~/.config/jangada/hypr/monitores.lua` |
| Teclado, atalhos e programas pessoais | `~/.config/jangada/hypr/usuario.lua` |
| Fonte da barra por monitor | `~/.config/jangada/waybar/style.css` (`window#waybar.NOME`) |
| Terminal, interface, GPU forçada, pastas de projetos (`JANGADA_PROJETOS`, `JANGADA_REPO`) | `~/.config/jangada/jangada.conf` |
| Canal de atualização | `JANGADA_CANAL` no `jangada.conf` |
| Perfis de agente e ganchos | `~/.config/jangada/agentes/`, `~/.config/jangada/ganchos/` |

Roteiro para uma máquina nova:

1. Clonar em `~/.local/share/jangada` a partir do remoto compartilhado (hoje
   o repositório em `~/GoogleDrive/jangada`, o remoto `drive` da cópia de
   trabalho) e rodar `bin/jangada-mapear`.
2. `JANGADA_SIMULAR=1 ./install.sh`, conferir, e `./install.sh`.
3. `jangada-importar` (se a máquina usava niri) e copiar o que servir dos
   arquivos `.importado`. Variáveis de driver de vídeo vêm comentadas.
4. Ajustar `monitores.lua` com os nomes de `hyprctl monitors`.
5. `jangada-verificar` e entrar na sessão **jangada**.

A GPU é escolhida sozinha (a placa com monitor ligado), e as conferências de
NVIDIA do `jangada-update` só rodam quando o módulo `nvidia` está carregado.

### Canal de atualização

`jangada-update` segue o ramo de `JANGADA_CANAL` (padrão `main`). A máquina
onde o jangada é desenvolvido fica em `main`; as outras podem usar
`JANGADA_CANAL=estavel`, que só avança quando a versão foi testada:

```sh
git -C ~/Projetos/jangada branch -f estavel main   # depois de testar
git -C ~/Projetos/jangada push drive estavel
```

O `jangada-update` também tira a cópia instalada de um ramo `agente/...`, se
ela tiver ficado num deles.

### Versões

As versões seguem o formato `v0.x.y`, em tags do git. O `CHANGELOG.md` é
gerado das mensagens de commit pelo `jangada-versao --lancar X.Y.Z`: o que
começa com `feat` entra em Novidades, o que começa com `fix` em Correções e o
resto em Outras mudanças. O `jangada-update` busca a origem, mostra os
commits e as novidades que chegariam, avisa quando mudam `migrations/`,
`install/` ou `bin/` (código que roda na máquina) e só aplica com `s`; sem
terminal para confirmar, não aplica nada. `jangada-versao` mostra a versão
instalada.

## Desenvolvimento

A cópia de trabalho fica em `~/Projetos/jangada` (`JANGADA_REPO`); a cópia
instalada só recebe avanço rápido (`--ff-only`) pelo `jangada-update`, depois
da confirmação. O `jangada-agente-fim --integrar` integra na cópia de trabalho
e não mexe na instalada. Para testar a cópia de trabalho sem instalar, rode
`JANGADA_PATH=$PWD bin/...`.

| Teste | O que confere |
|---|---|
| `testes/verificar.sh` | shellcheck, sintaxe Lua, JSON e TOML, comandos citados na configuração e, em seguida, todos os testes abaixo menos o `aninhado.sh` |
| `testes/diagnostico.sh` | diagnóstico do `jangada-verificar`: do `hyprland.log` só erros e avisos, sem caracteres de controle, marcados como dados |
| `testes/regra1.sh` | todo caminho de fora das pastas do jangada citado no código está nas exceções à regra 1 do `AGENTS.md` ou é só lido |
| `testes/validar.sh` | `jangada-validar` com claude e agy falsos: veredito, rodadas, pareceres e métricas |
| `testes/isolar.sh` | `jangada-isolar`: o que fica gravável, somente leitura e oculto, no worktree e direto no repositório |
| `testes/restaurar.sh` | `jangada-agentes --restaurar` com tmux falso: o comando sai de campos conferidos, nunca do estado |
| `testes/update.sh` | `jangada-update` só aplica com confirmação; `jangada-agente-fim --integrar` não mexe na cópia instalada nem roda ganchos do repositório do agente |
| `testes/eventos.sh` | histórico de estados dos agentes gravado pelos hooks e pela troca de foco |
| `testes/barra.sh` | módulo `custom/indicadores`, barra em pé do `jangada-barra` e a migração que o acrescenta |
| `testes/painel.sh` | coletor do painel sobre registros de exemplo e, com os pacotes R, o app no ar |
| `testes/subagentes.sh`, `testes/delegar.sh` | papéis de subagente e a instalação deles; `jangada-delegar` com agy falso |
| `testes/versao.sh` | `jangada-versao` num repositório temporário: grupos e prefixos das novidades, o `CHANGELOG.md` e a tag do `--lancar` e as recusas (árvore suja, versão menor, tag existente, nada novo) |
| `testes/importar.sh` | `jangada-importar` com um config.kdl de exemplo |
| `testes/fim.sh` | `jangada-agente-fim` recusa estado adulterado (ramo, worktree, raiz, base) sem mexer em nada; `--limpar-concluidos` só age com `s` |
| `testes/mapear.sh` | a máscara de segredos do `jangada-mapear` apaga tokens, chaves e senhas e preserva texto comum |
| `testes/rede.sh` | `jangada-rede` com nmcli falso: a senha do Wi-Fi nunca aparece nos argumentos |
| `testes/bluetooth.sh` | `jangada-bluetooth` com bluetoothctl falso: parear não confia no aparelho sem a escolha no menu |
| `testes/snapshot.sh` | `jangada-snapshot` com snapper falso: os do agente ficam fora da limpeza do snapper e só os mais recentes ficam |
| `testes/calendario.sh` | `jangada-calendario`: JSON corrompido guardado à parte, gravação atômica e gravações simultâneas sem perda |
| `testes/reverter.sh` | `reverter` do jangada shell, no bash e no zsh: prévia do que se perde e ramo de cópia |
| `testes/aninhado.sh` | sobe um Hyprland aninhado com a configuração (`--sem-usuario` só os padrões) e confere `configerrors` e o número de atalhos |

A cada push, o GitHub Actions (`.github/workflows/verificar.yml`) roda o
`testes/verificar.sh` num contêiner Arch e simula a instalação como usuário
sem sudo, conferindo que nada foi escrito. R e `lintr` ficam de fora da CI, e
o caso do `lintr` só roda na máquina local.

Os testes nunca tocam a configuração real: rodam com `XDG_CONFIG_HOME` e
`XDG_STATE_HOME` temporários, e o `jangada-tema` respeita o
`XDG_CONFIG_HOME` também nas saídas do matugen.

Mudança que exige ajuste numa instalação existente ganha uma migração em
`migrations/` (ver `migrations/README.md`). As revisões cruzadas e as
avaliações estão indexadas em `revisao/README.md`; a última auditoria
(`revisao/auditoria-20260927.md`) cobre o repositório inteiro, com 72
apontamentos: os 6 críticos, todos de fuga do isolamento, e os 8 altos foram
corrigidos, assim como os médios e os baixos.

## Estado

Em uso diário no desktop desde 19/09/2026 (Hyprland 0.56, RTX 4060, dois
monitores). Os itens do benchmark de gerenciadores de agentes estão feitos,
com a situação de cada um em `revisao/benchmark-agentes.md` (seção 7). Ainda
não foi instalado numa segunda máquina: a primeira instalação em outra
máquina é o teste que falta para a portabilidade.
