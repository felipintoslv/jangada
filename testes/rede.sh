#!/usr/bin/env bash
# Testa a conexão a uma rede Wi-Fi com senha no jangada-rede: a senha não
# aparece em nenhum argumento do nmcli e chega pelo passwd-file no formato
# 802-11-wireless-security.psk:SENHA. Nenhuma rede de verdade é usada: o
# nmcli, o fuzzel e o notify-send são falsos e registram como foram chamados.
#
# Uso: testes/rede.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" FALSO="$tmp/falso"
mkdir -p "$HOME" "$tmp/bin" "$FALSO"
senha='senha secreta:com dois pontos'
export FALSA_SENHA="$senha"

# nmcli falso. FALSO/seguranca é o campo SECURITY da rede "Minha Rede";
# FALSO/perfil, quando existe, é o perfil já criado para ela.
cat >"$tmp/bin/nmcli" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FALSO/argv"
tudo="$*"
case "$*" in
  "radio wifi") echo enabled ;;
  "-t -f TYPE device") echo wifi ;;
  "-t -f IN-USE,SSID,SIGNAL,SECURITY device wifi list")
    echo " :Minha Rede:80:$(cat "$FALSO/seguranca")" ;;
  "-t -f SECURITY,SSID device wifi list")
    echo "WPA2:Outra"; echo "$(cat "$FALSO/seguranca"):Minha Rede" ;;
  "-s device wifi connect Minha Rede") exit 4 ;;
  "-g connection.type,connection.uuid connection show id Minha Rede")
    [[ -f "$FALSO/perfil" ]] || exit 10
    echo "802-11-wireless:uuid-minha" ;;
  "connection add type wifi con-name Minha Rede ssid Minha Rede wifi-sec.key-mgmt "*)
    printf '%s\n' "${tudo##* }" >"$FALSO/chave"; : >"$FALSO/perfil" ;;
  "connection up uuid uuid-minha passwd-file "*)
    cat "${tudo##* }" >"$FALSO/passwd" ;;
  *) exit 0 ;;
esac
EOF
# fuzzel falso: escolhe a rede no menu e digita a senha no pedido de senha.
cat >"$tmp/bin/fuzzel" <<'EOF'
#!/usr/bin/env bash
case " $* " in
  *" --password "*) printf '%s\n' "$FALSA_SENHA" ;;
  *) grep -m1 "Wi-Fi: Minha Rede" ;;
esac
EOF
cat >"$tmp/bin/notify-send" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "$*" >>"$FALSO/avisos"
EOF
chmod +x "$tmp/bin/"*

rodar() {
  rm -f "$FALSO"/{argv,avisos,chave,passwd,perfil}
  printf '%s\n' "$1" >"$FALSO/seguranca"
  [[ "${2:-}" == perfil ]] && : >"$FALSO/perfil"
  PATH="$tmp/bin:$PATH" "$repo_jangada/bin/jangada-rede" menu >/dev/null 2>&1
}

# WPA2, rede nova: cria o perfil sem senha e ativa com o passwd-file.
rodar "WPA2"
conferir "WPA2: a senha não vai em argumento do nmcli" bash -c '! grep -qF "secreta" "$1"' _ "$FALSO/argv"
conferir "WPA2: perfil criado com wpa-psk" test "$(cat "$FALSO/chave" 2>/dev/null)" = wpa-psk
conferir "WPA2: passwd-file no formato do nmcli" \
  test "$(cat "$FALSO/passwd" 2>/dev/null)" = "802-11-wireless-security.psk:$senha"
conferir "WPA2: avisa que conectou" grep -q "Conectado a Minha Rede" "$FALSO/avisos"

# Transição WPA2/WPA3 fica em wpa-psk; WPA3 puro usa sae.
rodar "WPA2 WPA3"
conferir "WPA2/WPA3: perfil com wpa-psk" test "$(cat "$FALSO/chave" 2>/dev/null)" = wpa-psk
rodar "WPA3"
conferir "WPA3: perfil com sae" test "$(cat "$FALSO/chave" 2>/dev/null)" = sae
conferir "WPA3: senha pelo passwd-file" \
  test "$(cat "$FALSO/passwd" 2>/dev/null)" = "802-11-wireless-security.psk:$senha"

# Perfil já existente: não cria outro, só ativa com a senha nova.
rodar "WPA2" perfil
conferir "perfil existente: não cria outro" test ! -e "$FALSO/chave"
conferir "perfil existente: senha pelo passwd-file" \
  test "$(cat "$FALSO/passwd" 2>/dev/null)" = "802-11-wireless-security.psk:$senha"

# 802.1X pede mais que uma senha: nada é criado, o usuário vai para o editor.
rodar "WPA2 802.1X"
conferir "802.1X: não cria perfil" test ! -e "$FALSO/chave"
conferir "802.1X: não ativa" test ! -e "$FALSO/passwd"
conferir "802.1X: indica o editor" grep -q "editor de rede" "$FALSO/avisos"
conferir "nenhuma chamada levou a senha" bash -c '! grep -qF "secreta" "$1"' _ "$FALSO/argv"

if ((falhas)); then
  echo "rede: $falhas falha(s)"
  exit 1
fi
echo "rede: tudo certo"
