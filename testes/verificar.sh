#!/usr/bin/env bash
# Verificações estáticas do repositório. Não instala nem executa nada do jangada.
# Requer: shellcheck, luac (pacote lua), jq, python3.
set -uo pipefail
export LC_ALL=C.UTF-8
unset JANGADA_ISOLADO JANGADA_DELEGAR JANGADA_VALIDAR_REVISOR
cd "$(dirname "$0")/.." || exit 1
falhas=0
passo() { printf '\n== %s\n' "$*"; }
falha() { printf 'XX %s\n' "$*"; falhas=$((falhas + 1)); }

passo "capacidades da máquina"
testes/capacidades.sh || falha "falta capacidade exigida em JANGADA_TESTES_EXIGIR"

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
  # O Hyprland roda com a pasta atual em $HOME: um usuario.lua ou cores.lua ali
  # não pode tomar o lugar dos da configuração.
  mkdir -p "$tmp_cfg/casa"
  for m in usuario monitores cores; do
    echo "error('carregou $m.lua da pasta atual')" >"$tmp_cfg/casa/$m.lua"
  done
  (cd "$tmp_cfg/casa" && "$lua_bin" "$OLDPWD/testes/simular-hypr.lua" "$OLDPWD") >/dev/null \
    || falha "simulação com usuario.lua na pasta atual"
  rm -rf "$tmp_cfg"
fi

passo "JSON"
jq empty default/claude/hooks.json || falha "hooks.json"
jq empty default/agy/hooks.json || falha "agy/hooks.json"
jq empty default/delegacao/roteamento.json || falha "delegacao/roteamento.json"
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

# O tema de gráficos tem um arquivo por linguagem; as cores não podem divergir.
cores_do_tema() { grep -o '^ *"\?[a-z]\+"\? *[=:] *"#[0-9A-Fa-f]\{6\}"' "$1" | tr -d ' "' | tr '=' ':' | sort; }
diff <(cores_do_tema default/claude/skills/graficos/tema_dv.R) <(cores_do_tema default/claude/skills/graficos/tema_dv.py) \
  || falha "skill graficos: tintas ou paleta diferem entre tema_dv.R e tema_dv.py"
[[ "$(cores_do_tema default/claude/skills/graficos/tema_dv.R | wc -l)" -eq 11 ]] \
  || falha "skill graficos: esperadas 5 tintas e 6 cores em tema_dv.R"

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

passo "escritas fora das pastas do jangada estão nas exceções da regra 1"
testes/regra1.sh || falha "testes/regra1.sh"

passo "comandos citados nos protocolos dos agentes existem em bin/"
for c in $(grep -ho '`jangada-[a-z-]*' default/agentes/protocolo*.md | tr -d '`' | sort -u); do
  [[ -x "bin/$c" ]] || falha "bin/$c citado no protocolo mas ausente"
done

passo "jangada-validar com claude e agy falsos"
python3 testes/agente-seletor.py || falha "testes/agente-seletor.py"
if command -v git >/dev/null && command -v jq >/dev/null; then
  testes/validar.sh || falha "testes/validar.sh"
else
  echo "git ou jq ausente; etapa ignorada"
fi

passo "isolamento dos agentes"
testes/isolar.sh || falha "testes/isolar.sh"
testes/restaurar.sh || falha "testes/restaurar.sh"
testes/fim.sh || falha "testes/fim.sh"

passo "histórico de estados dos agentes"
testes/eventos.sh || falha "testes/eventos.sh"
testes/codex.sh || falha "testes/codex.sh"

passo "barra (módulos e migração)"
testes/barra.sh || falha "testes/barra.sh"
testes/interface.sh || falha "testes/interface.sh"
python3 testes/tarefas.py || falha "testes/tarefas.py"
testes/tarefas.sh || falha "testes/tarefas.sh"
python3 testes/pescador.py || falha "testes/pescador.py"
python3 testes/conversa.py || falha "testes/conversa.py"
testes/pescador-modelo.sh || falha "testes/pescador-modelo.sh"

passo "painel de indicadores"
python3 testes/metricas.py || falha "testes/metricas.py"
python3 testes/painel-local.py || falha "testes/painel-local.py"
python3 testes/painel-orquestracao.py || falha "testes/painel-orquestracao.py"
if command -v Rscript >/dev/null && Rscript -e 'quit(status = if (requireNamespace("arrow", quietly = TRUE) && requireNamespace("shiny", quietly = TRUE)) 0 else 1)' 2>/dev/null; then
  Rscript testes/painel-motores.R || falha "testes/painel-motores.R"
fi
testes/painel.sh || falha "testes/painel.sh"

passo "subagentes"
testes/subagentes.sh || falha "testes/subagentes.sh"
testes/delegar.sh || falha "testes/delegar.sh"
python3 testes/delegacao.py || falha "testes/delegacao.py"
python3 testes/avaliar-ollama.py || falha "testes/avaliar-ollama.py"
python3 testes/extracao.py || falha "testes/extracao.py"
python3 testes/orquestracao.py || falha "testes/orquestracao.py"
python3 testes/executor.py || falha "testes/executor.py"
python3 testes/supervisao.py || falha "testes/supervisao.py"
python3 testes/acompanhamento.py || falha "testes/acompanhamento.py"
python3 testes/deterministico.py || falha "testes/deterministico.py"
python3 testes/metricas-projeto.py || falha "testes/metricas-projeto.py"
python3 testes/saude.py || falha "testes/saude.py"
python3 testes/cota-codex.py || falha "testes/cota-codex.py"
python3 testes/codex-economico.py || falha "testes/codex-economico.py"

passo "versões"
testes/versao.sh || falha "testes/versao.sh"

passo "atualização da cópia instalada"
testes/update.sh || falha "testes/update.sh"

passo "diagnóstico do jangada-verificar"
testes/diagnostico.sh || falha "testes/diagnostico.sh"

passo "hooks com a configuração vazia ou inválida"
testes/hooks.sh || falha "testes/hooks.sh"

passo "importação da configuração do niri"
testes/importar.sh || falha "testes/importar.sh"

passo "utilitários (mapear, rede, bluetooth, snapshot, calendário, reverter)"
testes/mapear.sh || falha "testes/mapear.sh"
testes/rede.sh || falha "testes/rede.sh"
testes/bluetooth.sh || falha "testes/bluetooth.sh"
testes/snapshot.sh || falha "testes/snapshot.sh"
testes/calendario.sh || falha "testes/calendario.sh"
testes/reverter.sh || falha "testes/reverter.sh"

printf '\n'
((falhas == 0)) && echo "tudo certo" || echo "$falhas falha(s)"
exit $((falhas > 0))
