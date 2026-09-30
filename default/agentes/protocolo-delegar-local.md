8. Subagentes (delegação local e ao Claude):
   - Para ler documento longo ou revisar redação (papéis `leitor` e `redator`),
     use primeiro `jangada-delegar PAPEL "pedido" --arquivos ARQUIVOS`. Ele roda
     um modelo local no Ollama, sem gastar cota externa nem expor dados.
   - Para os demais papéis (explorador, pesquisador, verificador, auditor,
     arquiteto, otimizador), use o subagente do Claude do mesmo papel.
   - Só se o comando recusar (modelo ausente, jogo aberto, limite de contexto
     ou fatias), use o subagente do Claude do mesmo papel. Nunca
     `general-purpose` para essas funções.
