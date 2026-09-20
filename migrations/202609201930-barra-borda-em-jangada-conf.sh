#!/usr/bin/env bash
# Migração de 20/09/2026: borda da barra no jangada.conf.
#
# A barra passou a aceitar "jangada-barra --posicao topo|base|esquerda|direita".
# A escolha fica em JANGADA_BARRA_POSICAO, no ~/.config/jangada/jangada.conf, e
# o jangada-barra gera a partir dela uma configuração que inclui o config.jsonc
# em uso e sobrescreve o "position" dele.
#
# Quem tem cópia própria de ~/.config/jangada/waybar/config.jsonc com outra
# borda escrita à mão veria a barra voltar para o topo sem aviso, porque o
# padrão da chave nova é "topo". Esta migração lê a borda que está no arquivo
# do usuário e grava a chave com esse valor, uma única vez.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

conf="$JANGADA_CONFIG/jangada.conf"
barra="$JANGADA_CONFIG/waybar/config.jsonc"

if [[ ! -f "$conf" ]]; then
  ok "sem $conf; nada a migrar"
  exit 0
fi

if grep -q '^JANGADA_BARRA_POSICAO=' "$conf"; then
  ok "$conf já tem JANGADA_BARRA_POSICAO; nada a migrar"
  exit 0
fi

borda=topo
if [[ -f "$barra" ]]; then
  case "$(sed -n 's/.*"position"[[:space:]]*:[[:space:]]*"\([a-z]*\)".*/\1/p' "$barra" | head -n1)" in
    bottom) borda=base ;;
    left) borda=esquerda ;;
    right) borda=direita ;;
  esac
fi

copia_seguranca "$conf"
if simulando; then
  info "[simulação] acrescentaria JANGADA_BARRA_POSICAO=$borda em $conf"
else
  {
    printf '\n# Borda em que a barra fica: topo, base, esquerda ou direita.\n'
    printf '# Gravado também pelo "jangada-barra --posicao".\n'
    printf 'JANGADA_BARRA_POSICAO=%s\n' "$borda"
  } >>"$conf"
fi
ok "borda da barra registrada em $conf: $borda"
