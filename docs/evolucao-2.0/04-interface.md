# Decisão de interface e desenho do painel

Fase 2. Decisão tomada pelo usuário em 07/10/2026 (T10 em `09-decisoes.md`).

## 1. Decisão

**Só Shiny.** Não há serviço web novo, nem telas em HTML próprias, nem
biblioteca JavaScript.

1. O painel continua em R Shiny com bslib, em `default/painel/`, e ganha as
   seções da 2.0 como abas.
2. O painel continua só de leitura. Ele não cria, cancela, integra nem
   aprova nada.
3. As ações ficam onde já estão: Central Qt e terminal. As duas chamam os
   comandos de `bin/`, que aplicam as regras.
4. A autenticação do painel não muda: token na URL e conferência de origem
   (`bin/jangada-painel:132`, `app.R:308-309`). Sem ações, ela segue
   suficiente.

A recomendação desta fase era o híbrido (seção 3). O usuário escolheu
manter a estrutura atual. Híbrido, React e Vue ficam descartados.

Consequências aceitas:

- Ver as seções novas exige R e os pacotes do painel, que o instalador não
  instala (`bin/jangada-painel:86-95`). Operar não exige: a Central Qt e o
  terminal bastam.
- Atualização por sondagem, como hoje (`app.R:371`), sem eventos ao vivo.
- A pergunta sobre Vue ou JavaScript puro (D11) deixa de existir.
- O risco R5 do diagnóstico (ações de escrita pela web) deixa de existir.

## 2. Evidências que pesaram

| Fato | Onde | Efeito |
|---|---|---|
| O instalador só usa `pacman` e AUR; não há `npm` nem `node` nas listas | `install/pacotes/*.txt`, `install/lib.sh:116` | Cadeia de compilação web seria um tipo novo de dependência |
| Python e PyQt6 já são dependência | `install/pacotes/interface.txt` | Serviço em Python não acrescenta pacote |
| R e os pacotes do painel não são instalados pelo jangada; o comando só confere e avisa | `bin/jangada-painel:86-95` | O painel atual já é opcional; operação não pode depender dele |
| O painel não busca nada na rede | `default/painel/app.R:4` | Biblioteca de interface tem de estar no repositório |
| Token do painel vai na URL | `bin/jangada-painel:132` | Aceitável para leitura; insuficiente para ações |
| O agente isolado alcança a porta do painel, mas não o token | `bin/jangada-painel:23-24` | O serviço de ações precisa de mais que a porta local |
| O painel lê arquivos direto e atualiza por sondagem de 3 s | `app.R:371` | Sem camada de serviço para ações |
| A Central já cria, acompanha e integra sessões, com confirmação por SHA | `default/tarefas/janela.py`, `bin/jangada-agente-fim` | As regras de ação existem e são reaproveitáveis |
| Indicadores em R somam cerca de 1.760 linhas | `app.R`, `indicadores.R`, `hoje.R` | Reescrever seria custo sem ganho |

## 3. Comparação feita antes da decisão

Fica como registro. A decisão do usuário não seguiu o total: pesou manter a
estrutura atual.

Nota de 1 a 5. Os pesos são julgamento; as notas vêm dos fatos acima.

| Critério | Peso | Shiny | Híbrido | React | Vue com compilação |
|---|---|---|---|---|---|
| Reuso dos indicadores existentes | 20 | 5 | 5 | 1 | 1 |
| Ações com estado e atualização ao vivo | 20 | 2 | 4 | 5 | 5 |
| Instalação repetível, sem tipo novo de dependência | 15 | 4 | 5 | 1 | 1 |
| Manutenção nas linguagens do projeto | 15 | 4 | 4 | 2 | 2 |
| Superfície de ataque e dependências de terceiros | 15 | 3 | 4 | 2 | 2 |
| Acessibilidade e tema | 10 | 3 | 4 | 4 | 4 |
| Testes na suíte atual | 5 | 3 | 4 | 2 | 2 |
| **Total (máximo 500)** | 100 | **355** | **435** | **250** | **250** |

Justificativa das notas que decidem:

- **Shiny, ações (2):** dá para fazer, mas cada ação viraria código R
  chamando `bin/`, uma segunda implementação das regras ao lado da Central.
  E a operação passaria a exigir R instalado.
- **Shiny, superfície (3):** o processo que mostra gráficos passaria a
  poder integrar código, com o mesmo token.
- **React e Vue com compilação, instalação (1):** exigem `node` e um
  gerenciador de pacotes com centenas de dependências transitivas, contra a
  regra 2 e o modelo de ameaça da regra 10.
- **Híbrido, ações (4 e não 5):** sem compilação não há tipagem nem
  componentes de terceiros; é suficiente para nove seções de listas,
  formulários e detalhes.

As notas mudaram em relação à Fase 1 porque lá a instalação do R e a
ausência de `node` ainda não tinham sido conferidas.

## 4. Navegação

Abas do Shiny. A coluna "Ação" diz onde se age, já que o painel só lê.

| Seção | Conteúdo | Reaproveita | Ação |
|---|---|---|---|
| Visão Geral | Projetos ativos, tarefas pendentes, execuções em andamento, revisões à espera, falhas, agentes disponíveis, uso de recursos | Aba "Hoje" (`hoje.R`) | Nenhuma |
| Projetos | Lista, política de dados e orçamento, atividades do projeto | Pastas de `agentes/projetos/` | Terminal |
| Central de Atividades | Tarefas e sessões juntas, em lista e por projeto | Aba "Fila e provedores", JSON de sessão | Central Qt, `jangada-task` |
| Central de Agentes | Perfis: função, executor, modelo, permissões, tarefas e histórico | `jangada-agente --capacidades-json` | Terminal |
| Modelos e Provedores | Registro, níveis de disponibilidade, limites | Tabela `provedores` | `jangada-provedor` |
| Central de Revisão | Fila de pareceres, critérios, decisão | `validar.jsonl`, `revisoes/`, aba "Revisão e síntese" | `jangada-validar`, Central Qt |
| Monitoramento | CPU, memória, GPU, modelos carregados, erros | `jangada-monitor`, `/api/ps` | Nenhuma |
| Histórico e Artefatos | Linha do tempo por tarefa, artefatos por `sha256` | Tabelas `eventos`, `artefatos/` | Nenhuma |
| Configurações | Leitura validada de `jangada.conf`, perfis e provedores, com o arquivo a editar | `jangada-config` | Editor de texto |
| Indicadores | Abas analíticas atuais | Sem mudança | Nenhuma |

### 4.1 Central de Atividades

- **Lista:** padrão. Colunas: estado, título, projeto, agente, modelo,
  prioridade, atualizado. Filtros por projeto, estado, agente e período.
- **Por projeto:** atividades com suas tarefas e dependências.

O quadro com arrastar saiu: arrastar é ação, e o painel não age.

Detalhe da tarefa: instruções, critérios de aceite, dependências,
tentativas, execuções com modelo e duração, registro de eventos, artefatos,
e o comando que executa cada ação válida para o estado atual.

Estado bloqueado mostra o motivo persistido (cota, provedor, revisor,
pausa, dependência) em texto.

### 4.2 Modelos e Provedores

Cada provedor mostra os cinco níveis da seção 4.2 da arquitetura, com data
da última verificação. O campo de credencial só diz "configurada" ou
"ausente". O teste de conexão roda pelo terminal; a tela mostra o último
resultado.

## 5. Regras de desenho

- Fichas, tipografia e estados de `03-identidade-visual.md`, aplicados ao
  tema bslib e à Central Qt.
- Logo simbólica no cabeçalho, recolorida pelo tema.
- Estado sempre com rótulo e ícone, nunca só cor.
- Nenhum elemento sem função: sem ilustração, sem animação de entrada.
- Registros em texto selecionável, com busca.
- Todo número diz se é medido ou estimado.

## 6. Critérios para a Fase 5 aceitar a interface

1. As dez seções existem como abas e mostram dados reais, sem inventar
   valor ausente.
2. O painel não grava em nenhum arquivo de estado, com teste automático.
3. Acompanhar e integrar uma tarefa pela Central Qt, sem terminal, continua
   possível.
4. Contraste medido nos dois modos do painel, claro e escuro (`app.R:304`).
5. Uso completo por teclado.
6. As abas atuais seguem funcionando sem alteração de comportamento, e
   os testes de painel de `testes/verificar.sh` passam.

## 7. Reversão

As abas novas são arquivos R novos mais entradas na navegação de `app.R`.
Removê-las devolve o painel ao estado atual.

## 8. Implementação em 08/10/2026

As dez seções existem em `app.R`; as análises anteriores estão em
Indicadores. `operacional.R` lê `nucleo.json`, produzido pelo coletor a
partir das consultas de `default/nucleo/`. A identidade usa o hash do
projeto; projetos com o mesmo nome não compartilham seleção.

Central Qt tem as abas Sessões e Projetos e fila. Cadastro de projeto,
atividade, importação e transições da fila chamam os comandos existentes.
Acompanhamento de sessão reutiliza a seleção e a integração por SHA.
Revisão da fila continua no terminal; a Central mostra instruções e critérios.
Dados parciais ou consulta inválida bloqueiam as ações operacionais.

Monitoramento só consulta recursos depois de autenticação, com a aba
ativa e intervalo de 5 s. CPU usa diferença entre contadores; a primeira
medida fica ausente. GPU usa `nvidia-smi` quando disponível; outros
fabricantes permanecem sem medida. Modelos carregados vêm apenas de
`GET /api/ps` local, sem redirecionamento ou geração de modelos.

Cadastro, instalação do executável e observações de saúde aparecem
separados. Autenticação, contrato, modelos e cota não são inferidos do
cadastro. Configurações públicas têm campos permitidos e validação; não
incluem argumentos livres nem variáveis de credencial.

Os testes e a revisão técnica ficam registrados em `10-progresso.md`.
