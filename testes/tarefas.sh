#!/usr/bin/env bash
# Testa migração, central única e interrupções com estado e comandos temporários.
set -euo pipefail
cd "$(dirname "$0")/.."
repo_jangada="$PWD"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export JANGADA_PATH="$repo_jangada" XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/state"
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

printf '#!/bin/sh\nexit 1\n' >"$tmp/bin/tmux"
chmod +x "$tmp/bin/tmux"
export PATH="$tmp/bin:$PATH"
jq -n --arg dir "$tmp" --arg agora "$(date -Iseconds)" \
  '{estado:"trabalhando", agente:"codex", dir:$dir, atualizado:$agora}' \
  >"$XDG_STATE_HOME/jangada/agentes/interrompida.json"
cp "$XDG_STATE_HOME/jangada/agentes/interrompida.json" "$tmp/registro"
bin/jangada-agentes --lista >"$tmp/lista"
grep -q $'^interrompido\tinterrompida\t' "$tmp/lista"
cmp "$XDG_STATE_HOME/jangada/agentes/interrompida.json" "$tmp/registro"
# Fim de turno guardado continua sendo fim de turno, mesmo sem tmux.
jq '.estado="concluido"' "$tmp/registro" >"$XDG_STATE_HOME/jangada/agentes/turno.json"
bin/jangada-agentes --lista >"$tmp/lista"
grep -q $'^concluido\tturno\t' "$tmp/lista"

jq -n '{estado:"concluido", atualizado:"2000-01-01T00:00:00+00:00"}' \
  >"$XDG_STATE_HOME/jangada/agentes/orfa.json"
bin/jangada-agentes --limpar-orfaos
bin/jangada-agentes --lista-atualizada >"$tmp/lista"
[[ ! -e "$XDG_STATE_HOME/jangada/agentes/orfa.json" ]]
jq -e '.estado == "interrompido"' "$XDG_STATE_HOME/jangada/agentes/interrompida.json" >/dev/null
grep -q $'^concluido\tturno\t' "$tmp/lista"

# Prévia gráfica sai dos metadados protegidos e informa os commits atuais.
mkdir -p "$XDG_STATE_HOME/jangada/revisoes" "$tmp/projeto"
git -C "$tmp/projeto" init -q -b main
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm inicio --allow-empty
git -C "$tmp/projeto" checkout -qb agente/previa
echo proposta >"$tmp/projeto/proposta.txt"
git -C "$tmp/projeto" add proposta.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm proposta
jq -n --arg raiz "$tmp/projeto" '{raiz:$raiz, ramo:"agente/previa", base:"main"}' \
  >"$XDG_STATE_HOME/jangada/revisoes/previa.json"
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e '.candidate_sha != .base_sha and (.arquivos | contains("proposta.txt")) and .marca == {}' "$tmp/previa.json" >/dev/null
# Caminhos longos e contagem exata por arquivo não podem desaparecer na tela.
nome_longo="$(printf 'caminho%.0s' {1..18}).txt"
echo linha >"$tmp/projeto/$nome_longo"
git -C "$tmp/projeto" add "$nome_longo"
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm longo
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e --arg nome "$nome_longo" '.arquivos | contains("+1 -0 " + $nome)' "$tmp/previa.json" >/dev/null
b_previa="$(git -C "$tmp/projeto" rev-parse main)"
c_previa="$(git -C "$tmp/projeto" rev-parse agente/previa)"
jq -n --arg b "$b_previa" --arg c "$c_previa" \
  '{base_sha:$b, candidate_sha:$c, reviewer:"codex", local_verified:true, independent:false, limpo:true}' \
  >"$XDG_STATE_HOME/jangada/revisoes/validacao-previa.aprovado"
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e '.marca_atual and (.validacao_local | contains("passou")) and .marca.independent == false and .marca.reviewer == "codex"' "$tmp/previa.json" >/dev/null
jq '.independent = true' "$XDG_STATE_HOME/jangada/revisoes/validacao-previa.aprovado" >"$tmp/marca"
mv "$tmp/marca" "$XDG_STATE_HOME/jangada/revisoes/validacao-previa.aprovado"
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e '.marca_atual and .marca.independent' "$tmp/previa.json" >/dev/null
# Candidato diferente mantém os metadados identificados como outra entrega.
echo depois >>"$tmp/projeto/proposta.txt"
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qam depois
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e '(.marca_atual | not) and (.validacao_local | contains("outra entrega"))' "$tmp/previa.json" >/dev/null
# Base diferente também invalida a indicação da prévia.
git -C "$tmp/projeto" checkout -q main
echo base >"$tmp/projeto/base.txt"
git -C "$tmp/projeto" add base.txt
git -C "$tmp/projeto" -c user.name=t -c user.email=t@t commit -qm base
jq --arg c "$(git -C "$tmp/projeto" rev-parse agente/previa)" '.candidate_sha = $c' \
  "$XDG_STATE_HOME/jangada/revisoes/validacao-previa.aprovado" >"$tmp/marca"
mv "$tmp/marca" "$XDG_STATE_HOME/jangada/revisoes/validacao-previa.aprovado"
bin/jangada-agentes --integracao-json previa >"$tmp/previa.json"
jq -e '(.marca_atual | not) and (.validacao_local | contains("outra entrega"))' "$tmp/previa.json" >/dev/null
# Estado gravável não muda a origem da prévia.
jq -n '{raiz:"/inexistente", ramo:"agente/outro"}' >"$XDG_STATE_HOME/jangada/agentes/previa.json"
bin/jangada-agentes --integracao-json previa >"$tmp/previa2.json"
cmp "$tmp/previa.json" "$tmp/previa2.json"

mkdir -p "$tmp/jangada/bin" "$tmp/jangada/default/tarefas"
cp bin/jangada-tarefas bin/jangada-config "$tmp/jangada/bin/"
cp -r default/provedores "$tmp/jangada/default/"
cat >"$tmp/jangada/default/tarefas/central.py" <<'PYTHON'
import sys
print('\n'.join(sys.argv[1:]))
PYTHON
cat >"$tmp/jangada/bin/jangada-agentes" <<'SH'
#!/bin/sh
exit 99
SH
chmod +x "$tmp/jangada/bin/jangada-agentes"
echo JANGADA_CENTRAL=agentes >"$XDG_CONFIG_HOME/jangada/jangada.conf"
for opcao in '' --anterior --nova --waybar; do
  JANGADA_PATH="$tmp/jangada" bin/jangada-tarefas ${opcao:+"$opcao"} >"$tmp/saida"
  grep -qx -- '--real' "$tmp/saida"
  if [[ "$opcao" == --nova || "$opcao" == --waybar ]]; then
    grep -qx -- "$opcao" "$tmp/saida"
  else
    grep -qx -- '--mostrar' "$tmp/saida"
  fi
done
cat >"$tmp/jangada/bin/jangada-tarefas" <<'SH'
#!/bin/sh
printf 'central\n%s\n' "$*"
SH
chmod +x "$tmp/jangada/bin/jangada-tarefas"
for opcao in --janela --janela-anterior --painel --painel-anterior; do
  JANGADA_PATH="$tmp/jangada" bin/jangada-agentes "$opcao" >"$tmp/saida"
  grep -qx central "$tmp/saida"
done
JANGADA_PATH="$tmp/jangada" bin/jangada-agente --janela >"$tmp/saida"
grep -qx central "$tmp/saida"
grep -qx -- '--nova' "$tmp/saida"
cat >"$tmp/jangada/bin/jangada-terminal" <<'SH'
#!/bin/sh
printf '%s\n' "$@"
SH
chmod +x "$tmp/jangada/bin/jangada-terminal"
JANGADA_PATH="$tmp/jangada" bin/jangada-agente --janela --projeto "$tmp" >"$tmp/saida"
grep -qx -- '--projeto' "$tmp/saida"
! grep -qx central "$tmp/saida"
mkdir -p "$XDG_CONFIG_HOME/jangada/agentes"
printf 'COMANDO=codex\nDESCRICAO=Meu perfil local\nJANGADA_VALIDAR_REVISOR=agy\n' >"$XDG_CONFIG_HOME/jangada/agentes/codex.conf"
printf 'COMANDO=agy\n' >"$XDG_CONFIG_HOME/jangada/agentes/antigo.conf"
JANGADA_PATH="$repo_jangada" bin/jangada-agente --perfis >"$tmp/perfis.json"
jq -e 'any(.[]; .nome == "codex" and .descricao == "Meu perfil local") and any(.[]; .nome == "codex-agy") and any(.[]; .nome == "claude-agy") and all(.[]; .nome != "antigo")' "$tmp/perfis.json" >/dev/null
JANGADA_PATH="$repo_jangada" bin/jangada-agente --capacidades-json >"$tmp/capacidades.json"
jq -e '([.principais[].nome] == ["claude", "codex"]) and all(.principais[]; .instalado | type == "boolean")
  and any(.perfis[]; .nome == "codex-agy") and all(.perfis[]; .nome != "antigo")
  and all(.principais[], .perfis[]; .nome != "agy")' "$tmp/capacidades.json" >/dev/null
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
