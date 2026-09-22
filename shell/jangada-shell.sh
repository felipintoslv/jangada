# shellcheck shell=bash
# Funções e comandos injetados na sessão do jangada shell.
# Compatível com bash e zsh. Sem comandos perigosos, sem eval desprotegido.

# Garante que variáveis críticas existam
: "${JANGADA_PATH:=$HOME/.local/share/jangada}"
: "${JANGADA_PROJETOS:=$HOME/Projetos}"

# Pergunta de sim ou não que funciona nas duas shells. O "read -p" do bash pede
# um coprocesso no zsh, e "${resposta,,}" é erro de sintaxe lá, então a pergunta
# sai pelo printf e a resposta é comparada por padrão.
_jangada_confirmar() {
  local resposta=""
  printf '%s [s/N] ' "$1" >&2
  read -r resposta || return 1
  case "$resposta" in
    s*|S*) return 0 ;;
    *) return 1 ;;
  esac
}

# Ramo principal do repositório atual: o que o origin aponta, ou main, ou
# master. Devolve vazio quando nenhum dos três existe.
_jangada_ramo_base() {
  local base=""
  base="$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null || true)"
  base="${base#origin/}"
  if [ -n "$base" ] && git rev-parse --verify --quiet "$base" >/dev/null 2>&1; then
    printf '%s\n' "$base"
    return 0
  fi
  for base in main master; do
    if git rev-parse --verify --quiet "$base" >/dev/null 2>&1; then
      printf '%s\n' "$base"
      return 0
    fi
  done
  return 1
}

# Atalhos diretos para os comandos do jangada
agente() {
  "$JANGADA_PATH/bin/jangada-agente" "$@"
}

agentes() {
  "$JANGADA_PATH/bin/jangada-agentes" "$@"
}

status() {
  "$JANGADA_PATH/bin/jangada-agentes" --lista
}

fim() {
  "$JANGADA_PATH/bin/jangada-agente-fim" "$@"
}

audio() {
  "$JANGADA_PATH/bin/jangada-audio" "$@"
}

bluetooth() {
  "$JANGADA_PATH/bin/jangada-bluetooth" "$@"
}

rede() {
  "$JANGADA_PATH/bin/jangada-rede" "$@"
}

calendario() {
  "$JANGADA_PATH/bin/jangada-calendario" "$@"
}

# Revisão do diretório atual pelo outro modelo (jangada-validar): o agy
# revisa o Claude e o Claude revisa o agy. Fora de sessão, o revisor é o
# Claude; "revisar --revisor agy" troca.
revisar() {
  "$JANGADA_PATH/bin/jangada-validar" "$@"
}

# Mostra o que a tarefa mudou em relação ao ramo base.
#
# O nome não é "diff": um alias com esse nome sobrescreve o diff(1) do sistema
# dentro da subshell, e qualquer "diff a b" passaria a comparar outra coisa.
mudancas() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi
  local base
  base="$(_jangada_ramo_base || true)"
  if [ -z "$base" ]; then
    echo "nenhum ramo base (main/master); mostrando o que não está em commit" >&2
    git diff HEAD
    return
  fi
  if [ "$base" = "$(git rev-parse --abbrev-ref HEAD)" ]; then
    git diff HEAD
    return
  fi
  git diff "$base...HEAD"
}

# Integra a tarefa do worktree no ramo principal.
#
# O merge acontece no repositório principal, não aqui: o worktree da tarefa e o
# repositório principal são checkouts distintos do mesmo repositório, e um
# "git checkout main" dentro do worktree falha com "already used by worktree".
concluir() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi

  local ramo base principal ramo_principal pendentes commits
  ramo="$(git rev-parse --abbrev-ref HEAD)"
  if [ "$ramo" = "HEAD" ]; then
    echo "HEAD está solto (detached); troque para o ramo da tarefa antes de concluir." >&2
    return 1
  fi

  base="$(_jangada_ramo_base || true)"
  if [ -z "$base" ]; then
    echo "não encontrei um ramo principal (main ou master) neste repositório." >&2
    return 1
  fi

  if [ "$ramo" = "$base" ]; then
    echo "você já está no ramo principal ($base). Entre no worktree de uma tarefa para concluir."
    return 0
  fi

  # A primeira entrada de "git worktree list" é sempre o worktree principal.
  principal="$(git worktree list --porcelain | awk '/^worktree /{print substr($0, 10); exit}')"
  if [ -z "$principal" ] || [ ! -d "$principal" ]; then
    echo "não consegui localizar o repositório principal." >&2
    return 1
  fi

  pendentes="$(git status --porcelain)"
  if [ -n "$pendentes" ]; then
    echo "aviso: existem alterações não salvas no worktree:"
    printf '%s\n' "$pendentes" | head -10
    echo "faça commit das alterações antes de concluir."
    return 1
  fi

  commits="$(git log --oneline "$base..$ramo" 2>/dev/null || true)"
  if [ -z "$commits" ]; then
    echo "o ramo $ramo não tem nenhum commit além de $base; nada a integrar."
    return 0
  fi

  echo "Ramo da tarefa:  $ramo"
  echo "Integrar em:     $base ($principal)"
  echo ""
  echo "Commits a serem integrados:"
  printf '%s\n' "$commits"
  echo ""

  _jangada_confirmar "Mesclar '$ramo' em '$base'?" || { echo "operação cancelada."; return 0; }

  ramo_principal="$(git -C "$principal" rev-parse --abbrev-ref HEAD)"
  if [ "$ramo_principal" != "$base" ]; then
    echo "o repositório principal está em '$ramo_principal', não em '$base'." >&2
    echo "troque para $base lá e rode de novo." >&2
    return 1
  fi

  if ! git -C "$principal" merge --no-ff "$ramo"; then
    echo "ocorreram conflitos no merge; resolva-os em $principal." >&2
    return 1
  fi
  echo "merge realizado com sucesso em $principal."

  # O ramo só pode ser apagado depois que o worktree que o usa sumir; até lá o
  # git recusa com "checked out at". Quem remove o worktree é o jangada-agente-fim.
  echo "para remover o worktree e encerrar a sessão: fim <sessao> (ou Ctrl+X em 'agentes')"
}

# Seletor rápido de projetos com fzf
trocar() {
  if ! command -v fzf >/dev/null 2>&1; then
    echo "erro: fzf não encontrado no PATH" >&2
    return 1
  fi
  local d
  # A lista não depende de nenhum comando do jangada: antes ela só era montada
  # se "jangada-agente --ajuda" desse certo, e qualquer falha ali deixava o
  # seletor mudo, sem dizer por quê.
  d="$({
    command -v zoxide >/dev/null 2>&1 && zoxide query -l 2>/dev/null || true
    find "$JANGADA_PROJETOS" -mindepth 1 -maxdepth 1 -type d 2>/dev/null || true
    find "$JANGADA_PROJETOS" -maxdepth 3 -type d -name .git -prune -printf '%h\n' 2>/dev/null || true
  } | awk '!visto[$0]++' | fzf --prompt 'projeto > ' --height 50% --reverse)" || return 0

  if [[ -n "$d" && -d "$d" ]]; then
    cd -- "$d" || return 1
    echo "diretório: $PWD"
  fi
}

# Seletor e gerador de temas com matugen
tema() {
  if (($# == 0)); then
    "$JANGADA_PATH/bin/jangada-tema" --escolher
  else
    "$JANGADA_PATH/bin/jangada-tema" "$@"
  fi
}

# Gestão de energia, sessão e atalhos rápidos
energia() {
  "$JANGADA_PATH/bin/jangada-energia" "$@"
}

desligar() {
  if _jangada_confirmar "Deseja realmente desligar o computador?"; then
    systemctl poweroff
  fi
}

reiniciar() {
  if _jangada_confirmar "Deseja realmente reiniciar o computador?"; then
    systemctl reboot
  fi
}

suspender() {
  systemctl suspend
}

bloquear() {
  "$JANGADA_PATH/bin/jangada-bloquear" "$@"
}

sair() {
  if _jangada_confirmar "Deseja realmente sair da sessão?"; then
    hyprctl dispatch 'hl.dsp.exit()' 2>/dev/null || true
  fi
}

menu() {
  "$JANGADA_PATH/bin/jangada-menu" "$@"
}

sddm() {
  "$JANGADA_PATH/bin/jangada-sddm" "$@"
}

# Ajuda dos comandos do jangada shell
ajuda() {
  echo ""
  echo "⛵ Jangada Shell — Comandos Disponíveis:"
  echo ""
  echo "  agente            cria um agente (Claude ou agy) em worktree; o outro modelo revisa"
  echo "  revisar           manda o diff do diretório atual para o outro modelo revisar"
  echo "  status            lista as sessões de agentes ativas e seus estados"
  echo "  agentes           abre o seletor interativo de agentes ativos"
  echo "  mudancas          mostra as alterações feitas no ramo atual"
  echo "  concluir          integra a tarefa atual no ramo principal"
  echo "  trocar            muda rapidamente para outro projeto com fzf"
  echo "  tema [imagem]     escolhe ou aplica um papel de parede e recalcula as cores"
  echo "  audio [saida|ent] escolhe o dispositivo de áudio ativo (fones, microfone)"
  echo "  bluetooth         gerencia conexões de dispositivos Bluetooth"
  echo "  rede              gerencia conexões cabeada (Ethernet) e Wi-Fi"
  echo "  calendario        abre o calendário interativo com seus eventos"
  echo "  energia           gerencia perfis de consumo e estado de energia"
  echo "  bloquear          bloqueia a tela com hyprlock"
  echo "  suspender         suspende a máquina imediatamente"
  echo "  reiniciar         reinicia o computador (com confirmação)"
  echo "  desligar          desliga o computador (com confirmação)"
  echo "  sair              encerra a sessão do jangada (com confirmação)"
  echo "  sddm <ação>       tela de login: aplicar, restaurar, status ou testar"
  echo "  menu              abre o menu central do jangada (fuzzel)"
  echo "  fim <sessao>      encerra uma sessão de agente e limpa o worktree"
  echo "  ajuda             exibe esta lista de comandos"
  echo "  exit              sai do jangada shell e volta ao terminal normal"
  echo ""
}
