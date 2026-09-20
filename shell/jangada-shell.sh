# shellcheck shell=bash
# Funções e comandos injetados na sessão do jangada shell.
# Compatível com bash e zsh. Sem comandos perigosos, sem eval desprotegido.

# Garante que variáveis críticas existam
: "${JANGADA_PATH:=$HOME/.local/share/jangada}"
: "${JANGADA_PROJETOS:=$HOME/Projetos}"

# Atalhos diretos para os comandos do jangada
par() {
  "$JANGADA_PATH/bin/jangada-par" "$@"
}

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

# Auditoria com Antigravity no diretório atual
revisar() {
  if ! command -v agy >/dev/null 2>&1; then
    echo "erro: agy não encontrado no PATH" >&2
    return 1
  fi

  local diff_txt="" base_ref="HEAD"
  if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    # Tenta comparar com a branch base ou com HEAD~1
    local main_branch
    main_branch="$(git symbolic-ref refs/remotes/origin/HEAD 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo "main")"
    if git rev-parse --verify --quiet "$main_branch" >/dev/null 2>&1; then
      base_ref="$main_branch"
    fi
    diff_txt="$(git diff -- "$base_ref..HEAD" 2>/dev/null || git diff 2>/dev/null || true)"
  fi

  echo "==> Enviando código para auditoria com Antigravity..."
  local prompt_rev="Você é o auditor de qualidade e segurança do Jangada.
Analise os arquivos e as alterações recentes neste diretório.
Diferenças recentes (git diff):
$diff_txt

Avalie:
1. Segurança: Há injeção de comandos, credenciais expostas ou permissões perigosas?
2. Correção: Há erros lógicos, quebras de contrato ou casos de borda não tratados?
3. Boas práticas: O código está limpo, legível e seguindo as convenções?

Responda de forma concisa e estruturada com:
- STATUS: (APROVADO ou NECESSITA_AJUSTES)
- Resumo dos pontos fortes
- Lista numerada de eventuais problemas ou vulnerabilidades e como corrigi-los."

  agy -p "$prompt_rev" --effort high --add-dir .
}

# Exibe o diff da tarefa atual de forma segura
diff_tarefa() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi
  local base_branch="main"
  if ! git rev-parse --verify --quiet "$base_branch" >/dev/null 2>&1; then
    base_branch="$(git rev-parse --abbrev-ref HEAD)"
  fi
  git diff -- "$base_branch..HEAD"
}
alias diff="diff_tarefa"

# Finaliza a tarefa do worktree e mescla na branch principal com segurança
concluir() {
  if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "o diretório atual não é um repositório git" >&2
    return 1
  fi

  local raiz ramo
  raiz="$(git rev-parse --show-toplevel)"
  ramo="$(git rev-parse --abbrev-ref HEAD)"

  if [[ "$ramo" == "main" || "$ramo" == "master" ]]; then
    echo "você já está na branch principal ($ramo). Escolha o worktree de uma tarefa para concluir."
    return 0
  fi

  # Verifica se há alterações pendentes não salvas
  local pendentes
  pendentes="$(git status --porcelain)"
  if [[ -n "$pendentes" ]]; then
    echo "aviso: existem alterações não salvas no repositório:"
    printf '%s\n' "$pendentes" | head -10
    echo "faça commit das alterações antes de concluir."
    return 1
  fi

  echo "Ramo da tarefa: $ramo"
  echo "Repositório:    $raiz"
  echo ""
  echo "Commits a serem integrados:"
  git log --oneline "main..$ramo" 2>/dev/null || git log -3 --oneline

  local resposta
  read -r -p "Deseja mesclar '$ramo' na branch principal? [s/N] " resposta
  if [[ "${resposta,,}" != s* ]]; then
    echo "operação cancelada."
    return 0
  fi

  # Executa o merge de forma segura
  git checkout main
  if git merge --no-ff -- "$ramo"; then
    echo "merge realizado com sucesso."
    read -r -p "Deseja excluir o ramo '$ramo'? [s/N] " resposta
    if [[ "${resposta,,}" == s* ]]; then
      git branch -d -- "$ramo"
    fi
  else
    echo "ocorreram conflitos no merge; resolva-os manualmente."
  fi
}

# Seletor rápido de projetos com fzf
trocar() {
  local d
  # shellcheck disable=SC2154
  d="$("$JANGADA_PATH/bin/jangada-agente" --ajuda >/dev/null 2>&1 && {
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

# Ajuda dos comandos do jangada shell
ajuda() {
  echo ""
  echo "⛵ Jangada Shell — Comandos Disponíveis:"
  echo ""
  echo "  par \"tarefa\"      executa o ciclo completo (Claude cria, Antigravity revisa)"
  echo "  agente [nome]     inicia um agente Claude isolado em worktree"
  echo "  revisar           audita o código do diretório atual com Antigravity"
  echo "  status            lista as sessões de agentes ativas e seus estados"
  echo "  agentes           abre o seletor interativo de agentes ativos"
  echo "  diff              mostra as alterações feitas no ramo atual"
  echo "  concluir          mescla a tarefa atual na branch principal"
  echo "  trocar            muda rapidamente para outro projeto com fzf"
  echo "  tema [imagem]     escolhe ou aplica um papel de parede e recalcula as cores"
  echo "  fim <sessao>      encerra uma sessão de agente e limpa o worktree"
  echo "  ajuda             exibe esta lista de comandos"
  echo "  exit              sai do jangada shell e volta ao terminal normal"
  echo ""
}
