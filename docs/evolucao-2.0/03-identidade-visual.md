# Identidade visual

Levantamento do que existe e proposta de sistema visual para o painel 2.0.
O levantamento inicial precede a implementação. A situação em 08/10/2026
está registrada na seção 4; os caminhos e linhas anteriores são daquele levantamento.

## 1. O que existe

### 1.1 Logo

| Arquivo | Formato | Uso |
|---|---|---|
| `default/logo/jangada.png` | PNG 192 x 192, RGBA, preenchimento `#e6d9be` | Cabeçalho da Central de Atividades (`default/tarefas/janela.py:273`) |
| `default/logo/jangada-symbolic.svg` | SVG 24 x 24, preto, recolorível | Barra (`default/waybar/base.css:120`, com `-gtk-recolor`) |
| `default/logo/jangada.txt` | Arte em texto com 4 cores | `bin/jangada-logo` (fastfetch ou neofetch) |

O desenho é uma lua crescente à esquerda e uma jangada de vela triangular
sobre uma base horizontal. O comentário do SVG declara que o PNG mantém a
mesma geometria. A arte em texto é um desenho diferente (vela, casco e
ondas), usado só no terminal.

O painel Shiny não mostra a logo: o título é o texto "Indicadores do
jangada" (`default/painel/app.R:110`).

Regra para a 2.0: os três arquivos são a logo oficial e não mudam. O painel
novo usa o SVG simbólico recolorido pelo tema e o PNG onde precisar de
imagem fixa.

### 1.2 Cores

A paleta vem do papel de parede, pelo matugen (`default/matugen/config.toml`,
cor de reserva `#4f8fba`). Seis nomes são distribuídos
(`default/matugen/modelos/waybar.css`):

| Nome | Origem no matugen | Valor padrão (papel "cordel") |
|---|---|---|
| `superficie` | `surface` | `#141311` |
| `texto` | `on_surface` | `#e6e2de` |
| `texto_suave` | `on_surface_variant` | sem padrão no painel |
| `primaria` | `primary` | `#e6d9be` |
| `texto_primario` | `on_primary` | `#37301d` |
| `atencao` | `tertiary` | `#dbd8e9` |

Os valores padrão aparecem em `default/painel/app.R` e em
`default/sddm/jangada/theme.conf`.

Divergências (fato):

- A Central de Atividades não usa a paleta. Tem cores fixas:
  `#182128`, `#23313b`, `#e1e9ec` (`janela.py:301,322,379`) e cores de estado
  em `default/tarefas/dados.py:14-15` (`#f2c66d`, `#85baff`, `#96d6a8`,
  `#f09d93`). Só tem modo escuro.
- O painel tem modo claro e escuro (`app.R:304`), mas a paleta do matugen é
  gerada para um modo só.
- As 16 cores do terminal são fixas de propósito, porque têm significado
  (`default/matugen/modelos/ghostty`).
- Os gráficos da skill `graficos` têm paleta própria e fixa
  (`default/claude/skills/graficos/tema_dv.R:27-47`), igual em R e Python por
  teste (`testes/verificar.sh`).

### 1.3 Tipografia

| Superfície | Fonte |
|---|---|
| Barra | JetBrainsMono Nerd Font, 13 px (`default/waybar/base.css`) |
| Tela de login | JetBrainsMono Nerd Font, 12 pt (`default/sddm/jangada/theme.conf`) |
| Painel | Inter no texto, JetBrains Mono no código (`app.R:34-35`); Noto Sans nos gráficos (`app.R:329`) |
| Central | Fonte do sistema, 13 px (`janela.py:379`) |

São três famílias de texto em quatro superfícies.

### 1.4 Ícones e medidas

- Painel: Bootstrap Icons pelo pacote `bsicons`.
- Barra: glifos da Nerd Font.
- Medidas da barra em unidade de 4 px: 4, 8 e 32; raio de 8 px
  (`default/waybar/base.css`, comentário inicial).

## 2. Proposta de sistema visual

### 2.1 Princípios

1. A logo não muda.
2. A cor continua vindo do papel de parede; o painel e a Central passam a ler
   os mesmos seis nomes.
3. Cor de estado é fixa e não depende do papel de parede, pela mesma razão
   das cores do terminal.
4. Estado nunca é comunicado só por cor: sempre com rótulo e ícone.

### 2.2 Fichas de cor

| Ficha | Escuro | Claro | Uso |
|---|---|---|---|
| `superficie` | matugen `surface` | matugen `surface` do esquema claro | Fundo |
| `superficie_elevada` | derivada | derivada | Cartões |
| `texto` | `on_surface` | `on_surface` claro | Texto |
| `texto_suave` | `on_surface_variant` | idem claro | Legendas |
| `primaria` e `texto_primario` | `primary`, `on_primary` | idem claro | Ação principal, seleção |
| `atencao` | `tertiary` | idem claro | Destaque secundário |

O matugen gera os dois esquemas a partir da mesma imagem. A proposta é
acrescentar um modelo que grave as fichas dos dois modos num só arquivo.
Isso exige confirmar na Fase 2 a sintaxe de modelo do matugen instalado
(não verificado).

Estados, com base nas cores que a Central já usa:

| Estado 2.0 | Cor no escuro | Ícone sugerido |
|---|---|---|
| Planejada | `texto_suave` | círculo vazio |
| Pronta | `texto` | círculo cheio |
| Executando | `#85baff` | seta circular |
| Em revisão | `#c9b6f2` (nova) | lupa |
| Concluída | `#96d6a8` | marca de conferido |
| Bloqueada | `#f2c66d` | pausa |
| Falhou | `#f09d93` | xis |
| Cancelada | `texto_suave` | traço |

As variantes para o modo claro precisam ser calculadas e medidas. Nenhum
contraste foi medido nesta fase.

### 2.3 Tipografia e medidas

- Texto: Inter. Dados, identificadores e código: JetBrains Mono. É o que o
  painel já usa e aproxima a Central da barra.
- Escala de espaço em múltiplos de 4 px, a da barra. Raio de 8 px.
- Corpo de 14 px no painel; mínimo de 13 px.

### 2.4 Acessibilidade

Metas para a Fase 6, a medir com ferramenta:

- Contraste mínimo de 4,5:1 para texto e 3:1 para elementos gráficos, nos
  dois modos e com pelo menos três papéis de parede diferentes.
- Navegação completa por teclado, com foco visível.
- Rótulos de texto em todos os ícones de ação.
- Respeito à preferência do sistema por menos movimento.
- Tabelas com cabeçalhos marcados; gráficos com tabela equivalente.

Risco: como a paleta depende da imagem, um papel de parede pode gerar par de
cores com contraste baixo. Mitigação: conferir o contraste ao gerar o tema e
trocar pelo par padrão quando ficar abaixo da meta.

## 3. Pendências do levantamento inicial

- Medir contraste da paleta padrão e das cores de estado.
- Confirmar se o matugen instalado gera os dois esquemas num modelo só.
- Decidir se a Central Qt adota as fichas (decisão D7 em `09-decisoes.md`).
- Conferir painel e Central em tela; esta análise veio só do código.

## 4. Implementação em 08/10/2026

`default/matugen/modelos/fichas.json` gera sete fichas nos modos claro e
escuro em uma chamada do matugen 4.2.0. A sintaxe foi conferida com o
programa instalado. `default/visual/fichas.py` valida formato e contraste;
um esquema insuficiente usa a reserva de `default/visual/padrao.json`.
Painel e Central Qt leem essa mesma validação. A migração copia a reserva
só quando ausente; a próxima aplicação do tema gera as cores da imagem.

`testes/fichas.py` mediu texto e estados em ambos os modos, sobre fundo e
cartões, em três imagens sintéticas: azul, vermelha e cinza. Exige 4,5:1.
Também confere a reserva e a preservação de personalização na migração.
Não representa ensaio com todos os papéis de parede possíveis.

A logo simbólica foi aplicada sem alterar os três arquivos oficiais.
Texto usa Inter e dados usam JetBrains Mono; `inter-font` foi acrescentado
à lista da instalação. No ambiente desta sessão Inter ainda não está
instalada, e a conferência visual usa a fonte de reserva do sistema.
Raio de 8 px, corpo de 14 px, foco visível e modo claro foram aplicados à
Central. O painel respeita preferência por menos movimento em sua folha
de estilo. Estados combinam rótulo e símbolo.

A aprovação técnica e a situação das verificações ficam em `10-progresso.md`.
