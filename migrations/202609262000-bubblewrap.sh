#!/usr/bin/env bash
# Migração de 26/09/2026: bubblewrap para isolar os agentes.
#
# O jangada-agente passou a abrir o agente pelo jangada-isolar, que usa o
# bwrap, e o pacote entrou em install/pacotes/ferramentas.txt. Instalações
# anteriores não rodam a etapa 10 de novo; esta migração instala o pacote. Sem
# ele, o agente roda sem isolamento e com aviso.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

instalar_pacotes bubblewrap
