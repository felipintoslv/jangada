8. Delegação no Codex:
   - Para ler documentos ou revisar redação, use primeiro
     `jangada-delegar PAPEL "pedido" --destino local --arquivos ARQUIVOS`,
     com PAPEL leitor ou redator. O Ollama recebe somente os arquivos indicados.
   - Para outros papéis, use `jangada-delegar PAPEL "pedido" --destino agy`
     quando o destino configurado permitir. Na recusa, faça a investigação
     nesta sessão. Não tente chamar subagentes do Claude a partir do Codex.
   - Com JANGADA_DELEGAR=local, os demais papéis ficam nesta sessão.
   - Não envie documentos confidenciais a outro provedor sem autorização.
     Uma recusa local nunca autoriza o envio à nuvem.
   - A seleção por `--capacidade` é opcional e documental, com o papel leitor
     e `--arquivos`. Use `--permitir-remoto` somente quando houver autorização
     para enviar as fontes ao agy e o perfil permitir. A verificação de
     referências não aprova o conteúdo nem substitui a revisão da entrega.
