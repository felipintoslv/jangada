# Painel de indicadores do jangada. Só lê o cache em Parquet que o
# coletor.py grava (padrão ~/.local/state/jangada/painel) e recarrega quando
# o coleta.json muda. Sobe pelo jangada-painel, em 127.0.0.1, e só abre
# sessão com o token do painel-chave na URL; nenhum recurso vem da rede.

library(shiny)
library(bslib)

pasta_app <- getwd()
source(file.path(pasta_app, "indicadores.R"), local = TRUE)
source(file.path(pasta_app, "hoje.R"), local = TRUE)
source(file.path(pasta_app, "operacional.R"), local = TRUE)

estado <- file.path(Sys.getenv("XDG_STATE_HOME", file.path(Sys.getenv("HOME"), ".local/state")), "jangada")
cache <- getOption("jangada.painel.cache", file.path(estado, "painel"))
chave <- getOption("jangada.painel.chave", file.path(estado, "painel-chave", "token"))

source(file.path(pasta_app, "fichas.R"), local = TRUE)
fichas <- carregar_fichas()
cores <- unlist(fichas$dark)

regras_fichas <- function(modo) {
  c <- fichas[[modo]]
  sprintf("[data-bs-theme=%s] {
    --bs-body-bg: %s; --bs-body-color: %s; --bs-secondary-color: %s;
    --bs-primary: %s; --bs-primary-rgb: %s; --bs-link-color: %s;
    --bs-tertiary-bg: %s; --bs-emphasis-color: %s;
    --bs-border-color: %s; --jangada-elevada: %s; }
    [data-bs-theme=%s] .card { background-color: var(--jangada-elevada); }
    [data-bs-theme=%s] .nav-link.active { background: %s; color: %s; }",
    modo, c$superficie, c$texto, c$texto_suave, c$primaria,
    paste(grDevices::col2rgb(c$primaria), collapse = ","), c$primaria,
    c$superficie_elevada, c$texto, c$texto_suave, c$superficie_elevada,
    modo, modo, c$primaria, c$texto_primario)
}

tema <- bs_theme(
  version = 5, primary = fichas$light$primaria,
  base_font = font_collection("Inter", "system-ui", "sans-serif"),
  code_font = font_collection("JetBrains Mono", "monospace")
) |>
  bs_add_rules(paste(regras_fichas("dark"), regras_fichas("light"), "
    body { font-size: 14px; }
    .card { border-radius: 8px; }
    pre, code { font-family: 'JetBrains Mono', monospace; }
    :focus-visible { outline: 3px solid var(--bs-primary); outline-offset: 4px; }
    .aviso-pouco { color: var(--bs-body-color); font-weight: 600; }
    .cobertura { font-size: 13px; color: var(--bs-secondary-color); }
    .bslib-value-box .value-box-title { font-size: 14px; }
    .bslib-value-box.default .value-box-showcase > svg.bi { fill: var(--bs-primary) !important; }
    .dataTables_wrapper { font-size: 14px; }
    .op-detalhe td { overflow-wrap: anywhere; white-space: pre-wrap; }
    .marca-jangada { width: 24px; height: 24px; fill: currentColor; margin-right: 8px; }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { animation: none !important; transition: none !important; }
    }"))

paleta_clara <- c(claude = "#0072B2", codex = "#D55E00", ollama = "#009E73",
                  agy = "#AA4499", deterministico = "#B8860B", desconhecido = "#3C93C2")
paleta_escura <- c(claude = "#56B4E9", codex = "#E69F00", ollama = "#5DD39E",
                   agy = "#CC79A7", deterministico = "#F0E442", desconhecido = "#8ECAE6")

# Paginação e contagem só quando a tabela passa de uma página. Sem dado, uma
# coluna vazia leva o aviso "sem dado".
tabela <- function(d, busca = FALSE, ...) {
  if (!ncol(d)) d <- data.frame(` ` = character(), check.names = FALSE)
  dom <- if (nrow(d) > 10) "tip" else "t"
  if (busca) dom <- paste0("f", dom)
  DT::datatable(d, rownames = FALSE, options = list(pageLength = 10, dom = dom, scrollX = TRUE,
    language = list(info = "_START_ a _END_ de _TOTAL_", infoEmpty = "nada", emptyTable = "sem dado",
                    search = "Buscar:", paginate = list(previous = "anterior", `next` = "próxima"))), ...)
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

cartao <- function(titulo, ..., cob = NULL) {
  card(full_screen = TRUE, card_header(titulo), card_body(...), if (!is.null(cob)) card_footer(cob))
}

filtros <- sidebar(
  width = 260,
  dateRangeInput("periodo", "Período", start = Sys.Date(), end = Sys.Date(),
                 language = "pt-BR", separator = "a", format = "dd/mm/yyyy"),
  selectizeInput("projeto", "Projeto", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  selectizeInput("agente", "Agente ou perfil", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  selectizeInput("par", "Par autor → revisor", choices = NULL, multiple = TRUE,
                 options = list(placeholder = "todos")),
  selectizeInput("executor", "Executor do consumo", choices = NULL, multiple = TRUE),
  selectizeInput("origem_consumo", "Origem do consumo", choices = NULL, multiple = TRUE),
  selectizeInput("modelo_consumo", "Modelo do consumo", choices = NULL, multiple = TRUE),
  selectizeInput("provedor_consumo", "Provedor do consumo", choices = NULL, multiple = TRUE),
  selectizeInput("papel_consumo", "Papel da delegação", choices = NULL, multiple = TRUE),
  uiOutput("coleta")
)

marca <- paste(readLines(file.path(pasta_app, "../logo/jangada-symbolic.svg"), warn = FALSE), collapse = "")
marca <- gsub('fill="#000000"', 'fill="currentColor"', marca, fixed = TRUE)
marca <- sub('<svg ', '<svg class="marca-jangada" aria-hidden="true" ', marca, fixed = TRUE)

ui <- page_navbar(
  title = tagList(HTML(marca), "Jangada"), theme = tema, fillable = FALSE, id = "painel",
  window_title = "Painel do jangada", selected = "Operacional",
  nav_panel("Operacional",
  navset_bar(id = "secao_operacional", selected = "Visão Geral",
  nav_panel("Visão Geral", icon = bsicons::bs_icon("calendar-check"),
    uiOutput("op_resumo"), hoje_ui("hoje")
  ),
  nav_panel("Projetos", DT::DTOutput("op_projetos"),
    selectInput("op_p_detalhe", "Projeto para consultar", choices = NULL),
    uiOutput("op_projeto_detalhe")),
  nav_panel("Central de Atividades",
    p("Tarefas da fila e sessões de agentes. As ações ficam na Central Qt e no terminal."),
    fluidRow(column(4, selectInput("op_projeto", "Projeto", choices = c("Todos" = ""))),
      column(4, selectInput("op_estado", "Estado", choices = c("Todos" = "", "Planejada", "Pronta", "Executando",
        "Em revisão", "Concluída", "Bloqueada", "Falhou", "Cancelada"))),
      column(4, selectInput("op_agente", "Agente", choices = c("Todos" = "")))),
    checkboxInput("op_filtrar_periodo", "Filtrar por data de atualização", FALSE),
    dateRangeInput("op_periodo", "Atualização", start = Sys.Date() - 30, end = Sys.Date(), language = "pt-BR"),
    DT::DTOutput("op_atividades"),
    tags$details(tags$summary("Atividades por projeto"), DT::DTOutput("op_por_projeto")),
    selectInput("op_detalhe", "Detalhe da tarefa ou sessão", choices = NULL),
    uiOutput("op_detalhes"), h4("Comandos no terminal"), verbatimTextOutput("op_comandos")),
  nav_panel("Central de Agentes", p("Perfis configurados. Modelo ausente permanece não registrado."),
    DT::DTOutput("op_agentes"), h4("Execuções e consumo medido"), DT::DTOutput("op_execucoes")),
  nav_panel("Modelos e Provedores",
    p("Cadastro não comprova autenticação, contrato, modelo ou cota. A observação mostra o último resultado registrado."),
    p("CLI usa a autenticação do próprio programa. Credencial não observada não significa ausente."),
    DT::DTOutput("op_provedores")),
  nav_panel("Central de Revisão", p("Aguardar revisão não aprova a entrega. Use jangada-validar ou revisão da fila fora do isolamento."),
    h4("Tarefas à espera"), DT::DTOutput("op_pendentes"), h4("Pareceres da fila"), DT::DTOutput("op_revisoes"),
    h4("Validações registradas de sessões"), DT::DTOutput("op_validacoes"),
    p("A origem distingue registros protegidos de dados graváveis pelo agente. A integração confere a aprovação no backend.")),
  nav_panel("Monitoramento", p("Recursos medidos somente enquanto esta aba estiver aberta."),
    uiOutput("op_monitoramento")),
  nav_panel("Histórico e Artefatos", p("Eventos e hashes dos artefatos. Os registros são selecionáveis e têm busca."),
    DT::DTOutput("op_historico")),
  nav_panel("Configurações", p("Valores públicos validados. Edite o arquivo indicado pelo terminal ou editor."),
    uiOutput("op_configuracao")),
  )),
  nav_panel("Indicadores",
  layout_sidebar(sidebar = filtros,
  navset_bar(id = "secao_indicadores", selected = "Revisão e síntese",
  nav_panel("Fila e provedores", icon = bsicons::bs_icon("list-task"),
    h3("Execução automática de tarefas"),
    p("Esta fila reúne tarefas planejadas para execução automática. As sessões da Central de Tarefas são acompanhadas separadamente."),
    p("Provedores são os serviços ou executores usados pela automação, como Ollama, agy e Codex. Aqui aparecem apenas suas observações registradas."),
    tags$details(tags$summary("Como os dados chegam aqui?"),
      p("Cadastre um plano com ", code("jangada-fila --importar PLANO.json"),
        " no projeto. A execução usa ", code("jangada-executar"),
        "; atualizar o painel apenas coleta os registros, sem executar tarefas nem consultar provedores.")),
    uiOutput("g_vazia"),
    p(class = "cobertura",
      "Retrato da última coleta. O projeto filtra tarefas e métricas acumuladas; o período não altera este retrato."),
    uiOutput("g_erros"),
    layout_column_wrap(width = 1 / 4, fill = FALSE,
      value_box("Em execução", textOutput("g_executando")),
      value_box("Em espera ou bloqueadas", textOutput("g_esperando")),
      value_box("Aguardando revisão", textOutput("g_revisao")),
      value_box("Concluídas", textOutput("g_concluidas"))),
    cartao("Tarefas e motivos da espera", DT::DTOutput("g_tarefas")),
    cartao("Orçamento por tarefa", DT::DTOutput("g_orcamento"),
      cob = p(class = "cobertura", "Saldo desconhecido durante execução ou quando há consumo sem medida.")),
    cartao("Consumo e custo por projeto", DT::DTOutput("g_metricas"),
      cob = p(class = "cobertura",
        "Estimativas usam preços declarados pelo usuário. Parcela conhecida não representa o custo total.")),
    cartao("Supervisão e revisão por amostragem", DT::DTOutput("g_supervisao"),
      cob = p(class = "cobertura", "Contagens da fila, separadas das rodadas do jangada-validar.")),
    cartao("Provedores de todos os projetos", uiOutput("g_provedores_aviso"), DT::DTOutput("g_provedores"),
      cob = p(class = "cobertura",
        "Somente observações registradas. Validade da observação não garante disponibilidade após esse horário."))
  ),
  nav_panel("Revisão e síntese", icon = bsicons::bs_icon("check2-square"),
    uiOutput("manchete_dia"),
    uiOutput("situacao_fontes"),
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
      cartao("Taxa de aprovação direta por projeto", DT::DTOutput("a_projeto"), cob = uiOutput("a_cob")),
      cartao("Eficácia por par autor → revisor", DT::DTOutput("a_par"),
             cob = div(class = "cobertura", "* pouco dado: menos de 10 aprovadas. Sem registro: validações antigas, de antes do validar.jsonl. As taxas contam as rodadas registradas pela própria sessão, num arquivo que o agente isolado pode alterar."))
    ),
    layout_columns(col_widths = c(6, 6),
      cartao("Entregas no limite de rodadas (atrito elevado)", DT::DTOutput("a_limite")),
      cartao("Tamanho do diff: aprovadas de primeira e reprovadas", plotly::plotlyOutput("a_diff", height = 300),
             cob = uiOutput("a_diff_cob"))
    )
  ),
  nav_panel("Consumo de modelos", icon = bsicons::bs_icon("cpu"),
    uiOutput("insight_consumo"),
    cartao("Evolução diária do consumo", uiOutput("b_motores_area"),
           cob = uiOutput("b_motores_cob")),
    cartao("Consumo por executor, origem e modelo", DT::DTOutput("b_motores"),
           p(class = "cobertura", "Entrada inclui cache lido. Saída e raciocínio são mostrados separadamente e não são somados. Campos sem medida aparecem como ausentes; totais parciais têm contagem de cobertura.")),
    layout_columns(col_widths = c(6, 6),
      cartao("Desempenho do Ollama", plotly::plotlyOutput("b_local_grafico", height = 260),
             DT::DTOutput("b_local"),
             p(class = "cobertura", "Tokens/s usa apenas o tempo de geração medido. Registros antigos sem duração interna não permitem calcular velocidade. Poucas chamadas não estabelecem um comparativo de modelos.")),
      cartao("Ferramentas por executor", DT::DTOutput("b_ferramentas"),
             p(class = "cobertura", "O executor é quem chamou a ferramenta. O fluxo local do Ollama não dispõe de ferramentas."))
    ),
    cartao("Cobertura das fontes", DT::DTOutput("b_fontes")),
    h5("Detalhamento do histórico Claude"),
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
    p(class = "cobertura", "Os gráficos e cartões desta seção detalham o Claude e usam período e projeto. Os filtros de executor, origem e modelo se aplicam às tabelas acima. O resumo acima separa históricos externos das sessões geridas pelo jangada; o agy não fornece contagem legível de tokens.")
  ),
  nav_panel("Tempo e atenção", icon = bsicons::bs_icon("clock-history"),
    uiOutput("insight_tempo"),
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
  nav_panel("Gargalos e redes", icon = bsicons::bs_icon("diagram-3"),
    uiOutput("insight_gargalos"),
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
      navset_card_underline(title = "Retrabalho edit-test-edit", full_screen = TRUE,
        nav_panel("Por projeto", DT::DTOutput("d_ciclos_projeto")),
        nav_panel("Por sessão", DT::DTOutput("d_ciclos_sessao")),
        nav_panel("Arquivos", DT::DTOutput("d_ciclos_arquivo")))
    ),
    layout_columns(col_widths = c(7, 5),
      cartao("Pontos quentes: sessão × arquivo editado", visNetwork::visNetworkOutput("d_quentes", height = "480px")),
      navset_card_underline(title = "Arquivos com atrito", full_screen = TRUE,
        nav_panel("Disputados em mais sessões", DT::DTOutput("d_quentes_tab")),
        nav_panel("Com mais pareceres REVISAR", DT::DTOutput("d_revisar"),
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
  nav_panel("Autonomia de agentes", icon = bsicons::bs_icon("people"),
    p(class = "cobertura", "Período e projeto filtram esta aba. Demais filtros se aplicam às abas indicadas."),
    uiOutput("insight_subagentes"),
    cartao("Delegações atendidas por destino", plotly::plotlyOutput("e_destinos", height = 260),
      cob = p(class = "cobertura", "Fonte: delegacoes.jsonl. Subagentes nativos e recusas ficam fora destas barras.")),
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
      navset_card_underline(title = "Eficácia da aprovação na 1ª rodada (% e n)", full_screen = TRUE,
        nav_panel("Com e sem verificador", DT::DTOutput("e_verificador")),
        nav_panel("Com e sem agy", DT::DTOutput("e_agy")))
    ),
    layout_columns(col_widths = c(7, 5),
      cartao("Árvore hierárquica de delegação", visNetwork::visNetworkOutput("e_arvore", height = "480px"),
             cob = div(class = "cobertura", "Pasta, conversa (ou sessão, nas delegações) e cada subagente ou delegação.")),
      navset_card_underline(title = "Métricas de conformidade", full_screen = TRUE,
        nav_panel("Compressão", DT::DTOutput("e_compressao"),
                  p(class = "cobertura", "Claude: tokens do subagente por token devolvido. agy: passos por mil tokens devolvidos, série à parte.")),
        nav_panel("Retornos grandes", DT::DTOutput("e_grandes")),
        nav_panel("Desvios de escopo", DT::DTOutput("e_desvios_tab")),
        nav_panel("Sem fonte", DT::DTOutput("e_fonte")))
    )
  ),
  ))),
  nav_spacer(),
  nav_item(input_dark_mode(id = "modo", mode = "dark"))
)

server <- function(input, output, session) {
  if (!origem_local(session$request$HTTP_HOST, session$request$HTTP_ORIGIN)
      || !token_certo(session$request$HTTP_HOST, isolate(session$clientData$url_search), chave)) {
    session$close()
    return(invisible())
  }
  aparencia <- reactive({
    escuro <- is.null(input$modo) || identical(input$modo, "dark")
    if (escuro) {
      list(fundo = cores[["superficie"]], texto = cores[["texto"]], grade = "#6B7075",
           aresta = "#999999", destaque = cores[["primaria"]], neutra = "#B3B3B3", raciocinio = "#D7AD88")
    } else {
      list(fundo = fichas$light$superficie, texto = fichas$light$texto, grade = "#858A90",
           aresta = "#888888", destaque = fichas$light$primaria, neutra = "#4D4D4D", raciocinio = "#B08968")
    }
  })
  paleta <- reactive({
    if (is.null(input$modo) || identical(input$modo, "dark")) paleta_escura else paleta_clara
  })
  pl <- function(p, x = "", y = "") {
    p |>
      plotly::layout(paper_bgcolor = aparencia()$fundo, plot_bgcolor = aparencia()$fundo,
                     font = list(color = aparencia()$texto, family = "Inter, sans-serif"),
                     xaxis = list(title = list(text = x), showgrid = FALSE,
                                  zerolinecolor = aparencia()$grade),
                     yaxis = list(title = list(text = y), rangemode = "tozero",
                                  gridcolor = aparencia()$grade, zerolinecolor = aparencia()$grade, nticks = 8),
                     hoverlabel = list(bgcolor = aparencia()$fundo, font = list(color = aparencia()$texto)),
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

  grafo <- function(r) {
    validate(need(!is.null(r), "sem dado no período"))
    grupos <- unique(r$nos$group)
    v <- visNetwork::visNetwork(r$nos, r$arestas, width = "100%") |>
      # Física só até estabilizar: o layout fica compacto e depois para quieto.
      visNetwork::visPhysics(solver = "forceAtlas2Based", stabilization = list(iterations = 400),
                             forceAtlas2Based = list(gravitationalConstant = -60, avoidOverlap = 0.3)) |>
      visNetwork::visEvents(stabilizationIterationsDone = "function() { this.setOptions({physics: false}); }") |>
      visNetwork::visLayout(randomSeed = 1) |>
      visNetwork::visNodes(shape = "dot", font = list(color = aparencia()$texto, size = 18), scaling = list(min = 10, max = 40)) |>
      visNetwork::visEdges(color = list(color = aparencia()$aresta, highlight = aparencia()$destaque),
                           smooth = FALSE, scaling = list(min = 1, max = 8)) |>
      visNetwork::visOptions(highlightNearest = list(enabled = TRUE, degree = 1, hover = TRUE)) |>
      visNetwork::visInteraction(hover = TRUE, tooltipDelay = 100)
    for (g in grupos) {
      cor <- if (g %in% names(cores_grupos)) cores_grupos[[g]] else alerta
      if (!is.null(input$modo) && identical(input$modo, "light")) {
        if (cor == cores[["primaria"]]) cor <- fichas$light$primaria
        if (cor == cores[["atencao"]]) cor <- fichas$light$atencao
        if (cor == alerta) cor <- "#A44835"
        if (cor == "#b08968") cor <- "#805900"
      }
      v <- visNetwork::visGroups(v, groupname = g, color = list(background = cor, border = aparencia()$aresta,
                                 highlight = list(background = cor, border = aparencia()$texto)),
                                font = list(color = aparencia()$texto))
    }
    visNetwork::visLegend(v, useGroups = TRUE, position = "right", width = 0.22, zoom = FALSE)
  }

  dados <- reactivePoll(3000, session,
    checkFunc = function() file.mtime(file.path(cache, "coleta.json")),
    valueFunc = function() carregar_cache(cache))

  sub <- reactive({
    req(input$periodo)
    if (!is.null(dados()$subagentes$erro)) return(dados()$subagentes)
    if (!file.exists(file.path(cache, "subagentes.json"))) {
      return(list(erro = "atualize a coleta para carregar a autonomia"))
    }
    pedido <- jsonlite::toJSON(list(cache = file.path(cache, "subagentes.json"),
      inicio = as.character(input$periodo[1]), fim = as.character(input$periodo[2]),
      projetos = as.list(input$projeto)), auto_unbox = TRUE)
    tryCatch({
      saida <- suppressWarnings(system2("python3", shQuote(file.path(pasta_app, "autonomia.py")),
                                       input = pedido, stdout = TRUE, stderr = FALSE))
      if (!is.null(attr(saida, "status"))) stop("não foi possível recalcular a autonomia")
      jsonlite::fromJSON(paste(saida, collapse = "\n"), simplifyVector = FALSE)
    }, error = function(e) list(erro = conditionMessage(e)))
  })
  pc <- function(v, suf = "%") if (is.null(v)) "-" else paste0(format(v, decimal.mark = ","), suf)

  orq <- reactive({
    d <- dados()$orquestracao
    for (campo in c("tarefas", "projetos")) {
      if (length(input$projeto)) {
        d[[campo]] <- Filter(function(x) x$projeto %in% input$projeto, d[[campo]])
      }
    }
    d
  })
  hoje_server("hoje", dados)
  operacional_server(input, output, session, dados)
  estados_fila <- c(QUEUED = "Na fila", RUNNING = "Em execução", COMPLETED = "Concluída",
    REVIEW_REQUIRED = "Aguardando revisão", REVISION_REQUIRED = "Reprovada, corrigir",
    WAITING_PROVIDER = "Aguardando provedor", WAITING_QUOTA = "Aguardando cota",
    WAITING_REVIEWER = "Aguardando revisor", FAILED = "Falhou", CANCELLED = "Cancelada",
    PAUSED = "Pausada", BLOCKED = "Bloqueada")
  output$g_erros <- renderUI({
    erros <- orq()$erros
    if (length(erros)) div(class = "alert alert-warning",
      "Coleta incompleta; confira as lacunas antes de interpretar as contagens: ",
      paste(unlist(erros), collapse = "; "))
  })
  output$g_vazia <- renderUI({
    if (!length(orq()$tarefas) && !length(orq()$erros)) {
      if (length(dados()$orquestracao$tarefas)) {
        div(class = "alert alert-info", "Nenhuma tarefa de automação nos projetos selecionados. Ajuste o filtro de projeto para ver as demais.")
      } else {
        div(class = "alert alert-info", "Nenhuma tarefa de automação cadastrada na última coleta. As sessões dos agentes não entram nesta fila.")
      }
    }
  })
  output$g_provedores_aviso <- renderUI({
    if (!length(orq()$provedores) && !length(orq()$erros)) {
      p("Nenhuma observação de provedor registrada na última coleta. Isso não significa que os serviços estejam indisponíveis.")
    }
  })
  output$g_executando <- renderText(sum(vapply(orq()$tarefas, function(t) t$estado == "RUNNING", FALSE)))
  output$g_esperando <- renderText(sum(vapply(orq()$tarefas,
    function(t) t$estado %in% c("WAITING_PROVIDER", "WAITING_QUOTA", "WAITING_REVIEWER", "BLOCKED"), FALSE)))
  output$g_revisao <- renderText(sum(vapply(orq()$tarefas,
    function(t) t$estado == "REVIEW_REQUIRED", FALSE)))
  output$g_concluidas <- renderText(sum(vapply(orq()$tarefas, function(t) t$estado == "COMPLETED", FALSE)))
  output$g_tarefas <- DT::renderDT({
    d <- tabela_lista(orq()$tarefas,
      c("projeto", "id", "estado", "papel", "prioridade", "tentativas", "dependencias", "motivo"))
    d$estado <- unname(estados_fila[d$estado])
    prioridades <- c(critical = "Crítica", high = "Alta", normal = "Normal", low = "Baixa",
                     background = "Segundo plano")
    d$prioridade <- unname(prioridades[d$prioridade])
    tabela(setNames(d, c("projeto", "tarefa", "estado", "papel", "prioridade",
                        "tentativas", "dependências pendentes", "motivo")))
  })
  output$g_orcamento <- DT::renderDT({
    d <- tabela_lista(orq()$tarefas, c("projeto", "id", "limite_chamadas", "chamadas",
      "saldo_chamadas", "limite_segundos", "segundos", "saldo_segundos"))
    tabela(setNames(d, c("projeto", "tarefa", "limite de chamadas", "chamadas medidas",
      "saldo de chamadas", "limite (s)", "tempo medido (s)", "saldo (s)")))
  })
  output$g_metricas <- DT::renderDT({
    d <- tabela_lista(orq()$projetos, c("projeto", "chamadas", "chamadas_confirmadas",
      "chamadas_desconhecidas", "segundos_confirmados", "duracoes_desconhecidas",
      "tokens_entrada_confirmados", "tokens_saida_confirmados",
      "moeda", "custo_estimado", "custo_estimado_confirmado", "execucoes_sem_custo"))
    for (campo in c("custo_estimado", "custo_estimado_confirmado")) {
      d[[campo]] <- ifelse(is.na(d$moeda) | is.na(d[[campo]]), "sem medida",
        format(as.numeric(d[[campo]]), digits = 6, decimal.mark = ",", big.mark = ".", trim = TRUE))
    }
    tabela(setNames(d, c("projeto", "chamadas totais", "chamadas confirmadas",
      "execuções sem chamadas medidas", "tempo confirmado (s)", "durações desconhecidas",
      "tokens de entrada confirmados", "tokens de saída confirmados",
      "moeda", "custo total estimado", "custo estimado da parcela conhecida", "execuções sem custo medido")))
  })
  output$g_supervisao <- DT::renderDT({
    d <- tabela_lista(orq()$projetos, c("projeto", "supervisoes_aprovadas", "supervisoes_reprovadas",
      "supervisoes_inconclusivas", "esperas_supervisao", "selecionadas_na_amostra",
      "conclusoes_fora_da_amostra", "revisoes_aprovadas", "revisoes_reprovadas"))
    tabela(setNames(d, c("projeto", "supervisões aprovadas", "supervisões reprovadas",
      "supervisões inconclusivas", "esperas por supervisão", "selecionadas para revisão",
      "concluídas fora da amostra", "revisões aprovadas", "revisões reprovadas")))
  })
  output$g_provedores <- DT::renderDT({
    d <- tabela_lista(orq()$provedores, c("id", "status", "pausado", "cota", "modelo",
      "atualizado", "valido_ate", "espera_segundos", "motivo"))
    d$status <- unname(nomes_provedores[d$status])
    d$pausado <- ifelse(d$pausado == "1", "sim", "não")
    for (campo in c("atualizado", "valido_ate")) {
      instante <- as.numeric(d[[campo]])
      d[[campo]] <- ifelse(is.na(instante) | instante <= 0, "sem observação",
        format(as.POSIXct(instante, origin = "1970-01-01"), "%d/%m %H:%M:%S"))
    }
    tabela(setNames(d, c("provedor", "estado na coleta", "pausado", "cota disponível (%)", "modelo",
      "última observação", "observação válida até", "espera registrada (s)", "motivo")))
  })

  output$manchete_dia <- renderUI({
    v <- dados()$validacoes
    hoje_str <- as.character(Sys.Date())
    e <- entregas(v[v$origem != "revisoes", , drop = FALSE])
    e_hoje <- e[as.character(as.Date(e$fim)) == hoje_str, , drop = FALSE]
    e_ap <- e_hoje[e_hoje$aprovada, , drop = FALSE]
    n_hoje <- nrow(e_hoje)
    taxa_1a <- if (nrow(e_ap) > 0) round(100 * mean(e_ap$primeira)) else NA

    t_ent <- if (n_hoje > 0) {
      if (!is.na(taxa_1a)) sprintf("%d entrega(s) concluída(s) hoje com %d%% de aprovação na 1ª rodada.", n_hoje, taxa_1a)
      else sprintf("%d entrega(s) em andamento hoje.", n_hoje)
    } else {
      "Sem entregas finalizadas hoje até o momento."
    }

    div(class = "alert alert-primary mb-3 shadow-sm border-0",
        style = "background-color: var(--bs-secondary-bg); border-left: 4px solid var(--bs-primary) !important;",
        div(class = "d-flex align-items-center",
            bsicons::bs_icon("speedometer2", class = "fs-3 text-primary me-3 flex-shrink-0"),
            div(
              h6(class = "mb-1 fw-bold", "Diagnóstico Operacional do Dia"),
              p(class = "mb-0 text-body", t_ent)
            )
        )
    )
  })

  observe({
    d <- dados()
    registros <- unlist(d$subagentes$registros, recursive = FALSE)
    projetos <- sort(unique(c(d$validacoes$projeto, d$mensagens$projeto, d$eventos$projeto,
      d$consumo$projeto, vapply(registros, function(x) if (is.null(x$projeto)) "" else x$projeto, ""),
      vapply(d$orquestracao$projetos, function(x) x$projeto, ""))))
    agentes <- sort(unique(c(d$validacoes$autor, d$eventos$agente, d$sessoes$agente)))
    ent <- entregas(d$validacoes)
    for (campo in c("executor", "origem", "modelo", "provedor", "papel")) {
      id <- if (campo == "executor") campo else paste0(campo, "_consumo")
      escolhas <- sort(unique(c(d$consumo[[campo]], d$chamadas[[campo]])))
      updateSelectizeInput(session, id, choices = escolhas[!is.na(escolhas) & nzchar(escolhas)], selected = isolate(input[[id]]))
    }
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
                       text = ~entrega, colors = c(paleta()[["claude"]], paleta()[["codex"]])) |>
         plotly::layout(showlegend = FALSE),
       "", "linhas (+ e -)")
  })
  output$a_diff_cob <- renderUI(cobertura_ui(cobertura(ent()$fim[ent()$aprovada & !is.na(ent()$diff)])))

  # B. Consumo
  motores <- reactive({
    d <- filtrar(no_periodo(dados()$consumo), agente = "executor")
    for (campo in c("executor", "origem", "modelo", "provedor", "papel")) {
      id <- if (campo == "executor") campo else paste0(campo, "_consumo")
      if (length(input[[id]])) d <- d[d[[campo]] %in% input[[id]], , drop = FALSE]
    }
    d
  })
  output$b_motores <- DT::renderDT(tabela(resumo_motores(motores())))
  output$b_motores_area <- renderUI({
    d <- consumo_motores_diario(motores())
    n <- if (nrow(d)) length(unique(paste(d$executor, d$origem, d$modelo))) else 0
    altura <- if (n > 4) ceiling(n / 2) * 240 else 320
    plotly::plotlyOutput("b_motores_dia", height = altura)
  })
  # Título: Evolução diária do consumo de saída por executor e modelo
  # Fonte: consumo.parquet. Lacunas indicam dias sem medida.
  output$b_motores_dia <- plotly::renderPlotly({
    d <- consumo_motores_diario(motores())
    if (!nrow(d) || !any(is.finite(d$saida))) return(vazio())
    d$serie <- paste(d$executor, d$origem, d$modelo, sep = " · ")
    d$dica <- paste(esc(d$serie), "<br>", d$dia, "<br>Saída:", milhar(d$saida),
                    "<br>Com medida:", d$com_saida, "de", d$registros)
    d <- do.call(rbind, lapply(split(d, d$serie), function(g) {
      dias <- seq(min(as.Date(g$dia)), max(as.Date(g$dia)), by = "day")
      completo <- merge(data.frame(dia = as.character(dias)), g, by = "dia", all.x = TRUE)
      completo$serie <- g$serie[1]
      completo$executor <- g$executor[1]
      completo
    }))
    series <- sort(unique(d$serie))
    dias_eixo <- sort(unique(as.Date(d$dia)))
    if (length(dias_eixo) > 6) {
      dias_eixo <- dias_eixo[unique(round(seq(1, length(dias_eixo), length.out = 6)))]
    }
    eixo_dias <- list(tickmode = "array", tickvals = as.character(dias_eixo),
                      ticktext = format(dias_eixo, "%d/%m"))
    if (length(series) <= 4) {
      cores_series <- vapply(series, function(nome) {
        motor <- d$executor[match(nome, d$serie)]
        unname(paleta()[if (motor %in% names(paleta())) motor else "desconhecido"])
      }, "")
      p <- plotly::plot_ly(d, x = ~as.Date(dia), y = ~saida, color = ~serie, colors = cores_series,
        symbol = ~serie, symbols = c("circle", "square", "diamond", "triangle-up"),
        type = "scatter", mode = "lines+markers", connectgaps = FALSE, text = ~dica, hoverinfo = "text")
      if (length(series) == 1) {
        ponta <- tail(d[is.finite(d$saida), ], 1)
        p <- plotly::add_text(p, data = ponta, x = ~as.Date(dia), y = ~saida, text = esc(series),
          cliponaxis = FALSE, textposition = "top left", textfont = list(color = aparencia()$texto),
          inherit = FALSE, showlegend = FALSE)
      }
      pl(p |> plotly::layout(showlegend = length(series) > 1, xaxis = eixo_dias), "", "tokens de saída")
    } else {
      partes <- lapply(series, function(nome) {
        g <- d[d$serie == nome, ]
        g <- g[order(g$dia), ]
        motor <- if (g$executor[1] %in% names(paleta())) g$executor[1] else "desconhecido"
        p <- plotly::plot_ly(g, x = ~as.Date(dia), y = ~saida, type = "scatter", mode = "lines+markers",
          text = ~dica, hoverinfo = "text", name = nome, connectgaps = FALSE,
          line = list(color = unname(paleta()[motor])), marker = list(color = unname(paleta()[motor])))
        pl(p |> plotly::layout(xaxis = eixo_dias, showlegend = FALSE,
          yaxis = list(range = c(0, max(d$saida, na.rm = TRUE) * 1.08))), "", "tokens de saída")
      })
      partes <- lapply(seq_along(partes), function(i) partes[[i]] |>
        plotly::layout(annotations = list(list(text = esc(series[i]), x = 0, y = 1.08,
          xref = "paper", yref = "paper", showarrow = FALSE, xanchor = "left"))))
      plotly::subplot(partes, nrows = ceiling(length(partes) / 2), margin = 0.06,
                      shareX = FALSE, shareY = TRUE, titleY = TRUE)
    }
  })
  output$b_motores_cob <- renderUI({
    d <- motores()
    div(cobertura_ui(cobertura(d$data)),
        p(class = "cobertura", "Fonte: consumo.parquet. Lacunas indicam falta de medida. Tokens não medem custo."))
  })
  output$b_local <- DT::renderDT(tabela(desempenho_local(motores())))
  # Título: Velocidade de geração dos modelos locais
  # Fonte: chamadas Ollama com tokens e duração de geração registrados.
  output$b_local_grafico <- plotly::renderPlotly({
    d <- desempenho_local(motores())
    if (!nrow(d) || !any(is.finite(d$tokens_s))) return(vazio())
    d <- d[order(d$tokens_s, na.last = TRUE), ]
    d$dica <- paste(esc(d$modelo), "<br>Tokens/s:", format(round(d$tokens_s, 1), decimal.mark = ","),
                    "<br>Chamadas com medida:", d$com_tempo_geracao, "de", d$registros)
    pl(plotly::plot_ly(d, x = ~tokens_s, y = ~modelo, type = "bar", orientation = "h", text = ~dica,
      hoverinfo = "text", marker = list(color = unname(paleta()["ollama"]))) |>
      plotly::layout(xaxis = list(rangemode = "tozero", nticks = 8, gridcolor = aparencia()$grade),
        yaxis = list(categoryorder = "array", categoryarray = d$modelo, showgrid = FALSE)),
      "tokens por segundo de geração", "")
  })
  fontes <- reactive({
    d <- tabela_lista(dados()$fontes,
      c("fonte", "origem", "estado", "atualizado", "ultima_tentativa", "ultimo_dado",
        "registros", "ferramentas", "dados_preservados"))
    carimbos <- base::sub("Z$", "+0000", d$atualizado)
    carimbos <- gsub("([+-][0-9]{2}):([0-9]{2})$", "\\1\\2", carimbos)
    instantes <- as.POSIXct(carimbos, format = "%Y-%m-%dT%H:%M:%OS%z", tz = "UTC")
    minutos <- round(pmax(0, as.numeric(difftime(Sys.time(), instantes, units = "mins"))))
    d$idade <- ifelse(is.na(minutos), "sem data válida", as.character(minutos))
    names(d) <- c("fonte", "origem", "estado", "última coleta válida", "última tentativa",
                  "último registro", "consumo", "ferramentas", "dados preservados", "idade (min)")
    d
  })
  output$b_fontes <- DT::renderDT(tabela(fontes()))
  output$situacao_fontes <- renderUI({
    d <- tabela_lista(dados()$fontes, c("fonte", "estado", "atualizado", "ultima_tentativa"))
    falhas <- sum(d$estado == "erro", na.rm = TRUE)
    classe <- if (falhas) "alert alert-warning" else "alert alert-secondary"
    div(class = classe,
        sprintf("%d fonte(s) com dados; %d sem dados; %d com erro.",
                sum(d$estado == "ok", na.rm = TRUE), sum(d$estado == "sem_dados", na.rm = TRUE), falhas),
        if (falhas) p("Os dados anteriores dessas fontes podem estar preservados. Confira a última coleta válida em Consumo de modelos."))
  })
  output$b_ferramentas <- DT::renderDT({
    d <- filtrar(no_periodo(dados()$chamadas), agente = "executor")
    for (campo in c("executor", "origem", "modelo", "provedor", "papel")) {
      id <- if (campo == "executor") campo else paste0(campo, "_consumo")
      if (length(input[[id]])) d <- d[d[[campo]] %in% input[[id]], , drop = FALSE]
    }
    if (!nrow(d)) return(tabela(data.frame()))
    tabela(aggregate(list(chamadas = rep(1L, nrow(d))),
       d[c("executor", "origem", "ferramenta", "resultado")], sum))
  })
  # Por dia: os dias antigos só existem somados (JANGADA_PAINEL_RETENCAO).
  msg <- reactive({
    d <- consumo_diario(dados()$mensagens, dados()$mensagens_dias)
    filtrar(no_periodo(d[!d$modelo %in% "<synthetic>", , drop = FALSE], "dia"))
  })
  soma <- function(col) sum(msg()[[col]], na.rm = TRUE)

  output$insight_consumo <- renderUI({
    m <- motores()
    div(class = "alert alert-secondary py-2 px-3 mb-3",
        sprintf("%d registros no período; %d com saída medida. Fontes e modelos aparecem separados para preservar a cobertura e a origem do consumo.",
                nrow(m), sum(is.finite(m$saida))))
  })
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
    for (s in list(c("cache_criado", "cache criado", paleta()[["codex"]]), c("saida_texto", "saída", paleta()[["claude"]]),
                   c("raciocinio", "raciocínio", aparencia()$raciocinio), c("entrada", "entrada nova", aparencia()$neutra))) {
      p <- plotly::add_bars(p, y = a[[s[1]]], name = s[2], marker = list(color = s[3]))
    }
    pl(plotly::layout(p, barmode = "stack"), "", "tokens")
  })
  output$b_lido <- plotly::renderPlotly({
    m <- msg()
    if (!nrow(m)) return(vazio())
    a <- aggregate(m["cache_lido"], list(dia = as.Date(m$dia)), sum)
    pl(plotly::plot_ly(a, x = ~dia, y = ~cache_lido, type = "bar", marker = list(color = aparencia()$neutra), name = "cache lido"),
       "", "tokens")
  })
  output$b_blocos <- plotly::renderPlotly({
    b <- blocos()
    if (!nrow(b)) return(vazio())
    a <- aggregate(list(blocos = rep(1, nrow(b)), perto = as.integer(b$perto_limite)), list(semana = b$semana), sum)
    pl(plotly::plot_ly(a, x = ~semana) |>
         plotly::add_bars(y = ~ (blocos - perto), name = "longe do limite", marker = list(color = aparencia()$neutra)) |>
         plotly::add_bars(y = ~perto, name = "perto do limite", marker = list(color = paleta()[["codex"]])) |>
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

  output$insight_tempo <- renderUI({
    s <- dados()$sessoes
    if (!nrow(s)) return(NULL)
    par <- paradas()
    n_par <- nrow(par)
    texto_par <- if (n_par > 0) sprintf("Atenção: %d sessão(ões) abertas sem entrega há mais de 3 dias.", n_par)
                 else "Nenhuma sessão estagnada no momento."
    div(class = "alert alert-secondary py-2 px-3 mb-3",
        paste("Distribuição de tempo em aguardando e trocas de contexto.", texto_par))
  })

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
    pl(plotly::plot_ly(a, x = ~dia, y = ~horas, type = "bar", marker = list(color = paleta()[["codex"]])), "", "horas")
  })
  output$c_simult <- plotly::renderPlotly({
    s <- simultaneas_por_hora(iv())
    if (!nrow(s)) return(vazio())
    pl(plotly::plot_ly(s, x = ~hora, y = ~sessoes, type = "scatter", mode = "lines",
                       line = list(shape = "hv", color = paleta()[["claude"]])), "", "sessões")
  })
  output$c_foco <- plotly::renderPlotly({
    if (!nrow(foco())) return(vazio())
    pl(plotly::plot_ly(foco(), x = ~dia, y = ~trocas, type = "bar", marker = list(color = paleta()[["claude"]])), "", "trocas")
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

  output$insight_gargalos <- renderUI({
    q <- quentes()
    multi <- if (nrow(q)) sum(q$sessoes > 1) else 0
    cicl <- ciclos()
    n_cicl <- if (!is.null(cicl)) nrow(cicl) else 0

    alerta_multi <- if (multi > 0) {
      sprintf("Alerta de atrito: %d arquivo(s) foram editados concorrentemente por mais de uma sessão. Isole em worktrees individuais (jangada-agente).", multi)
    } else {
      "Nenhum conflito de edição concorrente entre sessões."
    }
    div(class = "alert alert-secondary py-2 px-3 mb-3",
        sprintf("Registrados %d ciclos de retrabalho edit-test-edit no período. %s", n_cicl, alerta_multi))
  })
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
  # Título: Delegações atendidas por destino
  # Fonte: delegacoes.jsonl, filtrado por período e projeto.
  output$e_destinos <- plotly::renderPlotly({
    destinos <- sub()$destinos
    if (!length(destinos)) return(vazio())
    d <- data.frame(destino = names(destinos), quantidade = as.numeric(unlist(destinos)))
    d <- d[order(d$quantidade), ]
    motor <- ifelse(d$destino == "local", "ollama",
                    ifelse(d$destino == "codex-economico", "codex", d$destino))
    cor <- unname(paleta()[motor])
    cor[is.na(cor)] <- aparencia()$neutra
    d$destino <- ifelse(d$destino == "codex-economico", "Codex econômico", d$destino)
    pl(plotly::plot_ly(d, x = ~quantidade, y = ~destino, type = "bar", orientation = "h",
      marker = list(color = cor), text = ~quantidade, textposition = "outside",
      textfont = list(color = aparencia()$texto), hoverinfo = "x+y") |>
      plotly::layout(xaxis = list(rangemode = "tozero", dtick = max(1, ceiling(max(d$quantidade) / 7)),
        nticks = 8, gridcolor = aparencia()$grade),
        yaxis = list(categoryorder = "array", categoryarray = d$destino, showgrid = FALSE),
        showlegend = FALSE), "delegações atendidas", "")
  })
  output$insight_subagentes <- renderUI({
    s <- sub()
    if (is.null(s)) return(NULL)
    if (!is.null(s$erro)) return(div(class = "alert alert-warning", s$erro))
    f <- s$fracao_agy
    fracao <- if (!is.null(f)) pc(f$fracao_agy_pct) else "-"
    recusas <- if (!is.null(f)) pc(f$taxa_recusa_pct) else "-"
    desvios <- sum(lengths(s$desvios))

    div(class = "alert alert-secondary py-2 px-3 mb-3",
        sprintf("No período e projeto selecionados: %s de encaminhamento ao agy e %s de recusas. Desvios registrados: %s.",
                fracao, recusas, desvios))
  })
  output$e_fracao <- renderText(pc(sub()$fracao_agy$fracao_agy_pct))
  output$e_fracao_n <- renderText({
    f <- sub()$fracao_agy
    # Com erro, o coletor grava só o erro, e os outros quadros ficam em "-".
    if (!is.null(sub()$erro)) paste0("indicadores não calculados na coleta de ", sub()$data, ": ", sub()$erro) else
    if (is.null(f)) "sem registro" else
      paste0(f$delegadas_agy, " delegação(ões) ao agy; ", f$delegadas_local,
        " local(is); ", f$delegadas_codex_economico, " ao Codex econômico; ",
        f$subagentes_claude, " subagente(s) do Claude e ", f$subagentes_agy, " do agy")
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
  output$e_desvios <- renderText(if (!is.null(sub()$erro)) "-" else sum(lengths(sub()$desvios)))
  output$e_desvios_n <- renderText({
    d <- sub()$desvios
    if (is.null(d)) "-" else paste(paste(base::sub("_", " ", names(d)), lengths(d)), collapse = ", ")
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
    fontes <- if (is.null(q$por_destino)) list("subagentes do Claude" = q$claude, "delegações registradas" = q$delegacoes) else
      list("subagentes do Claude" = q$claude, "delegações ao agy" = q$por_destino$agy,
           "delegações locais" = q$por_destino$local, "Codex econômico" = q$por_destino$`codex-economico`)
    tabela(do.call(rbind, lapply(names(fontes), function(nome) {
      x <- fontes[[nome]]
      data.frame(origem = nome, relatorios = num_ou_na(x$n), sem_fonte = num_ou_na(x$total), mediana = num_ou_na(x$mediana))
    })))
  })
}

shinyApp(ui, server)
