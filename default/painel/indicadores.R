# Indicadores do jangada-painel, calculados sobre o cache em Parquet que o
# coletor.py grava. Funções puras: recebem tabelas e devolvem tabelas, para o
# app e os testes usarem as mesmas definições.

POUCO_DADO <- 10

# Lê o cache. Tabela ausente vira tabela vazia com as colunas certas.
carregar_cache <- function(cache) {
  ler <- function(nome, vazia) {
    caminho <- file.path(cache, nome)
    ok <- if (dir.exists(caminho)) length(list.files(caminho, "\\.parquet$")) > 0 else file.exists(caminho)
    if (!ok) return(vazia)
    d <- if (dir.exists(caminho)) as.data.frame(arrow::open_dataset(caminho)) else as.data.frame(arrow::read_parquet(caminho))
    for (col in names(d)) if (inherits(d[[col]], "POSIXct")) attr(d[[col]], "tzone") <- ""
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
    sessoes = ler("sessoes.parquet", data.frame(
      sessao = character(), projeto = character(), agente = character(), estado = character(),
      desde = ts, atualizado = ts)),
    coleta = tryCatch(jsonlite::read_json(file.path(cache, "coleta.json")), error = function(e) list())
  )
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
                      limite = logical(), reprovacoes = integer(), diff = numeric()))
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

consumo_por <- function(m, por) {
  if (!nrow(m)) return(data.frame())
  m$raciocinio[is.na(m$raciocinio)] <- 0
  a <- aggregate(m[names(TIPOS_TOKEN)], list(grupo = m[[por]]), sum)
  a$respostas <- as.vector(table(m[[por]])[a$grupo])
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
# estado da mesma sessão (o foco não muda o estado); o último vale até agora,
# mas nunca além de 12 horas, para uma sessão esquecida não inflar a conta.
intervalos_estado <- function(ev, agora = Sys.time()) {
  ev <- ev[ev$estado != "foco", ]
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
