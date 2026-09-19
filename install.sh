#!/usr/bin/env bash
# Instalação do jangada. Executa as etapas de install/ em ordem numérica.
#
# Uso:
#   ./install.sh                  instala tudo
#   ./install.sh 20 50            executa só as etapas que começam com 20 e 50
#   JANGADA_SIMULAR=1 ./install.sh   mostra o que seria feito, sem executar
set -euo pipefail

JANGADA_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export JANGADA_PATH
# shellcheck source=install/lib.sh
source "$JANGADA_PATH/install/lib.sh"

[[ $EUID -ne 0 ]] || morrer "execute como usuário comum; o script pede sudo quando precisa"

simulando && aviso "modo simulação: nenhum comando será executado"

etapas=("$JANGADA_PATH"/install/[0-9][0-9]-*.sh)

deve_rodar() {
  local nome="$1" filtro
  (($# > 1)) || return 0
  shift
  for filtro in "$@"; do
    [[ "$nome" == "$filtro"-* ]] && return 0
  done
  return 1
}

for etapa in "${etapas[@]}"; do
  nome="$(basename "$etapa")"
  deve_rodar "$nome" "$@" || continue
  info "etapa $nome"
  # shellcheck disable=SC1090
  source "$etapa"
done

ok "instalação concluída"
info "rode jangada-verificar e depois escolha a sessão 'jangada' no gerenciador de login"
