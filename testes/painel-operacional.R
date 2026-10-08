# Dados sintéticos conferem identidade, leitura e monitoramento após autenticação.
cache_teste <- tempfile("painel-operacional-")
dir.create(cache_teste)
ids <- c(strrep("a", 64), strrep("b", 64))
projetos <- lapply(ids, function(id) list(id = id, nome = "Mesmo nome", caminho = paste0("/", id), politica = list()))
tarefas <- lapply(seq_along(ids), function(i) list(id = "T1", projeto = ids[i], estado = "Pronta", status = "QUEUED",
  atualizado = as.numeric(Sys.time()), especificacao = list(pedido = paste("Fonte", LETTERS[i]), dependencias = list())))
tarefas <- c(tarefas, list(list(id = "T3", projeto = ids[1], especificacao = list()),
  list(id = "T4", projeto = ids[1], estado = "Em revisão", especificacao = list(criterios_aceite = "Critério pendente"))))
n <- list(projetos = projetos, atividades = list(), tarefas = tarefas, sessoes = list(), execucoes = list(),
  revisoes = list(), eventos = list(), provedores = list(), perfis = list(), erros = list(), data = "2026-10-08T10:00:00Z")
jsonlite::write_json(n, file.path(cache_teste, "nucleo.json"), auto_unbox = TRUE)
jsonlite::write_json(list(), file.path(cache_teste, "coleta.json"))
options(jangada.painel.cache = cache_teste, jangada.painel.chave = file.path(cache_teste, "ausente"))
aplicacao <- shiny::shinyAppDir("default/painel")
ambiente <- environment(aplicacao$serverFuncSource())
jsonlite::write_json(list(projetos = "inválido"), file.path(cache_teste, "nucleo.json"))
stopifnot(length(ambiente$carregar_cache(cache_teste)$nucleo$erros) == 1L)
jsonlite::write_json(n, file.path(cache_teste, "nucleo.json"), auto_unbox = TRUE)
html <- as.character(ambiente$ui)
secoes <- c("Visão Geral", "Projetos", "Central de Atividades", "Central de Agentes", "Modelos e Provedores",
            "Central de Revisão", "Monitoramento", "Histórico e Artefatos", "Configurações", "Indicadores")
stopifnot(all(vapply(secoes, function(s) grepl(s, html, fixed = TRUE), logical(1))))
chamadas <- new.env()
chamadas$n <- 0L
tabela_original <- ambiente$tabela
ambiente$tabela <- function(d, ...) {
  if (identical(names(d), c("Projeto", "Tarefa", "Critérios", "Motivo", "Artefato"))) chamadas$pendentes <- d
  tabela_original(d, ...)
}
ambiente$system2 <- function(...) {
  chamadas$n <- chamadas$n + 1L
  jsonlite::toJSON(list(data = "2026-10-08T10:00:00Z", cpu_ticks = list(total = chamadas$n * 100, ocioso = chamadas$n * 20),
    memoria_bytes = list(total = 100, usada = 50), gpu = NULL, modelos_carregados = list(), erros = list()), auto_unbox = TRUE, null = "null")
}
antes <- tools::md5sum(list.files(cache_teste, full.names = TRUE))
shiny::testServer(aplicacao, {
  session$setInputs(secao = "Projetos", op_projeto = ids[1], op_detalhe = paste("tarefa", ids[2], "T1", sep = "|"))
  stopifnot(grepl("Selecione", output$op_detalhes), chamadas$n == 0L)
  session$setInputs(op_detalhe = paste("tarefa", ids[1], "T1", sep = "|"))
  stopifnot(grepl("Fonte A", output$op_detalhes), !grepl("Fonte B", output$op_detalhes))
  stopifnot(grepl("f", jsonlite::fromJSON(output$op_historico)$x$options$dom, fixed = TRUE))
  stopifnot(grepl(ids[1], output$op_detalhes, fixed = TRUE))
  invisible(output$op_pendentes)
  stopifnot(identical(chamadas$pendentes$Tarefa, "T4"))
  session$setInputs(op_projeto = ids[2], op_detalhe = paste("tarefa", ids[2], "T1", sep = "|"))
  stopifnot(grepl("Fonte B", output$op_detalhes), !grepl("Fonte A", output$op_detalhes))
  session$setInputs(secao = "Monitoramento")
  primeira <- jsonlite::fromJSON(output$op_monitoramento)
  stopifnot(chamadas$n == 1L, is.null(primeira$cpu_percentual_medido))
  session$elapse(5000)
  segunda <- jsonlite::fromJSON(output$op_monitoramento)
  stopifnot(chamadas$n == 2L, segunda$cpu_percentual_medido == 80)
  session$setInputs(secao = "Projetos")
  session$elapse(10000)
  stopifnot(chamadas$n == 2L)
})
SemToken <- R6::R6Class("SessaoSemToken", inherit = shiny::MockShinySession, portable = FALSE, lock_objects = FALSE,
  parent_env = asNamespace("shiny"),
  active = list(request = function() list(HTTP_HOST = "127.0.0.1:1", HTTP_ORIGIN = "http://127.0.0.1:1")))
shiny::testServer(aplicacao, session = SemToken$new(), {
  stopifnot(session$isClosed(), chamadas$n == 2L)
})
stopifnot(identical(antes, tools::md5sum(list.files(cache_teste, full.names = TRUE))))
unlink(cache_teste, recursive = TRUE)
message("Painel operacional: identidade, ausência, autenticação, leitura e monitoramento conferidos")
