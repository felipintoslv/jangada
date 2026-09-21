#!/usr/bin/env bash
# Testa o fluxo do jangada-par com claude e agy falsos no PATH: nada vai para
# a rede e nada toca o estado real (XDG_STATE_HOME e XDG_CONFIG_HOME apontam
# para uma pasta temporária).
#
# Uso: testes/par.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/config/jangada" "$tmp/estado" "$tmp/projeto"
printf 'JANGADA_WORKTREES=%s\n' "$tmp/worktrees" >"$tmp/config/jangada/jangada.conf"

# claude falso: na implementação e na avaliação faz um commit; na avaliação
# responde com a tabela, que o jangada-par grava como avaliação.
cat >"$tmp/bin/claude" <<'EOF'
#!/usr/bin/env bash
prompt="$2"
n=$(( $(cat "$FALSO_DIR/claude.n" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$FALSO_DIR/claude.n"
printf '%s' "$prompt" >"$FALSO_DIR/claude-$n.prompt"
echo "linha $n" >>arquivo.txt
git add arquivo.txt && git commit -qm "commit $n"
[[ -n "${FALSO_SOLTO:-}" ]] && echo "sem commit $n" >"solto-$n.txt"
if [[ "$prompt" == *"Avaliação do parecer"* ]]; then
  printf '# Avaliação do parecer\n\n| 1 | nome ruim | REJEITADO | MARCA-REJEICAO | nenhuma |\n'
fi
EOF

# agy falso: devolve em ordem as respostas de $FALSO_DIR/agy-respostas.
cat >"$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
n=$(( $(cat "$FALSO_DIR/agy.n" 2>/dev/null || echo 0) + 1 ))
echo "$n" >"$FALSO_DIR/agy.n"
printf '%s' "$2" >"$FALSO_DIR/agy-$n.prompt"
resp="$(sed -n "${n}p" "$FALSO_DIR/agy-respostas")"
jq -n --arg r "$resp" '{status:"SUCCESS", response:($r | gsub("\\\\n"; "\n"))}'
EOF
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/notify-send"
chmod +x "$tmp/bin/"*

git -C "$tmp/projeto" init -q -b main
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio

rodar_par() {
  local nome="$1" limite="$2"
  local -a alvo=(--nome "$nome")
  [[ "$nome" == direto ]] && alvo=(--direto)
  rm -f "$tmp/falso/"*.n "$tmp/falso/"*.prompt
  env PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp/falso" NO_COLOR=1 FALSO_SOLTO="${FALSO_SOLTO:-}" \
    XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" \
    JANGADA_PATH="$repo_jangada" GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t \
    GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t \
    "$repo_jangada/bin/jangada-par" --projeto "$tmp/projeto" "${alvo[@]}" \
    --limite "$limite" "tarefa de teste" </dev/null >"$tmp/saida-$nome.log" 2>&1
}
estado_de() { jq -r "$2" "$tmp/estado/jangada/agentes/projeto--$1.json" 2>/dev/null; }
mkdir -p "$tmp/falso"

# Caso 1: REVISAR, avaliação, APROVADO.
printf '%s\n' 'STATUS: REVISAR\n1. nome ruim' 'STATUS: APROVADO\ntudo certo' >"$tmp/falso/agy-respostas"
rodar_par um 2
conferir "caso 1: termina concluído" [ "$(estado_de um .estado)" = concluido ]
conferir "caso 1: avaliação da rodada 1 gravada" \
  grep -q MARCA-REJEICAO "$tmp/estado/jangada/agentes/avaliacao-projeto--um-r1.md"
conferir "caso 1: avaliação vai ao revisor na rodada 2" grep -q MARCA-REJEICAO "$tmp/falso/agy-2.prompt"
conferir "caso 1: revisor da rodada 1 não recebe avaliação" \
  bash -c '! grep -q "o Claude avaliou cada um" "$1"' _ "$tmp/falso/agy-1.prompt"
conferir "caso 1: claude avalia o parecer em vez de aplicar tudo" grep -q "REJEITADO" "$tmp/falso/claude-2.prompt"
conferir "caso 1: resumo sugere integrar" grep -q "jangada-agente-fim --integrar projeto--um" "$tmp/saida-um.log"

# Caso 2: limite 1 com REVISAR: avaliação final sem nova revisão.
printf '%s\n' 'STATUS: REVISAR\n1. nome ruim' >"$tmp/falso/agy-respostas"
rodar_par dois 1
conferir "caso 2: termina aguardando" [ "$(estado_de dois .estado)" = aguardando ]
conferir "caso 2: mensagem avisa que faltou revisão" \
  bash -c '[[ "$1" == *"sem nova revisão"* ]]' _ "$(estado_de dois .mensagem)"
conferir "caso 2: avaliação final gravada" test -s "$tmp/estado/jangada/agentes/avaliacao-projeto--dois-r1.md"
conferir "caso 2: agy chamado uma vez só" [ "$(cat "$tmp/falso/agy.n")" = 1 ]

# Caso 3: direto no repositório, com arquivo deixado sem commit. Na rodada 2 o
# revisor vê desde o início do ciclo (antes via só o último commit, HEAD~1) e
# vê o arquivo solto.
printf '%s\n' 'STATUS: REVISAR\n1. nome ruim' 'STATUS: APROVADO\ntudo certo' >"$tmp/falso/agy-respostas"
FALSO_SOLTO=1 rodar_par direto 2
conferir "caso 3: rodada 2 mostra o commit da rodada 1" grep -q '^+linha 1$' "$tmp/falso/agy-2.prompt"
conferir "caso 3: arquivo sem commit listado ao revisor" grep -q 'solto-.*sem commit' "$tmp/falso/agy-2.prompt"
conferir "caso 3: aviso de alteração sem commit" grep -q 'sem commit' "$tmp/saida-direto.log"
git -C "$tmp/projeto" clean -qf

if ((falhas)); then
  echo "$falhas falha(s); saídas em $tmp (mantido)"
  trap - EXIT
  exit 1
fi
echo "todos os testes do par passaram"
