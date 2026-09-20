# shellcheck shell=bash
# Etapa 30: integra o jangada ao bash e ao zsh (PATH, mise, zoxide, fzf).
# Acrescenta um bloco delimitado ao arquivo de inicialização, uma única vez.

_marca="# >>> jangada >>>"
_fim="# <<< jangada <<<"
# O caminho do repositório é gravado no bloco porque a shell não tem como
# descobri-lo antes de carregar o arquivo.
_bloco="$_marca
export JANGADA_PATH=\"$JANGADA_PATH\"
[ -f \"\$JANGADA_PATH/shell/jangada.sh\" ] && . \"\$JANGADA_PATH/shell/jangada.sh\"
$_fim"

for _rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [[ -f "$_rc" ]] || continue
  if grep -qF "$_marca" "$_rc"; then
    if [[ "$(sed -n "/^$_marca\$/,/^$_fim\$/p" "$_rc")" == "$_bloco" ]]; then
      ok "já integrado: $_rc"
      continue
    fi
    # Bloco de uma versão anterior: substituído no mesmo lugar, sem duplicar.
    copia_seguranca "$_rc"
    if simulando; then
      info "[simulação] atualizaria o bloco jangada em $_rc"
    else
      _tmp="$(mktemp)"
      awk -v ini="$_marca" -v fim="$_fim" -v novo="$_bloco" '
        $0 == ini { dentro = 1; print novo; next }
        dentro && $0 == fim { dentro = 0; next }
        dentro { next }
        { print }
      ' "$_rc" >"$_tmp" && cat "$_tmp" >"$_rc"
      rm -f "$_tmp"
    fi
    ok "atualizado: $_rc"
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
unset _marca _fim _bloco _rc _tmp
