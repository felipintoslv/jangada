# Revisões e referências do jangada

Este índice reúne sínteses mantidas no ramo principal.
Pareceres e avaliações do Gemini, prompts e scripts de revisão estão no ramo
`arquivo/evidencias`, commit `7a9d1e5`. O dono publicará esse ramo.

| Documento | Conteúdo |
|---|---|
| [auditoria-20260927.md](auditoria-20260927.md) | auditoria do repositório, com 72 apontamentos e ações registradas |
| [benchmark-agentes.md](benchmark-agentes.md) | comparação com gerenciadores de agentes e situação dos itens na seção 7 |
| [benchmark-agente-local.md](benchmark-agente-local.md) | comparação de usos do modelo local e verificação |
| [benchmark-waybar-omarchy.md](benchmark-waybar-omarchy.md) | comparação entre as barras do jangada e do Omarchy |
| [PENDENCIAS.md](PENDENCIAS.md) | testes no desktop e pendências da máquina real |
| [RESGATE.md](../../../revisao/RESGATE.md) | roteiro para recuperar personalizações do Noctalia |

## Consultar o arquivo histórico

A estrutura original de `revisao/` foi preservada, incluindo `gemini-*`,
`avaliacao-gemini-*`, `PROMPT_*.md`, `rodar-revisao.sh` e `rodar-gemini.sh`.
O roteiro `arquivo/evidencias:JANGADA_V2_INSTRUCOES.md` (commit `7a9d1e5`) também permanece na raiz daquele ramo.

```sh
git show arquivo/evidencias:revisao/PROMPT_AUDITORIA.md
git show 7a9d1e5:revisao/avaliacao-gemini-20260922-integrar-pull.md
```

Para o estado P0 e os limites P1, consulte a documentação de estabilização do Core.
Revisão de uma entrega continua sendo feita por `jangada-validar`.

## Cabeçalho dos relatórios

Novos relatórios identificam data, commits avaliados, revisor e veredito.
Nas avaliações, cada apontamento recebe ACEITO, ACEITO EM PARTE ou REJEITADO,
com justificativa conferida no código e o commit da ação tomada.
