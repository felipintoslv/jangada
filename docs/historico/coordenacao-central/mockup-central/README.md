# Evolução do mockup da Central

Guarda as imagens conceituais e as prévias navegáveis que levaram ao desenho
atual da Central de Tarefas. É **protótipo sintético**: todos os projetos,
tarefas e sessões das telas são fictícios. Não é software aprovado, e a
Central Qt real será outra tarefa.

## Linha do tempo

| Data | Pasta | O que mudou | Decisão do dono |
|---|---|---|---|
| 13/10/2026 | [v0-conceito](v0-conceito/) | Quatro imagens conceituais geradas (WebP, largura máxima de 1600 px). | A `conceito-4` ficou como referência visual: tarefas em destaque, logo original, paleta do jangada, conversa em sessão externa ("fechado!"). |
| 15/10/2026 | [ponto-de-partida](ponto-de-partida/) | Captura sintética da Central Qt atual, sem dados reais. | Serve de base de comparação para as prévias. |
| 15/10/2026 | [v1](v1/) | Primeira prévia HTML navegável, com projetos, conversas e tarefas (16 conferências externas no Chromium). | Avaliada como ponto de partida; a v2 mantém a estrutura da Central atual. |
| 15/10/2026 | [v2](v2/) | Prévia atual: preserva cabeçalho, resumo, abas e lista com detalhe, em evolução visual da Central (29 conferências externas, zero exceções JS). | Prévia vigente para discussão. |

## Como abrir

Abra `v1/index.html` ou `v2/index.html` direto no navegador, por `file://`.
O CSS, o JavaScript e os logos estão no próprio arquivo: não precisa de
servidor, instalação nem rede. Cada pasta tem um README com o alcance e as
conferências feitas.

## Aviso

Os dados são inventados e nada nas telas lê ou altera sessões reais. A
aprovação de uma prévia não autoriza implementação nem integração.
