#!/usr/bin/env bash
# Três comandos saíram do Shell: jangada-update (agora jangada-sistema-update,
# achado pelo botão de update), jangada-painel e jangada-agentes (agora do Core
# ou do Monitor, no PATH). A cópia própria da barra ainda chama o caminho antigo
# em $JANGADA_PATH/bin. Esta migração troca só o botão de update, quando a
# linha é idêntica à antiga, e tira o prefixo $JANGADA_PATH/bin/ dos comandos
# que não existem mais lá. Comandos do Shell ficam como estão, e o resto do
# arquivo (módulos próprios, comentários, espaços) não é tocado. Roda de novo
# sem efeito.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; nada a migrar"; exit 0; }
novo="$(mktemp "$alvo.jangada-XXXXXX")"
trap 'rm -f "$novo"' EXIT
pendentes="$(python3 - "$alvo" "$novo" "$JANGADA_PATH/bin" <<'PY'
import re
import sys
from pathlib import Path

ANTIGA = r'''"on-click": "setsid -f sh -c '\"$1\"/bin/jangada-terminal --titulo \"jangada update\" -e \"$1\"/bin/jangada-update; pkill -RTMIN+8 -x waybar' _ \"$JANGADA_PATH\"",'''
NOVA = r'''"on-click": "setsid -f sh -c 'cmd=\"$(command -v jangada-update)\" || cmd=\"$1\"/bin/jangada-sistema-update; \"$1\"/bin/jangada-terminal --titulo \"jangada update\" -e \"$cmd\"; pkill -RTMIN+8 -x waybar' _ \"$JANGADA_PATH\"",'''
bin_shell = Path(sys.argv[3])
prefixo = re.compile(r'\$JANGADA_PATH/bin/(jangada-[A-Za-z0-9_-]+)')

def solta(m):
    nome = m.group(1)
    if nome == 'jangada-update' or (bin_shell / nome).exists():
        return m.group(0)
    return nome

saida = []
for linha in Path(sys.argv[1]).read_text().splitlines(keepends=True):
    miolo = linha.rstrip('\r\n')
    sem_indent = miolo.lstrip()
    if sem_indent == ANTIGA:
        linha = miolo[:len(miolo) - len(sem_indent)] + NOVA + linha[len(miolo):]
    else:
        linha = prefixo.sub(solta, linha)
    saida.append(linha)
Path(sys.argv[2]).write_text(''.join(saida))
for n, linha in enumerate(saida, 1):
    if '/bin/jangada-update' in linha:
        print(n)
PY
)"
for n in $pendentes; do
  aviso "linha $n de $alvo ainda chama /bin/jangada-update; confira à mão (o comando agora é jangada-sistema-update)"
done
[[ "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "barra já usa os comandos do Core; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
if simulando; then
  info "[simulação] trocaria os comandos do Core em $alvo"
  exit 0
fi
chmod --reference="$alvo" "$novo" 2>/dev/null || true
mv -f "$novo" "$alvo"
ok "comandos do Core na barra atualizados: $alvo"
