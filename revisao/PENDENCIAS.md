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
3. **Noctalia.** O comando do lançador (`qs -c noctalia-shell ipc call launcher toggle`)
   e o início (`qs -c noctalia-shell`) seguem a documentação conhecida, mas
   dependem da versão instalada. O `jangada-mapear` registra a versão.
4. ~~**Terminal.**~~ Resolvido: `hyprctl clients` mostrou as classes
   `org.jangada.agente`, `org.jangada.painel` e `org.jangada.lista` em janelas
   separadas, cada uma com a sua regra aplicada.
5. ~~**Snapper com /.snapshots já montado.**~~ Resolvido: a simulação foi
   conferida antes e a etapa 20 rodou de verdade; `jangada-verificar` confirma
   snapper configurado e snap-pac presente. Sem entradas de boot para
   snapshots, porque a máquina usa systemd-boot: a volta exige um live USB.

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
