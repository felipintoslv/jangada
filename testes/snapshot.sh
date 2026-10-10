#!/usr/bin/env bash
# Testa a retenção dos snapshots no jangada-snapshot: o manual entra na
# limpeza por número do snapper; o do agente fica fora dela, marcado com
# jangada=agente, e só os JANGADA_SNAPSHOTS_AGENTE mais recentes ficam. Os
# manuais e os do snap-pac nunca são apagados por ele. O sudo e o snapper são
# falsos e registram como foram chamados.
#
# Uso: testes/snapshot.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" FALSO="$tmp/falso"
export JANGADA_SNAPPER_CONF="$tmp/snapper-root"
mkdir -p "$HOME" "$tmp/bin" "$FALSO" "$XDG_CONFIG_HOME/jangada"
: >"$JANGADA_SNAPPER_CONF"

printf '#!/bin/sh\nexec "$@"\n' >"$tmp/bin/sudo"
# snapper falso: o list devolve FALSO/lista; o resto só é registrado.
cat >"$tmp/bin/snapper" <<'FIM'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FALSO/argv"
case " $* " in
  *" list "*) cat "$FALSO/lista" ;;
  *" create "*) echo 99 ;;
esac
FIM
chmod +x "$tmp/bin/"*

# Seis do agente (2, 4, 5, 7, 8, 9), um manual (3), um par do snap-pac (10 e
# 11) e um do agente que o usuário passou para a limpeza por número (6).
cat >"$FALSO/lista" <<'FIM'
{"root": [
  {"number": 0, "type": "single", "cleanup": "", "description": "current", "userdata": null},
  {"number": 2, "type": "single", "cleanup": "", "description": "antes do agente a", "userdata": {"jangada": "agente"}},
  {"number": 3, "type": "single", "cleanup": "number", "description": "manual", "userdata": null},
  {"number": 4, "type": "single", "cleanup": "", "description": "antes do agente b", "userdata": {"jangada": "agente"}},
  {"number": 5, "type": "single", "cleanup": "", "description": "antes do agente c", "userdata": {"jangada": "agente"}},
  {"number": 6, "type": "single", "cleanup": "number", "description": "antes do agente d", "userdata": {"jangada": "agente"}},
  {"number": 7, "type": "single", "cleanup": "", "description": "antes do agente e", "userdata": {"jangada": "agente"}},
  {"number": 8, "type": "single", "cleanup": "", "description": "antes do agente f", "userdata": {"jangada": "agente"}},
  {"number": 9, "type": "single", "cleanup": "", "description": "antes do agente g", "userdata": {"jangada": "agente"}},
  {"number": 10, "type": "pre", "cleanup": "number", "description": "pacman", "userdata": null},
  {"number": 11, "type": "post", "cleanup": "number", "description": "", "userdata": null}
]}
FIM

snapshot() {
  rm -f "$FALSO/argv"
  PATH="$tmp/bin:$PATH" JANGADA_PATH="$PWD" bin/jangada-snapshot "$@" >"$tmp/saida" 2>&1
  rc=$?
}
chamou() { grep -qxF -- "$1" "$FALSO/argv"; }
nao_apagou() { ! grep -q -- " delete" "$FALSO/argv"; }

# Caso 1: snapshot manual, na limpeza do snapper e sem apagar nada.
snapshot "manual"
conferir "caso 1: termina sem erro ($rc)" test "$rc" -eq 0
conferir "caso 1: cria com a limpeza por número" \
  chamou "-c root create --type single --cleanup-algorithm number --description manual --print-number"
conferir "caso 1: não apaga nada" nao_apagou

# Caso 2: snapshot do agente, com o limite padrão de 5.
snapshot --agente "antes do agente x"
conferir "caso 2: termina sem erro ($rc)" test "$rc" -eq 0
conferir "caso 2: cria fora da limpeza, marcado" \
  chamou "-c root create --type single --userdata jangada=agente --description antes do agente x --print-number"
conferir "caso 2: apaga só o mais antigo do agente" chamou "-c root delete 2"

# Caso 3: limite do jangada.conf.
echo "JANGADA_SNAPSHOTS_AGENTE=2" >"$XDG_CONFIG_HOME/jangada/jangada.conf"
snapshot --agente "antes do agente x"
conferir "caso 3: fica com os 2 mais recentes do agente" chamou "-c root delete 2 4 5 7"

# Caso 4: limite inválido volta para 5 e avisa.
echo "JANGADA_SNAPSHOTS_AGENTE=0" >"$XDG_CONFIG_HOME/jangada/jangada.conf"
snapshot --agente "antes do agente x"
conferir "caso 4: limite inválido usa 5" chamou "-c root delete 2"
conferir "caso 4: avisa do limite inválido" grep -q "não é um número positivo" "$tmp/saida"

# Caso 5: dentro do limite, não apaga nada.
echo "JANGADA_SNAPSHOTS_AGENTE=10" >"$XDG_CONFIG_HOME/jangada/jangada.conf"
snapshot --agente "antes do agente x"
conferir "caso 5: dentro do limite não apaga" nao_apagou

# Caso 6: o jangada-agente --snapshot usa o snapshot do agente.
conferir "caso 6: jangada-agente chama jangada-snapshot --agente" \
  grep -q 'bin/jangada-snapshot" --agente ' bin/jangada-agente

# Caso 7: o snapshot é opcional para o jangada-agente (exceção permanente de
# K9). Numa cópia do jangada sem bin/jangada-snapshot, o --snapshot abre a
# sessão do mesmo jeito. O tmux é falso e registra as chamadas; HOME e as
# pastas de estado e de configuração ficam na pasta temporária. O
# jangada-projeto e o confianca.py também são falsos: os reais recusam o
# registro da sessão dentro do isolamento, e o caso precisa dar o mesmo
# resultado dentro e fora dele.
jp="$tmp/jangada"
mkdir -p "$jp/bin" "$jp/default/orquestracao" "$tmp/proj" "$tmp/state" "$tmp/config-agente/jangada" "$tmp/runtime"
for c in default/*; do
  [[ "$c" == default/orquestracao ]] || ln -s "$PWD/$c" "$jp/default/"
done
: >"$jp/default/orquestracao/confianca.py"
for c in bin/jangada*; do
  case "$c" in bin/jangada-snapshot|bin/jangada-projeto) ;; *) ln -s "$PWD/$c" "$jp/bin/" ;; esac
done
cat >"$jp/bin/jangada-projeto" <<'FIM'
#!/usr/bin/env bash
case " $* " in *" sessao-iniciar "*) echo '{"execucao": "e1"}' ;; esac
FIM
chmod +x "$jp/bin/jangada-projeto"
cat >"$tmp/bin/tmux" <<'FIM'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FALSO/tmux"
case " $* " in *" has-session "*) exit 1 ;; esac
exit 0
FIM
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/claude"
chmod +x "$tmp/bin/"*
agente() {
  rm -f "$FALSO/tmux" "$FALSO/snapshot"
  env -u TMUX -u JANGADA_SESSAO -u JANGADA_ISOLADO -u JANGADA_ESTADO -u JANGADA_SESSOES \
    -u WAYLAND_DISPLAY -u HYPRLAND_INSTANCE_SIGNATURE \
    PATH="$tmp/bin:$PATH" XDG_STATE_HOME="$tmp/state" XDG_CONFIG_HOME="$tmp/config-agente" \
    XDG_RUNTIME_DIR="$tmp/runtime" JANGADA_PATH="$jp" JANGADA_PROJETOS="$tmp" \
    "$jp/bin/jangada-agente" --direto --snapshot --agente claude --projeto "$tmp/proj" --prompt "$1" \
    >"$tmp/saida" 2>&1 </dev/null
  rc=$?
}
sessao_aberta() {
  grep -q -- ' new-session -d -s proj ' "$FALSO/tmux" && grep -q -- ' attach -t =proj$' "$FALSO/tmux" &&
    [ "$(jq -r .estado "$tmp/state/jangada/agentes/proj.json")" = iniciado ]
}
agente "sem o comando"
conferir "caso 7: sem jangada-snapshot, termina sem erro ($rc)" test "$rc" -eq 0
conferir "caso 7: sem jangada-snapshot, a sessão abre" sessao_aberta
rm -f "$tmp/state/jangada/agentes/proj.json"
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >"$FALSO/snapshot"\n' >"$jp/bin/jangada-snapshot"
chmod +x "$jp/bin/jangada-snapshot"
agente "com o comando"
conferir "caso 7: com jangada-snapshot, ele é chamado antes da sessão" \
  grep -qxF -- "--agente antes do agente proj" "$FALSO/snapshot"
conferir "caso 7: com jangada-snapshot, a sessão abre" sessao_aberta

if ((falhas)); then
  echo "--- última saída"; cat "$tmp/saida"
  echo "$falhas teste(s) do snapshot falharam"
  exit 1
fi
echo "todos os testes do snapshot passaram"
