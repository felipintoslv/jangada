#!/usr/bin/env bash
# Testa o jangada-validar com claude e agy falsos no PATH: nada vai para a
# rede e nada toca o estado real (XDG_STATE_HOME e XDG_CONFIG_HOME apontam
# para uma pasta temporária).
#
# Uso: testes/validar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
unset JANGADA_VALIDAR_REVISOR
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/bin" "$tmp/config/jangada" "$tmp/estado/jangada/agentes" "$tmp/projeto" "$tmp/falso"
estado="$tmp/estado/jangada/agentes"

# Os dois falsos gravam o pedido e respondem com $FALSO_RESPOSTA. O claude
# recebe o pedido pela entrada padrão; o agy, como argumento de -p, e responde
# em JSON.
cat >"$tmp/bin/claude" <<'EOF'
#!/usr/bin/env bash
cat >"$FALSO_DIR/claude.pedido"
printf '%b\n' "$FALSO_RESPOSTA"
EOF
cat >"$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
while (($#)); do [[ "$1" == -p ]] && { printf '%s' "$2" >"$FALSO_DIR/agy.pedido"; break; }; shift; done
jq -n --arg r "$(printf '%b' "$FALSO_RESPOSTA")" '{status:"SUCCESS", response:$r}'
EOF
chmod +x "$tmp/bin/"*

git -C "$tmp/projeto" init -q -b main
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio
git -C "$tmp/projeto" checkout -qb agente/x
echo "linha 1" >"$tmp/projeto/arquivo.txt"
git -C "$tmp/projeto" add arquivo.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "commit 1"

# Sessão falsa com o agente dado; o jangada-validar lê .agente, .revisor e .tarefa.
sessao_de() {
  jq -n --arg a "$1" --arg r "${2:-}" \
    '{sessao:"s", agente:$a, base:"main", tarefa:"tarefa de teste", estado:"trabalhando"}
     + (if $r != "" then {revisor:$r} else {} end)' \
    >"$estado/s.json"
  rm -f "$estado/validacao-s-r"* "$tmp/falso/"*.pedido
}
validar() {
  env -u JANGADA_VALIDAR_REVISOR PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp/falso" FALSO_RESPOSTA="$1" JANGADA_SESSAO=s \
    XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
    "$repo_jangada/bin/jangada-validar" "${@:2}" "$tmp/projeto" >"$tmp/saida.log" 2>&1
}

# Caso 1: sessão do Claude, o revisor é o agy.
sessao_de claude
validar 'STATUS: REVISAR\n1. arquivo.txt:1: problema'; rc=$?
conferir "caso 1: REVISAR sai com 3" [ "$rc" = 3 ]
conferir "caso 1: o agy revisou" test -s "$tmp/falso/agy.pedido"
conferir "caso 1: o claude não foi chamado" test ! -e "$tmp/falso/claude.pedido"
conferir "caso 1: pedido traz o diff e a tarefa" \
  bash -c 'grep -q "^+linha 1$" "$1" && grep -q "tarefa de teste" "$1"' _ "$tmp/falso/agy.pedido"
conferir "caso 1: estado registra a rodada e o revisor" [ "$(jq -r .validacao "$estado/s.json")" = "r1: REVISAR (agy)" ]
conferir "caso 1: parecer gravado" grep -q "problema" "$estado/validacao-s-r1.md"

# Caso 2: rodada 2 leva o parecer anterior e a resposta do agente.
validar 'STATUS: APROVADO\ntudo certo' --resposta "1 rejeitado: MARCA-RESPOSTA"; rc=$?
conferir "caso 2: APROVADO sai com 0" [ "$rc" = 0 ]
conferir "caso 2: pedido traz a resposta do agente" grep -q MARCA-RESPOSTA "$tmp/falso/agy.pedido"
conferir "caso 2: pedido traz o parecer anterior" grep -q "problema" "$tmp/falso/agy.pedido"

# Caso 3: sessão do agy, o revisor é o Claude; status com Markdown.
sessao_de agy
validar '## **STATUS: APROVADO**'; rc=$?
conferir "caso 3: o claude revisou" test -s "$tmp/falso/claude.pedido"
conferir "caso 3: o agy não foi chamado" test ! -e "$tmp/falso/agy.pedido"
conferir "caso 3: status com Markdown vale como APROVADO" [ "$rc" = 0 ]

# Caso 4: limite de rodadas.
sessao_de agy
for _ in 1 2; do validar 'STATUS: REVISAR\n1. x' >/dev/null; done
JANGADA_VALIDAR_RODADAS=2 validar 'STATUS: REVISAR\n1. x'; rc=$?
conferir "caso 4: acima do limite sai com 4" [ "$rc" = 4 ]

# Caso 5: pedido acima do limite de argumento do agy. O diff sai do pedido e
# vai para um arquivo que o agy lê.
sessao_de claude
head -c 140000 /dev/zero | tr '\0' 'a' | fold -w 100 >"$tmp/projeto/grande.txt"
git -C "$tmp/projeto" add grande.txt
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 5: aprovado mesmo com diff grande" [ "$rc" = 0 ]
conferir "caso 5: pedido cabe no argumento" [ "$(LC_ALL=C wc -c <"$tmp/falso/agy.pedido")" -lt 131072 ]
conferir "caso 5: pedido aponta o arquivo do diff" grep -q "leia o arquivo .*validacao-s-r1.md.diff" "$tmp/falso/agy.pedido"
git -C "$tmp/projeto" rm -qf grande.txt

# Caso 6: auto-revisão do agy (revisor agy gravado no estado).
sessao_de agy agy
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 6: auto-revisão do agy sai com 0" [ "$rc" = 0 ]
conferir "caso 6: o agy revisou o próprio trabalho" test -s "$tmp/falso/agy.pedido"
conferir "caso 6: o claude não foi chamado" test ! -e "$tmp/falso/claude.pedido"
conferir "caso 6: pedido identifica o autor como Antigravity" grep -q "agente (Antigravity" "$tmp/falso/agy.pedido"
conferir "caso 6: pedido alerta sobre revisão pelo mesmo modelo" grep -q "revisão pelo mesmo modelo" "$tmp/falso/agy.pedido"
conferir "caso 6: estado registra a rodada e o revisor agy" [ "$(jq -r .validacao "$estado/s.json")" = "r1: APROVADO (agy)" ]

# Caso 7: auto-revisão do Claude com --revisor mesmo.
sessao_de claude
validar 'STATUS: APROVADO' --revisor mesmo; rc=$?
conferir "caso 7: auto-revisão do claude com --revisor mesmo sai com 0" [ "$rc" = 0 ]
conferir "caso 7: o claude revisou o próprio trabalho" test -s "$tmp/falso/claude.pedido"
conferir "caso 7: o agy não foi chamado" test ! -e "$tmp/falso/agy.pedido"
conferir "caso 7: pedido identifica o autor como Claude" grep -q "agente (Claude)" "$tmp/falso/claude.pedido"
conferir "caso 7: pedido alerta sobre revisão pelo mesmo modelo" grep -q "revisão pelo mesmo modelo" "$tmp/falso/claude.pedido"
conferir "caso 7: estado registra a rodada e o revisor claude" [ "$(jq -r .validacao "$estado/s.json")" = "r1: APROVADO (claude)" ]

# Caso 8: perfis agy-agy e claude-claude definem variáveis esperadas.
(
  export JANGADA_PATH="$repo_jangada" XDG_CONFIG_HOME="$tmp/config"
  # shellcheck source=bin/jangada-config
  source "$repo_jangada/bin/jangada-config"
  jangada_perfil agy-agy
  [[ "$PERFIL_COMANDO" == "agy" ]] || exit 1
  [[ " ${PERFIL_AMBIENTE[*]} " == *" JANGADA_VALIDAR_REVISOR=agy "* ]] || exit 1

  jangada_perfil claude-claude
  [[ "$PERFIL_COMANDO" == "claude" ]] || exit 1
  [[ " ${PERFIL_AMBIENTE[*]} " == *" JANGADA_VALIDAR_REVISOR=claude "* ]] || exit 1
); rc=$?
conferir "caso 8: perfis agy-agy e claude-claude definem comando e revisor" [ "$rc" = 0 ]

# Caso 9: auto-revisão fora de sessão com --revisor mesmo.
rm -f "$tmp/falso/"*.pedido
env PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp/falso" FALSO_RESPOSTA='STATUS: APROVADO' \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  "$repo_jangada/bin/jangada-validar" --revisor mesmo "$tmp/projeto" >"$tmp/saida.log" 2>&1; rc=$?
conferir "caso 9: --revisor mesmo fora de sessão sai com 0" [ "$rc" = 0 ]
conferir "caso 9: o claude revisou" test -s "$tmp/falso/claude.pedido"
conferir "caso 9: pedido identifica autor coerente com revisor" grep -q "agente (Claude)" "$tmp/falso/claude.pedido"
conferir "caso 9: pedido inclui alerta de auto-revisão" grep -q "revisão pelo mesmo modelo" "$tmp/falso/claude.pedido"

# Caso 10: resolução de revisor no jangada-agente (precedência entre --revisor, perfil e global).
cat >"$tmp/bin/tmux" <<'EOF'
#!/usr/bin/env bash
for arg in "$@"; do [[ "$arg" == has-session ]] && exit 1; done
exit 0
EOF
chmod +x "$tmp/bin/tmux"

# 10a: Perfil agy-agy prevalece sobre JANGADA_VALIDAR_REVISOR=claude global
rm -f "$estado/"*.json
env -u TMUX -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  JANGADA_AGENTE_ESCOLHER=0 JANGADA_VALIDAR_REVISOR=claude \
  "$repo_jangada/bin/jangada-agente" --projeto "$tmp/projeto" --direto --perfil agy-agy </dev/null >/dev/null 2>&1
conferir "caso 10a: perfil agy-agy prevalece sobre global claude" \
  [ "$(jq -r '.revisor // ""' "$estado/projeto.json")" = "agy" ]

# 10b: Perfil claude-claude prevalece sobre JANGADA_VALIDAR_REVISOR=agy global
rm -f "$estado/"*.json
env -u TMUX -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  JANGADA_AGENTE_ESCOLHER=0 JANGADA_VALIDAR_REVISOR=agy \
  "$repo_jangada/bin/jangada-agente" --projeto "$tmp/projeto" --direto --perfil claude-claude </dev/null >/dev/null 2>&1
conferir "caso 10b: perfil claude-claude prevalece sobre global agy" \
  [ "$(jq -r '.revisor // ""' "$estado/projeto.json")" = "claude" ]

# 10c: Opção explícita --revisor prevalece sobre o perfil
rm -f "$estado/"*.json
env -u TMUX -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  JANGADA_AGENTE_ESCOLHER=0 \
  "$repo_jangada/bin/jangada-agente" --projeto "$tmp/projeto" --direto --perfil claude-claude --revisor agy </dev/null >/dev/null 2>&1
conferir "caso 10c: --revisor agy explícito prevalece sobre perfil claude-claude" \
  [ "$(jq -r '.revisor // ""' "$estado/projeto.json")" = "agy" ]

# 10d: JANGADA_VALIDAR_REVISOR=mesmo global resolve para o agente padrão
rm -f "$estado/"*.json
env -u TMUX -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  JANGADA_AGENTE_ESCOLHER=0 JANGADA_VALIDAR_REVISOR=mesmo \
  "$repo_jangada/bin/jangada-agente" --projeto "$tmp/projeto" --direto </dev/null >/dev/null 2>&1
conferir "caso 10d: JANGADA_VALIDAR_REVISOR=mesmo global resolve para o agente da sessão" \
  [ "$(jq -r '.revisor // ""' "$estado/projeto.json")" = "claude" ]

# 10e: Revisor do estado prevalece sobre JANGADA_VALIDAR_REVISOR global no jangada-validar
sessao_de agy agy
env PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp/falso" FALSO_RESPOSTA='STATUS: APROVADO' JANGADA_SESSAO=s \
  XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
  JANGADA_VALIDAR_REVISOR=claude \
  "$repo_jangada/bin/jangada-validar" "$tmp/projeto" >/dev/null 2>&1
conferir "caso 10e: revisor do estado prevalece sobre global claude no jangada-validar" \
  test -s "$tmp/falso/agy.pedido"

# Caso 11: portão determinístico local
# 11a: marcador de conflito no arquivo alterado reprova antes de chamar o revisor
sessao_de claude
echo -e "<<<<<<< HEAD\nconflito\n=======\noutro\n>>>>>>> branch" >"$tmp/projeto/conflito.txt"
git -C "$tmp/projeto" add conflito.txt
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 11a: falha local sai com código 3" [ "$rc" = 3 ]
conferir "caso 11a: revisor IA não foi chamado" test ! -e "$tmp/falso/agy.pedido"
conferir "caso 11a: estado gravado como REVISAR (local)" [ "$(jq -r .validacao "$estado/s.json")" = "r1: REVISAR (local)" ]

# 11b: --pular-local ignora a checagem e chama o revisor
validar 'STATUS: APROVADO' --pular-local; rc=$?
conferir "caso 11b: --pular-local chama o revisor mesmo com falha local" [ "$rc" = 0 ]
conferir "caso 11b: o revisor foi chamado com --pular-local" test -s "$tmp/falso/agy.pedido"

git -C "$tmp/projeto" rm -qf conflito.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "limpeza conflito"

# 11c: --reverter-se-limite restaura o worktree ao atingir o limite de rodadas
sessao_de agy
echo "alteração pendente" >"$tmp/projeto/pendente.txt"
git -C "$tmp/projeto" add pendente.txt
for _ in 1 2; do validar 'STATUS: REVISAR\n1. x' >/dev/null; done
JANGADA_VALIDAR_RODADAS=2 validar 'STATUS: REVISAR\n1. x' --reverter-se-limite; rc=$?
conferir "caso 11c: limite de rodadas com reversão sai com 4" [ "$rc" = 4 ]
conferir "caso 11c: arquivo pendente foi revertido" test ! -e "$tmp/projeto/pendente.txt"

# Caso 12: lintr nos arquivos R, só nas linhas alteradas. O cat() da linha 1
# de antigo.R vem da base e não conta; limpo.R serve para a remoção pura.
if Rscript -e 'quit(status = !requireNamespace("lintr", quietly = TRUE))' >/dev/null 2>&1; then
  git -C "$tmp/projeto" checkout -q main
  printf 'cat("legado\\n")\n' >"$tmp/projeto/antigo.R"
  printf 'x <- 1\ny <- 2\n' >"$tmp/projeto/limpo.R"
  git -C "$tmp/projeto" add antigo.R limpo.R
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "código legado"
  git -C "$tmp/projeto" checkout -q agente/x
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t merge -q main -m "traz o legado"

  # 12a: linha nova limpa passa, e o cat() da base não aparece.
  sessao_de claude
  echo 'y <- 2' >>"$tmp/projeto/antigo.R"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12a: linha nova limpa em arquivo legado passa" [ "$rc" = 0 ]
  conferir "caso 12a: cat() da base não é apontado" bash -c '! grep -q "antigo.R:1:" "$1"' _ "$tmp/saida.log"

  # 12b: sem .lintr no projeto, o achado só vira aviso e o revisor é chamado.
  sessao_de claude
  echo 'cat("novo\n")' >>"$tmp/projeto/antigo.R"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12b: sem .lintr, cat() novo não reprova" [ "$rc" = 0 ]
  conferir "caso 12b: sem .lintr, cat() novo sai como aviso" \
    grep -q "aviso do lintr" "$tmp/saida.log"
  conferir "caso 12b: o aviso aponta a linha nova" grep -q "antigo.R:3: \[undesirable_function_linter\]" "$tmp/saida.log"
  conferir "caso 12b: o revisor foi chamado" test -s "$tmp/falso/agy.pedido"

  # 12c: com .lintr no projeto, o achado reprova antes do revisor.
  sessao_de claude
  cp "$repo_jangada/default/r/lintr" "$tmp/projeto/.lintr"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12c: com .lintr, cat() novo reprova" [ "$rc" = 3 ]
  conferir "caso 12c: o revisor não foi chamado" test ! -e "$tmp/falso/agy.pedido"
  conferir "caso 12c: o parecer aponta a linha nova e não a da base" \
    bash -c 'grep -q "antigo.R:3:" "$1" && ! grep -q "antigo.R:1:" "$1"' _ "$estado/validacao-s-r1.md"

  # 12c: com .lintr, arquivo R só com linhas apagadas não gera achado.
  sessao_de claude
  git -C "$tmp/projeto" checkout -q -- antigo.R
  sed -i 2d "$tmp/projeto/limpo.R"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12c: só remoção de linha em arquivo R passa" [ "$rc" = 0 ]
  conferir "caso 12c: só remoção de linha não gera achado" bash -c '! grep -q "lintr" "$1"' _ "$tmp/saida.log"
  git -C "$tmp/projeto" checkout -q -- limpo.R

  # 12d: arquivo novo sem commit conta inteiro; # nolint no método print vale.
  sessao_de claude
  printf 'print.resumo <- function(x, ...) {\n  cat("Resumo\\n") # nolint: undesirable_function_linter.\n  invisible(x)\n}\n' >"$tmp/projeto/metodo.R"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12d: cat() com nolint em método print passa" [ "$rc" = 0 ]
  echo 'print(1)' >"$tmp/projeto/novo.R"
  sessao_de claude
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12d: arquivo R novo sem commit é conferido" [ "$rc" = 3 ]
  conferir "caso 12d: o parecer aponta o arquivo novo" grep -q "novo.R:1:" "$estado/validacao-s-r1.md"
  rm -f "$tmp/projeto/novo.R"

  # 12e: sem o lintr instalado (Rscript sai com 2), a etapa é pulada em silêncio.
  mkdir -p "$tmp/semlintr"
  printf '#!/usr/bin/env bash\nexit 2\n' >"$tmp/semlintr/Rscript"
  chmod +x "$tmp/semlintr/Rscript"
  echo 'print(1)' >"$tmp/projeto/novo.R"
  sessao_de claude
  PATH="$tmp/semlintr:$PATH" validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12e: sem lintr, a etapa é pulada" [ "$rc" = 0 ]
  conferir "caso 12e: sem lintr, nada é dito" bash -c '! grep -q "lintr" "$1"' _ "$tmp/saida.log"
  rm -f "$tmp/projeto/novo.R" "$tmp/projeto/metodo.R" "$tmp/projeto/.lintr"
else
  echo "pulado caso 12: R ou lintr não instalado"
fi

# Caso 14: critérios de escrita no pedido e aviso de commit com Co-Authored-By.
sessao_de claude
echo "sem coautor" >"$tmp/projeto/escrita.txt"
git -C "$tmp/projeto" add escrita.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "commit limpo"
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 14: pedido traz os critérios de escrita" \
  bash -c 'grep -q "código comentado" "$1" && grep -q "arquivo de resumo" "$1" && grep -q "corpo que repete o diff" "$1"' _ "$tmp/falso/agy.pedido"
conferir "caso 14: commit sem Co-Authored-By não gera aviso" bash -c '! grep -qi "co-authored-by" "$1"' _ "$tmp/saida.log"
sessao_de claude
echo "com coautor" >>"$tmp/projeto/escrita.txt"
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qam "commit com coautor" \
  -m "Corpo com MARCA-CORPO." -m "Co-authored-by: Fulano <f@f>"
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 14: Co-Authored-By só avisa, não reprova" [ "$rc" = 0 ]
conferir "caso 14: pedido traz o corpo do commit" grep -q "MARCA-CORPO" "$tmp/falso/agy.pedido"
conferir "caso 14: o aviso aponta o commit" \
  bash -c 'grep -q "aviso: commit com linha Co-Authored-By" "$1" && grep -q "commit com coautor" "$1" && ! grep -q "commit limpo" "$1"' _ "$tmp/saida.log"

# Caso 13: o jangada-agente acrescenta as regras de R só em projeto com arquivos R.
agente_em() {
  rm -f "$estado/"*.json "$estado/"protocolo-*.md "$estado/"prompt-*.md
  env -u TMUX -u HYPRLAND_INSTANCE_SIGNATURE PATH="$tmp/bin:$PATH" \
    XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
    JANGADA_AGENTE_ESCOLHER=0 "$repo_jangada/bin/jangada-agente" --projeto "$1" --direto "${@:2}" </dev/null >/dev/null 2>&1
}
mkdir -p "$tmp/semr" "$tmp/comr/R"
echo "x" >"$tmp/semr/notas.txt"
echo "x <- 1" >"$tmp/comr/R/analise.R"

agente_em "$tmp/semr"
conferir "caso 13a: sem R, o Claude recebe o protocolo padrão" \
  bash -c 'jq -r .comando "$1" | grep -q "default/agentes/protocolo.md"' _ "$estado/semr.json"
conferir "caso 13a: sem R, nenhum protocolo da sessão é gravado" test ! -e "$estado/protocolo-semr.md"

agente_em "$tmp/comr"
conferir "caso 13b: com R, o Claude recebe o protocolo da sessão" \
  bash -c 'jq -r .comando "$1" | grep -q "protocolo-comr.md"' _ "$estado/comr.json"
conferir "caso 13b: o protocolo da sessão traz o padrão e as regras de R" \
  bash -c 'grep -q "^7. Escrita" "$1" && grep -q "^8. Código R" "$1"' _ "$estado/protocolo-comr.md"

agente_em "$tmp/comr" --perfil agy-agy
conferir "caso 13c: com R, o agy recebe as regras de R no -i" grep -q "^8. Código R" "$estado/prompt-comr.md"

rm -f "$estado/"protocolo-*.md
JANGADA_AGENTE_PROTOCOLO=0 agente_em "$tmp/comr"
conferir "caso 13d: JANGADA_AGENTE_PROTOCOLO=0 desliga também as regras de R" \
  bash -c '! jq -r .comando "$1" | grep -q "append-system-prompt" && test ! -e "$2"' _ "$estado/comr.json" "$estado/protocolo-comr.md"

if ((falhas)); then
  echo "$falhas falha(s); saídas em $tmp (mantido)"
  trap - EXIT
  exit 1
fi
echo "todos os testes do jangada-validar passaram"
