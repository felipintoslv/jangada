#!/usr/bin/env bash
# Sobe um Hyprland aninhado, numa janela da sessão em uso, com a configuração
# desta cópia do jangada, e confere configerrors e atalhos. Só roda dentro de
# uma sessão Wayland; fora dela sai com "pulado" e código 0.
#
# Uso: testes/aninhado.sh [--sem-usuario]
#   --sem-usuario  carrega só os padrões, sem ~/.config/jangada/hypr
#
# Fica de fora o default.hypr.inicio: ele roda dbus-update-activation-environment
# --systemd --all e trocaria o ambiente da sessão em uso pelo da instância de
# teste. O aninhado usa o backend Wayland e nunca toca no DRM, então não testa
# a escolha de GPU nem AQ_DRM_DEVICES.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
usuario=1
[[ "${1:-}" == --sem-usuario ]] && usuario=0

if [[ -z "${WAYLAND_DISPLAY:-}" ]] || ! command -v Hyprland >/dev/null; then
  echo "pulado: exige uma sessão Wayland e o Hyprland instalado"
  exit 0
fi

runtime="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
cfg_usuario="${XDG_CONFIG_HOME:-$HOME/.config}/jangada/hypr"
tmp="$(mktemp -d)"
sig=""
encerrar() {
  if [[ -n "$sig" ]]; then
    HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl dispatch 'hl.dsp.exit()' >/dev/null 2>&1 || true
  fi
  rm -rf "$tmp"
}
trap encerrar EXIT

{
  echo "dofile(\"$repo/default/hypr/bootstrap.lua\")"
  ((usuario)) && echo "package.path = \"$cfg_usuario/?.lua;\" .. package.path"
  for m in ajudantes ambiente aparencia entrada regras atalhos; do
    echo "require(\"default.hypr.$m\")"
  done
  if ((usuario)); then
    for m in monitores usuario; do
      [[ -f "$cfg_usuario/$m.lua" ]] && echo "require(\"$m\")"
    done
  fi
} >"$tmp/hyprland.lua"

antes="$(ls "$runtime/hypr" 2>/dev/null | sort)"
env -u HYPRLAND_INSTANCE_SIGNATURE JANGADA_PATH="$repo" \
  setsid -f Hyprland --config "$tmp/hyprland.lua" >"$tmp/saida.log" 2>&1

# A instância nova é a pasta que apareceu em $XDG_RUNTIME_DIR/hypr, pronta
# quando o socket de comandos responde.
for _ in $(seq 1 60); do
  sig="$(comm -13 <(printf '%s\n' "$antes") <(ls "$runtime/hypr" 2>/dev/null | sort) | tail -n1)"
  if [[ -n "$sig" ]] && HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl version >/dev/null 2>&1; then
    break
  fi
  sleep 0.25
done
if [[ -z "$sig" ]]; then
  echo "FALHA: o Hyprland aninhado não subiu; saída:"
  tail -n 30 "$tmp/saida.log"
  exit 1
fi

falhas=0
erros="$(HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl configerrors 2>&1 | sed '/^[[:space:]]*$/d')"
if [[ -n "$erros" ]]; then
  echo "FALHA: erros de configuração:"
  printf '%s\n' "$erros" | sed 's/^/   /'
  falhas=$((falhas + 1))
else
  echo "ok    sem erros de configuração"
fi
n="$(HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl binds -j 2>/dev/null | jq length 2>/dev/null || echo 0)"
if ((n > 0)); then
  echo "ok    $n atalhos registrados"
else
  echo "FALHA: nenhum atalho registrado"
  falhas=$((falhas + 1))
fi
((falhas == 0)) && echo "configuração carregada sem erros no Hyprland aninhado"
exit $((falhas > 0))
