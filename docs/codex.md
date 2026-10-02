# Codex na Jangada

O Codex implementa no mesmo ciclo de worktree, tmux, validação e integração
usado pelos outros agentes. Há três perfis:

| Perfil | Implementa | Revisa |
|---|---|---|
| `codex` | Codex | Claude |
| `codex-codex` | Codex | outra instância do Codex |
| `codex-agy` | Codex | agy Flash, esforço alto |

```sh
jangada-agente --perfil codex --nome tarefa --prompt "Implemente a tarefa"
jangada-agente --perfil codex-codex --nome tarefa --prompt "Implemente a tarefa"
jangada-agente --perfil codex-agy --nome tarefa --prompt "Implemente a tarefa"
```

## Preparação

Instale o Codex CLI e faça `codex login` num terminal comum. A Jangada não
instala o CLI nem altera a configuração global dele. O adaptador exige uma
versão que ofereça `--no-daemon`, para não conectar a sessão a um processo
compartilhado fora do isolamento. A implementação foi conferida com a ajuda
do Codex CLI 0.159.2 e com executáveis simulados nos testes.

Os perfis são lidos diretamente de `default/agentes/`, com precedência da
cópia em `~/.config/jangada/agentes/`. Não exigem migração de configuração
ou instalação de hooks globais. A cópia instalada precisa receber a
atualização pelo fluxo habitual do `jangada-update`.

## Execução e isolamento

`bin/jangada-agente` chama `bin/jangada-codex` dentro do
`bin/jangada-isolar`. O adaptador acrescenta o protocolo por
`developer_instructions`, mantém `workspace-write`, pede permissões ao
usuário e usa `--no-daemon`. A pasta de estado é permitida ao isolamento
interno do Codex; as montagens do bubblewrap continuam limitando a escrita
aos arquivos de estado liberados pela Jangada.

O Codex exige isolamento, inclusive com `--sem-isolar` ou
`JANGADA_AGENTE_ISOLAR=0`. A chamada direta ao adaptador sem isolamento é
recusada antes de executar o CLI.

Dentro do bubblewrap, a pasta do Codex (`CODEX_HOME`, ou `~/.codex`) é
montada a partir de `~/.local/state/jangada/codex/SESSAO`. Conversas, bancos e
confiança dos hooks persistem ali. O `CODEX_HOME` não é trocado.
Configuração, autenticação, instruções globais, perfis, regras, skills,
plugins e hooks existentes são montados somente para leitura.
Arquivos de configuração ausentes ficam vazios; pastas de instruções
ausentes ficam vazias e somente leitura. A sessão não altera a configuração
do Codex aberto fora da Jangada.

No início da sessão, o adaptador pergunta se o usuário confia na pasta,
antes de executar o CLI. A confirmação fica em `jangada-confianca.json`
nos dados próprios da sessão, e a tabela `projects` com a entrada da pasta
é passada pela configuração da chamada. Assim o CLI não precisa gravar
no `config.toml` somente leitura. A pergunta não se repete na retomada da
mesma pasta; outra pasta exige nova confirmação. Uma entrada exata já
confiável na configuração global também dispensa a pergunta. Sem terminal
nem confiança registrada, o adaptador recusa abrir a sessão. O revisor
não passa por essa etapa, pois ignora a configuração do usuário e da pasta.

O parser de `-c` divide o nome da chave nos pontos, sem interpretar aspas
TOML nessa chave. Por isso a confiança vai como uma tabela TOML no valor
de `projects`, com o caminho entre aspas dentro da tabela. Usar
`projects."CAMINHO".trust_level` cria uma chave incorreta e deixa o CLI
pedir confiança novamente. O teste consulta `config/read` no Codex real,
quando instalado, para conferir o resultado sem fazer pedidos ao modelo.

Um endereço próprio em `CODEX_HOME` precisa ser absoluto e já existir.
`CODEX_SQLITE_HOME` é fixado na pasta montada para os bancos não escaparem
para um endereço global. O login não pode ser regravado dentro da sessão:
se exigir renovação, faça o login novamente no terminal comum.

O encerramento mantém os dados do Codex para preservar a conversa. Eles
ficam fora dos arquivos `agentes/SESSAO.json` removidos pela limpeza. Não há
limpeza automática desses dados nesta primeira integração.

## Hooks e estados

Os hooks são passados na configuração da chamada, sem editar
`~/.codex/config.toml`. O adaptador consulta `hooks/list` no Codex para
obter as chaves e hashes das oito definições da Jangada. Na primeira
abertura, mostra os comandos e pede autorização antes de abrir a conversa.
Uma recusa encerra a abertura; uma alteração na definição exige nova
autorização. A escolha fica em `jangada-hooks-confianca.json` nos dados da
sessão e entra pela tabela `hooks.state` na chamada. Outros hooks continuam
sujeitos à aprovação do próprio Codex. O revisor não passa por essa etapa.

Isso evita o `/hooks` tentando gravar a aprovação no `config.toml` montado
somente leitura. A consulta e a aprovação usam o CLI real, sem pedidos ao
modelo, e não desligam a verificação de confiança dos hooks.

O processo externo de `jangada-isolar` observa as gravações do arquivo de
estado da sessão com `inotifywait` e envia o sinal 10 à Waybar. O hook
isolado não enxerga o processo da barra no namespace de PID do host.
Sem o observador, a barra só perceberia o novo estado na consulta periódica
de 30 segundos. O observador é encerrado junto com o isolamento.

| Evento | Estado |
|---|---|
| `SessionStart` | `iniciado`, com UUID da conversa |
| `UserPromptSubmit`, `PreToolUse`, `PostToolUse` | `trabalhando` |
| `PermissionRequest` | `aguardando` |
| `Stop`, `Interrupt` | `concluido` |
| `SessionEnd` | `concluido`, com mensagem de encerramento |

`bin/jangada-hook-codex` não decide permissões: sua saída é vazia. Ele
atualiza apenas uma sessão existente, sob a trava comum, e grava mudanças
em `eventos-agentes.jsonl`. Eventos identificados como de subagente não
alteram o estado principal. A barra e o painel leem esses registros pelo
mecanismo existente. Perguntas ao usuário fora de `PermissionRequest` ainda
não têm estado de espera próprio.

## Restauração e delegação

`jangada-agentes --restaurar SESSAO` recompõe o comando da configuração
atual. Valida o UUID, a pasta, o agente e o revisor, ignora `.comando` e
`.isolar`, e refaz o protocolo antes de abrir a sessão.

Com UUID, usa `codex resume UUID`. Sem UUID, num worktree próprio, usa
`codex resume --last`, com o filtro de pasta do CLI. Sem UUID no modo direto,
abre uma conversa nova para não retomar a conversa de outro agente.

Os perfis `codex` e `codex-codex` usam `JANGADA_DELEGAR=local`: somente leitor e redator vão ao
Ollama, com arquivos explícitos. Os demais papéis ficam na sessão. Um perfil
com `JANGADA_DELEGAR=agy` permite delegar pelo `jangada-delegar` ao agy.
O perfil `codex-agy` já configura esse destino e fixa o revisor em
`gemini-3.8-flash-high`, evitando herdar o modelo principal do agy. Leitor
e redator continuam indo primeiro ao Ollama; os outros papéis usam Flash
com o esforço definido pelo papel. O protocolo do Codex não manda chamar
subagentes do Claude. Recusa local
nunca autoriza enviar documentos confidenciais a um provedor externo.

## Cota disponível

`jangada-router status --atualizar-codex --permitir-remoto` consulta somente
metadados pelo método `account/rateLimits/read` do Codex. Não inicia conversa,
gera texto, envia fontes ou ativa execução de ferramentas.

A consulta usa uma pasta temporária privada dentro do estado da orquestração,
com token de acesso existente e sem configuração do usuário. O token de
renovação não é transmitido nem copiado. Tokens vencidos ou com menos de
60 segundos de validade impedem a consulta e deixam o estado em `UNKNOWN`.
Encerra o grupo do processo e remove a pasta ao concluir, falhar ou receber
Ctrl-C, SIGTERM ou SIGHUP. Não faz login, não renova a credencial original e não usa
chaves de API do ambiente. Autenticação ausente ou incompatível deixa
o estado em `UNKNOWN`. O ambiente do filho contém somente caminhos
temporários, idioma, busca de executáveis, certificados e configuração de proxy.

O saldo registrado é o menor das janelas presentes no grupo de consumo
`codex`. Grupos diferentes não substituem esse saldo. Uma janela vencida
exige nova consulta; não se presume que a cota foi renovada. A observação
vale no máximo 60 segundos e expira antes da renovação mais próxima.
A reserva padrão é 25%, ajustável por `JANGADA_CODEX_COTA_MIN` entre 0 e 100.
Saldo zero produz `QUOTA_EXHAUSTED`; abaixo da reserva, `QUOTA_LOW`.
Pausa e espera vigente impedem a consulta.

Essa observação prepara a integração de executores Codex. A fila ainda usa
somente Ollama e agy. Não comprova acesso a um modelo específico nem cota
independente para variantes econômicas. Os estados continuam sendo dados
operacionais editáveis, não autorização para enviar fontes ou alterar recursos.

Referência: [cotas no Codex App Server](https://learn.chatgpt.com/docs/app-server#6-rate-limits-chatgpt).

## Revisão com Codex

`jangada-validar --revisor codex` também aceita `--modelo`. Sem modelo
explícito, usa o padrão do CLI com a configuração do usuário ignorada.
A revisão roda numa pasta temporária vazia, em `read-only`, sem retomada,
com `--ephemeral` e sem os hooks da sessão. Terminal, execução por código,
subagentes, plugins, aplicativos, navegador e busca externa são desativados.

Fora de uma sessão isolada, o revisor também passa pelo `jangada-isolar`,
mesmo com `JANGADA_AGENTE_ISOLAR=0`. Seus dados ficam em
`$JANGADA_ESTADO/codex/revisao-codex-ROTULO`, com login e configuração
somente leitura. A resposta sai por um arquivo da pasta temporária e o
processo pai grava o parecer em `revisoes/`. Dentro de uma sessão isolada,
usa a montagem do Codex já preparada nela. Por isso sessões de outros
agentes também recebem essa montagem quando há uma pasta do Codex existente.

O revisor recebe as regras da base, commits, diff e parecer anterior pela
entrada padrão. Nesta etapa ele avalia somente esse pedido, sem ler outros
arquivos do projeto. Isso preserva a proibição de comandos do protocolo.
Ausência de contexto pode resultar em `STATUS: REVISAR`.

A última mensagem é normalizada pelo mesmo mecanismo de Claude e agy.
Erro do processo não aprova a entrega, mesmo que tenha produzido um arquivo
com `STATUS: APROVADO`. A aprovação para integração continua sendo a revisão
externa para o commit exato e limpo, em `revisoes/`.

## Verificação

`testes/codex.sh` confere lançamento, protocolo, TOML, hooks e recusas.
`testes/restaurar.sh` cobre UUID, retomada por pasta e isolamento obrigatório.
`testes/isolar.sh` confere a separação dos dados e as montagens protegidas;
quando o ambiente permite bubblewrap, executa também esses controles.
`testes/validar.sh` verifica os pareceres e as falhas com Codex simulado.
`testes/cota-codex.py` confere protocolo, janelas, reserva, prazo, interrupção
e remoção de credenciais temporárias, sem serviços externos.

Referências: [CLI](https://learn.chatgpt.com/docs/developer-commands?surface=cli),
[configuração](https://learn.chatgpt.com/docs/config-file/config-reference) e
[hooks](https://learn.chatgpt.com/docs/hooks) da documentação oficial.
