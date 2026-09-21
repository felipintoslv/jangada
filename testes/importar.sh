#!/usr/bin/env bash
# Testa o jangada-importar com um config.kdl pequeno, sem tocar em
# ~/.config/jangada: a saída vai para uma pasta temporária.
#
# Uso: testes/importar.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
mkdir -p "$tmp/mapa/config/niri" "$tmp/config"
cat >"$tmp/mapa/config/niri/config.kdl" <<'KDL'
input {
    keyboard {
        xkb {
            layout "br"      // comentário
            options "caps:escape"
        }
    }
}
output "DP-1" {
    mode "2560x1440@144"
    scale 1.5
    position x=1920 y=0
    transform "90"
}
output "eDP-1" {
    off
}
environment {
    LIBVA_DRIVER_NAME "nvidia"
    DISPLAY null
}
spawn-at-startup "xwayland-satellite"
spawn-at-startup "sh" "-c" "sleep 2 && syncthing"
binds {
    Mod+Return { spawn "kitty"; }
    Mod+B hotkey-overlay-title="Navegador" { spawn "firefox"; }
    Mod+Alt+Z { spawn "kitty" "--title" "notas" "-e" "nvim"; }
    Mod+Shift+Y { spawn "sh" "-c" "$HOME_FALSO/bin/x.sh"; }
    XF86AudioMute allow-when-locked=true { spawn "wpctl" "set-mute" "@DEFAULT_AUDIO_SINK@" "toggle"; }
    Mod+Q { close-window; }
    Mod+O { toggle-overview; }
    Mod+W { spawn "qs" "-c" "noctalia-shell" "ipc" "call" "lockScreen" "lock"; }
    /-Mod+X { spawn "desligado"; }
    Mod+Minus { set-column-width "-10%"; }
}
KDL

env XDG_CONFIG_HOME="$tmp/config" JANGADA_PATH="$repo" \
  "$repo/bin/jangada-importar" --saida "$tmp/saida" "$tmp/mapa" >"$tmp/log" 2>&1
st=$?
conferir "termina sem erro" [ "$st" = 0 ]
u="$tmp/saida/hypr/usuario.lua.importado"
m="$tmp/saida/hypr/monitores.lua.importado"
tem() { grep -qF -- "$2" "$1"; }
conferir "teclado br com opções" tem "$u" 'kb_options = "caps:escape"'
conferir "ambiente sem o null" bash -c '! grep -q DISPLAY "$1"' _ "$u"
conferir "programa ao iniciar sem o sh -c" tem "$u" 'j.ao_iniciar("sleep 2 && syncthing")'
conferir "xwayland-satellite fica de fora" tem "$u" '--   xwayland-satellite'
conferir "título do niri vira descrição" tem "$u" 'j.atalho(SUPER .. " + B", "Navegador", "firefox")'
conferir "terminal com título passa pelo jangada-terminal" \
  tem "$u" 'j.cmd("jangada-terminal", "--titulo notas -e nvim")'
conferir "allow-when-locked vira locked" tem "$u" '"XF86AudioMute"'
conferir "bloqueio do Noctalia vira jangada-bloquear" tem "$u" 'j.cmd("jangada-bloquear")'
conferir "conflito com o padrão sai comentado" tem "$u" '-- j.atalho(SUPER .. " + RETURN"'
conferir "ação sem equivalente listada" tem "$u" '--   Mod+O: toggle-overview'
conferir "nó desligado com /- some" bash -c '! grep -q desligado "$1"' _ "$u"
conferir "largura de coluna vira resize repetido" tem "$u" 'repeating = true'
conferir "monitor com modo, escala, posição e rotação" \
  tem "$m" 'hl.monitor({ output = "DP-1", mode = "2560x1440@144", position = "1920x0", scale = 1.5, transform = 1 })'
conferir "monitor desligado" tem "$m" 'output = "eDP-1", disabled = true'
conferir "terminal no jangada.conf" tem "$tmp/saida/jangada.conf.importado" 'JANGADA_TERMINAL=kitty'
if command -v luac >/dev/null; then
  conferir "usuario.lua.importado é Lua válido" luac -p "$u"
  conferir "monitores.lua.importado é Lua válido" luac -p "$m"
fi
conferir "nada fora da pasta de saída" [ ! -e "$tmp/config/jangada" ]

if ((falhas)); then
  echo "$falhas falha(s); saída:"; cat "$tmp/log"; cat "$u"
  exit 1
fi
echo "todos os testes do importar passaram"
