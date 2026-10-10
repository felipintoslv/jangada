# Dados sintéticos conferem identidade, leitura e monitoramento após autenticação.
cache_teste <- tempfile("painel-operacional-")
dir.create(cache_teste)
ids <- c(strrep("a", 64), strrep("b", 64))
projetos <- lapply(ids, function(id) list(id = id, nome = "Mesmo nome", caminho = paste0("/", id), politica = list()))
tarefas <- lapply(seq_along(ids), function(i) list(id = "T1", projeto = ids[i], estado = "Pronta", status = "QUEUED",
  atualizado = as.numeric(Sys.time()), especificacao = list(pedido = paste("Fonte", LETTERS[i]), dependencias = list("Anterior"))))
tarefas <- c(tarefas, list(list(id = "T3", projeto = ids[1], especificacao = list()),
  list(id = "T4", projeto = ids[1], estado = "Em revisão", especificacao = list(criterios_aceite = "Critério pendente"))))
tarefas[[1]]$resultado <- list(delegacao = list(destino = "codex-economico"))
sessoes <- list(list(sessao = "sessao-codex", projeto = ids[1], estado = "Executando",
                     agente = "codex --model modelo", tarefa = "Pedido da sessão"))
n <- list(projetos = projetos, atividades = list(list(projeto = ids[1], titulo = "Atividade de exemplo")), tarefas = tarefas, sessoes = sessoes, execucoes = list(list(agente = "codex", projeto = ids[1], tarefa = "T1", id = "Execução vinculada")),
  configuracao = list(arquivo = "/config/jangada.conf", valores = list(
    list(chave = "VAZIO", valor = ""), list(chave = "NULO", valor = NULL),
    list(chave = "PREENCHIDO", valor = "componentes"))),
  revisoes = list(), eventos = list(), provedores = list(), perfis = list(), erros = list(), data = "2026-10-08T10:00:00Z")
jsonlite::write_json(n, file.path(cache_teste, "nucleo.json"), auto_unbox = TRUE)
jsonlite::write_json(list(), file.path(cache_teste, "coleta.json"))
options(jangada.painel.cache = cache_teste, jangada.painel.chave = file.path(cache_teste, "ausente"))
# O app roda de uma cópia fora do jangada: visual, logo e monitoramento vêm
# do JANGADA_PATH, não do getwd().
raiz_teste <- getwd()
Sys.setenv(JANGADA_PATH = raiz_teste)
copia_app <- file.path(cache_teste, "fora")
dir.create(copia_app)
file.copy("default/painel", copia_app, recursive = TRUE)
aplicacao <- shiny::shinyAppDir(file.path(copia_app, "painel"))
ambiente <- environment(aplicacao$serverFuncSource())
stopifnot(grepl("marca-jangada", ambiente$marca, fixed = TRUE),
          length(ambiente$cores) > 0L)
jsonlite::write_json(list(projetos = "inválido"), file.path(cache_teste, "nucleo.json"))
stopifnot(length(ambiente$carregar_cache(cache_teste)$nucleo$erros) == 1L)
jsonlite::write_json(n, file.path(cache_teste, "nucleo.json"), auto_unbox = TRUE)
html <- as.character(ambiente$ui)
secoes <- c("Visão Geral", "Projetos", "Central de Atividades", "Central de Agentes", "Modelos e Provedores",
            "Central de Revisão", "Monitoramento", "Histórico e Artefatos", "Configurações", "Indicadores")
stopifnot(all(vapply(secoes, function(s) grepl(s, html, fixed = TRUE), logical(1))))
stopifnot(grepl('id="painel"', html, fixed = TRUE),
  grepl('id="secao_operacional"', html, fixed = TRUE),
  grepl('id="secao_indicadores"', html, fixed = TRUE))
abas <- function(id) {
  barra <- strsplit(strsplit(html, paste0('id="', id, '"'), fixed = TRUE)[[1]][2], "</ul>", fixed = TRUE)[[1]][1]
  sum(gregexpr("data-value=", barra, fixed = TRUE)[[1]] > 0)
}
stopifnot(abas("painel") == 2L, abas("secao_operacional") == 9L, abas("secao_indicadores") == 6L)
seguro <- as.character(ambiente$op_registro(list(pedido = "<script>alert(1)</script>")))
stopifnot(!grepl("<script>", seguro, fixed = TRUE), grepl("&lt;script&gt;", seguro, fixed = TRUE))
chamadas <- new.env()
chamadas$n <- 0L
ambiente$updateSelectInput <- function(session, inputId, ...) {
  if (identical(inputId, "op_agente")) chamadas$agentes <- list(...)$choices
  shiny::updateSelectInput(session, inputId, ...)
}
tabela_original <- ambiente$tabela
ambiente$tabela <- function(d, ...) {
  if (identical(names(d), c("Projeto", "Tarefa", "Critérios", "Motivo", "Artefato"))) chamadas$pendentes <- d
  tabela_original(d, ...)
}
ambiente$system2 <- function(comando, argumentos, ...) {
  chamadas$n <- chamadas$n + 1L
  chamadas$programa <- argumentos
  jsonlite::toJSON(list(data = "2026-10-08T10:00:00Z", cpu_ticks = list(total = chamadas$n * 100, ocioso = chamadas$n * 20),
    memoria_bytes = list(total = 30.5 * 1024^3, usada = 9.2 * 1024^3),
    gpu = list(list(indice = 0, uso_percentual_medido = 24, memoria_usada_mib = 1285, memoria_total_mib = 8188)), modelos_carregados = list(), erros = list()), auto_unbox = TRUE, null = "null")
}
antes <- tools::md5sum(list.files(cache_teste, full.names = TRUE, recursive = TRUE))
shiny::testServer(aplicacao, {
  session$setInputs(painel = "Operacional", secao_operacional = "Projetos", op_projeto = ids[1], op_detalhe = paste("tarefa", ids[2], "T1", sep = "|"))
  stopifnot(grepl("Selecione", output$op_detalhes$html), chamadas$n == 0L)
  session$setInputs(op_detalhe = paste("tarefa", ids[1], "T1", sep = "|"))
  stopifnot(grepl("Fonte A", output$op_detalhes$html), !grepl("Fonte B", output$op_detalhes$html),
    grepl("<table", output$op_detalhes$html, fixed = TRUE),
    grepl("<details>", output$op_detalhes$html, fixed = TRUE),
    grepl("dependencias</h5>", output$op_detalhes$html, fixed = TRUE),
    grepl("Anterior</td>", output$op_detalhes$html, fixed = TRUE),
    grepl("Execução vinculada</td>", output$op_detalhes$html, fixed = TRUE))
  session$setInputs(op_p_detalhe = ids[1])
  stopifnot(grepl("<table", output$op_projeto_detalhe$html, fixed = TRUE),
    grepl("Atividades", output$op_projeto_detalhe$html),
    grepl("Atividade de exemplo</td>", output$op_projeto_detalhe$html, fixed = TRUE))
  configuracao <- output$op_configuracao$html
  stopifnot(grepl("/config/jangada.conf", configuracao, fixed = TRUE),
    grepl("Chave", configuracao), grepl("Valor", configuracao), grepl("não definido", configuracao),
    !grepl("<pre", configuracao, fixed = TRUE))
  stopifnot(grepl("f", jsonlite::fromJSON(output$op_historico)$x$options$dom, fixed = TRUE))
  stopifnot(grepl(ids[1], output$op_detalhes$html, fixed = TRUE))
  invisible(output$op_pendentes)
  stopifnot(identical(chamadas$pendentes$Tarefa, "T4"))
  session$setInputs(op_projeto = ids[2], op_detalhe = paste("tarefa", ids[2], "T1", sep = "|"))
  stopifnot(grepl("Fonte B", output$op_detalhes$html), !grepl("Fonte A", output$op_detalhes$html))
  stopifnot(all(c("codex-economico", "codex --model modelo") %in% chamadas$agentes))
  stopifnot(!"codex" %in% chamadas$agentes)
  session$setInputs(op_projeto = ids[1], op_agente = "codex-economico",
                    op_detalhe = paste("tarefa", ids[1], "T1", sep = "|"))
  stopifnot(grepl("Fonte A", output$op_detalhes$html))
  session$setInputs(op_agente = "codex --model modelo",
                    op_detalhe = paste("sessao", ids[1], "sessao-codex", sep = "|"))
  stopifnot(grepl("Pedido da sessão", output$op_detalhes$html))
  session$setInputs(op_agente = "")
  session$setInputs(painel = "Operacional", secao_operacional = "Monitoramento")
  primeira <- output$op_monitoramento$html
  monitoramento <- file.path(raiz_teste, "default/nucleo/monitoramento.py")
  stopifnot(identical(chamadas$programa, shQuote(monitoramento)),
            file.exists(monitoramento))
  stopifnot(chamadas$n == 1L, grepl("não registrado", primeira),
    grepl("9,2 de 30,5 GiB", primeira), grepl("1.285 de 8.188 MiB", primeira),
    grepl("24%", primeira), grepl("nenhum", primeira), !grepl("<pre", primeira, fixed = TRUE))
  session$elapse(5000)
  segunda <- output$op_monitoramento$html
  stopifnot(chamadas$n == 2L, grepl("80,0%", segunda))
  session$setInputs(painel = "Indicadores")
  session$elapse(10000)
  stopifnot(chamadas$n == 2L)
  session$setInputs(painel = "Operacional", secao_operacional = "Projetos")
  session$elapse(10000)
  stopifnot(chamadas$n == 2L)
})
SemToken <- R6::R6Class("SessaoSemToken", inherit = shiny::MockShinySession, portable = FALSE, lock_objects = FALSE,
  parent_env = asNamespace("shiny"),
  active = list(request = function() list(HTTP_HOST = "127.0.0.1:1", HTTP_ORIGIN = "http://127.0.0.1:1")))
shiny::testServer(aplicacao, session = SemToken$new(), {
  stopifnot(session$isClosed(), chamadas$n == 2L)
})
stopifnot(identical(antes, tools::md5sum(list.files(cache_teste, full.names = TRUE, recursive = TRUE))))
unlink(cache_teste, recursive = TRUE)
message("Painel operacional: identidade, ausência, autenticação, leitura e monitoramento conferidos")
