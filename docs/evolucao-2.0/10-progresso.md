# Progresso

## Estado em 07/10/2026

- Fases 1 e 2: concluídas (diagnóstico, arquitetura e decisão de interface).
- Fase 3 (registro de provedores): concluída e aprovada pelo
  `jangada-validar` (Codex, rodada 4, forçada pelo usuário).
- Fase 4: não iniciada; depende de autorização.
- Ramo: `agente/tarefa-ab47cef8d325`, sobre `9dcb640`. Último commit de
  código: `3018fb9`.

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

Depois da entrega, o `jangada-agente` passou a parar com erro quando nenhum
provedor tem a função `principal` (`3018fb9`). Antes abria a sessão sem o
protocolo, sem aviso.

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
