# Achados atuais e entrada em produção

Atualização de 09/10/2026. Registro documental no ramo principal, cuja base de código é `bf7a5f1`. Este commit não incorpora as correções de código da branch P0 nem atualiza a instalação ativa.

## Estado confirmado

| Verificação | Evidência | Alcance |
|---|---|---|
| Proteções P0 | 32/32 cenários passaram em Bubblewrap real | Versão `17178ded`, não o código atual de main |
| Interface | 67/67 testes passaram no terminal local | Cópia sintética da versão P0; não comprova o ciclo gráfico completo |
| Indicadores da tarefa par-cobaia | 294 conferências passaram em sete cenários | Artefato `bb3ad6b`, comparado com referência Python independente |
| Oráculo econômico | Duas rodadas Python/R concordantes | Ensaios determinísticos; não execução econômica completa por IA |
| Codex real | Chamada curta respondeu corretamente | Conectividade pelo isolamento P0 |
| agy no ambiente sintético | Autenticação falhou; última sonda retornou NoReply | Credencial não foi lida pela ponte; nenhuma revisão real nesse ambiente |
| Revisão na instalação ativa | Parecer apenas STATUS: APROVADO | Não comprova revisão metodológica fundamentada nem decisão protegida P0 |

## Riscos que impedem declarar produção validada

P0-A: na versão original e na baseline, o executor conseguia adulterar o SQLite e forjar conclusão/revisão. P0-B: o encerramento removia evidências necessárias para reconstruir a revisão. As correções estão na branch `correcao/confianca-p0-2026-10`, commit `17178ded546642e3246bfe3bd5c33df8da821874`. Acrescentar estes relatórios a main não corrige esses caminhos.

A instalação ativa difere da P0 nos lançadores e não contém `default/orquestracao/confianca.py`. A sessão real par-cobaia utilizou executáveis instalados, não a cópia P0. Não encerrar essa sessão para tentar comprovar garantias de arquivamento de outra versão.

A classificação P1 permanece **INCONCLUSIVA**. Não foram demonstrados o ciclo econômico completo com modelos reais, reprovação/correção, nova revisão, aprovação protegida e recuperação integral do histórico dessa atividade. A integração automática permanece bloqueada na versão P0; esse bloqueio não foi incorporado ao código de main por este registro documental.

## Sequência para disponibilização

1. Incorporar e verificar as correções P0 de código antes de disponibilizar main a agentes em projetos reais. Preservar o bloqueio de integração automática.
2. Identificar as sessões ativas e fazer backup verificável de configurações, bancos e evidências antes de atualizar a instalação. Não substituir executáveis usados por sessões em andamento.
3. Preparar a atualização da instalação com cópia de segurança e conferir os hashes dos componentes instalados. Evitar instalação geral ou mudanças de serviços para resolver somente o runtime dos agentes.
4. Confirmar inicialização, cadastro, tarefa, execução isolada, revisão externa pelo controlador, aprovação e encerramento em projeto descartável usando a versão efetivamente instalada.
5. Recuperar as evidências arquivadas sem consultar os documentos temporários. Somente depois avaliar uso experimental supervisionado por 30 dias.

A investigação de autenticação do agy foi interrompida a pedido do usuário. A sonda comparativa seguinte foi preparada, mas ainda não foi executada no terminal compatível. Não apresentar esse teste como aprovado.

## Relatórios e reprodução

- [Correção P0](correcao-p0/RELATORIO_FINAL.md)
- [Resultado P1](validacao-p1/relatorios/RELATORIO_FINAL.md)
- [Execução de modelos e falhas de autenticação](validacao-p1/relatorios/EXECUCAO_MODELOS.md)
- [Scripts de reprodução](validacao-p1/scripts/)
- [Evidências sintéticas](validacao-p1/evidencias/)

Os relatórios anteriores mantêm seus registros cronológicos. O estado atual está consolidado neste documento. A cópia P1 usa caminhos originais do ambiente de ensaio; adaptar somente os caminhos sintéticos ao reproduzir. `validacao-p1/SHA256SUMS` também referencia dados e gabaritos que permaneceram no repositório externo e não foram copiados para main. O manifesto deste registro lista apenas os documentos efetivamente incorporados.
