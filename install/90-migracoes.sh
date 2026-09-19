# shellcheck shell=bash
# Etapa 90: numa instalação nova, marca todas as migrações existentes como
# aplicadas, porque os padrões atuais já incorporam o que elas corrigiam.

executar mkdir -p "$JANGADA_ESTADO/migracoes"
for _m in "$JANGADA_PATH"/migrations/*.sh; do
  [[ -e "$_m" ]] || continue
  _marca="$JANGADA_ESTADO/migracoes/$(basename "$_m")"
  [[ -e "$_marca" ]] || executar touch "$_marca"
done
unset _m _marca
ok "migrações registradas"
