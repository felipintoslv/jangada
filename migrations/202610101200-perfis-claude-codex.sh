#!/usr/bin/env bash
# Migração de 10/10/2026: os perfis padrão passaram a ser só dois.
#
# Saíram claude-agy, claude-claude, codex, codex-agy e codex-codex; ficaram
# claude-codex e codex-claude, com revisor de outro provedor e delegação ao
# agy. O estado de cada sessão guarda o nome do perfil, e o
# jangada-agentes --restaurar recusa a sessão cujo perfil não existe mais.
#
# Esta migração troca, no estado das sessões, o perfil que saiu pelo novo do
# mesmo executor. O revisor da sessão é mantido: quando o estado não o
# guarda, entra o que o perfil antigo fixava. A delegação da sessão
# restaurada passa a ser a do perfil novo. Sessão cujo perfil tem cópia do
# usuário em ~/.config/jangada/agentes não muda.
set -euo pipefail
# shellcheck source=install/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/../install/lib.sh"

trocadas=0
for arq in "$JANGADA_ESTADO"/agentes/*.json; do
  [[ -f "$arq" ]] || continue
  perfil="$(jq -r '.perfil // "" | tostring' "$arq" 2>/dev/null)" || continue
  case "$perfil" in
    claude-agy) novo=claude-codex; revisor=agy ;;
    claude-claude) novo=claude-codex; revisor=claude ;;
    codex) novo=codex-claude; revisor=claude ;;
    codex-agy) novo=codex-claude; revisor=agy ;;
    codex-codex) novo=codex-claude; revisor=codex ;;
    *) continue ;;
  esac
  [[ -r "$JANGADA_CONFIG/agentes/$perfil.conf" ]] && continue
  trocadas=$((trocadas + 1))
  if simulando; then
    info "[simulação] trocaria o perfil $perfil por $novo em $arq"
    continue
  fi
  copia_seguranca "$arq"
  tmp="$(mktemp "$arq.XXXXXX")"
  if jq --arg p "$novo" --arg r "$revisor" \
    '.perfil = $p | if (.revisor // "") == "" then .revisor = $r else . end' "$arq" >"$tmp"; then
    mv -f "$tmp" "$arq"
    ok "sessão $(basename "$arq" .json): perfil $perfil trocado por $novo"
  else
    rm -f "$tmp"
    morrer "não foi possível regravar $arq"
  fi
done
((trocadas)) || ok "nenhuma sessão guardava perfil retirado"
