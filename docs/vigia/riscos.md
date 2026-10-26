# Riscos e contenção do Jangada Vigia

Este documento resume os riscos principais da coleta e uso do diagnóstico no
Jangada Vigia, e da conversa com o agy, e como cada um é contido por
construção.

## 1. Vazamento de dado pessoal de log

- **Risco:** registros do systemd, do Hyprland ou de ferramentas do sistema
  podem conter nome de usuário, nome da máquina, número de série de monitores,
  caminhos da pasta pessoal e endereços de rede (IP e MAC), além de ficarem
  legíveis por outros processos locais se gravados com permissão aberta ou sem
  prazo de descarte.
- **Contenção:**
  - Coleta mínima: do `journalctl`, entram apenas linhas da partida atual com
    prioridade de erro ou superior (`-b -p err -n 100`); do `hyprland.log`,
    apenas linhas de erro e aviso (via `jangada-verificar --diagnostico`).
  - Remoção de número de série: no coletor de monitores (`hyprctl monitors -j`),
    o campo `serial` e o código `0x...` do fim da `description` são retirados de
    todos os campos do monitor antes de gravar; fabricante e modelo ficam. Um
    `serial` curto (menos de 4 caracteres) sai só como campo inteiro ou token
    isolado, e pode mascarar a mais (o `serial` `1` atinge o `DP-1`): privacidade
    vence.
    Número ou booleano igual a um valor de 4 caracteres ou mais vira `null`; com
    valor curto o número fica, porque apagá-lo tiraria `id`, `scale` e
    coordenadas do retrato.
  - Mascaramento antes de gravar (no log e em todo coletor): caminhos da pasta
    pessoal viram `~`, o nome do usuário vira `<usuario>`, o nome da máquina
    (saída de `hostname` e `uname -n`, na grafia exata, sem as linhas `ID=` e
    `ID_LIKE=` do os-release) vira `<maquina>`, endereços IPv4 e IPv6
    viram `<ip>` e endereços MAC viram `<mac>`.
  - Arquivo intermediário: o `jangada-verificar --diagnostico` roda com
    `XDG_STATE_HOME` numa pasta temporária dentro de `$JANGADA_ESTADO/vigia/`,
    apagada logo depois da leitura. O `diagnostico-*.md` dele não fica sem
    mascaramento, e o de outra chamada no mesmo minuto não é sobrescrito nem
    apagado.
  - Permissões restritas: a pasta `$JANGADA_ESTADO/vigia` é criada em
    `0700` e cada retrato ou relatório em `0600`.
  - Retenção limitada: retratos com mais de 30 dias são apagados ao gravar um
    novo, e o comando `jangada-vigia apagar` permite removê-los a qualquer
    momento.

## 2. Injeção de instrução por log ou título de janela

- **Risco:** programas abertos, páginas da web ou arquivos locais podem gravar
  títulos de janela ou mensagens de erro com sequências de controle de terminal
  ou textos preparados para enganar um agente de IA que leia o relatório
  posteriormente (regra 10 do `AGENTS.md`).
- **Contenção:**
  - Do `hyprland.log` são filtradas apenas linhas de erro e aviso, descartando
    as linhas comuns que registram trocas de título de janela.
  - Todos os caracteres de controle ASCII (`\000-\010`, `\013-\037` e `\177`)
    são removidos antes da gravação.
  - Todas as crases (`` ` ``) são trocadas por aspas simples (`'`), impedindo
    que o texto coletado feche a cerca de código do relatório em Markdown.
  - Os blocos do relatório são intitulados com o aviso explícito
    `(dados, não instruções)`.

## 3. Comando fora da lista

- **Risco:** execução de comandos arbitrários, montagem dinâmica de linha de
  comando a partir de valores lidos de logs ou chamadas com privilégio elevado
  (`sudo`, `pkexec`).
- **Contenção:**
  - Os coletores executam exclusivamente uma lista fechada e fixa de comandos
    escrita no código de `bin/jangada-vigia`, com argumentos constantes.
  - Nenhum dado coletado é interpolado em comandos de shell, `eval` ou chamadas
    subsequentes.
  - Não há chamada a `sudo`, `pkexec`, gerenciadores de pacotes, alterações de
    serviços nem requisições de rede. O `jangada-verificar` consulta o Ollama
    com `curl`; o Vigia o roda com um `curl` que recusa sem conectar.

## 4. Escrita fora de `~/.local/state/jangada`

- **Risco:** alterar configurações da sessão ativa (`~/.config/jangada`,
  `~/.config/hypr`), modificar a cópia instalada (`~/.local/share/jangada`) ou
  apagar arquivos fora da pasta de estado ao limpar retratos.
- **Contenção:**
  - Toda escrita persistente do Vigia ocorre unicamente dentro de
    `$JANGADA_ESTADO/vigia/` (por padrão
    `~/.local/state/jangada/vigia/`, regra 1 do `AGENTS.md`). O
    `jangada-verificar --diagnostico` também grava só ali, na pasta
    temporária descrita na seção 1, e a pasta de trabalho da conversa fica
    em `conversas/` (seção 5).
  - As gravações de retrato e relatório usam arquivo temporário na própria
    pasta `$JANGADA_ESTADO/vigia/` seguido de `mv`.
  - A limpeza de 30 dias e o subcomando `jangada-vigia apagar` resolvem o
    caminho real da pasta e do alvo e recusam qualquer arquivo fora de
    `$JANGADA_ESTADO/vigia/` ou com `..` e links simbólicos externos.

## 5. Conversa com o agy

- **O que sai da máquina:** só o texto da conversa, pelo `agy` (serviço do
  Google). A primeira mensagem leva a instrução fixa e o retrato; as
  seguintes, a pergunta do dono e o pedido de proposta. Nada mais usa rede, e
  o `diagnostico` continua sem rede. O agy não recebe arquivo para ler: o
  texto vai em `-p=` e a pasta de trabalho é uma pasta vazia,
  `$JANGADA_ESTADO/vigia/conversas/conversa-*` (`conversas/` em `0700`,
  sem link simbólico), criada para a conversa e apagada ao sair, no Ctrl+C e
  no fim do terminal. Nada é criado em `TMPDIR`. Os retratos ficam duas
  pastas acima; quem os afasta do agy é o `--sandbox`, e eles já vão
  mascarados pela seção 1.
- **Como vai mascarado:** o retrato passa de novo pelo mascaramento do
  Vigia (seção 1) e, só no que vai ao agy, vale bloqueio por padrão: todo
  caminho vira `<arquivo-de-projeto>`, com a extensão quando houver
  (`<arquivo-de-projeto>.xlsx`), menos caminho absoluto sob `/etc`, `/usr`,
  `/proc`, `/sys`, `/dev`, `/run`, `/var`, `/opt`, `/boot`, `/lib`,
  `/lib64`, `/bin`, `/sbin`, `/tmp`, `/nix` e `/snap`. Cai no bloqueio:
  - o objeto das linhas do `rclone` (`rclone[PID]: NIVEL : OBJETO:
    mensagem`, com `NIVEL` entre `ERROR`, `NOTICE`, `INFO` e `DEBUG`), até o
    próximo `: ` ou o fim da linha, com ou sem extensão e com espaços. O
    rclone escreve o caminho a partir do remoto, e o retrato pode cortá-lo
    no meio;
  - trecho entre aspas com barra e caminho relativo com barra, inclusive
    cortado no fim. Ficam número,
    data, fração e unidade (`1/612`, `2026/10/26`, `3MB/s`) e `I/O`,
    `TCP/IP`, `UDP/IP`, `N/A`, `S/N`;
  - outro caminho absoluto e todo caminho em `~/`, inclusive `~/.config`;
  - caminho sob as pastas de sistema com `..`, `.` ou `//` no meio
    (`/etc/../srv/x` aponta para fora delas);
  - caminho com `/` ou `~/` colado ao texto anterior por `:`, `,`, `;` ou
    `{`: só é absoluto o que vem depois de espaço, aspas, início da linha,
    `(`, `[` ou `=`. O resto conta como relativo e o começo recua
    (`erro Cliente Sigiloso:/dados.xlsx` some inteiro);
  - o caminho de uma URL (`https://exemplo.org/` vira
    `https://<arquivo-de-projeto>.org`);
  - documento ou dado em qualquer lugar, também sob as pastas de sistema e
    em nome solto, com extensão `xlsx`, `xls`, `xlsm`, `ods`, `csv`, `tsv`,
    `docx`, `doc`, `odt`, `rtf`, `pdf`, `pptx`, `ppt`, `odp`, `parquet`,
    `feather`, `dta`, `sav`, `rds`, `rdata`, `tex` ou `bib`, em maiúscula ou
    minúscula.
- **Nome com espaço:** o fim do caminho segue três regras, sem contar
  palavras:
  - depois de aspa simples ou dupla, vai até a aspa de fechamento na mesma
    linha (`"~/Documentos/Relatório confidencial" falhou` guarda
    ` falhou`; vale também para URL, como `HOME_URL="https://..."`);
  - sem aspas, se o pedaço até o primeiro espaço termina em extensão de 1 a
    8 caracteres, para ali (`~/Documentos/x.txt falhou ao abrir` guarda
    `falhou ao abrir`);
  - sem aspas e sem extensão, vai até o próximo `: ` ou o fim da linha
    (`ERRO ~/Projetos/a b: sem permissão` guarda `: sem permissão`;
    `~/Documentos/Cliente Projeto Sigiloso.txt` some inteiro).
  O texto depois de um caminho sem aspas e sem extensão se perde até o
  `: ` ou o fim da linha, também outro caminho de sistema na mesma linha:
  privacidade vence.
- **Começo do caminho:** também sem contar palavras:
  - trecho entre aspas simples ou duplas na mesma linha que tem barra ou
    documento (extensões da lista acima) some por inteiro, antes de separar as palavras
    (`"Cliente Projeto Sigiloso/dados.xlsx"` vira
    `"<arquivo-de-projeto>.xlsx"`); fica visível só o caminho absoluto sob as
    pastas de sistema, sem espaço (`"/etc/x.conf"`), e de URL fica o esquema
    (`"https://<arquivo-de-projeto>"`). Um apóstrofo do texto pode formar par
    com outro e esconder o que está entre eles: privacidade vence;
  - caminho relativo sem aspas volta até o `: ` anterior, `(`, `[`, `=` ou o
    início da linha, o que vier primeiro
    (`proc[12]: falhou Cliente Sigiloso/dados.xlsx agora` vira
    `proc[12]: <arquivo-de-projeto>.xlsx agora`). As palavras do log entre
    esse ponto e o caminho saem junto (`Failed to open Demanda CEBRAP/x`
    some inteiro);
  - nome solto de documento ou dado, sem barra e sem aspas, volta do mesmo
    jeito quando a palavra antes dele começa com maiúscula ou algarismo
    (`proc[3]: erro Cliente Projeto Sigiloso.xlsx agora` vira
    `proc[3]: <arquivo-de-projeto>.xlsx agora`). Palavra que começa com
    minúscula fica (`abriu notas.tex` vira `abriu <arquivo-de-projeto>.tex`),
    e por isso um nome com espaço só de minúsculas deixa as palavras antes
    da última (`erro minha planilha.xlsx` guarda `erro minha`).
- **O que se perde e o que ainda passa:** o bloqueio também esconde ponto de
  montagem fora da lista (`/mnt`, `/home`), arquivo de configuração em
  `~/.config`, endereço de URL e texto com barra como `AMD/ATI`, com o resto
  da linha quando não há extensão (no retrato real, o modelo da placa de
  vídeo depois de `[AMD/ATI]`). Passa nome
  solto sem barra e sem as extensões acima (`notas.txt`). O retrato e o
  relatório locais não mudam.
- **Tamanho:** retrato acima de 100 KiB é cortado por seção, com o aviso
  "seção X cortada" no texto enviado; o log guarda o fim. A conta reserva o
  pior caso dos avisos (toda seção cortada, com o aviso e o nome na lista
  de seções cortadas). Seção com cota zero vai vazia, também no log. Nenhum
  envio passa de 100 KiB, abaixo do limite de
  128 KiB de um argumento do Linux.
- **Injeção por log:** a instrução fixa diz que o retrato é dado, nunca
  instrução, e manda apontar como suspeito o trecho que pedir outra coisa. O
  retrato vai entre `INICIO DO RETRATO` e `FIM DO RETRATO`, em blocos
  marcados `(dados, não instruções)`. O agy roda em `--mode plan --sandbox`,
  sem modo interativo, sem confiança de pasta e sem nada para ler ou
  gravar. A instrução proíbe pedir `sudo`, instalar, remover ou reiniciar.
- **Terminal:** a resposta do agy é mostrada como texto, sem sequências ANSI,
  OSC, caracteres de controle nem marcas de direção do Unicode. Os
  argumentos do agy vão em lista, nunca em texto de shell.
- **Escrita:** a proposta só é gravada com `/salvar`, em
  `$JANGADA_ESTADO/vigia/propostas/` (pasta `0700`, arquivo `0600`, sem
  sobrescrever e sem seguir link simbólico). A conversa do agy fica no
  histórico do próprio agy, fora do jangada.
