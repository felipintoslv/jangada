# Regressões de ausência, desempenho e filtros sobre dados sintéticos.
source("default/painel/indicadores.R")
stopifnot(is.na(soma_medida(c(NA, Inf, -1))), soma_medida(c(NA, 0)) == 0,
          is.na(media_avaliacoes(c(NA, NaN, Inf))), media_avaliacoes(c(NA, 0)) == 0)
cache <- tempfile("painel-motores-")
dir.create(cache)
jsonlite::write_json(list(), file.path(cache, "coleta.json"))
jsonlite::write_json(list(list(fonte = "codex_externo", origem = "interface_externa",
  estado = "erro", atualizado = "2026-09-30T23:00:00-03:00",
  ultima_tentativa = "2026-10-01T02:30:00Z", dados_preservados = TRUE),
  list(fonte = "legada", estado = "sem_dados", atualizado = "2026-09-30T23:00:00"),
  list(fonte = "ausente", estado = "sem_dados")), file.path(cache, "cobertura.json"))
d <- carregar_cache(cache)$consumo
r <- as.data.frame(lapply(d, function(x) rep(x[NA_integer_], 3)))
r$id <- c("local1", "local2", "externo")
r$data <- as.POSIXct(paste(c(Sys.Date(), Sys.Date() - 1, Sys.Date()), "12:00:00"), tz = "")
r$dia <- as.character(as.Date(r$data))
r$executor <- c("ollama", "ollama", "codex")
r$provedor <- c("ollama", "ollama", "openai")
r$origem <- c("jangada", "jangada", "interface_externa")
r$modelo <- c("qwen", "qwen", "codex")
r$papel <- c("leitor", "redator", "")
r$projeto <- "teste"
r$saida <- c(10, 90, NA)
r$entrada_total <- c(0, 100, NA)
r$tempo_geracao_ms <- c(1000, 3000, NA)
local <- desempenho_local(r)
stopifnot(local$tokens_s == 25, local$com_tempo_geracao == 2,
          resumo_motores(r)$registros[resumo_motores(r)$executor == "codex"] == 1)
diario <- consumo_motores_diario(r)
stopifnot(sum(diario$saida, na.rm = TRUE) == 100,
          is.na(diario$saida[diario$executor == "codex"]),
          diario$com_saida[diario$executor == "codex"] == 0)
r$tempo_geracao_ms <- NA_real_
stopifnot(is.na(desempenho_local(r)$tokens_s))
arrow::write_parquet(r, file.path(cache, "consumo.parquet"))
p <- carregar_cache(cache)$pesquisas
p <- as.data.frame(lapply(p, function(x) rep(x[NA_integer_], 2)))
p$id <- c("sem-nota", "zero")
p$data <- r$data[1:2]; p$dia <- r$dia[1:2]
p$estado <- "sem_auditoria"; p$autor <- "teste"; p$par <- "teste"
p$grau_fato <- c(NA_integer_, 0L); p$pergunta <- "Consulta sintética"
arrow::write_parquet(p, file.path(cache, "pesquisas.parquet"))
options(jangada.painel.cache = cache)
shiny::testServer(shiny::shinyAppDir("default/painel"), {
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()), executor = "ollama")
  stopifnot(nrow(motores()) == 1, nrow(pesqs()) == 1,
            identical(output$f_fato, "Sem avaliação"),
            !grepl("NA%", output$f_tabela),
            !grepl("NaN", output$manchete_dia))
  session$setInputs(executor = NULL, origem_consumo = "interface_externa")
  stopifnot(nrow(motores()) == 1, motores()$executor == "codex")
  session$setInputs(periodo = c(Sys.Date() - 1, Sys.Date()), origem_consumo = NULL,
                    modelo_consumo = "qwen")
  stopifnot(nrow(motores()) == 2, nrow(pesqs()) == 2)
  invisible(output$b_motores); invisible(output$b_local)
  invisible(output$b_fontes); invisible(output$b_ferramentas)
  stopifnot(grepl("com erro", output$situacao_fontes$html),
            sum(fontes()[["idade (min)"]] == "sem data válida") == 2)
  session$setInputs(modelo_consumo = NULL, provedor_consumo = "ollama", papel_consumo = "redator")
  stopifnot(nrow(motores()) == 1, motores()$papel == "redator")
  invisible(output$b_motores_dia); invisible(output$b_motores_cob)
  invisible(output$b_local_grafico)
})
unlink(cache, recursive = TRUE)
message("Indicadores e filtros de motores: testes passaram")
