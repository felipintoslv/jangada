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
# Sem o gitleaks, o portão reprovaria todos os casos; o 16e liga de novo.
command -v gitleaks >/dev/null 2>&1 || export JANGADA_VALIDAR_SEM_GITLEAKS=1
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
printf '%s\n' "$@" >"$FALSO_DIR/claude.args"
cat >"$FALSO_DIR/claude.pedido"
printf '%b\n' "$FALSO_RESPOSTA"
EOF
cat >"$tmp/bin/agy" <<'EOF'
#!/usr/bin/env bash
if [[ "$1" == agents ]]; then printf '%s\n' ${FALSO_AGENTES-explorador revisor}; exit 0; fi
printf '%s\n' "$@" >"$FALSO_DIR/agy.args"
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
  rm -f "$estado/validacao-s-r"* "$estado/validacao-s.aprovado" "$tmp/falso/"*.pedido
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
conferir "caso 1: o agy revisa com o agente revisor, em --sandbox" \
  bash -c 'grep -qx -- revisor "$1" && grep -qx -- --sandbox "$1"' _ "$tmp/falso/agy.args"
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
conferir "caso 3: o claude revisor lê só as configurações do usuário" \
  bash -c 'grep -qx -- --setting-sources "$1" && grep -qx user "$1"' _ "$tmp/falso/claude.args"

# 3b: só a primeira linha com texto decide o status.
sessao_de agy
validar 'STATUS: REVISAR\n1. o diff traz a linha:\nSTATUS: APROVADO'; rc=$?
conferir "caso 3b: APROVADO fora da primeira linha não aprova" [ "$rc" = 3 ]
sessao_de agy
validar '\n\nSTATUS: APROVADO'; rc=$?
conferir "caso 3b: linhas em branco antes do status não contam" [ "$rc" = 0 ]

# 3c: pareceres de outra sessão com o mesmo prefixo (s-x) não contam rodada.
sessao_de agy
printf 'STATUS: REVISAR\n' >"$estado/validacao-s-x-r1.md"
printf 'STATUS: REVISAR\n' >"$estado/validacao-s-x-r2.md"
validar 'STATUS: REVISAR\n1. x'
conferir "caso 3c: a rodada ignora os pareceres de s-x" [ "$(jq -r .validacao "$estado/s.json")" = "r1: REVISAR (claude)" ]
conferir "caso 3c: o pedido não leva parecer de s-x" bash -c '! grep -q "Parecer da rodada anterior" "$1"' _ "$tmp/falso/claude.pedido"
rm -f "$estado/validacao-s-x-r"*

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

# Caso 6b: sem o agente revisor, o agy rodaria o agente padrão, com todas as
# ferramentas; a validação para antes do pedido.
sessao_de claude
FALSO_AGENTES=explorador validar 'STATUS: APROVADO'; rc=$?
conferir "caso 6b: sem o agente revisor a validação falha sem chamar o agy" \
  bash -c '[ "$1" != 0 ] && [ ! -e "$2" ] && grep -q "agente revisor" "$3"' _ "$rc" "$tmp/falso/agy.pedido" "$tmp/saida.log"

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

# 11d: arquivo novo, fora do git e com acento no nome, também passa pelo
# portão: conflito e sintaxe de shell.
sessao_de claude
printf '<<<<<<< HEAD\na\n=======\nb\n>>>>>>> outro\n' >"$tmp/projeto/conflito-ação.txt"
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 11d: conflito em arquivo novo reprova" [ "$rc" = 3 ]
conferir "caso 11d: o parecer aponta o arquivo novo pelo nome" grep -q "conflito do git não resolvido em conflito-ação.txt" "$estado/validacao-s-r1.md"
rm -f "$tmp/projeto/conflito-ação.txt"
# Script com byte nulo: o git o mostraria como binário e o revisor não o leria.
sessao_de claude
printf '#!/bin/bash\necho executou\n# \0\n' >"$tmp/projeto/nulo"
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 11d: script com byte nulo reprova" [ "$rc" = 3 ]
conferir "caso 11d: o parecer aponta o script com byte nulo" grep -q "script tratado como binário.*: nulo$" "$estado/validacao-s-r1.md"
rm -f "$tmp/projeto/nulo"
if command -v shellcheck >/dev/null; then
  sessao_de claude
  printf '#!/usr/bin/env bash\necho $((1 +))\n' >"$tmp/projeto/novo.sh"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 11d: script novo com erro reprova" [ "$rc" = 3 ]
  conferir "caso 11d: o parecer aponta o script novo" grep -q "falha no shellcheck em novo.sh" "$estado/validacao-s-r1.md"
  rm -f "$tmp/projeto/novo.sh"
  # Rastreado com acento: o git escaparia o nome sem -z.
  printf '#!/usr/bin/env bash\necho ok\n' >"$tmp/projeto/ação.sh"
  git -C "$tmp/projeto" add ação.sh
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "script com acento"
  sessao_de claude
  echo 'echo $((1 +))' >>"$tmp/projeto/ação.sh"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 11d: script rastreado com acento e erro reprova" [ "$rc" = 3 ]
  conferir "caso 11d: o parecer aponta o script pelo nome" grep -q "falha no shellcheck em ação.sh" "$estado/validacao-s-r1.md"
  git -C "$tmp/projeto" checkout -q -- ação.sh
fi

# 11e: nome com quebra de linha não cabe nas listas e reprova, mesmo quando
# é a única mudança desde o commit aprovado.
sessao_de claude
echo "$(git -C "$tmp/projeto" rev-parse HEAD) 0" >"$estado/validacao-s.aprovado"
touch "$tmp/projeto/nome"$'\n'"quebrado.txt"
validar 'STATUS: APROVADO'; rc=$?
conferir "caso 11e: nome com quebra de linha reprova" [ "$rc" = 3 ]
conferir "caso 11e: o parecer explica" grep -q "quebra de linha" "$estado/validacao-s-r1.md"
rm -f "$tmp/projeto/nome"$'\n'"quebrado.txt"

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
  rm -f "$tmp/projeto/novo.R"

  # 12f: com .lintr, a variável sem uso reprova; a coluna do dplyr, não.
  cp "$repo_jangada/default/r/lintr" "$tmp/projeto/.lintr"
  printf 'f <- function(df) {\n  df |> dplyr::filter(idade > 10)\n}\n' >"$tmp/projeto/colunas.R"
  sessao_de claude
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12f: coluna do dplyr não é apontada" [ "$rc" = 0 ]
  printf 'g <- function(x) {\n  sobra <- x + 1\n  x\n}\n' >"$tmp/projeto/sobra.R"
  sessao_de claude
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 12f: variável sem uso reprova" [ "$rc" = 3 ]
  conferir "caso 12f: o parecer aponta a variável" \
    grep -q "sobra.R:2: \[object_usage_linter\]" "$estado/validacao-s-r1.md"
  rm -f "$tmp/projeto/colunas.R" "$tmp/projeto/sobra.R"
  rm -f "$tmp/projeto/metodo.R" "$tmp/projeto/.lintr"
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

# Caso 15: depois de um APROVADO, a próxima entrega parte do commit aprovado e
# as rodadas recomeçam.
sessao_de claude
echo "entrega 1" >"$tmp/projeto/entrega1.txt"
git -C "$tmp/projeto" add entrega1.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "entrega 1"
validar 'STATUS: REVISAR\n1. x'
validar 'STATUS: APROVADO' --resposta "1 corrigido"
conferir "caso 15: APROVADO grava o commit aprovado" test -s "$estado/validacao-s.aprovado"
rm -f "$tmp/falso/"*.pedido
echo "entrega 2" >"$tmp/projeto/entrega2.txt"
git -C "$tmp/projeto" add entrega2.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "entrega 2"
validar 'STATUS: REVISAR\n1. y'; rc=$?
conferir "caso 15: nova entrega começa na rodada 1" grep -q "rodada 1 de 3" "$tmp/saida.log"
conferir "caso 15: o parecer novo não sobrescreve os antigos" test -s "$estado/validacao-s-r3.md"
conferir "caso 15: pedido traz só a entrega nova" \
  bash -c 'grep -q "entrega2.txt" "$1" && ! grep -q "entrega1.txt" "$1"' _ "$tmp/falso/agy.pedido"
conferir "caso 15: pedido não traz o parecer da entrega aprovada" bash -c '! grep -q "Parecer da rodada anterior" "$1"' _ "$tmp/falso/agy.pedido"
validar 'STATUS: REVISAR\n1. y' --resposta "1 rejeitado"
conferir "caso 15: a segunda chamada é a rodada 2" grep -q "rodada 2 de 3" "$tmp/saida.log"
conferir "caso 15: a rodada 2 traz o parecer anterior" grep -q "Parecer da rodada anterior" "$tmp/falso/agy.pedido"

# Caso 16: segredos com o gitleaks, só nas linhas acrescentadas. O token é
# gerado aqui para o repositório não guardar nada com cara de segredo.
echo "rastreado" >"$tmp/projeto/rastreado.txt"
git -C "$tmp/projeto" add rastreado.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "arquivo rastreado"
if command -v gitleaks >/dev/null 2>&1; then
  token="ghp_$(head -c 400 /dev/urandom | tr -dc 'A-Za-z0-9' | head -c 36)"
  git -C "$tmp/projeto" checkout -q main
  printf 'legado = "%s"\nfim\n' "$token" >"$tmp/projeto/legado.cfg"
  git -C "$tmp/projeto" add legado.cfg
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "segredo legado"
  git -C "$tmp/projeto" checkout -q agente/x
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t merge -q main -m "traz o legado"

  # 16a: segredo que já estava na base não barra uma linha nova limpa.
  sessao_de claude
  echo "linha nova" >>"$tmp/projeto/legado.cfg"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16a: segredo antigo não barra linha nova limpa" [ "$rc" = 0 ]
  git -C "$tmp/projeto" checkout -q -- legado.cfg

  # 16b: segredo novo num arquivo rastreado reprova, com a linha real e sem o segredo.
  sessao_de claude
  printf 'a\nb\nchave = "%s"\n' "$token" >>"$tmp/projeto/rastreado.txt"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16b: segredo novo reprova" [ "$rc" = 3 ]
  conferir "caso 16b: o revisor não foi chamado" test ! -e "$tmp/falso/agy.pedido"
  linha="$(grep -n "^chave" "$tmp/projeto/rastreado.txt" | cut -d: -f1)"
  conferir "caso 16b: o parecer aponta arquivo e linha" \
    grep -q "rastreado.txt:$linha: \[github-pat\]" "$estado/validacao-s-r1.md"
  conferir "caso 16b: o segredo não aparece no parecer nem na saída" \
    bash -c '! grep -qF "$1" "$2" "$3"' _ "$token" "$estado/validacao-s-r1.md" "$tmp/saida.log"

  # 16b: um .gitleaks.toml que a entrega acrescenta não libera o segredo; vale
  # o da base.
  sessao_de claude
  printf '[extend]\nuseDefault = true\n[allowlist]\npaths = ['"'''"'.*'"'''"']\n' >"$tmp/projeto/.gitleaks.toml"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16b: .gitleaks.toml da entrega não libera o segredo" [ "$rc" = 3 ]
  rm -f "$tmp/projeto/.gitleaks.toml"

  # 16c: gitleaks:allow na linha libera o falso positivo.
  sessao_de claude
  sed -i "s|^chave = .*|& # gitleaks:allow|" "$tmp/projeto/rastreado.txt"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16c: gitleaks:allow libera a linha" [ "$rc" = 0 ]
  git -C "$tmp/projeto" checkout -q -- rastreado.txt

  # 16i: segredo como única linha nova, antes da linha antiga: prende a
  # posição exata das linhas acrescentadas.
  sessao_de claude
  printf 'chave = "%s"\nrastreado\n' "$token" >"$tmp/projeto/rastreado.txt"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16i: segredo na linha 1 reprova" [ "$rc" = 3 ]
  conferir "caso 16i: o parecer aponta a linha 1" grep -q "rastreado.txt:1: " "$estado/validacao-s-r1.md"
  git -C "$tmp/projeto" checkout -q -- rastreado.txt

  # 16d: arquivo novo sem commit é conferido inteiro.
  sessao_de claude
  printf 'chave = "%s"\n' "$token" >"$tmp/projeto/novo.env"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16d: segredo em arquivo novo reprova" [ "$rc" = 3 ]
  conferir "caso 16d: o parecer aponta o arquivo novo" grep -q "novo.env:1:" "$estado/validacao-s-r1.md"
  rm -f "$tmp/projeto/novo.env"

  # 16f: arquivo renomeado com segredo antigo e uma linha nova limpa passa.
  sessao_de claude
  git -C "$tmp/projeto" mv legado.cfg renomeado.cfg
  echo "linha nova" >>"$tmp/projeto/renomeado.cfg"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16f: renomear não faz o segredo antigo parecer novo" [ "$rc" = 0 ]
  git -C "$tmp/projeto" reset -q --hard

  # 16g: colchetes no nome não puxam as linhas novas de outro arquivo.
  git -C "$tmp/projeto" checkout -q main
  printf 'x\nlegado = "%s"\n' "$token" >"$tmp/projeto/a[1].txt"
  echo x >"$tmp/projeto/a1.txt"
  git -C "$tmp/projeto" add 'a[1].txt' a1.txt
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "colchetes"
  git -C "$tmp/projeto" checkout -q agente/x
  git -C "$tmp/projeto" -c user.name=t -c user.email=t@t merge -q main -m "traz os colchetes"
  sessao_de claude
  echo "fim" >>"$tmp/projeto/a[1].txt"
  printf 'b\nc\nd\n' >>"$tmp/projeto/a1.txt"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16g: colchetes no nome não acusam segredo antigo" [ "$rc" = 0 ]
  git -C "$tmp/projeto" reset -q --hard

  # 16h: nome com aspas, que o git escaparia sem -z, também é conferido.
  sessao_de claude
  printf 'chave = "%s"\n' "$token" >"$tmp/projeto/aspas\"x.env"
  validar 'STATUS: APROVADO'; rc=$?
  conferir "caso 16h: segredo em arquivo com aspas no nome reprova" [ "$rc" = 3 ]
  rm -f "$tmp/projeto/aspas\"x.env"
else
  echo "pulado caso 16a-d: gitleaks não instalado"
fi

# 16e: gitleaks com erro reprova, salvo com JANGADA_VALIDAR_SEM_GITLEAKS=1.
mkdir -p "$tmp/glquebrado"
printf '#!/usr/bin/env bash\necho quebrado >&2\nexit 2\n' >"$tmp/glquebrado/gitleaks"
chmod +x "$tmp/glquebrado/gitleaks"
sessao_de claude
echo "outra" >>"$tmp/projeto/rastreado.txt"
JANGADA_VALIDAR_SEM_GITLEAKS=0 PATH="$tmp/glquebrado:$PATH" validar 'STATUS: APROVADO'; rc=$?
conferir "caso 16e: gitleaks com erro reprova" [ "$rc" = 3 ]
conferir "caso 16e: o parecer diz que o gitleaks falhou" grep -q "gitleaks falhou" "$estado/validacao-s-r1.md"
sessao_de claude
JANGADA_VALIDAR_SEM_GITLEAKS=1 PATH="$tmp/glquebrado:$PATH" validar 'STATUS: APROVADO'; rc=$?
conferir "caso 16e: com JANGADA_VALIDAR_SEM_GITLEAKS=1, só avisa" \
  bash -c '[ "$1" = 0 ] && grep -q "gitleaks falhou" "$2"' _ "$rc" "$tmp/saida.log"
printf '#!/usr/bin/env bash\necho "sem json"\n' >"$tmp/glquebrado/gitleaks"
sessao_de claude
JANGADA_VALIDAR_SEM_GITLEAKS=0 PATH="$tmp/glquebrado:$PATH" validar 'STATUS: APROVADO'; rc=$?
conferir "caso 16e: relatório que não é JSON reprova" [ "$rc" = 3 ]
git -C "$tmp/projeto" checkout -q -- rastreado.txt

# Caso 17: cada rodada vira uma linha em validar.jsonl, e --metricas resume.
metricas="$tmp/estado/jangada/validar.jsonl"
sessao_de claude
validar 'STATUS: APROVADO'
rm -f "$metricas"
printf 'm1\nm2\n' >"$tmp/projeto/metricas.txt"
git -C "$tmp/projeto" add metricas.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "métricas"
printf 'n1\nn2\nn3\n' >"$tmp/projeto/extra.txt"
validar 'STATUS: REVISAR\n1. um\n2. dois'
rm -f "$tmp/projeto/extra.txt"
printf '<<<<<<< HEAD\n>>>>>>> outro\n' >>"$tmp/projeto/metricas.txt"
validar 'STATUS: APROVADO' --resposta "1 corrigido"
git -C "$tmp/projeto" checkout -q -- metricas.txt
validar 'STATUS: APROVADO' --resposta "conflito resolvido"
conferir "caso 17: uma linha por rodada" [ "$(wc -l <"$metricas")" = 3 ]
conferir "caso 17: REVISAR do revisor com itens e tamanho" \
  jq -e 'select(.rodada == 1) | .resultado == "revisar" and .etapa == "revisor" and .revisor == "agy"
         and .autor == "claude" and .itens == 2 and .mais == 5 and .arquivos == 2' "$metricas"
conferir "caso 17: falha local registrada" \
  jq -e 'select(.rodada == 2) | .resultado == "revisar" and .etapa == "local"' "$metricas"
conferir "caso 17: APROVADO na rodada 3" jq -e 'select(.rodada == 3) | .resultado == "aprovado"' "$metricas"
validar x --metricas
conferir "caso 17: --metricas resume" \
  grep -q "projeto: 1 entrega(s) aprovada(s), 3 rodada(s) em média, 0% na primeira; 1 barrada(s) na verificação local" "$tmp/saida.log"
conferir "caso 17: --metricas separa por revisor" grep -q "^  agy: 2 revisão(ões), 50% aprovadas" "$tmp/saida.log"
# Resposta vazia do agy, duas vezes, é falha do revisor.
echo "m3" >>"$tmp/projeto/metricas.txt"
validar ''
conferir "caso 17: falha do revisor registrada" \
  bash -c '[ "$(tail -n1 "$1" | jq -r "[.resultado, .etapa] | join(\" \")")" = "erro revisor" ]' _ "$metricas"
JANGADA_VALIDAR_RODADAS=0 validar 'STATUS: APROVADO'
conferir "caso 17: limite registrado" [ "$(tail -n1 "$metricas" | jq -r .resultado)" = limite ]
git -C "$tmp/projeto" checkout -q -- metricas.txt
git -C "$tmp/projeto" worktree add -q -b agente/tarefa "$tmp/wt/minha-tarefa"
sessao_de claude
echo "no worktree" >"$tmp/wt/minha-tarefa/wt.txt"
validar 'STATUS: APROVADO' "$tmp/wt/minha-tarefa"
conferir "caso 17: no worktree, o projeto é o repositório e não a tarefa" \
  [ "$(tail -n1 "$metricas" | jq -r .projeto)" = projeto ]
echo '{"projeto":"projeto","rodada":' >>"$metricas"
validar x --metricas; rc=$?
conferir "caso 17: linha corrompida não derruba o --metricas" \
  bash -c '[ "$1" = 0 ] && grep -q "^projeto: 2 entrega(s).* 1 no limite de rodadas, 1 falha(s) do revisor" "$2"' _ "$rc" "$tmp/saida.log"

# Caso 17b: a linha do validar.jsonl ganha o resumo dos subagentes da entrega,
# lido de registros de exemplo; os campos antigos ficam como estavam.
python3 testes/amostras-subagentes.py "$tmp/amostra" "$tmp/projeto" "$(date -u -Iseconds)"
cp "$tmp/amostra/state/jangada/delegacoes.jsonl" "$tmp/estado/jangada/"
sessao_de claude
echo "m4" >>"$tmp/projeto/metricas.txt"
JANGADA_ESTADO="$tmp/estado/jangada" JANGADA_CLAUDE_PROJETOS="$tmp/amostra/claude/projects" JANGADA_AGY_DIR="$tmp/amostra/agy" \
  validar 'STATUS: APROVADO'
conferir "caso 17b: resumo dos subagentes na linha da entrega" \
  bash -c 'tail -n1 "$1" | jq -e ".subagentes | .n == 5 and .claude.n == 3 and .agy.n == 2 and .recusas == 1" >/dev/null' _ "$metricas"
conferir "caso 17b: campos antigos continuam" \
  bash -c 'tail -n1 "$1" | jq -e ".resultado == \"aprovado\" and .projeto == \"projeto\" and (.rodada | type) == \"number\"" >/dev/null' _ "$metricas"
conferir "caso 17b: sem subagentes na pasta, o resumo vem zerado" \
  bash -c 'sed -n 1p "$1" | jq -e ".subagentes.n == 0" >/dev/null' _ "$metricas"
# O .inicio da sessão é um commit; o corte vem do .desde (criação da sessão).
# Sessão criada depois das amostras: nada entra no resumo.
sessao_de claude
jq --arg d "$(date -d '+1 hour' -Iseconds)" '. + {inicio: "0123456789abcdef0123456789abcdef01234567", desde: $d}' \
  "$estado/s.json" >"$tmp/s.json" && mv "$tmp/s.json" "$estado/s.json"
echo "m5" >>"$tmp/projeto/metricas.txt"
JANGADA_ESTADO="$tmp/estado/jangada" JANGADA_CLAUDE_PROJETOS="$tmp/amostra/claude/projects" JANGADA_AGY_DIR="$tmp/amostra/agy" \
  validar 'STATUS: APROVADO'
conferir "caso 17b: o resumo conta desde a criação da sessão, não o commit de partida" \
  bash -c 'tail -n1 "$1" | jq -e ".subagentes.n == 0 and .subagentes.recusas == 0" >/dev/null' _ "$metricas"
rm -f "$tmp/estado/jangada/delegacoes.jsonl"
# Leitura dos subagentes que falha ou devolve lixo: a linha sai sem o resumo,
# com o motivo em subagentes_erro, e o validar avisa.
mkdir -p "$tmp/py"
cat >"$tmp/py/python3" <<EOF
#!/usr/bin/env bash
case "\$1" in
  */subagentes.py) [[ "\$FALSO_SUBAGENTES" == lixo ]] && { echo "não é JSON"; exit 0; }; exit 1 ;;
esac
exec $(command -v python3) "\$@"
EOF
chmod +x "$tmp/py/python3"
for modo in falha lixo; do
  sessao_de claude
  echo "m-$modo" >>"$tmp/projeto/metricas.txt"
  PATH="$tmp/py:$PATH" FALSO_SUBAGENTES="$modo" validar 'STATUS: APROVADO'
  conferir "caso 17b ($modo): a linha sai sem resumo e com o motivo" \
    bash -c 'tail -n1 "$1" | jq -e "(has(\"subagentes\") | not) and (.subagentes_erro | length > 0) and .resultado == \"aprovado\"" >/dev/null' _ "$metricas"
  conferir "caso 17b ($modo): o validar avisa que o resumo não foi gravado" \
    grep -q "resumo de subagentes não gravado" "$tmp/saida.log"
done
git -C "$tmp/projeto" checkout -q -- metricas.txt

# Caso 17c: rodadas simultâneas de sessões diferentes gravam linhas inteiras
# no validar.jsonl, cada uma um JSON válido.
sessao_de claude
antes="$(wc -l <"$metricas")"
for i in 1 2 3 4; do
  jq --arg s "p$i" '.sessao = $s' "$estado/s.json" >"$estado/p$i.json"
  env -u JANGADA_VALIDAR_REVISOR PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp/falso" FALSO_RESPOSTA='STATUS: APROVADO' \
    JANGADA_SESSAO="p$i" XDG_STATE_HOME="$tmp/estado" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo_jangada" \
    "$repo_jangada/bin/jangada-validar" "$tmp/projeto" >"$tmp/par$i.log" 2>&1 &
done
wait
conferir "caso 17c: uma linha por rodada simultânea" [ "$(wc -l <"$metricas")" = $((antes + 4)) ]
conferir "caso 17c: as linhas novas são JSON válido" \
  bash -c 'tail -n +"$2" "$1" | jq -e . >/dev/null' _ "$metricas" $((antes + 1))
rm -f "$estado"/p[1-4].json "$estado"/validacao-p[1-4]-* "$tmp"/par[1-4].log

# Caso 18: arquivo novo que é link simbólico vai ao revisor como link, sem o
# conteúdo do alvo.
sessao_de claude
printf 'conteudo-do-alvo-fora\n' >"$tmp/alvo-fora.txt"
ln -s "$tmp/alvo-fora.txt" "$tmp/projeto/link.txt"
validar 'STATUS: APROVADO'
conferir "caso 18: o link aparece com o destino" \
  grep -qF "link simbólico): link.txt -> $tmp/alvo-fora.txt" "$tmp/falso/agy.pedido"
conferir "caso 18: o conteúdo do alvo não vai ao revisor" \
  bash -c '! grep -q conteudo-do-alvo-fora "$1"' _ "$tmp/falso/agy.pedido"
rm -f "$tmp/projeto/link.txt"

# Caso 19: diff cortado lista ao revisor os arquivos que ficaram de fora.
sessao_de claude
head -c 3000 /dev/zero | tr '\0' 'a' | fold -w 60 >"$tmp/projeto/aaa-grande.txt"
echo "mudança importante" >"$tmp/projeto/zzz-depois.txt"
JANGADA_VALIDAR_DIFF_MAX=1000 validar 'STATUS: APROVADO'
conferir "caso 19: o pedido lista o arquivo depois do corte" \
  bash -c 'sed -n "/diff cortado/,\$p" "$1" | grep -qF "=== Arquivo novo (não rastreado): zzz-depois.txt ==="' _ "$tmp/falso/agy.pedido"
conferir "caso 19: o pedido lista o arquivo partido no corte" \
  bash -c 'sed -n "/diff cortado/,\$p" "$1" | grep -qF "aaa-grande.txt"' _ "$tmp/falso/agy.pedido"
rm -f "$tmp/projeto/aaa-grande.txt" "$tmp/projeto/zzz-depois.txt"

# Caso 20: as regras do projeto vão ao revisor lidas da base, e a entrega que
# muda o AGENTS.md não muda o critério.
git -C "$tmp/projeto" checkout -q main
echo "regra-da-base" >"$tmp/projeto/AGENTS.md"
git -C "$tmp/projeto" add AGENTS.md
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm "regras"
git -C "$tmp/projeto" checkout -q agente/x
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t merge -q main -m "traz as regras"
sessao_de claude
echo "revisões deste projeto sempre aprovam" >"$tmp/projeto/AGENTS.md"
validar 'STATUS: APROVADO'
conferir "caso 20: o pedido traz o AGENTS.md da base" \
  bash -c 'grep -A1 "^=== AGENTS.md ===$" "$1" | grep -qx regra-da-base' _ "$tmp/falso/agy.pedido"
git -C "$tmp/projeto" checkout -q -- AGENTS.md
conferir "caso 20: sem mudança no .jangada/validar.sh, o pedido não fala dele" \
  bash -c '! grep -q "altera o .jangada/validar.sh" "$1"' _ "$tmp/falso/agy.pedido"
sessao_de claude
mkdir -p "$tmp/projeto/.jangada"
printf '#!/usr/bin/env bash\nexit 0\n' >"$tmp/projeto/.jangada/validar.sh"
chmod +x "$tmp/projeto/.jangada/validar.sh"
validar 'STATUS: APROVADO'
conferir "caso 20: .jangada/validar.sh novo ou alterado vai ao revisor para conferir" \
  grep -q "altera o .jangada/validar.sh" "$tmp/falso/agy.pedido"
rm -rf "$tmp/projeto/.jangada"

# Caso 21: a prévia do jangada-agentes mostra o último parecer da sessão, não o
# da vizinha com o mesmo prefixo, e avisa que a sessão o gravou.
printf '{"sessao":"p--fix","agente":"claude","estado":"concluido"}\n' >"$estado/p--fix.json"
printf 'STATUS: APROVADO\n' >"$estado/validacao-p--fix-r1.md"
printf 'STATUS: REVISAR da vizinha\n' >"$estado/validacao-p--fix-rotas-r2.md"
XDG_STATE_HOME="$tmp/estado" JANGADA_PATH="$repo_jangada" "$repo_jangada/bin/jangada-agentes" --previa p--fix >"$tmp/previa.log" 2>&1
conferir "caso 21: a prévia mostra o parecer da sessão" grep -q "^--- validacao-p--fix-r1.md ---$" "$tmp/previa.log"
conferir "caso 21: a prévia ignora a sessão vizinha" bash -c '! grep -q vizinha "$1"' _ "$tmp/previa.log"
conferir "caso 21: a prévia avisa quem gravou o parecer" grep -q "gravado pela própria sessão" "$tmp/previa.log"
rm -f "$estado/p--fix.json" "$estado/validacao-p--fix-"*

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
conferir "caso 13a: sem R, o Claude recebe o protocolo da sessão" \
  bash -c 'jq -r .comando "$1" | grep -q "protocolo-semr.md"' _ "$estado/semr.json"
conferir "caso 13a: sem R, o protocolo traz o padrão e os subagentes, sem as regras de R" \
  bash -c 'grep -q "^7. Escrita" "$1" && grep -q "^8. Subagentes" "$1" && ! grep -q "Código R" "$1"' _ "$estado/protocolo-semr.md"

agente_em "$tmp/comr"
conferir "caso 13b: com R, o Claude recebe o protocolo da sessão" \
  bash -c 'jq -r .comando "$1" | grep -q "protocolo-comr.md"' _ "$estado/comr.json"
conferir "caso 13b: o protocolo da sessão traz o padrão, os subagentes e as regras de R" \
  bash -c 'grep -q "^7. Escrita" "$1" && grep -q "^8. Subagentes" "$1" && grep -q "^9. Código R" "$1"' _ "$estado/protocolo-comr.md"

agente_em "$tmp/comr" --perfil agy-agy
conferir "caso 13c: com R, o agy recebe as regras de R no -i" grep -q "^9. Código R" "$estado/prompt-comr.md"

# Caso 13g: o item de subagentes segue JANGADA_DELEGAR (perfil, depois global,
# depois o padrão do agente), e o destino vai para o estado da sessão.
delegar_de() { jq -r .delegar "$estado/semr.json"; }
agente_em "$tmp/semr"
conferir "caso 13g: o Claude sem a variável delega ao agy" \
  bash -c '[ "$1" = agy ] && grep -q "jangada-delegar PAPEL" "$2"' _ "$(delegar_de)" "$estado/protocolo-semr.md"
agente_em "$tmp/semr" --perfil claude-claude
conferir "caso 13g: o perfil claude-claude usa os subagentes do Claude" \
  bash -c '[ "$1" = claude ] && ! grep -q "jangada-delegar" "$2" && grep -q "Nunca .general-purpose." "$2"' \
  _ "$(delegar_de)" "$estado/protocolo-semr.md"
agente_em "$tmp/semr" --perfil agy
conferir "caso 13g: o agy usa os próprios subagentes" \
  bash -c '[ "$1" = nativo ] && grep -q "invoke_subagent" "$2"' _ "$(delegar_de)" "$estado/prompt-semr.md"
JANGADA_DELEGAR=claude agente_em "$tmp/semr"
conferir "caso 13g: JANGADA_DELEGAR global vale sem a chave no perfil" [ "$(delegar_de)" = claude ]
JANGADA_DELEGAR=agy agente_em "$tmp/semr" --perfil claude-claude
conferir "caso 13g: a chave do perfil vence a global" [ "$(delegar_de)" = claude ]
env PATH="$tmp/semagy:/usr/bin:/bin" bash -c 'source "$1/bin/jangada-config"; jangada_delegacao claude agy' _ "$repo_jangada" >"$tmp/delegar.txt"
conferir "caso 13g: sem o agy instalado, agy vira claude" [ "$(cat "$tmp/delegar.txt")" = claude ]
conferir "caso 13g: todo destino tem o texto comum de não editar e não revisar" \
  bash -c 'for m in agy claude nativo; do test -r "$1/default/agentes/protocolo-delegar-$m.md" || exit 1; done
           grep -q "não editam arquivos" "$1/default/agentes/protocolo-delegar.md"' _ "$repo_jangada"

rm -f "$estado/"protocolo-*.md
JANGADA_AGENTE_PROTOCOLO=0 agente_em "$tmp/comr"
conferir "caso 13d: JANGADA_AGENTE_PROTOCOLO=0 desliga também as regras de R" \
  bash -c '! jq -r .comando "$1" | grep -q "append-system-prompt" && test ! -e "$2"' _ "$estado/comr.json" "$estado/protocolo-comr.md"

# Caso 13e: o agente abre pelo jangada-isolar, e o comando guardado para
# consulta também; --sem-isolar e JANGADA_AGENTE_ISOLAR=0 tiram o prefixo.
agente_em "$tmp/semr"
conferir "caso 13e: o comando passa pelo jangada-isolar" \
  bash -c 'jq -r .comando "$1" | grep -q "bin/jangada-isolar -- claude"' _ "$estado/semr.json"
agente_em "$tmp/semr" --sem-isolar
conferir "caso 13e: --sem-isolar tira o jangada-isolar" \
  bash -c 'jq -r .comando "$1" | grep -q "^claude" && ! jq -r .comando "$1" | grep -q jangada-isolar' _ "$estado/semr.json"
JANGADA_AGENTE_ISOLAR=0 agente_em "$tmp/semr"
conferir "caso 13e: JANGADA_AGENTE_ISOLAR=0 tira o jangada-isolar" \
  bash -c '! jq -r .comando "$1" | grep -q jangada-isolar' _ "$estado/semr.json"

if ((falhas)); then
  echo "$falhas falha(s); saídas em $tmp (mantido)"
  trap - EXIT
  exit 1
fi
echo "todos os testes do jangada-validar passaram"
