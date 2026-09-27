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

# Revisão do diretório atual pelo outro modelo (jangada-validar): o agy
# revisa o Claude e o Claude revisa o agy. Fora de sessão, o revisor é o
# Claude; "revisar --revisor agy" troca.
revisar() {
  # O revisor e o .jangada/validar.sh do projeto rodam isolados, como o agente.
  "$JANGADA_PATH/bin/jangada-isolar" -- "$JANGADA_PATH/bin/jangada-validar" "$@"
}

# Filtra comandos de terminal longos para economizar tokens do contexto
resumir() {
  "$JANGADA_PATH/bin/jangada-filtrar" "$@"
}

# Gera o mapa estrutural e assinaturas do repositório
mapa() {
  "$JANGADA_PATH/bin/jangada-mapa" "$@"
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

# Identifica a sessão de agente ativa no diretório atual.
# Lê a variável JANGADA_SESSAO ou localiza o arquivo de estado cujo worktree
# coincida com o diretório raiz do repositório atual.
_jangada_sessao_atual() {
  if [ -n "${JANGADA_SESSAO:-}" ]; then
    printf '%s\n' "$JANGADA_SESSAO"
    return 0
  fi
  local estado_dir="${JANGADA_ESTADO:-${XDG_STATE_HOME:-$HOME/.local/state}/jangada}/agentes"
  local toplevel
  toplevel="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  if [ -n "$toplevel" ] && [ -d "$estado_dir" ]; then
    local arqs arq
    arqs="$(find "$estado_dir" -maxdepth 1 -name '*.json' 2>/dev/null || true)"
    if [ -n "$arqs" ]; then
      while IFS= read -r arq; do
        [ -f "$arq" ] || continue
        if [ "$(jq -r '.worktree // empty' "$arq" 2>/dev/null)" = "$toplevel" ]; then
          basename "$arq" .json
          return 0
        fi
      done <<<"$arqs"
    fi
  fi
  return 1
}

# Integra a tarefa do worktree no ramo principal e encerra a sessão.
# Delega para jangada-agente-fim --integrar quando houver sessão associada.
concluir() {
  local sessao
  sessao="$(_jangada_sessao_atual || true)"
  if [ -n "$sessao" ]; then
    "$JANGADA_PATH/bin/jangada-agente-fim" --integrar "$sessao"
    return $?
  fi

  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi

  local ramo base
  ramo="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  base="$(_jangada_ramo_base || true)"
  if [ -n "$base" ] && [ "$ramo" = "$base" ]; then
    echo "você já está no ramo principal ($base). Entre no worktree de uma tarefa para concluir."
    return 0
  fi

  echo "nenhuma sessão de agente identificada no diretório atual." >&2
  echo "para integrar uma sessão pelo nome: fim --integrar <sessao>" >&2
  return 1
}

# Cancela a tarefa da sessão atual e remove o worktree sem mesclar alterações.
desistir() {
  local sessao
  sessao="$(_jangada_sessao_atual || true)"
  if [ -z "$sessao" ]; then
    echo "nenhuma sessão de agente identificada no diretório atual." >&2
    echo "para encerrar uma sessão específica: fim <sessao>" >&2
    return 1
  fi
  "$JANGADA_PATH/bin/jangada-agente-fim" "$sessao"
}

# Reverte o worktree para o ponto inicial da tarefa após confirmação
reverter() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi
  local base ponto ramo_atual dir_atual wt_padrao
  base="$(_jangada_ramo_base || true)"
  ramo_atual="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || true)"
  dir_atual="$(git rev-parse --show-toplevel 2>/dev/null || true)"
  wt_padrao="${JANGADA_WORKTREES:-$HOME/.local/share/jangada-worktrees}"

  if [ -n "$base" ] && [ "$ramo_atual" = "$base" ]; then
    echo "reverter cancelado: não é permitido reverter o ramo base ($ramo_atual)" >&2
    return 1
  fi
  if [ "$ramo_atual" = "main" ] || [ "$ramo_atual" = "master" ]; then
    echo "reverter cancelado: não é permitido reverter o ramo principal ($ramo_atual)" >&2
    return 1
  fi
  if [ "${dir_atual#"$wt_padrao"/}" = "$dir_atual" ]; then
    echo "reverter cancelado: o diretório atual não é um worktree gerenciado ($dir_atual)" >&2
    return 1
  fi
  if [ -n "$base" ]; then
    ponto="$(git merge-base "$base" HEAD 2>/dev/null || true)"
  fi
  ponto="${ponto:-HEAD}"

  if _jangada_confirmar "Deseja reverter todas as alterações deste worktree para o ponto inicial ($ponto)?"; then
    git reset --hard "$ponto"
    git clean -fd
    echo "worktree revertido para o ponto inicial limpo ($ponto)."
  fi
}

# Repassa o contexto e parecer de validação de uma sessão para outra
repassar() {
  local sessao_origem="${1:-}"
  local agente_destino="${2:-}"
  local estado_dir="${JANGADA_ESTADO:-${XDG_STATE_HOME:-$HOME/.local/state}/jangada}/agentes"

  if [ -z "$sessao_origem" ]; then
    sessao_origem="$(_jangada_sessao_atual || true)"
  fi

  if [ -z "$sessao_origem" ] && command -v fzf >/dev/null 2>&1; then
    sessao_origem="$("$JANGADA_PATH/bin/jangada-agentes" --lista 2>/dev/null | awk -F'\t' '{print $2}' | fzf --prompt 'repassar da sessão > ' --height 40% --reverse)" || return 0
  fi

  if [ -z "$sessao_origem" ]; then
    echo "informe a sessão de origem: repassar <sessao_origem> [perfil_destino]" >&2
    return 1
  fi

  local ultimo_parecer=""
  local arqs_val
  arqs_val="$(find "$estado_dir" -name "validacao-${sessao_origem}-r*.md" 2>/dev/null || true)"
  if [ -n "$arqs_val" ]; then
    ultimo_parecer="$(printf '%s\n' "$arqs_val" | sort -V | tail -n1)"
  fi

  local tmp_prompt
  tmp_prompt="$(mktemp "${TMPDIR:-/tmp}/jangada-repassar.XXXXXX")"
  {
    echo "Contexto repassado da sessão '$sessao_origem':"
    echo ""
    if [ -n "$ultimo_parecer" ] && [ -f "$ultimo_parecer" ]; then
      echo "## Parecer da última validação:"
      cat "$ultimo_parecer"
      echo ""
    fi
    local arq_estado="$estado_dir/$sessao_origem.json"
    if [ -f "$arq_estado" ]; then
      local tarefa
      tarefa="$(jq -r '.tarefa // empty' "$arq_estado" 2>/dev/null || true)"
      if [ -n "$tarefa" ]; then
        echo "## Tarefa original:"
        echo "$tarefa"
        echo ""
      fi
    fi
  } >"$tmp_prompt"

  if [ -n "$agente_destino" ]; then
    echo "abrindo nova tarefa para o agente '$agente_destino' com o contexto repassado..."
    "$JANGADA_PATH/bin/jangada-agente" --perfil "$agente_destino" --prompt-arquivo "$tmp_prompt"
    rm -f "$tmp_prompt"
  else
    echo "contexto preparado a partir de '$sessao_origem':"
    cat "$tmp_prompt"
    echo ""
    echo "para iniciar uma sessão com este contexto: repassar $sessao_origem <perfil_agente>"
    rm -f "$tmp_prompt"
  fi
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

# Ajuda dos comandos do jangada shell
ajuda() {
  echo ""
  echo "⛵ Jangada Shell: Comandos Disponíveis:"
  echo ""
  echo "  agente            cria um agente (Claude ou agy) em worktree; o outro modelo revisa"
  echo "  revisar           manda o diff do diretório atual para o outro modelo revisar"
  echo "  resumir <cmd>     executa comando condensando saídas longas de testes e linters"
  echo "  mapa [pasta]      extrai o mapa estrutural e assinaturas do repositório"
  echo "  repassar [orig]   transfere o contexto e parecer de uma sessão para outra"
  echo "  status            lista as sessões de agentes ativas e seus estados"
  echo "  agentes           abre o seletor interativo de agentes ativos"
  echo "  mudancas          mostra as alterações feitas no ramo atual"
  echo "  concluir          integra a tarefa da sessão no ramo principal e a encerra"
  echo "  desistir          cancela a tarefa da sessão e remove o worktree sem mesclar"
  echo "  reverter          restaura o worktree para o ponto limpo inicial da tarefa"
  echo "  trocar            muda rapidamente para outro projeto com fzf"
  echo "  fim <sessao>      encerra uma sessão de agente e limpa o worktree"
  echo "  ajuda             exibe esta lista de comandos"
  echo "  exit              sai do jangada shell e volta ao terminal normal"
  echo ""
  echo "Nota: Comandos de hardware e sessão ficam na barra (Waybar) e no menu central (SUPER+ESC)."
  echo ""
}
