#!/usr/bin/env bash
# Em 17/10/2026 o botão do Catamarã na barra passou a mostrar só a logo, com o
# estilo no base.css (202610172200-barra-catamara.sh). O style.css pessoal
# ainda pode ter o bloco #custom-catamara que o Catamarã pôs para a versão de
# texto: cápsula, cor fixa e a classe aviso. Lido depois do base.css, ele
# cobriria a logo. Esta migração tira esse bloco só quando o texto é o
# conhecido, linha a linha, tolerando espaço no fim da linha. Um bloco
# alterado fica, com aviso. O resto do style.css não muda. Roda de novo sem
# efeito.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"
alvo="$JANGADA_CONFIG/waybar/style.css"
[[ -f "$alvo" ]] || { ok "sem estilo próprio da barra; nada a migrar"; exit 0; }
novo="$(mktemp)"
trap 'rm -f "$novo"' EXIT
avisos="$(python3 - "$alvo" "$novo" <<'PY'
from pathlib import Path
import sys

BLOCO = '''/* Catamarã: estados ativo, aviso (entregas pendentes) e erro (portão reprovado). */
#custom-catamara {
  padding: 0 8px;
  border-radius: 8px;
  color: @primaria;
  background: alpha(@primaria, 0.12);
  border: 1px solid alpha(@primaria, 0.30);
}

#custom-catamara:hover {
  background: alpha(@primaria, 0.22);
}

#custom-catamara.aviso {
  color: @atencao;
  background: alpha(@atencao, 0.16);
  border: 1px solid alpha(@atencao, 0.40);
  font-weight: bold;
}

#custom-catamara.erro {
  color: @superficie;
  background: @atencao;
  border: 1px solid @atencao;
  font-weight: bold;
}'''.split('\n')

texto = Path(sys.argv[1]).read_text()
linhas = texto.split('\n')
limpas = [l.rstrip(' \t') for l in linhas]
n = len(BLOCO)
inicio = next((i for i in range(len(linhas) - n + 1) if limpas[i:i + n] == BLOCO), None)
if inicio is None:
    if BLOCO[0] in limpas or '#custom-catamara.aviso' in texto:
        print('bloco antigo do Catamarã com texto diferente do conhecido; mantido')
    sys.exit(0)
fim = inicio + n
# Sem o bloco, as linhas em branco de antes e de depois ficariam juntas.
if fim < len(linhas) and not limpas[fim] and (inicio == 0 or not limpas[inicio - 1]):
    fim += 1
Path(sys.argv[2]).write_text('\n'.join(linhas[:inicio] + linhas[fim:]))
PY
)"
[[ -z "$avisos" ]] || aviso "$avisos: $alvo"
[[ -s "$novo" && "$(<"$novo")" != "$(<"$alvo")" ]] || { ok "estilo da barra sem o bloco antigo do Catamarã; nada a migrar"; exit 0; }
copia_seguranca "$alvo"
executar gravar_atomico "$novo" "$alvo"
ok "bloco antigo do Catamarã retirado do estilo da barra: $alvo"
