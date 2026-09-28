# shellcheck shell=sh
# Integração do jangada com bash e zsh. Carregado pelo arquivo de inicialização.
# Compatível com as duas shells; evita recursos exclusivos de uma delas.

# O bloco gravado pelo instalador define JANGADA_PATH antes de carregar este
# arquivo. Sem ele, o caminho é deduzido do próprio arquivo, e só depois disso
# vale o local padrão. Deduzir importa quando o repositório não está em
# ~/.local/share/jangada: sem isso, o PATH apontaria para uma pasta inexistente.
if [ -z "${JANGADA_PATH:-}" ]; then
  # shellcheck disable=SC3028  # BASH_SOURCE no bash, $0 no zsh, vazio nas demais
  _jangada_arquivo="${BASH_SOURCE:-$0}"
  [ -n "$ZSH_VERSION" ] && eval '_jangada_arquivo=${(%):-%x}'
  case "$_jangada_arquivo" in
    */shell/jangada.sh) JANGADA_PATH="${_jangada_arquivo%/shell/jangada.sh}" ;;
  esac
  unset _jangada_arquivo
fi
export JANGADA_PATH="${JANGADA_PATH:-$HOME/.local/share/jangada}"

case ":$PATH:" in
  *":$JANGADA_PATH/bin:"*) ;;
  *) export PATH="$JANGADA_PATH/bin:$PATH" ;;
esac

if [ -n "$ZSH_VERSION" ]; then
  _jangada_shell=zsh
elif [ -n "$BASH_VERSION" ]; then
  _jangada_shell=bash
else
  _jangada_shell=""
fi

# Só ativa ferramentas em shells interativas.
case $- in
  *i*)
    if [ -n "$_jangada_shell" ]; then
      command -v mise   >/dev/null 2>&1 && eval "$(mise activate "$_jangada_shell")"
      command -v zoxide >/dev/null 2>&1 && eval "$(zoxide init "$_jangada_shell")"
      command -v fzf    >/dev/null 2>&1 && eval "$(fzf --"$_jangada_shell" 2>/dev/null)"
    fi
    ;;
esac
unset _jangada_shell
