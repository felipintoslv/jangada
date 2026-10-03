# Indicadores do jangada-painel, calculados sobre o cache em Parquet que o
# coletor.py grava. Funções puras: recebem tabelas e devolvem tabelas, para o
# app e os testes usarem as mesmas definições.

POUCO_DADO <- 10

# O visNetwork põe o title do nó em innerHTML. Nomes de arquivo, sessão, pasta
# e ferramenta vêm de registros que o agente isolado grava, então passam por
# aqui antes de entrar no HTML.
esc <- function(x) htmltools::htmlEscape(as.character(x))

# O app escuta só em 127.0.0.1, mas uma página qualquer aberta no navegador
# alcança a porta: direto, com Origin de fora, ou por DNS rebinding, com Host
# de fora. Vale a sessão cujo Host é local e cuja Origin, quando vem, é o
# próprio Host. Sem Host (shiny::testServer), não há pedido HTTP a conferir.
origem_local <- function(host, origem = NULL) {
  if (is.null(host)) return(TRUE)
  nome <- sub(":[0-9]+$", "", tolower(host))
  if (!nome %in% c("127.0.0.1", "localhost")) return(FALSE)
  is.null(origem) || !nzchar(origem) || tolower(origem) == paste0("http://", tolower(host))
}

# O agente isolado também alcança a porta, e com Host local. A sessão só abre
# com o token do arquivo CHAVE na URL (?token=), que o jangada-painel passa
# ao navegador e o jangada-isolar oculta. Sem o arquivo, nenhuma sessão abre.
# Sem Host (shiny::testServer), não há pedido HTTP a conferir.
token_certo <- function(host, busca, chave) {
  if (is.null(host)) return(TRUE)
  esperado <- tryCatch(suppressWarnings(readLines(chave, n = 1, warn = FALSE)),
                       error = function(e) "")
  recebido <- if (is.character(busca) && length(busca) == 1) shiny::parseQueryString(busca)$token
  length(esperado) == 1 && nchar(esperado) >= 32 && identical(recebido, esperado)
}

# Lê o cache. Tabela ausente vira tabela vazia com as colunas certas.
carregar_cache <- function(cache) {
  ler <- function(nome, vazia) {
    caminho <- file.path(cache, nome)
    ok <- if (dir.exists(caminho)) length(list.files(caminho, "\\.parquet$")) > 0 else file.exists(caminho)
    if (!ok) return(vazia)
    d <- if (dir.exists(caminho)) as.data.frame(arrow::open_dataset(caminho)) else as.data.frame(arrow::read_parquet(caminho))
    for (col in setdiff(names(vazia), names(d))) d[[col]] <- rep(vazia[[col]][NA_integer_], nrow(d))
    for (col in names(d)) if (inherits(d[[col]], "POSIXct")) attr(d[[col]], "tzone") <- ""
    # Uma compactação interrompida deixa a mesma linha em duas partes da pasta;
    # a próxima compactação do coletor desfaz, e até lá a leitura descarta.
    if ("id" %in% names(d)) d <- d[!duplicated(d$id), , drop = FALSE]
    d
  }
  ts <- as.POSIXct(character())
  list(
    validacoes = ler("validacoes.parquet", data.frame(
      data = ts, dia = character(), projeto = character(), rotulo = character(),
      rodada = integer(), resultado = character(), etapa = character(), revisor = character(),
      modelo = character(), autor = character(), arquivos = integer(), mais = integer(),
      menos = integer(), itens = integer(), segundos = integer(), entrega = character(),
      origem = character())),
    mensagens_dias = ler("mensagens-dias.parquet", data.frame(
      dia = character(), projeto = character(), modelo = character(), respostas = numeric(),
      entrada = numeric(), saida = numeric(), cache_criado = numeric(), cache_lido = numeric(),
      raciocinio = numeric())),
    mensagens = ler("mensagens", data.frame(
      id = character(), data = ts, dia = character(), conversa = character(),
      subagente = character(), projeto = character(), sessao = character(), cwd = character(),
      modelo = character(), entrada = numeric(), saida = numeric(), cache_criado = numeric(),
      cache_lido = numeric(), raciocinio = numeric())),
    ferramentas = ler("ferramentas", data.frame(
      id = character(), data = ts, dia = character(), conversa = character(),
      subagente = character(), projeto = character(), sessao = character(),
      ferramenta = character(), alvo = character(), arquivo = character())),
    resultados = ler("resultados", data.frame(id = character(), data = ts, erro = logical())),
    eventos = ler("eventos.parquet", data.frame(
      data = ts, dia = character(), sessao = character(), projeto = character(),
      agente = character(), estado = character())),
    apontamentos = ler("apontamentos.parquet", data.frame(
      data = ts, dia = character(), projeto = character(), rotulo = character(),
      arquivo = character())),
    sessoes = ler("sessoes.parquet", data.frame(
      sessao = character(), projeto = character(), agente = character(), estado = character(),
      desde = ts, atualizado = ts)),
    pesquisas = ler("pesquisas.parquet", data.frame(
      id = character(), data = ts, dia = character(), sessao = character(), estado = character(),
      par = character(), modo = character(), autor = character(), revisor = character(),
      pergunta = character(), grau_fato = integer(), grau_pescador = integer(),
      veredito = character(), fontes_qtd = integer(), segundos = numeric())),
    consumo = ler("consumo.parquet", data.frame(
      id = character(), data = ts, dia = character(), origem = character(), executor = character(),
      provedor = character(), modelo = character(), sessao = character(), projeto = character(),
      papel = character(), estado = character(), delegacao_id = character(), chamada_id = character(),
      entrada_total = numeric(), cache_lido = numeric(), cache_criado = numeric(),
      saida = numeric(), raciocinio = numeric(), tempo_total_ms = numeric(),
      tempo_carregamento_ms = numeric(), tempo_entrada_ms = numeric(), tempo_geracao_ms = numeric())),
    chamadas = ler("chamadas.parquet", data.frame(
      id = character(), data = ts, dia = character(), origem = character(), executor = character(),
      provedor = character(), modelo = character(), sessao = character(), projeto = character(),
      papel = character(), ferramenta = character(), resultado = character())),
    fontes = tryCatch(jsonlite::read_json(file.path(cache, "cobertura.json")), error = function(e) list()),
    coleta = tryCatch(jsonlite::read_json(file.path(cache, "coleta.json")), error = function(e) list()),
    subagentes = tryCatch(suppressWarnings(jsonlite::read_json(file.path(cache, "subagentes.json"))), error = function(e) list()),
    orquestracao = tryCatch(suppressWarnings(jsonlite::read_json(file.path(cache, "orquestracao.json"))),
                          error = function(e) list(erros = "atualize a coleta para carregar a orquestração"))
  )
}

# Ausência de medida continua ausente, inclusive em um conjunto inteiro sem notas.
soma_medida <- function(x) {
  x <- x[is.finite(x) & x >= 0]
  if (length(x)) sum(x) else NA_real_
}

media_avaliacoes <- function(x) {
  x <- x[is.finite(x) & x >= 0 & x <= 100]
  if (length(x)) round(mean(x)) else NA_real_
}

resumo_motores <- function(d) {
  if (!nrow(d)) return(data.frame())
  grupos <- interaction(d$executor, d$provedor, d$origem, d$modelo, drop = TRUE, lex.order = TRUE)
  partes <- split(d, grupos)
  do.call(rbind, lapply(partes, function(g) data.frame(
    executor = g$executor[1], provedor = g$provedor[1], origem = g$origem[1], modelo = g$modelo[1],
    registros = nrow(g), entrada = soma_medida(g$entrada_total), saida = soma_medida(g$saida),
    cache_lido = soma_medida(g$cache_lido), raciocinio = soma_medida(g$raciocinio),
    com_entrada = sum(is.finite(g$entrada_total)), com_saida = sum(is.finite(g$saida)),
    stringsAsFactors = FALSE)))
}

consumo_motores_diario <- function(d) {
  if (!nrow(d)) return(data.frame())
  do.call(rbind, lapply(split(d, d$dia), function(g)
    cbind(dia = g$dia[1], resumo_motores(g))))
}

desempenho_local <- function(d) {
  d <- d[d$executor == "ollama", , drop = FALSE]
  if (!nrow(d)) return(data.frame())
  do.call(rbind, lapply(split(d, d$modelo), function(g) {
    conhecidos <- is.finite(g$tempo_geracao_ms) & g$tempo_geracao_ms > 0 & is.finite(g$saida) & g$saida >= 0
    velocidades <- 1000 * g$saida[conhecidos] / g$tempo_geracao_ms[conhecidos]
    data.frame(modelo = g$modelo[1], registros = nrow(g), com_tempo_geracao = sum(conhecidos),
               geracao_s = soma_medida(g$tempo_geracao_ms) / 1000,
               carregamento_s = soma_medida(g$tempo_carregamento_ms) / 1000,
               tokens_s = if (any(conhecidos)) 1000 * sum(g$saida[conhecidos]) / sum(g$tempo_geracao_ms[conhecidos]) else NA_real_,
               mediana_tokens_s = if (length(velocidades)) median(velocidades) else NA_real_,
               p95_tokens_s = if (length(velocidades)) unname(quantile(velocidades, .95)) else NA_real_)
  }))
}

# Período coberto e número de observações de um indicador, com o aviso de
# pouco dado abaixo de POUCO_DADO.
cobertura <- function(datas, n = length(datas)) {
  datas <- datas[!is.na(datas)]
  periodo <- if (length(datas)) {
    paste(format(min(datas), "%d/%m/%Y"), "a", format(max(datas), "%d/%m/%Y"))
  } else "sem dado"
  list(periodo = periodo, n = n, pouco = n < POUCO_DADO,
       texto = paste0(periodo, ", ", n, " observação(ões)", if (n < POUCO_DADO) " · pouco dado" else ""))
}

# A. Qualidade da revisão ----------------------------------------------------

# Uma linha por entrega: as rodadas de um rótulo até o APROVADO. A rodada do
# APROVADO é quantas rodadas a entrega levou (como no jangada-validar
# --metricas). Tamanho do diff: o da última rodada.
entregas <- function(v) {
  if (!nrow(v)) {
    return(data.frame(entrega = character(), projeto = character(), rotulo = character(),
                      autor = character(), revisor = character(), par = character(),
                      inicio = as.POSIXct(character()), fim = as.POSIXct(character()),
                      aprovada = logical(), rodadas = integer(), primeira = logical(),
                      limite = logical(), reprovacoes = integer(), diff = numeric(),
                      fora = logical()))
  }
  v <- v[order(v$data), ]
  do.call(rbind, lapply(split(v, v$entrega), function(e) {
    ap <- e[e$resultado == "aprovado", ]
    ult <- e[nrow(e), ]
    aprovada <- nrow(ap) > 0
    autor <- ult$autor; revisor <- ult$revisor
    data.frame(
      entrega = ult$entrega, projeto = ult$projeto, rotulo = ult$rotulo,
      autor = autor, revisor = revisor,
      par = if (nzchar(autor) || nzchar(revisor)) paste0(if (nzchar(autor)) autor else "?", " → ", if (nzchar(revisor)) revisor else "?") else "sem registro",
      inicio = min(e$data), fim = if (aprovada) ap$data[1] else max(e$data),
      aprovada = aprovada,
      rodadas = if (aprovada) ap$rodada[1] else max(e$rodada, na.rm = TRUE),
      primeira = aprovada && isTRUE(ap$rodada[1] == 1),
      limite = any(e$resultado == "limite"),
      reprovacoes = sum(e$resultado == "revisar"),
      diff = if (is.na(ult$mais)) NA_real_ else ult$mais + ult$menos,
      # Revisão feita fora do isolamento (revisoes/), que o agente não altera.
      fora = isTRUE(ult$origem == "revisoes"),
      stringsAsFactors = FALSE)
  }))
}

# Taxa de aprovação na 1ª rodada e rodadas até a aprovação, por grupo. A
# taxa e as rodadas contam só as entregas aprovadas; o limite conta todas.
resumo_aprovacao <- function(ent, por = NULL) {
  if (!nrow(ent)) return(data.frame())
  g <- if (is.null(por)) rep("todos", nrow(ent)) else ent[[por]]
  r <- do.call(rbind, lapply(split(ent, g), function(e) {
    ap <- e[e$aprovada, ]
    data.frame(
      entregas = nrow(e), aprovadas = nrow(ap),
      primeira_pct = if (nrow(ap)) round(100 * mean(ap$primeira)) else NA_real_,
      rodadas_media = if (nrow(ap)) round(mean(ap$rodadas, na.rm = TRUE), 1) else NA_real_,
      rodadas_max = if (nrow(ap)) max(ap$rodadas, na.rm = TRUE) else NA_integer_,
      no_limite = sum(e$limite),
      aviso = if (nrow(ap) < POUCO_DADO) "pouco dado" else "")
  }))
  r <- cbind(grupo = rownames(r), r, stringsAsFactors = FALSE)
  rownames(r) <- NULL
  r[order(-r$entregas), ]
}

# B. Consumo ----------------------------------------------------------------

TIPOS_TOKEN <- c(entrada = "entrada nova", saida = "saída", raciocinio = "raciocínio",
                 cache_criado = "cache criado", cache_lido = "cache lido")

# Consumo por dia, projeto e modelo: as mensagens guardadas em detalhe, uma
# resposta por linha, e os dias que já saíram delas, somados pelo coletor.
consumo_diario <- function(m, dias) {
  cols <- c("dia", "projeto", "modelo", "respostas", names(TIPOS_TOKEN))
  m$respostas <- rep(1, nrow(m))
  d <- rbind(m[cols], dias[cols])
  d$raciocinio[is.na(d$raciocinio)] <- 0
  d
}

consumo_por <- function(m, por) {
  if (!nrow(m)) return(data.frame())
  m$raciocinio[is.na(m$raciocinio)] <- 0
  if (!"respostas" %in% names(m)) m$respostas <- rep(1, nrow(m))
  a <- aggregate(m[c(names(TIPOS_TOKEN), "respostas")], list(grupo = m[[por]]), sum)
  a$total <- a$entrada + a$saida + a$cache_criado + a$cache_lido
  a$lido_pct <- round(100 * a$cache_lido / pmax(a$total, 1))
  names(a)[1] <- por
  a[order(-a$saida), ]
}

# Blocos de 5 horas, com a regra do ccusage e do jangada-consumo: o bloco
# começa na hora cheia da primeira resposta e dura 5 horas; uma pausa de 5
# horas também abre bloco novo. Só as conversas principais e os subagentes
# do Claude; o <synthetic> não é resposta do modelo.
blocos_5h <- function(m) {
  m <- m[m$modelo != "<synthetic>", ]
  if (!nrow(m)) return(data.frame())
  m <- m[order(m$data), ]
  t <- as.numeric(m$data)
  janela <- 5 * 3600
  bloco <- integer(nrow(m)); ini <- NA_real_; ult <- NA_real_; b <- 0L
  for (i in seq_along(t)) {
    if (is.na(ini) || t[i] - ini > janela || t[i] - ult > janela) {
      b <- b + 1L
      ini <- floor(t[i] / 3600) * 3600
    }
    bloco[i] <- b; ult <- t[i]
  }
  m$bloco <- bloco
  r <- aggregate(m[c("entrada", "saida", "cache_criado", "cache_lido")], list(bloco = m$bloco), sum)
  r$inicio <- as.POSIXct(tapply(t, m$bloco, function(x) floor(min(x) / 3600) * 3600)[as.character(r$bloco)], origin = "1970-01-01")
  r$respostas <- as.vector(table(m$bloco)[as.character(r$bloco)])
  r$semana <- format(r$inicio, "%G-S%V")
  # Os registros não trazem o limite do plano. "Perto do limite" é um bloco com
  # pelo menos 80% da saída do maior bloco observado.
  r$perto_limite <- r$saida >= 0.8 * max(r$saida)
  r
}

# Tokens por entrega aprovada: as respostas da sessão da entrega (a sessão do
# jangada vem da pasta da conversa) entre o fim da entrega anterior do mesmo
# rótulo e o APROVADO. Sem entrega anterior, a janela começa 24 horas antes
# da primeira rodada, para não somar o histórico inteiro da pasta.
tokens_por_entrega <- function(ent, m) {
  ap <- ent[ent$aprovada, ]
  if (!nrow(ap) || !nrow(m)) return(data.frame())
  ap <- ap[order(ap$rotulo, ap$fim), ]
  todas <- ent[order(ent$rotulo, ent$fim), ]
  r <- lapply(seq_len(nrow(ap)), function(i) {
    e <- ap[i, ]
    antes <- todas[todas$rotulo == e$rotulo & todas$fim < e$fim, ]
    de <- if (nrow(antes)) max(antes$fim) else e$inicio - 24 * 3600
    sel <- m$sessao == e$rotulo & m$data > de & m$data <= e$fim
    if (!any(sel)) return(NULL)
    data.frame(entrega = e$entrega, projeto = e$projeto, fim = e$fim, primeira = e$primeira,
               respostas = sum(sel), saida = sum(m$saida[sel]), cache_criado = sum(m$cache_criado[sel]),
               total = sum(m$entrada[sel] + m$saida[sel] + m$cache_criado[sel] + m$cache_lido[sel]))
  })
  do.call(rbind, r)
}

# C. Tempo e atenção -----------------------------------------------------------

# Intervalos de estado por sessão: cada evento vale até o próximo evento de
# estado da mesma sessão (o foco e os subagentes não mudam o estado); o
# último vale até agora, mas nunca além de 12 horas, para uma sessão
# esquecida não inflar a conta.
intervalos_estado <- function(ev, agora = Sys.time()) {
  ev <- ev[ev$estado != "foco" & !startsWith(ev$estado, "subagente"), ]
  if (!nrow(ev)) return(data.frame())
  ev <- ev[order(ev$sessao, ev$data), ]
  do.call(rbind, lapply(split(ev, ev$sessao), function(s) {
    fim <- c(s$data[-1], min(agora, s$data[nrow(s)] + 12 * 3600))
    data.frame(sessao = s$sessao, projeto = s$projeto, agente = s$agente, estado = s$estado,
               ini = s$data, fim = fim)
  }))
}

# Segundos em um estado, por dia (o intervalo é cortado na meia-noite).
tempo_por_dia <- function(iv, estado = "aguardando") {
  iv <- iv[iv$estado == estado & iv$fim > iv$ini, ]
  if (!nrow(iv)) return(data.frame(dia = as.Date(character()), horas = numeric()))
  partes <- do.call(rbind, lapply(seq_len(nrow(iv)), function(i) {
    a <- iv$ini[i]; b <- iv$fim[i]; out <- NULL
    while (a < b) {
      # Meia-noite local seguinte; as.POSIXct(Date) daria a meia-noite em UTC.
      meia_noite <- as.POSIXct(paste(as.Date(format(a, "%Y-%m-%d")) + 1, "00:00:00"))
      c2 <- min(b, meia_noite)
      out <- rbind(out, data.frame(dia = as.Date(format(a, "%Y-%m-%d")), s = as.numeric(c2) - as.numeric(a)))
      a <- c2
    }
    out
  }))
  r <- aggregate(partes["s"], partes["dia"], sum)
  data.frame(dia = r$dia, horas = round(r$s / 3600, 2))
}

# Sessões ativas (trabalhando ou aguardando) em cada hora.
simultaneas_por_hora <- function(iv) {
  iv <- iv[iv$estado %in% c("trabalhando", "aguardando") & iv$fim > iv$ini, ]
  if (!nrow(iv)) return(data.frame(hora = as.POSIXct(character()), sessoes = integer()))
  horas <- do.call(rbind, lapply(seq_len(nrow(iv)), function(i) {
    h <- seq(trunc(iv$ini[i], "hours"), iv$fim[i], by = 3600)
    data.frame(hora = as.POSIXct(h), sessao = iv$sessao[i])
  }))
  horas <- unique(horas)
  r <- aggregate(list(sessoes = horas$sessao), list(hora = horas$hora), length)
  r[order(r$hora), ]
}

# Sessões abertas há mais de N dias sem entrega aprovada no período.
sessoes_paradas <- function(sess, ent, dias = 3, agora = Sys.time()) {
  if (!nrow(sess)) return(data.frame())
  ult <- if (any(ent$aprovada)) tapply(ent$fim[ent$aprovada], ent$rotulo[ent$aprovada], max) else numeric()
  sess$ultima_aprovacao <- as.POSIXct(ult[sess$sessao], origin = "1970-01-01")
  ref <- ifelse(is.na(sess$ultima_aprovacao), as.numeric(sess$desde), as.numeric(sess$ultima_aprovacao))
  sess$dias_sem_entrega <- round((as.numeric(agora) - ref) / 86400, 1)
  sess[!is.na(sess$dias_sem_entrega) & sess$dias_sem_entrega > dias,
       c("sessao", "projeto", "agente", "estado", "desde", "ultima_aprovacao", "dias_sem_entrega")]
}


# D. Redes -----------------------------------------------------------------------

EDICAO <- c("Edit", "Write", "NotebookEdit", "MultiEdit")

slug <- function(x) {
  x <- tolower(iconv(x, "UTF-8", "ASCII//TRANSLIT", sub = ""))
  gsub("^-+|-+$", "", gsub("[^a-z0-9_-]+", "-", x))
}

# Caminho de arquivo sem a parte da máquina: "repo/caminho" para arquivos de
# um projeto ou de uma worktree do jangada (a mesma tarefa em paralelo vira
# o mesmo arquivo), "~/..." para o resto.
normalizar_arquivo <- function(x,
                               projetos = Sys.getenv("JANGADA_PROJETOS", path.expand("~/Projetos")),
                               worktrees = Sys.getenv("JANGADA_WORKTREES", path.expand("~/.local/share/jangada-worktrees"))) {
  sem <- function(x, pre) ifelse(startsWith(x, pre), substring(x, nchar(pre) + 1), NA_character_)
  w <- sem(x, paste0(sub("/$", "", worktrees), "/"))
  w <- ifelse(is.na(w), NA_character_, sub("^([^/]+)/[^/]+/", "\\1/", w))
  p <- sem(x, paste0(sub("/$", "", projetos), "/"))
  casa <- sem(x, paste0(path.expand("~"), "/"))
  ifelse(!is.na(w), w, ifelse(!is.na(p), p, ifelse(!is.na(casa), paste0("~/", casa), x)))
}

# Chave para cruzar um arquivo editado com um arquivo citado num parecer:
# projeto (em slug) e caminho dentro do repositório.
chave_arquivo <- function(norm) {
  ifelse(grepl("^~|^/", norm), norm, paste0(slug(sub("/.*", "", norm)), "/", sub("^[^/]+/", "", norm)))
}

# Chamadas de ferramenta com o resultado, em ordem dentro de cada conversa
# (o subagente tem a própria sequência).
chamadas <- function(f, r) {
  f$erro <- r$erro[match(f$id, r$id)] %in% TRUE
  f$fio <- paste(f$conversa, f$subagente)
  f[order(f$fio, f$data), ]
}

# Ciclos de retrabalho: editar F, rodar os testes e falhar, editar F de novo.
# Um teste que passa limpa a pendência; outras ferramentas não mudam nada.
ciclos_retrabalho <- function(ch) {
  vazio <- data.frame(conversa = character(), projeto = character(), sessao = character(),
                      arquivo = character(), data = as.POSIXct(character()))
  ch <- ch[(ch$ferramenta %in% EDICAO & nzchar(ch$arquivo)) | (ch$ferramenta == "Bash" & ch$alvo == "testes"), ]
  if (!nrow(ch)) return(vazio)
  achados <- lapply(split(seq_len(nrow(ch)), ch$fio), function(ix) {
    editados <- character(); falhos <- character(); out <- integer(); arq <- character()
    for (i in ix) {
      if (ch$ferramenta[i] == "Bash") {
        falhos <- if (ch$erro[i]) union(falhos, editados) else character()
        editados <- character()
      } else {
        a <- ch$arquivo[i]
        if (a %in% falhos) { out <- c(out, i); arq <- c(arq, a); falhos <- setdiff(falhos, a) }
        editados <- union(editados, a)
      }
    }
    out
  })
  i <- unlist(achados, use.names = FALSE)
  if (!length(i)) return(vazio)
  data.frame(conversa = ch$conversa[i], projeto = ch$projeto[i], sessao = ch$sessao[i],
             arquivo = normalizar_arquivo(ch$arquivo[i]), data = ch$data[i], stringsAsFactors = FALSE)
}

# Grupo de um nó do grafo de transições, para a cor.
grupo_no <- function(ferramenta, alvo) {
  ifelse(ferramenta %in% EDICAO, "edição",
    ifelse(ferramenta == "Bash" & alvo == "testes", "teste",
      ifelse(ferramenta %in% c("Read", "Grep", "Glob") | alvo == "busca", "leitura e busca",
        ifelse(ferramenta == "Bash", "shell", "outra"))))
}

# Grafo de transição entre chamadas: nó = ferramenta + alvo resumido, aresta =
# uma chamada seguida da outra na mesma conversa. Poda: os max_nos nós mais
# usados e as arestas com peso mínimo; as métricas vêm do igraph.
rede_transicoes <- function(ch, max_nos = 40, peso_min = 2, destaque = character()) {
  if (nrow(ch) < 2) return(NULL)
  no <- ifelse(nzchar(ch$alvo), paste(ch$ferramenta, ch$alvo), ch$ferramenta)
  n <- length(no)
  mesmo <- ch$fio[-1] == ch$fio[-n]
  e <- data.frame(from = no[-n][mesmo], to = no[-1][mesmo], stringsAsFactors = FALSE)
  e <- e[e$from != e$to, ]
  uso <- sort(table(no), decreasing = TRUE)
  manter <- names(uso)[seq_len(min(max_nos, length(uso)))]
  e <- e[e$from %in% manter & e$to %in% manter, ]
  if (!nrow(e)) return(NULL)
  e <- aggregate(list(peso = rep(1L, nrow(e))), e, sum)
  e <- e[e$peso >= peso_min, ]
  if (!nrow(e)) return(NULL)
  ids <- unique(c(e$from, e$to))
  g <- igraph::graph_from_data_frame(e, directed = TRUE, vertices = data.frame(name = ids))
  entre <- igraph::betweenness(g, weights = 1 / e$peso)
  prim <- match(ids, no)
  nos <- data.frame(id = ids, label = ids, value = as.numeric(uso[ids]),
                    group = grupo_no(ch$ferramenta[prim], ch$alvo[prim]),
                    title = sprintf("%s<br>%d chamada(s)<br>intermediação: %.0f", esc(ids), as.integer(uso[ids]), entre[ids]),
                    stringsAsFactors = FALSE)
  nos$group[nos$group == "edição" & sub("^\\S+ ", "", nos$id) %in% destaque] <- "edição com retrabalho"
  list(nos = nos, arestas = data.frame(from = e$from, to = e$to, value = e$peso,
                                       title = paste(e$peso, "vez(es)"), arrows = "to"), grafo = g)
}

# Pontos quentes: grafo bipartido sessão × arquivo editado. A sessão é a do
# jangada (repo ou repo--tarefa); sem ela, a conversa.
edicoes <- function(ch) {
  # Rascunhos em /tmp não são arquivos do projeto.
  ed <- ch[ch$ferramenta %in% EDICAO & nzchar(ch$arquivo) & !startsWith(ch$arquivo, "/tmp/"), ]
  ed$quem <- ifelse(nzchar(ed$sessao), ed$sessao, substr(ed$conversa, 1, 8))
  ed$arq <- normalizar_arquivo(ed$arquivo)
  ed
}

pontos_quentes <- function(ed, apont = NULL) {
  if (!nrow(ed)) return(data.frame())
  a <- do.call(rbind, lapply(split(ed, ed$arq), function(x)
    data.frame(arquivo = x$arq[1], sessoes = length(unique(x$quem)), conversas = length(unique(x$conversa)),
               edicoes = nrow(x), ultima = max(x$data), stringsAsFactors = FALSE)))
  if (!is.null(apont) && nrow(apont)) {
    k <- table(paste0(apont$projeto, "/", apont$arquivo))
    a$revisar <- as.integer(k[chave_arquivo(a$arquivo)])
    a$revisar[is.na(a$revisar)] <- 0L
  } else {
    a$revisar <- 0L
  }
  rownames(a) <- NULL
  a[order(-a$sessoes, -a$edicoes), ]
}

rede_pontos_quentes <- function(ed, max_nos = 40) {
  if (!nrow(ed)) return(NULL)
  pq <- pontos_quentes(ed)
  # Arquivos primeiro pelos de mais sessões; cada arquivo traz as suas sessões.
  arqs <- character(); sess <- character()
  for (f in pq$arquivo) {
    novas <- setdiff(unique(ed$quem[ed$arq == f]), sess)
    if (length(arqs) + length(sess) + 1 + length(novas) > max_nos && length(arqs)) break
    arqs <- c(arqs, f); sess <- c(sess, novas)
  }
  x <- ed[ed$arq %in% arqs, ]
  e <- aggregate(list(value = rep(1L, nrow(x))), list(from = x$quem, to = x$arq), sum)
  g <- igraph::graph_from_data_frame(e, directed = FALSE)
  grau <- igraph::degree(g)
  nos <- rbind(
    data.frame(id = sess, label = sess, group = "sessão", shape = "square", value = 1,
               title = paste(esc(sess), "<br>", grau[sess], "arquivo(s)"), stringsAsFactors = FALSE),
    data.frame(id = arqs, label = basename(arqs), group = ifelse(grau[arqs] > 1, "arquivo em várias sessões", "arquivo"),
               shape = "dot", value = grau[arqs], title = paste(esc(arqs), "<br>", grau[arqs], "sessão(ões)"),
               stringsAsFactors = FALSE))
  list(nos = nos, arestas = data.frame(from = e$from, to = e$to, value = e$value, title = paste(e$value, "edição(ões)")),
       grafo = g)
}

# Capacidade de uma chamada, para o espaço de ferramentas: a ferramenta, com
# o nome da skill, o tipo do subagente, o servidor MCP ou o tipo do comando.
capacidade <- function(ferramenta, alvo) {
  mcp <- grepl("^mcp__", ferramenta)
  ifelse(mcp, paste("mcp", sub("^mcp__(.+?)__.*$", "\\1", ferramenta, perl = TRUE)),
    ifelse(ferramenta == "Skill", paste("skill", alvo),
      ifelse(ferramenta %in% c("Agent", "Task"), paste("subagente", alvo),
        ifelse(ferramenta == "Bash", paste("Bash", alvo), ferramenta))))
}

# Espaço de capacidades, como o Product Space (Hidalgo e Hausmann): vantagem
# relativa (RCA) de cada projeto em cada capacidade, M = RCA >= 1, e
# proximidade entre capacidades i e j = projetos com vantagem nas duas sobre
# o maior dos dois números de projetos com vantagem em cada uma. O quanto um
# projeto é típico: cosseno entre o uso dele e o uso de todos.
espaco_capacidades <- function(ch, min_chamadas = 30) {
  ch <- ch[nzchar(ch$projeto), ]
  if (!nrow(ch)) return(NULL)
  x <- unclass(table(ch$projeto, capacidade(ch$ferramenta, ch$alvo)))
  x <- x[rowSums(x) >= min_chamadas, , drop = FALSE]
  x <- x[, colSums(x) > 0, drop = FALSE]
  if (nrow(x) < 3 || ncol(x) < 3) return(NULL)
  parte <- x / rowSums(x)
  geral <- colSums(x) / sum(x)
  rca <- sweep(parte, 2, geral, "/")
  m <- (rca >= 1) * 1
  ubiq <- colSums(m)
  prox <- crossprod(m) / outer(ubiq, ubiq, pmax)
  prox[!is.finite(prox)] <- 0
  diag(prox) <- 0
  tipico <- apply(parte, 1, function(s) sum(s * geral) / sqrt(sum(s^2) * sum(geral^2)))
  vant <- apply(rca, 1, function(r) {
    r <- sort(r[r >= 1], decreasing = TRUE)
    paste(head(names(r), 4), collapse = ", ")
  })
  projetos <- data.frame(projeto = rownames(x), chamadas = rowSums(x), capacidades = rowSums(x > 0),
                         com_vantagem = rowSums(m), tipico = round(100 * tipico), vantagens = vant,
                         stringsAsFactors = FALSE)
  rownames(projetos) <- NULL
  list(uso = x, rca = rca, m = m, ubiquidade = ubiq, proximidade = prox,
       projetos = projetos[order(-projetos$tipico), ])
}

# Rede das capacidades: a árvore geradora máxima da proximidade, para
# ligar tudo, mais as arestas com proximidade >= limiar (como no Product
# Space), entre as max_nos capacidades mais usadas.
rede_capacidades <- function(esp, max_nos = 40, limiar = 0.5, projeto = NULL) {
  if (is.null(esp)) return(NULL)
  uso <- sort(colSums(esp$uso), decreasing = TRUE)
  caps <- names(uso)[seq_len(min(max_nos, length(uso)))]
  p <- esp$proximidade[caps, caps]
  g <- igraph::graph_from_adjacency_matrix(p, mode = "undirected", weighted = TRUE, diag = FALSE)
  if (!igraph::ecount(g)) return(NULL)
  # Arestas da árvore, achadas no grafo original pelas pontas.
  arv <- igraph::as_edgelist(igraph::mst(g, weights = 1 - igraph::E(g)$weight))
  ids <- union(igraph::get_edge_ids(g, as.vector(t(arv))), which(igraph::E(g)$weight >= limiar))
  h <- igraph::subgraph_from_edges(g, ids, delete.vertices = FALSE)
  w <- igraph::E(h)$weight
  el <- igraph::as_edgelist(h)
  grupo <- if (length(projeto) == 1 && projeto %in% rownames(esp$m)) {
    ifelse(esp$m[projeto, caps] > 0, paste("vantagem de", projeto), "outra")
  } else {
    ifelse(esp$ubiquidade[caps] >= stats::median(esp$ubiquidade[caps]), "comum", "rara")
  }
  nos <- data.frame(id = caps, label = caps, value = as.numeric(uso[caps]), group = grupo,
                    title = sprintf("%s<br>%d chamada(s)<br>%d projeto(s) com vantagem", esc(caps),
                                    as.integer(uso[caps]), as.integer(esp$ubiquidade[caps])),
                    stringsAsFactors = FALSE)
  list(nos = nos, arestas = data.frame(from = el[, 1], to = el[, 2], value = w,
                                       title = sprintf("proximidade %.2f", w)), grafo = h)
}

# E. Subagentes e delegações ----------------------------------------------------
# Os indicadores vêm prontos do subagentes.json (default/painel/subagentes.py);
# aqui só viram tabelas e grafo.

num_ou_na <- function(x) if (is.null(x)) NA_real_ else as.numeric(x)

# Uma linha por faixa de diff: n e medida com e sem o grupo (agy ou verificador).
tabela_comparar <- function(linhas, medida) {
  if (!length(linhas)) return(data.frame(faixa = character(), com = character(), sem = character()))
  lado <- function(l, k) {
    g <- l[[k]]
    v <- num_ou_na(g[[medida]])
    paste0(if (is.na(v)) "-" else format(v, big.mark = ".", decimal.mark = ","), " (", g$n, ")",
           if (isTRUE(g$pouco_dado)) "*" else "")
  }
  data.frame(faixa = vapply(linhas, function(l) l$faixa, ""),
             com = vapply(linhas, lado, "", "com"), sem = vapply(linhas, lado, "", "sem"))
}

# Lista de registros (desvios, retornos grandes) em data.frame.
tabela_lista <- function(itens, campos) {
  if (!length(itens)) return(as.data.frame(setNames(rep(list(character()), length(campos)), campos)))
  as.data.frame(lapply(setNames(campos, campos), function(k)
    vapply(itens, function(i) if (is.null(i[[k]])) NA_character_ else as.character(i[[k]]), "")))
}

# Árvore de delegação em rede: pasta, conversa (ramo) e cada filho.
arvore_rede <- function(ramos) {
  if (!length(ramos)) return(NULL)
  nos <- list(); arestas <- list()
  for (r in ramos) {
    pasta <- paste0("p:", r$pasta); ramo <- paste0("r:", r$conversa)
    nos[[pasta]] <- data.frame(id = pasta, label = basename(r$pasta), group = "pasta", value = 3, title = esc(r$pasta))
    nos[[ramo]] <- data.frame(id = ramo, label = sub(":.*", "", r$conversa), group = "conversa", value = 2,
      title = paste0(esc(r$conversa), "<br>", esc(r$n), " filho(s), ", esc(r$tokens_claude), " tokens no Claude, razão ",
                     if (is.null(r$razao)) "-" else esc(r$razao), ", ", esc(r$passos_agy), " passos no agy"))
    arestas[[length(arestas) + 1]] <- data.frame(from = pasta, to = ramo)
    for (f in r$filhos) {
      id <- paste0("f:", f$origem, ":", f$id, ":", length(nos))
      grupo <- if (isTRUE(f$recusa)) "recusa" else f$origem
      nos[[id]] <- data.frame(id = id, label = if (is.null(f$papel)) "?" else f$papel, group = grupo,
        value = 1 + log10(1 + num_ou_na(if (is.null(f$tokens)) 0 else f$tokens)) / 2,
        title = paste0(esc(f$origem), " ", esc(f$id),
                       if (is.null(f$destino)) "" else paste0("<br>destino ", esc(f$destino)),
                       if (is.null(f$modelo)) "" else paste0(", modelo ", esc(f$modelo)),
                       "<br>profundidade ", if (is.null(f$profundidade)) "-" else esc(f$profundidade),
                       ", tokens ", if (is.null(f$tokens)) "-" else esc(f$tokens),
                       ", retorno ", if (is.null(f$retorno_tokens)) "-" else esc(f$retorno_tokens)))
      arestas[[length(arestas) + 1]] <- data.frame(from = ramo, to = id)
    }
  }
  list(nos = do.call(rbind, nos), arestas = do.call(rbind, arestas))
}
