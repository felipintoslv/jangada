#!/usr/bin/env bash
# Testa o comando reverter do jangada shell, no bash e no zsh: antes de pedir
# confirmação ele mostra os commits, as alterações e os arquivos não
# rastreados que se perdem; ao confirmar, guarda o HEAD num ramo de cópia
# antes do reset; ao recusar, não muda nada. Confere também o cabeçalho de
# abertura do console (Jangada Core), com a logo e sem o arquivo dela.
#
# Uso: testes/reverter.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" GIT_CONFIG_NOSYSTEM=1
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export JANGADA_WORKTREES="$tmp/wt"
mkdir -p "$HOME" "$JANGADA_WORKTREES"

# Monta um repositório com main e um worktree gerenciado no ramo "tarefa",
# com dois commits, um arquivo alterado, um não rastreado e um ignorado.
preparar() {
  local repo="$tmp/$1-repo" wt="$JANGADA_WORKTREES/$1"
  git init -q -b main "$repo"
  printf 'base\n' >"$repo/a.txt"
  printf 'ignorado.txt\n' >"$repo/.gitignore"
  git -C "$repo" add -A && git -C "$repo" commit -qm base
  git -C "$repo" worktree add -q -b tarefa "$wt"
  printf 'um\n' >>"$wt/a.txt"; git -C "$wt" commit -qam "primeiro da tarefa"
  printf 'dois\n' >>"$wt/a.txt"; git -C "$wt" commit -qam "segundo da tarefa"
  printf 'sujo\n' >>"$wt/a.txt"
  mkdir -p "$wt/novo"; printf 'x\n' >"$wt/novo/b.txt"
  printf 'y\n' >"$wt/ignorado.txt"
  printf '%s\n' "$wt"
}

# Roda o reverter no shell dado, dentro do worktree, com a resposta na entrada.
reverter_em() {
  local sh="$1" wt="$2" resposta="$3"
  (cd "$wt" && printf '%s\n' "$resposta" |
    "$sh" -c '. "$1/jangada-shell.sh"; reverter' _ "$repo_jangada" 2>&1)
}

# Abre o console no shell dado, com a cópia do jangada em $2, e pede a ajuda.
console_em() {
  printf 'ajuda\n' | SHELL="$1" JANGADA_PATH="$2" "$repo_jangada/bin/jangada-shell" 2>&1
}

# Linhas da logo que saem com cor quando a saída do console é um terminal.
cores_no_terminal() {
  SHELL="$1" JANGADA_PATH="$repo_jangada" timeout 30 script -qec \
    "printf 'exit\n' | '$repo_jangada/bin/jangada-shell'" /dev/null </dev/null 2>&1 |
    sed '/Jangada Core: Console/q' | grep -c "$(printf '\033')\[[0-9]*m"
}

export -f cores_no_terminal
export repo_jangada

# Cópia do jangada sem o arquivo da logo.
mkdir -p "$tmp/semlogo"
ln -s "$repo_jangada/jangada-shell.sh" "$tmp/semlogo/jangada-shell.sh"

for sh in bash zsh; do
  if ! command -v "$sh" >/dev/null 2>&1; then
    ok "$sh ausente, pulado"
    continue
  fi

  saida="$(console_em "$sh" "$repo_jangada")"
  conferir "$sh: cabeçalho traz Jangada Core" \
    grep -qx "Jangada Core: Console de Agentes" <<<"$saida"
  conferir "$sh: ajuda traz Jangada Core" \
    grep -qx "Jangada Core: Comandos Disponíveis:" <<<"$saida"
  conferir "$sh: cabeçalho mostra a logo" grep -qF '| (*) \' <<<"$saida"
  # Só até a linha do nome: o prompt do zsh emite sequências de cor depois.
  logo="$(sed '/^Jangada Core: Console/q' <<<"$saida")"
  conferir "$sh: logo sai sem marcador nem cor fora do terminal" \
    bash -c '! grep -q -e "^\$[1-4]" -e "$(printf "\033")\[[0-9]*m" <<<"$1"' _ "$logo"
  conferir "$sh: nome antigo não aparece" bash -c '! grep -q "Jangada Shell" <<<"$1"' _ "$saida"
  if command -v script >/dev/null 2>&1; then
    conferir "$sh: no terminal, a logo sai com cor" \
      test "$(env -u NO_COLOR bash -c 'cores_no_terminal "$1"' _ "$sh")" -gt 0
    conferir "$sh: NO_COLOR definido, mesmo vazio, tira a cor" \
      test "$(NO_COLOR='' cores_no_terminal "$sh")" -eq 0
  else
    ok "$sh: script ausente, cor no terminal pulada"
  fi
  saida="$(console_em "$sh" "$tmp/semlogo")"
  conferir "$sh: sem o arquivo da logo, o console abre" \
    grep -qx "Jangada Core: Console de Agentes" <<<"$saida"
  conferir "$sh: sem o arquivo da logo, não desenha nada" \
    bash -c '! grep -qF "(*)" <<<"$1"' _ "$saida"

  # Recusa: mostra tudo e não muda nada.
  wt="$(preparar "$sh-n")"
  topo="$(git -C "$wt" rev-parse HEAD)"
  saida="$(reverter_em "$sh" "$wt" n)"
  conferir "$sh: lista os commits do ramo" grep -q "primeiro da tarefa" <<<"$saida"
  conferir "$sh: lista o segundo commit" grep -q "segundo da tarefa" <<<"$saida"
  conferir "$sh: lista a alteração não commitada" grep -q "M a.txt" <<<"$saida"
  conferir "$sh: lista o não rastreado" grep -q "novo/" <<<"$saida"
  conferir "$sh: não lista o ignorado" bash -c '! grep -q ignorado.txt <<<"$1"' _ "$saida"
  conferir "$sh: recusa mantém o HEAD" test "$(git -C "$wt" rev-parse HEAD)" = "$topo"
  conferir "$sh: recusa mantém o não rastreado" test -f "$wt/novo/b.txt"
  conferir "$sh: recusa não cria ramo de cópia" \
    test -z "$(git -C "$wt" branch --list 'backup/*')"

  # Confirmação: cópia no ramo, reset e clean.
  wt="$(preparar "$sh-s")"
  topo="$(git -C "$wt" rev-parse HEAD)"
  base="$(git -C "$wt" rev-parse main)"
  saida="$(reverter_em "$sh" "$wt" s)"
  copia="$(git -C "$wt" branch --list --format='%(refname:short)' 'backup/reverter-*')"
  conferir "$sh: cria o ramo de cópia" test -n "$copia"
  conferir "$sh: a cópia aponta para o HEAD anterior" \
    test "$(git -C "$wt" rev-parse "$copia" 2>/dev/null)" = "$topo"
  conferir "$sh: informa o nome da cópia" grep -qF "$copia" <<<"$saida"
  conferir "$sh: HEAD volta ao ponto inicial" test "$(git -C "$wt" rev-parse HEAD)" = "$base"
  conferir "$sh: apaga o não rastreado" test ! -e "$wt/novo"
  conferir "$sh: mantém o ignorado" test -f "$wt/ignorado.txt"
  conferir "$sh: descarta a alteração" test "$(cat "$wt/a.txt")" = base

  # Nada a reverter: não pergunta nem cria cópia.
  saida="$(reverter_em "$sh" "$wt" s)"
  conferir "$sh: sem nada a reverter, avisa" grep -q "nada a reverter" <<<"$saida"
  conferir "$sh: sem nada a reverter, não cria outra cópia" \
    test "$(git -C "$wt" branch --list 'backup/*' | wc -l)" -eq 1
done

if ((falhas)); then
  echo "reverter: $falhas falha(s)"
  exit 1
fi
echo "reverter: tudo certo"
