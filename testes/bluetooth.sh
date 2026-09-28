#!/usr/bin/env bash
# Testa o pareamento no jangada-bluetooth: parear não implica confiar, o trust
# só roda quando o usuário escolhe confiar no menu, e um pareamento que falha
# não tenta confiar nem conectar. O bluetoothctl, o fuzzel e o notify-send são
# falsos e registram como foram chamados.
#
# Uso: testes/bluetooth.sh
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/config" FALSO="$tmp/falso"
mkdir -p "$HOME" "$tmp/bin" "$FALSO"
mac="AA:BB:CC:DD:EE:FF"

# bluetoothctl falso: um aparelho à vista; FALSO/pair-falha faz o pair falhar.
cat >"$tmp/bin/bluetoothctl" <<FIM
#!/usr/bin/env bash
printf '%s\n' "\$*" >>"\$FALSO/argv"
case "\$1" in
  devices) echo "Device $mac Fone Teste" ;;
  pair) [[ ! -e "\$FALSO/pair-falha" ]] ;;
esac
FIM
# fuzzel falso: no menu de pareamento escolhe o aparelho; no de confiança,
# escolhe a linha que começa com FALSO/resposta, ou fecha o menu sem ela.
cat >"$tmp/bin/fuzzel" <<'FIM'
#!/usr/bin/env bash
case " $* " in
  *"parear dispositivo"*) grep -m1 'Fone Teste' ;;
  *"confiar em"*)
    : >"$FALSO/perguntou"
    [[ -f "$FALSO/resposta" ]] || exit 1
    grep -m1 "^$(cat "$FALSO/resposta")" ;;
  *) exit 1 ;;
esac
FIM
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/notify-send"
chmod +x "$tmp/bin/"*

parear() {
  rm -f "$FALSO/argv" "$FALSO/perguntou"
  PATH="$tmp/bin:$PATH" JANGADA_PATH="$PWD" bin/jangada-bluetooth scan >/dev/null 2>&1
  rc=$?
}
chamou() { grep -qx "$1" "$FALSO/argv"; }
nao_chamou() { ! grep -qE "$1" "$FALSO/argv"; }

# Caso 1: fechar o menu de confiança vale como não confiar.
parear
conferir "caso 1: termina sem erro ($rc)" test "$rc" -eq 0
conferir "caso 1: pareia" chamou "pair $mac"
conferir "caso 1: pergunta se confia" test -e "$FALSO/perguntou"
conferir "caso 1: não confia" nao_chamou "^trust"
conferir "caso 1: conecta" chamou "connect $mac"

# Caso 2: escolher não confiar.
echo "Não confiar" >"$FALSO/resposta"
parear
conferir "caso 2: não confia" nao_chamou "^trust"
conferir "caso 2: conecta" chamou "connect $mac"

# Caso 3: escolher confiar.
echo "Confiar" >"$FALSO/resposta"
parear
conferir "caso 3: confia" chamou "trust $mac"
conferir "caso 3: conecta" chamou "connect $mac"

# Caso 4: pareamento que falha para ali.
: >"$FALSO/pair-falha"
parear
conferir "caso 4: termina sem erro ($rc)" test "$rc" -eq 0
conferir "caso 4: não pergunta se confia" test ! -e "$FALSO/perguntou"
conferir "caso 4: não confia nem conecta" nao_chamou "^(trust|connect)"

if ((falhas)); then
  echo "$falhas teste(s) do bluetooth falharam"
  exit 1
fi
echo "todos os testes do bluetooth passaram"
