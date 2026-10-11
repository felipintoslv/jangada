#!/usr/bin/env bash
# O vidro fosco passa a ser padrão. Só fundos dos modelos antigos intactos
# recebem alpha; arquivos pessoais e cores não são regenerados.
set -euo pipefail
JANGADA_PATH="${JANGADA_PATH:-$HOME/.local/share/jangada}"
# shellcheck source=install/lib.sh
source "$JANGADA_PATH/install/lib.sh"
copiar_se_ausente "$JANGADA_PATH/config/jangada.conf" "$JANGADA_CONFIG/jangada.conf"
executar "$JANGADA_PATH/bin/jangada-vidro" --migrar
