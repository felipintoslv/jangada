# Painel de indicadores do jangada. Só lê o cache em Parquet que o
# coletor.py grava (padrão ~/.local/state/jangada/painel) e recarrega quando
# o coleta.json muda. Sobe pelo jangada-painel, em 127.0.0.1; nenhum recurso
# vem da rede.

library(shiny)
library(bslib)

pasta_app <- getwd()
source(file.path(pasta_app, "indicadores.R"), local = TRUE)

cache <- getOption("jangada.painel.cache",
  file.path(Sys.getenv("XDG_STATE_HOME", file.path(Sys.getenv("HOME"), ".local/state")), "jangada/painel"))

# Cores do matugen, as mesmas da barra. O arquivo traz a paleta escura; no
# modo claro, a cor de destaque é a do texto sobre a primária.
cores <- local({
  padrao <- c(superficie = "#141311", texto = "#e6e2de", texto_suave = "#cdc6ba",
              primaria = "#e6d9be", texto_primario = "#37301d", atencao = "#dbd8e9")
  arq <- file.path(Sys.getenv("XDG_CONFIG_HOME", file.path(Sys.getenv("HOME"), ".config")),
                   "jangada/waybar/cores.css")
  if (file.exists(arq)) {
    l <- regmatches(readLines(arq, warn = FALSE),
                    regexec("^@define-color ([a-z_]+) (#[0-9a-fA-F]{6})", readLines(arq, warn = FALSE)))
    for (x in l) if (length(x) == 3) padrao[x[2]] <- x[3]
  }
  padrao
})

tema <- bs_theme(
  version = 5, primary = cores[["texto_primario"]],
  base_font = font_collection("Inter", "system-ui", "sans-serif"),
  code_font = font_collection("JetBrains Mono", "monospace")
) |>
  bs_add_rules(sprintf("
    [data-bs-theme=dark] {
      --bs-body-bg: %s; --bs-body-color: %s; --bs-secondary-color: %s;
      --bs-primary: %s; --bs-primary-rgb: %s; --bs-link-color: %s;
    }
    .aviso-pouco { color: var(--bs-warning); font-weight: 600; }
    .cobertura { font-size: .8rem; color: var(--bs-secondary-color); }
    .bslib-value-box .value-box-title { font-size: .85rem; }
    .bslib-value-box.default .value-box-showcase > svg.bi { fill: var(--bs-primary) !important; }
    .dataTables_wrapper { font-size: .85rem; }",
    cores[["superficie"]], cores[["texto"]], cores[["texto_suave"]], cores[["primaria"]],
    paste(grDevices::col2rgb(cores[["primaria"]]), collapse = ","), cores[["primaria"]]))

# Gráficos sem barra de ferramentas e com fundo transparente, para seguir o
# tema. A legenda fica acima do gráfico, longe do título do eixo; as datas
# saem em português.
pl <- function(p, x = "", y = "") {
  p |>
    plotly::layout(paper_bgcolor = "rgba(0,0,0,0)", plot_bgcolor = "rgba(0,0,0,0)",
                   font = list(color = "#888"), xaxis = list(title = list(text = x)),
                   yaxis = list(title = list(text = y)),
                   separators = ",.", legend = list(orientation = "h", x = 0, y = 1.15)) |>
    plotly::config(displayModeBar = FALSE, locale = "pt-BR")
}

# Gráfico vazio: só o aviso, sem eixos.
vazio <- function() {
  ax <- list(visible = FALSE)
  pl(plotly::plot_ly(type = "scatter", mode = "markers")) |>
    plotly::layout(xaxis = ax, yaxis = ax, annotations = list(list(
      text = "sem dado no período", showarrow = FALSE, xref = "paper", yref = "paper", x = .5, y = .5,
      font = list(size = 14))))
}

# Paginação e contagem só quando a tabela passa de uma página. Sem dado, uma
# coluna vazia leva o aviso "sem dado".
tabela <- function(d, ...) {
  if (!ncol(d)) d <- data.frame(` ` = character(), check.names = FALSE)
  dom <- if (nrow(d) > 10) "tip" else "t"
  DT::datatable(d, rownames = FALSE, options = list(pageLength = 10, dom = dom, scrollX = TRUE,
    language = list(info = "_START_ a _END_ de _TOTAL_", infoEmpty = "nada", emptyTable = "sem dado",
                    paginate = list(previous = "anterior", `next` = "próxima"))), ...)
}

cobertura_ui <- function(cob) {
  div(class = "cobertura", cob$periodo, " · ", cob$n, " observação(ões)",
      if (cob$pouco) span(class = "aviso-pouco", " · pouco dado"))
}

milhar <- function(x) format(round(x), big.mark = ".", decimal.mark = ",", scientific = FALSE, trim = TRUE)
curto <- function(n) {
  if (is.na(n)) return("-")
  v <- function(x) format(round(x, 1), nsmall = 1, decimal.mark = ",")
  if (n >= 1e9) paste(v(n / 1e9), "bi") else if (n >= 1e6) paste(v(n / 1e6), "mi")
  else if (n >= 1e3) sprintf("%.0f mil", n / 1e3) else as.character(round(n))
}

cartao <- function(titulo, ..., cob = NULL) {
  card(full_screen = TRUE, card_header(titulo), card_body(...), if (!is.null(cob)) card_footer(cob))
}

filtros <- sidebar(
  width = 260,
  dateRangeInput("periodo", "Período", start = Sys.Date() - 30, end = Sys.Date(),
                 language = "pt-BR", separator = "a", format = "dd/mm/yyyy"),
  selectizeInput("projeto", "Projeto", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  selectizeInput("agente", "Agente ou perfil", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  selectizeInput("par", "Par autor → revisor", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  uiOutput("coleta")
)

ui <- page_navbar(
  title = "Indicadores do jangada", theme = tema, fillable = FALSE,
  window_title = "Indicadores do jangada",
  sidebar = filtros,
  nav_panel("Revisão", icon = bsicons::bs_icon("check2-square"),
    layout_column_wrap(width = 1 / 4, fill = FALSE,
      value_box("Aprovação na 1ª rodada", textOutput("vb_primeira"), showcase = bsicons::bs_icon("check2-circle"),
                p(textOutput("vb_primeira_n", inline = TRUE))),
      value_box("Rodadas até aprovar", textOutput("vb_rodadas"), showcase = bsicons::bs_icon("arrow-repeat"),
                p("média; máximo ", textOutput("vb_rodadas_max", inline = TRUE))),
      value_box("No limite de rodadas", textOutput("vb_limite"), showcase = bsicons::bs_icon("exclamation-triangle"),
                p("tarefa ambígua ou modelos em desacordo")),
      value_box("Itens por REVISAR", textOutput("vb_itens"), showcase = bsicons::bs_icon("list-check"),
                p("revisão leva ", textOutput("vb_segundos", inline = TRUE)))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Por projeto", DT::DTOutput("a_projeto"), cob = uiOutput("a_cob")),
      cartao("Por par autor → revisor", DT::DTOutput("a_par"),
             cob = div(class = "cobertura", "* pouco dado: menos de 10 aprovadas. Sem registro: validações antigas, de antes do validar.jsonl."))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Entregas no limite de rodadas", DT::DTOutput("a_limite")),
      cartao("Tamanho do diff: aprovadas de primeira e reprovadas", plotly::plotlyOutput("a_diff", height = 300),
             cob = uiOutput("a_diff_cob"))
    )
  ),
  nav_panel("Consumo", icon = bsicons::bs_icon("cpu"),
    layout_column_wrap(width = 1 / 4, fill = FALSE,
      value_box("Tokens de saída", textOutput("vb_saida"), showcase = bsicons::bs_icon("box-arrow-right"),
                p("raciocínio: ", textOutput("vb_raciocinio", inline = TRUE))),
      value_box("Cache criado", textOutput("vb_criado"), showcase = bsicons::bs_icon("database-add")),
      value_box("Cache lido", textOutput("vb_lido"), showcase = bsicons::bs_icon("database"),
                p(textOutput("vb_lido_pct", inline = TRUE), " do total")),
      value_box("Blocos de 5h perto do limite", textOutput("vb_blocos"), showcase = bsicons::bs_icon("hourglass-split"),
                p(textOutput("vb_blocos_n", inline = TRUE)))
    ),
    cartao("Tokens por dia, sem o cache lido", plotly::plotlyOutput("b_dia", height = 320), cob = uiOutput("b_cob")),
    layout_columns(col_widths = c(6, 6),
      cartao("Cache lido por dia", plotly::plotlyOutput("b_lido", height = 260)),
      cartao("Blocos de 5 horas por semana", plotly::plotlyOutput("b_blocos", height = 260),
             p(class = "cobertura", "Os registros não trazem o limite do plano: perto do limite é um bloco com 80% ou mais da saída do maior bloco observado."))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Por projeto", DT::DTOutput("b_projeto")),
      cartao("Por modelo", DT::DTOutput("b_modelo"))
    ),
    cartao("Tokens por entrega aprovada", DT::DTOutput("b_entrega"), cob = uiOutput("b_entrega_cob")),
    p(class = "cobertura", "Só o Claude Code: o agy não grava contagem de tokens legível (docs/registros.md).")
  ),
  nav_panel("Tempo e atenção", icon = bsicons::bs_icon("clock-history"),
    uiOutput("c_aviso"),
    layout_column_wrap(width = 1 / 3, fill = FALSE,
      value_box("Em aguardando, por dia", textOutput("vb_aguardando"), showcase = bsicons::bs_icon("hourglass")),
      value_box("Trocas de foco, por dia", textOutput("vb_foco"), showcase = bsicons::bs_icon("arrow-left-right")),
      value_box("Sessões sem entrega há mais de 3 dias", textOutput("vb_paradas"), showcase = bsicons::bs_icon("pause-circle"))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Horas em aguardando por dia", plotly::plotlyOutput("c_aguardando", height = 280), cob = uiOutput("c_cob")),
      cartao("Sessões simultâneas por hora", plotly::plotlyOutput("c_simult", height = 280))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Trocas de foco por dia", plotly::plotlyOutput("c_foco", height = 260)),
      cartao("Sessões abertas sem entrega aprovada há mais de 3 dias", DT::DTOutput("c_paradas"))
    )
  ),
  nav_spacer(),
  nav_item(input_dark_mode(id = "modo", mode = "dark"))
)

server <- function(input, output, session) {
  dados <- reactivePoll(3000, session,
    checkFunc = function() file.mtime(file.path(cache, "coleta.json")),
    valueFunc = function() carregar_cache(cache))

  observe({
    d <- dados()
    projetos <- sort(unique(c(d$validacoes$projeto, d$mensagens$projeto, d$eventos$projeto)))
    agentes <- sort(unique(c(d$validacoes$autor, d$eventos$agente, d$sessoes$agente)))
    ent <- entregas(d$validacoes)
    updateSelectizeInput(session, "projeto", choices = projetos[nzchar(projetos)], selected = isolate(input$projeto))
    updateSelectizeInput(session, "agente", choices = agentes[nzchar(agentes)], selected = isolate(input$agente))
    updateSelectizeInput(session, "par", choices = sort(unique(ent$par)), selected = isolate(input$par))
  })

  output$coleta <- renderUI({
    c <- dados()$coleta
    div(class = "cobertura", "Cache de ", if (length(c$data)) format(as.POSIXct(substr(c$data, 1, 19), format = "%Y-%m-%dT%H:%M:%S"), "%d/%m %H:%M") else "-",
        br(), "Clique no módulo da barra para atualizar.")
  })

  no_periodo <- function(d, col = "data") {
    if (!nrow(d)) return(d)
    dia <- as.Date(format(d[[col]], "%Y-%m-%d"))
    d[!is.na(dia) & dia >= input$periodo[1] & dia <= input$periodo[2], , drop = FALSE]
  }
  filtrar <- function(d, projeto = "projeto", agente = NULL) {
    if (length(input$projeto) && projeto %in% names(d)) d <- d[d[[projeto]] %in% input$projeto, , drop = FALSE]
    if (length(input$agente) && !is.null(agente)) d <- d[d[[agente]] %in% input$agente, , drop = FALSE]
    d
  }

  # A. Revisão
  # Tabela estreita: o aviso de pouco dado vira asterisco nas aprovadas.
  tabela_resumo <- function(e, por, rotulo) {
    r <- resumo_aprovacao(e, por)
    if (!nrow(r)) return(tabela(data.frame()))
    r$aprovadas <- paste0(r$aprovadas, ifelse(nzchar(r$aviso), "*", ""))
    r$rodadas <- ifelse(is.na(r$rodadas_media), "-",
                        paste0(format(r$rodadas_media, decimal.mark = ","), " / ", r$rodadas_max))
    tabela(setNames(r[c("grupo", "entregas", "aprovadas", "primeira_pct", "rodadas", "no_limite")],
                    c(rotulo, "entregas", "aprovadas", "1ª rodada (%)", "rodadas (média / máx.)", "no limite")))
  }
  ent <- reactive({
    e <- entregas(dados()$validacoes)
    e <- filtrar(no_periodo(e, "fim"), agente = "autor")
    if (length(input$par)) e <- e[e$par %in% input$par, ]
    e
  })
  rodadas <- reactive({
    v <- filtrar(no_periodo(dados()$validacoes), agente = "autor")
    v[v$entrega %in% ent()$entrega, ]
  })
  output$vb_primeira <- renderText({
    ap <- ent()[ent()$aprovada, ]
    if (nrow(ap)) paste0(round(100 * mean(ap$primeira)), "%") else "-"
  })
  output$vb_primeira_n <- renderText({
    n <- sum(ent()$aprovada)
    paste0(n, " entrega(s) aprovada(s)", if (n < POUCO_DADO) " · pouco dado" else "")
  })
  output$vb_rodadas <- renderText({
    ap <- ent()[ent()$aprovada, ]
    if (nrow(ap)) format(round(mean(ap$rodadas), 1), decimal.mark = ",") else "-"
  })
  output$vb_rodadas_max <- renderText({
    ap <- ent()[ent()$aprovada, ]
    if (nrow(ap)) max(ap$rodadas) else "-"
  })
  output$vb_limite <- renderText(sum(ent()$limite))
  output$vb_itens <- renderText({
    r <- rodadas()[rodadas()$resultado == "revisar", ]
    if (nrow(r)) format(round(mean(r$itens, na.rm = TRUE), 1), decimal.mark = ",") else "-"
  })
  output$vb_segundos <- renderText({
    r <- rodadas()[rodadas()$etapa == "revisor" & !is.na(rodadas()$segundos), ]
    if (nrow(r)) paste0(format(round(mean(r$segundos) / 60, 1), decimal.mark = ","), " min em média") else "- (sem registro)"
  })
  output$a_cob <- renderUI(cobertura_ui(cobertura(ent()$fim[ent()$aprovada])))
  output$a_projeto <- DT::renderDT(tabela_resumo(ent(), "projeto", "projeto"))
  output$a_par <- DT::renderDT(tabela_resumo(ent(), "par", "autor → revisor"))
  output$a_limite <- DT::renderDT({
    e <- ent()[ent()$limite, c("entrega", "projeto", "par", "fim", "reprovacoes")]
    e$fim <- format(e$fim, "%d/%m %H:%M")
    tabela(setNames(e, c("entrega", "projeto", "autor → revisor", "última rodada", "REVISAR")))
  })
  output$a_diff <- plotly::renderPlotly({
    e <- ent()[ent()$aprovada & !is.na(ent()$diff), ]
    e$grupo <- ifelse(e$primeira, "aprovada de primeira", "reprovada antes")
    if (!nrow(e)) return(vazio())
    pl(plotly::plot_ly(e, x = ~grupo, y = ~diff, type = "box", boxpoints = "all", color = ~grupo,
                       text = ~entrega, colors = c(cores[["primaria"]], cores[["atencao"]])) |>
         plotly::layout(showlegend = FALSE),
       "", "linhas (+ e -)")
  })
  output$a_diff_cob <- renderUI(cobertura_ui(cobertura(ent()$fim[ent()$aprovada & !is.na(ent()$diff)])))

  # B. Consumo
  msg <- reactive(filtrar(no_periodo(dados()$mensagens[dados()$mensagens$modelo != "<synthetic>", ])))
  soma <- function(col) sum(msg()[[col]], na.rm = TRUE)
  output$vb_saida <- renderText(curto(soma("saida")))
  output$vb_raciocinio <- renderText(curto(soma("raciocinio")))
  output$vb_criado <- renderText(curto(soma("cache_criado")))
  output$vb_lido <- renderText(curto(soma("cache_lido")))
  output$vb_lido_pct <- renderText({
    t <- soma("entrada") + soma("saida") + soma("cache_criado") + soma("cache_lido")
    if (t > 0) paste0(round(100 * soma("cache_lido") / t), "%") else "-"
  })
  blocos <- reactive(no_periodo(blocos_5h(filtrar(dados()$mensagens)), "inicio"))
  output$vb_blocos <- renderText(sum(blocos()$perto_limite))
  output$vb_blocos_n <- renderText(paste(nrow(blocos()), "bloco(s) no período"))
  output$b_cob <- renderUI(cobertura_ui(cobertura(msg()$data)))
  output$b_dia <- plotly::renderPlotly({
    m <- msg()
    if (!nrow(m)) return(vazio())
    m$raciocinio[is.na(m$raciocinio)] <- 0
    # A saída inclui o raciocínio; a série "saída" mostra só o texto.
    m$saida_texto <- pmax(m$saida - m$raciocinio, 0)
    a <- aggregate(m[c("entrada", "saida_texto", "raciocinio", "cache_criado")], list(dia = as.Date(m$dia)), sum)
    p <- plotly::plot_ly(a, x = ~dia)
    for (s in list(c("cache_criado", "cache criado", cores[["atencao"]]), c("saida_texto", "saída", cores[["primaria"]]),
                   c("raciocinio", "raciocínio", "#b08968"), c("entrada", "entrada nova", "#888888"))) {
      p <- plotly::add_bars(p, y = a[[s[1]]], name = s[2], marker = list(color = s[3]))
    }
    pl(plotly::layout(p, barmode = "stack"), "", "tokens")
  })
  output$b_lido <- plotly::renderPlotly({
    m <- msg()
    if (!nrow(m)) return(vazio())
    a <- aggregate(m["cache_lido"], list(dia = as.Date(m$dia)), sum)
    pl(plotly::plot_ly(a, x = ~dia, y = ~cache_lido, type = "bar", marker = list(color = "#888888"), name = "cache lido"),
       "", "tokens")
  })
  output$b_blocos <- plotly::renderPlotly({
    b <- blocos()
    if (!nrow(b)) return(vazio())
    a <- aggregate(list(blocos = rep(1, nrow(b)), perto = as.integer(b$perto_limite)), list(semana = b$semana), sum)
    pl(plotly::plot_ly(a, x = ~semana) |>
         plotly::add_bars(y = ~ (blocos - perto), name = "longe do limite", marker = list(color = "#888888")) |>
         plotly::add_bars(y = ~perto, name = "perto do limite", marker = list(color = cores[["atencao"]])) |>
         plotly::layout(barmode = "stack"), "", "blocos")
  })
  tabela_consumo <- function(por, rotulo) {
    a <- consumo_por(msg(), por)
    if (!nrow(a)) return(tabela(data.frame()))
    a <- a[c(por, "respostas", "saida", "raciocinio", "cache_criado", "entrada", "cache_lido", "lido_pct")]
    for (col in c("saida", "raciocinio", "cache_criado", "entrada", "cache_lido")) a[[col]] <- milhar(a[[col]])
    tabela(setNames(a, c(rotulo, "respostas", "saída", "raciocínio", "cache criado", "entrada nova", "cache lido", "lido (%)")))
  }
  output$b_projeto <- DT::renderDT(tabela_consumo("projeto", "projeto"))
  output$b_modelo <- DT::renderDT(tabela_consumo("modelo", "modelo"))
  tpe <- reactive(tokens_por_entrega(ent(), dados()$mensagens))
  output$b_entrega <- DT::renderDT({
    t <- tpe()
    if (is.null(t) || !nrow(t)) return(tabela(data.frame()))
    t$fim <- format(t$fim, "%d/%m %H:%M")
    t$primeira <- ifelse(t$primeira, "sim", "não")
    for (col in c("saida", "cache_criado", "total")) t[[col]] <- milhar(t[[col]])
    tabela(setNames(t, c("entrega", "projeto", "aprovada em", "de primeira", "respostas", "saída", "cache criado", "total")))
  })
  output$b_entrega_cob <- renderUI({
    t <- tpe()
    cobertura_ui(cobertura(if (is.null(t)) as.POSIXct(character()) else t$fim))
  })

  # C. Tempo e atenção
  ev <- reactive(filtrar(no_periodo(dados()$eventos), agente = "agente"))
  iv <- reactive(intervalos_estado(ev()))
  aguard <- reactive(tempo_por_dia(iv(), "aguardando"))
  output$c_aviso <- renderUI({
    e <- dados()$eventos
    if (nrow(e) < 50) {
      div(class = "alert alert-secondary",
          if (nrow(e)) paste0("Coletando desde ", format(min(e$data), "%d/%m/%Y"), ".")
          else "Ainda sem eventos: o histórico de estados (eventos-agentes.jsonl) começa na primeira sessão depois do jangada-atualizar.",
          " Com pouco dado, os números abaixo ainda não sustentam conclusão.")
    }
  })
  output$vb_aguardando <- renderText({
    a <- aguard()
    if (nrow(a)) paste0(format(round(mean(a$horas), 1), decimal.mark = ","), " h") else "-"
  })
  foco <- reactive({
    f <- ev()[ev()$estado == "foco", ]
    if (!nrow(f)) return(data.frame(dia = as.Date(character()), trocas = integer()))
    a <- aggregate(list(trocas = rep(1L, nrow(f))), list(dia = as.Date(f$dia)), sum)
    a
  })
  output$vb_foco <- renderText(if (nrow(foco())) format(round(mean(foco()$trocas), 1), decimal.mark = ",") else "-")
  paradas <- reactive(filtrar(sessoes_paradas(dados()$sessoes, entregas(dados()$validacoes)), agente = "agente"))
  output$vb_paradas <- renderText(nrow(paradas()))
  output$c_cob <- renderUI(cobertura_ui(cobertura(ev()$data)))
  output$c_aguardando <- plotly::renderPlotly({
    a <- aguard()
    if (!nrow(a)) return(vazio())
    pl(plotly::plot_ly(a, x = ~dia, y = ~horas, type = "bar", marker = list(color = cores[["atencao"]])), "", "horas")
  })
  output$c_simult <- plotly::renderPlotly({
    s <- simultaneas_por_hora(iv())
    if (!nrow(s)) return(vazio())
    pl(plotly::plot_ly(s, x = ~hora, y = ~sessoes, type = "scatter", mode = "lines",
                       line = list(shape = "hv", color = cores[["primaria"]])), "", "sessões")
  })
  output$c_foco <- plotly::renderPlotly({
    if (!nrow(foco())) return(vazio())
    pl(plotly::plot_ly(foco(), x = ~dia, y = ~trocas, type = "bar", marker = list(color = cores[["primaria"]])), "", "trocas")
  })
  output$c_paradas <- DT::renderDT({
    p <- paradas()
    if (!nrow(p)) return(tabela(data.frame()))
    p$desde <- format(p$desde, "%d/%m %H:%M")
    p$ultima_aprovacao <- ifelse(is.na(p$ultima_aprovacao), "nenhuma", format(p$ultima_aprovacao, "%d/%m %H:%M"))
    tabela(setNames(p, c("sessão", "projeto", "agente", "estado", "aberta em", "última aprovação", "dias sem entrega")))
  })
}

shinyApp(ui, server)
