# Decisões

## Tomadas na Fase 1

| Nº | Decisão | Motivo |
|---|---|---|
| T1 | Nenhum código, configuração ou dependência foi alterado; só documentos em `docs/evolucao-2.0/` | Regra da fase |
| T2 | `desac.md` foi lido em `~/Downloads/desac.md`, fora do repositório, e não foi copiado | Não está versionado; é arquivo do usuário |
| T3 | Documentação existente serviu de pista; cada fato foi conferido no código | Pedido de não tratar documentação como prova |
| T4 | Só são criados arquivos com conteúdo; os números livres ficam para as fases que os preencherem | Evitar arquivo vazio |
| T5 | Nenhum provedor externo foi chamado | Sem consentimento para envio de dados |

## Tomadas na Fase 2

| Nº | Decisão | Motivo |
|---|---|---|
| T6 | A Fase 2 também só produziu documentos, sem commit | A proibição de alterar código e de fazer commits está nas regras gerais do pedido, não só na Fase 1 |
| T7 | O plano de sete fases de `01-diagnostico.md` foi refeito com a divisão do pedido | A primeira versão usava uma divisão própria |
| T9 | O Ollama fica como está, nem mais nem menos: delegação local de leitor e redator, Conversa de Pescador, saúde e avaliação, com as variáveis atuais. Não vira agente de sessão, revisor nem supervisor, e o código da delegação local não é extraído. Os itens de `desac.md` que citam o Ollama (revisor `ollama`, `local.conf`) saem do plano. Responde D5 | Decisão do usuário em 07/10/2026, confirmada na mesma data. Detalhe em `02-arquitetura.md`, seção 1.1 |
| T10 | Interface: só Shiny, só leitura. Sem serviço web, sem biblioteca JavaScript. Ações na Central Qt e no terminal. Responde D1 e elimina D11 | Decisão do usuário em 07/10/2026, para manter a estrutura atual. Detalhe em `04-interface.md` |
| T11 | Os provedores testados são os de hoje: `claude`, `codex`, `agy` e `ollama`. Nenhum provedor remoto por API entra em teste de contrato. Responde D12 | Decisão do usuário em 07/10/2026 |
| T12 | Provedores por API ficam fora desta evolução. O usuário não vai usar chave de API agora. Ficam adiados, sem data: guarda de chaves (D2), consentimento para envio de diff a URL remota (D4), adaptador Anthropic (D8), adaptador `openai-compat` e revisor HTTP de `desac.md` (D9). O desenho deles segue em `02-arquitetura.md` como referência | D2 decidida pelo usuário em 07/10/2026. D4, D8 e D9 são consequência de T11 e T12: só existem para provedor por API. Reabrir qualquer uma exige nova decisão |
| T13 | `desac.md` não entra no repositório. Responde D10 | Decisão do usuário em 07/10/2026 |
| T8 | A rede não foi usada; dados de terceiros (Vue, APIs de provedores) ficaram marcados como não verificados | Não inventar capacidades |

## Propostas na Fase 2, à espera de confirmação

A Fase 2 foi iniciada sem resposta às perguntas D1 a D8. As propostas abaixo
são as recomendações levadas adiante nos documentos. D5 foi respondida
(T9). Qualquer uma pode ser trocada antes da Fase 3.

| Nº | Pergunta | Proposta | Onde está detalhada | Efeito de trocar |
|---|---|---|---|---|
| D3 | Formato do registro de provedores | `CHAVE=valor`, com leitor próprio que não exporta para o ambiente | `02-arquitetura.md`, seção 4 | Afeta a Fase 3 |
| D6 | Estado de sessão e de fila | Estados persistidos intactos; os oito estados da 2.0 são visão calculada | `02-arquitetura.md`, seção 8 | Afeta a Fase 4 |
| D7 | Central Qt | Mantida, passa a usar o núcleo e as fichas de cor | `04-interface.md`, seção 1 | Afeta as Fases 5 e 6 |

## Abertas

Nenhuma. Falta só a autorização para a Fase 3.

## Divergência entre o pedido e o protocolo da sessão

O protocolo do jangada pede commits pequenos e `jangada-validar` antes de
concluir. O pedido proíbe commits. Prevaleceu o pedido nas duas fases: não
houve commit nem `jangada-validar`, que precisa de commit para ter o que
revisar.
