#!/usr/bin/env bash
# Testa a migração 202610162000-barra-comandos-do-core: o botão de update ganha
# a linha nova, os comandos que saíram do Shell perdem o prefixo
# $JANGADA_PATH/bin, o resto do arquivo fica idêntico, a segunda execução e a
# simulação não mudam nada, e uma linha de update alterada pelo usuário gera
# aviso e fica intacta.
#
# Uso: testes/barra-comandos-core.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

mkdir -p "$HOME/.cache"
tmp="$(mktemp -d "$HOME/.cache/teste-barra.XXXX")"
trap 'rm -rf "$tmp"' EXIT
mig="$repo/migrations/202610162000-barra-comandos-do-core.sh"
real="$HOME/.config/jangada/waybar/config.jsonc"
antiga='    "on-click": "setsid -f sh -c '"'"'\"$1\"/bin/jangada-terminal --titulo \"jangada update\" -e \"$1\"/bin/jangada-update; pkill -RTMIN+8 -x waybar'"'"' _ \"$JANGADA_PATH\"",'
nova='    "on-click": "setsid -f sh -c '"'"'cmd=\"$(command -v jangada-update)\" || cmd=\"$1\"/bin/jangada-sistema-update; \"$1\"/bin/jangada-terminal --titulo \"jangada update\" -e \"$cmd\"; pkill -RTMIN+8 -x waybar'"'"' _ \"$JANGADA_PATH\"",'

entrada="$tmp/entrada.jsonc"
if [[ -f "$real" ]] && grep -qxF "$antiga" "$real"; then
  cp "$real" "$entrada"
else
  cat >"$entrada" <<AMOSTRA
{
  "modules-left": ["custom/menu", "custom/indicadores", "custom/proprio"],
  // módulo próprio do usuário
  "custom/proprio": {
    "exec": "$HOME/bin/proprio",
    "on-click": "$HOME/bin/proprio --abrir"
  },
  "custom/indicadores": {
    "exec": "\$JANGADA_PATH/bin/jangada-painel --waybar",
    "on-click": "setsid -f \$JANGADA_PATH/bin/jangada-painel",
    "on-click-right": "\$JANGADA_PATH/bin/jangada-painel --parar"
  },
  "custom/menu": {
    "on-click": "setsid -f \$JANGADA_PATH/bin/jangada-menu"
  },
  "custom/atualizacoes": {
$antiga
    "on-click-right": "setsid -f \$JANGADA_PATH/bin/jangada-atualizacoes"
  }
}
AMOSTRA
fi

rodar() { # arquivo [simular]
  local cfg="$tmp/cfg"
  rm -rf "$cfg"; mkdir -p "$cfg/jangada/waybar"
  cp "$1" "$cfg/jangada/waybar/config.jsonc"
  XDG_CONFIG_HOME="$cfg" JANGADA_PATH="$repo" JANGADA_SIMULAR="${2:-0}" bash "$mig" >"$tmp/saida" 2>"$tmp/erro"
  cp "$cfg/jangada/waybar/config.jsonc" "$tmp/resultado.jsonc"
}
arq() { printf '%s' "$tmp/cfg/jangada/waybar/config.jsonc"; }

# Casos 1 a 3: migração sobre a cópia do usuário.
rodar "$entrada"
conferir "caso 1: botão de update com a linha nova" grep -qxF "$nova" "$tmp/resultado.jsonc"
conferir "caso 1: linha antiga sumiu" bash -c '! grep -qxF "$1" "$2"' _ "$antiga" "$tmp/resultado.jsonc"
conferir "caso 2: sem \$JANGADA_PATH/bin/jangada-painel" bash -c '! grep -qF "\$JANGADA_PATH/bin/jangada-painel" "$1"' _ "$tmp/resultado.jsonc"
conferir "caso 2: sem /bin/jangada-update" bash -c '! grep -qF "/bin/jangada-update" "$1"' _ "$tmp/resultado.jsonc"
trocadas="$(diff "$entrada" "$tmp/resultado.jsonc" | grep -c '^>')"
# Cada linha com painel conta uma vez, mais a linha do botão de update.
esperadas="$(grep -cE '\$JANGADA_PATH/bin/jangada-(painel|agentes)' "$entrada")"
esperadas=$((esperadas + 1))
conferir "caso 3: diff só tem as $esperadas linhas trocadas (achou $trocadas)" test "$trocadas" -eq "$esperadas"
printf '      linhas trocadas na cópia testada: %s\n' "$trocadas"
conferir "caso 3: comando do Shell (jangada-menu) intacto" \
  bash -c 'a=$(grep -cF "\$JANGADA_PATH/bin/jangada-menu" "$1"); b=$(grep -cF "\$JANGADA_PATH/bin/jangada-menu" "$2"); [[ $a == $b ]]' _ "$entrada" "$tmp/resultado.jsonc"
conferir "caso 3: módulo próprio (proprio) intacto" \
  bash -c '[[ "$(grep -F proprio "$1")" == "$(grep -F proprio "$2")" ]]' _ "$entrada" "$tmp/resultado.jsonc"
conferir "caso 3: cópia de segurança criada" bash -c 'ls "$1"/*.bak >/dev/null 2>&1' _ "$tmp/cfg/jangada/waybar"

# Caso 4: segunda execução não muda nada.
cp "$tmp/resultado.jsonc" "$tmp/primeira.jsonc"
rodar "$tmp/primeira.jsonc"
conferir "caso 4: segunda execução idêntica" diff -q "$tmp/primeira.jsonc" "$tmp/resultado.jsonc"
conferir "caso 4: sem nova cópia de segurança" bash -c '[[ -z "$(ls "$1"/*.bak 2>/dev/null)" ]]' _ "$tmp/cfg/jangada/waybar"

# Caso 5: simulação não grava.
rodar "$entrada" 1
conferir "caso 5: simulação deixa o arquivo igual" diff -q "$entrada" "$tmp/resultado.jsonc"
conferir "caso 5: simulação não cria cópia" bash -c '[[ -z "$(ls "$1"/*.bak 2>/dev/null)" ]]' _ "$tmp/cfg/jangada/waybar"

# Caso 6: linha de update alterada pelo usuário gera aviso e fica intacta.
{
  sed 's|^    "on-click": "setsid -f sh -c .*jangada update.*$|    "on-click": "setsid -f \\"$1\\"/bin/jangada-update --meu-jeito",|' "$entrada"
} >"$tmp/alterada.jsonc"
rodar "$tmp/alterada.jsonc"
conferir "caso 6: aviso sobre a linha de update" grep -q 'jangada-update' "$tmp/erro"
conferir "caso 6: linha alterada intacta" grep -qF -- '--meu-jeito' "$tmp/resultado.jsonc"
conferir "caso 6: linha nova não entrou" bash -c '! grep -qxF "$1" "$2"' _ "$nova" "$tmp/resultado.jsonc"

# Caso 7: sem arquivo do usuário.
rm -rf "$tmp/cfg"
XDG_CONFIG_HOME="$tmp/cfg" JANGADA_PATH="$repo" bash "$mig" >/dev/null 2>&1
conferir "caso 7: sem arquivo, sai sem erro" test "$?" -eq 0

if ((falhas)); then printf '\n%d falha(s)\n' "$falhas"; exit 1; fi
printf '\ntudo certo\n'
