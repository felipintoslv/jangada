# Progresso

## Estado em 08/10/2026

- Fase 1 (diagnóstico): concluída com ressalvas. Sete dos doze critérios
  do pedido estão parciais; ver a matriz abaixo.
- Fase 2 (arquitetura e decisão de interface): entregue; o usuário
  autorizou a Fase 3 em seguida.
- Fase 3 (registro de provedores): concluída e aprovada pelo
  `jangada-validar` (Codex, rodada 4, forçada pelo usuário).
- Fase 4: autorizada em 08/10/2026; implementação não iniciada. O usuário
  pediu apresentação do escopo e confirmação antes de alterar código.
- Sessão da Fase 3: ramo `agente/tarefa-ab47cef8d325`, sobre `9dcb640`.
  HEAD da aprovação informado pelo usuário: `3018fb9`.

O ramo e os commits acima identificam a sessão anterior. Nesta continuação,
o ponto de partida é `bd7b9fe`, que integra aquela entrega.

## Matriz dos doze critérios da Fase 1

O pedido exige os doze critérios aprovados para a conclusão integral. Com
critérios parciais, a fase fica **concluída com ressalvas**. As seções
citadas são de `01-diagnostico.md`, salvo indicação.

| Nº | Critério | Situação | Evidência | Pendência |
|---|---|---|---|---|
| 1 | Inventário | PARCIAL | Seção 1.1 lista os doze diretórios de primeiro nível e a raiz do commit `9dcb640`; seção 1.2 lista os pontos de entrada | `install/`, `migrations/`, `shell/` e os hooks do agy e do Codex foram só listados; seis módulos Python foram lidos só em estrutura (seção 14) |
| 2 | Arquitetura | APROVADO | Seção 2.1, com 17 componentes e estado implementado, parcial, ausente ou não verificável; seção 2.2 com os limites fixos; seção 4 com as entidades ausentes | Nenhuma |
| 3 | Evidências | PARCIAL | Convenção fato, inferência e não verificado no início do documento; tabelas com caminho e linha | Não houve conferência de que todas as conclusões críticas têm marca; a tabela de riscos da seção 12 não cita evidência |
| 4 | Painel | PARCIAL | Seções 2.1 e 8: tecnologia, abas, origem dos dados e lacunas, com linhas de `app.R` | Painel não foi aberto em tela; a descrição vem do código |
| 5 | Atividades | PARCIAL | Seção 3 (fluxos da sessão e da fila) e seção 6 (mapa de estados) | Central Qt não foi aberta em tela; retomada e falha não foram executadas |
| 6 | Agentes e provedores | PARCIAL | Seções 2.1 e 2.2: CLI para `claude`, `codex` e `agy`; HTTP só na API do Ollama; busca sem ocorrência de API de terceiros | Os perfis `claude-agy`, `claude-claude`, `codex-agy`, `codex-codex` e `exemplo` de `default/agentes/` não foram classificados um a um |
| 7 | Identidade | APROVADO | `03-identidade-visual.md`, seção 1: logo, cores, tipografia, ícones e medidas localizados | Nenhuma para o critério; as pendências de contraste estão na seção 3 daquele arquivo |
| 8 | Desacoplamento | APROVADO | Seção 7 classifica os requisitos de `desac.md`, lido em `~/Downloads/desac.md` | O arquivo está fora do repositório (T2, T13); a classificação não pode ser refeita só com o repositório |
| 9 | Testes | APROVADO | Seção 10 inventaria a suíte; `testes/verificar.sh` foi executado, com código 0 e 44 etapas (seção "Testes executados" abaixo) | Um caso pulado pelo isolamento: "casa mínima (leitura)" |
| 10 | Riscos | PARCIAL | Seção 12: onze riscos com prioridade e mitigação | A tabela não tem colunas de evidência e de impacto |
| 11 | Documentação | APROVADO | `00-indice.md`, `01-diagnostico.md`, `03-identidade-visual.md`, `09-decisoes.md` e este arquivo, em `docs/evolucao-2.0/` | Nenhuma |
| 12 | Integridade | PARCIAL | O commit `9976e2a`, filho direto de `9dcb640`, só contém os sete arquivos de `docs/evolucao-2.0/` (`git diff --stat 9dcb640 9976e2a`). O `git status --short` ao fim das Fases 1 e 2 mostrava só `?? docs/evolucao-2.0/` | A saída do `git status` do início da fase não foi guardada, então a comparação entre início e fim não está comprovada. O worktree foi criado a partir de `9dcb640`; alterações preexistentes fora dele não foram conferidas |

Resultado: cinco aprovados (2, 7, 8, 9 e 11), o 8 com a ressalva da fonte
externa, e sete parciais (1, 3, 4, 5, 6, 10 e 12). Nenhum bloqueado nem
sem avaliação.

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

## Testes executados na Fase 1

`testes/verificar.sh` rodou uma vez, de dentro da sessão isolada, sobre o
código sem alteração:

- Código de saída 0 e linha final "tudo certo"; 44 etapas.
- Um caso pulado: "casa mínima (leitura): /var/tmp não é gravável aqui", em
  `testes/isolar.sh`. É limite do isolamento da sessão.
- Nenhuma etapa foi ignorada por falta de ferramenta.

O resultado vale para o código conferido na Fase 1. Não comprova as mudanças
das fases seguintes. Para fechar o caso pulado, rode
`bash testes/verificar.sh` num terminal fora da sessão.

## O que não foi feito na Fase 1

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

## Fase 3

Autorizada pelo usuário em 07/10/2026 ("Vamos para a fase 3"). Com as
decisões T9 a T13, o escopo é o registro de provedores com os quatro
atuais.

Feito:

- `default/provedores/` com `claude`, `agy`, `codex` e `ollama`.
- `jangada_provedor` e `jangada_provedores` em `bin/jangada-config`.
- `bin/jangada-agente`: a lista de agentes principais e a opção que entrega
  o protocolo vêm do registro.
- `bin/jangada-validar`: revisores aceitos, nome, modelo padrão e ordem de
  reserva vêm do registro.
- `testes/provedores.sh`, incluído em `testes/verificar.sh`.
- `docs/provedores.md`.

Verificação: `testes/verificar.sh` com código 0 e "tudo certo", 45 etapas,
de dentro da sessão isolada. Segue pulado o caso "casa mínima (leitura)".

Fica fora, com as listas próprias: fila (`estado.py:280`, `cli.py:131`),
saúde (`saude.py`), destinos do `jangada-delegar` e o catálogo de reserva da
Central (`janela.py:24`). Revisor novo ainda exige função `revisar_NOME`.

A aprovação da Fase 3 pelo `jangada-validar` ocorreu em 07/10/2026, com
HEAD em `3018fb9` (informação do usuário nesta continuação). O registro
anterior identifica Codex, rodada 4, forçada pelo usuário.

O commit `3018fb9` (`fix(provedores): jangada-agente para quando o registro
vem vazio`) faz o lançador parar com erro quando nenhum provedor tem a função
`principal`. Antes abria a sessão sem o protocolo, sem aviso. O commit e a
recusa foram conferidos no histórico Git e em `bin/jangada-agente:45-50`.
O histórico atual contém também alterações posteriores a esse HEAD; esta
nota não estende a aprovação de `3018fb9` a elas.

Não conferido: como a atualização leva `default/provedores/` à cópia
instalada. Sem essa pasta o `jangada-agente` não abre sessão.

## Como continuar

Uma sessão nova não tem a conversa anterior. O que ela precisa está aqui:

1. Ler `AGENTS.md`, este arquivo, `09-decisoes.md` e `docs/provedores.md`.
   As decisões T1 a T13 estão tomadas.
2. Regras do pedido que valem em todas as fases:
   - Não avançar de fase sem autorização explícita do usuário.
   - Não tratar documentação como prova de implementação; conferir no
     código.
   - Não inventar funcionalidades, resultados de testes, custos,
     capacidades ou caminhos de arquivos.
   - Preservar alterações preexistentes e arquivos do usuário.
   - Credenciais fora de registros e de arquivos versionados; nenhum dado
     sensível vai a serviço externo sem consentimento.
   - O executor não aprova o próprio resultado.
   - A interface não contorna regras do backend.
   - Sem ranking arbitrário de modelos e sem entidades redundantes.
3. Fases que faltam: 4 (modelo operacional de projetos, tarefas e
   revisões), 5 (reformulação visual), 6 (integração e monitoramento) e
   7 (testes e validação). O desenho está em `02-arquitetura.md` e
   `04-interface.md`.
4. Para fechar o caso pulado, rode `bash testes/verificar.sh` num terminal
   fora da sessão.
