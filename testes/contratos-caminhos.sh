#!/usr/bin/env bash
# Testa o contrato K2 (docs/modularizacao-3.0/03-contratos.md): cada caminho de
# testes/contratos/caminhos.txt existe, como arquivo ou como link, e nenhum
# link no caminho é absoluto nem leva para fora do repositório.
#
# Uso: testes/contratos-caminhos.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
lista="$repo_jangada/testes/contratos/caminhos.txt"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

caminhos() { grep -v -e '^#' -e '^$' "$lista"; }

# Um problema por linha; sem saída, a árvore de RAIZ cumpre o contrato.
problemas() {
  local raiz="$1" real caminho parcial parte
  real="$(realpath "$raiz")"
  while IFS= read -r caminho; do
    if [[ ! -e "$raiz/$caminho" ]]; then
      echo "ausente: $caminho"
      continue
    fi
    parcial="$raiz"
    while IFS= read -r parte; do
      parcial+="/$parte"
      [[ -L "$parcial" && "$(readlink "$parcial")" == /* ]] && echo "link absoluto: ${parcial#"$raiz"/}"
    done < <(tr '/' '\n' <<<"$caminho")
    [[ "$(realpath "$raiz/$caminho")" == "$real"/* ]] || echo "link para fora do repositório: $caminho"
  done < <(caminhos)
}

conferir "lista de caminhos sem linha repetida" [ -z "$(caminhos | sort | uniq -d)" ]
achados="$(problemas "$repo_jangada")"
conferir "todo caminho da lista existe e fica dentro do repositório" [ -z "$achados" ]
[[ -n "$achados" ]] && printf '      %s\n' "$achados"

# A configuração do usuário carrega os módulos por require("default.hypr.*").
faltam=""
for m in $(grep -ho 'require("default\.hypr\.[a-z_]*")' config/hypr/*.lua default/hypr/*.lua | sed 's/.*hypr\.//; s/")//' | sort -u); do
  caminhos | grep -qxF "default/hypr/$m.lua" || faltam+=" $m"
done
conferir "todo módulo de require(\"default.hypr.*\") está na lista:$faltam" [ -z "$faltam" ]

# O teste precisa falhar quando um caminho some ou sai do repositório: prova
# em cópias que só têm os caminhos da lista.
copia() {
  rm -rf "$tmp/copia" "$tmp/fora"
  mkdir "$tmp/copia" "$tmp/fora"
  caminhos | xargs -d '\n' cp -a --parents -t "$tmp/copia"
  # Caminho da lista que é link precisa do destino na cópia para existir.
  caminhos | while IFS= read -r c; do [[ -L "$c" ]] && realpath --relative-to=. "$c"; done |
    xargs -r -d '\n' cp -a --parents -t "$tmp/copia"
}
copia
conferir "cópia intacta dos caminhos passa" [ -z "$(problemas "$tmp/copia")" ]
rm "$tmp/copia/default/waybar/base.css"
conferir "caminho removido é apontado como ausente" \
  grep -qxF "ausente: default/waybar/base.css" <<<"$(problemas "$tmp/copia")"
copia
mkdir -p "$tmp/copia/shell/integracoes"
mv "$tmp/copia/shell/jangada.sh" "$tmp/copia/shell/integracoes/jangada.sh"
ln -s integracoes/jangada.sh "$tmp/copia/shell/jangada.sh"
conferir "link relativo para dentro do repositório passa" [ -z "$(problemas "$tmp/copia")" ]
ln -sfn "$tmp/copia/shell/integracoes/jangada.sh" "$tmp/copia/shell/jangada.sh"
conferir "link absoluto é apontado" \
  grep -qxF "link absoluto: shell/jangada.sh" <<<"$(problemas "$tmp/copia")"
copia
mv "$tmp/copia/default/claude/agents" "$tmp/fora/agents"
ln -s ../../../fora/agents "$tmp/copia/default/claude/agents"
conferir "link para fora do repositório é apontado" \
  grep -qxF "link para fora do repositório: default/claude/agents" <<<"$(problemas "$tmp/copia")"

((falhas == 0)) && echo "tudo certo" || echo "$falhas falha(s)"
exit $((falhas > 0))
