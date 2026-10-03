#!/usr/bin/env bash
# Testa a restauração de sessões (jangada-agentes --restaurar): o comando é
# recomposto de campos conferidos e da configuração, nunca lido do estado,
# que o agente isolado consegue gravar.
#
# O tmux é falso: o new-session guarda a pasta, e o send-keys roda o texto
# digitado num bash, como faria o shell da sessão. O jangada-isolar, o claude
# e o agy também são falsos e só registram como foram chamados.
#
# Uso: testes/restaurar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
estado="$tmp/state/jangada/agentes"
jp="$tmp/jangada"
log="$tmp/agente.log"
invadido="$tmp/invadido"
mkdir -p "$estado" "$tmp/bin" "$tmp/config/jangada/agentes" "$jp/bin" \
  "$tmp/projetos/proj" "$tmp/wt/proj/tarefa" "$tmp/fora" "$tmp/outro"
mkdir -p "$tmp/codex"
for pasta in "$tmp/projetos/proj" "$tmp/wt/proj/tarefa"; do
  printf '[projects."%s"]\ntrust_level = "trusted"\n' "$pasta" >>"$tmp/codex/config.toml"
done
ln -s "$repo_jangada/default" "$jp/default"
ln -s "$repo_jangada/bin/jangada-codex" "$jp/bin/jangada-codex"
ln -s "$repo_jangada/bin/jangada-hook-codex" "$jp/bin/jangada-hook-codex"
ln -s "$repo_jangada/bin/jangada-codex-hooks" "$jp/bin/jangada-codex-hooks"
ln -s "$repo_jangada/testes" "$jp/testes"
ln -s "$repo_jangada/bin/jangada-config" "$jp/bin/jangada-config"
cat >"$tmp/config/jangada/jangada.conf" <<EOF
JANGADA_PROJETOS=$tmp/projetos
JANGADA_WORKTREES=$tmp/wt
EOF
# Perfil do usuário que desliga o isolamento: o estado não pode escolhê-lo
# para sair do bwrap.
printf 'COMANDO=claude\nJANGADA_AGENTE_ISOLAR=0\nFALSO_PERFIL=1\n' >"$tmp/config/jangada/agentes/solto.conf"
# A instalação e um repositório fora das pastas de projeto são repositórios git.
git -C "$jp" init -q
git -C "$tmp/outro" init -q

cat >"$tmp/bin/tmux" <<'EOF'
#!/usr/bin/env bash
case " $* " in
  *" has-session "*) exit 1 ;;
  *" new-session "*)
    while (($#)); do
      case "$1" in
        -c) printf '%s\n' "$2" >"$FALSO_DIR/pasta"; shift 2 ;;
        -e) printf '%s\n' "$2" >>"$FALSO_DIR/ambiente"; shift 2 ;;
        *) shift ;;
      esac
    done
    ;;
  *" send-keys "*)
    texto="${*: -2:1}"
    printf '%s\n' "$texto" >>"$FALSO_DIR/digitado"
    (cd "$(cat "$FALSO_DIR/pasta")" && bash -c "$texto")
    ;;
esac
exit 0
EOF
for a in claude agy codex; do
  cat >"$tmp/bin/$a" <<EOF
#!/usr/bin/env bash
for arg in "\$@"; do
  if [[ "\$arg" == app-server ]]; then
    exec python3 "\$JANGADA_PATH/testes/falso-codex-hooks.py" "\$@"
  fi
done
if [[ "\${1:-}" == --help ]]; then echo --no-daemon; exit 0; fi
printf '%s|%s|%s%s\n' "\${FALSO_ISOLADO:-fora}" "\$PWD" "$a" "\$(printf ' %q' "\$@")" >>"\$FALSO_LOG"
EOF
done
cat >"$jp/bin/jangada-isolar" <<'EOF'
#!/usr/bin/env bash
[[ "$1" == -- ]] && shift
FALSO_ISOLADO=isolado JANGADA_ISOLADO=1 JANGADA_MARCA_ISOLADO=/ exec "$@"
EOF
chmod +x "$tmp/bin/"* "$jp/bin/jangada-isolar"

uuid=0123abcd-4567-89ab-cdef-0123456789ab
# restaurar JSON [env extra...]: grava o estado da sessão "s" e restaura.
restaurar() {
  rm -f "$log" "$tmp/pasta" "$tmp/ambiente" "$tmp/digitado" "$invadido" "$estado/s.json"
  jq -n --arg dir "$tmp/projetos/proj" --argjson extra "$1" \
    '{sessao:"s", dir:$dir, agente:"claude", estado:"interrompido",
      atualizado:(now | todate)} + $extra' >"$estado/s.json"
  env -u TMUX -u JANGADA_ISOLADO -u JANGADA_AGENTE_ISOLAR -u JANGADA_DELEGAR -u JANGADA_VALIDAR_REVISOR \
    PATH="$tmp/bin:$PATH" FALSO_DIR="$tmp" FALSO_LOG="$log" CODEX_HOME="$tmp/codex" \
    XDG_STATE_HOME="$tmp/state" XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$jp" \
    "${@:2}" "$repo_jangada/bin/jangada-agentes" --restaurar s >"$tmp/saida" 2>&1
}
linha() { cat "$log" 2>/dev/null; }
nada_rodou() { [[ ! -e "$log" && ! -e "$tmp/digitado" && ! -e "$invadido" ]]; }

# Caso 1: estado legítimo do Claude volta isolado, na pasta, na conversa e
# com o protocolo refeito.
restaurar "{\"conversa\":\"$uuid\"}"
conferir "caso 1: o Claude abre isolado na pasta do projeto" \
  bash -c '[[ "$(cut -d"|" -f1,2 "$1")" == "isolado|$2" ]]' _ "$log" "$tmp/projetos/proj"
conferir "caso 1: retoma a conversa e recebe o protocolo" \
  bash -c 'grep -q -- "--resume $2" "$1" && grep -q -- "--append-system-prompt" "$1" && grep -q "Subagentes" "$1"' _ "$log" "$uuid"
conferir "caso 1: o estado passa a iniciado" [ "$(jq -r .estado "$estado/s.json")" = iniciado ]

# Caso 2: comando com um segundo comando depois do ";". O .comando é ignorado.
restaurar "{\"conversa\":\"$uuid\", \"comando\":\"claude; touch $invadido #\"}"
conferir "caso 2: o comando gravado no estado não roda" [ ! -e "$invadido" ]
conferir "caso 2: a sessão abre com o comando recomposto" grep -q "^isolado|.*claude .*--resume $uuid" "$log"

# Caso 3: .isolar falso no estado não tira o isolamento.
restaurar '{"isolar":false, "comando":"claude"}'
conferir "caso 3: isolar:false no estado é ignorado" grep -q '^isolado|' "$log"

# Caso 4: só a configuração do usuário desliga o isolamento.
restaurar '{}' JANGADA_AGENTE_ISOLAR=0
conferir "caso 4: JANGADA_AGENTE_ISOLAR=0 abre fora do jangada-isolar" \
  bash -c 'grep -q "^fora|" "$1" && ! grep -q jangada-isolar "$2"' _ "$log" "$tmp/digitado"

# Caso 5: campos que não passam na conferência: recusa sem rodar nada.
restaurar "{\"agente\":\"claude; touch $invadido #\"}"
conferir "caso 5: agente com comando anexado é recusado" nada_rodou
restaurar '{"agente":"bash"}'
conferir "caso 5: agente fora da lista é recusado" nada_rodou
restaurar "{\"conversa\":\"x; touch $invadido #\"}"
conferir "caso 5: id de conversa inválido é recusado" nada_rodou
conferir "caso 5: a recusa diz o motivo" grep -q "id de conversa inválido" "$tmp/saida"
restaurar "{\"dir\":\"$tmp/fora\"}"
conferir "caso 5: pasta fora dos projetos e sem git é recusada" nada_rodou
restaurar "{\"dir\":\"$jp\"}"
conferir "caso 5: a instalação do jangada é recusada, mesmo sendo repositório git" nada_rodou
restaurar "{\"dir\":\"$tmp/projetos/proj/../../fora\"}"
conferir "caso 5: .. no caminho não escapa da conferência" nada_rodou
restaurar '{"perfil":"../../x"}'
conferir "caso 5: perfil com caminho é recusado" nada_rodou
restaurar '{"revisor":"sh -c x"}'
conferir "caso 5: revisor fora da lista é recusado" nada_rodou

# Caso 6: perfil do usuário com JANGADA_AGENTE_ISOLAR=0 escolhido pelo estado.
restaurar '{"perfil":"solto"}'
conferir "caso 6: o perfil não desliga o isolamento na restauração" grep -q '^isolado|' "$log"
conferir "caso 6: o resto do ambiente do perfil vale" \
  bash -c 'grep -qx FALSO_PERFIL=1 "$1" && ! grep -q "^JANGADA_AGENTE_ISOLAR=" "$1"' _ "$tmp/ambiente"

# Caso 7: agy pelo perfil: argumentos do perfil e a mesma conversa.
restaurar "{\"agente\":\"agy\", \"perfil\":\"agy\", \"conversa\":\"$uuid\", \"comando\":\"agy --yolo\"}"
conferir "caso 7: o agy volta com os argumentos do perfil e a conversa" \
  grep -qx "isolado|$tmp/projetos/proj|agy --effort high --conversation $uuid" "$log"

# Caso 8: worktree sem id de conversa usa --continue.
restaurar "{\"dir\":\"$tmp/wt/proj/tarefa\", \"worktree\":\"$tmp/wt/proj/tarefa\"}"
conferir "caso 8: worktree sem id retoma com --continue" grep -q "^isolado|$tmp/wt/proj/tarefa|claude .*--continue" "$log"

# Caso 9: repositório git fora das pastas de projeto continua restaurável.
restaurar "{\"dir\":\"$tmp/outro\"}"
conferir "caso 9: repositório git fora de JANGADA_PROJETOS restaura" grep -q "^isolado|$tmp/outro|" "$log"

# Caso 10: link simbólico plantado no lugar do protocolo é trocado, não seguido.
echo "SEGREDO-PLANTADO-42" >"$tmp/segredo"
ln -sf "$tmp/segredo" "$estado/protocolo-s.md"
restaurar '{}'
conferir "caso 10: o protocolo é refeito das fontes" \
  bash -c '[[ ! -L "$1" ]] && ! grep -q SEGREDO-PLANTADO "$2" && grep -q SEGREDO-PLANTADO "$3"' _ "$estado/protocolo-s.md" "$log" "$tmp/segredo"

restaurar "{\"agente\":\"codex\", \"perfil\":\"codex-codex\", \"revisor\":\"codex\", \"conversa\":\"$uuid\", \"isolar\":false}"
conferir "caso 11: Codex retoma isolado com UUID e revisor Codex" \
  bash -c 'grep -q "^isolado|.*codex .*--no-daemon.*resume $2" "$1" && grep -qx JANGADA_VALIDAR_REVISOR=codex "$3"' _ "$log" "$uuid" "$tmp/ambiente"
conferir "caso 11: protocolo de delegação do Codex refeito" grep -q 'Não tente chamar subagentes do Claude' "$estado/protocolo-s.md"
restaurar "{\"agente\":\"codex\", \"dir\":\"$tmp/wt/proj/tarefa\", \"worktree\":\"$tmp/wt/proj/tarefa\"}"
conferir "caso 12: Codex sem UUID no worktree retoma por pasta" grep -q 'resume --last' "$log"
restaurar '{"agente":"codex"}'
conferir "caso 13: Codex direto sem UUID abre conversa nova" \
  bash -c 'test -s "$1" && ! grep -q "resume" "$1"' _ "$log"

mv "$tmp/bin/agy" "$tmp/agy-guardado"
rm -f "$estado/protocolo-s.md"
restaurar '{}' env PATH="$tmp/bin:/usr/bin:/bin"
conferir "caso 14: sem revisor, restauração preserva o protocolo" \
  bash -c 'grep -q "append-system-prompt" "$1" && grep -q "^7. Escrita" "$2"' _ "$log" "$estado/protocolo-s.md"
conferir "caso 14: sem revisor, restauração avisa" grep -q 'revisão indisponível' "$tmp/saida"
mv "$tmp/agy-guardado" "$tmp/bin/agy"

if ((falhas)); then
  echo "$falhas falha(s); saídas em $tmp (mantido)"
  trap - EXIT
  exit 1
fi
echo "todos os testes da restauração passaram"
