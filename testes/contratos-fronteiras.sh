#!/usr/bin/env bash
# Põe o teste do contrato K9 (testes/fronteiras.sh) no passo "contratos entre
# módulos" de testes/verificar.sh, que só roda testes/contratos-*.
exec "$(dirname "$0")/fronteiras.sh" "$@"
