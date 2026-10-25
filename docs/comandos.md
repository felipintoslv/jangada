# Comandos do jangada

## Comandos

| Comando | Função |
|---|---|
| `jangada-update` | busca o ramo de `JANGADA_CANAL`, mostra os commits novos, o resumo por arquivo e um aviso quando mudam `migrations/`, `install/` ou `bin/`, e só os aplica se a resposta for `s` (sem terminal não aplica); mostra se o conjunto do Hyprland mudou, atualiza o sistema, aplica migrações, confere initramfs e driver NVIDIA e roda o gancho `pos-update`. Se o pacman ou o AUR falhar, a conferência da imagem de boot roda mesmo assim, e as migrações e a recarga do Hyprland ficam para depois do conserto |
| `jangada-verificar` | confere pacotes, snapshots, sessão, hooks e erros de configuração do Hyprland; `--diagnostico` grava um relatório e `--agente` abre um agente com ele no repositório do jangada; do `hyprland.log` entram só erros e avisos, e o log e o relatório de falha vão marcados como dados |
| `jangada-vigia diagnostico\|lista\|apagar` | grava sob pedido um retrato do sistema e da sessão em `~/.local/state/jangada/vigia` (`.md` e `.json`), só leitura, sem rede nem modelo de IA; `lista` mostra os retratos e `apagar` remove um ou `--todos`; veja [Vigia](vigia/README.md) |
| `jangada-versao` | mostra a versão da cópia (`0.1.0`, ou `0.1.0-3-gabc1234` com commits depois da tag); `--novidades [DE [ATE]]` lista as mudanças, `--registro` imprime o registro completo e `--lancar X.Y.Z` grava o `CHANGELOG.md`, faz o commit e cria a tag `vX.Y.Z` (sem push); `-C DIR` opera em outro repositório |
| `jangada-assinar` | assina com a chave SSH (`JANGADA_ASSINATURA_CHAVE`) os commits da cópia de trabalho ainda não enviados e sem assinatura válida, depois da confirmação; roda num terminal comum, porque o isolamento oculta o `~/.ssh` |
| `jangada-migrar` | aplica as migrações pendentes (o `jangada-update` já chama) |
| `jangada-snapshot "descrição"` | cria um snapshot manual do sistema; com `--agente`, o do `jangada-agente --snapshot`, fora da limpeza do snapper e limitado aos `JANGADA_SNAPSHOTS_AGENTE` mais recentes |
| `jangada-tema [imagem]` | gera as cores a partir de um papel de parede e recarrega a interface |
| `jangada-tarefas` | central gráfica de tarefas (`--nova`, `--waybar`, `--simular`) |
| `jangada-agente` | escolhe o agente (Claude ou Codex; o agy fica só de suporte), o projeto e cria um worktree, e abre o agente numa sessão tmux, isolado pelo `jangada-isolar` (`--prompt`, `--prompt-arquivo`, `--perfil`) |
| `jangada-isolar` | roda um comando no bubblewrap, com o sistema somente leitura e a pasta atual gravável; `--mostrar` imprime a chamada ao `bwrap` |
| `jangada-delegar PAPEL "pedido"` | executa o apoio com destino e fontes explícitos; veja [subagentes e delegação](subagentes-e-delegacao.md) |
| `jangada-avaliar-ollama` | repete três casos de leitura com fontes sintéticas, compara fatos e referências com um gabarito e registra recusas, tempo e variação; não promove o modelo nem chama provedores remotos |
| `jangada-fila` | mostra a fila persistente do projeto; `--importar PLANO.json` acrescenta tarefas, `--json` detalha o estado, `--revisao` lista o que aguarda revisão e `--metricas` resume consumo, revisões e custo estimado pelos preços de `precos.json` (ver [fila](subagentes-e-delegacao.md#fila-persistente-de-projetos)) |
| `jangada-projeto` | cadastra projeto e política, cria atividade, reassocia caminho e consulta sessões, fila, execuções e revisões; `consultar --todos` reúne todos os projetos sem alterar o estado |
| `jangada-executar` | executa tarefas elegíveis da fila pelo `jangada-delegar`, sem aprovar o conteúdo (`--limite`, `--perfil balanced\|quality\|offline`, `--permitir-remoto`, `--permitir-codex`, `--supervisionar`, `--amostrar`, `--paralelo`); `--acompanhar` mantém a fila em primeiro plano até o prazo |
| `jangada-retomar` | recoloca na fila tarefas que esperavam cota ou provedor, quando há executor, orçamento e tentativas (`--atualizar`, `--executar`) |
| `jangada-task ID AÇÃO` | controla uma tarefa: `pausar`, `retomar`, `cancelar`, `repetir`, `revisar --aprovar\|--reprovar --parecer` (aceita `ID1,ID2` no mesmo parecer), e `assumir`, `entregar` e `executar-principal` para os agentes principais |
| `jangada-router status` | estado, cota e espera dos provedores (`--atualizar`, `--atualizar-codex`) |
| `jangada-provedor pausar\|ativar ID` | tira um provedor da execução da fila ou o devolve |
| `jangada-filtrar` | roda um comando e condensa a saída para o agente (`-m`, `-e`, `-p`); prefira `jangada-filtrar -- COMANDO` ao modo cano, que não vê o código de saída |
| `jangada-mapa [PASTA]` | mapa compacto do repositório (arquivos e assinaturas de funções) para dar contexto a um agente |
| `jangada-worktree-preparar` | leva para um worktree novo os arquivos ignorados que o projeto precisa (chamado pelo `jangada-agente`) |
| `jangada-validar` | confere a entrega localmente e manda o diff ao revisor configurado (Claude, agy ou Codex) e devolve `STATUS: APROVADO` ou `REVISAR`; ferramenta aplicável ausente, validação pulada e autorrevisão não aprovam; o agente chama antes de entregar |
| `jangada-shell` | inicia subshell enriquecida com comandos diretos de agentes e projetos. O console se apresenta como Jangada Core; o comando continua sendo `jangada-shell` |
| `jangada-agentes` | lista as sessões de agentes, com estado, e permite abrir, integrar ou encerrar (`--proximo`, `--anterior`, `--restaurar`) |
| `jangada-agente-fim` | encerra uma sessão e remove o worktree após conferência; `--integrar` exige aprovação independente protegida, confirmação humana e testes; mantém sessão, ramo e worktree. Veja [ciclo da tarefa](ciclo-da-tarefa.md#fim-da-sessão) |
| `jangada-consumo` | tokens do Claude Code no bloco de 5 horas em andamento (também na dica da barra) |
| `jangada-indicadores` | resumo de tarefas, revisores e delegações a partir dos registros; `--json` alimenta a aba Indicadores da Central |
| `jangada-gancho` | roda os ganchos do usuário de um evento (chamado pelos outros comandos) |
| `jangada-importar` | converte a configuração do niri em arquivos `.importado` |
| `jangada-atalhos` | paleta de atalhos no fuzzel que executa a ação escolhida, reunindo atalhos do Hyprland, da Central e do tmux (`--lista` imprime no terminal) |
| `jangada-sddm aplicar` | deixa o jangada como única sessão no SDDM, com o tema de login do jangada (`restaurar`, `status`, `testar`) |
| `jangada-barra` | sobe ou reinicia a waybar do jangada; `--posicao topo\|base\|esquerda\|direita\|ciclo` troca a borda |
| `jangada-recarregar` | recarrega o Hyprland e mostra os erros de configuração |
| `jangada-rede`, `jangada-bluetooth`, `jangada-audio`, `jangada-energia` | menus no fuzzel para Wi-Fi e cabo, dispositivos Bluetooth, saída e entrada de áudio, e perfil de energia e bateria (abertos pela barra) |
| `jangada-calendario`, `jangada-captura`, `jangada-monitor`, `jangada-atualizacoes` | calendário com eventos, captura de tela (`regiao\|tela`), monitor do sistema e atualizações pendentes (abertos pela barra e pelos atalhos) |
| `jangada-menu` | menu central com as ações acima, mais bloquear, suspender, reiniciar, desligar e sair |
| `jangada-logo` | mostra o símbolo do jangada com as informações do sistema (fastfetch; neofetch como alternativa) |
| `jangada-mapear` | inventário da configuração atual da máquina (Hyprland, Noctalia, terminal, agentes), sem alterar nada |
