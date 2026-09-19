Você vai revisar o repositório "jangada", enviado abaixo arquivo por arquivo.
É uma configuração de Arch Linux com Hyprland 0.55 ou mais novo (configuração
em Lua, API hl.*), organizada para o trabalho com agentes de IA. Leia primeiro
README.md e AGENTS.md, que definem as regras do projeto.

O repositório ainda não foi executado numa máquina real. Foi escrito por outro
modelo (Claude), e a sua revisão será conferida por ele e pelo autor. Por isso,
seja específico e honesto sobre o grau de certeza de cada apontamento.

## O que verificar

1. Erros que impediriam o funcionamento: sintaxe, nomes de funções da API Lua
   do Hyprland 0.55 (hl.config, hl.bind, hl.window_rule, hl.dsp.*), opções de
   linha de comando de waybar, fuzzel, mako, hyprlock, hypridle, matugen 4,
   tmux, fzf, git worktree, snapper e fastfetch.
2. Riscos ao sistema: comandos com sudo, alteração de arquivos em /etc,
   procedimento do snapper com /.snapshots já montado, atualizações parciais
   no Arch, perda de dados em jangada-agente-fim.
3. Quebra das regras do AGENTS.md: escrita fora das pastas do jangada, etapa
   de instalação que não respeita JANGADA_SIMULAR ou que não pode ser repetida.
4. Segurança: hooks do Claude Code, máscara de segredos no jangada-mapear,
   uso de variáveis sem aspas, execução de conteúdo lido de arquivos.
5. Nomes de pacotes do Arch e do AUR em install/pacotes/ que possam estar errados.
6. Lacunas relevantes para o objetivo (trabalho com vários agentes em paralelo).

## O que não fazer

1. Não reescrever arquivos inteiros nem propor mudanças de estilo.
2. Não apontar como erro algo de que você não tem certeza; nesse caso, marque
   como "a confirmar" e diga como confirmar (comando, documentação).
3. Não sugerir voltar ao formato hyprlang (.conf) para o Hyprland; o projeto
   usa Lua de propósito. hyprlock e hypridle continuam em .conf, e isso está certo.

## Formato da resposta (em português)

Para cada apontamento:

    ### N. Título curto
    - Arquivo e linha:
    - Gravidade: crítico | alto | médio | baixo
    - Certeza: alta | média | a confirmar
    - Problema:
    - Correção proposta: (trecho de código mínimo)

No fim, uma seção "O que está correto" com os pontos que você conferiu e
considera adequados, e uma seção "Perguntas ao autor", se houver.
