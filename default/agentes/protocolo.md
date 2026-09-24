Você trabalha numa sessão do jangada, num worktree próprio. Siga este protocolo
durante toda a conversa.

1. Trabalhe só dentro da pasta atual. Nunca edite `~/.local/share/jangada`
   (cópia instalada) nem arquivos de configuração fora do projeto.
2. Leia o `AGENTS.md` (ou `CLAUDE.md`) do projeto antes de alterar qualquer
   coisa e siga as regras dele, inclusive a de testes.
3. Faça commits pequenos, com mensagem em português e sem linha
   `Co-Authored-By`.
4. Ao executar suítes de testes ou comandos com saída extensa no terminal,
   utilize `jangada-filtrar` (ou o atalho `resumir` no jangada shell) para
   condensar a saída e economizar tokens do contexto. Para consultar a
   estrutura do repositório, utilize `jangada-mapa`.
5. Antes de dizer que terminou, rode `jangada-validar`. Ele executa primeiro
   uma verificação determinística local (conflitos do Git, sintaxe e testes do
   projeto). Passando no teste local, manda o diff para o revisor técnico (por
   padrão o outro modelo, ou o revisor configurado para a sessão) e imprime o
   parecer. A revisão pode levar alguns minutos: se a ferramenta de comando
   tiver tempo limite, dê 10 minutos.
   - `STATUS: APROVADO`: resuma o que foi feito e pare.
   - `STATUS: REVISAR`: o revisor pode errar. Confira cada apontamento no
     código, corrija o que for procedente, faça commit e rode de novo dizendo
     o que fez com cada item:
     `jangada-validar --resposta "1 corrigido; 2 rejeitado: motivo"`.
     O comando recusa depois do limite de rodadas; nesse caso, pare e descreva
     o que ficou pendente ou use `reverter` no shell para reiniciar a tarefa.
6. Não rode `jangada-validar` a cada passo: ele gasta tokens do revisor. Uma
   vez por entrega é o suficiente.
