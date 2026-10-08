#!/usr/bin/env bash
# Testa o registro de provedores do jangada-config: os quatro do repositório,
# a precedência do arquivo do usuário e as recusas de arquivo inválido.
#
# Uso: testes/provedores.sh
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada"
usuario="$tmp/config/jangada/provedores"
mkdir -p "$usuario"
# shellcheck source=bin/jangada-config
source "$repo_jangada/bin/jangada-config"

lista() { jangada_provedores "$@" | paste -sd' '; }
campos() {
  jangada_provedor "$1" || return 1
  printf '%s|%s|%s|%s|%s|%s|%s' "$PROVEDOR_NOME" "$PROVEDOR_TIPO" "$PROVEDOR_COMANDO" \
    "$PROVEDOR_FUNCOES" "$PROVEDOR_PROTOCOLO_ARG" "$PROVEDOR_MODELO_REVISOR" "$PROVEDOR_RESERVA"
}

conferir "os quatro provedores do repositório" test "$(lista)" = "agy claude codex ollama"
conferir "sessão principal: claude e codex" test "$(lista principal)" = "claude codex"
conferir "revisão: agy, claude e codex" test "$(lista revisor)" = "agy claude codex"
conferir "delegação: agy e ollama" test "$(lista delegacao)" = "agy ollama"
conferir "claude reproduz o protocolo, o modelo e a reserva" \
  test "$(campos claude)" = "Claude|cli|claude|principal revisor|--append-system-prompt|sonnet|1"
conferir "agy" test "$(campos agy)" = "Antigravity|cli|agy|revisor delegacao|||2"
conferir "codex" test "$(campos codex)" = "Codex|cli|codex|principal revisor|||3"
conferir "ollama só é descrito, sem comando" test "$(campos ollama)" = "Ollama|ollama||delegacao|||"

if jangada_provedor nenhum; then falha "provedor ausente foi aceito"; else ok "provedor ausente é recusado"; fi
if jangada_provedor ../claude; then falha "nome com barra foi aceito"; else ok "nome com barra é recusado"; fi

printf 'TIPO=cli\nCOMANDO=outro\nFUNCOES=principal\nPROTOCOLO_ARG=--system\nSEGREDO=x\n' >"$usuario/novo.conf"
conferir "provedor do usuário entra na lista" test "$(lista principal)" = "claude codex novo"
conferir "sem NOME, vale o nome do arquivo, que também é o executável" test "$(campos novo)" = "novo|cli|novo|principal|--system||"
conferir "chave desconhecida não vira variável" test -z "${SEGREDO:-}"
conferir "nada do registro é exportado" \
  bash -c 'source "$1/bin/jangada-config"; jangada_provedor novo; ! env | grep -q "^PROVEDOR_\|^SEGREDO="' _ "$repo_jangada"

printf 'TIPO=cli\nFUNCOES=principal\nPROTOCOLO_ARG=--fim' >"$usuario/semfim.conf"
conferir "arquivo sem quebra de linha no fim é lido inteiro" test "$(campos semfim)" = "semfim|cli|semfim|principal|--fim||"
rm "$usuario/semfim.conf"

printf 'NOME=Outro\nTIPO=cli\nFUNCOES=revisor\n' >"$usuario/claude.conf"
conferir "arquivo do usuário tem precedência" test "$(campos claude)" = "Outro|cli|claude|revisor|||"
conferir "e muda a lista de principais" test "$(lista principal)" = "codex novo"
rm "$usuario/claude.conf"

recusa() {
  local d="$1"; shift
  printf '%s\n' "$@" >"$usuario/ruim.conf"
  if jangada_provedor ruim; then falha "$d foi aceito"; else ok "$d é recusado"; fi
  [[ " $(lista) " != *" ruim "* ]] || falha "$d aparece na lista"
}
recusa "tipo de API" TIPO=openai-compat FUNCOES=revisor
recusa "tipo ausente" FUNCOES=revisor
recusa "função desconhecida" TIPO=cli FUNCOES=supervisor
recusa "sem função" TIPO=cli
recusa "argumento de protocolo com comando embutido" TIPO=cli FUNCOES=principal 'PROTOCOLO_ARG=--a $(id)'
recusa "argumento de protocolo com espaço" TIPO=cli FUNCOES=principal 'PROTOCOLO_ARG=--a b'
recusa "reserva não numérica" TIPO=cli FUNCOES=revisor RESERVA=primeiro
recusa "modelo com espaço" TIPO=cli FUNCOES=revisor 'MODELO_REVISOR=a b'
rm "$usuario/ruim.conf"

printf '#!/bin/sh\n' >"$tmp/novo"; chmod +x "$tmp/novo"
PATH="$tmp:$PATH" "$repo_jangada/bin/jangada-agente" --capacidades-json >"$tmp/cap.json"
conferir "o catálogo de agentes principais vem do registro" \
  jq -e '[.principais[].nome] == ["claude", "codex", "novo"]
    and (.principais[] | select(.nome == "novo") | .instalado) == true' "$tmp/cap.json" >/dev/null

mkdir -p "$tmp/vazio"
if XDG_CONFIG_HOME="$tmp/vazio" JANGADA_PATH="$tmp/vazio" "$repo_jangada/bin/jangada-agente" --capacidades-json >"$tmp/vazio.out" 2>"$tmp/vazio.err"; then
  falha "registro vazio foi aceito pelo jangada-agente"
else
  ok "registro vazio faz o jangada-agente parar"
fi
conferir "e o erro diz onde o registro foi procurado" grep -q "default/provedores" "$tmp/vazio.err"
conferir "sem imprimir catálogo" test ! -s "$tmp/vazio.out"

if ((falhas)); then
  printf '\n%d falha(s)\n' "$falhas"
  exit 1
fi
printf '\ntudo certo\n'
