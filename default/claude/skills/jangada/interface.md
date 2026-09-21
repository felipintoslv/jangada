# Barra, tema, bloqueio e login

## Waybar

- **Todo on-click que abre janela usa `setsid -f`.** A waybar espera o fim do
  on-click antes de rodar o `exec` do módulo de novo; um terminal em primeiro
  plano congela o contador da barra onde houve o clique.
- Para atualizar um módulo na hora, o módulo declara `"signal": N` e quem
  mudou o estado roda `pkill -RTMIN+N -x waybar`.
- A barra é gerada pelo `jangada-barra`, que inclui o `config.jsonc` em uso e
  aplica `JANGADA_BARRA_POSICAO`.

## Tema (`jangada-tema`)

- O matugen gera cores de bordas, barra, notificações, menu, bloqueio,
  terminal e login a partir do papel de parede. Modelos em
  `default/matugen/modelos/`.
- Não passe `--source-color-index`: ele ignora o `prefer` do
  `default/matugen/config.toml`. O esquema vem de `JANGADA_TEMA_ESQUEMA`
  (padrão `scheme-fidelity`).
- No terminal (ghostty), só fundo, texto, cursor e seleção vêm do papel de
  parede; as 16 cores ANSI ficam fixas porque têm significado.
- O papel de parede por tela vai para `~/.cache/jangada/papel`
  (`JANGADA_PAPEL_AJUSTE`: espelho, desfoque, cor, cobrir).

## Bloqueio e ociosidade

- O `hypridle` ignora `-c`: sempre lê `$XDG_CONFIG_HOME/hypr/hypridle.conf`.
  O jangada sobe com `env XDG_CONFIG_HOME=$JANGADA_PATH/default/hypridle
  hypridle`. O `-c` do `hyprlock` funciona.
- Falha de programa lançado com `hl.exec_cmd` na partida não aparece no
  `hyprland.log`; rode o comando à mão para ver o erro.

## Tela de login (SDDM)

O tema fica numa pasta do sistema; o `jangada-tema` não consegue atualizá-lo.
Depois de trocar cores ou papel de parede, rode `jangada-sddm aplicar`.
`jangada-sddm testar` abre o tema numa janela sem alterar nada.
