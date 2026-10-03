#!/usr/bin/env bash
# Atualiza os comandos padrão da central em cópias próprias da Waybar.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; usa o padrão atualizado"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
python3 - "$alvo" "$novo" <<'PY'
import json
from pathlib import Path
import re
import sys

texto = Path(sys.argv[1]).read_text()
padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'
tokens = [m for m in re.finditer(padrao, texto)
          if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
trocas = {
    'exec': ('$JANGADA_PATH/bin/jangada-agentes --waybar',
             '$JANGADA_PATH/bin/jangada-tarefas --waybar'),
    'on-click': ('setsid -f $JANGADA_PATH/bin/jangada-agentes --janela',
                 'setsid -f $JANGADA_PATH/bin/jangada-tarefas'),
    'on-click-right': ('setsid -f $JANGADA_PATH/bin/jangada-agentes --painel',
                       'setsid -f $JANGADA_PATH/bin/jangada-tarefas --nova'),
}
edicoes = []
for i, token in enumerate(tokens[:-2]):
    if token[0] != '"custom/agentes"' or [t[0] for t in tokens[i+1:i+3]] != [':', '{']:
        continue
    nivel = 0
    campos = {}
    for n in range(i+2, len(tokens)):
        valor = tokens[n][0]
        if nivel == 1 and valor.startswith('"') and n+2 < len(tokens) and tokens[n+1][0] == ':':
            campos[json.loads(valor)] = tokens[n+2]
        if valor in ('{', '['):
            nivel += 1
        elif valor in ('}', ']'):
            nivel -= 1
            if nivel == 0:
                break
    for chave, (antigo, novo) in trocas.items():
        campo = campos.get(chave)
        if campo and campo[0].startswith('"') and json.loads(campo[0]) == antigo:
            edicoes.append((campo.start(), campo.end(), json.dumps(novo)))
    contador = campos.get('exec')
    intervalo = campos.get('interval')
    if contador and json.loads(contador[0]) in (trocas['exec'][0], trocas['exec'][1]):
        if intervalo and intervalo[0] == '30':
            edicoes.append((intervalo.start(), intervalo.end(), '10'))
    break
for de, ate, valor in sorted(edicoes, reverse=True):
    texto = texto[:de] + valor + texto[ate:]
Path(sys.argv[2]).write_text(texto)
PY
[[ "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "central já atualizada ou personalizada"; exit 0; }
copia_seguranca "$alvo"
if simulando; then
  info "[simulação] atualizaria a central de tarefas em $alvo"
else
  executar cp "$novo" "$alvo"
fi
ok "central de tarefas configurada: $alvo"
