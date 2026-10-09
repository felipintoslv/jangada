# Relatório de prontidão

**NÃO APTA para congelamento da baseline de 30 dias neste momento.**

O risco prioritário de perda de edições concorrentes foi efetivamente bloqueado. A integração automática não publica nem recupera o principal e conserva sessão, ramo e worktree. A reversão automática ao atingir limite também foi bloqueada. Validação indisponível, pulada, autorrevisão e autoria externa sem cópia protegida não geram aprovação. As marcas e a prévia conferem identidade da entrega.

Há evidência positiva dos ensaios de preservação, aprovação, encerramento, atualização, backup e recuperação sintéticos e das duas suítes R do painel. A suíte completa foi executada, mas não passou: o sandbox impede comunicação local e o perfil de isolamento sem rede. Foram 7 grupos reprovados, descritos em `TESTES_BASELINE.md` e `EVIDENCIAS.json`; isso não significa apenas 7 asserções individuais. Essas etapas não podem ser corrigidas alterando serviços ou permissões globais, nem por execução fora do isolamento, dentro dos limites desta missão.

## Disponível e restrito

Disponíveis na worktree de engenharia: comandos de projetos e tarefas, fila e persistência; execução em worktree e isolamento existente; revisão congelada; validação com recusa conservadora; encerramento após conferência; atualização e assinatura; componentes da Central e do painel. A aplicação cotidiana desses fluxos depende das verificações de ambiente pendentes.

Bloqueados no backend: integração automática com ramo próprio e reversão automática da validação. Restritos por falta de evidência: ponta a ponta gráfico, comunicação completa de serviços locais e validação sem rede neste sandbox. Os modos manuais de trabalho direto, execução sem isolamento e descarte ainda existem; não compõem o plano de 30 dias.

## Condições para congelar

Executar a suíte completa sem falhas em ambiente compatível, incluindo isolamento real, D-Bus e serviços locais; concluir um ensaio gráfico com agente e revisor reais sobre projeto sintético; conferir backup completo e recuperação; aprovar uso supervisionado com integração manual. Até lá, conservar os commits para revisão e não criar `jangada-baseline-2026-10`.

Código conferido: `5816c76e81829569e9e4c9593ed176c53c4e69bc`.

O ramo de estabilização contém somente commits locais. `main`, `estavel`, instalação ativa, serviços e pacotes do host foram preservados. Nenhum push, merge em main, release ou tag foi executado. Os commits e seus testes estão registrados em `EVIDENCIAS.json`; o commit final de documentação é apresentado na entrega da missão.
