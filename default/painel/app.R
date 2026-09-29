# Painel de indicadores do jangada. Só lê o cache em Parquet que o
# coletor.py grava (padrão ~/.local/state/jangada/painel) e recarrega quando
# o coleta.json muda. Sobe pelo jangada-painel, em 127.0.0.1, e só abre
# sessão com o token do painel-chave na URL; nenhum recurso vem da rede.

library(shiny)
library(bslib)

pasta_app <- getwd()
source(file.path(pasta_app, "indicadores.R"), local = TRUE)

estado <- file.path(Sys.getenv("XDG_STATE_HOME", file.path(Sys.getenv("HOME"), ".local/state")), "jangada")
cache <- getOption("jangada.painel.cache", file.path(estado, "painel"))
chave <- getOption("jangada.painel.chave", file.path(estado, "painel-chave", "token"))

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

# Cores dos grupos dos grafos, na paleta dos outros gráficos.
alerta <- "#e07a5f"
cores_grupos <- c(
  "edição" = cores[["primaria"]], "edição com retrabalho" = alerta, "teste" = cores[["atencao"]],
  "leitura e busca" = "#888888", "shell" = "#b08968", "outra" = "#5f7f8f",
  "sessão" = "#888888", "arquivo" = cores[["primaria"]], "arquivo em várias sessões" = alerta,
  "comum" = cores[["primaria"]], "rara" = "#888888",
  "pasta" = "#888888", "conversa" = "#5f7f8f", "claude" = cores[["primaria"]], "agy" = cores[["atencao"]],
  "delegacao" = "#b08968", "recusa" = alerta)

# Grafo do visNetwork com layout do igraph (sem física, para não tremer) e
# rótulos num cinza legível nos dois modos.
grafo <- function(r) {
  validate(need(!is.null(r), "sem dado no período"))
  grupos <- unique(r$nos$group)
  v <- visNetwork::visNetwork(r$nos, r$arestas, width = "100%") |>
    # Física só até estabilizar: o layout fica compacto e depois para quieto.
    visNetwork::visPhysics(solver = "forceAtlas2Based", stabilization = list(iterations = 400),
                           forceAtlas2Based = list(gravitationalConstant = -60, avoidOverlap = 0.3)) |>
    visNetwork::visEvents(stabilizationIterationsDone = "function() { this.setOptions({physics: false}); }") |>
    visNetwork::visLayout(randomSeed = 1) |>
    visNetwork::visNodes(font = list(color = "#8a8a8a", size = 18), scaling = list(min = 10, max = 40)) |>
    visNetwork::visEdges(color = list(color = "#8888884d", highlight = cores[["primaria"]]),
                         smooth = FALSE, scaling = list(min = 1, max = 8)) |>
    visNetwork::visOptions(highlightNearest = list(enabled = TRUE, degree = 1, hover = TRUE)) |>
    visNetwork::visInteraction(hover = TRUE, tooltipDelay = 100)
  for (g in grupos) {
    cor <- if (g %in% names(cores_grupos)) cores_grupos[[g]] else alerta
    v <- visNetwork::visGroups(v, groupname = g, color = list(background = cor, border = "#777777",
                               highlight = list(background = cor, border = cores[["texto"]])))
  }
  visNetwork::visLegend(v, useGroups = TRUE, position = "right", width = 0.22, zoom = FALSE)
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
             cob = div(class = "cobertura", "* pouco dado: menos de 10 aprovadas. Sem registro: validações antigas, de antes do validar.jsonl. As taxas contam as rodadas registradas pela própria sessão, num arquivo que o agente isolado pode alterar."))
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
  nav_panel("Redes", icon = bsicons::bs_icon("diagram-3"),
    layout_column_wrap(width = 1 / 3, fill = FALSE,
      sliderInput("max_nos", "Nós por grafo (afrouxa a poda)", min = 10, max = 120, value = 40, step = 5),
      sliderInput("peso_min", "Transições: vezes mínimas por aresta", min = 1, max = 10, value = 2),
      sliderInput("limiar", "Capacidades: proximidade mínima", min = 0.2, max = 0.9, value = 0.5, step = 0.05)
    ),
    layout_column_wrap(width = 1 / 3, fill = FALSE,
      value_box("Ciclos de retrabalho", textOutput("vb_ciclos"), showcase = bsicons::bs_icon("arrow-counterclockwise"),
                p(textOutput("vb_ciclos_n", inline = TRUE))),
      value_box("Testes que falharam", textOutput("vb_testes"), showcase = bsicons::bs_icon("bug"),
                p(textOutput("vb_testes_n", inline = TRUE))),
      value_box("Arquivos editados em mais de uma sessão", textOutput("vb_multi"), showcase = bsicons::bs_icon("files"),
                p("risco de conflito entre agentes em paralelo"))
    ),
    layout_columns(col_widths = c(7, 5),
      cartao("Transições entre chamadas de ferramenta", visNetwork::visNetworkOutput("d_transicoes", height = "480px"),
             cob = div(class = "cobertura", "Ciclo de retrabalho: editar um arquivo, os testes falharem e editar o mesmo arquivo de novo. ",
                       "Só conta edição pelas ferramentas Edit e Write: edição por comando (sed, python) não diz o arquivo.")),
      navset_card_underline(title = "Retrabalho", full_screen = TRUE,
        nav_panel("Por projeto", DT::DTOutput("d_ciclos_projeto")),
        nav_panel("Por sessão", DT::DTOutput("d_ciclos_sessao")),
        nav_panel("Arquivos", DT::DTOutput("d_ciclos_arquivo")))
    ),
    layout_columns(col_widths = c(7, 5),
      cartao("Pontos quentes: sessão × arquivo editado", visNetwork::visNetworkOutput("d_quentes", height = "480px")),
      navset_card_underline(title = "Arquivos", full_screen = TRUE,
        nav_panel("Em mais sessões", DT::DTOutput("d_quentes_tab")),
        nav_panel("Com mais REVISAR", DT::DTOutput("d_revisar"),
                  p(class = "cobertura", "O arquivo citado em cada item dos pareceres REVISAR.")))
    ),
    card(full_screen = TRUE,
      card_header("Espaço de ferramentas (exploratório, sem meta)"),
      div(class = "alert alert-secondary",
          "Como no Product Space (Hidalgo e Hausmann): um projeto tem vantagem numa capacidade quando a usa mais que a média ",
          "(RCA >= 1); duas capacidades são próximas quando os mesmos projetos têm vantagem nas duas. ",
          "Típico: o quanto o uso do projeto se parece com o de todos. Com um só projeto no filtro, o grafo marca as vantagens dele. ",
          "Entram projetos com 30 chamadas ou mais no período, sem o filtro de projeto."),
      layout_columns(col_widths = c(7, 5),
        visNetwork::visNetworkOutput("d_capacidades", height = "520px"),
        DT::DTOutput("d_projetos"))
    ),
    p(class = "cobertura", "Só o Claude Code: o agy não grava as chamadas de ferramenta de forma legível (docs/registros.md).")
  ),
  nav_panel("Subagentes", icon = bsicons::bs_icon("people"),
    div(class = "alert alert-secondary",
        "Subagentes do Claude e do agy e delegações do jangada-delegar, desde o primeiro registro (sem os filtros ao lado). ",
        "Regras de decisão no README, seção Subagentes. * = pouco dado (15 entregas ou menos no grupo)."),
    layout_column_wrap(width = 1 / 4, fill = FALSE,
      value_box("Delegado ao agy", textOutput("e_fracao"), showcase = bsicons::bs_icon("share"),
                p(textOutput("e_fracao_n", inline = TRUE))),
      value_box("Recusas do jangada-delegar", textOutput("e_recusas"), showcase = bsicons::bs_icon("slash-circle"),
                p(textOutput("e_recusas_n", inline = TRUE))),
      value_box("Cota do agy por delegação", textOutput("e_cota"), showcase = bsicons::bs_icon("battery-half"),
                p(textOutput("e_cota_n", inline = TRUE))),
      value_box("Desvios do protocolo (meta zero)", textOutput("e_desvios"), showcase = bsicons::bs_icon("exclamation-triangle"),
                p(textOutput("e_desvios_n", inline = TRUE)))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Tokens do Claude por entrega aprovada (mediana e n)", DT::DTOutput("e_tokens"),
             cob = div(class = "cobertura", "Conversa principal (sem o cache lido) mais os subagentes do Claude. Faixa: tercis de linhas mudadas.")),
      navset_card_underline(title = "Aprovação na 1ª rodada (% e n)", full_screen = TRUE,
        nav_panel("Com e sem verificador", DT::DTOutput("e_verificador")),
        nav_panel("Com e sem agy", DT::DTOutput("e_agy")))
    ),
    layout_columns(col_widths = c(7, 5),
      cartao("Árvore de delegação", visNetwork::visNetworkOutput("e_arvore", height = "480px"),
             cob = div(class = "cobertura", "Pasta, conversa (ou sessão, nas delegações) e cada subagente ou delegação.")),
      navset_card_underline(title = "Detalhes", full_screen = TRUE,
        nav_panel("Compressão", DT::DTOutput("e_compressao"),
                  p(class = "cobertura", "Claude: tokens do subagente por token devolvido. agy: passos por mil tokens devolvidos, série à parte.")),
        nav_panel("Retornos grandes", DT::DTOutput("e_grandes")),
        nav_panel("Desvios", DT::DTOutput("e_desvios_tab")),
        nav_panel("Sem fonte", DT::DTOutput("e_fonte")))
    )
  ),
  nav_panel("Pesquisas", icon = bsicons::bs_icon("search"),
    div(class = "alert alert-secondary",
        "Histórico e verificação de fatos do Conversa de Pescador. Consultas rápidas com auditoria cética multi-agente, sem dependência de projeto."),
    layout_column_wrap(width = 1 / 3, fill = FALSE,
      value_box("Total de pesquisas", textOutput("f_total"), showcase = bsicons::bs_icon("chat-dots")),
      value_box("Termômetro de veracidade", textOutput("f_fato"), showcase = bsicons::bs_icon("shield-check"),
                p("média de fatos comprovados")),
      value_box("Consultas hoje", textOutput("f_hoje"), showcase = bsicons::bs_icon("calendar-check"))
    ),
    layout_column_wrap(width = 1 / 2, fill = FALSE,
      cartao("Nuvem de tópicos e palavras-chave", uiOutput("f_nuvem")),
      cartao("Termos mais frequentes", plotly::plotlyOutput("f_grafico_termos", height = "280px"))
    ),
    cartao("Consultas realizadas e veredito do auditor", DT::DTOutput("f_tabela"))
  ),
  nav_spacer(),
  nav_item(input_dark_mode(id = "modo", mode = "dark"))
)

server <- function(input, output, session) {
  if (!origem_local(session$request$HTTP_HOST, session$request$HTTP_ORIGIN)
      || !token_certo(session$request$HTTP_HOST, isolate(session$clientData$url_search), chave)) {
    session$close()
    return(invisible())
  }
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
    v <- d[[col]]
    # A coluna dia já vem em texto; data e inicio são carimbos.
    dia <- if (is.character(v)) as.Date(v, "%Y-%m-%d") else as.Date(format(v, "%Y-%m-%d"))
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
  # As revisões feitas fora do isolamento repetem, na integração, entregas já
  # revisadas dentro: ficam fora das taxas e aparecem só na contagem abaixo.
  ent_todas <- reactive({
    e <- entregas(dados()$validacoes)
    e <- filtrar(no_periodo(e, "fim"), agente = "autor")
    if (length(input$par)) e <- e[e$par %in% input$par, ]
    e
  })
  ent <- reactive(ent_todas()[!ent_todas()$fora, ])
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
    f <- ent_todas()[ent_todas()$fora, ]
    paste0(n, " entrega(s) aprovada(s)", if (n < POUCO_DADO) " · pouco dado" else "",
           " · fora do isolamento: ", sum(f$aprovada), " de ", nrow(f), " aprovada(s)")
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
  # Por dia: os dias antigos só existem somados (JANGADA_PAINEL_RETENCAO).
  msg <- reactive({
    d <- consumo_diario(dados()$mensagens, dados()$mensagens_dias)
    filtrar(no_periodo(d[!d$modelo %in% "<synthetic>", , drop = FALSE], "dia"))
  })
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
  output$b_cob <- renderUI(cobertura_ui(cobertura(as.Date(msg()$dia), sum(msg()$respostas))))
  output$b_dia <- plotly::renderPlotly({
    m <- msg()
    if (!nrow(m)) return(vazio())
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

  # D. Redes
  todas <- reactive(chamadas(no_periodo(dados()$ferramentas), dados()$resultados))
  ch <- reactive({
    t <- todas()
    if (length(input$projeto)) t <- t[t$projeto %in% input$projeto, ]
    t
  })
  ciclos <- reactive(ciclos_retrabalho(ch()))
  ed <- reactive(edicoes(ch()))
  apont <- reactive(filtrar(no_periodo(dados()$apontamentos)))
  quentes <- reactive(pontos_quentes(ed(), apont()))
  output$vb_ciclos <- renderText(nrow(ciclos()))
  output$vb_ciclos_n <- renderText({
    n <- length(unique(ch()$conversa))
    k <- length(unique(ciclos()$conversa))
    paste0("em ", k, " de ", n, " conversa(s)")
  })
  testes <- reactive(ch()[ch()$ferramenta == "Bash" & ch()$alvo == "testes", ])
  output$vb_testes <- renderText(if (nrow(testes())) paste0(round(100 * mean(testes()$erro)), "%") else "-")
  output$vb_testes_n <- renderText(paste(milhar(sum(testes()$erro)), "de", milhar(nrow(testes())), "execuções de teste"))
  output$vb_multi <- renderText(if (nrow(quentes())) sum(quentes()$sessoes > 1) else 0)
  output$d_transicoes <- visNetwork::renderVisNetwork(
    grafo(rede_transicoes(ch(), input$max_nos, input$peso_min, destaque = basename(ciclos()$arquivo))))
  por <- function(col, rotulo) {
    ci <- ciclos()
    if (!nrow(ci)) return(tabela(data.frame()))
    total <- tapply(ch()$conversa, ch()[[col]], function(x) length(unique(x)))
    a <- do.call(rbind, lapply(split(ci, ci[[col]]), function(x)
      data.frame(g = x[[col]][1], ciclos = nrow(x), com = length(unique(x$conversa)))))
    a$conversas <- as.integer(total[a$g])
    a$por_conversa <- format(round(a$ciclos / a$conversas, 2), decimal.mark = ",")
    tabela(setNames(a[order(-a$ciclos), ], c(rotulo, "ciclos", "conversas com ciclo", "conversas", "ciclos por conversa")))
  }
  output$d_ciclos_projeto <- DT::renderDT(por("projeto", "projeto"))
  output$d_ciclos_sessao <- DT::renderDT(por("sessao", "sessão"))
  output$d_ciclos_arquivo <- DT::renderDT({
    ci <- ciclos()
    if (!nrow(ci)) return(tabela(data.frame()))
    a <- aggregate(list(ciclos = rep(1L, nrow(ci))), list(arquivo = ci$arquivo), sum)
    tabela(a[order(-a$ciclos), ])
  })
  output$d_quentes <- visNetwork::renderVisNetwork(grafo(rede_pontos_quentes(ed(), input$max_nos)))
  output$d_quentes_tab <- DT::renderDT({
    q <- quentes()
    if (!nrow(q)) return(tabela(data.frame()))
    q$ultima <- format(q$ultima, "%d/%m %H:%M")
    tabela(setNames(q[c("sessoes", "edicoes", "revisar", "ultima", "arquivo")],
                    c("sessões", "edições", "REVISAR", "última edição", "arquivo")))
  })
  output$d_revisar <- DT::renderDT({
    a <- apont()
    if (!nrow(a)) return(tabela(data.frame()))
    r <- do.call(rbind, lapply(split(a, paste(a$projeto, a$arquivo)), function(x)
      data.frame(projeto = x$projeto[1], arquivo = x$arquivo[1], itens = nrow(x),
                 entregas = length(unique(x$rotulo)))))
    tabela(setNames(r[order(-r$itens), ], c("projeto", "arquivo", "itens REVISAR", "rótulos")))
  })
  esp <- reactive(espaco_capacidades(todas()))
  output$d_capacidades <- visNetwork::renderVisNetwork({
    grafo(rede_capacidades(esp(), input$max_nos, input$limiar, projeto = input$projeto))
  })
  output$d_projetos <- DT::renderDT({
    e <- esp()
    if (is.null(e)) return(tabela(data.frame()))
    tabela(setNames(e$projetos[c("projeto", "tipico", "com_vantagem", "chamadas", "vantagens")],
                    c("projeto", "típico (%)", "com vantagem", "chamadas", "vantagens")))
  })


  # E. Subagentes
  sub <- reactive(dados()$subagentes)
  pc <- function(v, suf = "%") if (is.null(v)) "-" else paste0(format(v, decimal.mark = ","), suf)
  output$e_fracao <- renderText(pc(sub()$fracao_agy$fracao_agy_pct))
  output$e_fracao_n <- renderText({
    f <- sub()$fracao_agy
    # Com erro, o coletor grava só o erro, e os outros quadros ficam em "-".
    if (!is.null(sub()$erro)) paste0("indicadores não calculados na coleta de ", sub()$data, ": ", sub()$erro) else
    if (is.null(f)) "sem registro" else
      paste0(f$delegadas_agy, " delegação(ões); ", f$subagentes_claude, " subagente(s) do Claude, ", f$subagentes_agy, " do agy")
  })
  output$e_recusas <- renderText(pc(sub()$fracao_agy$taxa_recusa_pct))
  output$e_recusas_n <- renderText({
    f <- sub()$fracao_agy
    if (is.null(f)) "-" else paste0(f$recusas, " de ", f$chamadas, " chamada(s)")
  })
  output$e_cota <- renderText(pc(sub()$cota_agy$media_pp, " pp"))
  output$e_cota_n <- renderText({
    k <- sub()$cota_agy
    if (is.null(k)) "-" else paste0(k$n, " medida(s), ", k$abaixo_da_resolucao, " sem variação; cabem ",
                                    if (is.null(k$delegacoes_por_bloco)) "-" else k$delegacoes_por_bloco, " por bloco de 5 h")
  })
  output$e_desvios <- renderText(sum(lengths(sub()$desvios)))
  output$e_desvios_n <- renderText({
    d <- sub()$desvios
    if (is.null(d)) "-" else paste(paste(sub("_", " ", names(d)), lengths(d)), collapse = ", ")
  })
  output$e_tokens <- DT::renderDT(tabela(setNames(tabela_comparar(sub()$tokens_por_entrega, "mediana_tokens"),
                                                  c("faixa", "com agy", "sem agy"))))
  output$e_verificador <- DT::renderDT(tabela(setNames(tabela_comparar(sub()$validacao$verificador, "primeira_pct"),
                                                       c("faixa", "com verificador", "sem verificador"))))
  output$e_agy <- DT::renderDT(tabela(setNames(tabela_comparar(sub()$validacao$agy, "primeira_pct"),
                                               c("faixa", "com agy", "sem agy"))))
  output$e_arvore <- visNetwork::renderVisNetwork(grafo(arvore_rede(sub()$arvore)))
  output$e_compressao <- DT::renderDT({
    c <- sub()$compressao
    p <- c$claude$por_papel
    d <- data.frame(serie = character(), papel = character(), mediana = numeric())
    if (length(p)) d <- data.frame(serie = "Claude", papel = names(p), mediana = vapply(p, num_ou_na, 0))
    a <- num_ou_na(c$agy$mediana_passos_por_mil_tokens)
    if (!is.na(a)) d <- rbind(d, data.frame(serie = "agy", papel = "delegações", mediana = a))
    tabela(d)
  })
  output$e_grandes <- DT::renderDT(tabela(tabela_lista(sub()$compressao$retornos_grandes,
                                                       c("origem", "papel", "id", "inicio", "retorno_tokens"))))
  output$e_desvios_tab <- DT::renderDT({
    d <- sub()$desvios
    itens <- unlist(lapply(names(d), function(k) lapply(d[[k]], function(x) c(list(desvio = k), x))), recursive = FALSE)
    tabela(tabela_lista(itens, c("desvio", "origem", "tipo", "descricao", "inicio")))
  })
  output$e_fonte <- DT::renderDT({
    q <- sub()$qualidade
    if (is.null(q)) return(tabela(data.frame()))
    tabela(data.frame(origem = c("subagentes do Claude", "delegações ao agy"),
                      relatorios = c(q$claude$n, q$delegacoes$n), sem_fonte = c(q$claude$total, q$delegacoes$total),
                      mediana = c(num_ou_na(q$claude$mediana), num_ou_na(q$delegacoes$mediana))))
  })

  # F. Pesquisas (Conversa de Pescador)
  pesqs <- reactive(dados()$pesquisas)
  output$f_total <- renderText({
    p <- pesqs()
    if (nrow(p) == 0) "0" else as.character(nrow(p))
  })
  output$f_fato <- renderText({
    p <- pesqs()
    if (nrow(p) == 0) "-" else paste0(round(mean(p$grau_fato, na.rm = TRUE)), "% Fato")
  })
  output$f_hoje <- renderText({
    p <- pesqs()
    if (nrow(p) == 0) "0" else as.character(sum(p$dia == as.character(Sys.Date()), na.rm = TRUE))
  })
  # Frequência de termos e palavras das pesquisas
  termos_pesquisas <- reactive({
    p <- pesqs()
    if (nrow(p) == 0) return(data.frame(termo = character(), n = integer()))

    texto <- paste(p$pergunta, collapse = " ")
    palavras <- unlist(strsplit(tolower(texto), "[^[:alnum:]áéíóúâêîôûãõàèìòùäëïöüçñ]+"))
    palavras <- palavras[nchar(palavras) >= 3]

    sw_extras <- c("qual", "quais", "como", "sobre", "pode", "dar", "uma", "uns", "mais",
                   "menos", "você", "para", "com", "por", "que", "pra", "ter", "ser",
                   "isso", "esse", "essa", "esta", "este", "dos", "das", "the", "and", "for", "with")
    sw <- if (requireNamespace("stopwords", quietly = TRUE)) {
      unique(c(stopwords::stopwords("pt"), stopwords::stopwords("en"), sw_extras))
    } else {
      sw_extras
    }

    palavras_limpas <- palavras[!palavras %in% sw]
    if (length(palavras_limpas) == 0) return(data.frame(termo = character(), n = integer()))

    tb <- sort(table(palavras_limpas), decreasing = TRUE)
    data.frame(termo = names(tb), n = as.integer(tb), stringsAsFactors = FALSE)
  })

  # Nuvem de palavras responsiva e esteticamente harmonizada ao matugen
  output$f_nuvem <- renderUI({
    df <- termos_pesquisas()
    if (nrow(df) == 0) {
      return(div(class = "text-muted p-4 text-center", "Nenhum termo registrado para exibição na nuvem."))
    }

    df <- head(df, 35)
    max_n <- max(df$n)
    min_n <- min(df$n)

    tags_list <- lapply(seq_len(nrow(df)), function(i) {
      termo <- df$termo[i]
      qtd <- df$n[i]

      tam <- if (max_n == min_n) 1.15 else 0.85 + ((qtd - min_n) / max(1, (max_n - min_n))) * 1.35
      opac <- 0.70 + (qtd / max_n) * 0.30

      tags$span(
        title = paste0(termo, " (", qtd, " ocorrência(s))"),
        class = "badge rounded-pill me-1 mb-2",
        style = sprintf(
          "font-size: %.2frem; padding: 0.35em 0.65em; font-weight: 500; opacity: %.2f; background-color: var(--bs-secondary-bg); color: var(--bs-body-color); border: 1px solid var(--bs-border-color); display: inline-block;",
          tam, opac
        ),
        termo,
        tags$small(class = "ms-1 text-muted", paste0("(", qtd, ")"))
      )
    })

    div(style = "line-height: 2.2; text-align: center; padding: 8px;", tags_list)
  })

  # Gráfico de barras horizontais com os termos mais recorrentes
  output$f_grafico_termos <- plotly::renderPlotly({
    df <- termos_pesquisas()
    if (nrow(df) == 0) {
      return(plotly::plotly_empty() |> plotly::layout(
        title = list(text = "Sem dados de pesquisa", font = list(color = cores[["texto_suave"]])),
        paper_bgcolor = "rgba(0,0,0,0)", plot_bgcolor = "rgba(0,0,0,0)"
      ))
    }
    top_df <- head(df, 10)
    top_df <- top_df[order(top_df$n), ]
    top_df$termo <- factor(top_df$termo, levels = top_df$termo)

    p <- plotly::plot_ly(
      data = top_df,
      x = ~n,
      y = ~termo,
      type = "bar",
      orientation = "h",
      marker = list(color = cores[["primaria"]]),
      hoverinfo = "text",
      text = ~paste0(termo, ": ", n, " consulta(s)")
    )
    plotly::layout(
      p,
      xaxis = list(title = "Consultas", dtick = 1, color = cores[["texto_suave"]]),
      yaxis = list(title = "", color = cores[["texto"]]),
      margin = list(l = 80, r = 20, t = 10, b = 35),
      paper_bgcolor = "rgba(0,0,0,0)",
      plot_bgcolor = "rgba(0,0,0,0)",
      font = list(color = cores[["texto"]])
    )
  })

  output$f_tabela <- DT::renderDT({
    p <- pesqs()
    if (nrow(p) == 0) {
      return(tabela(data.frame(aviso = "Nenhuma pesquisa registrada no Pescador.")))
    }
    ord <- order(p$data, decreasing = TRUE)
    df <- data.frame(
      data = format(p$data[ord], "%d/%m %H:%M"),
      sessao = p$sessao[ord],
      pergunta = p$pergunta[ord],
      termo = paste0(p$grau_fato[ord], "%"),
      veredito = p$veredito[ord],
      fontes = p$fontes_qtd[ord],
      segundos = sprintf("%.1fs", p$segundos[ord]),
      stringsAsFactors = FALSE
    )
    tabela(setNames(df, c("data", "sessão", "pergunta", "fato (%)", "diagnóstico do auditor", "fontes", "tempo")))
  })
}

shinyApp(ui, server)
