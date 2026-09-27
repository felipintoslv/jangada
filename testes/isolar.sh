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
trap 'rm -rf "$tmp"' EXIT
casa="$tmp/casa"
mkdir -p "$casa/.ssh" "$casa/.claude" "$casa/extra" "$casa/.cache/yay/pacote" "$casa/.cache/cliphist" \
  "$tmp/config/jangada"
echo "senha copiada" >"$casa/.cache/cliphist/db"
echo "chave" >"$casa/.ssh/id_teste"
echo "senha" >"$casa/.netrc"
echo "{}" >"$casa/.claude.json"
git init -q -b main "$tmp/repo"
git -C "$tmp/repo" -c user.name=t -c user.email=t@t commit -q --allow-empty -m inicio
git -C "$tmp/repo" worktree add -q -b agente/t "$tmp/wt"

isolar() {
  (cd "$1" && env -u XDG_CACHE_HOME HOME="$casa" XDG_STATE_HOME="$casa/.local/state" XDG_CONFIG_HOME="$tmp/config" \
    JANGADA_PATH="$repo_jangada" "${@:2}")
}
mostrar() { isolar "$tmp/wt" "$@" "$repo_jangada/bin/jangada-isolar" --mostrar -- true >"$tmp/args"; }
seguidos() { grep -A2 -xF -- "$1" "$tmp/args" | paste -sd' ' | grep -qF -- "$1 $2 $3"; }

# Caso 1: a chamada ao bwrap.
mostrar
conferir "caso 1: a pasta é gravável" seguidos --bind "$tmp/wt" "$tmp/wt"
conferir "caso 1: o .git comum do worktree é somente leitura" seguidos --ro-bind "$tmp/repo/.git" "$tmp/repo/.git"
conferir "caso 1: objetos do git graváveis" seguidos --bind "$tmp/repo/.git/objects" "$tmp/repo/.git/objects"
conferir "caso 1: refs do git graváveis" seguidos --bind "$tmp/repo/.git/refs" "$tmp/repo/.git/refs"
conferir "caso 1: pasta do worktree no .git gravável" \
  seguidos --bind "$tmp/repo/.git/worktrees/wt" "$tmp/repo/.git/worktrees/wt"
conferir "caso 1: commondir do worktree somente leitura" \
  seguidos --ro-bind "$tmp/repo/.git/worktrees/wt/commondir" "$tmp/repo/.git/worktrees/wt/commondir"
conferir "caso 1: gitdir do worktree somente leitura" \
  seguidos --ro-bind "$tmp/repo/.git/worktrees/wt/gitdir" "$tmp/repo/.git/worktrees/wt/gitdir"
conferir "caso 1: namespace de PID próprio" grep -qxF -- --unshare-pid "$tmp/args"
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
conferir "caso 1: /tmp próprio" seguidos --tmpfs /tmp ""
conferir "caso 1: marca do isolamento montada no /tmp próprio" \
  seguidos --ro-bind /dev/null /tmp/.jangada-isolado
conferir "caso 1: histórico da área de transferência oculto" seguidos --tmpfs "$casa/.cache/cliphist" ""
conferir "caso 1: termina com o comando" [ "$(tail -n1 "$tmp/args")" = true ]
conferir "caso 1: estado dos agentes gravável" \
  seguidos --bind "$casa/.local/state/jangada/agentes" "$casa/.local/state/jangada/agentes"
conferir "caso 1: métricas do validar graváveis" \
  seguidos --bind "$casa/.local/state/jangada/validar.jsonl" "$casa/.local/state/jangada/validar.jsonl"
conferir "caso 1: histórico de estados gravável" \
  seguidos --bind "$casa/.local/state/jangada/eventos-agentes.jsonl" "$casa/.local/state/jangada/eventos-agentes.jsonl"
conferir "caso 1: registro de delegações gravável" \
  seguidos --bind "$casa/.local/state/jangada/delegacoes.jsonl" "$casa/.local/state/jangada/delegacoes.jsonl"
conferir "caso 1: o resto do estado não é gravável" \
  bash -c '! grep -qxF "$1" "$2"' _ "$casa/.local/state/jangada" "$tmp/args"
conferir "caso 1: fora do tmux e do agente SSH" \
  bash -c 'grep -qxF TMUX "$1" && grep -qxF SSH_AUTH_SOCK "$1" && ! grep -q "tmux-" "$1"' _ "$tmp/args"
conferir "caso 1: pasta ausente não entra" bash -c '! grep -qxF "$1" "$2"' _ "$casa/.gemini" "$tmp/args"

mostrar JANGADA_ISOLAR_ESCRITA="$casa/extra:"
conferir "caso 1: JANGADA_ISOLAR_ESCRITA acrescenta gravável" seguidos --bind "$casa/extra" "$casa/extra"
mostrar JANGADA_ISOLAR_OCULTAR=
conferir "caso 1: JANGADA_ISOLAR_OCULTAR vazio não oculta nada" bash -c '! grep -qxF "$1" "$2"' _ "$casa/.ssh" "$tmp/args"

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
: >/tmp/.jangada-isolado-teste 2>/dev/null
conferir "caso 2: arquivo comum no lugar da marca não vale" \
  bash -c '! awk -v m="$1" '"'"'$5 == m { a = 1 } END { exit !a }'"'"' /proc/self/mountinfo' _ /tmp/.jangada-isolado-teste
rm -f /tmp/.jangada-isolado-teste

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
if bwrap --ro-bind / / --dev /dev --proc /proc true 2>/dev/null; then
  roda() { isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- bash -c "$1" >/dev/null 2>&1; }
  conferir "caso 3: grava na pasta" roda 'echo a >dentro.txt'
  conferir "caso 3: o arquivo chega ao disco" test -f "$tmp/wt/dentro.txt"
  conferir "caso 3: commit no worktree" \
    roda 'git add dentro.txt && git -c user.name=t -c user.email=t@t commit -qm dentro'
  conferir "caso 3: o commit chega ao repositório" git -C "$tmp/repo" rev-parse --verify -q agente/t~1 >/dev/null
  roda "echo x >'$casa/fora.txt'"
  conferir "caso 3: gravação na HOME não chega ao disco" test ! -e "$casa/fora.txt"
  conferir "caso 3: chave oculta" roda "! test -e '$casa/.ssh/id_teste' && ! grep -q senha '$casa/.netrc'"
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
  conferir "caso 3: histórico da área de transferência não é legível" \
    roda "! grep -q senha '$casa/.cache/cliphist/db'"
  roda "echo envenenado >'$casa/.cache/cliphist/db'"
  conferir "caso 3: histórico da área de transferência não muda" \
    [ "$(cat "$casa/.cache/cliphist/db")" = "senha copiada" ]

  # Dentro, com a marca montada, o jangada-isolar roda direto, sem aninhar.
  saida="$(isolar "$tmp/wt" "$repo_jangada/bin/jangada-isolar" -- \
    "$repo_jangada/bin/jangada-isolar" --mostrar -- true 2>/dev/null)"
  conferir "caso 3: já isolado, roda direto sem aninhar" [ -z "$saida" ]
  conferir "caso 3: a marca não é removível de dentro" roda '! rm -f /tmp/.jangada-isolado'
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
