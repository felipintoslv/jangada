#!/usr/bin/env bash
# Testa migração, central única e interrupções com estado e comandos temporários.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_jangada="$PWD"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export JANGADA_PATH="$repo_jangada" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state" WAYLAND_DISPLAY=wayland-teste
mkdir -p "$tmp/bin" "$XDG_CONFIG_HOME/jangada/waybar" "$XDG_STATE_HOME/jangada/agentes"
alvo="$XDG_CONFIG_HOME/jangada/waybar/config.jsonc"
cat >"$alvo" <<'JSON'
{
 // manter meu comentário
 "modules-left": ["custom/agentes"],
 "custom/agentes": {
   "exec": "$JANGADA_PATH/bin/jangada-agentes --waybar",
   "interval": 30,
   "signal": 10,
   "on-click": "setsid -f $JANGADA_PATH/bin/jangada-agentes --janela",
   "on-click-right": "setsid -f $JANGADA_PATH/bin/jangada-agentes --painel",
 },
}
JSON
cp "$alvo" "$tmp/antes"
migracao=migrations/202610031500-central-tarefas.sh
JANGADA_SIMULAR=1 bash "$migracao"
cmp "$alvo" "$tmp/antes"
bash "$migracao"
grep -q '// manter meu comentário' "$alvo"
grep -q 'jangada-tarefas --waybar' "$alvo"
grep -q 'jangada-tarefas --nova' "$alvo"
grep -q '"interval": 10' "$alvo"
[[ "$(compgen -G "$alvo.jangada-*.bak" | wc -l)" == 1 ]]
cmp "$alvo".jangada-*.bak "$tmp/antes"
cp "$alvo" "$tmp/depois"
bash "$migracao"
cmp "$alvo" "$tmp/depois"
[[ "$(compgen -G "$alvo.jangada-*.bak" | wc -l)" == 1 ]]
printf '{"custom/agentes":{"exec":"pessoal","on-click":"pessoal","interval":45}}\n' >"$alvo"
cp "$alvo" "$tmp/pessoal"
bash "$migracao"
cmp "$alvo" "$tmp/pessoal"
sed 's/"interval": 30/"interval": 45/' "$tmp/antes" >"$alvo"
bash "$migracao"
grep -q 'jangada-tarefas --waybar' "$alvo"
grep -q '"interval": 45' "$alvo"
grep -q '// manter meu comentário' "$alvo"
rm "$alvo"
bash "$migracao"
[[ ! -e "$alvo" ]]

mkdir -p "$tmp/bin"
export PATH="$tmp/bin:$PATH"

mkdir -p "$tmp/jangada/bin" "$tmp/jangada/default/tarefas"
cp bin/jangada-tarefas bin/jangada-shell-config "$tmp/jangada/bin/"
cat >"$tmp/jangada/default/tarefas/central.py" <<'PYTHON'
import os
import sys
from pathlib import Path
if '--waybar' in sys.argv:
    assert Path(os.environ['CHAMADAS_AGENTES']).read_text() == '--limpar-orfaos\n'
print('\n'.join(sys.argv[1:]))
print('sessoes=' + os.environ['JANGADA_SESSOES'])
PYTHON
# O jangada-agentes é do Core: aqui entra um falso no PATH.
cat >"$tmp/bin/jangada-agentes" <<'SH'
#!/bin/sh
printf '%s\n' "$*" >>"$CHAMADAS_AGENTES"
[ "$#" -eq 1 ] && [ "$1" = --limpar-orfaos ] || exit 99
SH
chmod +x "$tmp/bin/jangada-agentes"
export CHAMADAS_AGENTES="$tmp/chamadas-agentes"
echo JANGADA_CENTRAL=agentes >"$XDG_CONFIG_HOME/jangada/jangada.conf"
for opcao in '' --anterior --nova --waybar; do
  JANGADA_PATH="$tmp/jangada" bin/jangada-tarefas ${opcao:+"$opcao"} >"$tmp/saida"
  grep -qx -- '--real' "$tmp/saida"
  grep -A1 -x -- '--estado' "$tmp/saida" | grep -qxF "$XDG_STATE_HOME/jangada/agentes"
  if [[ "$opcao" == --nova || "$opcao" == --waybar ]]; then
    grep -qx -- "$opcao" "$tmp/saida"
  else
    grep -qx -- '--mostrar' "$tmp/saida"
  fi
  [[ "$opcao" == --waybar ]] || [[ ! -e "$CHAMADAS_AGENTES" ]]
done
# O modo simulado não recebe --estado: a pasta de sessões chega pela variável.
JANGADA_PATH="$tmp/jangada" bin/jangada-tarefas --simular >"$tmp/saida"
grep -qxF "sessoes=$XDG_STATE_HOME/jangada/agentes" "$tmp/saida"
! grep -q -- --estado "$tmp/saida"
# Sem o jangada-agentes no PATH (Core ausente), a barra segue sem limpar órfãos.
mv "$tmp/bin/jangada-agentes" "$tmp/jangada-agentes.falso"
rm -f "$CHAMADAS_AGENTES"
printf 'import sys\nprint("\\n".join(sys.argv[1:]))\n' >"$tmp/jangada/default/tarefas/central.py"
JANGADA_PATH="$tmp/jangada" PATH="$tmp/bin:/usr/bin:/bin" bin/jangada-tarefas --waybar >"$tmp/saida"
grep -qx -- '--waybar' "$tmp/saida"
[[ ! -e "$CHAMADAS_AGENTES" ]]
cat >"$tmp/jangada/bin/jangada-tarefas" <<'SH'
#!/bin/sh
printf 'central\n%s\n' "$*"
SH
chmod +x "$tmp/jangada/bin/jangada-tarefas"
cat >"$tmp/bin/fuzzel" <<'SH'
#!/bin/sh
cat >"$MENU_TESTE"
printf 'Nova tarefa\n'
SH
chmod +x "$tmp/bin/fuzzel"
MENU_TESTE="$tmp/menu" JANGADA_PATH="$tmp/jangada" bin/jangada-menu >"$tmp/saida"
grep -qx -- '--nova' "$tmp/saida"
! grep -q 'Central anterior' "$tmp/menu"
echo 'migração, central única e leitura das interrupções passaram'

python3 - "$repo_jangada/default/tarefas/central.py" <<'PY'
import contextlib
import io
import json
import runpy
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
sys.modules['PyQt6'] = None
script = sys.argv[1]
sys.argv = [script, '--waybar']
saida = io.StringIO()
with contextlib.redirect_stdout(saida):
    runpy.run_path(script, run_name='__main__')
assert json.loads(saida.getvalue())['class'] == 'aguardando'
print('contador funciona sem Qt')
PY
