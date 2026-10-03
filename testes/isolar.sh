#!/usr/bin/env bash
# Testa o jangada-isolar. A parte que roda o bwrap de verdade se pula onde ele
# não consegue criar o namespace (alguns contêineres).
#
# Uso: testes/isolar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp" /tmp/isolar-teste' EXIT
rm -f /tmp/isolar-teste
marca_teste="$tmp/.jangada-isolado-teste"
casa="$tmp/casa"
mkdir -p "$casa/.ssh" "$casa/.claude" "$casa/extra" "$casa/.cache/yay/pacote" "$casa/.cache/cliphist" \
  "$casa/.gemini/antigravity-cli/bin" "$tmp/config/jangada"
echo "exec agy" >"$casa/.gemini/antigravity-cli/bin/agentapi"
echo "senha copiada" >"$casa/.cache/cliphist/db"
echo "chave" >"$casa/.ssh/id_teste"
echo "senha" >"$casa/.netrc"
echo "senha" >"$casa/.pgpass"
mkdir -p "$casa/.config/gcloud"
echo "{}" >"$casa/.claude.json"
git init -q -b main "$tmp/repo"
git -C "$tmp/repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio
git -C "$tmp/repo" worktree add -q -b agente/t "$tmp/wt"

isolar() {
  (cd "$1" && env -u JANGADA_SESSAO -u CODEX_HOME -u XDG_CACHE_HOME -u JANGADA_ISOLADO HOME="$casa" XDG_STATE_HOME="$casa/.local/state" XDG_CONFIG_HOME="$tmp/config" \
    JANGADA_PATH="$repo_jangada" JANGADA_MARCA_ISOLADO="$marca_teste" "${@:2}")
}
mostrar() { isolar "$tmp/wt" "$@" "$repo_jangada/bin/jangada-isolar" --mostrar -- true >"$tmp/args"; }
seguidos() { grep -A2 -xF -- "$1" "$tmp/args" | paste -sd' ' | grep -qF -- "$1 $2 $3"; }

# Caso 1: a chamada ao bwrap.
mostrar
conferir "caso 1: a pasta é gravável" seguidos --bind "$tmp/wt" "$tmp/wt"
conferir "caso 1: o .git comum do worktree é somente leitura" seguidos --ro-bind "$tmp/repo/.git" "$tmp/repo/.git"
conferir "caso 1: objetos do git graváveis" seguidos --bind "$tmp/repo/.git/objects" "$tmp/repo/.git/objects"
conferir "caso 1: das refs, só a pasta do ramo e a das cópias são graváveis" \
  bash -c 'for d in refs/heads/agente refs/heads/backup logs/refs/heads/agente logs/refs/heads/backup; do
    grep -A2 -xF -- --bind "$1" | paste -sd" " | grep -qF -- "--bind $2/$d $2/$d" || exit 1; done' _ "$tmp/args" "$tmp/repo/.git"
conferir "caso 1: refs e logs inteiros não são graváveis" \
  bash -c 'for d in refs logs refs/heads; do ! grep -qxF -- "$2/$d" "$1" || exit 1; done' _ "$tmp/args" "$tmp/repo/.git"
conferir "caso 1: pasta do worktree no .git gravável" \
  seguidos --bind "$tmp/repo/.git/worktrees/wt" "$tmp/repo/.git/worktrees/wt"
conferir "caso 1: commondir do worktree somente leitura" \
  seguidos --ro-bind "$tmp/repo/.git/worktrees/wt/commondir" "$tmp/repo/.git/worktrees/wt/commondir"
conferir "caso 1: gitdir do worktree somente leitura" \
  seguidos --ro-bind "$tmp/repo/.git/worktrees/wt/gitdir" "$tmp/repo/.git/worktrees/wt/gitdir"
conferir "caso 1: namespace de PID próprio" grep -qxF -- --unshare-pid "$tmp/args"
conferir "caso 1: morre com o processo pai" grep -qxF -- --die-with-parent "$tmp/args"
conferir "caso 1: sem Hyprland, Wayland nem X no ambiente" \
  bash -c 'grep -qxF HYPRLAND_INSTANCE_SIGNATURE "$1" && grep -qxF WAYLAND_DISPLAY "$1" && grep -qxF DISPLAY "$1"' _ "$tmp/args"
conferir "caso 1: settings.json do Claude somente leitura" \
  seguidos --ro-bind "$casa/.claude/settings.json" "$casa/.claude/settings.json"
conferir "caso 1: settings.json ausente vira {}" [ "$(cat "$casa/.claude/settings.json")" = "{}" ]
conferir "caso 1: skills do Claude somente leitura" seguidos --ro-bind "$casa/.claude/skills" "$casa/.claude/skills"
conferir "caso 1: clones do yay somente leitura" seguidos --ro-bind "$casa/.cache/yay" "$casa/.cache/yay"
conferir "caso 1: arquivo .git do worktree somente leitura" seguidos --ro-bind "$tmp/wt/.git" "$tmp/wt/.git"
conferir "caso 1: ~/.ssh oculto" seguidos --tmpfs "$casa/.ssh" ""
conferir "caso 1: ~/.netrc oculto" seguidos --ro-bind /dev/null "$casa/.netrc"
conferir "caso 1: ~/.pgpass oculto" seguidos --ro-bind /dev/null "$casa/.pgpass"
conferir "caso 1: credenciais do gcloud ocultas" seguidos --tmpfs "$casa/.config/gcloud" ""
conferir "caso 1: variáveis de credencial não entram" \
  bash -c 'for v in GH_TOKEN GITHUB_TOKEN AWS_SECRET_ACCESS_KEY VAULT_TOKEN; do
    grep -A1 -xF -- --unsetenv "$1" | grep -qxF "$v" || exit 1; done' _ "$tmp/args"
conferir "caso 1: /tmp próprio" seguidos --tmpfs /tmp ""
conferir "caso 1: marca do isolamento montada no /tmp próprio" \
  seguidos --ro-bind /dev/null "$marca_teste"
conferir "caso 1: histórico da área de transferência oculto" seguidos --tmpfs "$casa/.cache/cliphist" ""
conferir "caso 1: token do painel oculto" seguidos --tmpfs "$casa/.local/state/jangada/painel-chave" ""
conferir "caso 1: a pasta do token existe antes do agente, só para o dono" \
  [ "$(stat -c %a "$casa/.local/state/jangada/painel-chave" 2>/dev/null)" = 700 ]
conferir "caso 1: revisões feitas fora do isolamento ocultas" \
  seguidos --tmpfs "$casa/.local/state/jangada/revisoes" ""
conferir "caso 1: a pasta das revisões existe antes do agente, só para o dono" \
  [ "$(stat -c %a "$casa/.local/state/jangada/revisoes" 2>/dev/null)" = 700 ]
conferir "caso 1: termina com o comando" [ "$(tail -n1 "$tmp/args")" = true ]
conferir "caso 1: estado dos agentes gravável" \
  seguidos --bind "$casa/.local/state/jangada/agentes" "$casa/.local/state/jangada/agentes"
conferir "caso 1: métricas do validar graváveis" \
  seguidos --bind "$casa/.local/state/jangada/validar.jsonl" "$casa/.local/state/jangada/validar.jsonl"
conferir "caso 1: histórico de estados gravável" \
  seguidos --bind "$casa/.local/state/jangada/eventos-agentes.jsonl" "$casa/.local/state/jangada/eventos-agentes.jsonl"
conferir "caso 1: registro de delegações gravável" \
  seguidos --bind "$casa/.local/state/jangada/delegacoes.jsonl" "$casa/.local/state/jangada/delegacoes.jsonl"
conferir "caso 1: trava local gravável" \
  seguidos --bind "$casa/.local/state/jangada/local.lock" "$casa/.local/state/jangada/local.lock"
conferir "caso 1: dispositivos de GPU não expostos" \
  bash -c '! grep -E -q "/dev/nvidia|/dev/dri" "$1"' _ "$tmp/args"
conferir "caso 1: o resto do estado não é gravável" \
  bash -c '! grep -qxF "$1" "$2"' _ "$casa/.local/state/jangada" "$tmp/args"
conferir "caso 1: fora do tmux e do agente SSH" \
  bash -c 'grep -qxF TMUX "$1" && grep -qxF SSH_AUTH_SOCK "$1" && ! grep -q "tmux-" "$1"' _ "$tmp/args"
conferir "caso 1: pasta ausente não entra" bash -c '! grep -qxF "$1" "$2"' _ "$casa/.cache/paru" "$tmp/args"
conferir "caso 1: bin do agy em camada temporária ou somente leitura" bash -c \
  'grep -A1 -xF -- --tmp-overlay "$2" | grep -qxF "$1" || grep -A1 -xF -- --ro-bind "$2" | grep -qxF "$1"' \
  _ "$casa/.gemini/antigravity-cli/bin" "$tmp/args"
grep -A1 -xF -- --tmp-overlay "$tmp/args" | grep -qxF "$casa/.gemini/antigravity-cli/bin" && sobreposicao=1 || sobreposicao=0

# Casa mínima: a pasta pessoal some e volta só o que está na lista.
conferir "caso 1: sem a opção, a pasta pessoal não é esvaziada" bash -c '! grep -A1 -xF -- --tmpfs "$1" | grep -qxF "$2"' _ "$tmp/args" "$casa"
mostrar JANGADA_ISOLAR_CASA=minima JANGADA_ISOLAR_CASA_LER="$casa/extra"
conferir "casa mínima: a pasta pessoal vira pasta vazia" seguidos --tmpfs "$casa" ""
conferir "casa mínima: o .claude.json volta somente leitura" seguidos --ro-bind "$casa/.claude.json" "$casa/.claude.json"
conferir "casa mínima: JANGADA_ISOLAR_CASA_LER volta somente leitura" seguidos --ro-bind "$casa/extra" "$casa/extra"
conferir "casa mínima: a pasta vazia vem antes das outras montagens" \
  bash -c '[ "$(grep -n -xF -- "$2" "$1" | head -n1 | cut -d: -f1)" -lt "$(grep -n -xF -- "$3" "$1" | head -n1 | cut -d: -f1)" ]' \
  _ "$tmp/args" "$casa" "$tmp/wt"

# Sem a sobreposição (bwrap que a recusa), nada do que seria temporário fica
# gravável no disco.
mkdir -p "$tmp/bwrap-sem-overlay"
printf '#!/bin/sh\nexit 1\n' >"$tmp/bwrap-sem-overlay/bwrap"
chmod +x "$tmp/bwrap-sem-overlay/bwrap"
mostrar PATH="$tmp/bwrap-sem-overlay:$PATH"
conferir "caso 1: sem sobreposição, nenhuma camada temporária" bash -c '! grep -qxF -- --tmp-overlay "$1"' _ "$tmp/args"
for d in "$casa/.cache" "$casa/.claude/shell-snapshots" "$casa/.claude/session-env" "$casa/.claude/ide"; do
  conferir "caso 1: sem sobreposição, ${d#"$casa"/} vazio em memória" seguidos --tmpfs "$d" ""
  conferir "caso 1: sem sobreposição, ${d#"$casa"/} não é gravável no disco" bash -c '! grep -A2 -xF -- --bind "$2" | paste -sd" " | grep -qF -- "--bind $1 $1"' _ "$d" "$tmp/args"
done
conferir "caso 1: sem sobreposição, bin do agy somente leitura" \
  seguidos --ro-bind "$casa/.gemini/antigravity-cli/bin" "$casa/.gemini/antigravity-cli/bin"

mostrar JANGADA_ISOLAR_ESCRITA="$casa/extra:"
conferir "caso 1: JANGADA_ISOLAR_ESCRITA acrescenta gravável" seguidos --bind "$casa/extra" "$casa/extra"
mostrar JANGADA_ISOLAR_OCULTAR=
conferir "caso 1: JANGADA_ISOLAR_OCULTAR vazio não oculta a lista padrão" bash -c '! grep -qxF "$1" "$2"' _ "$casa/.ssh" "$tmp/args"
conferir "caso 1: JANGADA_ISOLAR_OCULTAR vazio ainda oculta o token do painel" \
  seguidos --tmpfs "$casa/.local/state/jangada/painel-chave" ""
conferir "caso 1: JANGADA_ISOLAR_OCULTAR vazio ainda oculta as revisões" \
  seguidos --tmpfs "$casa/.local/state/jangada/revisoes" ""

# Caso 1b: repositório principal (--direto).
isolar "$tmp/repo" "$repo_jangada/bin/jangada-isolar" --mostrar -- true >"$tmp/args"
conferir "caso 1b: o .git principal é gravável" seguidos --bind "$tmp/repo/.git" "$tmp/repo/.git"
conferir "caso 1b: commondir criado apontando para o próprio .git" [ "$(cat "$tmp/repo/.git/commondir")" = . ]
conferir "caso 1b: commondir somente leitura" seguidos --ro-bind "$tmp/repo/.git/commondir" "$tmp/repo/.git/commondir"
conferir "caso 1b: config do git somente leitura" seguidos --ro-bind "$tmp/repo/.git/config" "$tmp/repo/.git/config"
conferir "caso 1b: hooks do git somente leitura" seguidos --ro-bind "$tmp/repo/.git/hooks" "$tmp/repo/.git/hooks"
conferir "caso 1b: worktrees somente leitura" seguidos --ro-bind "$tmp/repo/.git/worktrees" "$tmp/repo/.git/worktrees"
conferir "caso 1b: o git segue funcionando com o commondir" git -C "$tmp/repo" status --porcelain

# Caso 2: desligado, roda o comando direto.
saida="$(isolar "$tmp/wt" JANGADA_AGENTE_ISOLAR=0 "$repo_jangada/bin/jangada-isolar" -- sh -c 'echo "${JANGADA_ISOLADO:-fora}"')"
conferir "caso 2: JANGADA_AGENTE_ISOLAR=0 não isola" [ "$saida" = fora ]
echo "JANGADA_AGENTE_ISOLAR=0" >"$tmp/config/jangada/jangada.conf"
saida="$(isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- sh -c 'echo "${JANGADA_ISOLADO:-fora}"')"
conferir "caso 2: jangada.conf desliga" [ "$saida" = fora ]
rm -f "$tmp/config/jangada/jangada.conf"
# JANGADA_ISOLADO herdado, sem a marca que só o bwrap monta, não basta.
mostrar JANGADA_ISOLADO=1
conferir "caso 2: JANGADA_ISOLADO sem a marca não dispensa o isolamento" [ "$(head -n1 "$tmp/args")" = bwrap ]
: >"$marca_teste" 2>/dev/null
conferir "caso 2: arquivo comum no lugar da marca não vale" \
  bash -c '! awk -v m="$1" '"'"'$5 == m { a = 1 } END { exit !a }'"'"' /proc/self/mountinfo' _ "$marca_teste"
rm -f "$marca_teste"

# Caso 2b: sem o bwrap, recusa em vez de rodar sem isolamento.
sem_bwrap="$tmp/sem-bwrap"
mkdir -p "$sem_bwrap"
IFS=: read -ra dirs_path <<<"$PATH"
for d in "${dirs_path[@]}"; do
  for f in "$d"/*; do
    n="${f##*/}"
    [[ "$n" == bwrap || -e "$sem_bwrap/$n" || ! -x "$f" ]] || ln -s "$f" "$sem_bwrap/$n"
  done
done
saida="$(isolar "$tmp/wt" PATH="$sem_bwrap" "$repo_jangada/bin/jangada-isolar" -- sh -c 'echo rodou' 2>"$tmp/erro")"
rc=$?
conferir "caso 2b: sem bwrap, não roda o comando" [ -z "$saida" ]
conferir "caso 2b: sem bwrap, sai com erro" [ "$rc" -ne 0 ]
conferir "caso 2b: sem bwrap, indica o --sem-isolar" grep -q -- --sem-isolar "$tmp/erro"
saida="$(isolar "$tmp/wt" PATH="$sem_bwrap" JANGADA_AGENTE_ISOLAR=0 "$repo_jangada/bin/jangada-isolar" -- sh -c 'echo rodou')"
conferir "caso 2b: sem bwrap e desligado, roda direto" [ "$saida" = rodou ]

# Caso 3: o isolamento de verdade.
mkdir -p "$casa/.codex/skills"
printf 'model = "modelo-teste"\n' >"$casa/.codex/config.toml"
printf '\n[projects."%s"]\ntrust_level = "trusted"\n' "$tmp/wt" >>"$casa/.codex/config.toml"
printf '{"token":"FALSO-LOGIN"}\n' >"$casa/.codex/auth.json"
isolar "$tmp/wt" JANGADA_SESSAO=teste-codex "$repo_jangada/bin/jangada-isolar" --mostrar -- \
  "$repo_jangada/bin/jangada-codex" -- codex >"$tmp/args"
conferir "caso Codex: execução em dados próprios da sessão" \
  seguidos --bind "$casa/.local/state/jangada/codex/teste-codex" "$casa/.codex"
conferir "caso Codex: configuração global somente leitura" \
  seguidos --ro-bind "$casa/.codex/config.toml" "$casa/.codex/config.toml"
conferir "caso Codex: login somente leitura" seguidos --ro-bind "$casa/.codex/auth.json" "$casa/.codex/auth.json"
conferir "caso Codex: skills somente leitura" seguidos --ro-bind "$casa/.codex/skills" "$casa/.codex/skills"
conferir "caso Codex: configuração ausente não vem do estado" \
  seguidos --ro-bind /dev/null "$casa/.codex/requirements.toml"
conferir "caso Codex: SQLite usa dados da sessão" seguidos --setenv CODEX_SQLITE_HOME "$casa/.codex"
conferir "caso Codex: pasta de dados não exposta por fora" \
  bash -c '! grep -A2 -xF -- --bind "$1" | grep -qFx "$2"' _ "$tmp/args" "$casa/.local/state/jangada/codex"
ln -s "$casa/.ssh" "$casa/.local/state/jangada/codex/link"
isolar "$tmp/wt" JANGADA_SESSAO=link "$repo_jangada/bin/jangada-isolar" --mostrar -- \
  "$repo_jangada/bin/jangada-codex" -- codex >"$tmp/saida" 2>"$tmp/erro"
conferir "caso Codex: link no lugar dos dados é recusado" [ "$?" != 0 ]
for nome_invalido in . ..; do
  isolar "$tmp/wt" JANGADA_SESSAO="$nome_invalido" "$repo_jangada/bin/jangada-isolar" --mostrar -- \
    "$repo_jangada/bin/jangada-codex" -- codex >"$tmp/saida" 2>"$tmp/erro"
  conferir "caso Codex: sessão $nome_invalido é recusada" [ "$?" != 0 ]
done

if bwrap --ro-bind / / --dev /dev --proc /proc true 2>/dev/null; then
  # O programa falso grava dados e testa as montagens no mesmo processo do CLI.
  mkdir -p "$tmp/wt/codex-bin"
  cat >"$tmp/wt/codex-bin/codex" <<'EOF'
#!/usr/bin/env bash
for arg in "$@"; do
  if [[ "$arg" == app-server ]]; then
    exec python3 "$JANGADA_PATH/testes/falso-codex-hooks.py" "$@"
  fi
done
if [[ "${1:-}" == --help ]]; then echo --no-daemon; exit 0; fi
printf 'conversa\n' >"$HOME/.codex/historico-teste"
grep -q 'modelo-teste' "$HOME/.codex/config.toml" || exit 1
grep -q 'FALSO-LOGIN' "$HOME/.codex/auth.json" || exit 1
! echo 'configuração adulterada' >"$HOME/.codex/config.toml" || exit 1
! echo 'login adulterado' >"$HOME/.codex/auth.json" || exit 1
! touch "$HOME/.codex/skills/invadido" || exit 1
[[ "$(cat "$HOME/.codex/historico-teste")" == conversa ]]
EOF
  chmod +x "$tmp/wt/codex-bin/codex"
  isolar "$tmp/wt" JANGADA_AGENTE_ISOLAR=0 JANGADA_SESSAO=teste-codex "$repo_jangada/bin/jangada-isolar" -- \
    "$repo_jangada/bin/jangada-codex" -- "$tmp/wt/codex-bin/codex" >"$tmp/codex.log" 2>&1
  conferir "caso Codex real: dados graváveis e configuração protegida" [ "$?" = 0 ]
  conferir "caso Codex real: histórico persiste no estado" test -f "$casa/.local/state/jangada/codex/teste-codex/historico-teste"
  conferir "caso Codex real: histórico não contamina pasta global" test ! -e "$casa/.codex/historico-teste"
  isolar "$tmp/wt" JANGADA_AGENTE_ISOLAR=0 JANGADA_SESSAO=teste-revisor "$repo_jangada/bin/jangada-isolar" -- \
    "$repo_jangada/bin/jangada-codex" --revisar -- "$tmp/wt/codex-bin/codex" >"$tmp/codex-revisor.log" 2>&1
  conferir "caso Codex real: revisor isolado mesmo com isolamento global desligado" [ "$?" = 0 ]
  conferir "caso Codex real: revisor grava apenas no próprio estado" test -f "$casa/.local/state/jangada/codex/teste-revisor/historico-teste"
  conferir "caso Codex real: revisor não grava na pasta global" test ! -e "$casa/.codex/historico-teste"
  roda() { isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- bash -c "$1" >/dev/null 2>&1; }
  conferir "caso 3: grava na pasta" roda 'echo a >dentro.txt'
  conferir "caso 3: o arquivo chega ao disco" test -f "$tmp/wt/dentro.txt"
  conferir "caso 3: commit no worktree" \
    roda 'git add dentro.txt && git -c user.name=t -c user.email=t@t commit -qm dentro'
  conferir "caso 3: o commit chega ao repositório" git -C "$tmp/repo" rev-parse --verify -q agente/t~1 >/dev/null
  conferir "caso 3: o agente não move o main" roda '! git update-ref refs/heads/main HEAD'
  conferir "caso 3: o main segue onde estava" \
    [ "$(git -C "$tmp/repo" rev-parse main)" = "$(git -C "$tmp/repo" rev-parse agente/t~1)" ]
  conferir "caso 3: o agente não cria tag" roda '! git tag v-teste'
  conferir "caso 3: o agente não grava o stash" roda '! git update-ref refs/stash HEAD'
  conferir "caso 3: ramo de cópia em backup/ é criado" roda 'git branch backup/copia HEAD'
  roda "echo x >'$casa/fora.txt'"
  conferir "caso 3: gravação na HOME não chega ao disco" test ! -e "$casa/fora.txt"
  conferir "caso 3: chave oculta" roda "! test -e '$casa/.ssh/id_teste' && ! grep -q senha '$casa/.netrc'"
  conferir "caso 3: variável de credencial não chega ao agente" \
    isolar "$tmp/wt" GH_TOKEN=segredo ANTHROPIC_API_KEY=chave "$repo_jangada/bin/jangada-isolar" -- \
    bash -c '[[ -z "${GH_TOKEN:-}" && "$ANTHROPIC_API_KEY" == chave ]]'
  conferir "caso 3: hook do git não é gravável" roda "! echo x >'$tmp/repo/.git/hooks/pre-commit'"
  conferir "caso 3: config do git não é gravável" roda '! git config --local user.x y'
  conferir "caso 3: arquivo .git do worktree não é gravável" roda '! echo "gitdir: /x" >.git'
  roda "echo x >'$casa/.local/state/jangada/agentes/teste'"
  conferir "caso 3: estado dos agentes é gravável" test -f "$casa/.local/state/jangada/agentes/teste"
  roda "echo x >'$casa/.local/state/jangada/outro'"
  conferir "caso 3: o resto do estado não é gravável" test ! -e "$casa/.local/state/jangada/outro"
  export TMUX=x SSH_AUTH_SOCK=y
  conferir "caso 3: sem TMUX nem SSH_AUTH_SOCK" roda '[ -z "${TMUX:-}${SSH_AUTH_SOCK:-}" ]'
  unset TMUX SSH_AUTH_SOCK
  # A casa do teste fica no /tmp, e o /tmp do isolamento é gravável: confere
  # o arquivo de verdade, do lado de fora.
  roda "echo x >>'$casa/.claude.json'"
  conferir "caso 3: ~/.claude.json não muda" [ "$(cat "$casa/.claude.json")" = "{}" ]
  roda 'echo x >/tmp/isolar-teste'
  conferir "caso 3: o /tmp do agente é próprio" test ! -e /tmp/isolar-teste

  # Ataque do commondir: um config plantado com core.fsmonitor rodaria no
  # próximo git status de fora.
  marca="$tmp/PWNED"
  planta="c=\$(git rev-parse --path-format=absolute --git-common-dir); mkdir -p \"\$c/mal\"
    printf '[core]\\n\\tfsmonitor = \"touch $marca; false\"\\n' >\"\$c/mal/config\""
  conferir "caso 3: commondir do worktree não é gravável" \
    roda "$planta; ! echo ../../mal >\"\$c/worktrees/wt/commondir\""
  conferir "caso 3: commondir do .git principal não é criado pelo worktree" \
    roda "! echo mal >\"\$(git rev-parse --path-format=absolute --git-common-dir)/commondir\""
  git -C "$tmp/wt" status >/dev/null 2>&1
  git -C "$tmp/repo" status >/dev/null 2>&1
  conferir "caso 3: git status de fora não roda o fsmonitor plantado" test ! -e "$marca"
  rodap() { isolar "$tmp/repo" "$repo_jangada/bin/jangada-isolar" -- bash -c "$1" >/dev/null 2>&1; }
  conferir "caso 3: commit no repositório principal" \
    rodap 'echo p >p.txt && git add p.txt && git -c user.name=t -c user.email=t@t commit -qm p'
  conferir "caso 3: commondir do .git principal não é gravável" rodap '! echo mal >.git/commondir'
  git -C "$tmp/repo" status >/dev/null 2>&1
  conferir "caso 3: git status de fora segue sem fsmonitor" test ! -e "$marca"

  # Canais que executam fora: Hyprland, D-Bus, processos de fora.
  conferir "caso 3: hyprctl não alcança o Hyprland" roda '! hyprctl version'
  conferir "caso 3: sem socket do Wayland" roda '! ls "${XDG_RUNTIME_DIR:-/nada}"/wayland-*'
  conferir "caso 3: systemd-run --user falha" roda '! systemd-run --user true'
  if [[ -n "${DBUS_SESSION_BUS_ADDRESS:-}" ]] && command -v xdg-dbus-proxy >/dev/null 2>&1 \
     && command -v busctl >/dev/null 2>&1; then
    conferir "caso 3: D-Bus só com o keyring e as notificações" \
      roda '[ -z "$(busctl --user list --no-legend | awk "{print \$1}" | grep -v "^:" \
        | grep -vxE "org\.freedesktop\.(DBus|secrets|Notifications)")" ]'
    conferir "caso 3: systemd do usuário fora de alcance pelo D-Bus" \
      roda '! busctl --user call org.freedesktop.systemd1 /org/freedesktop/systemd1 org.freedesktop.systemd1.Manager ListUnits'
  else
    echo "pulado caso 3 do D-Bus: sem sessão D-Bus, xdg-dbus-proxy ou busctl"
  fi
  echo guardado >"$casa/.cache/guardado.txt"
  minima() { isolar "$tmp/wt" JANGADA_ISOLAR_CASA=minima "$repo_jangada/bin/jangada-isolar" -- bash -c "$1" >/dev/null 2>&1; }
  # O /tmp do agente é próprio e já esconde a casa do teste: a leitura só se
  # confere com uma casa fora dele.
  if casa_fora="$(mktemp -d -p /var/tmp 2>/dev/null)"; then
    echo pessoal >"$casa_fora/documento.txt"
    le() { (cd "$tmp/wt" && env -u JANGADA_ISOLADO HOME="$casa_fora" JANGADA_PATH="$repo_jangada" JANGADA_MARCA_ISOLADO="$marca_teste" \
      "${@:2}" "$repo_jangada/bin/jangada-isolar" -- bash -c "$1" >/dev/null 2>&1); }
    conferir "casa mínima: sem ela o documento pessoal é legível" le "grep -q pessoal '$casa_fora/documento.txt'"
    conferir "casa mínima: documento pessoal fora de alcance" \
      le "! test -e '$casa_fora/documento.txt'" JANGADA_ISOLAR_CASA=minima
    rm -rf "$casa_fora"
  else
    echo "pulado casa mínima (leitura): /var/tmp não é gravável aqui"
  fi
  conferir "casa mínima: chave segue oculta" minima "! test -e '$casa/.ssh/id_teste'"
  conferir "casa mínima: a pasta do Claude segue gravável" minima "echo x >'$casa/.claude/minima.txt'"
  conferir "casa mínima: o cache de fora segue legível" minima "grep -q guardado '$casa/.cache/guardado.txt'"
  conferir "casa mínima: commit no worktree" \
    minima 'echo m >minima.txt && git add minima.txt && git -c user.name=t -c user.email=t@t commit -qm minima'
  minima "echo x >'$casa/solto.txt'"
  conferir "casa mínima: o que o agente grava na casa não chega ao disco" test ! -e "$casa/solto.txt"
  # O keyring só é liberado para o agy. O proxy falso anota o que recebeu.
  mkdir -m 0700 "$tmp/run"
  mkdir -p "$tmp/proxy-falso" "$tmp/agy-falso"
  printf '#!/bin/sh\nprintf "%%s\\n" "$@" >"$PROXY_ARGS"\nprintf x\n' >"$tmp/proxy-falso/xdg-dbus-proxy"
  printf '#!/bin/sh\n' >"$tmp/agy-falso/agy"
  chmod +x "$tmp/proxy-falso/xdg-dbus-proxy" "$tmp/agy-falso/agy"
  proxy() {
    isolar "$tmp/wt" PATH="$tmp/proxy-falso:$1/usr/bin:/bin" PROXY_ARGS="$tmp/proxy.args" XDG_RUNTIME_DIR="$tmp/run" \
      DBUS_SESSION_BUS_ADDRESS=unix:path=/nada "$repo_jangada/bin/jangada-isolar" -- true >/dev/null 2>&1
  }
  if PATH=/usr/bin:/bin command -v agy >/dev/null 2>&1; then
    echo "pulado caso 3 do keyring: agy instalado em /usr/bin"
  else
    proxy ""
    conferir "caso 3: sem agy, o proxy não libera o keyring" \
      bash -c 'grep -qxF -- --talk=org.freedesktop.Notifications "$1" && ! grep -q secrets "$1"' _ "$tmp/proxy.args"
    proxy "$tmp/agy-falso:"
    conferir "caso 3: com agy, o proxy libera o keyring e as notificações" \
      bash -c 'grep -qxF -- --talk=org.freedesktop.Notifications "$1" && grep -qxF -- --talk=org.freedesktop.secrets "$1"' _ "$tmp/proxy.args"
  fi
  conferir "caso 3: não vê os processos de fora" roda '[ "$(ls /proc | grep -c "^[0-9]")" -lt 10 ]'

  # Configuração do Claude e caches que alimentam código de fora.
  conferir "caso 3: settings.json do Claude não é gravável" roda "! echo x >>'$casa/.claude/settings.json'"
  conferir "caso 3: pasta de skills do Claude não é gravável" roda "! mkdir '$casa/.claude/skills/nova'"
  roda "echo x >'$casa/.claude/projects-teste'"
  conferir "caso 3: o resto do ~/.claude segue gravável" test -f "$casa/.claude/projects-teste"
  roda "echo x >'$casa/.claude/shell-snapshots/snapshot-teste.sh'"
  conferir "caso 3: retrato do shell gravado dentro não chega ao disco" \
    test ! -e "$casa/.claude/shell-snapshots/snapshot-teste.sh"
  conferir "caso 3: ~/.cache/yay não é gravável" roda "! echo x >'$casa/.cache/yay/pacote/PKGBUILD'"
  roda "echo x >'$casa/.cache/outro'"
  conferir "caso 3: gravação no ~/.cache não chega ao disco" test ! -e "$casa/.cache/outro"
  if ((sobreposicao)); then
    conferir "caso 3: o agy regrava o agentapi dentro" \
      roda "echo envenenado >'$casa/.gemini/antigravity-cli/bin/agentapi'"
  else
    roda "echo envenenado >'$casa/.gemini/antigravity-cli/bin/agentapi'"
  fi
  conferir "caso 3: o agentapi regravado dentro não chega ao disco" \
    [ "$(cat "$casa/.gemini/antigravity-cli/bin/agentapi")" = "exec agy" ]
  conferir "caso 3: histórico da área de transferência não é legível" \
    roda "! grep -q senha '$casa/.cache/cliphist/db'"
  roda "echo envenenado >'$casa/.cache/cliphist/db'"
  conferir "caso 3: histórico da área de transferência não muda" \
    [ "$(cat "$casa/.cache/cliphist/db")" = "senha copiada" ]

  # Dentro, com a marca montada, o jangada-isolar roda direto, sem aninhar.
  saida="$(isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- \
    "$repo_jangada/bin/jangada-isolar" --mostrar -- true 2>/dev/null)"
  conferir "caso 3: já isolado, roda direto sem aninhar" [ -z "$saida" ]
  conferir "caso 3: a marca não é removível de dentro" roda "! rm -f '$marca_teste'"

  # Propagação de código de saída e sinais
  rc_prop=0
  isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- sh -c 'exit 42' 2>/dev/null || rc_prop=$?
  conferir "caso 3: propaga código de saída" [ "$rc_prop" -eq 42 ]

  testar_sinal() {
    local sig="$1" rc_esperado="$2"
    python3 -c '
import subprocess, time, signal, sys, os

sig_name = sys.argv[1]
expected_rc = int(sys.argv[2])
sig = getattr(signal, "SIG" + sig_name)

wt = sys.argv[3]
casa = sys.argv[4]
config = sys.argv[5]
repo = sys.argv[6]
marca = sys.argv[7]

env = os.environ.copy()
env.pop("XDG_CACHE_HOME", None)
env.pop("JANGADA_ISOLADO", None)
env["HOME"] = casa
env["XDG_STATE_HOME"] = f"{casa}/.local/state"
env["XDG_CONFIG_HOME"] = config
env["JANGADA_PATH"] = repo
env["JANGADA_MARCA_ISOLADO"] = marca

def achar_sleep():
    pids = subprocess.run(["pgrep", "-f", "sleep 25.123"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                if "25.123" not in f.read().decode("utf-8", errors="ignore"):
                    continue
            with open(f"/proc/{pid}/environ", "rb") as f:
                if f"HOME={casa}" in f.read().decode("utf-8", errors="ignore").split("\0"):
                    return pid
        except OSError:
            pass
    return None

p = subprocess.Popen([f"{repo}/bin/jangada-isolar", "--", "sleep", "25.123"],
                     cwd=wt, env=env)
for _ in range(50):
    if achar_sleep():
        break
    time.sleep(0.05)
else:
    p.kill()
    sys.exit(1)

p.send_signal(sig)
try:
    rc = p.wait(timeout=5)
except subprocess.TimeoutExpired:
    p.kill()
    sys.exit(2)

if rc < 0:
    rc = 128 + (-rc)

if rc != expected_rc:
    sys.exit(3)

time.sleep(0.1)
for _ in range(30):
    if not achar_sleep():
        break
    time.sleep(0.05)
else:
    sys.exit(4)

sys.exit(0)
' "$sig" "$rc_esperado" "$tmp/wt" "$casa" "$tmp/config" "$repo_jangada" "$marca_teste"
  }

  conferir "caso 3: propaga sinal SIGTERM" testar_sinal TERM 143
  conferir "caso 3: propaga sinal SIGHUP" testar_sinal HUP 129

  testar_sigint_sleep_grupo() {
    python3 -c '
import subprocess, time, signal, sys, os

wt = sys.argv[1]
casa = sys.argv[2]
config = sys.argv[3]
repo = sys.argv[4]
marca = sys.argv[5]

env = os.environ.copy()
env.pop("XDG_CACHE_HOME", None)
env.pop("JANGADA_ISOLADO", None)
env["HOME"] = casa
env["XDG_STATE_HOME"] = f"{casa}/.local/state"
env["XDG_CONFIG_HOME"] = config
env["JANGADA_PATH"] = repo
env["JANGADA_MARCA_ISOLADO"] = marca

def achar_sleep():
    pids = subprocess.run(["pgrep", "-f", "sleep 25.123"], capture_output=True, text=True).stdout.split()
    for pid in pids:
        try:
            with open(f"/proc/{pid}/cmdline", "rb") as f:
                if "25.123" not in f.read().decode("utf-8", errors="ignore"):
                    continue
            with open(f"/proc/{pid}/environ", "rb") as f:
                if f"HOME={casa}" in f.read().decode("utf-8", errors="ignore").split("\0"):
                    return pid
        except OSError:
            pass
    return None

p = subprocess.Popen([f"{repo}/bin/jangada-isolar", "--", "sleep", "25.123"],
                     cwd=wt, env=env, start_new_session=True)
for _ in range(50):
    if achar_sleep():
        break
    time.sleep(0.05)
else:
    p.kill()
    sys.exit(1)

os.killpg(p.pid, signal.SIGINT)

try:
    rc = p.wait(timeout=5)
except subprocess.TimeoutExpired:
    p.kill()
    sys.exit(2)

if rc < 0:
    rc = 128 + (-rc)

if rc != 130:
    sys.exit(3)

time.sleep(0.1)
for _ in range(30):
    if not achar_sleep():
        break
    time.sleep(0.05)
else:
    sys.exit(4)

sys.exit(0)
' "$tmp/wt" "$casa" "$tmp/config" "$repo_jangada" "$marca_teste"
  }
  conferir "caso 3: propaga sinal SIGINT ao grupo" testar_sigint_sleep_grupo
  conferir "caso 3: processo filho sleep não sobra" \
    bash -c '
      for ((i=0; i<30; i++)); do
        sobrou=0
        for pid in $(pgrep -f "sleep 25\.123" 2>/dev/null || true); do
          if tr "\0" "\n" <"/proc/$pid/environ" 2>/dev/null | grep -q "^HOME=$1$"; then
            sobrou=1
            break
          fi
        done
        ((!sobrou)) && exit 0
        sleep 0.05
      done
      exit 1
    ' _ "$casa"

  testar_sigint_grupo() {
    python3 -c '
import subprocess, time, signal, sys, os

wt = sys.argv[1]
casa = sys.argv[2]
config = sys.argv[3]
repo = sys.argv[4]
marca = sys.argv[5]

env = os.environ.copy()
env.pop("XDG_CACHE_HOME", None)
env.pop("JANGADA_ISOLADO", None)
env["HOME"] = casa
env["XDG_STATE_HOME"] = f"{casa}/.local/state"
env["XDG_CONFIG_HOME"] = config
env["JANGADA_PATH"] = repo
env["JANGADA_MARCA_ISOLADO"] = marca

sig_file = os.path.join(wt, ".sigint_recebido")
rdy_file = os.path.join(wt, ".rdy_sigint")
if os.path.exists(sig_file): os.remove(sig_file)
if os.path.exists(rdy_file): os.remove(rdy_file)

py_cmd = f"""
import signal, time, sys, os
entregas = 0
def handler(s, f):
    global entregas
    entregas += 1
    with open("{sig_file}", "w") as out:
        out.write(f"{{entregas}}\\n")
    if entregas == 1:
        time.sleep(0.2)
        sys.exit(42)
signal.signal(signal.SIGINT, handler)
with open("{rdy_file}", "w") as out:
    out.write("ok\\n")
while True:
    time.sleep(0.05)
"""

p = subprocess.Popen([f"{repo}/bin/jangada-isolar", "--", "python3", "-c", py_cmd],
                     cwd=wt, env=env, start_new_session=True)

for _ in range(100):
    if os.path.exists(rdy_file):
        break
    time.sleep(0.05)
else:
    p.kill()
    sys.exit(1)

os.killpg(p.pid, signal.SIGINT)

try:
    rc = p.wait(timeout=5)
except subprocess.TimeoutExpired:
    p.kill()
    sys.exit(2)

if rc < 0:
    rc = 128 + (-rc)

if rc != 42:
    sys.exit(3)

if not os.path.exists(sig_file) or open(sig_file).read().strip() != "1":
    sys.exit(4)

sys.exit(0)
' "$tmp/wt" "$casa" "$tmp/config" "$repo_jangada" "$marca_teste"
  }
  conferir "caso 3: SIGINT ao grupo de processos chega ao filho isolado uma única vez" testar_sigint_grupo

  testar_sigint_capturado_sucesso() {
    python3 -c '
import subprocess, time, signal, sys, os

wt = sys.argv[1]
casa = sys.argv[2]
config = sys.argv[3]
repo = sys.argv[4]
marca = sys.argv[5]

env = os.environ.copy()
env.pop("XDG_CACHE_HOME", None)
env.pop("JANGADA_ISOLADO", None)
env["HOME"] = casa
env["XDG_STATE_HOME"] = f"{casa}/.local/state"
env["XDG_CONFIG_HOME"] = config
env["JANGADA_PATH"] = repo
env["JANGADA_MARCA_ISOLADO"] = marca

sig_file = os.path.join(wt, ".sigint_zero_recebido")
rdy_file = os.path.join(wt, ".rdy_zero")
if os.path.exists(sig_file): os.remove(sig_file)
if os.path.exists(rdy_file): os.remove(rdy_file)

py_cmd = f"""
import signal, time, sys, os
def handler(s, f):
    with open("{sig_file}", "w") as out:
        out.write("recebido\\n")
signal.signal(signal.SIGINT, handler)
with open("{rdy_file}", "w") as out:
    out.write("ok\\n")
for _ in range(50):
    if os.path.exists("{sig_file}"):
        break
    time.sleep(0.05)
time.sleep(0.1)
sys.exit(0)
"""

p = subprocess.Popen([f"{repo}/bin/jangada-isolar", "--", "python3", "-c", py_cmd],
                     cwd=wt, env=env, start_new_session=True)

for _ in range(100):
    if os.path.exists(rdy_file):
        break
    time.sleep(0.05)
else:
    p.kill()
    sys.exit(1)

os.killpg(p.pid, signal.SIGINT)

try:
    rc = p.wait(timeout=5)
except subprocess.TimeoutExpired:
    p.kill()
    sys.exit(2)

if rc < 0:
    rc = 128 + (-rc)

if rc != 0:
    sys.exit(3)

if not os.path.exists(sig_file) or open(sig_file).read().strip() != "recebido":
    sys.exit(4)

sys.exit(0)
' "$tmp/wt" "$casa" "$tmp/config" "$repo_jangada" "$marca_teste"
  }
  conferir "caso 3: filho isolado captura SIGINT e encerra com código 0" testar_sigint_capturado_sucesso

  # Entrada padrão interativa / por pipe
  saida_pipe="$(printf 'dados-stdin-123\n' | isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- cat 2>/dev/null)"
  conferir "caso 3: entrada padrão via pipe chega ao comando isolado" [ "$saida_pipe" = "dados-stdin-123" ]
  saida_read="$(printf 'linha-lida\n' | isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- sh -c 'read -r x && printf "%s" "$x"' 2>/dev/null)"
  conferir "caso 3: leitura interativa de linha via pipe funciona" [ "$saida_read" = "linha-lida" ]

  # Caso 3b: marcas do host (vram-livre e jogo-ativo) e monitor
  bin_falso="$tmp/bin_falso"
  mkdir -p "$bin_falso"
  cat >"$bin_falso/nvidia-smi" <<'EOF'
#!/bin/sh
echo 6144
EOF
  chmod +x "$bin_falso/nvidia-smi"

  cat >"$bin_falso/pgrep" <<EOF
#!/bin/sh
if [ -f "$tmp/jogo_ativo_flag" ]; then
  echo 9999
  exit 0
fi
exit 1
EOF
  chmod +x "$bin_falso/pgrep"

  touch "$tmp/jogo_ativo_flag"
  saida_marcas="$(JANGADA_MONITOR_INTERVALO=30.789123 PATH="$bin_falso:$PATH" isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- bash -c \
    'cat "$JANGADA_ESTADO/marcas/vram-livre" 2>/dev/null; echo "---"; cat "$JANGADA_ESTADO/marcas/jogo-ativo" 2>/dev/null')"

  conferir "caso 3b: vram-livre criada e legível dentro do isolamento" \
    bash -c 'echo "$1" | head -n1 | grep -qE "^6144 [0-9]+$"' _ "$saida_marcas"
  conferir "caso 3b: jogo-ativo criado e legível dentro do isolamento" \
    bash -c 'echo "$1" | tail -n1 | grep -qE "^[0-9]+$"' _ "$saida_marcas"
  conferir "caso 3b: vram-livre gravada no host" [ -f "$casa/.local/state/jangada/marcas/vram-livre" ]
  conferir "caso 3b: jogo-ativo gravado no host" [ -f "$casa/.local/state/jangada/marcas/jogo-ativo" ]

  # Jogo fecha: próxima chamada deve remover jogo-ativo
  rm -f "$tmp/jogo_ativo_flag"
  JANGADA_MONITOR_INTERVALO=30.789123 PATH="$bin_falso:$PATH" isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- true
  conferir "caso 3b: jogo-ativo removido quando o jogo fecha" [ ! -e "$casa/.local/state/jangada/marcas/jogo-ativo" ]

  # Encerramento limpo do monitor
  conferir "caso 3b: monitor não deixa sleep em segundo plano" \
    bash -c '
      sleep 0.2
      for pid in $(pgrep -f "sleep 30\.789123" 2>/dev/null || true); do
        if tr "\0" "\n" <"/proc/$pid/environ" 2>/dev/null | grep -q "^HOME=$1$"; then
          exit 1
        fi
      done
      exit 0
    ' _ "$casa"
  conferir "caso 3b: nenhum temporário .vram-livre deixado para trás" \
    [ -z "$(find "$casa/.local/state/jangada/marcas" -name '.vram-livre.*' 2>/dev/null)" ]
  conferir "caso 3b: nenhum temporário .jogo-ativo deixado para trás" \
    [ -z "$(find "$casa/.local/state/jangada/marcas" -name '.jogo-ativo.*' 2>/dev/null)" ]

  # Caso 3c: renovação dinâmica das marcas e surgimento de jogo em sessão já aberta
  rm -f "$tmp/wt/.sinal_leitura1" "$tmp/wt/.sinal_atualizado" "$tmp/wt/.resultado_3c"
  rm -f "$casa/.local/state/jangada/marcas/jogo-ativo"

  (
    JANGADA_MONITOR_INTERVALO=30.789123 PATH="$bin_falso:$PATH" isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- bash -c '
      vl1="$(cat "$JANGADA_ESTADO/marcas/vram-livre" 2>/dev/null | awk "{print \$1}")"
      ja1="nao"
      [[ -f "$JANGADA_ESTADO/marcas/jogo-ativo" ]] && ja1="sim"

      touch .sinal_leitura1

      for ((k = 0; k < 100; k++)); do
        [[ -f .sinal_atualizado ]] && break
        sleep 0.05
      done

      vl2="$(cat "$JANGADA_ESTADO/marcas/vram-livre" 2>/dev/null | awk "{print \$1}")"
      ja2="nao"
      [[ -f "$JANGADA_ESTADO/marcas/jogo-ativo" ]] && ja2="sim"

      printf "%s %s %s %s\n" "$vl1" "$ja1" "$vl2" "$ja2" >.resultado_3c
    '
  ) &
  pid_sessao=$!

  for ((t = 0; t < 100; t++)); do
    [[ -f "$tmp/wt/.sinal_leitura1" ]] && break
    sleep 0.05
  done

  # Host atualiza marcas atomicamente com novos inodes e cria jogo-ativo
  tmp_vl="$(mktemp "$casa/.local/state/jangada/marcas/.vram-livre.XXXXXX")"
  printf "7168 %s\n" "$(date +%s)" >"$tmp_vl"
  mv -f "$tmp_vl" "$casa/.local/state/jangada/marcas/vram-livre"

  tmp_ja="$(mktemp "$casa/.local/state/jangada/marcas/.jogo-ativo.XXXXXX")"
  date +%s >"$tmp_ja"
  mv -f "$tmp_ja" "$casa/.local/state/jangada/marcas/jogo-ativo"

  touch "$tmp/wt/.sinal_atualizado"

  wait "$pid_sessao" || true

  res_3c="$(cat "$tmp/wt/.resultado_3c" 2>/dev/null || true)"
  conferir "caso 3c: sandbox enxerga atualização dinâmica de vram e novo jogo-ativo" \
    [ "$res_3c" = "6144 nao 7168 sim" ]

  rm -f "$casa/.local/state/jangada/marcas/jogo-ativo"
  # O hook muda o JSON dentro do PID isolado; o observador no host avisa
  # a barra. O arquivo de sinais fica fora dos caminhos graváveis do agente.
  if command -v inotifywait >/dev/null 2>&1; then
    bin_status="$tmp/bin_status"
    estado_status="$casa/.local/state/jangada/agentes/status-codex.json"
    sinais_status="$tmp/sinais-waybar"
    mkdir -p "$bin_status" "$(dirname "$estado_status")"
    printf '{"estado":"iniciado", "raiz":"projeto"}\n' >"$estado_status"
    cat >"$bin_status/pkill" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == -RTMIN+10 ]]; then
  jq -r .estado "$estado_status" >>"$sinais_status"
  exit 0
fi
exec /usr/bin/pkill "\$@"
EOF
    printf '#!/bin/sh\nexit 0\n' >"$bin_status/notify-send"
    chmod +x "$bin_status/"*
    isolar "$tmp/wt" PATH="$bin_status:$PATH" JANGADA_SESSAO=status-codex \
      "$repo_jangada/bin/jangada-isolar" -- bash -c '
        sleep 0.2
        printf "{}\n" >"$JANGADA_ESTADO/agentes/outra-sessao.json"
        for estado in trabalhando aguardando concluido; do
          printf "{}\n" | "$JANGADA_PATH/bin/jangada-hook-codex" "$estado"
          sleep 0.3
        done
      ' >"$tmp/status.log" 2>&1
    conferir "caso 3d: hooks executam dentro do isolamento" [ "$?" = 0 ]
    conferir "caso 3d: Waybar recebe os três estados pelo observador no host" \
      bash -c '[[ "$(uniq "$1")" == $'"'"'trabalhando\naguardando\nconcluido'"'"' ]]' _ "$sinais_status"
    conferir "caso 3d: observador do estado não deixa inotifywait após encerrar" \
      bash -c '! pgrep -f "^inotifywait .*${1}/agentes" >/dev/null' _ "$casa/.local/state/jangada"
  fi
else
  echo "pulado caso 3: bwrap não cria namespace aqui"
fi

# Caso 4: a trava do estado não abre para escrita um caminho que o agente
# controla. Um link .trava para um arquivo de fora não pode truncá-lo.
estado="$casa/.local/state/jangada/agentes"
mkdir -p "$estado"
echo '{"estado":"iniciado"}' >"$estado/s.json"
echo "conteúdo de fora" >"$tmp/alvo"
ln -sfn "$tmp/alvo" "$estado/.trava"
if command -v flock >/dev/null 2>&1; then
  isolar "$tmp/wt" bash -c 'source "$1/bin/jangada-config"; jangada_alterar_estado "$2/s.json" "$2/s.tmp" ".estado = \"ok\""' \
    _ "$repo_jangada" "$estado"
  conferir "caso 4: alvo do link da trava intacto" [ "$(cat "$tmp/alvo")" = "conteúdo de fora" ]
  conferir "caso 4: estado alterado sob a trava" [ "$(jq -r .estado "$estado/s.json")" = ok ]
else
  echo "pulado caso 4: sem flock"
fi

if ((falhas)); then
  echo "$falhas falha(s); saídas em $tmp (mantido)"
  trap - EXIT
  exit 1
fi
echo "todos os testes do jangada-isolar passaram"
