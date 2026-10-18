# Instalação e uso

O Shell é a camada Arch + Hyprland + waybar do jangada: sessão, barra, temas,
menus, atalhos e a Central de Tarefas. Mora em `~/.local/share/jangada`
(`JANGADA_PATH`). Os comandos de sessões de agentes, isolamento, revisão e
indicadores pertencem ao Core, que é outro repositório e se instala à parte.

## Antes de instalar: mapear a máquina

Rode primeiro `bin/jangada-mapear`. Ele registra a configuração atual em
`mapeamento/` (fora do git), com chaves, tokens e senhas mascarados.
Quem vem do niri converte a configuração com `jangada-importar`, que grava,
sem sobrescrever nada, arquivos `.importado` em `~/.config/jangada`
(`hypr/usuario.lua.importado`, `hypr/monitores.lua.importado` e
`jangada.conf.importado`). Compare com `diff -u` e copie o que servir.

## Instalação

```sh
git clone <url> ~/.local/share/jangada
cd ~/.local/share/jangada
JANGADA_SIMULAR=1 ./install.sh   # confere o que será feito
./install.sh                     # aplica
```

O `install.sh` recusa rodar da cópia de trabalho (`JANGADA_REPO`), de um
worktree ou de `JANGADA_WORKTREES`: essas pastas são graváveis de dentro do
isolamento. Nelas só a simulação roda. Depois, encerre a sessão atual e
escolha **jangada** no gerenciador de login.

## Relação com o Core

O jangada tem dois repositórios: o Shell (este) e o Core
(`felipintoslv/jangada-core`). O Shell chama os comandos do Core só pelo
nome, via `PATH`, e tolera a ausência dele: sem o Core, a barra e a Central
seguem de pé, sem dados de sessões. Os indicadores de consumo e revisão ficam
na aba Indicadores da Central, com dados do `jangada-indicadores` do Core. O
`jangada-monitor` é outra coisa: abre o btop ou o htop do sistema e pertence
ao Shell. Para a Central de Tarefas achar o Core fora do `PATH`, a
raiz vem de `JANGADA_CORE_PATH` no ambiente ou, se ela estiver vazia, da linha
`JANGADA_CORE_PATH=` que o `jangada-config` do Core imprime. Nenhuma pasta
vizinha é presumida.

## Máquinas com duas GPUs

O `jangada-sessao` define `AQ_DRM_DEVICES` antes de o compositor subir,
escolhendo a placa que tem monitor ligado. Para forçar outra, preencha
`JANGADA_GPU` no `jangada.conf` com um caminho de `/dev/dri/by-path`; ele é
resolvido para o `/dev/dri/cardN` correspondente, porque o `:` do endereço
PCI quebraria a lista do aquamarine. Com placa NVIDIA, a sessão define
também `LIBVA_DRIVER_NAME`, `__GLX_VENDOR_LIBRARY_NAME` e `NVD_BACKEND`;
`GBM_BACKEND` fica de fora de propósito. O `jangada-verificar` mostra a placa
escolhida e avisa se ela não tiver monitor ligado.

## Várias máquinas

O repositório é o mesmo em todas; o que muda fica em `~/.config/jangada`.

| O que muda por máquina | Onde fica |
|---|---|
| Posição, escala e modo dos monitores | `hypr/monitores.lua` |
| Teclado, atalhos e programas pessoais | `hypr/usuario.lua` |
| Fonte da barra por monitor | `waybar/style.css` (`window#waybar.NOME`) |
| Terminal, interface, GPU, pastas de projetos, canal | `jangada.conf` |

Roteiro para uma máquina nova: clonar e rodar `bin/jangada-mapear`;
`JANGADA_SIMULAR=1 ./install.sh`, conferir e `./install.sh`; `jangada-importar`
se a máquina usava niri; ajustar `monitores.lua` com os nomes de
`hyprctl monitors`; `jangada-verificar` e entrar na sessão **jangada**.

### Canal de atualização

O `jangada-sistema-update` segue o ramo de `JANGADA_CANAL` (padrão `main`).
Máquinas que só consomem podem usar `JANGADA_CANAL=estavel`, ramo que avança
quando a versão foi testada.

### Commits assinados

Com `~/.config/jangada/allowed_signers`, o `jangada-sistema-update` só aplica
commits assinados por uma chave desse arquivo. O arquivo fica fora da cópia de
trabalho. Para habilitar, num terminal comum:

```sh
ssh-keygen -t ed25519 -f ~/.ssh/id_ed25519   # se ainda não houver chave
echo "$(git config user.email) namespaces=\"git\" $(cat ~/.ssh/id_ed25519.pub)" \
  >~/.config/jangada/allowed_signers
```

Quem assina os commits dos agentes é o `jangada-assinar`, comando do Core.
