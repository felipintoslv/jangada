# Regressões de ausência, desempenho e filtros sobre dados sintéticos.
source("default/painel/indicadores.R")
source("default/painel/hoje.R")
stopifnot(is.na(soma_medida(c(NA, Inf, -1))), soma_medida(c(NA, 0)) == 0)
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
options(jangada.painel.cache = cache)
carimbo <- format(Sys.time(), "%Y-%m-%dT%H:%M:%S%z")
ontem <- format(Sys.time() - 86400, "%Y-%m-%dT%H:%M:%S%z")
jsonlite::write_json(list(registros = list(subagentes = list(), entregas = list(), delegacoes = list(
  list(data = carimbo, projeto = "teste", destino = "codex-economico", sem_fonte = 2),
  list(data = carimbo, projeto = "outro", destino = "local", sem_fonte = 7),
  list(data = ontem, projeto = "teste", destino = "agy", sem_fonte = 9)))),
  file.path(cache, "subagentes.json"), auto_unbox = TRUE)
jsonlite::write_json(list(tarefas = list(
  list(projeto = "teste", id = "espera", estado = "WAITING_QUOTA", saldo_chamadas = NULL),
  list(projeto = "outro", id = "concluida", estado = "COMPLETED")),
  projetos = list(list(projeto = "teste", chamadas_confirmadas = 2, custo_estimado = NULL)),
  provedores = list(), erros = list()), file.path(cache, "orquestracao.json"), auto_unbox = TRUE, null = "null")
shiny::testServer(hoje_server, args = list(dados = shiny::reactive(carregar_cache(cache))), {
  stopifnot(grepl("Sessões aguardando: 0", output$aviso$html),
            grepl("Sem observações de provedores", output$aviso$html),
            !grepl("<td", output$sessoes), !grepl("<td", output$revisoes), !grepl("<td", output$paradas))
})
d_hoje <- carregar_cache(cache)
d_hoje$sessoes <- data.frame(sessao = "aguarda", projeto = "teste", agente = "codex",
  estado = "aguardando", desde = Sys.time() - 4 * 86400, atualizado = Sys.time())
v_hoje <- as.data.frame(lapply(d_hoje$validacoes, function(x) rep(x[NA_integer_], 3)))
v_hoje$data <- Sys.time() + c(-3, -2, -1)
v_hoje$rotulo <- "aguarda"; v_hoje$projeto <- "teste"
v_hoje$entrega <- c("antiga", "aprovada", "atual")
v_hoje$resultado <- c("revisar", "aprovado", "revisar")
v_hoje$rodada <- 1L; v_hoje$mais <- 1L; v_hoje$menos <- 0L
v_hoje$origem <- "agentes"; v_hoje$autor <- "codex"; v_hoje$revisor <- "claude"
d_hoje$validacoes <- v_hoje
d_hoje$orquestracao$tarefas[[1]]$estado <- "REVIEW_REQUIRED"
d_hoje$orquestracao$provedores <- list(list(id = "ollama", status = "UNKNOWN", motivo = "observação vencida"))
d_hoje$orquestracao$erros <- list("fonte indisponível")
shiny::testServer(hoje_server, args = list(dados = shiny::reactive(d_hoje)), {
  stopifnot(grepl("Sessões aguardando: 1", output$aviso$html),
            grepl("Coleta incompleta", output$aviso$html),
            grepl("Revisões pendentes registradas: 2", output$aviso$html), grepl("aguarda", output$sessoes),
            grepl("espera", output$revisoes), grepl("Desconhecido", output$provedores),
            nrow(hoje_pendentes()) == 1, !grepl("<td", output$paradas), grepl("ollama", output$consumo))
})
aplicacao <- shiny::shinyAppDir("default/painel")
html <- as.character(environment(aplicacao$serverFuncSource())$ui)
stopifnot(grepl('class="active">\\s*<a[^>]*data-value="Hoje"', html),
          grepl("Esta fila reúne tarefas planejadas", html),
          grepl("Provedores são os serviços ou executores", html))
shiny::testServer(aplicacao, {
  session$setInputs(modo = "dark", periodo = c(Sys.Date(), Sys.Date()), executor = "ollama")
  escuro <- jsonlite::fromJSON(output$b_motores_dia, simplifyVector = FALSE)
  vazio_escuro <- plotly::plotly_build(vazio())$x$layout
  stopifnot(escuro$x$layout$paper_bgcolor == aparencia()$fundo,
            escuro$x$layout$font$color == aparencia()$texto,
            vazio_escuro$font$color == aparencia()$texto)
  session$setInputs(modo = "light")
  claro <- jsonlite::fromJSON(output$b_motores_dia, simplifyVector = FALSE)
  stopifnot(claro$x$layout$paper_bgcolor == "#FFFFFF",
            claro$x$layout$font$color == "#1A1A1A",
            claro$x$data[[1]]$marker$color != escuro$x$data[[1]]$marker$color)
  rede <- list(nos = data.frame(id = 1:2, label = c("Leitura", "Teste"), group = c("leitura e busca", "teste")),
               arestas = data.frame(from = 1L, to = 2L))
  rede_clara <- grafo(rede)$x
  stopifnot(rede_clara$options$edges$color$color == "#888888",
            rede_clara$options$edges$color$color != aparencia()$grade)
  session$setInputs(modo = "dark")
  rede_escura <- grafo(rede)$x
  stopifnot(rede_escura$options$nodes$font$color == aparencia()$texto,
            rede_clara$options$nodes$font$color == "#1A1A1A",
            rede_escura$options$edges$color$color == "#999999",
            rede_escura$options$edges$color$color != aparencia()$grade,
            rede_escura$options$edges$color$color != rede_clara$options$edges$color$color)
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()), executor = "ollama")
  stopifnot(nrow(motores()) == 1)
  session$setInputs(executor = NULL, origem_consumo = "interface_externa")
  stopifnot(nrow(motores()) == 1, motores()$executor == "codex")
  session$setInputs(periodo = c(Sys.Date() - 1, Sys.Date()), origem_consumo = NULL,
                    modelo_consumo = "qwen")
  stopifnot(nrow(motores()) == 2)
  invisible(output$b_motores); invisible(output$b_local)
  invisible(output$b_fontes); invisible(output$b_ferramentas)
  stopifnot(grepl("com erro", output$situacao_fontes$html),
            sum(fontes()[["idade (min)"]] == "sem data válida") == 2)
  session$setInputs(modelo_consumo = NULL, provedor_consumo = "ollama", papel_consumo = "redator")
  stopifnot(nrow(motores()) == 1, motores()$papel == "redator")
  invisible(output$b_motores_dia); invisible(output$b_motores_cob)
  invisible(output$b_local_grafico)
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()), projeto = "teste")
  stopifnot(sub()$destinos$`codex-economico` == 1, length(sub()$destinos) == 1,
            length(orq()$tarefas) == 1, identical(output$g_esperando, "1"),
            identical(output$g_concluidas, "0"),
            sub()$qualidade$por_destino$`codex-economico`$n == 1)
  invisible(output$e_fonte)
  invisible(output$e_destinos)
  invisible(output$g_metricas)
  invisible(output$g_provedores)
  session$setInputs(periodo = c(Sys.Date() - 1, Sys.Date()))
  stopifnot(length(sub()$destinos) == 2, sub()$destinos$agy == 1,
            identical(output$g_esperando, "1"))
  session$setInputs(projeto = "outro")
  stopifnot(length(sub()$destinos) == 1, sub()$destinos$local == 1,
            identical(output$g_concluidas, "1"))
  stopifnot(grepl("Nenhuma observação", output$g_provedores_aviso$html))
  session$setInputs(projeto = "sem-fila")
  stopifnot(grepl("projetos selecionados", output$g_vazia$html))
})
r7 <- r[rep(1, 7), ]
r7$id <- paste0("serie", seq_len(7))
r7$modelo <- paste("modelo", seq_len(7))
arrow::write_parquet(r7, file.path(cache, "consumo.parquet"))
shiny::testServer(shiny::shinyAppDir("default/painel"), {
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()))
  grafico <- jsonlite::fromJSON(output$b_motores_dia, simplifyVector = FALSE)
  stopifnot(length(grafico$x$data) >= 7,
            all(vapply(grafico$x$data, function(t) t$type == "scatter", FALSE)))
})
jsonlite::write_json(list(tarefas = list(), projetos = list(), provedores = list(), erros = list()),
                     file.path(cache, "orquestracao.json"), auto_unbox = TRUE)
shiny::testServer(shiny::shinyAppDir("default/painel"), {
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()))
  session$setInputs(projeto = character())
  stopifnot(grepl("Nenhuma tarefa de automação cadastrada", output$g_vazia$html),
            grepl("Nenhuma observação", output$g_provedores_aviso$html))
})
jsonlite::write_json(list(erros = "Coleta incompleta"), file.path(cache, "orquestracao.json"), auto_unbox = TRUE)
shiny::testServer(shiny::shinyAppDir("default/painel"), {
  session$setInputs(periodo = c(Sys.Date(), Sys.Date()))
  stopifnot(grepl("Coleta incompleta", output$g_erros$html),
            is.null(output$g_vazia), is.null(output$g_provedores_aviso))
})
unlink(cache, recursive = TRUE)
message("Indicadores e filtros de motores: testes passaram")
