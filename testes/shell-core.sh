#!/usr/bin/env bash
# Testa a fronteira do jangada-shell.sh com o Core: os atalhos chamam o comando
# do Core pelo nome, via PATH, e sem o Core avisam e devolvem 127 sem quebrar a
# shell. O Core é representado por comandos falsos.
#
# Uso: testes/shell-core.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/com" "$tmp/sem"
for c in jangada-agente jangada-agentes jangada-agente-fim jangada-filtrar jangada-mapa jangada-isolar jangada-validar; do
  printf '#!/bin/sh\nprintf "%s %%s\\n" "$*"\n' "$c" >"$tmp/com/$c"
  chmod +x "$tmp/com/$c"
done
# PATH mínimo com o que a shell precisa; os comandos do Core ficam de fora.
for c in bash sh git env cat sed tr grep awk dirname basename mktemp rm; do
  alvo="$(command -v "$c")" && ln -sf "$alvo" "$tmp/sem/$c"
done

chamar() {
  local caminho="$1"; shift
  PATH="$caminho" JANGADA_PATH="$repo" bash -c '. "$1/jangada-shell.sh"; shift; "$@"' _ "$repo" "$@" 2>&1
}

saida="$(chamar "$tmp/com:$tmp/sem" agente --x)"
conferir "agente chama jangada-agente pelo nome" [ "$saida" = "jangada-agente --x" ]
saida="$(chamar "$tmp/com:$tmp/sem" status)"
conferir "status chama jangada-agentes --lista" [ "$saida" = "jangada-agentes --lista" ]
saida="$(chamar "$tmp/com:$tmp/sem" fim --integrar t)"
conferir "fim chama jangada-agente-fim" [ "$saida" = "jangada-agente-fim --integrar t" ]
saida="$(chamar "$tmp/com:$tmp/sem" revisar --revisor agy)"
conferir "revisar roda o jangada-validar dentro do jangada-isolar" [ "$saida" = "jangada-isolar -- $tmp/com/jangada-validar --revisor agy" ]

for atalho in agente agentes status fim revisar resumir mapa; do
  saida="$(chamar "$tmp/sem" "$atalho")"
  codigo=$?
  conferir "$atalho sem o Core avisa" grep -q 'não está instalado' <<<"$saida"
  conferir "$atalho sem o Core devolve 127" [ "$codigo" = 127 ]
done

((falhas == 0)) && echo "shell-core: tudo certo" || echo "shell-core: $falhas falha(s)"
exit $((falhas > 0))
