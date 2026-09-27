#!/usr/bin/env bash
# Migração de 26/09/2026: gitleaks para o jangada-validar.
#
# A verificação local do jangada-validar passou a procurar segredos com o
# gitleaks nas linhas que a entrega acrescenta, e o pacote entrou em
# install/pacotes/ferramentas.txt. Instalações anteriores não rodam a etapa 10
# de novo; esta migração instala o pacote. Sem ele, o jangada-validar só avisa.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

instalar_pacotes gitleaks
