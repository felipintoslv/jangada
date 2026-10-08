# Projeções do núcleo e detalhes permanecem somente leitura.
op_texto <- function(x) {
  if (is.null(x) || !length(x)) return("não registrado")
  if (is.atomic(x) && length(x) == 1) {
    if (is.na(x) || is.numeric(x) && !is.finite(x)) return("não registrado")
    return(as.character(x))
  }
  as.character(jsonlite::toJSON(x, auto_unbox = TRUE, null = "null"))
}

op_tabela <- function(registros, campos) {
  if (!length(registros)) return(data.frame())
  colunas <- lapply(campos, function(campo) vapply(registros, function(r) {
    valor <- r
    for (parte in strsplit(campo, ".", fixed = TRUE)[[1]]) {
      valor <- if (is.list(valor)) valor[[parte]] else NULL
    }
    op_texto(valor)
  }, character(1)))
  names(colunas) <- names(campos)
  as.data.frame(colunas, check.names = FALSE)
}

op_estado <- function(estado) {
  icones <- c(Planejada = "○", Pronta = "●", Executando = "↻", `Em revisão` = "⌕",
              Concluída = "✓", Bloqueada = "Ⅱ", Falhou = "×", Cancelada = "−")
  if (is.null(estado) || !estado %in% names(icones)) return("? Não registrado")
  paste(icones[[estado]], estado)
}

operacional_server <- function(input, output, session, dados) {
  com_busca <- function(d) tabela(d, busca = TRUE)
  nucleo <- reactive(dados()$nucleo)
  output$op_resumo <- renderUI({
    n <- nucleo()
    if (is.null(n$projetos)) return(p("Núcleo não disponível. Atualize a coleta; contagens não registradas."))
    tagList(p("Retrato operacional: ", op_texto(n$data)),
      p(length(n$projetos), " projetos · ", length(n$atividades), " atividades · ",
        length(n$tarefas), " tarefas · ", length(n$sessoes), " sessões"),
      if (length(n$erros)) div(class = "alert alert-warning", paste(unlist(n$erros), collapse = " · ")))
  })
  rotular <- function(registros) {
    lapply(registros, function(r) {
      projeto <- Filter(function(p) identical(p$id, r$projeto), nucleo()$projetos)
      r$nome_projeto <- if (length(projeto)) paste(projeto[[1]]$nome, substr(r$projeto, 1, 12)) else r$projeto
      if (!is.null(r$estado)) r$estado_rotulo <- op_estado(r$estado)
      r
    })
  }
  observe({
    n <- nucleo()
    nomes <- vapply(n$projetos, function(p) paste(p$nome, substr(p$id, 1, 12)), character(1))
    ids <- vapply(n$projetos, function(p) p$id, character(1))
    escolhas <- stats::setNames(ids, nomes)
    updateSelectInput(session, "op_projeto", choices = c("Todos" = "", escolhas), selected = isolate(input$op_projeto))
    updateSelectInput(session, "op_p_detalhe", choices = escolhas, selected = isolate(input$op_p_detalhe))
    agentes <- unique(vapply(n$execucoes, function(e) op_texto(e$agente), character(1)))
    updateSelectInput(session, "op_agente", choices = c("Todos" = "", agentes), selected = isolate(input$op_agente))
  })
  output$op_projetos <- DT::renderDT(com_busca(op_tabela(nucleo()$projetos,
    c(Projeto = "nome", Identificador = "id", Caminho = "caminho", Política = "politica"))))
  output$op_projeto_detalhe <- renderText({
    p <- Filter(function(p) identical(p$id, input$op_p_detalhe), nucleo()$projetos)
    atividades <- Filter(function(a) identical(a$projeto, input$op_p_detalhe), nucleo()$atividades)
    as.character(jsonlite::toJSON(list(projeto = p, atividades = atividades), auto_unbox = TRUE, pretty = TRUE, null = "null"))
  })
  atividades <- reactive({
    n <- nucleo()
    tarefas <- lapply(n$tarefas, function(t) {
      t$tipo <- "Tarefa"
      t$titulo <- t$especificacao$pedido
      t$agente <- t$resultado$delegacao$destino
      t$modelo <- t$resultado$delegacao$modelo
      t$prioridade <- t$especificacao$prioridade
      t$chave <- paste("tarefa", t$projeto, t$id, sep = "|")
      t
    })
    sessoes <- lapply(n$sessoes, function(s) {
      s$tipo <- "Sessão"
      s$id <- s$sessao
      s$titulo <- s$tarefa
      s$chave <- paste("sessao", s$projeto, s$id, sep = "|")
      s
    })
    r <- c(tarefas, sessoes)
    if (length(input$op_projeto) && nzchar(input$op_projeto)) r <- Filter(function(t) identical(t$projeto, input$op_projeto), r)
    if (length(input$op_estado) && nzchar(input$op_estado)) r <- Filter(function(t) identical(t$estado, input$op_estado), r)
    if (length(input$op_agente) && nzchar(input$op_agente)) r <- Filter(function(t) identical(t$agente, input$op_agente), r)
    if (isTRUE(input$op_filtrar_periodo) && !is.null(input$op_periodo)) r <- Filter(function(t) {
      valor <- t$atualizado
      data <- if (is.numeric(valor)) as.Date(as.POSIXct(valor, origin = "1970-01-01")) else as.Date(substr(if (is.null(valor)) "" else valor, 1, 10), format = "%Y-%m-%d")
      !is.na(data) && data >= input$op_periodo[1] && data <= input$op_periodo[2]
    }, r)
    rotular(r)
  })
  observe({
    r <- atividades()
    escolhas <- stats::setNames(vapply(r, function(t) t$chave, character(1)),
      vapply(r, function(t) paste(t$tipo, t$id, t$nome_projeto), character(1)))
    updateSelectInput(session, "op_detalhe", choices = escolhas, selected = isolate(input$op_detalhe))
  })
  output$op_atividades <- DT::renderDT(com_busca(op_tabela(atividades(),
    c(Origem = "tipo", Estado = "estado_rotulo", Título = "titulo", Projeto = "nome_projeto",
      Atividade = "atividade", Agente = "agente", Modelo = "modelo", Prioridade = "prioridade", Atualizado = "atualizado"))))
  output$op_por_projeto <- DT::renderDT(com_busca(op_tabela(rotular(nucleo()$atividades),
    c(Estado = "estado_rotulo", Projeto = "nome_projeto", Atividade = "titulo", Objetivo = "objetivo", Critérios = "criterios"))))
  output$op_detalhes <- renderText({
    r <- Filter(function(t) identical(t$chave, input$op_detalhe), atividades())
    if (!length(r)) return("Selecione uma tarefa ou sessão.")
    t <- r[[1]]
    vinculos <- lapply(c("execucoes", "revisoes", "eventos"), function(campo) Filter(function(e) {
      identical(e$projeto, t$projeto) && (identical(e$tarefa, t$id) || identical(e$sessao, t$id))
    }, nucleo()[[campo]]))
    names(vinculos) <- c("execucoes", "revisoes", "eventos")
    as.character(jsonlite::toJSON(c(list(item = t), vinculos), auto_unbox = TRUE, pretty = TRUE, null = "null"))
  })
  output$op_comandos <- renderText({
    r <- Filter(function(t) identical(t$chave, input$op_detalhe), atividades())
    if (!length(r) || r[[1]]$tipo != "Tarefa") return("Sessões: use Abrir sessão ou Conferir e integrar na Central Qt.")
    t <- r[[1]]
    p <- Filter(function(p) identical(p$id, t$projeto), nucleo()$projetos)
    if (!length(p) || is.null(p[[1]]$caminho)) return("Caminho não registrado; consulte a Central Qt.")
    acoes <- switch(t$status, QUEUED = c("pausar", "cancelar"), PAUSED = c("retomar", "cancelar"),
      REVIEW_REQUIRED = "revisar --parecer PARECER --aprovar OU --reprovar", REVISION_REQUIRED = "repetir",
      WAITING_QUOTA = c("retomar", "cancelar"), WAITING_PROVIDER = c("retomar", "cancelar"), character())
    paste(vapply(acoes, function(a) paste("jangada-task --projeto", shQuote(p[[1]]$caminho), shQuote(t$id), a), character(1)), collapse = "\n")
  })
  output$op_agentes <- DT::renderDT(com_busca(op_tabela(nucleo()$perfis,
    c(Perfil = "nome", Descrição = "descricao", Função = "funcao", Executor = "executor", Modelo = "modelo", Permissões = "permissoes"))))
  output$op_execucoes <- DT::renderDT(com_busca(op_tabela(rotular(nucleo()$execucoes),
    c(Execução = "id", Projeto = "nome_projeto", Tarefa = "tarefa", Sessão = "sessao", Função = "funcao",
      Agente = "agente", Modelo = "modelo", Estado = "status", Início = "inicio", Fim = "fim",
      `Chamadas medidas` = "chamadas", `Segundos medidos` = "segundos", Roteamento = "roteamento"))))
  output$op_provedores <- DT::renderDT({
    r <- lapply(nucleo()$provedores, function(p) {
      observacoes <- Filter(function(s) {
        id <- switch(s$id, local = "ollama", `codex-economico` = "codex", `codex-principal` = "codex", s$id)
        identical(id, p$id)
      }, dados()$orquestracao$provedores)
      p$observacao <- if (length(observacoes)) observacoes else NULL
      p
    })
    com_busca(op_tabela(r, c(Provedor = "nome", Cadastro = "id", Tipo = "tipo", Instalado = "instalado", Funções = "funcoes",
      `Modelo de revisão` = "modelo_revisor", `Última observação` = "observacao")))
  })
  output$op_revisoes <- DT::renderDT(com_busca(op_tabela(rotular(nucleo()$revisoes),
    c(Projeto = "nome_projeto", Tarefa = "tarefa", Decisão = "status", Revisor = "revisor",
      Modelo = "modelo", Independência = "independente", Critérios = "criterios_aceite", Artefato = "artefato_sha256", Parecer = "parecer"))))
  output$op_pendentes <- DT::renderDT(com_busca(op_tabela(rotular(Filter(function(t) t$estado == "Em revisão", nucleo()$tarefas)),
    c(Projeto = "nome_projeto", Tarefa = "id", Critérios = "especificacao.criterios_aceite", Motivo = "motivo", Artefato = "hash_artefato"))))
  output$op_validacoes <- DT::renderDT({
    v <- dados()$validacoes
    linhas <- lapply(seq_len(nrow(v)), function(i) as.list(v[i, , drop = FALSE]))
    com_busca(op_tabela(linhas, c(Sessão = "rotulo", Projeto = "projeto", Execução = "execucao", Origem = "origem",
      Data = "data", Resultado = "resultado", Autor = "autor", Revisor = "revisor", Modelo = "modelo")))
  })
  output$op_historico <- DT::renderDT(com_busca(op_tabela(rotular(nucleo()$eventos),
    c(Projeto = "nome_projeto", Tarefa = "tarefa", Data = "data", Evento = "evento", Dados = "dados"))))
  output$op_configuracao <- renderText(as.character(jsonlite::toJSON(nucleo()$configuracao,
    auto_unbox = TRUE, pretty = TRUE, null = "null")))
  cpu_anterior <- reactiveVal(NULL)
  output$op_monitoramento <- renderText({
    req(identical(input$secao, "Monitoramento"))
    invalidateLater(5000, session)
    programa <- file.path(pasta_app, "../nucleo/monitoramento.py")
    resposta <- tryCatch(system2("python3", shQuote(programa), stdout = TRUE, stderr = FALSE),
                         error = function(e) character())
    if (!length(resposta) || !is.null(attr(resposta, "status"))) return("Medições indisponíveis.")
    m <- tryCatch(jsonlite::fromJSON(paste(resposta, collapse = "\n"), simplifyVector = FALSE),
                  error = function(e) NULL)
    if (is.null(m)) return("Medições inválidas.")
    anterior <- isolate(cpu_anterior())
    cpu_anterior(m$cpu_ticks)
    m["cpu_percentual_medido"] <- list(NULL)
    if (!is.null(anterior) && !is.null(m$cpu_ticks)) {
      total <- m$cpu_ticks$total - anterior$total
      ocioso <- m$cpu_ticks$ocioso - anterior$ocioso
      if (total > 0 && ocioso >= 0 && ocioso <= total) m$cpu_percentual_medido <- 100 * (1 - ocioso / total)
    }
    m$cpu_ticks <- NULL
    as.character(jsonlite::toJSON(m, auto_unbox = TRUE, pretty = TRUE, null = "null"))
  })
}
