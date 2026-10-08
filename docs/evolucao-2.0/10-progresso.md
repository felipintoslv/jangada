# Progresso

## Estado em 08/10/2026

- Fase 1 (diagnóstico): concluída com ressalvas. Sete dos doze critérios
  do pedido estão parciais; ver a matriz abaixo.
- Fase 2 (arquitetura e decisão de interface): entregue; o usuário
  autorizou a Fase 3 em seguida.
- Fase 3 (registro de provedores): concluída e aprovada pelo
  `jangada-validar` (Codex, rodada 4, forçada pelo usuário).
- Fase 4: aprovada pelo `jangada-validar` em 08/10/2026, HEAD `0d43dce`.
- Fases 5 a 7: concluídas e aprovadas pelo `jangada-validar`, HEAD `3bff4b9`.
- Fases 4 a 7: autorizadas com autonomia em 08/10/2026.
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

## Fase 4

O escopo foi apresentado e confirmado antes de alterar código. O usuário
autorizou em 08/10/2026 todas as fases restantes com a mensagem: "Eu vou dormir
e deixo autorizado fazer todas as etapas, com total autonomia". Autorizou
também o uso de subagentes do Codex para análise. Três subagentes analisaram
persistência, revisão e núcleo;
não editaram arquivos nem revisaram a entrega. O agy foi tentado e recusado
por `JANGADA_DELEGAR=local`; esse limite não foi alterado.

Implementado:

- Cadastro e política em `projeto.json`; reassociação preservando
  especificações e hashes, com resolução transitória de caminhos.
- Tabelas adicionais `atividades` e `execucoes`, sem migrar registros antigos.
- Critérios, contexto e vínculos opcionais de tarefas e sessões.
- Revisão identificada fora do isolamento, com hash e critérios; nomes
  alternativos do Codex não permitem autoraprovação.
- Orçamento de chamadas reservado entre conexões; consumo desconhecido e
  teto de custo sem limite comprovável recusam execução de modelos.
- Consulta conjunta em `default/nucleo/`, sem alterar banco ou arquivos
  auxiliares na origem. Ações encaminhadas aos comandos existentes.
- Modos manual, assistido e automático supervisionado, preservando os
  perfis atuais da fila e a delegação local.

Os 24 testes de `testes/operacional.py` passaram. Incluem WAL ativo,
transação pendente, banco antigo, reassociação determinística, isolamento
da revisão, orçamento concorrente e execução direta com provedor falso.
A suíte `testes/verificar.sh` passou em 08/10/2026, código zero, em 196 s.
A revisão técnica aprovou a fase em 08/10/2026, HEAD `0d43dce`, na segunda
rodada desta entrega. O parecer é `validacao-jangada--tarefa-ddeff1c4d2f2-r3.md`.
O revisor conferiu as sete respostas; declarou não ter executado testes.
A suíte local foi executada nesta sessão. A integração de interfaces e
recursos pertence às fases seguintes.

## Fases 5 a 7

Implementação autorizada pela mesma mensagem de 08/10/2026. As interfaces
e a ligação ao núcleo foram desenvolvidas em conjunto, mantendo a separação
entre consultas Shiny e ações Qt/terminal. A revisão técnica aprovou esta
entrega em 08/10/2026, HEAD `3bff4b9`, na segunda rodada, com Claude Sonnet.
O parecer é `validacao-jangada--tarefa-ddeff1c4d2f2-r5.md`; contém somente
`STATUS: APROVADO`, sem declaração de testes executados pelo revisor.

Implementado e conferido no código:

- Paletas clara e escura no mesmo modelo matugen, validadas em Python e
  consumidas pelas duas interfaces. Migração repetível e simulada preserva
  personalizações. Inter entra na lista de pacotes, sem instalação nesta sessão.
- Dez seções Shiny, filtros por identificador de projeto e detalhes com
  critérios, dependências, execuções, revisões, eventos e hashes de artefatos.
- Cadastro, atividades, importação e transições da fila na Central Qt,
  sempre pelos comandos existentes. Identidades incluem tipo, projeto e ID.
- Configuração pública com campos permitidos; cadastro separado de instalação
  e observações de saúde. Ausências permanecem explícitas.
- `nucleo.json` no coletor e vínculo opcional de execução nas validações.
  A leitura legada também usa cópia SQLite/WAL; não grava auxiliares na origem.
- CPU e memória por `/proc`, GPU por `nvidia-smi` quando disponível, e
  listagem local de modelos por `/api/ps`. Sem redirecionamento ou geração.
  Monitoramento só depois de autenticação, na aba ativa, a cada 5 s.

Verificações observadas até aqui:

- `testes/fichas.py`: cinco testes passaram, incluindo três PNGs sintéticos
  e os dois esquemas, contraste, recuperação de JSON inválido e simulação.
  A migração preserva o arquivo existente.
- `testes/monitoramento.py`: quatro testes passaram, com `/proc` real, API
  local sintética e comando `--json`. Falha e indisponibilidade não viram zero.
- `testes/tarefas.py`: 64 testes passaram; seleção de T1 em dois projetos,
  recusa de cancelamento, dados parciais, foco e modos incluídos.
- `testes/painel-operacional.R` passou: filtros, cache intacto, sessão sem
  token encerrada, primeira medida de CPU ausente e coleta suspensa fora da aba.
- `testes/painel.sh` passou com o app real, autenticação e coleta; os
  testes de indicadores e os 28 contratos operacionais também passaram.
- `testes/verificar.sh` passou em 08/10/2026, código zero, em 206 s,
  depois das correções e dos contratos adicionais pedidos na revisão.
- A Central Qt foi aberta sem servidor gráfico nos dois modos, com quatro
  tarefas sintéticas. As imagens foram inspecionadas; não foi uma sessão Hyprland.

O primeiro parecer técnico desta entrega pediu revisão. Foram corrigidos
o tratamento de paleta inválida, o filtro com estado ausente, a simulação
do tema e o alinhamento da lista de pacotes. Os testes foram ampliados
para catálogos com falha, configurações públicas inválidas, isolamento do
Codex, comando de monitoramento e eventos da consulta.
A alegação de sessão sem projeto não se confirmou: `consultar` cria um
projeto transitório, conferido por um teste sem cadastro e sem gravação.
A cópia da paleta foi mantida e documentada conforme a regra 3 de `AGENTS.md`.

Não houve instalação, atualização da cópia instalada ou envio de commits.
Na entrega anterior, os contratos usaram executores sintéticos, sem modelos
remotos reais. A revisão independente usa o revisor configurado.
As imagens de contraste são sintéticas, e a fonte de reserva é usada nesta
máquina enquanto Inter não estiver instalada.

## Testes finais adicionais em 08/10/2026

O usuário autorizou testes em sessão Hyprland e execuções reais de modelos
remotos. Foram feitas duas consultas com a mesma fonte sintética de quatro
linhas. O contrato exigiu fatos numéricos e referências exatas em JSON,
comparados deterministicamente com o gabarito; não aprova a implementação.

- Claude: CLI real, alias `sonnet`; o retorno identificou `claude-sonnet-5-5`.
  Código zero, 3,20 s, um turno, 83 tokens de saída. O contrato passou.
  Entrada registrada: 2 tokens, 2.042 de criação de cache e 531 lidos do cache.
- Codex: adaptador `jangada-codex --revisar`, com o modelo configurado
  `gpt-6.1-sol` solicitado explicitamente. Código zero, 5,56 s, 11.157
  tokens de entrada e 57 de saída. O contrato passou.

Ferramentas foram desativadas. As execuções usaram montagens que permitem
gravar apenas na pasta temporária do teste, com autenticação somente para
leitura. Não houve login, alteração de configuração externa ou chave de API.
A primeira tentativa do Codex falhou na inicialização porque seus dados
estavam somente para leitura. A repetição montou dados próprios do teste,
preservando `CODEX_HOME`. O retorno avisou que o modo de código estava
desativado; a resposta sem ferramentas e o consumo foram recebidos.
Esses testes conferem geração e formato, não o ciclo completo de sessão,
fila, revisão e integração com executores reais.

Hyprland instalado: 0.56.2. `testes/aninhado.sh --sem-usuario` retornou
"pulado", pois esta sessão isolada não tem `WAYLAND_DISPLAY` nem soquete
Wayland visível. Essa execução não conta como aprovação do teste gráfico.

Depois, o usuário executou o mesmo comando em um terminal comum e
forneceu a saída: "sem erros de configuração", "65 atalhos registrados"
e "configuração carregada sem erros no Hyprland aninhado". O resultado
foi informado pelo usuário, não executado por esta sessão isolada.
O teste aninhado exclui a inicialização que alteraria o ambiente da
sessão e não testa DRM ou escolha de GPU.

As capturas `Imagem colada (4).png` e `Imagem colada (5).png`, fornecidas
pelo usuário em `~/Downloads`, foram abertas e inspecionadas nesta sessão.
Mostram a Central no cenário 4 da simulação, nos modos escuro e claro,
com logo, abas, seleção e foco visíveis. Alguns textos da lista ficam
truncados. Isso confere a apresentação mostrada; não comprova todas as
ações, a aba Projetos e fila ou o painel Shiny na sessão gráfica.
As imagens não foram copiadas para o repositório.

A suíte `testes/verificar.sh` passou novamente, código zero, em 207 s,
depois desses testes adicionais e do registro documental.
Após registrar o resultado gráfico fornecido pelo usuário e as capturas,
a suíte passou outra vez, código zero, em 209 s.

## Revisão externa da integração

A tentativa de integração fornecida pelo usuário recebeu `REVISAR`, rodada
2 de 3, para o conjunto desde `main`. O diff de 255.082 bytes foi cortado
em 150.000; o revisor declarou não ter lido todos os arquivos. Os pareceres
anteriores aprovam suas entregas parciais, não substituem essa revisão externa.

Resposta aos quatro apontamentos:

1. Corrigido o desfazimento da expiração por recusa de orçamento. `reservar`
   registra a tarefa impedida em `WAITING_QUOTA` e continua a seleção.
   Consumo de reserva expirada permanece desconhecido, com orientação para
   aguardar o fim da janela do orçamento. Não é convertido em zero.
   O teste com orçamento confere expiração persistida, outra tarefa
   determinística reservada, cadastro recusado na janela e retomada depois dela.
2. O lançador mantém a causa do backend e orienta conferir política e
   orçamento, usando a fila controlada. O teste confere a recusa e a mensagem.
3. Mantida a simulação integral do tema. `install/40-interface.sh` chama
   o tema por `executar`, que já não o executa na instalação simulada.
   Nenhuma dependência de execução real foi identificada nos testes;
   `test_tema_simulado_nao_grava_nem_recarrega` confere ausência de gravações.
4. Reforçado `test_consulta_com_wal_ativo_nao_escreve_na_origem`: o banco
   aberto com `immutable=1` não contém a tarefa confirmada, que está no WAL.
   O teste confere ausência de SHM na cópia antes da conexão, leitura da
   tarefa confirmada, exclusão da alteração pendente e origem intacta.

Os 29 contratos de `testes/operacional.py` passaram. `testes/codex.sh`
também passou, incluindo as duas verificações da mensagem de recusa.
A suíte completa `testes/verificar.sh` passou, código zero, em 209 s,
após as correções do parecer externo.
A revisão externa do commit atualizado continua necessária antes da mescla.

O usuário forneceu depois `validacao-tarefa-ddeff1c4d2f2-r1.md`, com
cinco novos apontamentos. Foram tratados assim:

1. Projetos sem caminho ficam somente para consulta na Central. Os botões
   de tarefas, atividades e importação recusam ações; o cadastro de outra
   pasta permanece disponível porque não usa o projeto selecionado.
   Argumentos inválidos mostram mensagem
   no estado da janela, sem exceção escapando do método chamado pelo Qt.
2. Atualizada a descrição da ligação do painel e da Central ao núcleo em
   `docs/subagentes-e-delegacao.md`.
3. `sessao-conferir` consulta o estado sem criar cadastro ou banco.
   A política vazia permite executor sem cadastro; vínculos ausentes são
   recusados. A mesma regra de provedor é usada na consulta e na escrita.
   Os testes conferem arquivos e datas intactos tanto na permissão quanto
   na recusa de fila antiga ou de projeto com política.
4. A Central usa `consultar --todos --sem-catalogos`. Os catálogos
   continuam disponíveis na consulta completa usada pelo painel.
   Cada evento reinicia a espera de 200 ms, com limite de adiamento de 1 s;
   a consulta periódica de 30 s continua como reserva. Os testes conferem
   agrupamento, atualização durante fluxo contínuo de eventos e
   consulta independente dos executáveis dos catálogos.
5. A reserva principal aplica a exceção de orçamento para `validacao_json`
   e foi exercitada com limite de zero chamadas. A alteração de supervisão
   foi retirada: tarefas determinísticas já são inelegíveis e recusadas
   antes desse ponto. O teste confere essa recusa, sem habilitar esse fluxo.

Passaram 33 contratos operacionais e 66 testes da Central com esses cenários.
A suíte completa passou, código zero, em 207 s após essas correções.

A revisão local pediu cadastro independente da seleção, retirada da exceção
inalcançável de supervisão e limite de adiamento durante eventos contínuos.
Os três ajustes estão no commit `2561cf4`. Passaram 33 contratos operacionais
e 67 testes da Central, incluindo eventos a cada 40 ms. A suíte completa
passou novamente, código zero, em 209 s. A aprovação desta correção e a
revisão externa para integração continuam pendentes.
A revisão manual externa deve informar `JANGADA_SESSAO` com o identificador
completo, para usar o mesmo rótulo e a mesma marca procurada pela integração.

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
3. Fases 4 a 7 concluídas e aprovadas. Os limites dos testes estão acima;
   as ressalvas históricas da Fase 1 continuam registradas na matriz.
   O desenho está em `02-arquitetura.md` e `04-interface.md`.
4. Para fechar o caso pulado, rode `bash testes/verificar.sh` num terminal
   fora da sessão.
