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

## O que só pode ser confirmado no desktop

1. **API Lua do Hyprland.** A imitação só confere a estrutura. Confirmar com
   `hyprctl configerrors` depois de entrar na sessão, em especial:
   `workspace = "special:agentes silent"` na regra do painel,
   `hl.dsp.focus({ window = "address:..." })` no `jangada-agentes --focar` e
   `hyprctl dispatch 'hl.dsp.dpms(...)'` no hypridle.
2. **Nomes de pacotes.** Não foi possível consultar os repositórios do Arch
   daqui. O instalador lista os que não encontrar, sem interromper. Os mais
   incertos: `matugen` (pode estar só no AUR, como `matugen-bin`),
   `ttf-jetbrains-mono-nerd`, `hyprpolkitagent`, `limine-snapper-sync`.
3. **Noctalia.** O comando do lançador (`qs -c noctalia-shell ipc call launcher toggle`)
   e o início (`qs -c noctalia-shell`) seguem a documentação conhecida, mas
   dependem da versão instalada. O `jangada-mapear` registra a versão.
4. **Terminal.** `ghostty --class=org.jangada.agente` abre uma instância
   separada; confirmar que as regras de janela reconhecem a classe
   (`hyprctl clients`).
5. **Snapper com /.snapshots já montado.** O procedimento segue a wiki do Arch,
   mas mexe em subvolume. Rodar primeiro com `JANGADA_SIMULAR=1 ./install.sh 20`
   e conferir `sistema/subvolumes.txt` no mapa.

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
