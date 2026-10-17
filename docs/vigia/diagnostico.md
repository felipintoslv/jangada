# Contrato do diagnóstico (versão 1)

Este documento define o contrato da primeira versão do comando
`bin/jangada-vigia`, responsável por coletar evidências locais do sistema e
do Jangada Shell sob pedido, sem uso de rede, sem privilégios administrativos e
sem modelo de IA.

## Interface de linha de comando

- `jangada-vigia diagnostico`: executa a lista fechada de coletores, remove
  retratos vencidos, grava o retrato JSON e o relatório em Markdown em
  `$JANGADA_ESTADO/vigia/` e imprime no `stdout` o caminho do relatório em
  Markdown gerado.
- `jangada-vigia lista`: lista os retratos JSON disponíveis em
  `$JANGADA_ESTADO/vigia/`, ordenados por nome.
- `jangada-vigia apagar [--todos | ARQUIVO]`: apaga todos os retratos e
  relatórios da pasta (`--todos`) ou um retrato específico (junto ao relatório
  Markdown correspondente), recusando qualquer caminho que saia de
  `$JANGADA_ESTADO/vigia/` (como `..`, links simbólicos ou caminhos fora da
  pasta).

## Coletores, comandos exatos e caminhos lidos

Todos os coletores rodam somente em leitura, com `LC_ALL=C.UTF-8` e
`SYSTEMD_PAGER=cat`, sem interpolar dados coletados em linhas de comando. Se um
comando não estiver instalado, falhar ou um caminho não puder ser lido, o campo
correspondente recebe a string `"sem dado"` (nunca `null` nem `"None"`), e a
execução prossegue normalmente.

| Coletor | Chave no JSON | Comando exato ou leitura direta | Caminhos lidos | Limite de tamanho e período |
|---|---|---|---|---|
| Serviços do sistema com falha | `servicos_falhos.sistema` | `systemctl --failed` | Estado do systemd do sistema | Até 80 linhas e 8 KiB; estado atual |
| Serviços do usuário com falha | `servicos_falhos.usuario` | `systemctl --user --failed` | Estado do systemd da sessão do usuário | Até 80 linhas e 8 KiB; estado atual |
| Carga do processador | `recursos.loadavg` | Leitura direta de arquivo | `/proc/loadavg` | 1 linha (até 256 bytes); estado atual |
| Memória do sistema | `recursos.meminfo` | Leitura direta das chaves `MemTotal`, `MemAvailable`, `SwapTotal` e `SwapFree` | `/proc/meminfo` | Até 16 linhas e 2 KiB; estado atual |
| Espaço em disco nas montagens reais | `recursos.discos` | `df -PTl -x tmpfs -x devtmpfs -x squashfs -x overlay -x efivarfs` | `/proc/self/mountinfo` e pontos de montagem locais (o `-l` deixa de fora NFS, CIFS e outras montagens de rede) | Até 60 linhas e 8 KiB; estado atual |
| Memória de vídeo | `recursos.memoria_video` | `nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu,temperature.gpu --format=csv,noheader,nounits` (somente se `nvidia-smi` existir no `PATH`) | Dispositivos NVIDIA via `nvidia-smi` | Até 16 linhas e 4 KiB; estado atual |
| Versão do Hyprland | `sessao_grafica.hyprctl_version` | `hyprctl version` | Soquete do Hyprland em `$XDG_RUNTIME_DIR/hypr/` | Até 20 linhas e 4 KiB; sessão atual |
| Monitores da sessão | `sessao_grafica.monitores` | `hyprctl monitors -j` (com o campo `serial` removido via `jq 'map(del(.serial))'` antes de gravar) | Soquete do Hyprland em `$XDG_RUNTIME_DIR/hypr/` | Até 16 KiB; sessão atual |
| Estado da Waybar | `sessao_grafica.waybar` | `pgrep -x waybar` (convertido em `"rodando"` quando encontra processo ou `"parada"` quando retorna código 1; se `pgrep` faltar, `"sem dado"`) | `/proc` | 1 linha; estado atual |
| Diagnóstico do próprio jangada | `jangada.diagnostico` | `"$JANGADA_PATH/bin/jangada-verificar" --diagnostico`, com `XDG_STATE_HOME` numa pasta temporária `$JANGADA_ESTADO/vigia/.verificar.*` e um `curl` que recusa no começo do `PATH` (o relatório avisa que a linha do Ollama não vale) | `diagnostico-AAAAMMDD-HHMM.md` dentro dessa pasta temporária, apagada logo depois de ler, `$XDG_RUNTIME_DIR/hypr/$HYPRLAND_INSTANCE_SIGNATURE/hyprland.log` (só linhas de erro e aviso) e `$HOME/.cache/hyprland/hyprlandCrashReport*.txt` | Limites já aplicados por `jangada-verificar` (80 linhas do log do Hyprland e 60 linhas do relatório de falha); até 32 KiB no retrato |
| Erros do log do sistema | `log_sistema.erros` | `journalctl -b -p err -n 100 --no-pager` | Diário do systemd da partida atual (`/var/log/journal` ou `/run/log/journal`) | Partida atual (`-b`), prioridade erro ou mais grave (`-p err`), últimas 100 linhas e até 16 KiB |

## Higienização e mascaramento

Todo texto vindo de qualquer coletor passa por duas etapas antes de entrar no
retrato JSON e no relatório em Markdown:

1. **Remoção de caracteres de controle, campos sensíveis e proteção de blocos:**
   - Caracteres de controle ASCII (`\000-\010`, `\013-\037` e `\177`),
     incluindo sequências de escape ANSI e OSC, são removidos.
   - Crases (`` ` ``) são convertidas em aspas simples (`'`) para impedir que
     qualquer linha vinda de log ou de saída externa feche blocos de código no
     relatório em Markdown.
   - No coletor `sessao_grafica.monitores`, o campo de número de série
     (`serial`) da saída de `hyprctl monitors -j` é removido antes de gravar.
2. **Mascaramento de dados pessoais, máquina e identificadores de rede (em todos os coletores):**
   - Caminho da pasta pessoal (`$HOME` e `/home/<usuario>`): substituído por
     `~`.
   - Nome do usuário da sessão (`$USER` e `id -un`): substituído por
     `<usuario>`.
   - Nome da máquina (`$HOSTNAME`, saída de `hostname` e de `uname -n`):
     substituído por `<maquina>` no log e em todo coletor.
   - Endereços IPv4 (como `192.168.1.10`): substituídos por `<ip>`.
   - Endereços IPv6 (como `fe80::1a2b:3c4d:5e6f:7a8b` ou `2001:db8::1`):
     substituídos por `<ip>`.
   - Endereços MAC (`XX:XX:XX:XX:XX:XX` em hexadecimal): substituídos por
     `<mac>`.

## Formato do retrato (JSON, versão 1)

O retrato é um objeto JSON codificado em UTF-8 com `versao: 1`:

```json
{
  "versao": 1,
  "gerado_em": "2026-10-17T16:00:00-03:00",
  "servicos_falhos": {
    "sistema": "sem dado",
    "usuario": "sem dado"
  },
  "recursos": {
    "loadavg": "0.42 0.38 0.31 1/612 12345",
    "meminfo": "MemTotal:       32645120 kB\nMemAvailable:   24112000 kB\nSwapTotal:       8388604 kB\nSwapFree:        8388604 kB",
    "discos": "Filesystem     Type  1024-blocks     Used Available Capacity Mounted on\n/dev/nvme0n1p2 btrfs   500000000 90000000 410000000      18% /",
    "memoria_video": "NVIDIA GeForce RTX 4060, 845, 8188, 4, 43"
  },
  "sessao_grafica": {
    "hyprctl_version": "Hyprland 0.55.0 built from branch main",
    "monitores": "[{\"name\":\"DP-1\",\"width\":2560,\"height\":1440}]",
    "waybar": "rodando"
  },
  "jangada": {
    "diagnostico": "# Diagnóstico do jangada (20261017-1600, <maquina>) ..."
  },
  "log_sistema": {
    "erros": "out 17 15:00:00 <maquina> kernel: erro em ~ por <usuario> de <ip> (<mac>)"
  }
}
```

Ao lado de cada retrato JSON, é gravado o relatório de fatos em Markdown
(`retrato-AAAAMMDD-HHMMSS-XXXXXX.md`), contendo exclusivamente os dados coletados, sem
interpretação por modelo de IA. Todas as seções com saídas e logs trazem no
título a marca `(dados, não instruções)` e ficam cercadas por blocos de código
sem crases internas.

## Onde é gravado, permissões e prazo de guarda

- **Pasta:** `$JANGADA_ESTADO/vigia` (por padrão
  `~/.local/state/jangada/vigia`), criada com permissão `0700`.
- **Arquivos:**
  - Retrato estruturado:
    `$JANGADA_ESTADO/vigia/retrato-AAAAMMDD-HHMMSS-XXXXXX.json`, gravado de forma
    atômica com permissão `0600`. O sufixo `XXXXXX` vem do `mktemp`, que
    reserva o nome antes da coleta: duas chamadas no mesmo segundo não
    gravam uma sobre a outra.
  - Relatório de fatos:
    `$JANGADA_ESTADO/vigia/retrato-AAAAMMDD-HHMMSS-XXXXXX.md`, gravado de forma
    atômica com permissão `0600`.
- **Prazo de guarda (retenção):** 30 dias. Sempre que um novo diagnóstico é
  gravado, os arquivos `retrato-*.json` e `retrato-*.md` com data de
  modificação superior a 30 dias dentro de `$JANGADA_ESTADO/vigia/` são
  removidos automaticamente. Nenhum arquivo fora dessa pasta ou com outro
  prefixo é apagado pela limpeza de retenção.
