#!/usr/bin/env bash
# Corrige controles do microfone em cópias próprias da configuração da Waybar.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/config.jsonc"
[[ -f "$alvo" ]] || { ok "sem cópia própria da barra; nada a migrar"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
python3 - "$alvo" "$novo" <<'PY'
import json, pathlib, re, sys
texto = pathlib.Path(sys.argv[1]).read_text()
# Guarde posições dos tokens para não reformatar o JSONC nem apagar comentários.
padrao = r'\s+|//[^\n]*|/\*[\s\S]*?\*/|"(?:\\.|[^"\\])*"|[{}\[\]:,]|[^\s{}\[\]:,]+'
tokens = [m for m in re.finditer(padrao, texto)
          if not m[0].isspace() and not m[0].startswith(('//', '/*'))]
edicoes = []
for i, token in enumerate(tokens[:-2]):
    if token[0] != '"pulseaudio#microfone"' or [t[0] for t in tokens[i+1:i+3]] != [':', '{']:
        continue
    campos = {}
    nivel = 0
    fim = None
    for n in range(i+2, len(tokens)):
        valor = tokens[n][0]
        if nivel == 1 and valor.startswith('"') and n+2 < len(tokens) and tokens[n+1][0] == ':':
            campos[json.loads(valor)] = tokens[n+2]
        if valor in ('{', '['):
            nivel += 1
        elif valor in ('}', ']'):
            nivel -= 1
            if nivel == 0:
                fim = n
                break
    if fim is None:
        print('configuração incompleta do microfone; preservada', file=sys.stderr)
        break
    dica = campos.get('tooltip-format')
    if dica and dica[0] == '"{source_desc} · {volume}%"':
        edicoes.append((dica.start(), dica.end(), '"{source_desc} · {source_volume}%"'))
    passo = campos.get('scroll-step')
    if not {'on-scroll-up', 'on-scroll-down'} & campos.keys() and (passo is None or passo[0] in ('5', '5.0')):
        ultimo = tokens[fim-1]
        if ultimo[0] not in (',', '{'):
            edicoes.append((ultimo.end(), ultimo.end(), ','))
        controles = '\n    "on-scroll-up": "wpctl set-volume -l 1 @DEFAULT_AUDIO_SOURCE@ 5%+",\n'
        controles += '    "on-scroll-down": "wpctl set-volume @DEFAULT_AUDIO_SOURCE@ 5%-"\n  '
        edicoes.append((tokens[fim].start(), tokens[fim].start(), controles))
    break
for de, ate, novo in sorted(edicoes, reverse=True):
    texto = texto[:de] + novo + texto[ate:]
pathlib.Path(sys.argv[2]).write_text(texto)
PY
[[ "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "microfone já corrigido ou personalizado"; exit 0; }
copia_seguranca "$alvo"
if simulando; then
  info "[simulação] corrigiria controles do microfone em $alvo"
else
  cat "$novo" >"$alvo"
fi
ok "controles do microfone corrigidos: $alvo"
