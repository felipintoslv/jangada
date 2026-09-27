#!/usr/bin/env bash
# Testa o jangada-agente-fim e o jangada-agentes --limpar-concluidos com estado
# adulterado: o arquivo SESSAO.json é gravável pelo agente isolado, então pid,
# ramo, worktree, raiz, base e estado vindos dele não podem levar a operação
# destrutiva fora da sessão. O tmux é falso: lista as sessões de um arquivo e
# registra o kill-session.
#
# Uso: testes/fim.sh
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
vitima=""
trap '[[ -n "$vitima" ]] && kill "$vitima" 2>/dev/null; rm -rf "$tmp"' EXIT

export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_NOSYSTEM=1
: >"$GIT_CONFIG_GLOBAL"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/home/.config" XDG_STATE_HOME="$tmp/home/.local/state"
export JANGADA_PATH="$repo_jangada"
unset HYPRLAND_INSTANCE_SIGNATURE JANGADA_SESSAO JANGADA_REPO JANGADA_SIMULAR JANGADA_WORKTREES
estado="$XDG_STATE_HOME/jangada/agentes"
wts="$HOME/.local/share/jangada-worktrees"
mkdir -p "$estado" "$wts" "$tmp/bin"

export FALSO_DIR="$tmp"
: >"$tmp/sessoes"
cat >"$tmp/bin/tmux" <<'EOF'
#!/usr/bin/env bash
case " $* " in
  *" list-sessions "*) cat "$FALSO_DIR/sessoes" ;;
  *" has-session "*) s="${*: -1}"; grep -qxF "${s#=}" "$FALSO_DIR/sessoes" ;;
  *" kill-session "*) printf '%s\n' "${*: -1}" >>"$FALSO_DIR/mortas" ;;
esac
EOF
chmod +x "$tmp/bin/tmux"
export PATH="$tmp/bin:$PATH"

# Repositório do projeto e um segundo repositório, alvo do agente.
proj="$tmp/proj"; outro="$tmp/outro"
for r in "$proj" "$outro"; do
  git init --quiet -b main "$r"
  echo a >"$r/a"; git -C "$r" add a; git -C "$r" commit --quiet -m inicio
done
git -C "$outro" branch agente/x

gravar() { # sessão e campos em JSON
  printf '%s\n' "$2" >"$estado/$1.json"
}
fim() { "$repo_jangada/bin/jangada-agente-fim" "$@" </dev/null >"$tmp/saida" 2>&1; rc=$?; }
novo_worktree() { # repositório, nome
  git -C "$1" worktree add --quiet -b "agente/$2" "$wts/$(basename "$1")/$2" main
}
recusado() { # descrição, sessão
  conferir "$1: recusado ($rc)" test "$rc" -ne 0
  conferir "$1: explica" grep -q 'estado inválido' "$tmp/saida"
  conferir "$1: estado mantido" test -f "$estado/$2.json"
  conferir "$1: tmux intocado" test ! -s "$tmp/mortas"
}

echo "== pid do estado"
sleep 300 & vitima=$!
gravar p "{\"raiz\": \"$proj\", \"estado\": \"trabalhando\", \"pid\": $vitima}"
fim p
conferir "sessão direta encerra ($rc)" test "$rc" -eq 0
conferir "o pid gravado não é morto" kill -0 "$vitima"
: >"$tmp/mortas"

echo "== ramo inválido"
novo_worktree "$proj" r1
gravar r1 "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/r1\", \"ramo\": \"main\", \"base\": \"main\"}"
fim r1
recusado "ramo main" r1
conferir "ramo main: worktree mantido" test -d "$wts/proj/r1"

echo "== worktree fora de JANGADA_WORKTREES"
git -C "$proj" worktree add --quiet -b agente/f "$tmp/fora/proj/f" main
gravar f "{\"raiz\": \"$proj\", \"worktree\": \"$tmp/fora/proj/f\", \"ramo\": \"agente/f\", \"base\": \"main\"}"
fim f
recusado "worktree fora" f
conferir "worktree fora: mantido" test -d "$tmp/fora/proj/f"

gravar d "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/../../x/r1\", \"ramo\": \"agente/r1\", \"base\": \"main\"}"
fim d
recusado "worktree com .." d

echo "== worktree por link simbólico"
mkdir -p "$tmp/alvo"
git -C "$outro" worktree add --quiet -b agente/l "$tmp/alvo/l" main
ln -s "$tmp/alvo" "$wts/outro"
gravar l "{\"raiz\": \"$outro\", \"worktree\": \"$wts/outro/l\", \"ramo\": \"agente/l\", \"base\": \"main\"}"
fim l
recusado "link simbólico" l
conferir "link simbólico: worktree mantido" test -d "$tmp/alvo/l"
rm "$wts/outro"

echo "== raiz de outro repositório"
novo_worktree "$proj" x
gravar x "{\"raiz\": \"$outro\", \"worktree\": \"$wts/proj/x\", \"ramo\": \"agente/x\", \"base\": \"main\"}"
fim x
recusado "raiz trocada" x
conferir "raiz trocada: ramo do outro repositório mantido" git -C "$outro" show-ref --quiet --verify refs/heads/agente/x
fim --integrar x
conferir "raiz trocada com --integrar: recusado ($rc)" test "$rc" -ne 0

# Worktree já removido: a raiz precisa ter o nome da pasta do repositório.
gravar y "{\"raiz\": \"$outro\", \"worktree\": \"$wts/proj/x-sumiu\", \"ramo\": \"agente/x-sumiu\", \"base\": \"main\"}"
fim y
recusado "raiz trocada sem worktree" y

echo "== pasta que não é worktree registrado"
mkdir -p "$wts/proj/solto"
git init --quiet "$wts/proj/solto"
gravar s1 "{\"raiz\": \"$wts/proj/solto\", \"worktree\": \"$wts/proj/solto\", \"ramo\": \"agente/solto\", \"base\": \"main\"}"
fim s1
recusado "worktree igual à raiz" s1
gravar s2 "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/solto\", \"ramo\": \"agente/solto\", \"base\": \"main\"}"
fim s2
recusado "pasta de outro repositório" s2
# Pasta cujo .git aponta para o registro de outro worktree do projeto: mesmo
# diretório comum, mas não é ela que o repositório registra.
mkdir -p "$wts/proj/copia"
printf 'gitdir: %s\n' "$proj/.git/worktrees/r1" >"$wts/proj/copia/.git"
gravar s3 "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/copia\", \"ramo\": \"agente/copia\", \"base\": \"main\"}"
fim s3
recusado "pasta sem registro" s3
conferir "pasta sem registro: motivo" grep -q 'não é worktree registrado' "$tmp/saida"

echo "== base que vira opção do git"
gravar b "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/x\", \"ramo\": \"agente/x\", \"base\": \"--output=$tmp/escrito\"}"
fim b
recusado "base --output" b
conferir "base --output: nada gravado" test ! -e "$tmp/escrito"

echo "== estado válido"
gravar x "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/x\", \"ramo\": \"agente/x\", \"base\": \"main\", \"estado\": \"concluido\"}"
fim x
conferir "encerra ($rc)" test "$rc" -eq 0
conferir "worktree removido" test ! -d "$wts/proj/x"
conferir "estado apagado" test ! -f "$estado/x.json"
conferir "ramo mantido" git -C "$proj" show-ref --quiet --verify refs/heads/agente/x
: >"$tmp/mortas"

echo "== --limpar-concluidos"
rm -f "$estado"/*.json
agora="$(date -Iseconds)"
novo_worktree "$proj" viva
# Outra sessão, viva no tmux, marcada como concluída pelo agente.
printf 'viva\n' >"$tmp/sessoes"
gravar viva "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/viva\", \"ramo\": \"agente/viva\", \"base\": \"main\", \"estado\": \"concluido\", \"atualizado\": \"$agora\", \"dir\": \"$wts/proj/viva\"}"
limpar() { "$repo_jangada/bin/jangada-agentes" --limpar-concluidos >"$tmp/saida" 2>&1; rc=$?; }
limpar <<<n
conferir "resposta n: termina sem erro ($rc)" test "$rc" -eq 0
conferir "resposta n: lista a sessão" grep -q 'viva.*sessão aberta no tmux' "$tmp/saida"
conferir "resposta n: sessão não encerrada" test ! -s "$tmp/mortas"
conferir "resposta n: worktree mantido" test -d "$wts/proj/viva"
limpar </dev/null
conferir "sem terminal: sessão não encerrada" test ! -s "$tmp/mortas"
conferir "sem terminal: estado mantido" test -f "$estado/viva.json"
limpar <<<s
conferir "resposta s: encerra ($rc)" test "$rc" -eq 0
conferir "resposta s: sessão encerrada" grep -qx '=viva' "$tmp/mortas"
conferir "resposta s: worktree removido" test ! -d "$wts/proj/viva"

if ((falhas)); then
  echo "--- última saída"; cat "$tmp/saida"
  echo "$falhas falha(s)"
  exit 1
fi
echo "tudo certo"
