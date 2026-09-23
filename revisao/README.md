# Revisões do jangada

Pareceres de revisão cruzada (Antigravity/Gemini), avaliações do Claude sobre
cada parecer, comparações com outros projetos e roteiros. Os registros brutos
do agy (`*.json`, `*.log`) ficam fora do git.

## Cabeçalho fixo

Todo parecer ou avaliação novo começa assim:

```markdown
# <Tipo>: <assunto>

- Data: DD/MM/AAAA
- Commits: <primeiro>..<último>  (ou "repositório inteiro")
- Revisor: <agy + modelo, ou Claude>
- Veredito: aprovado | aprovado com ressalvas | revisar
- Parecer avaliado: <arquivo>  (só nas avaliações)
```

Na avaliação, cada apontamento recebe ACEITO, ACEITO EM PARTE ou REJEITADO,
com a justificativa verificada no código e a ação tomada (commit). É o mesmo
formato usado nas avaliações de revisão cruzada.

## Índice

| Data | Arquivo | Tipo | Assunto | Resultado |
|---|---|---|---|---|
| 19/09/2026 | [gemini-20260919-1850.md](gemini-20260919-1850.md) | parecer | primeira revisão (flash-lite, parcial) | superficial |
| 19/09/2026 | [avaliacao-gemini-20260919-1850.md](avaliacao-gemini-20260919-1850.md) | avaliação | do parecer acima | repetia pendências conhecidas |
| 19/09/2026 | [gemini-20260919-2038.md](gemini-20260919-2038.md) | parecer | repositório inteiro | 8 apontamentos |
| 19/09/2026 | [avaliacao-gemini-20260919-2038.md](avaliacao-gemini-20260919-2038.md) | avaliação | do parecer acima | 7 aceitos, 1 rejeitado |
| 20/09/2026 | [benchmark-waybar-omarchy.md](benchmark-waybar-omarchy.md) | comparação | barra do jangada e do Omarchy | fechado |
| 21/09/2026 | [benchmark-agentes.md](benchmark-agentes.md) | comparação | gerenciadores de agentes e camadas de Hyprland | itens A a L e seção 4 com situação na seção 7 |
| 21/09/2026 | [gemini-20260921-0909-itens1a3.md](gemini-20260921-0909-itens1a3.md) | parecer | itens A, B e D do benchmark | ver avaliação |
| 21/09/2026 | [avaliacao-gemini-20260921-0909-itens1a3.md](avaliacao-gemini-20260921-0909-itens1a3.md) | avaliação | do parecer acima | aplicada em 04e61a6 e 37ed61a |
| 21/09/2026 | [gemini-20260921-fechamento.md](gemini-20260921-fechamento.md) | parecer | commits db70c2d..f026c23 (itens C, E a L e seção 4) | 15 apontamentos |
| 21/09/2026 | [avaliacao-gemini-20260921-fechamento.md](avaliacao-gemini-20260921-fechamento.md) | avaliação | do parecer acima | 7 aceitos, 6 em parte, 2 rejeitados |
| 22/09/2026 | [gemini-20260922-agy-validar.md](gemini-20260922-agy-validar.md) | parecer | agy na sessão, hooks do agy e jangada-validar | 8 apontamentos |
| 22/09/2026 | [avaliacao-gemini-20260922-agy-validar.md](avaliacao-gemini-20260922-agy-validar.md) | avaliação | do parecer acima | 7 aceitos, 1 rejeitado |
| 22/09/2026 | [gemini-20260922-integrar-pull.md](gemini-20260922-integrar-pull.md) | parecer | atualização da cópia instalada e gancho pos-agente-fim | 4 apontamentos |
| 22/09/2026 | [avaliacao-gemini-20260922-integrar-pull.md](avaliacao-gemini-20260922-integrar-pull.md) | avaliação | do parecer acima | 4 aceitos e aplicados |

## Outros documentos

| Arquivo | Conteúdo |
|---|---|
| [PENDENCIAS.md](PENDENCIAS.md) | testes feitos no desktop e o que ainda depende da máquina real |
| [RESGATE.md](RESGATE.md) | roteiro para trazer as personalizações do Noctalia |
| [PROMPT_GEMINI.md](PROMPT_GEMINI.md) | instruções da revisão do repositório inteiro |
| [rodar-revisao.sh](rodar-revisao.sh) | roda a revisão completa pelo agy (`-a área` restringe) |
| [rodar-gemini.sh](rodar-gemini.sh) | versão antiga, pelo Gemini CLI |

## Como pedir uma auditoria de uma série de commits

O prompt vai como argumento e o Linux limita um argumento a 128 KiB. Grave o
diff num arquivo e libere a pasta com `--add-dir`:

```sh
aud=$(mktemp -d)
git diff BASE..HEAD >"$aud/diff.patch"
git log --oneline BASE..HEAD >"$aud/commits.txt"
agy -p "$(cat prompt.md)" --output-format json --effort high \
  --add-dir "$aud" </dev/null >"$aud/resposta.json"
jq -r .response "$aud/resposta.json" >revisao/gemini-AAAAMMDD-assunto.md
```

O prompt deve mandar o agy não executar comandos: sem terminal, ele não tem a
quem pedir permissão e devolve resposta vazia.
