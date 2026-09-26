#!/usr/bin/env bash
# Verificações estáticas do repositório. Não instala nem executa nada do jangada.
# Requer: shellcheck, luac (pacote lua), jq, python3.
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
falhas=0
passo() { printf '\n== %s\n' "$*"; }
falha() { printf 'XX %s\n' "$*"; falhas=$((falhas + 1)); }

passo "sintaxe bash"
for f in install.sh install/*.sh bin/* shell/jangada.sh migrations/*.sh; do
  [[ -f "$f" ]] || continue
  bash -n "$f" || falha "bash -n: $f"
done

passo "shellcheck"
if command -v shellcheck >/dev/null; then
  shellcheck -x -S warning install.sh install/*.sh bin/* migrations/*.sh testes/*.sh || falha "shellcheck"
  shellcheck -s sh -S warning shell/jangada.sh || falha "shellcheck shell/jangada.sh"
  # As funções da subshell não estavam sendo conferidas por ninguém.
  shellcheck -S warning shell/jangada-shell.sh || falha "shellcheck shell/jangada-shell.sh"
else
  echo "shellcheck ausente; etapa ignorada"
fi

passo "sintaxe Lua"
luac_bin="$(command -v luac || command -v luac5.4 || command -v luac5.3 || true)"
if [[ -n "$luac_bin" ]]; then
  for f in default/hypr/*.lua config/hypr/*.lua; do
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
  rm -rf "$tmp_cfg"
fi

passo "JSON"
jq empty default/claude/hooks.json || falha "hooks.json"
jq empty default/agy/hooks.json || falha "agy/hooks.json"
# config.jsonc tem comentários; remove as linhas de comentário antes de validar.
sed 's#^[[:space:]]*//.*##' default/waybar/config.jsonc | jq empty || falha "waybar/config.jsonc"
sed 's#^[[:space:]]*//.*##' default/fastfetch/config.jsonc | jq empty || falha "fastfetch/config.jsonc"

passo "skills do Claude Code"
# O Claude Code ignora a skill sem frontmatter ou com name diferente da pasta.
for d in default/claude/skills/*/; do
  d="${d%/}"
  cab="$(awk 'NR == 1 && $0 != "---" {exit} NR > 1 && $0 == "---" {exit} NR > 1' "$d/SKILL.md" 2>/dev/null)"
  grep -qx "name: ${d##*/}" <<<"$cab" || falha "skill ${d##*/}: sem name igual à pasta"
  grep -q '^description:' <<<"$cab" || falha "skill ${d##*/}: sem description"
done

passo "TOML"
if python3 -c 'import tomllib' 2>/dev/null; then
  python3 -c 'import tomllib,sys; tomllib.load(open(sys.argv[1],"rb"))' default/matugen/config.toml || falha "matugen/config.toml"
else
  echo "python sem tomllib (exige 3.11 ou mais novo); etapas de TOML ignoradas"
fi

passo "modelos do matugen referenciados existem"
if python3 -c 'import tomllib' 2>/dev/null; then
python3 - <<'PY' || falha "modelos do matugen"
import tomllib, os, sys
cfg = tomllib.load(open("default/matugen/config.toml", "rb"))
faltando = [t["input_path"] for t in cfg["templates"].values()
            if not os.path.exists(os.path.join("default/matugen", t["input_path"]))]
if faltando:
    print("faltando:", faltando); sys.exit(1)
PY
fi

passo "tema de login (QML)"
qmllint_bin="$(command -v qmllint6 || { [[ -x /usr/lib/qt6/bin/qmllint ]] && echo /usr/lib/qt6/bin/qmllint; } || true)"
if [[ -n "$qmllint_bin" ]]; then
  # sddm, config, userModel e sessionModel vêm do SDDM em tempo de execução.
  "$qmllint_bin" --unqualified disable default/sddm/jangada/Main.qml || falha "qmllint: default/sddm/jangada/Main.qml"
else
  echo "qmllint ausente; etapa ignorada"
fi
for chave in MainScript=Main.qml ConfigFile=theme.conf QtVersion=6; do
  grep -qx "$chave" default/sddm/jangada/metadata.desktop || falha "metadata.desktop sem $chave"
done

passo "comandos citados na configuração do Hyprland existem em bin/"
for c in $(grep -ho 'j\.cmd("[a-z-]*"' default/hypr/*.lua | sed 's/j\.cmd("//; s/"//' | sort -u); do
  [[ -x "bin/$c" ]] || falha "bin/$c citado mas ausente"
done

passo "jangada-validar com claude e agy falsos"
if command -v git >/dev/null && command -v jq >/dev/null; then
  testes/validar.sh || falha "testes/validar.sh"
else
  echo "git ou jq ausente; etapa ignorada"
fi

passo "importação da configuração do niri"
testes/importar.sh || falha "testes/importar.sh"

printf '\n'
((falhas == 0)) && echo "tudo certo" || echo "$falhas falha(s)"
exit $((falhas > 0))
