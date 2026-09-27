8. Subagentes (delegação ao agy):
   - Para explorar código ou registros, ler documento longo, pesquisar na
     web ou verificar antes do `jangada-validar`, use primeiro
     `jangada-delegar PAPEL "pedido"`, com PAPEL explorador, leitor,
     pesquisador ou verificador. Ele roda um agente Flash do agy e devolve
     um relatório curto.
   - Só se o comando recusar (cota, erro ou tempo), use o subagente do
     Claude do mesmo papel. Nunca `general-purpose` para essas funções.
