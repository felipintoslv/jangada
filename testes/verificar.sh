#!/usr/bin/env bash
# Verificações do repositório do Shell. Roda sem o Core e sem o Monitor.
# Não instala nem executa nada com impacto permanente no sistema.
# Requer: shellcheck (opcional), luac (opcional), jq, python3.
set -uo pipefail
export LC_ALL=C.UTF-8
unset JANGADA_ISOLADO JANGADA_DELEGAR JANGADA_VALIDAR_REVISOR
cd "$(dirname "$0")/.." || exit 1
falhas=0
passo() { printf '\n== %s\n' "$*"; }
falha() { printf 'XX %s\n' "$*"; falhas=$((falhas + 1)); }

passo "capacidades da máquina"
testes/capacidades.sh || falha "falta capacidade exigida em JANGADA_TESTES_EXIGIR"

shopt -s nullglob
scripts_shell=(install.sh install/*.sh bin/* jangada.sh jangada-shell.sh migrations/*.sh)
shopt -u nullglob

passo "sintaxe bash"
for f in "${scripts_shell[@]}"; do
  [[ -f "$f" ]] || continue
  bash -n "$f" || falha "bash -n: $f"
done

passo "shellcheck"
if command -v shellcheck >/dev/null; then
  shellcheck -x -S warning install.sh install/*.sh bin/* migrations/*.sh testes/*.sh \
    jangada-shell.sh || falha "shellcheck"
  shellcheck -s sh -S warning jangada.sh || falha "shellcheck jangada.sh"
else
  echo "shellcheck ausente; etapa ignorada"
fi

passo "sintaxe Lua do Hyprland"
luac_bin="$(command -v luac || command -v luac5.4 || command -v luac5.3 || true)"
if [[ -n "$luac_bin" ]]; then
  for f in hyprland/*.lua default/hypr/*.lua; do
    [[ -f "$f" ]] || continue
    "$luac_bin" -p "$f" || falha "luac: $f"
  done
else
  echo "luac ausente; etapa ignorada"
fi

passo "execução da configuração Lua com API imitada"
lua_bin="$(command -v lua5.4 || command -v lua || true)"
if [[ -n "$lua_bin" ]]; then
  "$lua_bin" testes/simular-hypr.lua "$PWD" || falha "simulação da configuração Lua"
  tmp_cfg="$(mktemp -d)"; mkdir -p "$tmp_cfg/jangada"
  echo "JANGADA_INTERFACE=noctalia" >"$tmp_cfg/jangada/jangada.conf"
  "$lua_bin" testes/simular-hypr.lua "$PWD" "$tmp_cfg" || falha "simulação no modo noctalia"
  mkdir -p "$tmp_cfg/casa"
  for m in usuario monitores cores; do
    echo "error('carregou $m.lua da pasta atual')" >"$tmp_cfg/casa/$m.lua"
  done
  (cd "$tmp_cfg/casa" && "$lua_bin" "$OLDPWD/testes/simular-hypr.lua" "$OLDPWD") >/dev/null \
    || falha "simulação com usuario.lua na pasta atual"
  rm -rf "$tmp_cfg"
fi

passo "vidro fosco"
if [[ -n "$lua_bin" ]]; then
  "$lua_bin" testes/vidro-fosco.lua "$PWD" || falha "vidro fosco: eventos Lua"
fi
python3 testes/vidro-fosco.py || falha "vidro fosco: fundos e migração"

passo "configurações JSONC e TOML do Shell"
arq_waybar="waybar/config.jsonc"
[[ -f "$arq_waybar" ]] || arq_waybar="default/waybar/config.jsonc"
sed 's#^[[:space:]]*//.*##' "$arq_waybar" | jq empty || falha "waybar config.jsonc"

arq_fastfetch="temas/fastfetch/config.jsonc"
[[ -f "$arq_fastfetch" ]] || arq_fastfetch="default/fastfetch/config.jsonc"
sed 's#^[[:space:]]*//.*##' "$arq_fastfetch" | jq empty || falha "fastfetch config.jsonc"

arq_matugen="temas/matugen/config.toml"
[[ -f "$arq_matugen" ]] || arq_matugen="default/matugen/config.toml"
if python3 -c 'import tomllib' 2>/dev/null; then
  python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],"rb"))' "$arq_matugen" || falha "matugen config.toml"
fi

passo "fichas visuais e paleta de cores"
python3 testes/fichas.py || falha "testes/fichas.py"

passo "tema de login (SDDM)"
arq_sddm="temas/sddm/jangada/metadata.desktop"
[[ -f "$arq_sddm" ]] || arq_sddm="default/sddm/jangada/metadata.desktop"
for chave in MainScript=Main.qml ConfigFile=theme.conf QtVersion=6; do
  grep -qx "$chave" "$arq_sddm" || falha "metadata.desktop sem $chave"
done

passo "testes de interface: aninhado, barra, interface e atalhos"
testes/aninhado.sh || falha "testes/aninhado.sh"
testes/barra.sh || falha "testes/barra.sh"
testes/barra-comandos-core.sh || falha "testes/barra-comandos-core.sh"
testes/interface.sh || falha "testes/interface.sh"

passo "testes de interface: tarefas (Qt)"
python3 testes/tarefas.py || falha "testes/tarefas.py"
testes/tarefas.sh || falha "testes/tarefas.sh"

passo "testes de interface: utilitários (rede, bluetooth, snapshot, calendário, importar, mapear)"
testes/rede.sh || falha "testes/rede.sh"
testes/bluetooth.sh || falha "testes/bluetooth.sh"
testes/snapshot.sh || falha "testes/snapshot.sh"
testes/calendario.sh || falha "testes/calendario.sh"
testes/importar.sh || falha "testes/importar.sh"
testes/mapear.sh || falha "testes/mapear.sh"

passo "diagnóstico, reversão, regras e fronteira com o Core"
testes/diagnostico.sh || falha "testes/diagnostico.sh"
testes/vigia.sh || falha "testes/vigia.sh"
testes/reverter.sh || falha "testes/reverter.sh"
testes/regra1.sh || falha "testes/regra1.sh"
testes/contratos-caminhos.sh || falha "testes/contratos-caminhos.sh"
testes/shell-core.sh || falha "testes/shell-core.sh"
python3 testes/sambura-retirada.py || falha "testes/sambura-retirada.py"
python3 testes/barra-catamara.py || falha "testes/barra-catamara.py"
python3 testes/barra-catamara-migracao.py || falha "testes/barra-catamara-migracao.py"
python3 testes/barra-catamara-estilo.py || falha "testes/barra-catamara-estilo.py"
python3 testes/teclado-waybar.py || falha "testes/teclado-waybar.py"

passo "atualização do sistema e instalação"
testes/update.sh || falha "testes/update.sh"
python3 testes/update-codigo.py || falha "testes/update-codigo.py"

printf '\n'
((falhas == 0)) && echo "todos os testes do Shell passaram" || echo "$falhas falha(s)"
exit $((falhas > 0))
