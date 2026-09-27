# Registro de mudanças

Gerado das mensagens de commit por `jangada-versao --lancar`; não edite
à mão. A versão instalada aparece em `jangada-versao`.

## 0.1.0 (2026-09-26)

### Novidades

- versao: versões com tag e CHANGELOG gerado dos commits
- agentes: isola o agente no bubblewrap com o jangada-isolar
- validar: registra cada rodada em validar.jsonl e resume com --metricas
- validar: procura segredos com o gitleaks nas linhas acrescentadas
- escrita: fecha lacunas em relação ao benchmark
- validar: revisor confere regras objetivas de escrita
- skills: acrescenta skills de relatório técnico e acadêmico
- agente: acrescenta regras de código R ao protocolo em projetos R
- validar: roda o lintr nas linhas R alteradas antes do revisor
- protocolo: acrescenta regras de escrita para os agentes
- suporte macos, console de agentes focado e atalhos na waybar
- agente-fim: atualiza cópia instalada após integração e repassa raiz e integrado a pos-agente-fim
- agente: suporta opção --revisor e seletor com auto-revisão
- validar: suporta auto-revisão pelo mesmo modelo e opção --revisor mesmo
- agentes: adiciona perfis agy-agy e claude-claude para auto-revisão
- waybar: adiciona módulos nativos systemd-failed-units, privacy e disk

### Correções

- agente: --janela repassa o --sem-isolar ao terminal novo
- validar: nomes, renomeações e métricas apontados pela revisão
- validar: conflito e sintaxe conferem também arquivos novos
- validar: cada entrega aprovada reinicia base e rodadas
- resolve apontamentos de auditoria tecnica com claude e portabilidade macos
- agente-fim: permite encerrar sessoes diretas com --integrar sem erro fatal
- resolve inconsistencias gerais e cobertura de testes
- validar,agente: ajusta precedência de revisor e coerência de auto-revisão
- waybar: preserva hide-on-ok na barra em pé e remove format-ok inalcançável
- ajustes da revisão do tema e do papel por tela
- detecta systemd-boot sem precisar de root
- caminho na shell, corrida no estado do agente e Lua 5.5

### Outras mudanças

- ci: roda os testes e simula a instalação num contêiner Arch
- style: aplica tom do papel de parede ao icone da jangada no waybar
- docs(revisao): registra parecer e avaliação da atualização automática pós-integração
- docs(agentes): documenta auto-revisão, novos perfis e opção --revisor
- benchmarking: revisão de escopo, adjetivação e lições de segurança
- benchmarking: revisão do Claude sobre o README do agy
- docs(waybar): corrige fontes do cliphist e screenrecorder no benchmark
- docs(waybar): benchmarking de repositórios e módulos do waybar
- agentes: revisão cruzada no jangada-validar e fim do jangada-par
- agy: correções da revisão (modo direto no jangada-validar, status com Markdown, limpeza do prompt, JSON no verificar)
- agentes: agy como agente da sessão, com hook próprio, seletor de agente e jangada-validar (Claude só revisa o diff)
- skill: compartilhamento de tela, tamanho lógico no seletor e custo do monitor 4K
- agentes: lista em janela espera Enter depois do Alt+I e do Ctrl+X
- auditoria do fechamento: parecer do agy (15 itens) e avaliação; 13 aplicados no todo ou em parte
- README: ciclo dos agentes, várias máquinas, canal e testes; revisao/README.md com índice e cabeçalho fixo; situação dos itens do benchmark
- portabilidade: regra do DP-3 sai de base.css e a skill deixa de citar esta máquina; skill de agentes cobre avaliação, hooks, restauração, perfis e ganchos
- importar: niri para usuario.lua, monitores.lua e jangada.conf com extensão .importado; lista e shell focam a janela aberta
- testes/aninhado.sh: carrega a configuração num Hyprland aninhado
- update: canal, conferência do boot e da NVIDIA; ganchos do usuário
- verificar: --diagnostico e --agente; chaves JANGADA_REPO e JANGADA_CANAL
- jangada-consumo: tokens do Claude no bloco de 5 horas
- agente: perfis em ~/.config/jangada/agentes/NOME.conf
- agentes: --integrar, --restaurar e --anterior
- agente: --prompt e --prompt-arquivo; nome de ramo sem acento
- hooks: id da conversa, SessionStart/SessionEnd e tipo da notificação
- par: Claude avalia cada apontamento do agy antes de implementar
- agentes: jangada-agente-fim recusa opção e sessão inexistente
- agentes: corrige nomes com acento no preparo, reflink entre subvolumes e campos vazios no painel
- revisao: parecer do agy sobre os itens 1 a 3 e avaliação
- agentes: SUPER+N foca o próximo agente que espera
- agentes: skill do jangada para o Claude Code
- agentes: prepara o worktree novo com o que o git não leva
- par: limita o prompt do agy em bytes, não o diff em caracteres
- revisao: compara o jangada com gerenciadores de agentes e camadas de Hyprland
- waybar: solta os terminais abertos por clique na barra
- tema: cores fieis ao papel de parede, modelo do sddm e papel sem corte por tela
- sddm: tema de login no estilo do menu e sessao exclusiva sem mover arquivos de pacotes
- sessao: acoes rapidas de energia, tema cordel no hyprlock e exclusividade sddm
- waybar: compensa tamanho de fonte no monitor 4K (DP-3)
- waybar: correcoes da revisao tecnica de ilhas e agentes
- waybar: layout em ilhas flutuantes e enriquecimento do modulo de agentes
- migrar: a simulação não grava mais a marca da migração
- revisao: corrige a nota do Noctalia, que saiu do AUR
- revisao: fecha o benchmarking da barra e registra o Noctalia parado
- barra: posição escolhível nas quatro bordas, com formatos só de ícone em pé
- barra: escala de medidas no lugar dos números soltos
- fuzzel: jangada-energia usa a função compartilhada
- instalador: declara o less, que o mudancas precisa
- shell: revisar diz ao agy para não executar comandos
- jangada-par: captura a resposta do agy por cano, não por arquivo
- barra: temperatura resolve o sensor por dispositivo, não por número
- energia: menu de perfil, bateria e sessão no clique da bateria
- revisão: compara a barra do jangada com a do Omarchy
- barra: mostra a janela em foco entre os agentes e o relógio
- barra: clique direito da rede abre o nmtui
- agentes: escolhe o parecer sem ls e cobre o subshell no verificar
- shell: conserta o diff, o concluir e o caminho do subshell
- calendario: comandos add, listar e importar na linha de comando
- agentes: prévia do seletor imune à expansão de igual do zsh
- barra: aplica o que o benchmarking com o Omarchy apontou
- jangada-par: repete a chamada do agy quando ela volta vazia
- comandos de áudio, bluetooth, rede e calendário na barra e no menu
- jangada-par: evita estourar o limite de tokens na revisão
- painel respeita ciclos encerrados em concluido ou aguardando
- jangada-par: aplica a revisão do Antigravity e conserta o prompt dele
- jangada-par: cor e negrito na saída, e limpeza do que o ciclo cria
- jangada-par: preserva o estado final, confere o agy e mostra o worktree
- monitor: btop em janela flutuante e indicadores de carga na waybar
- shell: subshell com comandos diretos de agentes e projetos
- par: protocolo de trabalho em par entre o Claude e o Antigravity
- agentes: painel enxerga sessões sem tmux e o fzf cancelado não derruba o script
- atalhos: comando jangada-atalhos, no espírito do Omarchy
- tema: o terminal passa a receber as cores do matugen
- hypridle: sobe o daemon pelo XDG_CONFIG_HOME
- sessão: resolve a GPU para /dev/dri/cardN antes do aquamarine
- revisao: registra os testes feitos no desktop e fecha quatro pendências
- verificar: não trata glob vazio como arquivo Lua
- mapear: reconhece systemd-boot sem precisar de root
- escolha da GPU antes de o compositor subir e dois pacotes que faltavam
- revisão: script rodar-revisao.sh para o Antigravity CLI (agy -p)
- revisão cruzada: aplica 7 apontamentos do Gemini, rejeita 1 e corrige alvo do tmux
- jangada: estrutura inicial, instalador, Hyprland em Lua, camada de agentes, mapeamento e revisão
