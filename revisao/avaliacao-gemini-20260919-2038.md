# Avaliação da revisão gemini-20260919-2038.md

Revisão feita pelo Gemini no Antigravity CLI, desta vez cobrindo bin/ e
install/. Avaliação feita pelo Claude, apontamento por apontamento, com
conferência no código-fonte do Hyprland e testes onde foi possível.

## Resumo

| Nº | Apontamento | Veredito | Ação |
|---|---|---|---|
| 1 | `hyprctl dispatch` não aceitaria expressões Lua | **Rejeitado (incorreto)** | nenhuma |
| 2 | Sessão gravada com `sudo tee` e sem cópia de segurança | Aceito | corrigido |
| 3 | `kill-session` antes da limpeza em jangada-agente-fim | Aceito, com outra correção | corrigido |
| 4 | jangada-tema --escolher sem pasta de imagens | Aceito em parte | corrigido |
| 5 | Mais arquivos sensíveis no filtro do jangada-mapear | Aceito, com expressão mais restrita | corrigido |
| 6 | `/.snapshots` existente e não montado | Aceito, com correção mais segura | corrigido |
| 7 | Worktree órfão registrado no git | Aceito | corrigido |
| 8 | `tomllib` exige Python 3.11 | Aceito (baixo impacto) | corrigido |

## Detalhes

**1. Rejeitado.** No Hyprland 0.55 com configuração em Lua, o `hyprctl dispatch`
passa o argumento para `hl.dispatch(...)`. O trecho está em
`src/debug/HyprCtl.cpp` (tag v0.55.3, função `dispatchRequest`): com
`CONFIG_LUA`, o comando vira `return hl.dispatch(<argumento>)`, e a sintaxe
antiga (`focuswindow`, `dpms off`, `exit`) recebe a nota "your syntax might
need to be updated". Aplicar a correção proposta quebraria o foco de janelas,
o painel de agentes, a saída da sessão e o desligamento da tela. A sessão
jangada usa Lua, então a forma atual (`hl.dsp.focus(...)`, `hl.dsp.dpms(...)`)
é a correta.

**2. Aceito.** Troca de `sudo tee` por `como_root tee` e `copia_seguranca`
antes de gravar, como pede o AGENTS.md.

**3. Aceito, com outra correção.** O problema é real: chamado de dentro da
própria sessão, o script morreria ao encerrá-la. A correção proposta (remover
o worktree antes de encerrar a sessão) apagaria a pasta com o agente ainda
rodando dentro dela. A solução adotada mantém a ordem segura (encerrar, remover,
apagar estado) e, quando o comando vem de dentro da sessão, faz a limpeza num
processo separado, com registro em `agentes/fim-<sessão>.log`. Testado.

**4. Aceito em parte.** O script não chegava a abortar (a falha era absorvida
por `|| exit 0`), mas terminava sem aviso. Agora mostra uma notificação.

**5. Aceito, com expressão mais restrita.** A expressão proposta
(`id_[a-z0-9_]+$`) excluiria arquivos legítimos cujo nome termina em
"id_alguma-coisa" (por exemplo, `grid_layout`). A adotada lista as chaves SSH
pelo nome (`id_rsa`, `id_dsa`, `id_ecdsa`, `id_ed25519` e `.pub`) e acrescenta
`.env`, `.netrc`, `.pgpass` e `.p12`.

**6. Aceito, com correção mais segura.** A proposta ignorava a falha do
`rmdir` e seguia. A adotada remove `/.snapshots` só se estiver vazia e, caso
contrário, interrompe a instalação com a orientação de conferir os subvolumes.

**7 e 8. Aceitos.** `git worktree prune` antes de criar o worktree; etapas de
TOML ignoradas com aviso quando o Python não tem `tomllib`.

## Perguntas ao autor

1. **Título da janela igual ao nome da sessão:** depende de o terminal aceitar
   o título enviado pelo tmux (`set-titles on`). Ghostty, kitty e foot aceitam
   por padrão, mas fica como ponto a confirmar no desktop (PENDENCIAS.md).
2. **Mesmo nome de tarefa no mesmo repositório:** por projeto, o nome é
   único. Rodar `jangada-agente` de novo com o mesmo nome reabre a sessão e
   o worktree existentes, em vez de criar outro. Para dois agentes em paralelo
   no mesmo repositório, usam-se nomes diferentes.

## Erro encontrado fora da revisão

Ao testar a correção 3, apareceu um erro que nenhuma das revisões apontou:
`tmux send-keys -t "=sessão"` não encontra o painel (o tmux exige
`"=sessão:"` quando o alvo é um painel). Com isso, o `jangada-agente` criava a
sessão mas não iniciava o agente, e o seletor do `jangada-agentes` não mostrava
a prévia. Corrigido em `bin/jangada-agente` e `bin/jangada-agentes` e testado.
