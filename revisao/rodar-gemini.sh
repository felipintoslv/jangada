#!/bin/sh
# O Gemini CLI foi aposentado pelo Google em 18/06/2026 e substituído pelo
# Antigravity CLI (comando agy), que não tem modo não interativo documentado.
# A revisão passa a ser feita dentro do agy; este script só mostra como.
cat <<'TXT'
Revisão com o Antigravity CLI:

  cd <pasta do jangada> && agy

Depois, peça ao agente:

  Leia revisao/PROMPT_GEMINI.md e siga as instruções, revisando todos os
  arquivos do repositório, inclusive bin/ e install/. Não altere nenhum
  arquivo; grave apenas a resposta em revisao/gemini-<AAAAMMDD-HHMM>.md.

Use /model para escolher o modelo mais forte do plano e mantenha a aprovação
de ferramentas em modo de revisão (toolPermission: "request-review").
TXT
