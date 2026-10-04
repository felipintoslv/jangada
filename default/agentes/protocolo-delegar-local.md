8. Subagentes (delegação local e ao Claude):
   - Para ler documento longo ou revisar redação (papéis `leitor` e `redator`),
     use primeiro `jangada-delegar PAPEL "pedido" --arquivos ARQUIVOS`. Ele roda
     um modelo local no Ollama, sem gastar cota externa nem expor dados.
   - Para os demais papéis (explorador, pesquisador, verificador, auditor,
     arquiteto, otimizador, supervisor), use o subagente do Claude do mesmo papel.
   - Se o comando recusar (modelo ausente, jogo aberto, limite de contexto
     ou fatias), avise o usuário antes de recorrer ao subagente do Claude caso
     o conteúdo seja confidencial. Em tarefas comuns, use o subagente do Claude
     do mesmo papel. Nunca `general-purpose` para essas funções.
