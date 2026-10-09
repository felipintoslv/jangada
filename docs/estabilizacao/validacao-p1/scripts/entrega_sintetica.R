# Artefato de teste produzido pelo auditor, não por IA. Lê só entradas públicas.
a <- commandArgs(trailingOnly=TRUE)
stopifnot(length(a)==3)
origem <- a[1];destino <- a[2];defeito <- a[3]
dir.create(destino,recursive=TRUE,showWarnings=FALSE)
x <- read.csv(file.path(origem,"emprego.csv"),stringsAsFactors=FALSE)
cad <- read.csv(file.path(origem,"municipios.csv"),stringsAsFactors=FALSE)
mapa <- read.csv(file.path(origem,"classificacao.csv"),stringsAsFactors=FALSE)
x <- x[x$municipio %in% cad$municipio & x$ano %in% 2019:2025 & (is.na(x$emprego)|x$emprego>=0) & x$versao==ifelse(x$ano<=2021,"antiga","nova"),]
if (defeito=="A1") {
 x <- merge(x,mapa,by="codigo",all.x=FALSE) # defeito: omite versão e multiplica linhas
 x <- aggregate(emprego~municipio+setor+ano,transform(x,emprego=ifelse(is.na(emprego),0,emprego)),sum)
} else {
 x$setor <- mapa$setor[match(paste(x$codigo,x$versao),paste(mapa$codigo,mapa$versao))]
 x <- x[!is.na(x$setor),c("municipio","setor","ano","emprego")]
 x <- unique(x)
 if (defeito=="A2") {
  alterado <- x$ano>=2022 & as.integer(sub("S","",x$setor))>=61
  n <- as.integer(sub("S","",x$setor[alterado]))
  x$setor[alterado] <- sprintf("S%03d",61+(n-60)%%20)
 }
}
y <- expand.grid(ano=2019:2025,setor=sort(unique(mapa$setor)),municipio=sort(cad$municipio),stringsAsFactors=FALSE)
y <- y[order(y$municipio,y$setor,y$ano),]
y$emprego <- x$emprego[match(paste(y$municipio,y$setor,y$ano),paste(x$municipio,x$setor,x$ano))]
for (idx in split(seq_len(nrow(y)),paste(y$municipio,y$setor))) {
 ok <- !is.na(y$emprego[idx])
 if (defeito=="A5") y$emprego[idx][!ok] <- 0 else y$emprego[idx] <- approx(y$ano[idx][ok],y$emprego[idx][ok],xout=y$ano[idx])$y
}
mi <- aggregate(emprego~municipio+ano,y,sum)
sj <- aggregate(emprego~setor+ano,y,sum)
nt <- aggregate(emprego~ano,y,sum)
y$municipal <- mi$emprego[match(paste(y$municipio,y$ano),paste(mi$municipio,mi$ano))]
y$ref_setor <- sj$emprego[match(paste(y$setor,y$ano),paste(sj$setor,sj$ano))]
y$ref_total <- nt$emprego[match(y$ano,nt$ano)]
if (defeito=="A4") {
 y$regiao <- cad$regiao[match(y$municipio,cad$municipio)]
 sr <- aggregate(emprego~setor+ano+regiao,y,sum);nr <- aggregate(emprego~ano+regiao,y,sum)
 y$ref_setor <- sr$emprego[match(paste(y$setor,y$ano,y$regiao),paste(sr$setor,sr$ano,sr$regiao))]
 y$ref_total <- nr$emprego[match(paste(y$ano,y$regiao),paste(nr$ano,nr$regiao))]
}
if (defeito=="A7") {
 sf <- aggregate(emprego~setor,y,sum)
 y$ref_setor <- sf$emprego[match(y$setor,sf$setor)]
 y$ref_total <- sum(y$emprego)
}
ql <- y[,c("municipio","setor","ano")];ql$ql <- (y$emprego/y$municipal)/(y$ref_setor/y$ref_total)
e0 <- y[y$ano==2019,];e1 <- y[y$ano==2025,]
G <- nt$emprego[nt$ano==2025]/nt$emprego[nt$ano==2019]-1
g <- sj$emprego[match(paste(e0$setor,2025),paste(sj$setor,sj$ano))]/sj$emprego[match(paste(e0$setor,2019),paste(sj$setor,sj$ano))]-1
shift <- e0[,c("municipio","setor")]
shift$e0 <- e0$emprego;shift$e1 <- e1$emprego
shift$ns <- shift$e0*G;shift$im <- shift$e0*(g-G)
shift$delta <- shift$e1-shift$e0
shift$rs <- shift$delta-shift$ns-shift$im
if (defeito=="A6") shift$rs <- shift$delta-shift$ns+shift$im
write.csv(y[,c("municipio","setor","ano","emprego")],file.path(destino,"painel.csv"),row.names=FALSE)
write.csv(ql,file.path(destino,"ql.csv"),row.names=FALSE)
write.csv(shift,file.path(destino,"shift.csv"),row.names=FALSE)
texto <- "Análise sintética descritiva; crescimento não identifica efeito causal."
if (defeito=="A3") texto <- "A taxa agregada caiu, portanto a taxa de emprego caiu dentro de ambos os grupos."
if (defeito=="A8") texto <- "A diversificação causou o crescimento do emprego; o QL demonstra esse efeito causal."
writeLines(texto,file.path(destino,"relatorio.txt"))
cat("ENTREGA SINTETICA DO AUDITOR, sem execução de modelo:",defeito,"\n")
