# Avaliação: parecer do fechamento do benchmark de agentes

- Data: 21/09/2026
- Commits: db70c2d..f026c23
- Revisor: Claude
- Veredito: aprovado com ressalvas (7 aceitos, 6 aceitos em parte, 2 rejeitados)
- Parecer avaliado: [gemini-20260921-fechamento.md](gemini-20260921-fechamento.md)

O parecer tem 15 itens. Cada um foi conferido no código e, quando a afirmação
era sobre o comportamento do bash, testado num exemplo mínimo. As correções
estão no commit que acompanha este arquivo.

| Nº | Apontamento | Veredito | Motivo verificado | Ação |
|---|---|---|---|---|
| 1 | `jangada-shell` aborta sob `set -e` quando não há janela para focar | REJEITADO | `a && f && exit 0` com `f` falhando não encerra o script: o `set -e` ignora as falhas de uma lista `&&` fora do último comando | nenhuma |
| 2 | `--restaurar` em lote para na primeira falha | REJEITADO | mesmo caso: `restaurar "$s" && n=...` dentro do `while` continua | nenhuma |
| 3 | `limpar_orfaos` apaga o `revisao-*.json` do par | ACEITO | o JSON bruto não tem pid nem estado, e a barra o apagava a cada poucos segundos. Explica a pegadinha de 20/09 ("o JSON bruto sumiu nas duas falhas"), que ficou sem causa até agora. No meio do ciclo não quebrava nada, porque o par guarda a resposta na memória | `eh_estado` em `bin/jangada-agentes`: lista e limpeza ignoram `revisao-*` |
| 4 | gravação do estado sem trava | ACEITO EM PARTE | o `PostToolUse` roda um hook por ferramenta, em paralelo quando as ferramentas são paralelas, e cada um lê, altera e troca o arquivo. A perda é pequena porque todo evento regrava a conversa, mas a trava é barata. Com o painel a corrida é rara: ele só marca sessões sem tmux e sem pid | `jangada_alterar_estado` em `bin/jangada-config` (flock em `agentes/.trava`), usada pelo hook e pelo `marcar` |
| 5 | `--integrar`: raiz com alterações, ramo apagado sem confirmação, `branch -d` sob `set -e` | ACEITO EM PARTE | (1) procede em parte: o git já recusa o merge com índice alterado ou arquivo em conflito, mas deixa passar arquivo alterado que o ramo não toca, e o motivo sai confuso. (2) rejeitado: ramo sem commits além da base não guarda nada, e o `-d` confere a mesclagem. (3) rejeitado pelo mesmo motivo dos itens 1 e 2 | conferência da raiz antes do merge, com a lista dos arquivos |
| 6 | restauração sem id retoma conversa alheia com `--continue` | ACEITO EM PARTE | direto no repositório, a conversa mais recente da pasta pode ser de outro agente. No worktree ela é da própria sessão. A sessão do tmux não morre se o `claude` falhar, porque o comando vai por `send-keys` para um shell | sem id e sem worktree, abre conversa nova e avisa |
| 7 | mensagem do hook apagada no `Stop` e "Claude encerrado ()" | ACEITO | só o `Notification` traz `.message`; o aviso de conclusão dizia sempre "sem mensagem" | mensagem de `.message`, `.last_assistant_message` ou `.prompt` (primeira linha); sem nenhuma, mantém a anterior; "turno concluído" no Stop; parênteses só com motivo |
| 8 | par: resto sem commit no worktree e `HEAD~1` no modo direto | ACEITO EM PARTE | o modo direto mostrava só o último commit na rodada 2, e o que ficava sem commit não chegava ao revisor. Descartar com `git clean -fd`, como o parecer propõe, apagaria trabalho sem ninguém ver | ponto de partida do ciclo guardado (`inicio`), merge-base no worktree, diff até a árvore de trabalho, arquivos novos listados e aviso na tela. Teste no `testes/par.sh` (caso 3) |
| 9 | avaliação longa estoura o limite do argumento | ACEITO | o corte só mexia no diff | `AVALIACAO_MAX` (30 000 bytes) com a íntegra liberada ao revisor por `--add-dir` |
| 10 | importador: saída sem aspas e `scale auto` | ACEITO | o KDL 2 aceita nome sem aspas; `scale auto` gerava `scale = auto`, variável Lua indefinida | nome sem aspas aceito; escala não numérica vira `"auto"`. Casos novos em `testes/importar.sh` |
| 11 | `pacman -Syu` com falha aborta antes da conferência da imagem de boot | ACEITO | é justamente o caso em que a conferência importa | a falha é registrada, a conferência roda e o script sai com erro no fim |
| 12 | falha no AUR segue para a recarga | ACEITO EM PARTE | os pacotes citados (`noctalia-shell-git`, `quickshell-git`) não estão no `conjunto_hypr`, mas o risco existe | com falha no pacman ou no AUR, migrações e recarga ficam de fora, com aviso de atualização parcial |
| 13 | `jangada-agente` sem terminal morre em silêncio no `read` | ACEITO | EOF no `read` com `set -e` | mensagem que pede `--nome`, `--prompt` ou `--direto` |
| 14 | `JANGADA_REPO` só em `~/Projetos` | ACEITO EM PARTE | o `JANGADA_PROJETOS` já é configurável no `jangada.conf`; varrer nomes de pasta seria adivinhar | quando não acha, usa o `origin` da cópia instalada, se for pasta local |
| 15 | matugen grava em `~/.config/jangada` fixo | ACEITO | com `XDG_CONFIG_HOME` em outro lugar, o tema ia para a pasta errada, e um teste isolado escreveria na configuração real | `jangada-tema` usa uma cópia temporária do `config.toml` com o destino trocado |

Da seção de portabilidade, a nota sobre variáveis de GPU no importador foi
aceita: `LIBVA_DRIVER_NAME`, `GBM_BACKEND`, `__GLX_VENDOR_LIBRARY_NAME` e
afins saem comentadas no `usuario.lua.importado`, porque o jangada escolhe a
GPU sozinho (`JANGADA_GPU`). A falta do `pacman-contrib` e do `imagemagick`
não procede para instalação nova: os dois estão em `install/pacotes/`.

## Evidência dos itens rejeitados

Itens 1, 2 e 5.3, com `set -euo pipefail`:

```sh
$ bash -c 'set -euo pipefail; f(){ return 1; }; d=""; [[ -z "$d" ]] && f && exit 0; echo seguiu'
seguiu
$ bash -c 'set -euo pipefail; r(){ return 1; }; n=0
    while read -r s; do r "$s" && n=$((n+1)); done < <(printf "a\nb\n"); echo "seguiu n=$n"'
seguiu n=0
```

É o mesmo engano que o `jangada-par` já cita no prompt de avaliação ("já
apontou como fatal um `(( x )) && ...` que o set -e não interrompe").

Item 5.2: `git branch -d` recusa ramo não mesclado. Um ramo sem commits além
da base está mesclado por definição e não tem nada a perder.
