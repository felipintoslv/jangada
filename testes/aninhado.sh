#!/usr/bin/env bash
# Sobe um Hyprland aninhado, numa janela da sessão em uso, com a configuração
# desta cópia do jangada, e confere configerrors e atalhos. Só roda dentro de
# uma sessão Wayland; fora dela sai com "pulado" e código 0.
#
# Uso: testes/aninhado.sh [--sem-usuario] [--vidro-desligado] [--jogo-pessoal] [--manter]
#   --sem-usuario  carrega só os padrões, sem ~/.config/jangada/hypr
#   --vidro-desligado  preferências descartáveis com vidro desligado desde a carga
#   --jogo-pessoal     regra real +vidro-jogo para a classe org.jangada.teste_jogo
#   --manter           espera Enter antes de encerrar a instância de teste
#
# Fica de fora o default.hypr.inicio: ele roda dbus-update-activation-environment
# --systemd --all e trocaria o ambiente da sessão em uso pelo da instância de
# teste. O aninhado usa o backend Wayland e nunca toca no DRM, então não testa
# a escolha de GPU nem AQ_DRM_DEVICES.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
usuario=1
desligado=0
jogo_pessoal=0
manter=0
for opcao in "$@"; do
  case "$opcao" in
    --sem-usuario) usuario=0 ;;
    --vidro-desligado) desligado=1 ;;
    --jogo-pessoal) jogo_pessoal=1 ;;
    --manter) manter=1 ;;
    *) echo "opção desconhecida: $opcao" >&2; exit 1 ;;
  esac
done

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
  if ((jogo_pessoal)); then
    echo 'hl.window_rule({ match = { class = "^org[.]jangada[.]teste_jogo$" }, tag = "+vidro-jogo" })'
  fi
} >"$tmp/hyprland.lua"

config_teste="${XDG_CONFIG_HOME:-$HOME/.config}"
if ((!usuario || desligado)); then
  config_teste="$tmp/config"
  mkdir -p "$config_teste/jangada"
  if ((desligado)); then
    echo 'JANGADA_VIDRO=0' >"$config_teste/jangada/jangada.conf"
  fi
fi

antes="$(ls "$runtime/hypr" 2>/dev/null | sort)"
env -u HYPRLAND_INSTANCE_SIGNATURE JANGADA_PATH="$repo" XDG_CONFIG_HOME="$config_teste" \
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
HYPRLAND_INSTANCE_SIGNATURE="$sig" hyprctl binds -j >"$tmp/binds.json" 2>"$tmp/binds.erro"
n="$(jq 'if type == "array" then length else 0 end' "$tmp/binds.json" 2>/dev/null || echo 0)"
if ((n > 0)); then
  echo "ok    $n atalhos registrados"
else
  echo "FALHA: nenhum atalho registrado ou resposta JSON inválida"
  cat "$tmp/binds.erro" "$tmp/binds.json"
  falhas=$((falhas + 1))
fi
((falhas == 0)) && echo "configuração carregada sem erros no Hyprland aninhado"
if ((manter)); then
  printf 'instância aninhada: %s\nconfiguração e saída de binds: %s\n' "$sig" "$tmp"
  echo 'Use somente essa assinatura nos comandos de conferência. Enter encerra o teste.'
  read -r _
fi
exit $((falhas > 0))
