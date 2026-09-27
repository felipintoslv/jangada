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
├── default/               padrões atualizáveis (hypr em Lua, waybar, matugen, tmux, hooks e skills do Claude Code)
├── config/                modelos copiados uma única vez para ~/.config/jangada
├── shell/                 integração com bash e zsh
├── migrations/            ajustes aplicados em ordem a cada atualização
├── testes/                verificar.sh (estático + testes do validar, do isolar, do importar e do versao) e aninhado.sh
├── mapeamento/            inventários do jangada-mapear (fora do git)
└── revisao/               pareceres, avaliações e comparações; índice em revisao/README.md
```

## Antes de instalar: mapear a máquina

Em cada máquina, rode primeiro `bin/jangada-mapear`. Ele registra a configuração atual, inclusive as personalizações do Noctalia, em `mapeamento/` (fora do git). O roteiro de resgate está em `revisao/RESGATE.md`.

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
| `jangada-update` | atualiza o repositório no ramo de `JANGADA_CANAL` e mostra as novidades que chegaram, mostra se o conjunto do Hyprland mudou, atualiza o sistema, aplica migrações, confere initramfs e driver NVIDIA e roda o gancho `pos-update`. Se o pacman ou o AUR falhar, a conferência da imagem de boot roda mesmo assim, e as migrações e a recarga do Hyprland ficam para depois do conserto |
| `jangada-verificar` | confere pacotes, snapshots, sessão, hooks e erros de configuração do Hyprland; `--diagnostico` grava um relatório e `--agente` abre um agente com ele no repositório do jangada |
| `jangada-versao` | mostra a versão da cópia (`0.1.0`, ou `0.1.0-3-gabc1234` com commits depois da tag); `--novidades [DE [ATE]]` lista as mudanças, `--registro` imprime o registro completo e `--lancar X.Y.Z` grava o `CHANGELOG.md`, faz o commit e cria a tag `vX.Y.Z` (sem push); `-C DIR` opera em outro repositório |
| `jangada-migrar` | aplica as migrações pendentes (o `jangada-update` já chama) |
| `jangada-snapshot "descrição"` | cria um snapshot manual do sistema |
| `jangada-tema [imagem]` | gera as cores a partir de um papel de parede e recarrega a interface |
| `jangada-agente` | escolhe o agente (Claude ou agy), o projeto e cria um worktree, e abre o agente numa sessão tmux, isolado pelo `jangada-isolar` (`--prompt`, `--prompt-arquivo`, `--perfil`, `--sem-isolar`) |
| `jangada-isolar` | roda um comando no bubblewrap, com o sistema somente leitura e a pasta atual gravável; `--mostrar` imprime a chamada ao `bwrap` |
| `jangada-validar` | manda o diff do worktree para o outro modelo revisar (o agy revisa o Claude, o Claude revisa o agy) e devolve `STATUS: APROVADO` ou `REVISAR`; o agente chama antes de entregar |
| `jangada-shell` | inicia subshell enriquecida com comandos diretos de agentes e projetos |
| `jangada-agentes` | lista as sessões de agentes, com estado, e permite abrir, integrar ou encerrar (`--proximo`, `--anterior`, `--restaurar`) |
| `jangada-agente-fim` | encerra uma sessão e remove o worktree, com conferência de alterações pendentes; `--integrar` faz antes o merge na base, atualiza a cópia instalada se for o repositório do jangada e apaga o ramo |
| `jangada-consumo` | tokens do Claude Code no bloco de 5 horas em andamento (também no tooltip da barra) |
| `jangada-gancho` | roda os ganchos do usuário de um evento (chamado pelos outros comandos) |
| `jangada-importar` | converte a configuração do niri em arquivos `.importado` |
| `jangada-atalhos` | mostra todos os atalhos ativos, lidos do próprio Hyprland (`--lista` para o terminal) |
| `jangada-sddm aplicar` | deixa o jangada como única sessão no SDDM, com o tema de login do jangada (`restaurar`, `status`, `testar`) |
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

## Skills do Claude Code

A etapa de agentes liga cada pasta de `default/claude/skills` em
`~/.claude/skills/<nome>`, e o Claude Code carrega a skill quando a tarefa
combina com a descrição dela, mesmo aberto em outro projeto:

- `jangada`: regras do projeto e pegadinhas já resolvidas (`hyprctl dispatch`
  só com Lua, hypridle que ignora `-c`, on-click da waybar com `setsid -f`,
  agy sem terminal).
- `relatorio-tecnico`: investigação, postmortem, RFC, ADR e relatório formal
  (NBR 10719), com a estrutura de cada tipo e o checklist de entrega.
- `relatorio-academico`: artigo, monografia e tese, com o que levantar antes
  de redigir, `[FALTA: ...]` no lugar de dado ou citação sem origem e o
  checklist de entrega.

O agy não lê essas skills; para ele, diga na tarefa qual arquivo seguir, por
exemplo "siga `~/.claude/skills/relatorio-tecnico/SKILL.md`".

## Ciclo de uma tarefa com agentes

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
   conversa nova, porque a mais recente da pasta pode ser de outro agente.

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
   (`JANGADA_VALIDAR_MODELO`).
   Antes do revisor, uma verificação local procura conflitos do git, confere
   a sintaxe de shell e Lua e roda o `lintr` nos arquivos R, só nas linhas
   que o agente alterou (`cat()` e `print()` fora de métodos `print`, código
   comentado, `1:length()`; a variável sem uso fica de fora porque o
   lintr confunde as colunas do dplyr com variáveis). Com `.lintr` no projeto, um
   achado reprova sem chamar o revisor; sem ele, vale `default/r/lintr` e o
   achado só aparece como aviso. Sem R ou sem o pacote `lintr`, a etapa é
   pulada. O `gitleaks` procura segredos nas linhas acrescentadas; um achado
   reprova sem mostrar o segredo no parecer, e `gitleaks:allow` num comentário
   da linha libera um falso positivo. Commit com `Co-Authored-By` gera aviso.
   Na escrita, o revisor aponta só casos objetivos nas linhas novas: código
   comentado, comentário que narra a mudança, repete o código ou fala com o
   revisor, enchimento ("vale ressaltar", "basicamente"), documentação que
   contradiz o código, arquivo de resumo que ninguém pediu e corpo de commit
   que repete o diff em vez de dar o porquê.
3. Os pareceres ficam em `~/.local/state/jangada/agentes/validacao-*`. No
   jangada shell, `revisar` roda o mesmo comando no diretório atual. Cada
   rodada acrescenta uma linha a `~/.local/state/jangada/validar.jsonl`
   (resultado, etapa, revisor, rodada, linhas alteradas, apontamentos e
   segundos), e `jangada-validar --metricas` resume por projeto e revisor:
   quantas rodadas uma entrega leva até o `APROVADO` e quanto cada revisor
   aprova.
4. A barra acompanha o agy pelo hook `jangada-hook-agy`, instalado em
   `~/.gemini/config/hooks.json`: trabalhando e concluído. O agy não tem
   evento de pedido de permissão, então não há "aguardando". `Enter` restaura
   com `agy --conversation`.
5. Em cada worktree novo o agy pergunta se confia na pasta; responda na
   janela. A confiança é por caminho exato.

Detalhes que valem para o dia a dia:

- O `--integrar` recusa mesclar se o repositório principal tiver alterações
  sem commit.
- Os arquivos de estado são alterados sob uma trava
  (`~/.local/state/jangada/agentes/.trava`), porque os hooks do Claude Code
  rodam em paralelo.
- O `jangada-agente` sem terminal exige `--nome`, `--prompt` ou `--direto`.

Perfis de agente (outra conta, outro modelo, outro programa) ficam em
`~/.config/jangada/agentes/NOME.conf`; veja `default/agentes/exemplo.conf`.
A chave `DESCRICAO=` é o texto entre parênteses no seletor.
Ganchos do usuário ficam em `~/.config/jangada/ganchos/EVENTO` ou
`EVENTO.d/`, para os eventos `pos-update`, `pos-tema`, `pos-agente-fim`
(recebe sessão, raiz e se houve integração) e `pos-validar` (sessão e status). Um exemplo útil: `pos-tema` rodando `jangada-sddm aplicar`.

### Isolamento

O agente roda no bubblewrap, pelo `jangada-isolar`. Ele grava só na pasta da
tarefa (o worktree, ou o repositório com `--direto`), no `.git` comum do
repositório, em `~/.claude`, em `~/.gemini/antigravity-cli`, em `~/.cache`, em
`~/.local/state/jangada/agentes` e no `validar.jsonl`. O resto do sistema e da
pasta pessoal fica somente leitura, inclusive `~/.claude.json` (perdê-lo só
perde contadores), `~/.local/share/claude` (o Claude não se atualiza de
dentro), os hooks do agy em `~/.gemini/config` e o resto do estado do jangada
(barra, migrações), que alimenta código que roda fora. O `config` e os `hooks`
do git e o arquivo `.git` do worktree ficam somente leitura mesmo dentro do
`.git` comum: por eles o git rodaria, fora do isolamento, código escrito pelo
agente. O `/tmp` é próprio da sessão e some no fim; com ele fica de fora o
socket do tmux, e `TMUX`, `TMUX_PANE` e `SSH_AUTH_SOCK` saem do ambiente: o
agente não comanda as outras sessões nem usa o agente SSH. A notificação de
uma sessão isolada vem sem o botão Abrir. Ficam ocultos `~/.ssh`, `~/.gnupg`,
`~/.password-store`, `~/.aws`, `~/.azure`, `~/.kube`, `~/.docker`, `~/.netrc`,
`~/.git-credentials`, `~/.config/gh`, `~/.config/rclone`, os perfis do
Chromium, do Chrome e do Firefox e `~/.local/share/keyrings`; por isso o
`git push` fica com o usuário, fora da sessão. Dentro dela,
`JANGADA_ISOLADO=1`, e um `jangada-isolar` chamado ali roda o comando direto,
sem aninhar. A função `revisar` do jangada shell e o `.jangada/preparar.sh` do
worktree também rodam isolados.

A proteção é contra o dano acidental: `rm` fora do projeto, edição de
dotfiles, leitura de chaves. Não é fronteira contra agente malicioso: o D-Bus
da sessão fica aberto (o agy tira o login do chaveiro por ele), e por ele um
`systemd-run --user` roda fora do isolamento; o IPC do Hyprland também fica ao
alcance; e `~/.claude`, cujo `settings.json` define hooks, segue gravável.

`JANGADA_ISOLAR_ESCRITA` no `jangada.conf` acrescenta pastas graváveis,
separadas por `:` (`~/dados:~/R`). `JANGADA_ISOLAR_OCULTAR` substitui a lista
de ocultos, com caminhos relativos à pasta pessoal ou absolutos; definida
vazia, não oculta nada. Para desligar: `jangada-agente --sem-isolar` numa
sessão, `JANGADA_AGENTE_ISOLAR=0` num perfil ou no `jangada.conf` para todas.
O prefixo `jangada-isolar` entra no comando guardado, e o estado registra
`isolar`; na restauração, se o prefixo tiver sumido do comando de uma sessão
isolada, o `jangada-agentes` o põe de volta. Sem o pacote `bubblewrap`, o
agente abre sem isolamento e com aviso.

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
resto em Outras mudanças. Depois do `git pull`, o `jangada-update` mostra as
novidades que chegaram. `jangada-versao` mostra a versão instalada.

## Desenvolvimento

A cópia de trabalho fica em `~/Projetos/jangada` (`JANGADA_REPO`); a cópia
instalada só recebe `git pull --ff-only`. Para testar a cópia de trabalho sem
instalar, rode `JANGADA_PATH=$PWD bin/...`.

| Teste | O que confere |
|---|---|
| `testes/verificar.sh` | shellcheck, sintaxe Lua, JSON e TOML, comandos citados na configuração, `jangada-validar` com claude e agy falsos, o `jangada-isolar` (o que fica gravável, somente leitura e oculto), `jangada-importar` com um config.kdl de exemplo |
| `testes/versao.sh` | `jangada-versao` num repositório temporário: grupos e prefixos das novidades, o `CHANGELOG.md` e a tag do `--lancar` e as recusas (árvore suja, versão menor, tag existente, nada novo); também roda dentro do `verificar.sh` |
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
(`revisao/avaliacao-gemini-20260921-fechamento.md`) cobre os commits do
fechamento do benchmark, com 13 dos 15 apontamentos aplicados no todo ou em
parte.

## Estado

Em uso diário no desktop desde 19/09/2026 (Hyprland 0.56, RTX 4060, dois
monitores). Os itens do benchmark de gerenciadores de agentes estão feitos,
com a situação de cada um em `revisao/benchmark-agentes.md` (seção 7). Ainda
não foi instalado numa segunda máquina: a primeira instalação em outra
máquina é o teste que falta para a portabilidade.
