#!/usr/bin/env bash
# O jangada.sh passou da pasta shell/ para a raiz do repositório. O bloco que o
# install/30-shell.sh gravou em ~/.bashrc e ~/.zshrc ainda aponta para
# $JANGADA_PATH/shell/jangada.sh. Esta migração troca só esse bloco, entre as
# marcas "# >>> jangada >>>" e "# <<< jangada <<<", e deixa o resto do arquivo
# como está. Roda de novo sem efeito: bloco já novo não é tocado.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

_marca="# >>> jangada >>>"
_fim="# <<< jangada <<<"
_tmp=""
trap '[[ -z "$_tmp" ]] || rm -f "$_tmp"' EXIT

for _rc in "$HOME/.bashrc" "$HOME/.zshrc"; do
  [[ -f "$_rc" ]] || continue
  _bloco_atual="$(sed -n "/^$_marca\$/,/^$_fim\$/p" "$_rc")"
  if [[ "$_bloco_atual" != *'/shell/jangada.sh'* ]]; then
    ok "sem bloco antigo: $_rc"
    continue
  fi
  _novo="${_bloco_atual//\/shell\/jangada.sh//jangada.sh}"
  copia_seguranca "$_rc"
  if simulando; then
    info "[simulação] trocaria o bloco jangada em $_rc"
    continue
  fi
  _tmp="$(mktemp)"
  awk -v ini="$_marca" -v fim="$_fim" -v novo="$_novo" '
    $0 == ini { dentro = 1; print novo; next }
    dentro && $0 == fim { dentro = 0; next }
    dentro { next }
    { print }
  ' "$_rc" >"$_tmp"
  cat "$_tmp" >"$_rc"
  rm -f "$_tmp"
  _tmp=""
  ok "bloco atualizado: $_rc"
done
