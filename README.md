# jangada

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
├── default/               padrões atualizáveis (hypr em Lua, waybar, matugen, tmux, hooks)
├── config/                modelos copiados uma única vez para ~/.config/jangada
├── shell/                 integração com bash e zsh
├── migrations/            ajustes aplicados em ordem a cada atualização
├── testes/                verificações estáticas (shellcheck, sintaxe Lua, JSON, TOML)
└── revisao/               instruções e resultados das revisões cruzadas
```

## Antes de instalar: mapear a máquina

No desktop, rode primeiro `bin/jangada-mapear`. Ele registra a configuração atual, inclusive as personalizações do Noctalia, em `mapeamento/` (fora do git). O roteiro de resgate está em `revisao/RESGATE.md`.

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

## Tela de login (SDDM)

`jangada-sddm aplicar` instala o tema `jangada` em `/usr/share/sddm/themes/jangada` e faz o SDDM ler as sessões de `/usr/local/share/jangada/sessoes`, que só contém o jangada. Os arquivos de sessão dos outros pacotes (Hyprland, niri, Plasma) não são movidos nem apagados; `jangada-sddm restaurar` remove `/etc/sddm.conf.d/zz-jangada.conf` e todas voltam a aparecer. O prefixo `zz-` faz o arquivo ser lido depois do `kde_settings.conf`, que de outro modo imporia o tema escolhido no Plasma.

O tema imita o menu do `SUPER + Esc`: caixa centralizada com as mesmas medidas do fuzzel, linhas `usuário >` e `senha >` e a lista **Entrar**, **Suspender**, **Reiniciar** e **Desligar**. Setas escolhem a ação e Enter executa; digitar a senha volta a seleção para Entrar. As cores vêm do `fuzzel.ini` gerado pelo `jangada-tema` e o fundo é o papel de parede atual, copiados no momento do `aplicar`. Depois de trocar o papel de parede, rode `jangada-sddm aplicar` de novo. `jangada-sddm testar` abre o tema numa janela, sem alterar o sistema.

A instalação pergunta se deve aplicar a exclusividade; a resposta padrão é não.

## Comandos

| Comando | Função |
|---|---|
| `jangada-update` | atualiza o repositório, mostra se o conjunto do Hyprland mudou, atualiza o sistema e aplica migrações |
| `jangada-verificar` | confere pacotes, snapshots, sessão e erros de configuração do Hyprland |
| `jangada-snapshot "descrição"` | cria um snapshot manual do sistema |
| `jangada-tema [imagem]` | gera as cores a partir de um papel de parede e recarrega a interface |
| `jangada-agente` | escolhe um projeto, cria um worktree e abre um agente numa sessão tmux |
| `jangada-par` | executa tarefa em par (Claude implementa, Antigravity revisa e Claude corrige) |
| `jangada-shell` | inicia subshell enriquecida com comandos diretos de agentes e projetos |
| `jangada-agentes` | lista as sessões de agentes, com estado, e permite abrir ou encerrar |
| `jangada-agente-fim` | encerra uma sessão e remove o worktree, com conferência de alterações pendentes |
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
| `SUPER + P` | tarefa em par (Claude + Antigravity) |
| `SUPER + SHIFT + A` | lista de agentes |
| `SUPER + CTRL + A` | painel de agentes (workspace especial) |
| `SUPER + Esc` | menu jangada |
| `SUPER + CTRL + R` | recarregar e mostrar erros de configuração |
| `SUPER + /` | mostra todos os atalhos ativos, pesquisáveis |

A lista completa aparece no `SUPER + /`, que lê os atalhos do próprio Hyprland
e por isso inclui também os que você definiu em
`~/.config/jangada/hypr/usuario.lua`. Os padrões estão em
`default/hypr/atalhos.lua`.

## Estado

Versão inicial, ainda não testada numa máquina real. Veja `revisao/` para as revisões feitas.
