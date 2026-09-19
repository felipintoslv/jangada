#!/bin/sh
# Envia o repositório ao Gemini CLI para revisão e grava a resposta em
# revisao/gemini-<data>.md. Apenas lê os arquivos; não executa nada do jangada.
# Compatível com o sh do macOS e do Linux.
#
# Uso (na raiz do repositório): sh revisao/rodar-gemini.sh [modelo]
set -eu
cd "$(dirname "$0")/.."

command -v gemini >/dev/null 2>&1 || { echo "gemini CLI não encontrado"; exit 1; }

saida="revisao/gemini-$(date +%Y%m%d-%H%M).md"
pacote="$(mktemp)"
trap 'rm -f "$pacote"' EXIT

# Junta todos os arquivos versionados (menos as próprias revisões) num texto só.
git ls-files | grep -v '^revisao/gemini-' | while IFS= read -r f; do
  printf '\n===== ARQUIVO: %s =====\n' "$f"
  cat "$f"
done >"$pacote"

echo "enviando $(wc -l <"$pacote" | tr -d ' ') linhas ao Gemini..."
if [ $# -ge 1 ]; then
  gemini -m "$1" -p "$(cat revisao/PROMPT_GEMINI.md)" <"$pacote" >"$saida"
else
  gemini -p "$(cat revisao/PROMPT_GEMINI.md)" <"$pacote" >"$saida"
fi
echo "revisão gravada em $saida"
