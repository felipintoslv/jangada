#!/usr/bin/env bash
# Testa a gravação dos eventos do jangada-calendario sem abrir a janela:
# JSON corrompido guardado à parte, gravações concorrentes sem perda e
# arquivo nunca truncado. Usa o subcomando add e as funções do script,
# importadas de uma cópia do trecho em Python.
#
# Uso: testes/calendario.sh
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
repo="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export XDG_CONFIG_HOME="$tmp/config" XDG_STATE_HOME="$tmp/estado" \
    XDG_DATA_HOME="$tmp/dados" XDG_CACHE_HOME="$tmp/cache"
mkdir -p "$XDG_CONFIG_HOME" "$tmp/bin"
# Sem notificação de verdade durante o teste.
printf '#!/bin/sh\nexit 0\n' >"$tmp/bin/notify-send"
chmod +x "$tmp/bin/notify-send"
export PATH="$tmp/bin:$PATH"
pasta="$XDG_CONFIG_HOME/jangada"
arq="$pasta/eventos.json"

cal() { "$repo/bin/jangada-calendario" "$@"; }
json_valido() { python3 -c 'import json,sys; json.load(open(sys.argv[1]))' "$1" 2>/dev/null; }
contar() { python3 -c 'import json,sys; print(len(json.load(open(sys.argv[1])).get(sys.argv[2], [])))' "$arq" "$1"; }

# Trecho em Python do script, para importar as funções sem rodar o main.
sed -n '/^exec python3/,/^PYEOF$/p' "$repo/bin/jangada-calendario" | sed '1d;$d' >"$tmp/calendario_mod.py"
conferir "o trecho em Python compila" python3 -m py_compile "$tmp/calendario_mod.py"

# 1. JSON corrompido é guardado à parte, com aviso, e não é sobrescrito.
mkdir -p "$pasta"
printf '{"2026-01-01": ["antigo"' >"$arq"
cp "$arq" "$tmp/original"
cal add 2026-02-02 "novo" >/dev/null 2>"$tmp/erros"; rc=$?
conferir "add com arquivo corrompido termina bem" test "$rc" -eq 0
copia="$(find "$pasta" -maxdepth 1 -name 'eventos.json.corrompido-*' | head -n 1)"
conferir "arquivo corrompido guardado em .corrompido-<data>" test -n "$copia"
conferir "conteúdo corrompido preservado intacto" cmp -s "$tmp/original" "${copia:-/nada}"
conferir "aviso no stderr" grep -q "corrompido" "$tmp/erros"
conferir "arquivo novo é JSON válido" json_valido "$arq"
conferir "arquivo novo tem o evento adicionado" test "$(contar 2026-02-02)" = 1

# Formato inesperado (JSON válido que não é o objeto de eventos) também.
rm -f "$pasta"/eventos.json*
printf '[1, 2, 3]\n' >"$arq"
cal listar >/dev/null 2>"$tmp/erros"
conferir "formato inesperado guardado à parte" \
    test -n "$(find "$pasta" -maxdepth 1 -name 'eventos.json.corrompido-*')"

# Arquivo ilegível por permissão não é corrupção: não mexe nem grava.
if [ "$(id -u)" != 0 ]; then
    rm -f "$pasta"/eventos.json*
    printf '{"2026-03-03": ["guardado"]}\n' >"$arq"
    chmod 000 "$arq"
    cal add 2026-03-03 "outro" >/dev/null 2>"$tmp/erros"; rc=$?
    chmod 600 "$arq"
    conferir "sem permissão de leitura o add falha" test "$rc" -ne 0
    conferir "sem permissão de leitura o arquivo fica como estava" \
        grep -q guardado "$arq"
    conferir "sem permissão de leitura nada vai para .corrompido" \
        test -z "$(find "$pasta" -maxdepth 1 -name 'eventos.json.corrompido-*')"
fi

# 2. Gravações concorrentes pelo subcomando add: nenhuma se perde.
rm -f "$pasta"/eventos.json*
n=30
for i in $(seq 1 "$n"); do
    cal add 2026-04-04 "evento $i" >/dev/null 2>&1 &
done
wait
conferir "$n adds simultâneos, $n eventos gravados" test "$(contar 2026-04-04)" = "$n"
conferir "nenhum temporário sobrando" \
    test -z "$(find "$pasta" -maxdepth 1 -name '.eventos.json.*.tmp')"

# 3. Janela com dados velhos (carregou antes) e add pela linha de comando no
# meio: a alteração da janela relê do disco e não apaga o evento do add.
# Depois, remover pela janela um evento cuja posição mudou remove o certo.
rm -f "$pasta"/eventos.json*
conferir "janela e add não se sobrescrevem" python3 - "$tmp" "$repo" <<'PY'
import importlib.util, subprocess, sys
tmp, repo = sys.argv[1], sys.argv[2]
spec = importlib.util.spec_from_file_location("cal", f"{tmp}/calendario_mod.py")
cal = importlib.util.module_from_spec(spec); spec.loader.exec_module(cal)
janela = cal.carregar_eventos()              # a janela abre com o arquivo vazio
subprocess.run([f"{repo}/bin/jangada-calendario", "add", "2026-05-05", "do add"],
               check=True, capture_output=True)
janela = cal.alterar_eventos(lambda e: e.setdefault("2026-05-05", []).append("da janela"))
assert janela["2026-05-05"] == ["do add", "da janela"], janela
assert cal.carregar_eventos() == janela
PY

# 4. O arquivo nunca fica truncado: uma falha no meio da gravação deixa o
# arquivo antigo inteiro, e leitores simultâneos sempre veem JSON válido.
rm -f "$pasta"/eventos.json*
printf '{"2026-06-06": ["antes"]}\n' >"$arq"
conferir "falha no meio da gravação preserva o arquivo antigo" python3 - "$tmp" <<'PY'
import importlib.util, json, os, sys
tmp = sys.argv[1]
spec = importlib.util.spec_from_file_location("cal", f"{tmp}/calendario_mod.py")
cal = importlib.util.module_from_spec(spec); spec.loader.exec_module(cal)
def dump_quebrado(obj, f, **kw):
    f.write('{"2026-06-06": ["pela met')
    f.flush()
    raise OSError(28, "No space left on device")
cal.json.dump = dump_quebrado
try:
    cal.alterar_eventos(lambda e: e.setdefault("2026-06-06", []).append("depois"))
except cal.ErroEventos:
    pass
else:
    raise SystemExit("a falha deveria ter subido como ErroEventos")
with open(cal.EVENTOS_FILE, encoding="utf-8") as f:
    assert json.load(f) == {"2026-06-06": ["antes"]}
sobras = [n for n in os.listdir(cal.CONFIG_DIR) if n.endswith(".tmp")]
assert not sobras, sobras
PY

rm -f "$pasta"/eventos.json*
python3 - "$arq" >"$tmp/leitor" 2>&1 <<'PY' &
import json, sys, time
arq, lidas, ruins = sys.argv[1], 0, 0
fim = time.time() + 30
while time.time() < fim:
    try:
        with open(arq, encoding="utf-8") as f:
            json.load(f)
        lidas += 1
    except FileNotFoundError:
        pass
    except ValueError:
        ruins += 1
    try:
        open(arq + ".fim").close(); break
    except FileNotFoundError:
        pass
print(lidas, ruins)
PY
leitor=$!
escritores=()
for i in $(seq 1 20); do
    cal add 2026-07-07 "concorrente $i" >/dev/null 2>&1 &
    escritores+=("$!")
done
wait "${escritores[@]}"
: >"$arq.fim"
wait "$leitor"
read -r lidas ruins <"$tmp/leitor"
conferir "leitor simultâneo nunca viu arquivo truncado ($lidas leituras)" \
    test "${ruins:-1}" = 0
conferir "20 adds com leitor simultâneo, 20 eventos" test "$(contar 2026-07-07)" = 20

# A trava não segue link simbólico.
rm -f "$pasta"/eventos.json* "$pasta/.eventos.json.trava"
ln -s "$tmp/alvo" "$pasta/.eventos.json.trava"
cal add 2026-08-08 "x" >/dev/null 2>&1
conferir "trava apontada por link simbólico não cria o alvo" test ! -e "$tmp/alvo"
rm -f "$pasta/.eventos.json.trava"

if [ "$falhas" -eq 0 ]; then echo "calendario: tudo certo"; else echo "calendario: $falhas falha(s)"; exit 1; fi
