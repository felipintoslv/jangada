# Avaliação da revisão gemini-20260921-0909-itens1a3.md

Revisão feita pelo Gemini no Antigravity CLI sobre os três commits dos itens 1
a 3 do benchmark (preparo do worktree, skill do Claude Code e
`jangada-agentes --proximo`). O prompt levou o `PROMPT_GEMINI.md`, a lista dos
arquivos alterados e o diff. Avaliação feita pelo Claude, apontamento por
apontamento, com teste de cada afirmação.

## Resumo

| Nº | Apontamento | Veredito | Ação |
|---|---|---|---|
| 1 | `((worktree_novo)) && ...` abortaria o jangada-agente com `set -e` | **Rejeitado (incorreto)** | nenhuma; trocar por `if` é opcional |
| 2 | `((copiados + ligados)) && echo` abortaria o preparo | **Rejeitado (incorreto)** | nenhuma; trocar por `if` é opcional |
| 3 | `git ls-files` devolve caminho com acento entre aspas e em octal | Aceito, com outra correção | a decidir |
| 4 | Título da janela comparado por igualdade exata no `--proximo` | Rejeitado | nenhuma |
| 5 | `reflink_provavel` falha entre subvolumes btrfs | Aceito em parte, com outra correção | a decidir |

Achado fora da revisão, anterior a estes commits: `listar` do
`jangada-agentes` perde campos quando um deles vem vazio (detalhe no fim).

## Detalhes

**1. Rejeitado.** O `set -e` do bash não encerra o script quando o comando que
falha é um dos que vêm antes do último numa lista `&&`. Teste:
`bash -c 'set -euo pipefail; x=0; ((x)) && echo nunca; echo seguiu'` imprime
"seguiu". O caso em que a linha derruba o script é quando ela é o último
comando de uma função, porque a função devolve 1. Nos dois arquivos, a linha
está no nível de cima do bloco `if`, seguida de `dir="$worktree"`. O worktree
reaproveitado segue normalmente. Trocar por `if` evita que alguém mova a linha
para o fim de uma função sem perceber, e só por isso pode entrar.

**2. Rejeitado.** Pelo mesmo motivo. Teste: o preparo num repositório sem
`.worktreeinclude` nem `.jangada/links` terminou com status 0 e chegou ao
`exit 0`.

**3. Aceito, com outra correção.** O problema é real e, nos projetos em
português, é provável. Num repositório de teste com a pasta ignorada
`dados área/`, o `git ls-files` devolveu `"dados \303\241rea/"`, o
`check-ignore` não reconheceu esse texto e a pasta ficou de fora **sem
aviso**. Já `meu arquivo.env` foi copiado, então o problema é com acento, não
com espaço (o `core.quotePath` só põe aspas quando o nome tem acento, aspas,
barra invertida ou caractere de controle). A correção proposta,
`-c core.quotePath=false`, resolve o acento mas ainda põe aspas em nomes com
`"` ou quebra de linha. A correção melhor é `git ls-files -z` com
`mapfile -d ''`, que não põe aspas em nada.

**4. Rejeitado.** O título da janela do agente é o nome da sessão por
contrato (`set-titles-string "#S"` em `default/tmux/agentes.conf`), então a
igualdade exata é a comparação certa. A comparação por trecho proposta erra
com nomes que são prefixo um do outro: com `proj--a1` e `proj--a10` na fila, a
janela de `proj--a10` casaria com `proj--a1`. O `focar` usa `test($s)` como
segunda tentativa para achar a janela, não para decidir posição numa fila.

**5. Aceito em parte, com outra correção.** É verdade que cada subvolume btrfs
tem um `st_dev` próprio, e que o reflink funciona entre subvolumes do mesmo
sistema de arquivos. Com projetos e worktrees em subvolumes diferentes, o
limite de 500 MB seria aplicado sem necessidade. Nesta máquina não acontece:
`~/Projetos` e `~/.local/share` estão no mesmo subvolume (dev 53). A correção
proposta, porém, não resolve: no btrfs o `f_fsid` (`stat -f -c %i`) também
muda por subvolume, porque o kernel mistura nele o id do subvolume. O que
identifica o sistema de arquivos inteiro é o UUID: `findmnt -no UUID -T
<pasta>` devolveu o mesmo valor para `/home` e `~/Projetos` e outro para `/`.
Impacto baixo; o pior caso é uma recusa com aviso, nunca uma cópia errada.

**Perguntas ao autor.**

1. Falha do `.jangada/preparar.sh` só gera aviso, de propósito: o worktree
   já existe e o agente pode começar. O aviso aparece no terminal onde o
   agente é lançado. Um registro no estado do agente seria possível, mas não
   parece necessário agora.
2. `--selecionar S` para abrir o seletor já sobre a sessão: boa ideia e
   barata (`fzf --query`), mas é escopo novo.

## Achado fora da revisão

`listar`, em `bin/jangada-agentes`, lê a linha com `IFS=$'\t' read`. Tabulação
conta como espaço em branco para o `IFS`, então duas tabulações seguidas viram
uma, e um campo vazio desloca os seguintes. Com `dir` vazio, a data cai no
campo `dir`, `vencido ''` responde sim e a sessão some do painel. Os estados
gravados hoje sempre têm `dir`, então não aparece no uso normal. Surgiu nos
testes do `--proximo`, com estados montados à mão. Correção possível: trocar a
tabulação por um separador que não seja espaço em branco (`\x1f`) no jq e no
`read`, ou ler cada campo com seu próprio `jq -r`.
