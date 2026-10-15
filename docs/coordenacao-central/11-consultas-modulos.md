# Consultas do terminal e do Monitor, recorte M1.2

O terminal e o retrato de orquestração do Monitor consultam o Core sem
conhecer nomes de arquivos ou descobrir bancos. Este recorte retira duas
exceções de K9. Não conclui M1: compatibilidade, volume e prova integral
continuam nos recortes seguintes. Não altera políticas de delegação.

## Sessão por árvore de trabalho

`bin/jangada-agentes --sessao-worktree-json CAMINHO` retorna
`{"versao":1,"sessao":"nome"}` ou `{"versao":1,"sessao":null}`.
O caminho exige forma absoluta, até 4.096 caracteres. A comparação com
`worktree` é literal, sem normalizar barras, consultar processos ou aplicar
retenção. `dir` e `raiz` não participam. Assim, uma sessão `--direto` sem
`worktree` não corresponde; uma sessão legada ou encerrada ainda corresponde.
O nome continua vindo do arquivo, mesmo sem campo `sessao` no registro.
Arquivos reservados a revisões, delegações e contextos de validação não são
registros de sessão e não são abertos; diretórios `*.json` são ignorados.

`JANGADA_SESSAO` mantém precedência no terminal e dispensa a consulta.
Sem essa variável, `_jangada_sessao_atual` entrega ao Core o topo do Git.
Ausência de correspondência retorna 1 na função do terminal. Falhas retornam
2 com diagnóstico. `repassar` não abre o seletor após erro da consulta.

Havia ambiguidade quando vários registros tinham o mesmo `worktree`: o
Shell escolhia o primeiro resultado de `find`, cuja ordem não era contrato.
A consulta agora recusa e informa os nomes, sem escolher arbitrariamente.

## Contexto explícito por sessão

`bin/jangada-agentes --contexto-json SESSAO` retorna um objeto com:

| Campo | Tipo e significado |
|---|---|
| `versao` | Inteiro 1 |
| `sessao` | Nome solicitado |
| `tarefa` | Texto original; ausente ou nulo vira texto vazio |
| `parecer` | Nulo ou objeto com `rodada` inteira, `origem` relativa e `texto` |

A seleção preserva a origem anterior: Markdown `validacao-SESSAO-rN.md`
na árvore de `agentes/`, inclusive subpastas de pareceres. Não desce em
`agentes/projetos/` ou `agentes/runtime/`, áreas operacionais protegidas.
Não consulta `revisoes/`,
conversas, históricos dos modelos, protocolos nem credenciais. A maior
rodada numérica vence, portanto r10 vem depois de r2 independentemente da
subpasta. Empate na maior rodada recusa o repasse. A ordenação anterior
por caminho completo podia privilegiar a subpasta; esse caso não tinha
critério explícito por rodada. Sufixos diferentes de dígitos não são pareceres.
Rodadas acima de nove dígitos recusam a consulta.

`repassar` continua sendo ação explícita do dono. O texto é marcado como
dado não confiável, sem autoridade de aprovação ou execução. O consumidor
substitui caracteres de controle, preservando tabulações e quebras de linha.
O comando não dá acesso a pareceres protegidos por ligações simbólicas ou
adicionais. Ausência de registro e parecer produz contexto vazio identificado,
como antes. Um erro impede criar ou abrir a nova tarefa.

## Limites do terminal

Nomes seguem `[A-Za-z0-9_.-]+`, até 255 caracteres, exceto `.` e `..`.
A pasta final não pode ser simbólica. A raiz configurada do estado é resolvida
antes da leitura; os componentes abaixo dela são abertos sem seguir links.
JSON e parecer selecionado exigem arquivo regular sem ligações adicionais,
até 1 MiB. `worktree` e `tarefa` exigem texto ou nulo, até 16.000 caracteres.
JSON malformado ou de outro tipo em registro de sessão recusa a consulta,
inclusive se o registro não corresponder à árvore solicitada.

São aceitos até 4.096 registros na busca por árvore, 16.384 entradas de
pasta e profundidade 32 na busca de parecer. Diretórios simbólicos não são
percorridos; um parecer candidato simbólico ou FIFO recusa a consulta.
A resposta UTF-8 inteira tem teto de 1 MiB, sem truncamento. O Core sai
com 1, diagnóstico e stdout vazio em caso de erro.

O terminal valida versão inteira 1, campos e tipos antes de usar a resposta.
O transporte usa Python em modo isolado (`-I`), sem importar módulos da
pasta atual ou de `PYTHONPATH`. Limita stdout e stderr agregados a 1 MiB e
dez segundos.
Falha, JSON malformado ou versão desconhecida não vira ausência de sessão.
O prazo encerra o processo direto; não promete encerrar seus descendentes.
Não há retorno à leitura dos arquivos privados.

## Fila e provedores do Monitor

`nucleo.consultas.consultar_filas(raiz, projetos=(), precos=None)` recebe a
raiz configurada do estado, caminhos dos projetos conhecidos e a tabela de
preços já lida pelo consumidor. A resposta tem versão inteira 1 e listas
`projetos`, `provedores`, `erros`.

Cada projeto entrega `id` opaco, `caminho` conhecido ou nulo, `tarefas`,
`consumos` por ID e `metricas`. O Core decide descoberta, seleção dos bancos
e correspondência dos caminhos. A chave usa o destino resolvido, mas
`caminho` conserva o texto recebido, inclusive aliases por links simbólicos.
O Monitor decide apenas o nome de exibição;
para projeto desconhecido, conserva `projeto-` seguido dos primeiros doze
caracteres do ID. Não recebe conexão SQL nem caminho de banco.

Cada tarefa entrega apenas `id`, `status`, `tentativas`, `motivo`, `atualizado`
e a parte de `especificacao` usada na apresentação: `papel`, `capacidade`,
`prioridade`, `dependencias`, `max_chamadas` e `tempo_total`. Campos opcionais
ausentes continuam ausentes. Pedidos, objetivos, resultados e demais colunas
não atravessam esse contrato. O cálculo interno conserva os dados completos.
Consumo continua
com `chamadas` e `segundos`. As métricas reutilizam o cálculo existente no
Core, sobre o mesmo retrato de leitura. Preços inválidos continuam gerando
erro; consumo ou custo desconhecido continua nulo. Provedores mantêm a
expiração, a pausa e a cota não confirmada. Não há consulta remota.

Cada erro contém `projeto` e `caminho` opcionais, além de `mensagem`.
Projeto ilegível não entrega tarefas ou métricas parciais. Erro de provedores
é explícito. Ausência de estado ou de banco é resultado vazio válido e não
cria pastas. Fila existente sem tarefas ainda entrega métricas vazias.
O Monitor recusa versão desconhecida e conserva o erro na saída do coletor.

Bancos e WAL são copiados para pasta temporária privada, nunca abertos para
escrita na origem. `query_only` e transação de leitura permanecem ativos.
Banco, WAL e SHM simbólicos ou não regulares são recusados. Cada arquivo
copiado admite 64 MiB; há até 4.096 projetos e 16.384 tarefas ou provedores
por banco. Eventos não têm teto de contagem separado do limite dos arquivos.
A resposta codificada admite 1 MiB. Provedores são consultados primeiro.
Projeto cuja apresentação excede o saldo da resposta gera erro identificado,
sem descartar provedores ou outras filas válidas. Uma reserva de 1 KiB
permite relatar erros de limite. Se os próprios diagnósticos excederem a
resposta, são resumidos por uma mensagem explícita com a quantidade de erros. O esquema legado tem `user_version=0`;
outro valor é erro nesta API. Esses tetos são proteções, não prova de
adequação a volume. Mudança concorrente durante a cópia continua exigindo
nova tentativa limitada ou erro, conforme `banco_leitura`.

## Provas e pendências

`testes/consulta-terminal.sh` exerce as fachadas reais com estado reposicionado,
retenção zero, sessões antigas, `--direto`, duplicidade e r2/r10. No bash e
zsh, também usa comando sintético e estado privado inacessível para provar
precedência, transporte, versão e recusa sem executar o destino.

`testes/consultas-modulos.py` compara o cálculo existente e o conteúdo do
Monitor com SQLite sintético, WAL confirmado e transação não confirmada.
Confere preços, provedores expirados, fila vazia, erros, limites, links e
FIFO. O consumidor recebe uma resposta pública sintética sem poder enumerar
ou testar arquivos privados. Ambos os testes comparam caminhos e hashes da
origem antes/depois, inclusive WAL e ausência de estado.

Os contratos existentes de consulta, fachada, caminhos e fronteiras continuam
ativos. Não foram ampliados tetos ou exceções de K9. Não há alteração de TSV,
de `--lista-json` versão 1, de links relativos ou de registros documentados.

Antes de integrar, executar `testes/painel-orquestracao.py` e a suíte integral
em ambiente com autoridade para preparar as fontes sintéticas. As provas
específicas incluem 400 pedidos longos sem aumentar a resposta, estouro por
projeto com provedores preservados e aliases simbólicos no nome de exibição.
A busca do terminal é conferida com contextos grandes, relatórios inválidos
e mais de 16.384 artefatos protegidos, sem abrir essas fontes como sessões
ou pareceres. Esses casos não substituem a avaliação de volume de M1.3.
