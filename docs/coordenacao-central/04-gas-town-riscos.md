# 04. Gas Town: princípios, limites e riscos

Gas Town oferece referências de identidade, trabalho persistente e rastreabilidade.
O Jangada pode aproveitar esses princípios sem importar sua estrutura, terminologia, dependências ou autonomia.
No primeiro aceite, há um coordenador por projeto e várias conversas/tarefas; vários coordenadores no mesmo projeto são futuro.
Exploração e apoio agy aprimoram a skill e o fluxo atual antes de acrescentar infraestrutura.
Isolamento de vários coordenadores e a UX desta proposta são requisitos próprios, não capacidades presumidas da referência.

## Fontes oficiais acessíveis

Leitura web em 13/10/2026 do repositório oficial `gastownhall/gastown`, ramo `main`.
Não houve clone, instalação ou execução. As páginas são móveis; o acesso usado não fixou SHA da referência.
A comparação descreve documentação acessível nessa consulta, não prova de comportamento operacional ou auditoria de segurança.
A tentativa anterior de ler `docs/concepts/hooks.md` retornou erro; Hooks foi examinado no README e glossário efetivamente acessíveis.
Nesta continuação, as seis fontes da tabela foram acessadas novamente; a diferença documental sobre o ciclo dos Polecats permanece verificável.

| Fonte | Trechos examinados e uso |
|---|---|
| [README oficial](https://github.com/gastownhall/gastown) | Seções Overview e Core Concepts: Mayor, Rigs, Polecats, Hooks, Convoys e Beads |
| [Understanding Gas Town](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/overview.md) | Seções Role Taxonomy, Convoys: Tracking Work, Identity and Attribution e The Propulsion Principle |
| [Architecture](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/design/architecture.md) | Seções Two-Level Beads Architecture, Storage Layer: Dolt SQL Server, Beads Redirects, Merge Queue: Batch-then-Bisect e Polecat Lifecycle: Self-Managed Completion |
| [Convoys](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/concepts/convoy.md) | Seções Concept, Convoy vs Swarm, Cross-Rig Tracking e Convoy vs Rig Status |
| [Polecat Lifecycle](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/concepts/polecat-lifecycle.md) | Seções Overview, The Retired Completion Model e The Three Layers |
| [Glossary](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/glossary.md) | Seções Core Principles e Work Units: definição de Beads e Hook |

## Comparação de princípios

| Conceito da referência | O que a fonte efetivamente descreve | Padrão útil para Jangada | Limite da transposição |
|---|---|---|---|
| Mayor | Coordenador global persistente, com visão de projetos no README e Overview | Identidade de coordenação separada de tarefas | Um coordenador por projeto é o recorte próprio inicial; coexistência no mesmo projeto é evolução futura |
| Rigs | Contêineres de projeto associados a repositórios, conforme README | Projeto como unidade explícita de escopo | Contêiner de projeto não comprova sigilo entre conversas |
| Polecats | Trabalhadores com identidade persistente e sessões temporárias, conforme Lifecycle | Separar identidade, execução e espaço de trabalho | Descarte de sessão e envio remoto descritos ali não autorizam operações equivalentes no Jangada |
| Hooks | Trabalho ligado ao agente e preservado, segundo README e Glossary | Retomar atribuição por estado durável | Não confundir com autorização humana autenticada nem com hooks de segurança do Jangada |
| Convoys | Acompanhamento persistente de itens relacionados, separado do conjunto temporário de trabalhadores | Plano/atividade reúne tarefas sem depender da sessão do modelo | Relação de acompanhamento não define dependência, aceite ou permissão |
| Beads | Unidade estruturada de trabalho; Architecture e Glossary descrevem armazenamento em Dolt | Proveniência, estados e vínculos verificáveis | Não exige substituir SQLite nem adotar servidor/dependências da referência |

As fontes distinguem identidade e sessão. O documento Lifecycle descreve aposentadoria da sessão concluída, preservando identidade e evidências.
Architecture ainda descreve retorno à disponibilidade no ciclo do trabalhador; essa diferença impede tratar toda documentação como contrato operacional único.
O aprendizado aplicável é a separação de camadas, sem copiar a regra de reciclagem.
([Lifecycle](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/concepts/polecat-lifecycle.md),
[Architecture](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/design/architecture.md)).

Convoys permite uma visão de itens de vários projetos; isso não exige compartilhar os diálogos que originaram cada item.
O Jangada deve agregar metadados operacionais autorizados e preservar as fronteiras de contexto.
([Convoys](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/concepts/convoy.md)).

Overview recomenda executar trabalho atribuído sem esperar confirmação.
No Jangada, atribuição só habilita execução depois de verificação da autorização pelo controlador.
Uma instrução em artefato recebido não pode ampliar permissões.
([Overview](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/overview.md)).

Architecture documenta banco Dolt central e uma estrutura de processamento de integrações.
Isso serve como referência de arbitragem; não demonstra que copiar esse armazenamento resolveria segurança, custo ou concorrência do Jangada.
A proposta conserva revisão independente e gesto humano da entrega exata.
([Architecture](https://raw.githubusercontent.com/gastownhall/gastown/main/docs/design/architecture.md)).

## Riscos e mitigação proposta

Os riscos atuais usam os achados A1 a A20 do [01](01-diagnostico.md).
Os riscos futuros decorrem das novas fronteiras do [02](02-coordenador-contextos.md), não são afirmações de defeito já explorado.

| Risco | Base e efeito | Mitigação e prova futura |
|---|---|---|
| Confundir pastas com independência | A2/A3: remoção de Shell/Monitor pode retirar configuração/diagnóstico | Contratos e teste de remoção em cópia de teste; classificar testes mistos sem esconder dependência real |
| Elevar o modelo a controlador | A6/A10: nome ou narrativa pode parecer autoridade | Modelo isolado; recibos fora de sua escrita; testes de proposta adulterada e operação sem gesto humano |
| Misturar conversas | A8/A20: armazenamento e clientes atuais não demonstram isolamento fino | Escopo obrigatório em mensagens, consultas, eventos, buscas e adaptadores; dois coordenadores em dois projetos distintos desde fase 2; testar também conversas do mesmo coordenador |
| Vazamento de fontes e credenciais | A20: proteção de escrita não limita toda leitura/rede | Delimitar contexto e acesso do adaptador; negar rota não aprovada; preferência agy não autoriza fonte confidencial nem remove restrições de envio |
| Injeção por página, log ou colaboração | Conteúdo externo chega ao modelo | Dado sem autoridade; controlador valida operação estruturada; texto “integre” em fonte não inicia integração |
| Resumo transforma hipótese em decisão | A7 e nova memória operacional | Referenciar gesto humano preservado; rótulos de proposta, decisão e evidência diferentes |
| Aprovação obsoleta | A16/A17: objeto muda entre prévia e execução | Recibo vinculado ao conteúdo/versão, reconferência e revisão do novo candidato |
| Execução duplicada ou revogada | Queda entre autorização, despacho e confirmação | ID repetível, registro de intenção, geração da reserva e revogação atômica; resultado incerto bloqueia repetição cega |
| Edição concorrente e integração conflitante | A12/A16: reservas de fila não cobrem todo editor/Git externo | Recursos declarados, versões e serialização no Core; detectar ação externa, preservar trabalho e pedir decisão |
| Interrupção e retomada incorreta | A13: acompanhamento não é serviço persistente | Reconciliar processos e artefatos; avaliar supervisão; nunca concluir pela memória do modelo |
| Atualização quebra sessão ativa | A18/A19: versões e acoplamentos compartilhados | Sessão registra versão de código/contrato/política; atualização incompatível recusa ou aguarda encerramento autorizado |
| Regressão ao ampliar Central | A4/A5/A17: filtros, foco e encerramento já têm comportamento próprio | Protótipo com dados sintéticos; contratos de ações; destino fixo, rascunhos separados e teste de fechamento |
| Consultas caras | A14/A15: cópia de banco/WAL e listagem integral | Medir tempo, memória, bytes e tamanho; paginação, cursor, filtros e atualização incremental sem escrever na origem |
| Custo contínuo de coordenação | Modelo pode girar durante espera | Despertar por eventos relevantes, agrupar duplicados e impor orçamento conjunto; medir chamadas por ciclo |
| Cota agy partilhada | Consulta de cota não equivale a reserva entre chamadas simultâneas | Preservar limites e orçamento; registrar indisponibilidade/consumo desconhecido e não trocar para Ollama |
| Medidas incompletas confundidas com zero | Consumo varia por adaptador | Preservar nulos e cobertura; não escolher modelo por preço/competência inferidos |
| Retenção apaga evidência ou guarda diálogo demais | Três finalidades distintas | Políticas separadas, preservação antes de exclusão e auditoria indicando o que deixou de ser recuperável |
| Apoio agy apenas declarado | Perfil ou destino configurado não prova trabalho efetivo | Subtarefa delimitada, evidências e contribuição conferida; bloqueio comunicado, sem trocar destino nem substituir Claude |
| Exploração confundida com autorização | Alternativa recomendada pode parecer decisão do dono | Separar explorar, propor e autorizar; perguntar somente por lacuna que muda objetivo/escopo/conteúdo |
| Infraestrutura antecipada | Novo serviço ou envio integrado sem problema demonstrado | Avaliar sessões e Central atuais primeiro; benefício e decisão próprios antes de expandir |
| Complexidade importada da referência | Papéis e dependências adicionais sem necessidade demonstrada | Coordenador mínimo por eventos; sem hierarquia, Dolt, nomenclatura ou reescrita presumida |

## Provedores por função

A seleção proposta separa coordenar, executar, revisar e apoiar leitura.
O [01](01-diagnostico.md#provedores-examinados) identifica os adaptadores examinados e suas restrições.
Como fato do código examinado, Claude/Codex têm sessões principais e revisão; agy tem apoio e revisão; Ollama tem conversa local e apoio delimitado.
A política recebida para a proposta é outra: todas as delegações usam `JANGADA_DELEGAR=agy`, inclusive leitor/redator.
Não há local primeiro nem alternativa Ollama; indisponibilidade, confiança, cota ou permissão insuficiente viram bloqueio comunicado.
Claude permanece o revisor independente desta tarefa; preferência de delegação não modifica essa função.
Isso não comprova que qualquer um já ofereça o novo protocolo de coordenador persistente.
Kimi é exemplo do briefing, sem integração examinada que autorize recomendação de capacidade.

Critérios de seleção: adequação demonstrada à função, disponibilidade observada, destino permitido dos dados,
conectividade, custo conhecido, contexto suportado e independência em relação ao autor.
Desconhecido permanece desconhecido. Modelos de apoio devem ser avaliados dentro do destino agy autorizado.
A preferência global não autoriza envio de documentos confidenciais.
Correção dos padrões/protocolos fica na tarefa separada `delegacao-agy-padrao`, sem ampliar escopo desta entrega.
O dono já escolheu o destino agy para delegação; demais funções e modelos continuam configuráveis conforme autorização.
Alternativa entre modelos do agy só usa candidatos autorizados e registra motivo/modelo efetivo; falha não muda para Ollama.

## Prioridade

No fluxo inicial, aperfeiçoar exploração, pedido executável e participação agy com evidências.
Fronteiras de autoridade e contexto continuam condições de qualquer ampliação de operação ou acesso.
A arbitragem e transferência entre coordenadores no mesmo projeto são riscos de evolução futura, não exigência inicial de implementação.
UX e indicadores dependem desses contratos; um desenho visual não corrige isolamento no Core.
Segurança exige provas negativas, recuperação exige provas de falha e desempenho exige medição.
Nenhuma dessas provas futuras é substituída por um parecer de modelo ou pelo estado datado de estabilização.
