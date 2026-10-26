# Identidade visual

Guia da aparência das janelas Qt do jangada, a partir da prévia Cordel da v2
(`docs/historico/coordenacao-central/mockup-central/v2/`). Os componentes estão
em `menus/tarefas/aparencia.py` e não dependem da Central: outra janela importa
o módulo, aplica `folha_de_estilo(cores, modo)` e monta as peças.

Cada regra diz se o valor vem das fichas ou se é fixo. Fichas são as cores do
tema atual, lidas de `~/.config/jangada/fichas.json` e conferidas por
`default/visual/fichas.py`. Quando um par não alcança contraste 4,5:1, o modo
inteiro volta para a reserva de `default/visual/padrao.json`.

## Logo

Os três arquivos de `default/logo/` são a logo oficial e não mudam.

| Arquivo | Uso |
| --- | --- |
| `jangada-symbolic.svg` | Cabeçalho das janelas, com 40 x 40 px e recolorido com a primária. A barra usa o mesmo arquivo. |
| `jangada.png` | Onde só cabe imagem fixa, como documentação. A cor é a do arquivo. |
| `jangada.txt` | Terminal, pelo `jangada-logo`. |

Se o SVG não carrega, a logo some e o título continua. Não há imagem
substituta.

## Fichas

| Ficha | Papel |
| --- | --- |
| `superficie` | Fundo da janela, das listas e dos campos. |
| `superficie_elevada` | Cartão cheio, faixa de resumo, cabeçalho de colunas e botão secundário. |
| `texto` | Texto comum. |
| `texto_suave` | Rótulo de apoio, motivo de botão indisponível, aba não escolhida. |
| `primaria` | Botão principal, aba escolhida, linha selecionada, foco e logo. |
| `texto_primario` | Texto sobre a primária. |
| `atencao` | Aviso e falha de consulta. |

Os dois modos, escuro e claro, têm as mesmas sete fichas. Cores derivadas
saem de misturas das fichas e também precisam passar no contraste:

- linha divisória: `texto` a 22% sobre `superficie`;
- contorno de controle: a mistura mais leve de `texto_suave` sobre
  `superficie` com 3:1;
- linha selecionada: `superficie_elevada` com a primária por cima em 4,5:1.

## Estados

As cores de estado são fixas em `ESTADOS` de `fichas.py`, uma tabela por modo,
e não seguem o tema. A cor nunca aparece sozinha: o símbolo e o rótulo vêm
juntos.

| Estado | Símbolo | Na Central |
| --- | --- | --- |
| Planejada | ○ | texto suave |
| Pronta | ● | texto |
| Executando | ↻ | Em execução |
| Em revisão | ⌕ | Pronto para conferir |
| Concluída | ✓ | |
| Bloqueada | Ⅱ | Precisa da sua resposta |
| Falhou | × | Interrompida |
| Cancelada | − | texto suave |

## Tipografia e medidas

Fixos, iguais nos dois modos:

- texto em Inter 14 px; o menor tamanho é 13 px;
- dados e saída de terminal em JetBrains Mono 13 px;
- título da janela 24 px, peso 600; subtítulo 18 px, peso 600;
- número da faixa de resumo 20 px, peso 500;
- espaços em múltiplos de 4 px (4, 8, 12, 16, 20, 24);
- raio de 8 px em botões, campos, cartões e faixas.

## Botões

| Tipo | Aparência |
| --- | --- |
| Principal | Fundo na primária, texto em `texto_primario`, peso 600. |
| Secundário | Fundo elevado com contorno de 1 px. É o padrão. |
| Indisponível | Botão desligado: contorno tracejado, fundo da superfície, texto suave e o motivo escrito ao lado. |
| Perigo | Fundo da superfície, texto e borda na cor de falha. |

Indisponível vale para qualquer tipo: desligado, o botão perde a cor do tipo.
O motivo também vai para a descrição acessível do botão. Use
`definir_tipo(botao, tipo)` e `BotaoComMotivo(botao)`.

## Cabeçalho

Logo à esquerda, "Jangada" pequeno em texto suave e, abaixo, o título grande.
Os comandos da janela ficam à direita. Abaixo de 1080 px de largura o nome
pequeno sai, as margens caem de 24 para 16 px e os comandos descem para a
linha seguinte. Componente: `Cabecalho`.

## Faixa de resumo

Uma caixa elevada com os contadores lado a lado, separados por linhas. Cada
contador mostra número, símbolo na cor do estado e nome. Clicar filtra; o
contador marcado ganha fundo na primária e todo o texto em `texto_primario`.
Componente: `FaixaResumo`.

## Foco

Botões, campos e listas com foco ganham borda de 2 px na primária. Contadores
e abas usam borda tracejada na primária. Sobre a primária, como no botão
principal e no contador marcado, a borda tracejada fica em `texto_primario`.
O foco nunca depende só de cor de fundo.

## Listas, abas e cartões

- Aba escolhida: texto na primária com sublinhado de 2 px.
- Linha selecionada: fundo de seleção, texto na primária e barra de 3 px à
  esquerda.
- Cartão: borda de linha divisória ou, cheio, fundo elevado sem borda.

## O que não muda

Barra (waybar), tela de login e terminal seguem as cores do matugen e têm
regras próprias. Este guia vale para as janelas Qt.
