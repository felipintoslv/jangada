# Pendências e pontos a confirmar no desktop

Registro da revisão feita pelo Claude antes da revisão cruzada com o Gemini.

## O que já foi testado (fora do Arch, em ambiente isolado)

| Teste | Resultado |
|---|---|
| `bash -n` e `shellcheck` em todos os scripts | sem erros |
| Sintaxe Lua (`luac -p`) | sem erros |
| Execução da configuração Lua com a API `hl` imitada (modos componentes e noctalia) | 61 atalhos, 8 regras, sem erro de execução |
| Modelos do matugen renderizados com o matugen 4.2 real | todos os arquivos gerados, sem marcadores sobrando; `cores.lua` válido |
| Instalação em modo simulação, como usuário comum | nenhum arquivo escrito; sequência de comandos coerente |
| `jangada-agente`: criação de worktree, ramo e sessão tmux | funcionou |
| `jangada-hook-claude` com JSON válido e inválido | sai sempre com 0; estado gravado |
| `jangada-agentes --lista` e `--waybar` | saída correta |
| `jangada-agente-fim` com alterações pendentes, recusando e aceitando | recusa preserva tudo; aceite remove o worktree e mantém o ramo |
| Mesclagem dos hooks em `~/.claude/settings.json` já existente | hooks antigos preservados |
| `jangada-mapear` com segredos falsos | chaves mascaradas; `.credentials.json` ignorado |

## O que já foi testado no desktop (19/09/2026)

Hyprland 0.56.0 aninhado dentro da sessão niri, com a mesma configuração da
sessão menos `default.hypr.inicio` (esse módulo roda
`dbus-update-activation-environment`, que trocaria o ambiente da sessão em uso).

| Teste | Resultado |
|---|---|
| `hyprctl configerrors` | vazio |
| Atalhos registrados (`hyprctl binds`) | 61, igual à API imitada |
| Opções aplicadas | `kb_layout br`, `layout dwindle`, `rounding 8`, `border_size 2`, `gaps_in 4` |
| Regra do painel (`workspace = "special:agentes silent"`) | janela `org.jangada.painel` foi para `special:agentes` sem roubar o foco |
| Regra da lista (`float`, `size`, `center`) | flutuante e 1100x650; o monitor aninhado tinha 631 de largura, então a janela ficou em x=-235, que é o centro exato para uma janela mais larga que a tela |
| Regra da borda (`tag = "+agente"`) | janela `org.jangada.agente` recebeu a etiqueta |
| `hl.dsp.window.close()`, `hl.dsp.window.float({action="toggle"})` | funcionam |
| `hl.dsp.workspace.toggle_special("agentes")` | funciona |
| `hl.dsp.focus({ window = "address:0x..." })` do `jangada-agentes --focar` | foco trocou para a janela indicada |
| `hl.dsp.dpms({ action = "disable" / "enable" })` do hypridle | `dpmsStatus` acompanhou |
| `hl.dsp.exit()` do `jangada-menu` | encerrou a instância |
| Instalação real das etapas 10, 20 e 40 | concluída; `jangada-verificar` diz tudo certo |

## Primeira entrada na sessão (19/09/2026): AQ_DRM_DEVICES quebrado

As três tentativas de entrar pelo SDDM voltaram à tela de login. O Hyprland
abortava em `CCompositor::initServer` menos de um segundo depois, com
`std::__throw_bad_variant_access`. O relatório em
`~/.cache/hyprland/hyprlandCrashReport*.txt` mostra a causa:

```
drm: Explicit device list /dev/dri/by-path/pci-0000:01:00.0-card
ERR: drm: Failed to canonicalize path /dev/dri/by-path/pci-0000
ERR: drm: Failed to canonicalize path 01
ERR: drm: Failed to canonicalize path 00.0-card
ERR: drm: Found no gpus to use, cannot continue
CRIT: Cannot open backend: no allocator available
```

O aquamarine separa a lista de `AQ_DRM_DEVICES` por `:`, e o nome em
`/dev/dri/by-path` traz `:` no endereço PCI. O caminho vira três caminhos
inválidos, nenhuma GPU é encontrada e o compositor morre antes de abrir a
tela. Correção: `gpu_para_aquamarine`, em `bin/jangada-config`, resolve cada
dispositivo para o `/dev/dri/cardN` correspondente antes de exportar a
variável. O `by-path` continua sendo o que se escreve em `JANGADA_GPU`, porque
a numeração de `cardN` muda entre partidas; a resolução acontece na hora de
subir a sessão. O `jangada-sessao` também volta para a detecção automática
quando o caminho do `jangada.conf` não existe mais, e o `jangada-verificar`
passou a mostrar o valor resolvido em vez de dar por boa a lista quebrada. O
trecho equivalente em `default/hypr/ambiente.lua` foi removido: a configuração
não resolve links, e o backend já escolheu a placa quando ela é lida.

Lição para os próximos testes: o Hyprland aninhado usa o backend Wayland e
nunca toca no DRM, então não serve para conferir nada da escolha de GPU. Para
isso, ou se entra pelo SDDM, ou se roda `jangada-sessao` num terminal virtual
livre (`Ctrl+Alt+F3`), onde a mensagem de erro fica à vista.

## Revisões cruzadas

| Arquivo | Resultado |
|---|---|
| gemini-20260919-1850.md | revisão superficial (modelo flash-lite); avaliação em avaliacao-gemini-20260919-1850.md |
| gemini-20260919-2038.md | revisão completa pelo Antigravity; 7 de 8 apontamentos aceitos, 1 rejeitado com base no código do Hyprland; avaliação em avaliacao-gemini-20260919-2038.md |

## O que só pode ser confirmado no desktop

1. ~~**API Lua do Hyprland.**~~ Resolvido em 19/09/2026 no Hyprland aninhado:
   `configerrors` vazio e as três expressões duvidosas funcionando (ver a tabela
   acima). Confirmado também que `hyprctl dispatch` aceita só expressões Lua:
   `hyprctl dispatch exec foo` responde erro de sintaxe, e a forma certa é
   `hyprctl dispatch 'hl.dsp.exec_cmd("foo")'`.
2. ~~**Nomes de pacotes.**~~ Resolvido na instalação real: o `matugen` veio do
   AUR como `matugen-bin` 4.1.0 e os demais nomes existem. Foram acrescentados
   `pipewire-pulse` e `qt6-wayland`, que faltavam na lista da interface.
3. **Noctalia.** Verificado em 20/09/2026: o `qs -c noctalia-shell` não funciona
   mais, e a causa não é a versão instalada. O Noctalia saiu do AUR e entrou nos
   repositórios oficiais como `extra/noctalia` 5.1.0-1, que é uma reescrita
   nativa: as dependências do pacote não têm Qt nem Quickshell, e ele entrega um
   binário só, `/usr/bin/noctalia`, sem `qs`. Os pacotes `noctalia-qs` 0.0.12-1 e
   `noctalia-shell` 4.7.7-1, que esta máquina ainda tem instalados, deixaram de
   existir no AUR, e `yay -Si` não devolve nada para nenhum dos dois. O `qs`
   instalado sai com `undefined symbol ... Qt_6_PRIVATE_API` desde que o
   `qt6-base` passou de 6.11.1 para 6.11.2, no mesmo dia; recompilar não resolve,
   porque não há mais pacote para recompilar. Quem precisar do `qs` para outra
   coisa usa `extra/quickshell` 0.3.1-1, que ocupa `/usr/bin/qs` e
   `/usr/bin/quickshell`, os mesmos dois caminhos do `noctalia-qs`: instalar um
   sem remover o outro dá conflito de arquivos.

   A migração para o 5.x troca `qs -c noctalia-shell ipc call <alvo> <ação>` por
   `noctalia msg <comando>`, conforme a documentação do projeto:

   | uso | comando |
   |-----|---------|
   | iniciar a shell | `noctalia` |
   | lançador | `noctalia msg panel-toggle launcher` |
   | configurações | `noctalia msg settings-toggle` |
   | bloquear a tela | `noctalia msg session lock` |
   | menu de sessão | `noctalia msg panel-toggle session` |

   O emoji deixou de ser comando próprio e virou um provedor do lançador,
   acionado por prefixo de busca, configurável em
   `[shell.launcher.providers.emoji]`.

   Cinco pontos do jangada dependem da troca: `default/hypr/atalhos.lua:8`,
   `default/hypr/inicio.lua:20`, `bin/jangada-verificar:18`, o regex
   `conjunto_hypr` em `bin/jangada-update:14` e a busca do QML em
   `bin/jangada-mapear:146`. Nenhum arquivo de `install/pacotes/` declara
   quickshell ou noctalia, então instalação nova não herda o problema. Até a
   troca ser feita, `JANGADA_INTERFACE=noctalia` fica sem barra e sem lançador.

   O `jangada-update` avisa quando o conjunto do Hyprland muda, mas não avisa
   neste caso: ele compara versões de pacotes instalados, e nem um pacote que
   sumiu do AUR nem um binário quebrado por atualização do `qt6-base` aparecem
   nessa comparação. Registrado aqui, sem alterar o `jangada-update`.
4. ~~**Terminal.**~~ Resolvido: `hyprctl clients` mostrou as classes
   `org.jangada.agente`, `org.jangada.painel` e `org.jangada.lista` em janelas
   separadas, cada uma com a sua regra aplicada.
5. ~~**Snapper com /.snapshots já montado.**~~ Resolvido: a simulação foi
   conferida antes e a etapa 20 rodou de verdade; `jangada-verificar` confirma
   snapper configurado e snap-pac presente. Sem entradas de boot para
   snapshots, porque a máquina usa systemd-boot: a volta exige um live USB.

## Benchmarking com a barra do Omarchy

Os quinze itens propostos em `benchmark-waybar-omarchy.md`, seção 4, estão
todos fechados. Os de 4.1 a 4.13 saíram nos commits do dia; 4.14 e 4.15 ficaram
para o fim porque mexem na aparência inteira da barra.

1. ~~**4.1 a 4.9 e 4.13.**~~ Resolvidos em 20/09/2026: classe `ativo` dos
   agentes e estado `aviso` da bateria estilizados, clique na bateria, clique
   direito da rede abrindo o `nmtui`, bandeja completa, inibidor de repouso,
   lista de pacotes fechada, módulo de atualizações pendentes, módulo de mídia
   e aviso quando falta o locale `pt_BR.UTF-8`.
2. ~~**4.10 Janela em foco.**~~ Resolvido em 20/09/2026: `hyprland/window`
   entre os agentes e o relógio, com `max-length` e `separate-outputs`.
3. ~~**4.11 Menu de energia.**~~ Resolvido em 20/09/2026: `jangada-energia` no
   clique da bateria, com perfil, bateria e sessão.
4. ~~**4.12 Temperatura.**~~ Resolvido em 20/09/2026: `hwmon-path-abs` mais
   `input-filename` no lugar do `hwmonN` fixo, com migração.
5. ~~**4.14 Escala de medidas no CSS.**~~ Resolvido em 20/09/2026: a escala
   está no topo de `default/waybar/base.css`, com unidade de 4px, folga interna
   e raio de 8px, e o `spacing` do `config.jsonc` alinhado a ela. Falta a
   conferência visual, que exige reiniciar a barra.
6. ~~**4.15 Barra vertical e reposicionável.**~~ Resolvido em 20/09/2026:
   `jangada-barra --posicao topo|base|esquerda|direita`, com a escolha em
   `JANGADA_BARRA_POSICAO` e um conjunto de formatos só de ícone para as bordas
   em pé. Falta a conferência visual e, com ela, confirmar que a mesclagem do
   `include` da waybar preserva as chaves que não foram sobrescritas.

## Decisões tomadas nesta revisão

1. **Sem IgnorePkg para o Hyprland.** A ideia inicial era fixar o Hyprland e
   atualizá-lo à parte. Isso cria atualização parcial: as bibliotecas do
   conjunto (aquamarine, hyprutils, hyprlang, hyprgraphics) avançariam sem o
   Hyprland e a sessão deixaria de abrir. O `jangada-update` agora avisa quando
   o conjunto muda, mostra as versões e pede confirmação, e o snap-pac garante
   o retorno.
2. **Sessão separada.** O Hyprland 0.55 dá preferência a `hyprland.lua` sobre
   `hyprland.conf` na mesma pasta. Escrever em `~/.config/hypr` trocaria a
   configuração da sessão atual sem aviso. Por isso o jangada usa
   `~/.config/jangada/hypr` e inicia com `--config`.
3. **tmux em socket próprio** (`tmux -L jangada`), para não misturar as
   sessões de agentes com o tmux pessoal nem depender do `~/.tmux.conf`.
4. **Estado dos agentes só para sessões do jangada.** O hook usa a variável
   `JANGADA_SESSAO`; agentes abertos fora do `jangada-agente` geram aviso, mas
   não aparecem na barra.
5. **Worktree removido, ramo mantido.** O `jangada-agente-fim` nunca apaga o
   ramo `agente/<nome>`, para que nenhum commit do agente se perca.
6. **Interface intercambiável.** `JANGADA_INTERFACE=noctalia` permite usar o
   Noctalia dentro da sessão jangada enquanto as personalizações não forem
   convertidas.

## Próxima etapa

Barra em Quickshell com o painel de agentes integrado, a partir das
personalizações do Noctalia registradas pelo `jangada-mapear`.
