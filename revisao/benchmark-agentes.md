# Comparação do jangada com projetos semelhantes

Documento de consulta, feito em 21/09/2026. A situação de cada item está na
seção 7.

Fonte: busca na API do GitHub (`search/repositories`, ordenada por estrelas)
com os termos "claude code worktree tmux", "agents git worktree parallel",
"coding agents orchestrator terminal", "hyprland dotfiles quickshell",
"hyprland arch dotfiles installer" e "claude code hooks notification", mais a
leitura do README de 18 projetos e dos scripts `bin/omarchy-*` ligados a
agentes. Estrelas e datas do último envio são as do dia da consulta.

## 1. Onde o jangada se encaixa

O jangada junta duas coisas que no GitHub quase sempre aparecem separadas:

1. **Camada de área de trabalho** para Arch e Hyprland (instalador, tema pelo
   papel de parede, barra, menus, atualização com migrações).
2. **Camada de agentes** (worktree por tarefa, sessão tmux, estado por hooks,
   painel, revisão cruzada).

Só o Omarchy 4 tenta as duas ao mesmo tempo. Os demais projetos de área de
trabalho não têm nada de agentes, e os gerenciadores de agentes não sabem que
existe um compositor.

### 1.1 Camada de área de trabalho

| Projeto | Estrelas | O que é | Relação com o jangada |
|---|---|---|---|
| [omacom/omarchy](https://github.com/omacom/omarchy) | 42.457 | Arch + Hyprland completo, versão 4 com barra em Quickshell | Modelo de repositório, migrações e comandos `*-update`; já tem comandos de agente (itens D, I, J e K) |
| [end-4/dots-hyprland](https://github.com/end-4/dots-hyprland) | 16.175 | Configuração do Hyprland com shell em Quickshell | Só aparência; sem agentes |
| [caelestia-dots/shell](https://github.com/caelestia-dots/shell) | 12.445 | Shell em Quickshell | Só aparência |
| [noctalia-dev/noctalia](https://github.com/noctalia-dev/noctalia) | 10.759 | Shell reescrita em Wayland nativo, sem Qt | Era a interface alternativa do jangada; mudou de programa (ver `PENDENCIAS.md`, item 3) |
| [HyDE-Project/HyDE](https://github.com/HyDE-Project/HyDE) | 9.616 | Configuração do Hyprland com temas | Instalador mexe em GRUB, SDDM e `pacman.conf` sem sessão isolada |
| [AvengeMedia/DankMaterialShell](https://github.com/AvengeMedia/DankMaterialShell) | 8.167 | Shell em Quickshell + serviço em Go, para niri e Hyprland | Candidato natural se a barra do jangada for para Quickshell (seção 5) |
| [mylinuxforwork/dotfiles](https://github.com/mylinuxforwork/dotfiles) | 5.028 | ML4W, Hyprland completo | Só aparência |

### 1.2 Camada de agentes

| Projeto | Estrelas | Forma | Pontos que interessam ao jangada |
|---|---|---|---|
| [BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban) | 28.151 | Aplicação web com quadro kanban | **Anunciou o encerramento do projeto** |
| [manaflow-ai/cmux](https://github.com/manaflow-ai/cmux) | 27.303 | Terminal para macOS baseado no Ghostty | Aba acende quando o agente pede atenção; lateral com ramo, PR, portas abertas e última notificação |
| [superset-sh/superset](https://github.com/superset-sh/superset) | 14.433 | IDE gráfica para muitos agentes | Fora do escopo |
| [smtg-ai/claude-squad](https://github.com/smtg-ai/claude-squad) | 8.508 | TUI em Go sobre tmux | Nova sessão com prompt (`N`), aba de diff, pausar e retomar, perfis de agente |
| [max-sixty/worktrunk](https://github.com/max-sixty/worktrunk) | 8.253 | CLI de worktree para agentes | Merge com limpeza num comando, cópia de pastas ignoradas por reflink, porta por worktree |
| [dagger/container-use](https://github.com/dagger/container-use) | 4.047 | Servidor MCP que isola o agente em contêiner | Fora do escopo por ora |
| [agent-of-empires](https://github.com/agent-of-empires/agent-of-empires) | 3.277 | TUI + web + API sobre tmux | Sessões persistentes, acesso pelo celular, contêiner opcional |
| [raine/workmux](https://github.com/raine/workmux) | 2.689 | worktree + janela tmux | O mais próximo do jangada em filosofia; ver abaixo |
| [kbwo/ccmanager](https://github.com/kbwo/ccmanager) | 1.247 | TUI sem tmux | Restaura sessões depois de reiniciar; `.worktreeinclude`; copia o histórico do Claude entre worktrees |
| [asheshgoplani/agent-deck](https://github.com/asheshgoplani/agent-deck) | 936 | TUI de sessões | Bifurcar sessão, "conductor" que responde pelos agentes, ponte com Telegram |
| [tuchg/Lucarne](https://github.com/tuchg/Lucarne) | 340 | Serviço de notificação | Aprovar e responder ao agente pelo Telegram |
| [epilande/ccmux](https://github.com/epilande/ccmux) | 173 | TUI sobre tmux | Pular para quem espera, repassar a resposta de uma sessão para outra, diff por trecho |

O workmux merece destaque porque escolheu o mesmo caminho do jangada
(tmux + worktree, nada de interface gráfica) e o README dele diz por quê:
"Build on your terminal setup instead of yet another agentic GUI that won't
exist next year". O fim anunciado do vibe-kanban, o maior da lista, é um
argumento a favor dessa escolha.

## 2. O que o jangada já faz e os outros não

| Recurso | jangada | Quem mais tem |
|---|---|---|
| Estado do agente na barra do sistema e notificação com botão que foca a janela certa (`bin/jangada-hook-claude`, `jangada-agentes --focar`) | sim | cmux faz algo parecido, só em macOS e dentro do próprio terminal |
| Área de trabalho especial para os agentes (`SUPER+CTRL+A`) | sim | ninguém; os outros vivem dentro de um terminal |
| Revisão cruzada automática entre dois modelos, com rodadas (`jangada-par`: Claude implementa, Antigravity revisa, Claude corrige) | sim | ccmux só repassa texto à mão; agent-deck tem um agente coordenador, sem papel de revisor |
| Snapshot do sistema antes de o agente começar (`--snapshot`) | sim | ninguém |
| Migrações a cada atualização e sessão isolada no gerenciador de login | sim | Omarchy tem migrações, não isola a sessão |
| Revisor proibido de executar comandos (decisão de 20/09) | sim | claude-squad e ccmanager vão no sentido oposto, com aprovação automática |

## 3. O que vale acrescentar

Ordenado por valor sobre custo. Cada item diz de onde vem a ideia e onde
entraria no jangada.

### 3.1 Prioridade alta (baixo custo, uso diário)

**A. Arquivos ignorados pelo git no worktree novo.** Um `git worktree add`
cria uma cópia limpa: sem `.Renviron`, sem `.env`, sem a pasta de dados que
está no `.gitignore`. Nos projetos em R isso quebra o script logo na primeira
leitura de dados. workmux (`files.copy` e `files.symlink`), agent-deck e
ccmanager (`.worktreeinclude`, sintaxe do `.gitignore`) resolvem do mesmo
jeito. Proposta para `bin/jangada-agente`, logo depois do `worktree add`:

- ler `.worktreeinclude` na raiz do repositório;
- pastas grandes viram link simbólico (dados de CNPJ e RAIS não podem ser
  copiados); arquivos pequenos são copiados;
- como o sistema está em btrfs (há snapper), `cp --reflink=auto` copia pastas
  inteiras sem gastar espaço, que é o truque do `wt step copy-ignored` do
  worktrunk;
- rodar `.jangada/preparar.sh` do projeto, se existir (o
  `worktree-setup.sh` do agent-deck, o `post_create` do workmux).

**B. Pular para o agente que espera.** workmux (`last-done`, com repetição
que percorre os demais do mais recente ao mais antigo) e ccmux fazem disso o
atalho principal. Hoje o jangada exige abrir a lista e escolher. Proposta:
`jangada-agentes --proximo`, que foca a sessão `aguardando` mais antiga (ou
`concluido`, se não houver), ligado a um atalho livre como `SUPER+grave`
(`SUPER+ALT+A` já é o `assistente.sh`). Complemento
barato: `--anterior`, que alterna entre os dois últimos agentes visitados.

**C. Criar a tarefa já com o prompt.** claude-squad (`N`), workmux (`-p`,
`-P arquivo`, `-e` abre o editor) e Omarchy (`omarchy agent prompt "..."`)
aceitam a instrução na criação. Proposta: `jangada-agente --prompt TEXTO` e
`--prompt-arquivo ARQ`, passados ao `claude` como argumento posicional; o nome
da tarefa pode sair das primeiras palavras do prompt quando `--nome` faltar.
Abre caminho para despachar várias tarefas de uma lista sem abrir o seletor.

**D. Skill do jangada para os agentes.** O Omarchy entrega
`default/agents/skills/omarchy/SKILL.md`, que o agente carrega sempre que vai
mexer em `~/.config/hypr` ou no próprio Omarchy, com guias separados por
assunto (`hyprland.md`, `theming.md`, `hooks.md`). O jangada acumulou
pegadinhas que hoje só estão na memória do Claude desta máquina e no
`AGENTS.md`: `hyprctl dispatch` só aceita Lua, `-j` do `binds` é JSON
inválido, `+1` de monitor anda pelo id, hypridle ignora `-c`, on-click da
waybar não pode prender terminal, teste aninhado não toca no DRM. Uma skill
em `default/claude/skills/jangada/` (instalada como os hooks) deixa isso
disponível para qualquer agente aberto em qualquer projeto, inclusive o
Antigravity, e evita redescobrir a mesma coisa.

**E. Estado mais fiel pelos hooks.** O `default/claude/hooks.json` usa
`UserPromptSubmit`, `PostToolUse`, `Notification` e `Stop`. Faltam:

- `SessionEnd`, para marcar a sessão como encerrada quando o `claude` sai, em
  vez de depender de pid e tmux no `limpar_orfaos`;
- `SessionStart`, para registrar o id da conversa do Claude no JSON de estado
  (usado no item G);
- separar, no `Notification`, pedido de permissão de simples ociosidade: o
  ccmux distingue permissão, aprovação de plano e pergunta, e só o primeiro
  justifica notificação crítica. Conferir na documentação do Claude Code quais
  campos e filtros o evento traz na versão instalada antes de implementar.

### 3.2 Prioridade média

**F. Integrar e limpar num comando.** Hoje são dois passos: `concluir` (no
subshell) faz o merge e `jangada-agente-fim` remove o worktree e mantém o
ramo. workmux (`merge`) e worktrunk fazem merge, remoção do worktree,
fechamento da sessão e remoção do ramo de uma vez. Proposta:
`jangada-agente-fim --integrar`, que chama o mesmo código do `concluir` e só
apaga o ramo se o merge entrou.

**G. Recuperar as sessões depois de reiniciar.** O tmux `-L jangada` morre com
a máquina, e o JSON de estado já guarda diretório, ramo e agente. ccmanager e
agent-of-empires reabrem o que estava rodando. Proposta:
`jangada-agentes --restaurar`, que recria cada sessão viva no último registro
com `claude --resume <id>` (id gravado pelo `SessionStart`, item E) ou
`claude --continue` como alternativa.

**H. Perfis de agente.** `JANGADA_AGENTE` é uma string. workmux e
claude-squad aceitam perfis com nome, comando, argumentos e variáveis de
ambiente (por exemplo `CLAUDE_CONFIG_DIR` para separar contas). Proposta:
`~/.config/jangada/agentes/<perfil>.conf` e `jangada-agente --perfil NOME`,
com o seletor mostrando os perfis quando houver mais de um. Útil se o Codex ou
o Antigravity passarem a implementar, e não só revisar.

**I. Consumo na barra.** O Omarchy tem `omarchy-agent-usage-claude` e um
módulo de barra com cota e gasto por dia; o `ccusage`
([ccusage/ccusage](https://github.com/ccusage/ccusage), 18.661 estrelas) lê os
registros locais do Claude Code. Um tooltip no `custom/agentes` com o uso da
janela de 5 horas evita bater no limite no meio de um `jangada-par`.

**J. Diagnóstico entregue ao agente.** `omarchy-agent-crash` pega o que o
`systemd-coredump` registrou e abre o agente padrão com uma skill de
diagnóstico. No jangada as falhas mais caras foram de sessão que não sobe
(`AQ_DRM_DEVICES`, hypridle) e de pacote que quebra depois da atualização
(Noctalia, driver NVIDIA sem reiniciar). Proposta: `jangada-verificar
--agente`, que junta a saída do verificar, `hyprctl configerrors`, o último
`~/.cache/hyprland/hyprlandCrashReport*.txt` e o fim do `hyprland.log` num
prompt e abre um agente no repositório do jangada.

**K. Proteção durante a atualização.** O Omarchy suspende o recarregamento
automático do Hyprland enquanto o pacman roda
(`omarchy-hyprland-reload-guard`) e confere o log da atualização atrás de
falha do initramfs (`omarchy-update-analyze-logs`). O `jangada-update` já
avisa quando o kernel mudou; faltam o aviso de initramfs e a conferência de
versão do módulo NVIDIA carregado contra o pacote instalado, que foi a causa
do problema registrado no projeto de jogos.

**L. Ganchos do usuário.** `omarchy-hook` roda
`~/.config/omarchy/hooks/<nome>` e `<nome>.d/*` em pontos fixos
(`post-update`, `theme-set`). No jangada serviria para o que hoje é aviso
manual, como reaplicar o tema do SDDM depois do `jangada-tema`.

### 3.3 Não fazer, ou adiar

| Ideia | Onde aparece | Motivo para não fazer agora |
|---|---|---|
| Aprovação automática de permissões | claude-squad (`-y`), ccmanager (aprovação por IA) | Contraria a decisão de manter o revisor sem shell; o risco cai sobre projetos com dados que não estão no git |
| Agente coordenador que responde pelos outros | agent-deck ("conductor") | Mesmo motivo; e o `jangada-par` já cobre o ciclo que interessa |
| Acesso pelo celular, web ou Telegram | agent-of-empires, agent-deck, Lucarne | Abre porta de rede para algo que roda com as credenciais do usuário |
| Quadro kanban ou fila a partir de Linear e Jira | vibe-kanban, groundcrew | Não há fila de tickets no fluxo de trabalho; o vibe-kanban está sendo encerrado |
| Contêiner por agente | workmux, container-use, groundcrew, agent-of-empires | Custo alto (imagem com R, dados montados); só compensa se um dia o agente rodar sem pedir permissão. Se chegar a isso, `bubblewrap` resolve com menos peças que Docker |
| Navegador embutido | cmux, vibe-kanban | Fora do escopo de uma camada de área de trabalho |
| Reescrever o painel como TUI própria | todos os gerenciadores | O fzf com prévia do `capture-pane` já faz o essencial; o que falta são ações (itens B, F, G), não outra interface |
| Adotar workmux ou worktrunk como dependência | | Os dois são ativos, mas trazem a própria noção de estado e de sessão, que teria de conviver com a do jangada; copiar as ideias sai mais barato |

## 4. Melhorias de fluxo de trabalho no próprio repositório

1. **Teste aninhado automatizado.** O procedimento de subir o Hyprland dentro
   da sessão em uso, conferir `configerrors` e o número de atalhos está
   descrito em texto e é feito à mão. Um `testes/aninhado.sh` opcional (roda
   só com `WAYLAND_DISPLAY` presente) transforma a tabela de
   `PENDENCIAS.md` em verificação repetível e pega regressão de atalho antes
   de entrar na sessão real.
2. **Escrever o `jangada-importar`.** Continua pendente: o `jangada-mapear`
   gera o mapa e ninguém o lê. A importação manual de 19/09 é o roteiro.
3. **Pareceres com formato fixo.** Os arquivos em `revisao/` misturam
   avaliação, revisão e benchmark. Um cabeçalho comum (data, commit revisado,
   revisor, veredito) e um índice em `revisao/README.md` facilitam achar o que
   já foi decidido e por quê.
4. **Lançar ou focar.** `omarchy-launch-or-focus` foca a janela se ela já
   existe em vez de abrir outra. Aplicado ao `jangada-agentes --janela` e ao
   `jangada-shell --janela`, evita a lista duplicada esquecida no
   `special:rascunho`, que foi o que congelou a barra em 21/09.
5. **Canal de atualização.** O Omarchy tem canais (`omarchy-channel-set`). Com
   três cópias do repositório (trabalho, instalada, Drive), um ramo `estavel`
   que o `jangada-update` segue por padrão evita que a cópia instalada volte a
   ficar num ramo `agente/...`, como aconteceu em 21/09.

## 5. A barra em Quickshell

O plano era fazer a próxima barra em Quickshell com o painel de agentes. Com o
Noctalia fora do Quickshell, as opções são:

- **manter a waybar** e investir nos itens B, E e I, que dão ao módulo de
  agentes o que ele não tem hoje;
- **DankMaterialShell**, que roda em Hyprland, já usa matugen e tem sistema de
  plugins com versões travadas (`plugins.lock.json`): o painel de agentes
  seria um plugin, sem escrever a shell inteira;
- **Quickshell do zero**, como o Omarchy 4 fez.

Recomendação: manter a waybar por enquanto. O valor do jangada está no
contrato de estado dos agentes (`$JANGADA_ESTADO/agentes/*.json`), que
qualquer barra consegue ler. Se um dia a barra precisar mostrar a tela do
agente ou aceitar resposta, avaliar o plugin no DankMaterialShell antes de
escrever uma shell própria.

## 6. Ordem sugerida

1. A (`.worktreeinclude` e preparação do worktree)
2. D (skill do jangada)
3. B (pular para o agente que espera)
4. E (hooks `SessionStart` e `SessionEnd`), que prepara G
5. C (prompt na criação)
6. F e G (integrar num comando e restaurar depois de reiniciar)
7. Fluxo: teste aninhado e `jangada-importar`

## 7. Situação em 21/09/2026

| Item | Situação | Onde |
|---|---|---|
| A. Arquivos ignorados no worktree | feito | `bin/jangada-worktree-preparar` (`.worktreeinclude`, `.jangada/links`, `.jangada/preparar.sh`) |
| B. Pular para o agente que espera | feito | `jangada-agentes --proximo` (SUPER+N) e `--anterior` (SUPER+SHIFT+N) |
| C. Tarefa já com o prompt | feito | `jangada-agente --prompt` e `--prompt-arquivo`; o nome sai das primeiras palavras |
| D. Skill do jangada | feito | `default/claude/skills/jangada/` |
| E. Hooks mais fiéis | feito | `SessionStart`, `SessionEnd`, tipo da notificação e `conversa` no estado |
| F. Integrar e limpar num comando | feito | `jangada-agente-fim --integrar`; Alt+I no seletor |
| G. Restaurar depois de reiniciar | feito | estado `interrompido` e `jangada-agentes --restaurar` (`claude --resume`) |
| H. Perfis de agente | feito | `~/.config/jangada/agentes/NOME.conf` e `jangada-agente --perfil` |
| I. Consumo na barra | feito | `jangada-consumo`, no tooltip do módulo de agentes |
| J. Diagnóstico entregue ao agente | feito | `jangada-verificar --diagnostico` e `--agente`; entrada no menu |
| K. Proteção durante a atualização | feito em parte | `jangada-update` confere mkinitcpio, dkms e a versão da NVIDIA e avisa quando é preciso reiniciar. **Adiado:** suspender a recarga automática do Hyprland durante o pacman. O pacman não toca em `~/.config/jangada` nem em `default/` (que só muda por `git pull`), então não há recarga disparada no meio da transação; o problema do Omarchy vem de pacotes que escrevem na configuração do Hyprland, o que o jangada não faz |
| L. Ganchos do usuário | feito | `jangada-gancho`: `pos-tema`, `pos-agente-fim`, `pos-par`, `pos-update` |
| Par com avaliação | feito (fora da lista original) | o Claude avalia cada apontamento do agy antes de implementar |
| 4.1 Teste aninhado | feito | `testes/aninhado.sh` |
| 4.2 `jangada-importar` | feito | lê o niri (atual ou de um mapeamento) e grava arquivos `.importado` |
| 4.3 Pareceres com formato fixo | feito | `revisao/README.md` |
| 4.4 Lançar ou focar | feito | `jangada-agentes --janela` e `jangada-shell --janela` |
| 4.5 Canal de atualização | feito | `JANGADA_CANAL` (padrão `main`); ramo `estavel` criado no repositório |
| 5. Barra em Quickshell | adiado | a waybar continua; o contrato de estado vale para qualquer barra |
| 3.3 Não fazer | mantido | aprovação automática, coordenador, acesso remoto, kanban, contêiner, navegador |
