# Progresso

## Estado em 07/10/2026

- Fase 1 (diagnóstico): aprovada pelo usuário ("vamos para a fase 2").
- Fase 2 (proposta arquitetural e decisão de interface): entregue, à espera
  de aprovação.
- Ramo: `agente/tarefa-ab47cef8d325`, commit `9dcb640`, sem commit novo.
- `git status --short` ao final: só `?? docs/evolucao-2.0/`.

## O que foi feito

- Leitura de `AGENTS.md`, `config/jangada.conf`, perfis em `default/agentes/`
  e `JANGADA_V2_INSTRUCOES.md`.
- Leitura integral de `bin/jangada-agente`, `default/orquestracao/cli.py` e
  `estado.py`; leitura dirigida de `jangada-validar`, `jangada-delegar`,
  `jangada-config`, `jangada-agentes`, `jangada-agente-fim`,
  `jangada-isolar`, `jangada-painel`, `saude.py`, `executor.py`,
  `default/painel/app.R` e `default/tarefas/`.
- Inspeção da logo, do matugen, da barra e do tema de login.
- Leitura de `testes/verificar.sh` e de `.github/workflows/verificar.yml`.
- Leitura de `~/Downloads/desac.md`, fora do repositório.

## Testes executados

`testes/verificar.sh` rodou uma vez, de dentro da sessão isolada, sobre o
código sem alteração:

- Código de saída 0 e linha final "tudo certo"; 44 etapas.
- Um caso pulado: "casa mínima (leitura): /var/tmp não é gravável aqui", em
  `testes/isolar.sh`. É limite do isolamento da sessão.
- Nenhuma etapa foi ignorada por falta de ferramenta.

O resultado vale para o código atual. Não diz nada sobre a proposta, que não
tem código. Para fechar o caso pulado, rode `bash testes/verificar.sh` num
terminal fora da sessão.

## O que não foi feito

- `jangada-validar` não rodou: a fase proíbe commits e sem commit não há
  entrega para revisar.
- Nenhuma delegação a subagente foi usada.
- Painel e Central não foram abertos em tela.
- Nenhum provedor externo foi consultado.
- Arquivos lidos só em estrutura estão listados em `01-diagnostico.md`,
  seção 14.

## Fase 2

Leituras a mais: `install/pacotes/`, modo do tema em `bin/jangada-tema`,
`default/orquestracao/principal.py` (inteiro), `supervisao.py` (parecer e
candidatos), `metricas_projeto.py` (`ler_precos`), `tarefa_valida` e
`alterar` em `estado.py`, `jangada_perfil` em `bin/jangada-config`,
autenticação em `bin/jangada-painel` e `docs/proposta-atualizacao-painel.md`.

Produzido: `02-arquitetura.md`, `04-interface.md`; plano de fases de
`01-diagnostico.md` refeito; `09-decisoes.md` atualizado.

Não feito na Fase 2:

- Nenhum teste foi executado: não houve mudança de código desde a execução
  da Fase 1.
- Nenhum protótipo de serviço ou de tela.
- Nenhuma consulta à rede: os formatos das APIs de provedores remotos estão
  marcados como não verificados.

## Como continuar

1. Todas as perguntas foram respondidas (T9 a T13 em `09-decisoes.md`):
   Ollama como está, só Shiny, testes com os provedores atuais, provedores
   por API adiados, `desac.md` fora do repositório. D3, D6 e D7 seguem como
   propostas, sem objeção.
2. Aprovada a Fase 2, a Fase 3 começa pelo registro de provedores com os
   quatro provedores padrão reproduzindo o comportamento atual, antes de
   qualquer adaptador novo. A Fase 3 altera código: volta a valer o ciclo
   de commits, `testes/verificar.sh` e `jangada-validar`, se você liberar.
