#!/usr/bin/env bash
# Confere identificação da interface sem abrir janelas ou tocar noutras sessões.
set -euo pipefail
cd "$(dirname "$0")/.."
repo="$PWD"
tmp="$(mktemp -d)"
pids=()
limpar() { ((${#pids[@]} == 0)) || kill "${pids[@]}" 2>/dev/null || true; rm -rf "$tmp"; }
trap limpar EXIT
mkdir -p "$tmp/bin" "$tmp/config/jangada"
export XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" JANGADA_PATH="$repo"
export HYPRLAND_INSTANCE_SIGNATURE=teste-interface WAYLAND_DISPLAY=wayland-teste
# shellcheck source=bin/jangada-config
source bin/jangada-config
# shellcheck source=bin/jangada-interface-processos
source bin/jangada-interface-processos
cat >"$tmp/processo.py" <<'PY'
import ctypes, pathlib, signal, sys, time
ctypes.CDLL(None).prctl(15, sys.argv[1].encode(), 0, 0, 0)
log = pathlib.Path(sys.argv[2])
def recebido(sig, _):
    with log.open('a') as f:
        f.write(signal.Signals(sig).name + '\n')
    if sig == signal.SIGTERM:
        sys.exit(0)
signal.signal(signal.SIGTERM, recebido)
signal.signal(signal.SIGUSR2, recebido)
log.write_text('pronto\n')
time.sleep(40)
PY
iniciar() {
  local nome="$1" registro="$2"; shift 2
  env "$@" python3 "$tmp/processo.py" "$nome" "$tmp/$registro" \
    --config "${CONFIG_PROCESSO:-$JANGADA_ESTADO/waybar/borda.jsonc}" &
  pids+=("$!")
  for _ in {1..50}; do [[ -f "$tmp/$registro" ]] && return 0; sleep 0.02; done
  echo "FALHA: processo simulado não iniciou"; exit 1
}
iniciar waybar propria
propria="${pids[-1]}"
iniciar waybar outra-sessao HYPRLAND_INSTANCE_SIGNATURE=outra-sessao
CONFIG_PROCESSO="$tmp/outra.json" iniciar waybar outra-config
jangada_interface_sinalizar waybar USR2
for _ in {1..50}; do grep -q SIGUSR2 "$tmp/propria" && break; sleep 0.02; done
grep -q SIGUSR2 "$tmp/propria"
[[ "$(cat "$tmp/outra-sessao")" == pronto && "$(cat "$tmp/outra-config")" == pronto ]]
echo "ok    recarga atinge só a barra da sessão e configuração corretas"
jangada_interface_sinalizar waybar TERM
wait "$propria"
[[ "$(cat "$tmp/outra-sessao")" == pronto && "$(cat "$tmp/outra-config")" == pronto ]]
echo "ok    reinício preserva barras alheias"
iniciar swaybg papel JANGADA_INTERFACE_PROCESSO=papel
papel="${pids[-1]}"
iniciar swaybg papel-alheio
jangada_interface_sinalizar swaybg TERM
wait "$papel"
[[ "$(cat "$tmp/papel-alheio")" == pronto ]]
echo "ok    papel de parede sem marca não é encerrado"
CONFIG_PROCESSO="$JANGADA_CONFIG/mako/config" iniciar mako notificacoes
mako="${pids[-1]}"
printf '#!/bin/sh\nprintf "u %%s\\n" "$DONO_BUS"\n' >"$tmp/bin/busctl"
printf '#!/bin/sh\necho reload >>"$LOG_MAKO"\n' >"$tmp/bin/makoctl"
chmod +x "$tmp/bin/"*
export PATH="$tmp/bin:$PATH" LOG_MAKO="$tmp/mako.log" DONO_BUS="${pids[1]}"
jangada_interface_recarregar_mako
[[ ! -e "$LOG_MAKO" ]]
export DONO_BUS="$mako"
jangada_interface_recarregar_mako
[[ "$(cat "$LOG_MAKO")" == reload ]]
echo "ok    makoctl só recarrega quando o dono do serviço pertence à sessão"
unset HYPRLAND_INSTANCE_SIGNATURE WAYLAND_DISPLAY
[[ -z "$(jangada_interface_pids waybar)" ]]
echo "ok    sem sessão gráfica, não seleciona processos"

cat >"$tmp/bin/hyprctl" <<'EOF'
#!/bin/sh
cat "$ATALHOS_ENTRADA"
EOF
chmod +x "$tmp/bin/hyprctl"
export ATALHOS_ENTRADA="$tmp/atalhos"
printf 'bindd\n\tmodmask: 64\n\tsubmap: \n\tkey: A\n\tdescription: Primeiro\n\nbindd\n\tmodmask: 65\n\tsubmap: teste\n\tkey: B\n\tdescription: Ultimo' >"$ATALHOS_ENTRADA"
bin/jangada-atalhos --lista >"$tmp/lista"
grep -q Primeiro "$tmp/lista"
grep -q 'SUPER + SHIFT + B.*modo teste.*Ultimo' "$tmp/lista"
[[ "$(wc -l <"$tmp/lista")" == 2 ]]
printf '\n\n' >>"$ATALHOS_ENTRADA"
bin/jangada-atalhos --lista >"$tmp/lista-com-delimitador"
[[ "$(cat "$tmp/lista")" == "$(cat "$tmp/lista-com-delimitador")" ]]
echo "ok    último atalho aparece uma vez, com ou sem delimitador final"
