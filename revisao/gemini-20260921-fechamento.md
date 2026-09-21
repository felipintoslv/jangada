# Parecer: fechamento do benchmark de agentes

- Data: 21/09/2026
- Commits: db70c2d..f026c23
- Revisor: agy (Antigravity), --effort high
- Veredito: revisar


### 1. Quebra sob `set -e` ao abrir terminal do Jangada Shell em janela
- Arquivo e linha: [bin/jangada-shell](../bin/jangada-shell#L30-L34)
- Gravidade: alto
- Certeza: alta
- Problema: No bloco `if ((janela)); then`, a linha 30 executa `[[ -n "$destino" ]] && args+=("$destino")` e a linha 32 executa `[[ -z "$destino" ]] && jangada_focar_classe org.jangada.shell && exit 0`. O script usa `set -euo pipefail`. Quando invocado sem destino (o caso padrão vindo de atalhos e menus), `[[ -z "$destino" ]]` é verdadeiro (0), acionando `jangada_focar_classe org.jangada.shell`. Se nenhuma janela da classe `org.jangada.shell` estiver aberta no momento, a função retorna status 1. Por estar encadeada com `&& exit 0` no nível superior do script (fora de um `if`), a falha de `jangada_focar_classe` faz a linha inteira avaliar como 1, disparando o `set -e` e abortando o script imediatamente. Com isso, a linha 33 (`exec ... jangada-terminal`) nunca é alcançada e o terminal nunca abre quando não há uma janela prévia.
- Correção proposta: Substituir o encadeamento `&&` por um bloco condicional seguro:
```bash
if [[ -n "$destino" ]]; then
  args+=("$destino")
elif jangada_focar_classe org.jangada.shell; then
  exit 0
fi
```

### 2. Laço de restauração em lote aborta precocemente se uma sessão falhar
- Arquivo e linha: [bin/jangada-agentes](../bin/jangada-agentes#L446-L449)
- Gravidade: alto
- Certeza: alta
- Problema: Na opção `--restaurar`, a iteração sobre as sessões usa:
```bash
while IFS=$'\t' read -r est s _resto; do
  [[ "$est" == interrompido ]] || continue
  restaurar "$s" && n=$((n + 1))
done < <(listar)
```
Se `restaurar "$s"` falhar (por exemplo, se o diretório do worktree foi removido manualmente do disco ou estiver corrompido, fazendo `restauravel` retornar 1), a expressão `restaurar "$s" && n=$((n + 1))` resulta em status de saída 1. Como o corpo de um laço `while` não é uma condição de teste isenta sob `set -e`, o bash aborta o script imediatamente na primeira falha, impedindo a restauração de quaisquer outras sessões subsequentes da fila.
- Correção proposta: Trocar o `&&` por um `if`:
```bash
if restaurar "$s"; then
  n=$((n + 1))
fi
```

### 3. Limpeza periódica de órfãos apaga JSONs de trabalho do `jangada-par`
- Arquivo e linha: [bin/jangada-agentes](../bin/jangada-agentes#L122-L144) e [bin/jangada-par](../bin/jangada-par#L485)
- Gravidade: alto
- Certeza: alta
- Problema: A função `limpar_orfaos()` itera incondicionalmente sobre `"$estado_dir"/*.json`. O script [bin/jangada-par](../bin/jangada-par#L485) grava a resposta do revisor no mesmo diretório em `json_revisao="$estado_dir/revisao-$sessao-r$rodada.json"`. Como o arquivo de revisão não é uma sessão tmux viva, não possui `.pid` de processo nem o campo `.agente` de um estado válido, `limpar_orfaos()` (invocado a cada 2 segundos pelo monitor do painel e a cada chamada da Waybar) considera o arquivo como órfão e executa `rm -f "$arq"` (linha 143), apagando a revisão no meio da execução do ciclo em par.
- Correção proposta: Salvar arquivos intermediários e pareceres em um subdiretório separado (ex.: `$estado_dir/dados/` ou `$estado_dir/revisoes/`), ou filtrar o glob em `limpar_orfaos` para ignorar prefixos que não correspondam a descritores de sessão (como `revisao-*`).

### 4. Condição de corrida sem bloqueio nos arquivos de estado da sessão
- Arquivo e linha: [bin/jangada-hook-claude](../bin/jangada-hook-claude#L61-L70) e [bin/jangada-agentes](../bin/jangada-agentes#L156-L165)
- Gravidade: alto
- Certeza: alta
- Problema: Os hooks do Claude Code gravam eventos de forma concorrente e assíncrona executando `jq ... "$arq" >"$tmp" && mv "$tmp" "$arq"`. Ao mesmo tempo, o painel de agentes e a Waybar chamam `marcar` em [bin/jangada-agentes](../bin/jangada-agentes#L156-L165) realizando exatamente o mesmo ciclo de leitura, alteração e `mv` sobre o mesmo arquivo. Não há nenhum bloqueio de arquivo (`flock`). Quando um evento do hook (como a captura de `session_id` em `SessionStart` ou `PostToolUse`) ocorre no mesmo instante de uma verificação do painel, a gravação de um processo sobrescreve a do outro, descartando campos recém-adicionados como o `.conversa` (ID da sessão) ou corrompendo a transição de estado.
- Correção proposta: Usar bloqueio mútuo exclusivo com `flock` (disponível por padrão no pacote `util-linux`) em todas as rotinas que leem e atualizam `$estado_dir/$sessao.json`:
```bash
(
  flock -x 200
  # operações de jq e mv aqui
) 200>"$arq.lock"
```

### 5. `jangada-agente-fim --integrar`: risco de mesclar em raiz com alterações pendentes e exclusão sem confirmação
- Arquivo e linha: [bin/jangada-agente-fim](../bin/jangada-agente-fim#L60-L85) e [bin/jangada-agente-fim](../bin/jangada-agente-fim#L124-L130)
- Gravidade: alto
- Certeza: alta
- Problema:
  1. A validação confere se o `$worktree` está sem alterações pendentes (`git -C "$worktree" status --porcelain`), mas não verifica se o repositório principal (`$raiz`) está limpo. Se houver alterações locais não commitadas no diretório principal na branch `$base`, o `git merge --no-ff` misturará essas modificações no commit de merge ou falhará com conflitos.
  2. Se a tarefa não tiver commits além da base (`novos` vazio na linha 72), a mensagem de que não há commits é exibida, mas a flag `apagar_ramo=1` é ligada (linha 84) sem pedir confirmação do usuário (a função `confirmar` só existe no bloco `else`). Em seguida, o ramo é apagado sumariamente em `limpar()`.
  3. Na linha 127, `git -C "$raiz" branch -d "$ramo" && echo "ramo apagado: $ramo"` está sob `set -e`. Se a exclusão do ramo falhar por qualquer motivo (por exemplo, se o worktree ainda mantiver referência no git antes do `worktree prune`), o comando avalia como falso e o script aborta sem executar a linha 131 (`rm -f "$arq"`), deixando o estado da sessão ativo no painel.
- Correção proposta:
  1. Checar se a raiz principal está limpa antes de mesclar:
     `[[ -z "$(git -C "$raiz" status --porcelain)" ]] || { echo "o repositório principal ($raiz) tem alterações não salvas; salve ou descarte antes de integrar" >&2; exit 1; }`
  2. Solicitar confirmação do usuário antes de apagar o ramo quando não houver novos commits.
  3. Substituir a linha 127 por um `if git -C "$raiz" branch -d "$ramo"; then ... fi` para não abortar a remoção do arquivo de estado caso a exclusão do ramo falhe.

### 6. Restauração de sessão sem ID de conversa retoma conversa arbitrária via `claude --continue`
- Arquivo e linha: [bin/jangada-agentes](../bin/jangada-agentes#L370-L376)
- Gravidade: médio
- Certeza: alta
- Problema: Em `restaurar()`, quando o campo `conversa` não existe no estado, o comando executado recebe `--continue`. O `--continue` do Claude Code busca a conversa mais recente registrada naquele diretório. Caso o agente tenha trabalhado diretamente no repositório principal (`--direto`) ou se mais de um agente tiver sido aberto na mesma pasta, `--continue` pode retomar a conversa de outro agente ou de uma sessão manual alheia. Além disso, se nenhuma conversa prévia tiver sido iniciada na pasta, `claude --continue` falha na inicialização com erro, deixando a sessão recém-criada no tmux morta.
- Correção proposta: Se `conversa` estiver vazia, alertar o usuário no terminal de que o ID da conversa não foi encontrado em vez de passar `--continue` cegamente, ou solicitar confirmação para abrir uma nova conversa limpa.

### 7. Perda de mensagens de estado e inconsistência de campos no hook do Claude Code
- Arquivo e linha: [bin/jangada-hook-claude](../bin/jangada-hook-claude#L15-L20), [bin/jangada-hook-claude](../bin/jangada-hook-claude#L48) e [bin/jangada-hook-claude](../bin/jangada-hook-claude#L65-L68)
- Gravidade: médio
- Certeza: alta
- Problema:
  1. No hook do Claude Code, eventos como `Stop` (concluído) e `UserPromptSubmit` (trabalhando) não enviam o campo `.message` no JSON (o `UserPromptSubmit` envia `.prompt`, e `Stop` envia apenas metadados de sessão). A função `campo .message` resulta em string vazia.
  2. Na linha 67, a expressão do `jq` aplica `.mensagem = $m` incondicionalmente sempre que `$e != ""`. Com isso, o campo `.mensagem` existente é apagado em todo ciclo `Stop`, fazendo com que a notificação de conclusão (linhas 80-82) mostre sempre o texto de fallback `"sem mensagem"`.
  3. No evento `fim` (SessionEnd), linha 48, se `.reason` não for informado ou for vazio, a mensagem gravada fica como `"Claude encerrado ()"`.
- Correção proposta:
  1. Alterar o `jq` na linha 67 para atualizar `.mensagem` somente quando `$m` for não-vazio: `(if $m != "" then .mensagem = $m else . end)`.
  2. No evento `Stop`, preencher uma mensagem padrão (ex.: `"Turno finalizado"` ou manter a última mensagem válida).
  3. Em `SessionEnd`, verificar se `.reason` é não-vazio antes de formatar os parênteses.

### 8. `jangada-par`: alterações rejeitadas podem persistir no worktree e falta validação de commits
- Arquivo e linha: [bin/jangada-par](../bin/jangada-par#L326-L328) e [bin/jangada-par](../bin/jangada-par#L398-L406)
- Gravidade: alto
- Certeza: alta
- Problema:
  1. Na função `avaliar_parecer`, o Claude roda com `--dangerously-skip-permissions`. O prompt instrui o Claude a implementar apenas o que aceitar e não commitar se rejeitar tudo. Porém, se o modelo editar ou criar arquivos para testar uma hipótese antes de rejeitar um apontamento e não desfizer a edição, essas modificações ficam soltas (dirty) na árvore de trabalho.
  2. A apuração de diferenças da rodada seguinte (linhas 404-405) calcula o diff apenas entre commits (`$ponto_base..HEAD`). As alterações soltas não entram no diff enviado ao revisor, mas continuam no disco, contaminando os testes subsequentes e bloqueando a integração posterior via `jangada-agente-fim --integrar` (que aborta caso o worktree tenha arquivos modificados).
  3. Se `base` estiver vazia (modo `--direto`), a linha 403 define `ponto_base="${base:-HEAD~1}"`. Na rodada 2, `git diff HEAD~1..HEAD` mostrará somente o último commit realizado, ocultando do Antigravity as alterações feitas nos commits anteriores da mesma tarefa.
- Correção proposta:
  1. Após o término da execução de `avaliar_parecer`, verificar `git status --porcelain`. Se houver arquivos modificados não commitados, descartá-los explicitamente (`git checkout -- . && git clean -fd`) para garantir que nenhum resíduo de item rejeitado permaneça na árvore.
  2. No modo `--direto`, salvar o commit SHA inicial no início do script para servir de referência estável em vez de `HEAD~1`.

### 9. Risco de falha com `E2BIG` no `jangada-par` quando a avaliação anterior for volumosa
- Arquivo e linha: [bin/jangada-par](../bin/jangada-par#L489-L506)
- Gravidade: médio
- Certeza: alta
- Problema: O script possui teto de segurança `PROMPT_BYTES_MAX=126000` para evitar o limite de tamanho de argumentos do kernel (`MAX_ARG_STRLEN`). No entanto, a rotina de ajuste calcula o orçamento e reduz exclusivamente o `diff_conteudo`. O conteúdo de `ultima_avaliacao` (saída integral do Claude Code capturada via `tee` na linha 344) é injetado via `$(secao_avaliacao)` sem qualquer controle de tamanho. Se a resposta de avaliação do Claude contiver saída detalhada de testes, código ou tabelas que superem 126 KB, o orçamento para o diff cai para zero, mas o prompt total continua acima do limite do sistema operacional, fazendo a chamada `agy "${args_agy[@]}"` abortar com o erro `E2BIG` (Argument list too long).
- Correção proposta: Limitar também o tamanho máximo de `ultima_avaliacao` inserido no prompt do revisor ou alimentar o prompt via entrada padrão/arquivo quando o tamanho ultrapassar o limite de argumentos de linha de comando.

### 10. `bin/jangada-importar`: omissão de saídas sem aspas do KDL e geração de Lua com `scale = auto`
- Arquivo e linha: [bin/jangada-importar](../bin/jangada-importar#L98-L100), [bin/jangada-importar](../bin/jangada-importar#L335-L338) e [bin/jangada-importar](../bin/jangada-importar#L349)
- Gravidade: médio
- Certeza: alta
- Problema:
  1. Em `textos(s)`, a expressão regular busca apenas strings delimitadas por aspas: `re.findall(r'"((?:[^"\\]|\\.)*)"', s)`. No KDL do niri, identificadores de nós podem ser escritos sem aspas (ex.: `output DP-1 { ... }`). Quando o nome da saída não tem aspas, `textos(cab)` retorna uma lista vazia `[]`, e o bloco `if not nome: continue` na linha 337 descarta o monitor silenciosamente, não gerando sua configuração em `monitores.lua.importado`.
  2. Na linha 349, `campos.append(f"scale = {esc if esc else lua_str('auto')}")`: se no KDL a escala estiver configurada explicitamente como `scale auto` (sem aspas), a função `valor()` retorna `"auto"`. Como `esc` é não-vazio, a linha gera `scale = auto` no Lua gerado. Em Lua, `auto` é tratado como uma variável global inexistente (`nil`), gerando tabela inválida para o Hyprland.
- Correção proposta:
  1. Se `textos(cab)` não encontrar strings entre aspas, obter o identificador imediatamente após a palavra `output`:
```python
nome = textos(cab) or re.findall(r'output\s+([^\s{]+)', cab)
```
  2. Tratar `esc` para que valores não numéricos sejam sempre delimitados como strings:
```python
campos.append(f"scale = {esc if esc and esc.replace('.','',1).isdigit() else lua_str(esc or 'auto')}")
```

### 11. `bin/jangada-update`: `sudo pacman -Syu` aborta o script sob `set -e` e omite diagnósticos de boot
- Arquivo e linha: [bin/jangada-update](../bin/jangada-update#L66) e [bin/jangada-update](../bin/jangada-update#L91-L100)
- Gravidade: alto
- Certeza: alta
- Problema: Na linha 66, `sudo pacman -Syu` é executado com `set -euo pipefail`. Se a transação do pacman encontrar falha em hooks críticos do ALPM (como `mkinitcpio` ou `dkms`), o comando `pacman` encerra com código de saída 1. O `set -e` aborta imediatamente a execução do script na linha 66. Com isso, as linhas 91 a 100, cujo propósito é justamente inspecionar o `/var/log/pacman.log` em busca de falhas em `mkinitcpio` ou `dkms` para avisar o usuário antes de reiniciar ("confira antes de reiniciar (sudo mkinitcpio -P refaz as imagens)"), NUNCA são executadas quando ocorre um erro real na geração da imagem de boot.
- Correção proposta: Capturar o status de retorno do pacman sem abortar antes das verificações:
```bash
st_pacman=0
sudo pacman -Syu || st_pacman=$?
```
e prosseguir com a leitura dos erros de boot no log para que o usuário receba o alerta antes do encerramento com erro.

### 12. `bin/jangada-update`: atualização parcial silenciosa entre repositórios oficiais e AUR
- Arquivo e linha: [bin/jangada-update](../bin/jangada-update#L68-L74)
- Gravidade: médio
- Certeza: alta
- Problema: O script roda `sudo pacman -Syu` e depois tenta atualizar o AUR com `"$aur" -Sua || echo "!! falha na atualização do AUR"`. Vários pacotes do ecossistema Hyprland monitorados em `conjunto_hypr` (como `noctalia-shell-git` ou `quickshell-git`) residem no AUR. Se o pacman atualizar o Hyprland oficial (com nova ABI) e a compilação do AUR falhar, o script apenas emite um eco e continua o fluxo, aplicando migrações e chamando `jangada-recarregar`. Isso deixa o sistema em estado de atualização parcial, quebrando a interface gráfica ativa.
- Correção proposta: Verificar se pacotes pertencentes a `conjunto_hypr` estavam pendentes no AUR; caso a etapa do AUR falhe, alertar expressamente sobre a quebra de compatibilidade binária e orientar a resolução antes de recarregar a sessão.

### 13. `bin/jangada-agente`: falha por EOF ao rodar sem terminal e sem prompt
- Arquivo e linha: [bin/jangada-agente](../bin/jangada-agente#L111)
- Gravidade: baixo
- Certeza: alta
- Problema: Quando o comando é chamado sem terminal na entrada padrão (`! -t 0`), sem `--prompt` e sem `--nome`, a execução atinge a linha 111: `read -r -p "nome da tarefa... " nome`. Como `stdin` não é interativo e chega de imediato ao fim do arquivo (EOF), o `read` retorna status 1. Sob `set -e`, o script encerra de forma abrupta sem mensagens claras.
- Correção proposta: Proteger a leitura com fallback ou checagem de terminal:
```bash
if [[ -t 0 ]]; then
  read -r -p "nome da tarefa (vazio = trabalhar direto no repositório): " nome || nome=""
else
  nome=""
fi
```

### 14. `bin/jangada-config`: detecção automática de repositório restrita à capitalização `~/Projetos`
- Arquivo e linha: [bin/jangada-config](../bin/jangada-config#L15) e [bin/jangada-config](../bin/jangada-config#L626-L628)
- Gravidade: baixo
- Certeza: alta
- Problema: A variável `JANGADA_PROJETOS` assume o padrão fixo `"$HOME/Projetos"`. A atribuição automática `JANGADA_REPO="$JANGADA_PROJETOS/jangada"` procura apenas nessa pasta. Em máquinas onde o usuário utiliza diretórios em minúsculas (como `~/projetos/jangada`) ou convenções internacionais (`~/projects`, `~/src`, `~/dev`), `JANGADA_REPO` permanece vazio. Isso quebra a execução de `jangada-verificar --agente`, que falha informando que `JANGADA_REPO` não foi encontrado.
- Correção proposta: Expandir a busca em diretórios comuns caso `JANGADA_REPO` não esteja definido:
```bash
if [[ -z "$JANGADA_REPO" ]]; then
  for _d in "$JANGADA_PROJETOS/jangada" "$HOME/projetos/jangada" "$HOME/projects/jangada" "$HOME/src/jangada"; do
    if [[ -d "$_d/.git" ]]; then JANGADA_REPO="$_d"; break; fi
  done
fi
```

### 15. `default/matugen/config.toml`: caminhos de saída absolutos ignoram `$XDG_CONFIG_HOME` alternativo
- Arquivo e linha: [default/matugen/config.toml](../default/matugen/config.toml#L12-L36)
- Gravidade: baixo
- Certeza: alta
- Problema: As saídas de templates geradas pelo matugen utilizam caminhos fixos iniciados por `~/.config/jangada/...`. Caso o usuário defina uma variável de ambiente `XDG_CONFIG_HOME` apontando para outro local (ex.: partição dedicada, dotfiles em repositório ou pasta temporária de testes), o `matugen` continuará gravando obrigatoriamente dentro de `~/.config/jangada`, divergindo dos caminhos lidos pelos demais scripts do framework.
- Correção proposta: Parametrizar o `config.toml` ou gerar a configuração do matugen em tempo de instalação respeitando `$JANGADA_CONFIG`.

---

## Portabilidade

- **Nomes de monitores**: A regra específica de compensação de DPI para `DP-3` foi removida de `base.css` no commit `f026c23` e mantida apenas como exemplo comentado em `style.css.modelo`. No entanto, em `bin/jangada-importar`, saídas de monitor declaradas sem aspas no KDL do niri são descartadas.
- **Variáveis de GPU importadas**: O comando `bin/jangada-importar` copia variáveis de ambiente do niri (como `LIBVA_DRIVER_NAME="nvidia"`) diretamente para `usuario.lua.importado`, o que quebra a aceleração de vídeo por hardware se o arquivo for importado em máquinas com placas AMD ou Intel.
- **Detecção de repositório e diretório de projetos**: `bin/jangada-config` ancora os projetos em `$HOME/Projetos`. Em máquinas configuradas em inglês ou com caixas baixas (`~/projects`, `~/projetos`, `~/src`), a detecção automática de `JANGADA_REPO` não localiza a cópia de trabalho.
- **Dependência de pacotes adicionais**: O comando `checkupdates` em `bin/jangada-update` depende de `pacman-contrib`; sem ele, a conferência de atualizações do Hyprland falha silenciosamente. A manipulação de imagens depende estritamente do binário `magick` (`imagemagick`), sem o qual os papéis de parede em monitores de aspecto diferente não são redimensionados.
- **Configuração do Matugen e caminhos XDG**: `default/matugen/config.toml` tem caminhos de saída fixados em `~/.config/jangada/`, ignorando `$XDG_CONFIG_HOME` quando este aponta para diretório alternativo.

---

## Resumo

A série de 11 commits auditados (`db70c2d..f026c23`) trouxe avanços estruturais importantes para o framework, incluindo a camada de avaliação crítica dos pareceres pelo Claude Code antes de aplicar correções, suporte a perfis de agentes em arquivos `.conf`, registro e restauração de sessões interrompidas via `claude --resume`, integração automatizada de worktrees com `--integrar` e a ferramenta de migração a partir do niri.

Entretanto, foram identificados pontos de fragilidade que impactam a robustez do fluxo em produção:
1. **Comportamento sob `set -e`**: Ocorrências de comandos em cadeia com `&&` no nível do script (como em `bin/jangada-shell`) causam abortos prematuros ao abrir janelas caso a janela alvo ainda não exista, e a restauração de agentes em lote interrompe prematuramente na primeira falha.
2. **Concorrência e limpeza indesejada**: A ausência de bloqueios em arquivos JSON permite que o painel e os hooks assíncronos do Claude Code sobrescrevam dados mútuos (perdendo IDs de sessão). Além disso, `limpar_orfaos` apaga arquivos de trabalho do `jangada-par` (`revisao-*.json`) enquanto o ciclo ainda está ocorrendo.
3. **Fluxo do `jangada-par` e do `jangada-agente-fim`**: O protocolo em par ainda não isola a árvore de trabalho de alterações em itens rejeitados que tenham sido deixados pelo Claude, e o prompt para o revisor pode exceder os limites de linha de comando (`E2BIG`). No `--integrar`, faltam travas para impedir mesclagens quando o repositório principal estiver sujo, além do risco de exclusão prematura do ramo sem confirmação caso nenhum commit novo tenha sido registrado.
4. **Atualizações de sistema**: Em `bin/jangada-update`, a execução de `sudo pacman -Syu` sob `set -e` aborta imediatamente em caso de erro nos hooks do ALPM, mascarando os alertas diagnósticos de falha na geração da imagem de boot do kernel.

