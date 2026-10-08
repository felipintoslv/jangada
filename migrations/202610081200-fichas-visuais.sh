#!/usr/bin/env bash
# Instala a reserva sem regenerar os temas ou recarregar a sessão existente.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
copiar_se_ausente "$JANGADA_PATH/default/visual/padrao.json" "$JANGADA_CONFIG/fichas.json"
info "A próxima aplicação de jangada-tema gera as fichas do papel de parede."
