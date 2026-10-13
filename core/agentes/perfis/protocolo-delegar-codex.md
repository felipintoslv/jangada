8. Delegação no Codex:
   - Para todos os papéis de apoio, inclusive leitor e redator, use primeiro
     `jangada-delegar PAPEL "pedido" --destino agy --permitir-remoto`,
     com escopo e fontes autorizados nesta tarefa em `--arquivos`.
   - Agy é o destino padrão também sem perfil. A preferência não autoriza
     compartilhar dados confidenciais; obtenha autorização para as fontes
     antes de usar `--permitir-remoto`.
   - Na recusa, registre e informe o bloqueio. A investigação pode continuar
     nesta sessão, mas o apoio não foi concluído. Não tente chamar subagentes do Claude
     a partir do Codex nem encaminhe automaticamente ao Ollama.
   - Com `JANGADA_DELEGAR=local` explicitamente escolhido, leitor e redator
     podem usar `--destino local --arquivos ARQUIVOS`; os demais papéis ficam
     nesta sessão. Uma falha local nunca autoriza envio remoto.
   - A seleção por `--capacidade` é opcional e documental, com o papel leitor
     e `--arquivos`. A política padrão seleciona somente agy; sem autorização,
     confiança, acesso ou cota, registra bloqueio sem alternativa local automática.
   - O papel `supervisor`, com `analise_documental`, confere somente relatórios
     intermediários autorizados. Não use o Ollama para emitir esse parecer
     nem substitua o `jangada-validar` por supervisão de conteúdo.
