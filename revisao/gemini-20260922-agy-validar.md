# Revisão do jangada (20260922-agy-validar)

Aqui está a revisão técnica detalhada do commit que integra o Antigravity (agy) como agente de sessão no jangada.

### 1. Nomes das opções de ferramentas da CLI do Claude Code em jangada-validar
- Arquivo e linha: [bin/jangada-validar](file:///home/felipinto/Projetos/jangada/bin/jangada-validar#L148-L149)
- Gravidade: crítico
- Certeza: alta (a confirmar no binário local com `claude --help | grep -i tool`)
- Problema: A CLI oficial do Claude Code padroniza seus argumentos em kebab-case (`--allowed-tools` e `--disallowed-tools`). A notação camelCase (`--allowedTools` e `--disallowedTools`) não é reconhecida pelo analisador de opções do Claude Code, que aborta a execução com erro (`error: unknown option '--allowedTools'`). Como o bloco está sob `if ! (cd "$dir" && ...) >"$saida.tmp"`, qualquer chamada a `jangada-validar` falha imediatamente na linha 153 com a mensagem "a chamada ao Claude falhou", impedindo a revisão do diff. Convém também confirmar se a ferramenta de leitura de arquivos no binário instalado chama-se `Read` ou `View`.
- Correção proposta:
```bash
if ! (cd "$dir" && env -u JANGADA_SESSAO JANGADA_HOOK_DESLIGADO=1 claude -p \
      --model "$modelo" \
      --allowed-tools "Read,Grep,Glob" \
      --disallowed-tools "Bash,Edit,Write,NotebookEdit,WebFetch,WebSearch" \
      <<<"$pedido") >"$saida.tmp"; then
```

### 2. Modo direto omite commits do agente durante a validação
- Arquivo e linha: [bin/jangada-validar](file:///home/felipinto/Projetos/jangada/bin/jangada-validar#L68-L72)
- Gravidade: alto
- Certeza: alta
- Problema: Quando o agente trabalha em modo direto (sem worktree, opção `--direto`), a variável `base` fica vazia no estado da sessão. O script define `base` como o próprio ramo atual (por exemplo, `main`). Em seguida, `ponto="$(git merge-base "$base" HEAD)"` resulta no próprio `HEAD`. Com isso, `git diff "$ponto"` compara `HEAD` com a árvore de trabalho (mostrando apenas arquivos não commitados), e `git log "$ponto..HEAD"` fica vazio. Se o agente seguir a regra 3 do protocolo ("Faça commits pequenos..."), os commits realizados não entram no diff nem no histórico enviado ao Claude. Se a árvore de trabalho estiver limpa, o comando encerra na linha 82 informando que não há nada a revisar. No worktree isso não ocorre porque o ramo bifurca da base.
- Correção proposta:
```bash
ponto=""
[[ -n "$base" ]] && ponto="$(git -C "$dir" merge-base "$base" HEAD 2>/dev/null || true)"
if [[ -z "$ponto" || "$ponto" == "$(git -C "$dir" rev-parse HEAD)" ]]; then
  # No modo direto, se HEAD já é a base, compara a partir do início registrado no estado
  ponto="$(jq -r '.inicio // empty' "$arq_estado" 2>/dev/null || true)"
fi
[[ -n "$ponto" ]] || ponto="$(git -C "$dir" rev-parse HEAD)"
```
*(Nota: requer gravar o commit inicial em `bin/jangada-agente` quando `eh_git` estiver ativo e `worktree` for vazio, de forma análoga ao que é feito no `bin/jangada-par`)*.

### 3. Criação de cópia de segurança indevida para arquivo inexistente em mesclar_hooks_agy
- Arquivo e linha: [install/lib.sh](file:///home/felipinto/Projetos/jangada/install/lib.sh#L195), [L207](file:///home/felipinto/Projetos/jangada/install/lib.sh#L207)
- Gravidade: médio
- Certeza: alta
- Problema: Em sistemas onde `~/.gemini/config/hooks.json` ainda não existe, a linha 195 cria o arquivo com `echo '{}' >"$cfg"`. Mais adiante, na linha 207, `copia_seguranca "$cfg"` é chamado antes do `mv`. Como o arquivo foi criado na linha 195, a função encontra o arquivo e gera um backup `hooks.json.jangada-*.bak` contendo apenas `{}`. Isso contraria a regra 3 do `AGENTS.md` ("Arquivos existentes só mudam depois de copia_seguranca"), gerando arquivos de backup desnecessários na primeira instalação.
- Correção proposta:
```bash
mesclar_hooks_agy() {
  local cfg="$HOME/.gemini/config/hooks.json" novos tmp existia=0
  novos="$(sed "s|@JANGADA_PATH@|$JANGADA_PATH|g" "$JANGADA_PATH/default/agy/hooks.json")"
  if simulando; then
    info "[simulação] instalaria os hooks do jangada em $cfg"
    return 0
  fi
  mkdir -p "$(dirname "$cfg")"
  [[ -f "$cfg" ]] && existia=1 || echo '{}' >"$cfg"
  tmp="$(mktemp)"
  if ! jq --argjson novos "$novos" '. + $novos' "$cfg" >"$tmp"; then
    rm -f "$tmp"
    aviso "não consegui ler $cfg; hooks do agy não instalados"
    return 0
  fi
  if [[ "$(jq -cS . "$tmp")" == "$(jq -cS . "$cfg")" ]]; then
    rm -f "$tmp"
    ok "hooks do agy já instalados"
    return 0
  fi
  ((existia)) && copia_seguranca "$cfg"
  mv "$tmp" "$cfg"
  ok "hooks do agy instalados em $cfg"
}
```

### 4. Reconhecimento de status aprovado sensível a cabeçalhos markdown
- Arquivo e linha: [bin/jangada-validar](file:///home/felipinto/Projetos/jangada/bin/jangada-validar#L159)
- Gravidade: médio
- Certeza: média
- Problema: A expressão regular `^\**STATUS:\**[[:space:]]*\**APROVADO` exige que a linha inicie exatamente no começo (`^`), permitindo apenas asteriscos antes de `STATUS:`. Modelos de linguagem frequentemente formatam títulos usando marcações markdown como `## STATUS: APROVADO` ou `### STATUS: APROVADO`. Quando isso ocorre, o `grep` falha e o parecer é classificado como `REVISAR`, exigindo rodadas manuais ou forçadas mesmo com o parecer favorável.
- Correção proposta:
```bash
status="REVISAR"
grep -qEi '^[#[:space:]*]*STATUS:[[:space:]*]*APROVADO' "$saida" && status="APROVADO"
```

### 5. Arquivo temporário de prompt não removido no encerramento da sessão
- Arquivo e linha: [bin/jangada-agente-fim](file:///home/felipinto/Projetos/jangada/bin/jangada-agente-fim#L140-L143)
- Gravidade: baixo
- Certeza: alta
- Problema: Em `bin/jangada-agente`, o prompt inicial acompanhado do protocolo é gravado em `$estado_dir/prompt-$sessao.md`. Ao encerrar a sessão com `bin/jangada-agente-fim`, o arquivo de estado `.json` e os arquivos de validação `validacao-$s-r*.md` são excluídos, mas `prompt-$s.md` permanece no diretório `~/.local/state/jangada/agentes/`.
- Correção proposta:
```bash
  rm -f "$arq"
  rm -f "$JANGADA_ESTADO/agentes/prompt-$s.md"
  # Os pareceres do jangada-validar contam as rodadas: uma sessão nova com o
  # mesmo nome começa da primeira.
  rm -f "$JANGADA_ESTADO/agentes/validacao-$s-r"*.md
```

### 6. Verificação estática não valida a sintaxe de default/agy/hooks.json
- Arquivo e linha: [testes/verificar.sh](file:///home/felipinto/Projetos/jangada/testes/verificar.sh#L48)
- Gravidade: baixo
- Certeza: alta
- Problema: O script de validação estática do repositório confere a integridade do JSON de `default/claude/hooks.json`, mas não inclui o novo arquivo `default/agy/hooks.json`. A regra 6 do `AGENTS.md` determina que `testes/verificar.sh` seja executado antes de concluir qualquer mudança.
- Correção proposta:
```bash
passo "JSON"
jq empty default/claude/hooks.json || falha "claude/hooks.json"
jq empty default/agy/hooks.json || falha "agy/hooks.json"
```

### 7. Mensagem de erro ao carregar perfil omite caminho padrão do sistema
- Arquivo e linha: [bin/jangada-agente](file:///home/felipinto/Projetos/jangada/bin/jangada-agente#L81)
- Gravidade: baixo
- Certeza: alta
- Problema: Em `bin/jangada-config`, a função `jangada_perfil` passou a buscar arquivos tanto em `$JANGADA_CONFIG/agentes/$1.conf` quanto em `$JANGADA_PATH/default/agentes/$1.conf`. Quando o perfil informado não existe, a mensagem de erro ainda aponta unicamente para `$JANGADA_CONFIG/agentes/$perfil.conf`.
- Correção proposta:
```bash
  if ! jangada_perfil "$perfil"; then
    echo "perfil não encontrado em $JANGADA_CONFIG/agentes/$perfil.conf nem em $JANGADA_PATH/default/agentes/$perfil.conf" >&2
    echo "perfis existentes: $(jangada_perfis | tr '\n' ' ')" >&2
    exit 1
  fi
```

### 8. Restauração de sessão agy em modo direto sem aviso no terminal
- Arquivo e linha: [bin/jangada-agentes](file:///home/felipinto/Projetos/jangada/bin/jangada-agentes#L202-L210)
- Gravidade: baixo
- Certeza: alta
- Problema: Na função `restaurar`, para o agente Claude, quando a sessão não possui `conversa` gravada e não possui worktree próprio, há uma mensagem de diagnóstico informando a abertura de uma nova conversa. Para o `agy`, caso a sessão esteja no modo direto e sem identificador de conversa, o comando simplesmente inicia sem parâmetros nem aviso no terminal.
- Correção proposta:
```bash
  if [[ "$(basename "${agente%% *}")" == agy ]]; then
    # O id vem do hook do agy (conversationId). Sem ele, o --continue retoma a
    # conversa mais recente do agy, que pode ser de outra pasta: só no worktree.
    if [[ -n "$conversa" ]]; then
      cmd+=" --conversation $(printf '%q' "$conversa")"
    elif [[ -n "$(jq -r '.worktree // ""' "$arq")" ]]; then
      cmd+=" --continue"
    else
      echo "$s: sem o id da conversa e sem worktree próprio; abrindo conversa nova" >&2
    fi
  fi
```

---

### O que está correto

1. **Isolamento de ambiente nas chamadas de apoio:** O uso de `env -u JANGADA_SESSAO` em `bin/jangada-par` e `bin/jangada-validar`, associado a `JANGADA_HOOK_DESLIGADO=1`, impede que os hooks de sessão registrem estados falsos ou disparem notificações na área de trabalho durante tarefas de revisão em segundo plano.
2. **Entrega de instruções iniciais via send-keys:** A construção `cmd_agente+=" -i \"\$(cat $(printf '%q' "$arq_prompt"))\""` protege contra expansão antecipada no shell e divisão de palavras. Aspas, quebras de linha e caracteres especiais no texto do prompt não provocam injeção de comandos na subshell da sessão tmux.
3. **Resiliência do hook do agy:** `bin/jangada-hook-agy` emite `echo '{}'` logo no início para cumprir o contrato síncrono exigido pelo agy CLI. Todo o bloco de persistência e notificação roda redirecionado para `/dev/null` sem `set -e`, garantindo que eventuais problemas de estado nunca interrompam o agente.
4. **Tratamento de fullyIdle:** A verificação explícita com `if .fullyIdle == false then "false" else "true" end` no `jq` contorna adequadamente a pegadinha do operador `//` no jq (onde `false // true` avalia para `true`).
5. **Segurança no envio de notificações:** O despacho via `setsid -f bash -c '...' _ "$urg" ...` com argumentos posicionais evita interpolação de variáveis em strings executadas pelo shell.
6. **Precedência e mesclagem de perfis:** A alteração em `jangada_perfil` e `jangada_perfis` em `bin/jangada-config` respeita a prioridade da configuração do usuário sobre os arquivos fornecidos em `default/agentes/`, desduplicando entradas e ignorando o modelo `exemplo.conf`.
7. **Controle de concorrência com trava:** A atualização dos arquivos de estado em `bin/jangada-hook-agy` e `bin/jangada-validar` utiliza `jangada_alterar_estado` com `flock` sobre `.trava`, prevenindo condições de corrida entre turnos simultâneos.
8. **Idempotência de migração e instalação:** `migrations/202609221000-agy-hooks-validar.sh` e `mesclar_hooks_agy` checam o conteúdo antes de reescrever e respeitam `JANGADA_SIMULAR=1`.

---

### Perguntas ao autor

1. **Parâmetros de permissão do Claude Code:** A sua instalação local do Claude Code aceita a flag `--allowed-tools` em kebab-case e lista a ferramenta de leitura como `Read` (em vez de `View`)? Vale rodar `claude --help | grep -E 'allowed|tool'` para confirmar a sintaxe exata antes de subir a correção.
2. **Validação no modo direto:** O fluxo de trabalho com o agy deve suportar oficialmente `--direto`, ou o protocolo assume obrigatoriamente o uso de worktrees isolados? Se o modo direto for mantido como opção válida para o agy, é necessário persistir o commit inicial no arquivo de estado para que `jangada-validar` saiba qual trecho revisar após commits locais.
