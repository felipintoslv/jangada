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
unset HYPRLAND_INSTANCE_SIGNATURE JANGADA_SESSAO JANGADA_REPO JANGADA_SIMULAR JANGADA_WORKTREES JANGADA_ISOLADO
unset JANGADA_VALIDAR_REVISOR JANGADA_VALIDAR_MODELO
export JANGADA_VALIDAR_SEM_GITLEAKS=1
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
# Revisor falso do jangada-validar: registra a chamada e responde
# $FALSO_RESPOSTA. Com $FALSO_AVANCA, faz antes um commit nesse worktree, como
# o agente que segue trabalhando durante a revisão; com $FALSO_COMANDO, roda
# o comando.
cat >"$tmp/bin/claude" <<'EOF'
#!/usr/bin/env bash
cat >/dev/null
: >>"$FALSO_DIR/revisor-chamado"
if [[ -n "${FALSO_AVANCA:-}" ]]; then
  echo depois >"$FALSO_AVANCA/depois.txt"
  git -C "$FALSO_AVANCA" add depois.txt
  git -C "$FALSO_AVANCA" commit --quiet -m depois
fi
[[ -z "${FALSO_COMANDO:-}" ]] || eval "$FALSO_COMANDO"
printf '%b\n' "${FALSO_RESPOSTA:-STATUS: REVISAR}"
EOF
chmod +x "$tmp/bin/tmux" "$tmp/bin/claude"
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
# Pareceres da sessão x e da vizinha x-rotas, com o mesmo prefixo.
printf 'STATUS: APROVADO\n' >"$estado/validacao-x-r1.md"
printf 'STATUS: APROVADO\n' >"$estado/validacao-x-rotas-r1.md"
fim x
conferir "pareceres da sessão apagados" test ! -e "$estado/validacao-x-r1.md"
conferir "parecer da sessão vizinha mantido" test -f "$estado/validacao-x-rotas-r1.md"
rm -f "$estado/validacao-x-rotas-r1.md"
conferir "encerra ($rc)" test "$rc" -eq 0
conferir "worktree removido" test ! -d "$wts/proj/x"
conferir "estado apagado" test ! -f "$estado/x.json"
conferir "ramo mantido" git -C "$proj" show-ref --quiet --verify refs/heads/agente/x
: >"$tmp/mortas"

echo "== --integrar e a revisão fora do isolamento"
revisoes="$XDG_STATE_HOME/jangada/revisoes"
mkdir -p "$revisoes"
integrar_teste() { # sessão, resposta à confirmação, opções extras
  local s="$1" r="$2"; shift 2
  rm -f "$tmp/revisor-chamado"
  "$repo_jangada/bin/jangada-agente-fim" --integrar "$@" "$s" <<<"$r" >"$tmp/saida" 2>&1; rc=$?
}
preparar() { # sessão
  novo_worktree "$proj" "$1"
  echo "$1" >"$wts/proj/$1/$1.txt"
  git -C "$wts/proj/$1" add "$1.txt"
  git -C "$wts/proj/$1" commit --quiet -m "$1"
  gravar "$1" "{\"raiz\": \"$proj\", \"worktree\": \"$wts/proj/$1\", \"ramo\": \"agente/$1\", \"base\": \"main\", \"estado\": \"concluido\"}"
}

# Marca como o jangada-validar grava: sessão, pasta e, para trocar um campo,
# um filtro do jq.
marca() {
  local c
  c="$(git -C "$proj" rev-parse "agente/$1")"
  jq -n --arg c "$c" --arg t "$(git -C "$proj" rev-parse "$c^{tree}")" --arg b "$(git -C "$proj" rev-parse main)" \
    '{cabeca: $c, num: 1, limpo: true, base: "main", base_sha: $b, candidate_sha: $c, candidate_tree: $t,
      reviewer: "agy", author: "claude", independent: true}' | jq "${3:-.}" >"$2/validacao-$1.aprovado"
}

# Confirmação gráfica vincula os dois commits e exige aprovação independente.
preparar gui
b_gui="$(git -C "$proj" rev-parse main)"
c_gui="$(git -C "$proj" rev-parse agente/gui)"
integrar_teste gui '' --confirmacao "$b_gui" "$c_gui"
conferir "GUI: sem marca recusa" test "$rc" -ne 0
conferir "GUI: sem marca mantém worktree" test -d "$wts/proj/gui"
marca gui "$revisoes" '.independent = false'
integrar_teste gui '' --confirmacao "$b_gui" "$c_gui"
conferir "GUI: autorrevisão recusa" test "$rc" -ne 0
marca gui "$revisoes"
integrar_teste gui '' --confirmacao "$b_gui" "$b_gui"
conferir "GUI: candidato diferente recusa" test "$rc" -ne 0
integrar_teste gui '' --confirmacao "$c_gui" "$c_gui"
conferir "GUI: base diferente recusa" test "$rc" -ne 0
# A aprovação é retirada depois da prévia, antes da reconferência sob trava.
mkdir -p "$tmp/hash-gui"
cat >"$tmp/hash-gui/sha256sum" <<EOF
#!/usr/bin/env bash
rm -f "$revisoes/validacao-gui.aprovado"
exec $(command -v sha256sum) "\$@"
EOF
chmod +x "$tmp/hash-gui/sha256sum"
PATH="$tmp/hash-gui:$PATH" integrar_teste gui '' --confirmacao "$b_gui" "$c_gui"
conferir "GUI: marca retirada antes da trava recusa" test "$rc" -ne 0
conferir "GUI: marca retirada não mescla" test ! -e "$proj/gui.txt"
marca gui "$revisoes"
integrar_teste gui '' --confirmacao "$b_gui" "$c_gui"
conferir "GUI: confirmação exata integra sem entrada padrão" test "$rc" -eq 0
conferir "GUI: conteúdo integrado" test -e "$proj/gui.txt"

# Aprovação de fora para o commit do ramo: integra sem chamar o revisor.
preparar i1
marca i1 "$revisoes"
printf 'STATUS: APROVADO\n' >"$revisoes/validacao-i1-r1.md"
integrar_teste i1 s
conferir "aprovação de fora: integra ($rc)" test "$rc" -eq 0
conferir "aprovação de fora: diz que vale" grep -q "aprovado fora do isolamento no commit" "$tmp/saida"
conferir "aprovação de fora: o revisor não roda" test ! -e "$tmp/revisor-chamado"
conferir "aprovação de fora: mesclado" test -e "$proj/i1.txt"
conferir "aprovação de fora: a revisão sai com a sessão" \
  bash -c 'test ! -e "$1/validacao-i1.aprovado" && test ! -e "$1/validacao-i1-r1.md"' _ "$revisoes"

# Marca forjada em agentes/ e aprovação de fora com o worktree sujo não
# contam: o revisor roda, reprova, e a resposta n não integra.
preparar i2
marca i2 "$estado"
printf 'STATUS: APROVADO\n' >"$estado/validacao-i2-r1.md"
marca i2 "$revisoes" '.limpo = false'
FALSO_RESPOSTA='STATUS: REVISAR\n1. i2.txt:1: problema' integrar_teste i2 n
conferir "marca forjada: o revisor roda fora" test -e "$tmp/revisor-chamado"
conferir "marca forjada: o parecer vai para revisoes/" grep -q problema "$revisoes/validacao-i2-r1.md"
conferir "marca forjada: pede confirmação sem aprovação" grep -q "sem aprovação feita fora do isolamento" "$tmp/saida"
conferir "marca forjada: resposta n não integra ($rc)" bash -c '[ "$1" -ne 0 ] && test ! -e "$2/i2.txt"' _ "$rc" "$proj"
conferir "marca forjada: sessão mantida" test -f "$estado/i2.json"

# Revisor aprova: a marca nova vale e o merge segue.
FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste i2 s
conferir "revisão aprovada fora: integra ($rc)" bash -c '[ "$1" -eq 0 ] && test -e "$2/i2.txt"' _ "$rc" "$proj"
conferir "revisão aprovada fora: pergunta sem o aviso" bash -c '! grep -q "sem aprovação feita fora" "$1"' _ "$tmp/saida"

# --sem-revisao: não chama o revisor e pede a confirmação explícita.
preparar i3
integrar_teste i3 n --sem-revisao
conferir "--sem-revisao: o revisor não roda" test ! -e "$tmp/revisor-chamado"
conferir "--sem-revisao: pede confirmação sem aprovação" grep -q "sem aprovação feita fora do isolamento" "$tmp/saida"
conferir "--sem-revisao: resposta n não integra" test ! -e "$proj/i3.txt"
integrar_teste i3 s --sem-revisao
conferir "--sem-revisao: resposta s integra ($rc)" bash -c '[ "$1" -eq 0 ] && test -e "$2/i3.txt"' _ "$rc" "$proj"

# O ramo avança durante a revisão: nem o commit conferido nem o novo entram.
preparar i5
FALSO_AVANCA="$wts/proj/i5" FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste i5 s
conferir "ramo avançou: recusa ($rc)" test "$rc" -ne 0
conferir "ramo avançou: explica" grep -q "mudou depois da conferência" "$tmp/saida"
conferir "ramo avançou: nada mesclado" bash -c 'test ! -e "$1/i5.txt" && test ! -e "$1/depois.txt"' _ "$proj"
conferir "ramo avançou: sessão mantida" test -f "$estado/i5.json"

# Marca no formato antigo (COMMIT N ESTADO) não diz base nem revisor: não vale.
preparar i6
printf '%s 1 limpo\n' "$(git -C "$proj" rev-parse agente/i6)" >"$revisoes/validacao-i6.aprovado"
FALSO_RESPOSTA='STATUS: REVISAR\n1. x' integrar_teste i6 n
conferir "marca antiga: o revisor roda de novo" test -e "$tmp/revisor-chamado"
conferir "marca antiga: não integra" test ! -e "$proj/i6.txt"

# Árvore diferente da que o revisor leu: não vale.
marca i6 "$revisoes" '.candidate_tree = "4b825dc642cb6eb9a060e54bf8d69288fbee4904"'
FALSO_RESPOSTA='STATUS: REVISAR\n1. x' integrar_teste i6 n
conferir "árvore trocada: o revisor roda de novo" test -e "$tmp/revisor-chamado"

# Autorrevisão: não vale como aprovação, e revisar de novo daria a mesma.
marca i6 "$revisoes" '.independent = false | .reviewer = "claude"'
integrar_teste i6 n
conferir "autorrevisão: o revisor não roda de novo" test ! -e "$tmp/revisor-chamado"
conferir "autorrevisão: avisa e pede a confirmação à parte" \
  bash -c 'grep -q "só tem autorrevisão" "$1" && grep -q "nada foi feito" "$1"' _ "$tmp/saida"
conferir "autorrevisão: resposta n não integra" test ! -e "$proj/i6.txt"

# A base andou depois da revisão: a aprovação era contra outra base.
marca i6 "$revisoes"
echo b >"$proj/base.txt"; git -C "$proj" add base.txt; git -C "$proj" commit --quiet -m "base anda"
FALSO_RESPOSTA='STATUS: REVISAR\n1. x' integrar_teste i6 n
conferir "base andou: o revisor roda de novo" test -e "$tmp/revisor-chamado"
conferir "base andou: não integra" test ! -e "$proj/i6.txt"

# A base anda durante a revisão: a marca nasce contra a base antiga, e mesmo
# com a resposta s nada é mesclado.
FALSO_COMANDO="echo c >'$proj/durante.txt'; git -C '$proj' add durante.txt; git -C '$proj' commit --quiet -m durante" \
  FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste i6 s
conferir "base andou na revisão: recusa ($rc)" test "$rc" -ne 0
conferir "base andou na revisão: explica" \
  bash -c 'grep -q "a base main mudou depois da conferência" "$1"' _ "$tmp/saida"
conferir "base andou na revisão: nada mesclado, sessão mantida" \
  bash -c 'test ! -e "$1/i6.txt" && test -f "$2/i6.json"' _ "$proj" "$estado"

# Outra integração segura a trava do repositório: esta não mescla.
marca i6 "$revisoes"
trava="$revisoes/travas/$(realpath "$proj/.git" | sha256sum | cut -c1-16)"
mkdir -p "$trava"
flock "$trava" sleep 8 &
vitima=$!
sleep 1
integrar_teste i6 s
kill "$vitima" 2>/dev/null; wait "$vitima" 2>/dev/null; vitima=""
conferir "trava ocupada: recusa ($rc)" test "$rc" -ne 0
conferir "trava ocupada: explica" grep -q "outra integração segura a trava" "$tmp/saida"
conferir "trava ocupada: nada mesclado" test ! -e "$proj/i6.txt"

# Duas integrações ao mesmo tempo, as duas aprovadas contra a mesma base: só
# entra o que foi conferido contra a base em que o merge acontece.
preparar i7
marca i6 "$revisoes"; marca i7 "$revisoes"
base_antes="$(git -C "$proj" rev-parse main)"
for n in i6 i7; do
  ( FALSO_RESPOSTA='STATUS: APROVADO' "$repo_jangada/bin/jangada-agente-fim" --integrar "$n" <<<s >"$tmp/saida-$n" 2>&1
    echo $? >"$tmp/rc-$n" ) &
done
wait
conferir "simultâneas: ao menos uma integra" \
  bash -c '[ "$(cat "$1/rc-i6")" = 0 ] || [ "$(cat "$1/rc-i7")" = 0 ]' _ "$tmp"
for n in i6 i7; do
  conferir "simultâneas: $n foi mesclada se e só se saiu com 0 ($(cat "$tmp/rc-$n"))" \
    bash -c 'if [ "$(cat "$1/rc-$3")" = 0 ]; then test -e "$2/$3.txt"; else test ! -e "$2/$3.txt"; fi' _ "$tmp" "$proj" "$n"
done
conferir "simultâneas: cada merge parte da base conferida ou de outro merge, com o repositório íntegro" \
  bash -c 'git -C "$1" fsck --no-dangling >/dev/null 2>&1 && git -C "$1" merge-base --is-ancestor "$2" main \
           && [ -z "$(git -C "$1" status --porcelain --untracked-files=no)" ]' _ "$proj" "$base_antes"
for n in i6 i7; do
  [[ "$(cat "$tmp/rc-$n")" == 0 ]] || FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste "$n" s
done
conferir "simultâneas: a que ficou de fora integra depois de revisada de novo" \
  bash -c 'test -e "$1/i6.txt" && test -e "$1/i7.txt"' _ "$proj"

# Objeto trocado em .git/objects depois da revisão: o git mesclaria o conteúdo
# forjado com o nome do original. O espelho já tem o objeto honesto.
preparar i8
FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste i8 n
blob="$(git -C "$proj" rev-parse agente/i8:i8.txt)"
objeto="$proj/.git/objects/${blob:0:2}/${blob:2}"
chmod u+w "$objeto"
python3 -c 'import sys, zlib
d = b"forjado\n"
sys.stdout.buffer.write(zlib.compress(b"blob %d\0" % len(d) + d))' >"$objeto"
conferir "objeto forjado: a marca ainda vale para o commit" \
  jq -e --arg c "$(git -C "$proj" rev-parse agente/i8)" '.candidate_sha == $c and .independent' "$revisoes/validacao-i8.aprovado"
integrar_teste i8 s
conferir "objeto forjado: recusa ($rc)" test "$rc" -ne 0
conferir "objeto forjado: explica" grep -q "não conferem com o espelho" "$tmp/saida"
conferir "objeto forjado: nada mesclado" test ! -e "$proj/i8.txt"
rm -f "$objeto"

# Objeto trocado entre a conferência com o espelho e o merge: um git falso
# forja o blob na hora do merge. A mescla refeita no espelho não bate com o
# que foi escrito, e a base volta para onde estava.
preparar i9
FALSO_RESPOSTA='STATUS: APROVADO' integrar_teste i9 n
blob="$(git -C "$proj" rev-parse agente/i9:i9.txt)"
objeto="$proj/.git/objects/${blob:0:2}/${blob:2}"
git_real="$(command -v git)"
mkdir -p "$tmp/git-forja"
cat >"$tmp/git-forja/git" <<FIM
#!/usr/bin/env bash
if [[ " \$* " == *" merge --no-ff "* ]]; then
  chmod u+w "$objeto"
  python3 -c 'import sys, zlib
d = b"forjado\n"
sys.stdout.buffer.write(zlib.compress(b"blob %d\0" % len(d) + d))' >"$objeto"
  "$git_real" "\$@" || exit \$?
  indice="\$("$git_real" -C "$proj" rev-parse --path-format=absolute --git-path index)"
  python3 -c 'import os, sys, time; t = time.time() + 10; os.utime(sys.argv[1], (t, t))' "\$indice"
  "$git_real" -C "$proj" update-index --really-refresh
  python3 -c 'import os, sys, time; t = time.time() + 10; os.utime(sys.argv[1], (t, t))' "\$indice"
  "$git_real" -C "$proj" diff-index --quiet HEAD -- && touch "$tmp/indice-enganado"
  exit 0
fi
exec "$git_real" "\$@"
FIM
chmod +x "$tmp/git-forja/git"
base_antes="$(git -C "$proj" rev-parse main)"
PATH="$tmp/git-forja:$PATH" integrar_teste i9 s
conferir "objeto forjado durante o merge: o índice considera o conteúdo limpo" test -e "$tmp/indice-enganado"
conferir "objeto forjado durante o merge: recusa ($rc)" test "$rc" -ne 0
conferir "objeto forjado durante o merge: explica" grep -q "não confere com a mescla refeita no espelho" "$tmp/saida"
conferir "objeto forjado durante o merge: a base volta e nada fica mesclado" \
  bash -c '[ "$(git -C "$1" rev-parse main)" = "$2" ] && [ ! -e "$1/i9.txt" ]' _ "$proj" "$base_antes"
rm -f "$objeto"

# Falha ao listar os arquivos e troca de tipo ou permissão depois do merge.
for caso in diff-tree link executavel sem-execucao; do
  preparar "i-$caso"
  if [[ "$caso" == sem-execucao ]]; then
    chmod +x "$wts/proj/i-$caso/i-$caso.txt"
    git -C "$wts/proj/i-$caso" add .
    git -C "$wts/proj/i-$caso" commit --quiet -m executavel
  fi
  marca "i-$caso" "$revisoes"
  mkdir -p "$tmp/git-conferencia"
  cat >"$tmp/git-conferencia/git" <<FIM
#!/usr/bin/env bash
if [[ "$caso" == diff-tree && " \$* " == *" diff-tree "* ]]; then
  exit 1
fi
if [[ " \$* " == *" merge --no-ff "* ]]; then
  "$git_real" "\$@" || exit \$?
  case "$caso" in
    link)
      mv "$proj/i-$caso.txt" "$tmp/alvo-link"
      ln -s "$tmp/alvo-link" "$proj/i-$caso.txt"
      ;;
    executavel) chmod +x "$proj/i-$caso.txt" ;;
    sem-execucao) chmod -x "$proj/i-$caso.txt" ;;
  esac
  exit 0
fi
exec "$git_real" "\$@"
FIM
  chmod +x "$tmp/git-conferencia/git"
  base_antes="$(git -C "$proj" rev-parse main)"
  PATH="$tmp/git-conferencia:$PATH" integrar_teste "i-$caso" s
  conferir "conferência $caso: recusa ($rc)" test "$rc" -ne 0
  conferir "conferência $caso: explica" grep -q "não confere com a mescla refeita no espelho" "$tmp/saida"
  conferir "conferência $caso: a base volta e a sessão permanece" \
    bash -c '[ "$(git -C "$1" rev-parse main)" = "$2" ] && test -e "$3"' \
    _ "$proj" "$base_antes" "$estado/i-$caso.json"
done

# Dentro do isolamento não há revisão que valha: nem roda o revisor.
preparar i4
JANGADA_ISOLADO=1 integrar_teste i4 n
conferir "dentro do isolamento: o revisor não roda" test ! -e "$tmp/revisor-chamado"
conferir "dentro do isolamento: explica" grep -q "rode o --integrar fora dele" "$tmp/saida"
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
