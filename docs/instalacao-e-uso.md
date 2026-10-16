# Instalação e uso em várias máquinas

## Antes de instalar: mapear a máquina

Em cada máquina, rode primeiro `bin/jangada-mapear`. Ele registra a configuração atual, inclusive as personalizações do Noctalia, em `mapeamento/` (fora do git). Chaves, tokens, senhas, blocos de chave privada e senhas em URL são mascarados nas cópias; `bin/jangada-mapear --mascarar <arquivo` aplica a mesma máscara a qualquer texto, para conferir antes de compartilhar. O roteiro de resgate está em `revisao/RESGATE.md`.

Quem vem do niri converte a configuração com `jangada-importar`, que lê `~/.config/niri/config.kdl` (ou uma pasta de mapeamento) e grava, sem sobrescrever nada:

| Arquivo gerado | Conteúdo |
|---|---|
| `~/.config/jangada/hypr/usuario.lua.importado` | teclado, variáveis de ambiente, programas ao iniciar e atalhos; os que batem com um padrão do jangada saem comentados, e as ações sem equivalente (colunas, overview) ficam listadas |
| `~/.config/jangada/hypr/monitores.lua.importado` | nome, modo, posição, escala e rotação de cada tela |
| `~/.config/jangada/jangada.conf.importado` | o terminal do `Mod+Return` |

Compare com `diff -u` e copie o que quiser para os arquivos sem a extensão.

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

### Commits assinados

Com `~/.config/jangada/allowed_signers`, o `jangada-update` só aplica commits
assinados por uma chave desse arquivo. O arquivo fica fora da cópia de
trabalho e é somente leitura para o agente isolado, que também não vê a chave.
Os commits dos agentes chegam sem assinatura. Antes do envio ao remoto,
rode `jangada-assinar` fora do isolamento. Para habilitar a conferência,
num terminal comum:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519   # se ainda não houver chave
echo "$(git config user.email) namespaces=\"git\" $(cat ~/.ssh/id_ed25519.pub)" \
  >~/.config/jangada/allowed_signers
jangada-assinar          # antes do envio ao remoto
```

Outra chave vai em `JANGADA_ASSINATURA_CHAVE` no `jangada.conf`. Nas outras
máquinas, o mesmo `allowed_signers` faz o `jangada-update` recusar o que
chega do remoto sem assinatura.

### Versões

As versões seguem o formato `v0.x.y`, em tags do git. O `CHANGELOG.md` é
gerado das mensagens de commit pelo `jangada-versao --lancar X.Y.Z`: o que
começa com `feat` entra em Novidades, o que começa com `fix` em Correções e o
resto em Outras mudanças. O `jangada-update` busca a origem, mostra os
commits e as novidades que chegariam, avisa quando mudam `migrations/`,
`install/` ou `bin/` (código que roda na máquina) e só aplica com `s`; sem
terminal para confirmar, não aplica nada. O aviso ainda não cobre `core/`,
`shell/` e `monitor/`, onde os comandos moram desde a modularização 3.0;
a mudança neles aparece só no resumo por arquivo (pendência registrada em
[06-validacao-final.md](modularizacao-3.0/06-validacao-final.md)). `jangada-versao` mostra a versão
instalada.
