# shellcheck shell=bash
# Etapa 30: integra o jangada ao bash e ao zsh (PATH, mise, zoxide, fzf).
# Acrescenta um bloco delimitado ao arquivo de inicialização, uma única vez.

_marca="# >>> jangada >>>"
_bloco="$_marca
[ -f \"$JANGADA_PATH/shell/jangada.sh\" ] && . \"$JANGADA_PATH/shell/jangada.sh\"
# <<< jangada <<<"

for _rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [[ -f "$_rc" ]] || continue
  if grep -qF "$_marca" "$_rc"; then
    ok "já integrado: $_rc"
  else
    copia_seguranca "$_rc"
    if simulando; then
      info "[simulação] acrescentaria o bloco jangada em $_rc"
    else
      printf '\n%s\n' "$_bloco" >>"$_rc"
    fi
    ok "integrado: $_rc"
  fi
done
unset _marca _bloco _rc
