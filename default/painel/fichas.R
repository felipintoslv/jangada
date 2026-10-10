# A mesma validação de cores serve ao painel e à Central Qt.
carregar_fichas <- function() {
  visual <- file.path(raiz_jangada, "default/visual")
  reserva <- jsonlite::read_json(file.path(visual, "padrao.json"))
  programa <- file.path(visual, "fichas.py")
  resposta <- tryCatch(
    system2("python3", c(shQuote(programa), "--json"), stdout = TRUE, stderr = FALSE),
    error = function(e) character()
  )
  if (!length(resposta) || !is.null(attr(resposta, "status"))) return(reserva)
  tryCatch(jsonlite::fromJSON(paste(resposta, collapse = "\n"), simplifyVector = FALSE),
           error = function(e) reserva)
}
