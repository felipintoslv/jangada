# Riscos e contenção do Jangada Vigia

Este documento resume os quatro riscos principais da coleta e uso do
diagnóstico no Jangada Vigia e como cada um é contido por construção.

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
    o campo `serial`, o valor dele em qualquer outro texto do monitor e o código
    `0x...` no fim da `description` são retirados antes de gravar; fabricante e
    modelo ficam.
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
    temporária descrita na seção 1.
  - As gravações de retrato e relatório usam arquivo temporário na própria
    pasta `$JANGADA_ESTADO/vigia/` seguido de `mv`.
  - A limpeza de 30 dias e o subcomando `jangada-vigia apagar` resolvem o
    caminho real da pasta e do alvo e recusam qualquer arquivo fora de
    `$JANGADA_ESTADO/vigia/` ou com `..` e links simbólicos externos.
