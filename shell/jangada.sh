# Integração do jangada com bash e zsh. Carregado pelo arquivo de inicialização.
# Compatível com as duas shells; evita recursos exclusivos de uma delas.

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
