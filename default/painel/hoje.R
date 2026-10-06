# Tela inicial: lê o retrato completo da coleta, sem os filtros analíticos.
hoje_ui <- function(id) {
  ns <- shiny::NS(id)
  bslib::layout_column_wrap(width = 1, fill = FALSE,
    shiny::uiOutput(ns("aviso")),
    p("Retrato de todos os projetos na última coleta. Consumo apenas de hoje; filtros ficam na área avançada."),
    bslib::card(bslib::card_header("Precisa da sua resposta"), shiny::tableOutput(ns("sessoes"))),
    bslib::card(bslib::card_header("Revisões pendentes"), shiny::tableOutput(ns("revisoes"))),
    bslib::card(bslib::card_header("Saúde dos provedores"), shiny::tableOutput(ns("provedores"))),
    bslib::card(bslib::card_header("Consumo de hoje"), shiny::tableOutput(ns("consumo"))),
    bslib::card(bslib::card_header("Sessões sem entrega há mais de três dias"), shiny::tableOutput(ns("paradas")))
  )
}

hoje_server <- function(id, dados) {
  shiny::moduleServer(id, function(input, output, session) {
    hoje_entregas <- reactive(entregas(dados()$validacoes))
    hoje_pendentes <- reactive({
      e <- hoje_entregas()
      e <- e[order(e$fim, decreasing = TRUE), , drop = FALSE]
      e <- e[!duplicated(e$rotulo), , drop = FALSE]
      e[!e$aprovada & e$rotulo %in% dados()$sessoes$sessao, , drop = FALSE]
    })
    fila_pendente <- reactive({
      d <- tabela_lista(dados()$orquestracao$tarefas, c("projeto", "id", "estado"))
      d[d$estado %in% c("REVIEW_REQUIRED", "REVISION_REQUIRED", "WAITING_REVIEWER"), , drop = FALSE]
    })
    output$aviso <- renderUI({
      d <- dados()
      esperando <- sum(d$sessoes$estado == "aguardando", na.rm = TRUE)
      avisos <- unlist(d$orquestracao$erros)
      fontes <- Filter(function(x) identical(x$estado, "erro"), d$fontes)
      div(class = "alert alert-info",
        p(sprintf("Sessões aguardando: %d. Revisões pendentes registradas: %d.",
          esperando, nrow(hoje_pendentes()) + nrow(fila_pendente()))),
        p("Última coleta: ", if (is.null(d$coleta$data)) "não informada" else d$coleta$data),
        if (!length(d$orquestracao$provedores)) p("Sem observações de provedores; disponibilidade desconhecida."),
        if (length(avisos)) p("Coleta incompleta: ", paste(avisos, collapse = "; ")),
        if (length(fontes)) p("Fontes com erro: ", paste(vapply(fontes, function(x) x$fonte, ""), collapse = ", ")))
    })
    output$sessoes <- renderTable({
      s <- dados()$sessoes
      s[s$estado %in% "aguardando", c("sessao", "projeto", "atualizado"), drop = FALSE]
    })
    output$revisoes <- renderTable({
      e <- hoje_pendentes()
      fila <- fila_pendente()
      rbind(data.frame(projeto = e$projeto, tarefa = e$rotulo, origem = rep("Sessão", nrow(e))),
        data.frame(projeto = fila$projeto, tarefa = fila$id, origem = rep("Fila", nrow(fila))))
    })
    output$provedores <- renderTable({
      d <- tabela_lista(dados()$orquestracao$provedores, c("id", "status", "motivo", "atualizado", "valido_ate"))
      d$status <- unname(nomes_provedores[d$status])
      for (campo in c("atualizado", "valido_ate")) {
        instante <- as.numeric(d[[campo]])
        d[[campo]] <- ifelse(is.na(instante) | instante <= 0, "sem observação",
          format(as.POSIXct(instante, origin = "1970-01-01"), "%d/%m %H:%M:%S"))
      }
      setNames(d, c("provedor", "estado na coleta", "motivo", "observado em", "válido até"))
    })
    output$consumo <- renderTable({
      d <- dados()$consumo
      r <- resumo_motores(d[d$dia == as.character(Sys.Date()), , drop = FALSE])
      if (!nrow(r)) return(r)
      setNames(r[c("executor", "origem", "modelo", "entrada", "saida", "registros", "com_saida")],
        c("executor", "origem", "modelo", "entrada", "saída", "registros", "com saída medida"))
    }, na = "Sem medida")
    output$paradas <- renderTable({
      sessoes_paradas(dados()$sessoes, hoje_entregas())
    })
  })
}
