# Parecer: atualização automática da cópia instalada e gancho pos-agente-fim

- Data: 22/09/2026
- Commits: 017358e..0fa4d4e
- Revisor: agy (Gemini 3.8 Flash High)
- Veredito: revisar

Revisão técnica das alterações em `bin/jangada-agente-fim`, `bin/jangada-gancho`, `README.md` e `default/claude/skills/jangada/agentes.md`.

### 1. Valor incorreto de integração para o gancho quando não há novos commits
- Arquivo e linha: [bin/jangada-agente-fim](file:///home/felipinto/Projetos/jangada/bin/jangada-agente-fim#L120-L135)
- Gravidade: alto
- Certeza: alta
- Problema: Quando `--integrar` era fornecido mas o ramo não continha commits além da base (`novos` vazio), o bloco do `merge` não era executado. No entanto, a variável `$integrar` permanecia com valor `1`, fazendo com que `pos-agente-fim` recebesse `1` como terceiro argumento, sinalizando indevidamente que houve integração.
- Correção proposta: Separar a opção de linha de comando (`integrar`) de uma flag de conclusão efetiva (`integrado=0`), que só passa para `1` após o sucesso do `git merge`.

### 2. Insegurança e erro semântico ao tratar URLs remotas em origem
- Arquivo e linha: [bin/jangada-agente-fim](file:///home/felipinto/Projetos/jangada/bin/jangada-agente-fim#L70-L77)
- Gravidade: alto
- Certeza: alta
- Problema: Se a cópia instalada tiver sido clonada de uma URL remota (HTTPS ou SSH), `origem` contém uma URL de rede. Chamar `realpath "$origem"` tenta resolver a string relativa ao diretório atual, resultando em caminho inexistente ou inválido.
- Correção proposta: Seguir a convenção canônica de `bin/jangada-config:58`, testando se `[[ "$origem" == /* && -d "$origem/.git" ]]` antes de chamar `realpath`.

### 3. Falta de conferência do ramo ativo em JANGADA_PATH antes do pull
- Arquivo e linha: [bin/jangada-agente-fim](file:///home/felipinto/Projetos/jangada/bin/jangada-agente-fim#L80-L85)
- Gravidade: médio
- Certeza: alta
- Problema: Se a cópia instalada estivesse em outro canal ou ramo (ex: `estavel` ou um ramo temporário), rodar `git pull --ff-only` tentaria mesclar a ponta errada ou falharia.
- Correção proposta: Verificar se o ramo ativo em `$JANGADA_PATH` coincide com `$base` antes de disparar o pull.

### 4. Exportação de variáveis para o processo em segundo plano (setsid)
- Arquivo e linha: [bin/jangada-agente-fim](file:///home/felipinto/Projetos/jangada/bin/jangada-agente-fim#L185)
- Gravidade: médio
- Certeza: alta
- Problema: Ao encerrar a sessão de dentro dela mesma, o processo desanexado precisa receber a flag de integração efetiva para repassar ao gancho `pos-agente-fim`.
- Correção proposta: Incluir a variável `integrado` na lista de exports do `setsid`.
