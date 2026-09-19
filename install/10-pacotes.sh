# shellcheck shell=bash
# Etapa 10: instala os pacotes das listas em install/pacotes/.
# snapshots.txt fica de fora; ele é tratado na etapa 20.

mapfile -t _pacotes < <(
  for _lista in base interface ferramentas; do
    ler_lista "$JANGADA_PATH/install/pacotes/$_lista.txt"
  done
)
instalar_pacotes "${_pacotes[@]}"
unset _pacotes _lista
