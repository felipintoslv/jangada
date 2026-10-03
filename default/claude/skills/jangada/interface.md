# Barra, tema, bloqueio e login

## Waybar

- O módulo nativo `mpris` fica fora das listas de módulos por padrão.
  Na Waybar 0.15.0, quedas locais em 22/09 e 01/10/2026 passaram por
  `Gtk::Widget::set_visible` e `libplayerctl`, semelhantes ao relato
  https://github.com/Alexays/Waybar/issues/2747. A configuração permanece
  disponível para ativação manual; reativar exige conferir a estabilidade
  ao iniciar e encerrar reprodução, inclusive no navegador.

- O `pulseaudio#microfone` precisa de comandos próprios de rolagem com
  `@DEFAULT_AUDIO_SOURCE@`: a rolagem padrão do módulo muda a saída.
  Na dica, `{source_volume}` é o volume da entrada; `{volume}` é o da saída.
- `jangada-interface-processos` confere sessão, configuração e argumentos
  antes de sinalizar Waybar ou Mako. O swaybg iniciado pelo tema recebe
  `JANGADA_INTERFACE_PROCESSO=papel`; processos antigos sem essa marca não
  são encerrados. Reinicie a sessão uma vez ao receber esta atualização.
- **Todo on-click que abre janela usa `setsid -f`.** A waybar espera o fim do
  on-click antes de rodar o `exec` do módulo de novo; um terminal em primeiro
  plano congela o contador da barra onde houve o clique. Só `--parar` e
  `toggle`, que terminam na hora, ficam sem ele; o `testes/barra.sh` confere.
- Para atualizar um módulo na hora, o módulo declara `"signal": N` e quem
  mudou o estado roda `pkill -RTMIN+N -x waybar`. O sinal 10 fica reservado
  às sessões e ao contador da Central de Tarefas. O contador consulta a cada
  dez segundos e não importa Qt; a janela consulta a cada dois segundos.
- A Central de Tarefas usa soquete de arquivo numa pasta 0700 em
  `$XDG_RUNTIME_DIR/jangada-tarefas`, oculta pelo runtime privado do isolamento.
  Soquete abstrato ignora permissões de arquivo e fica acessível no espaço
  de rede compartilhado. O segundo clique exige confirmação da janela.
  `--mostrar` usa QCoreApplication para encaminhar sem inicializar a tela.
- A barra é gerada pelo `jangada-barra`, que inclui o `config.jsonc` em uso e
  aplica `JANGADA_BARRA_POSICAO`.
- No módulo `privacy`, a folga interna (padding) fica em `#privacy-item`, não
  em `#privacy`. O contêiner pai `#privacy` com padding reserva largura visual
  mesmo com os seletores recolhidos; já no `#privacy-item`, a barra recolhe o
  espaço por completo quando não há captura ativa.

## Painel de indicadores

- Em séries diárias do Plotly, marcas automáticas podem cair entre os dias
  e repetir o rótulo `dd/mm`. Defina os dias das marcas e limite a quantidade
  conforme o espaço disponível.
- `subplot(..., shareY = TRUE)` compartilha escalas por linha de painéis.
  Para comparar todas as séries na mesma escala, defina também o mesmo
  intervalo de valores em cada painel. Rótulos de valores na ponta podem
  ser cortados; pequenos múltiplos usam o nome da série acima do painel.
- A paleta do protocolo de gráficos foi validada sobre branco. O painel
  mantém esse fundo nos gráficos, mesmo com a interface em modo escuro.

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

## Compartilhar tela (Meet, navegador)

- A captura passa pelo `xdg-desktop-portal-hyprland`, com dmabuf. O seletor
  mostra o tamanho lógico do monitor (um 4K com escala 2 aparece como
  1920x1080), mas o quadro enviado sai na resolução física.
- Monitor 4K inteiro deixa o compartilhamento travado: o navegador reduz e
  codifica mais de 8 milhões de pixels por quadro. Oriente a compartilhar uma
  guia (não passa pelo portal), uma janela ou o monitor de menor resolução.
- O xdph lê `$XDG_CONFIG_HOME/hypr/xdph.conf`. Para limitar quadros sem
  escrever em `~/.config/hypr`, use o mesmo recurso do hypridle: um drop-in do
  serviço de usuário com `XDG_CONFIG_HOME` apontando para `default/`.
