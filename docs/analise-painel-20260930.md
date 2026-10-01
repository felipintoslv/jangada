# Análise do painel com os dados de 30/09/2026

- Fuso: America/Fortaleza, UTC−3.
- Janela observada: 00:00 até 23:04:50 de 30/09/2026.
- Estado: retrato parcial do dia, com as fontes disponíveis no momento da coleta.
- Método: três agentes analisaram metadados de Ollama, validações/estados/Pescador e Codex; o agente principal conferiu o consumo e as ferramentas do Claude contra o cache diário.
- Conteúdo: contagens e métricas; perguntas, respostas, documentos e credenciais não foram reproduzidos.

## 1. Conclusão

Os números diários de consumo do Claude conferem com suas tabelas no cache. O painel ainda oferece uma visão parcial da atividade: uma delegação ao Ollama com consumo medido não entra nos totais gerais, e o Codex possui registros externos à Jangada que exigem classificação própria antes da importação.

Não existe amostra de uso do Pescador neste dia. As 20 consultas do seu histórico pertencem a 28 e 29/09. Elas podem fundamentar uma análise histórica, mas não um diagnóstico de hoje.

## 2. Consumo e cobertura

| Fonte | Atividade observada | Entrada | Saída | Cobertura no painel |
|---|---|---:|---:|---|
| Claude, cache de conversas | 30 respostas em 14 conversas | 60 sem cache; cache em campos separados | 70.726 | Totais conferidos com `hoje.json` |
| Ollama, delegações Jangada | 1 delegação local bem-sucedida | 3.535 | 5.302 | Registros existem, mas faltam nas agregações gerais |
| Codex, interface externa | 499 registros de uso em 10 arquivos de sessões/subagentes | 50.146.568, incluindo cache | 239.344 | Ausente do coletor atual; não atribuir aos agentes Jangada |
| Codex, conversas gerenciadas pela Jangada | Nenhum arquivo de conversa na fonte consultada | Indisponível | Indisponível | Há revisões Codex nos registros de validação, mas sem consumo importado |
| agy, delegações | Nenhum registro de delegação nesta janela | Indisponível | Indisponível | Há eventos agy; ausência de delegação não comprova ausência de uso |
| Pescador | Nenhuma consulta hoje nas fontes consultadas | Indisponível | Indisponível | Histórico existente cobre dias anteriores |

Os campos de entrada dos provedores têm semânticas diferentes. No Claude, o cache criado e o cache lido são campos separados dos 60 tokens de entrada. No Codex, o cache informado está dentro da entrada. Não somar novamente cache à entrada Codex e não interpretar a coluna “Entrada” como comparação direta de esforço entre modelos.

### Claude

| Modelo registrado | Respostas | Entrada sem cache | Cache criado | Cache lido | Saída |
|---|---:|---:|---:|---:|---:|
| claude-opus-5-5 | 5 | 10 | 18.416 | 179.239 | 1.732 |
| claude-sonnet-5-5 | 25 | 50 | 665.169 | 822.345 | 68.994 |
| Total | 30 | 60 | 683.585 | 1.001.584 | 70.726 |

O cache registra 50.907 tokens de raciocínio em campo separado. Não acrescentar esse campo à saída sem confirmar a semântica da fonte. As contagens de resposta, entrada, saída e cache não demonstram custo financeiro nem economia causal.

Há 23 chamadas de ferramentas: 15 Grep, 3 Read, 4 Bash e 1 ReportFindings. Todas possuem resultado relacionado; nenhuma contém erro sinalizado nesse resultado. Isso informa sucesso reportado pelas ferramentas, não aprovação ou correção do trabalho final. Nenhuma das 30 respostas tem identificador de subagente preenchido no cache.

### Ollama

Uma delegação do papel leitor ao `qwen3:4b` terminou com código zero, sem recusa, consumindo 3.535 tokens de entrada e 5.302 de saída. O registro guarda 87 segundos de duração total.

O relatório devolvido ao orquestrador tem 79 palavras e estimativa de 138 tokens. A diferença entre geração e retorno pode envolver raciocínio ou resultados intermediários, mas os registros atuais não permitem decompor essa diferença. Não usá-la como medida de economia de tokens da nuvem.

Faltam tempos internos de geração, carregamento e avaliação, número de chamadas/fatias e tamanho original do documento. Os 87 segundos não permitem calcular velocidade de geração. Amostra de uma delegação não permite comparar desempenho entre modelos ou concluir estabilidade.

### Codex

Na fonte geral da interface foram encontrados dez arquivos: três sessões da interface VS Code e sete de subagentes. Existem 499 registros de uso por resposta, sem `response_id` repetido ou conflitante na janela consultada.

O agregado inclui 48.561.152 tokens de entrada recuperada do cache e 61.139 tokens de raciocínio. Cache é subconjunto da entrada; raciocínio é subconjunto da saída. Os totais incluem o trabalho desta interface e suas análises, não apenas projetos gerenciados pela Jangada.

Foram encontradas 443 chamadas de ferramentas: 387 execuções e 56 chamadas de colaboração, espera ou entrada do usuário. Não foram inspecionados comandos internos para contar operações separadas.

A soma usou apenas `token_usage_record.payload.usage`, deduplicado por `response_id`. Os 515 eventos `token_count` e demais contadores cumulativos não foram acrescentados. Um adaptador futuro deve validar essa regra na versão instalada e tratar retomadas e duplicações entre fontes.

## 3. Revisões e entregas

| Grupo | Linhas de validação | Entregas distintas | Entregas aprovadas | Aprovação na primeira rodada |
|---|---:|---:|---:|---:|
| Internas | 14 | 2 | 1 | 0 |
| Externas | 6 | 3 | 2 | 0 |
| Total observado | 20 | 5 | 3 | 0 |

Resultados das 20 linhas: 15 “revisar”, 1 “limite”, 3 “aprovado” e 1 “erro”. As seis linhas externas têm Codex como revisor e autoria ausente; são revisões, não produção automaticamente atribuível ao Codex.

O resumo diário informa uma entrega interna aprovada, 0% de aprovação na primeira rodada e um registro de limite. Esses números coincidem com o agrupamento por entregas neste retrato. Ainda assim, o coletor conta linhas, enquanto as visualizações agrupam por entrega. Usar uma definição comum evita divergência quando houver resultados repetidos ou várias ocorrências de limite.

Uma entrega aprovada é amostra insuficiente para avaliar a qualidade do fluxo pela taxa de primeira rodada.

## 4. Estados e pesquisas

Foram observados 51 eventos em duas sessões, todos identificados como agy: 25 “trabalhando” e 26 “concluído”. A recomposição indica zero segundos em estado “aguardando” nos registros disponíveis. Isso não significa que o usuário não esperou; falta cobertura de outras origens e de outras formas de espera.

O cache atual de sessões está vazio. Esse resultado é um retrato do inventário disponível, não prova ausência de todas as sessões de agentes na máquina. Os dados externos do Codex mostram a necessidade de declarar o alcance dessa fonte.

O Pescador possui 20 consultas históricas: seis em 28/09 e catorze em 29/09; nenhuma no dia 30 até o corte. A aba atual não aplica o filtro global de período às pesquisas. A falha da média com notas ausentes foi reproduzida sinteticamente na análise anterior, mas não ocorreu nesta coleta de hoje, que não tem consultas Pescador.

## 5. Prioridade orientada por estes dados

1. Corrigir notas ausentes, filtros de pesquisas e classificação das delegações locais. Esses erros comprometem a interpretação do painel mesmo antes de ampliar a coleta.
2. Incorporar os tokens Ollama já disponíveis e apresentar a duração total com seu significado correto. Não esperar a captura de todas as métricas para aproveitar os registros atuais.
3. Separar origens “Jangada” e “interface externa” no adaptador Codex, preservando sessões principais e subagentes. Importar consumo e ferramentas sem duplicar contadores cumulativos.
4. Exibir cobertura e atualização por fonte. Ausência de registro não equivale a atividade zero; períodos sem dados devem ficar visíveis.
5. Unificar contagens por entrega e ampliar métricas de desempenho local por requisição. Depois formar uma amostra para comparar execução direta e delegada.

Este retrato serve como referência inicial para conferir a implementação proposta em [proposta-atualizacao-painel.md](proposta-atualizacao-painel.md). Ele observa uso real; um experimento controlado de desempenho é uma etapa distinta.
