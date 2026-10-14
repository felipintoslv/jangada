# Consolidação arquitetural e Central de Trabalho

A prioridade é preservar e aprimorar a coordenação atual, com um coordenador por projeto e várias conversas e tarefas.
O coordenador ajuda o dono a construir alternativas antes de definir um pedido executável.
A evolução aproveita sessões, comandos, revisão e Central existentes; nova infraestrutura depende de benefício demonstrado e autorização própria.

## Decisões recebidas e recorte

Atualização do dono em 13/10/2026, prevalecendo sobre o briefing original:

- Um coordenador por projeto no primeiro aceite, com identidade própria e várias conversas/tarefas.
- Todas as delegações usam `JANGADA_DELEGAR=agy`, inclusive leitor/redator, sem local primeiro ou alternativa Ollama.
- Apoio agy concreto e verificável, com contribuição examinada ou bloqueio explícito; não basta perfil configurado.
- Exploração de alternativas antes da implementação: entender o problema, questionar premissas, recomendar com justificativa e explicitar decisões pendentes.
- Objetivos, conteúdo e permissões continuam com o dono. Exploração e proposta não autorizam execução.
- Isolamento entre projetos e entre conversas do mesmo coordenador continua necessário.
- Dois coordenadores nos ensaios iniciais significam dois projetos distintos.
- Múltiplos coordenadores no mesmo projeto, transferências e arbitragem entre eles são evolução futura, fora do primeiro aceite.
- Conversa integrada e processo supervisionado são opções a avaliar, sem substituir as sessões atuais por presunção.

Esta tarefa só produz seis documentos. Não altera nem instala a skill ativa,
não implementa, integra, assina, publica ou aplica configurações.
Autor e coordenador: Codex. Revisor independente exigido: Claude, pelo fluxo de `jangada-validar`.

## Base e método

Código examinado em 13/10/2026 no commit `6e7b751a16f51f1de9db4916ccbe92e292f125f7`.
Identificação Git: `jangada-pre-modularizacao-3.0-132-g6e7b751`.
Localizadores do diagnóstico referem-se a essa versão, não à instalação ativa.

Foram consultados README, AGENTS, CLAUDE, ciclo, registros, isolamento, provedores, delegação e documentos 01 a 06 da modularização 3.0.
Os registros de estabilização e modularização foram tratados como datados, com achados atuais confrontados com o código.
A skill existente foi examinada como fonte do fluxo atual; a proposta textual está no [02](02-coordenador-contextos.md).
A atualização completa do pedido foi lida, sem copiar conteúdo privado para os documentos.
Fontes Gas Town são oficiais e acessíveis pela web, com limites no [04](04-gas-town-riscos.md).
Não houve consulta a históricos privados dos provedores nem operação real para demonstrar capacidades.

## Índice e resultados

| Resultado | Documento |
|---|---|
| Mapa atual, dependências e evidências | [01 Diagnóstico](01-diagnostico.md) |
| Inventário reutilizável e lacunas | [01 Diagnóstico](01-diagnostico.md) |
| Coordenador, ciclo, exploração e proposta textual da skill | [02 Coordenador e contextos](02-coordenador-contextos.md) |
| Identidade, contextos, apoio agy, segurança e evolução futura | [02 Coordenador e contextos](02-coordenador-contextos.md) |
| UX atual aprimorada e opção de conversa integrada | [03 Central e UX](03-central-ux.md) |
| Gas Town, limites e riscos | [04 Gas Town e riscos](04-gas-town-riscos.md) |
| Marcos, dependências, aceite e complexidade | [05 Plano incremental](05-plano-incremental.md) |

O diagnóstico confirma componentes reutilizáveis, mas não independência funcional completa ou identidade persistente de coordenador já implementada.
A primeira entrega futura melhora o fluxo atual. As ampliações opcionais ficam separadas no plano.

## Decisões arquiteturais pendentes

A direção recebida acima está definida. As escolhas abaixo dizem respeito à forma de realizá-la, não reabrem o escopo.

| Decisão | Recomendação a avaliar | Consequência da alternativa |
|---|---|---|
| D1: fronteiras | Contratos públicos de comandos, consultas e eventos; retirar dependências obrigatórias do Core | Manter exceções adia independência funcional |
| D2: representação da identidade | ID estável por projeto, separado do provedor, associado às sessões atuais | Um nome de exibição não prova vínculo ou permissão |
| D3: recuperação de contexto | Estado operacional mínimo e seleção explícita entre conversas; sem importar diálogos automaticamente | Compartilhamento adicional exige decisão específica de objetos e retenção |
| D4: continuidade | Primeiro avaliar retomada manual e tmux; serviço só se houver lacuna comprovada | Instalar processo antes dessa avaliação aumenta manutenção e superfície de autoridade |
| D5: modelos por função | Candidatos explicados por capacidade examinada, dados permitidos, disponibilidade e independência | Não há configuração definitiva escolhida pelo dono |
| D6: retenção | Separar conversa, memória operacional e evidências, inclusive quando o diálogo fica no cliente atual | Um prazo único pode apagar provas ou conservar diálogos demais |
| D7: concorrência inicial | Preservar controles de tarefas, recursos e integração; delimitar lacunas | Arbitragem entre coordenadores no mesmo projeto fica para evolução futura |
| D8: conversa na Central | Avaliar navegação para sessões existentes e protótipo antes de decidir envio integrado | Integração imediata não é requisito do primeiro aceite |
| D9: compatibilidade | Registrar versões e impedir atualização incompatível de sessões ativas | Sem coexistência comprovada, aguardar encerramento autorizado |
| D10: confirmação humana | Preservar canais externos atuais; qualquer novo canal deve ser inacessível ao executor e comprovar gesto sobre objeto exato | Parâmetro declarado pelo modelo não autentica autorização |
| D11: evolução textual da skill | Avaliar o texto proposto e seus exemplos em tarefa própria | A direção de explorar alternativas já foi decidida; a skill ativa permanece intacta nesta entrega |

D1/D9 condicionam contratos; D2/D3/D5/D6/D10 condicionam qualquer novo registro ou operação de coordenação.
D11 permite melhorar exploração e apoio agy antes de ampliar infraestrutura.
Os padrões/protocolos agy e a cobrança de apoio na skill já estão corrigidos no repositório local.
A instalação não recebeu essa atualização. Exploração de alternativas e identidade persistente permanecem propostas.
Esta entrega é documental; o estado de verificação está no [05](05-plano-incremental.md).
A preferência global não autoriza envio de dados confidenciais; fontes, destino e permissão técnica continuam sujeitos a conferência.
D4/D8 só habilitam expansões após avaliação e decisão separadas.

## Verificação e limites

O resultado datado da suíte está no [05](05-plano-incremental.md).
Inspector, acessórios da Waybar, memória automaticamente compartilhada, hierarquias complexas e autonomia irrestrita continuam fora da proposta.
A reorganização visual não cria capacidade privilegiada, e aprovação documental não autoriza implementação ou integração.
