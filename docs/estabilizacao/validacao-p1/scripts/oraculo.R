# Implementação independente em R base, sem respostas do executor.
args <- commandArgs(trailingOnly=TRUE)
stopifnot(length(args)==2)
entrada <- args[1]; saida <- args[2]
dir.create(saida, recursive=TRUE, showWarnings=FALSE)
options(digits=17)
raw <- read.csv(file.path(entrada,"emprego.csv"), colClasses=c("character","character","character","integer","numeric"))
mun <- read.csv(file.path(entrada,"municipios.csv"), colClasses="character")
mapa <- read.csv(file.path(entrada,"classificacao.csv"), colClasses="character")
setores <- sort(unique(mapa$setor))
kmapa <- paste(mapa$codigo,mapa$versao)
stopifnot(!anyDuplicated(kmapa))
raw$setor <- mapa$setor[match(paste(raw$codigo,raw$versao),kmapa)]
valido <- raw$municipio %in% mun$municipio & raw$ano %in% 2019:2025 & !is.na(raw$setor) &
  (is.na(raw$emprego)|raw$emprego>=0) & raw$versao==ifelse(raw$ano<=2021,"antiga","nova")
invalidos <- sum(!valido)
d <- raw[valido,c("municipio","setor","ano","emprego")]
limpo <- unique(d)
duplicatas <- nrow(d)-nrow(limpo)
chave <- function(x) paste(x$municipio,x$setor,x$ano,sep="|")
stopifnot(!anyDuplicated(chave(limpo)))
p <- expand.grid(ano=2019:2025,setor=setores,municipio=sort(mun$municipio),stringsAsFactors=FALSE)
p <- p[order(p$municipio,p$setor,p$ano),c("municipio","setor","ano")]
p$emprego <- limpo$emprego[match(chave(p),chave(limpo))]
imputadas <- sum(is.na(p$emprego))
series <- split(seq_len(nrow(p)),paste(p$municipio,p$setor))
for (idx in series) {
  observado <- !is.na(p$emprego[idx])
  stopifnot(observado[1],observado[length(idx)])
  p$emprego[idx] <- approx(p$ano[idx][observado],p$emprego[idx][observado],xout=p$ano[idx])$y
}
stopifnot(nrow(p)==84000,all(is.finite(p$emprego)),all(p$emprego>=0))
mi <- aggregate(emprego~municipio+ano,p,sum)
sj <- aggregate(emprego~setor+ano,p,sum)
nt <- aggregate(emprego~ano,p,sum)
mi <- mi[order(mi$municipio,mi$ano),]
p$total_m <- mi$emprego[match(paste(p$municipio,p$ano),paste(mi$municipio,mi$ano))]
p$total_s <- sj$emprego[match(paste(p$setor,p$ano),paste(sj$setor,sj$ano))]
p$total_n <- nt$emprego[match(p$ano,nt$ano)]
ql <- p[,c("municipio","setor","ano")]
ql$ql <- (p$emprego/p$total_m)/(p$total_s/p$total_n)
p$proporcao <- p$emprego/p$total_m
hhi <- aggregate(proporcao~municipio+ano,transform(p,proporcao=proporcao^2),sum)
sh <- aggregate(proporcao~municipio+ano,transform(p,proporcao=-proporcao*log(proporcao)),sum)
ind <- mi;ind$crescimento_base <- mi$emprego/mi$emprego[match(paste(mi$municipio,2019),paste(mi$municipio,mi$ano))]-1
ind$hhi <- hhi$proporcao[match(paste(mi$municipio,mi$ano),paste(hhi$municipio,hhi$ano))]
ind$diversidade <- 1-ind$hhi
ind$shannon <- sh$proporcao[match(paste(mi$municipio,mi$ano),paste(sh$municipio,sh$ano))]
ind$efetivos <- exp(ind$shannon)
e0 <- p[p$ano==2019,c("municipio","setor","emprego")]
e1 <- p[p$ano==2025,c("municipio","setor","emprego")]
stopifnot(identical(e0$municipio,e1$municipio),identical(e0$setor,e1$setor))
G <- nt$emprego[nt$ano==2025]/nt$emprego[nt$ano==2019]-1
gj <- sj$emprego[match(paste(e0$setor,2025),paste(sj$setor,sj$ano))]/sj$emprego[match(paste(e0$setor,2019),paste(sj$setor,sj$ano))]-1
shift <- e0[,1:2];shift$e0 <- e0$emprego;shift$e1 <- e1$emprego
shift$ns <- shift$e0*G
shift$im <- shift$e0*(gj-G)
shift$rs <- shift$e1-shift$e0*(1+gj)
shift$delta <- shift$e1-shift$e0
stopifnot(max(abs(shift$ns+shift$im+shift$rs-shift$delta))<1e-8)
stopifnot(all(abs(aggregate(proporcao~municipio+ano,p,sum)$proporcao-1)<1e-12))
write.csv(p[,c("municipio","setor","ano","emprego")],file.path(saida,"painel.csv"),row.names=FALSE,na="")
write.csv(ql,file.path(saida,"ql.csv"),row.names=FALSE,na="")
write.csv(ind,file.path(saida,"indicadores.csv"),row.names=FALSE,na="")
write.csv(shift,file.path(saida,"shift.csv"),row.names=FALSE,na="")
write.csv(data.frame(invalidos,duplicatas,imputadas),file.path(saida,"qualidade.csv"),row.names=FALSE)
cat("Oraculo R concluido,",nrow(p),"celulas,",nrow(shift),"componentes shift-share\n")
