# Interface, temas e atalhos

## Interface

| Interface | Componentes | Condição |
|---|---|---|
| `JANGADA_INTERFACE=componentes` | waybar, fuzzel e mako, com cores do matugen | configuração padrão |
| `JANGADA_INTERFACE=noctalia` | Noctalia já instalado, preservando suas personalizações | exige a interface antiga `qs -c noctalia-shell` |

A escolha fica em `~/.config/jangada/jangada.conf`. A integração ainda usa
Quickshell; a incompatibilidade registrada com o Noctalia 5.x permanece
pendente em [PENDENCIAS.md](historico/revisao/PENDENCIAS.md#o-que-só-pode-ser-confirmado-no-desktop).
Até essa adaptação, use `componentes` se a instalação não oferecer a
interface antiga.

O botão do Catamarã não faz parte da barra do jangada. Na cópia pessoal da
barra, a atualização tira o botão quando a definição é a que o jangada ou
o próprio Catamarã punham; uma definição pessoal diferente fica, com aviso. Os indicadores do jangada ficam na aba
Indicadores da Central.

## Cores e papel de parede

`jangada-tema imagem` gera com o matugen as cores de bordas de janela, barra, notificações, menu, bloqueio, terminal e tela de login. A cor-fonte é escolhida pelo `prefer` do `default/matugen/config.toml`, e o esquema vem de `JANGADA_TEMA_ESQUEMA` (padrão `scheme-fidelity`, que mantém a cor da imagem; o `scheme-tonal-spot` do matugen satura imagens quase monocromáticas até virarem outra cor).

O papel de parede aparece inteiro em todas as telas. Numa tela de proporção diferente da imagem, como um monitor 21:9 com uma figura 16:9, o `jangada-tema` gera uma versão com as medidas da tela (em `~/.cache/jangada/papel`) e a entrega ao swaybg e ao hyprlock; o tema de login faz a mesma conta em cada tela. `JANGADA_PAPEL_AJUSTE` escolhe como completar o espaço que sobra: `espelho` (padrão, reflete a borda da figura), `desfoque`, `cor` ou `cobrir` (o comportamento antigo, que corta a figura).

O [vidro fosco](vidro-fosco.md) é ligado por padrão para janelas e
componentes. `JANGADA_VIDRO=0` em `jangada.conf`, seguido de `jangada-vidro`,
desliga transparência e desfoque. Jogos identificados e tela cheia suspendem
o desfoque; vídeos embutidos numa página não são detectados automaticamente.

## Tela de login (SDDM)

`jangada-sddm aplicar` instala o tema `jangada` em `/usr/share/sddm/themes/jangada` e faz o SDDM ler as sessões de `/usr/local/share/jangada/sessoes`, que só contém o jangada. Os arquivos de sessão dos outros pacotes (Hyprland, niri, Plasma) não são movidos nem apagados; `jangada-sddm restaurar` remove `/etc/sddm.conf.d/zz-jangada.conf` e todas voltam a aparecer. O prefixo `zz-` faz o arquivo ser lido depois do `kde_settings.conf`, que de outro modo imporia o tema escolhido no Plasma.

O tema imita o menu do `SUPER + Esc`: caixa centralizada com as mesmas medidas do fuzzel, linhas `usuário >` e `senha >` e a lista **Entrar**, **Suspender**, **Reiniciar** e **Desligar**. Setas escolhem a ação e Enter executa; digitar a senha volta a seleção para Entrar. As cores vêm de um modelo próprio do matugen (`default/matugen/modelos/sddm.conf`, gerado em `~/.config/jangada/sddm/theme.conf.user`), com os mesmos papéis de cor do fuzzel, e o fundo é o papel de parede atual, copiados no momento do `aplicar`. O SDDM fica numa pasta do sistema, então o `jangada-tema` não consegue atualizá-lo sozinho: quando as cores ou o papel de parede mudam, ele avisa que é preciso rodar `jangada-sddm aplicar` de novo. `jangada-sddm testar` abre o tema numa janela, sem alterar o sistema.

A instalação pergunta se deve aplicar a exclusividade; a resposta padrão é não.

## Atalhos principais

| Atalho | Ação |
|---|---|
| `SUPER + Enter` | terminal |
| `SUPER + Espaço` | lançador de aplicativos |
| `SUPER + A` | novo agente |
| `SUPER + SHIFT + A` | lista de agentes |
| `SUPER + CTRL + A` | painel de agentes (workspace especial) |
| `SUPER + N` | próximo agente que espera resposta; repetir percorre a fila |
| `SUPER + SHIFT + N` | volta ao agente focado antes do atual |
| `SUPER + Esc` | menu jangada |
| `SUPER + CTRL + R` | recarregar e mostrar erros de configuração |
| `SUPER + /` | mostra todos os atalhos ativos, pesquisáveis |

A lista completa aparece no `SUPER + /`, que lê os atalhos do próprio Hyprland
e por isso inclui também os que você definiu em
`~/.config/jangada/hypr/usuario.lua`. Os padrões estão em
`default/hypr/atalhos.lua`.

## Central de tarefas v0.1

`jangada-tarefas`, `SUPER + SHIFT + A` e `SUPER + CTRL + A` abrem a central.
A aparência segue o guia [`identidade-visual.md`](identidade-visual.md).
Cada sessão representa uma tarefa. Pendências aparecem primeiro, seguidas
por interrupções, trabalho em andamento e tarefas prontas para conferir.

A consulta automática roda a cada dois segundos, preservando a seleção.
Uma falha preserva os últimos dados e o histórico, com aviso de erro; as ações
sobre sessões ficam desabilitadas até a próxima consulta bem-sucedida.
O detalhe mostra última atividade, saída recente do terminal e até 50 mudanças
observadas nesta janela. O histórico começa ao abrir a central, fica em memória
e recomeça quando a execução da sessão muda. Sessões que saem da lista deixam
de ser acompanhadas. A coluna Atualização usa a data
publicada pelo agente, sem tratar uma consulta recente como atividade recente.

**Pronto para conferir** corresponde ao estado `concluido` dos hooks.
Ele não confirma conclusão da tarefa nem aprovação da entrega.
Os hooks não registram falha da tarefa nem integração. Por isso, a Central
não deriva os estados Falhou e Integrada; encerramentos removem a sessão da lista.
Perguntas e permissões são atendidas pelo botão **Abrir terminal**.
Sessões interrompidas podem ser retomadas pelo mesmo botão.
Na tarefa selecionada, **Conferir e integrar** (`Alt+I`) consulta
`jangada-agentes --integracao-json` e mostra arquivos, linhas, revisão e SHA.
A confirmação gráfica vincula base e candidato; `jangada-agente-fim`
exige aprovação independente e reconfere a marca sob a trava.
A Central não aprova entregas; a indicação local informa o registro disponível,
sem certificar uma passagem quando falta dado.
**Integrar pelo terminal** preserva o diagnóstico e as confirmações originais.
**Encerrar sem integrar** (`Ctrl+X`) chama
`jangada-agente-fim` sem integração. As ações pelo terminal mantêm as conferências, a revisão e a confirmação
de descarte quando há alterações sem commit. A integração gráfica mostra
seu resultado na aba Entrega e impede fechar a Central enquanto está em curso.
A lista acompanha automaticamente o encerramento. Terminais abertos pela
Central permanecem abertos quando ela fecha. Enquanto a ação está em andamento, outra ação de
encerramento para a mesma sessão fica bloqueada, inclusive ao reabrir a central.
Se o terminal sair antes de iniciar a ação, o bloqueio é liberado após dez segundos.
Cada tentativa usa uma pasta própria; um terminal atrasado não inicia a tentativa anterior após a liberação.
Se o terminal for morto à força depois de iniciar a ação, sem executar a limpeza,
o bloqueio permanece até encerrar a sessão gráfica. Registros inconsistentes
(como duas tentativas na mesma pasta) também mantêm esse bloqueio.
Isso evita uma segunda integração durante uma operação sem acompanhamento.
No formulário Nova tarefa, `Ctrl+X` continua recortando texto.
A central não encerra agentes ao fechar. A janela observa substituições dos arquivos de estado e consulta a cada
30 segundos como reserva. Eventos próximos são agrupados por 200 ms.
A consulta da janela apenas lê os
registros; o contador da barra mantém a limpeza automática de estados órfãos
e o registro persistente das interrupções, pelo mecanismo anterior.

**Nova tarefa** pede projeto e pedido, com modo **Recomendado**.
Esse modo escolhe o primeiro executor instalado na ordem de
`jangada-agente --capacidades-json`, atualmente Claude e depois Codex.
Revisor, segurança e delegação seguem os padrões configurados do lançador.
As opções avançadas ficam recolhidas e preservam agente e perfil; também
permitem escolher revisor e delegação. A opção antiga **Sem isolamento**
continua no formulário, mas é ignorada com aviso: o agente roda isolado.
Alterar um controle seleciona o modo Personalizado; recolher a área preserva as escolhas.
A barra do topo segue a ordem do trabalho: **Novo projeto**, **Novo coordenador**
e **Nova tarefa**. **Novo projeto** pede o nome (ou uma pasta existente) e cria a
pasta vazia em `JANGADA_PROJETOS`. A Central não inicia o git nem faz commit: só
lê o repositório. Pasta que já é repositório com commit é cadastrada, e a Central
oferece abrir o coordenador nela. Pasta sem repositório mostra o aviso "Esta pasta
ainda não é um repositório git. Rode no terminal:" com os dois comandos
(`git -C PASTA init` e `git -C PASTA commit --allow-empty -m "Inicia repositório"`),
**Copiar comandos** e **Já rodei, conferir**, que cadastra a pasta quando ela já
tem ao menos um commit. Nenhum arquivo é apagado ou sobrescrito.
**Nova pasta**, no formulário, usa o mesmo caminho e deixa a pasta selecionada.
Uma pasta escolhida que não é repositório git mostra o mesmo aviso, em vez de
seguir para uma abertura que falharia. A conferência do git roda fora da linha da
interface: o formulário mostra "Conferindo o repositório git da pasta...", fica
desligado até a resposta, menos Fechar, e a janela segue respondendo; o prazo de
20 segundos da abertura só começa depois dela. Todos os botões que conferem o git
(Iniciar tarefa, Escolher pasta, Nova pasta, "Já rodei, conferir" e os de Novo
projeto) passam pela mesma conferência, uma por vez, e só o resultado da
conferência atual muda o campo. Fechar o diálogo cancela a conferência e
descarta o resultado; um cadastro já pedido ao Core termina e o projeto entra na
Central, sem mudar o diálogo.
**Iniciar tarefa** abre o agente num terminal da Central. Se ele falhar, o terminal
fica aberto com a mensagem, e a Central mostra as últimas linhas do erro quando a
tarefa não entra na lista em 20 segundos: a Central reconsulta aos 15 e conclui aos 20.
**Painel de indicadores** leva à aba Indicadores.
Aprovações nativas e envio de respostas ficam fora desta versão.

Na Waybar, `custom/agentes` passa a contar tarefas, andamento, pendências e
interrupções. O contador consulta a cada dez segundos, com atualização imediata
pelo sinal dos hooks. Clique abre ou foca a central existente; botão direito abre
Nova tarefa. O sinal 10 continua reservado aos estados das sessões.
Falhas aparecem como erro, sem um zero que pareça uma consulta bem-sucedida.
O consumo do Claude está disponível em `jangada-consumo --curto`.

### Instalação e atualização

A dependência `python-pyqt6` já pertence à etapa 10 da instalação.
Uma instalação nova usa os padrões da etapa 40. Em instalações existentes,
`jangada-update` aplica `202610031500-central-tarefas.sh` pelo migrador.
A migração guarda cópia de segurança e altera apenas os comandos anteriores
conhecidos em uma cópia própria da Waybar, preservando comentários e controles
personalizados. Sem cópia própria, a barra usa o padrão atualizado.

Rode `jangada-update` na instalação e `jangada-barra` para carregar o módulo.
Se a dependência estiver ausente, instale `python-pyqt6` antes de abrir a central.
Para conferir a migração sem aplicar, na cópia instalada:

```sh
JANGADA_SIMULAR=1 bash "$JANGADA_PATH/migrations/202610031500-central-tarefas.sh"
```

Para revisar o visual no worktree, sem agentes ou configuração ativa:

```sh
JANGADA_PATH="$PWD" bin/jangada-tarefas --simular
```

### Central única

`SUPER+A` e **Nova tarefa** no menu abrem o formulário da central de tarefas.
Os atalhos de acompanhamento e os cliques da barra usam essa mesma central.
O formulário oferece Claude e Codex como agentes principais e os perfis
configurados: `claude-codex`, `codex-claude` e os pessoais. A escolha do perfil preserva
executor, revisor e delegação. O agy atende as delegações e a revisão.

Os comandos antigos `jangada-agentes --janela`, `--painel`,
`--janela-anterior`, `--painel-anterior` e `jangada-tarefas --anterior`
encaminham para a central de tarefas. `JANGADA_CENTRAL` deixou de selecionar
outra interface. A criação de sessões pelo terminal continua disponível
com `jangada-agente`.

### Atuação dos coordenadores

A coluna de coordenadores distingue o ciclo da atuação da sessão em execução.
Com `ciclo=aberta` e sem processo, mostra **aguardando retomada** e mantém as
tarefas. Resposta pronta (`concluido`) e hook encerrado não finalizam a atuação.
O ciclo só termina por fechamento explícito no Core.

**Retomar** usa projeto e provedor registrados. Em **Novo coordenador**, um
projeto com atuação aberta oferece retomada, com escolha explícita do provedor.
Ambos chamam `jangada-coordenador --projeto CAMINHO --provedor P --janela`;
o Core decide entre criar e retomar. Uma sessão viva recebe somente foco na
mesma janela. Trocar provedor exige saída voluntária anterior. A Central e o
login não iniciam coordenações automaticamente.

**Provedores.** O seletor de **Novo coordenador** oferece `claude`, `codex` e
`agy (Argon High)`. O Core abre o agy com modelo fixo e grava `provedor: "agy"`
no registro; a Central mostra esse nome na lista e no painel. Um provedor que
esta Central não conhece, trazido por um Core mais novo, não derruba a lista:
a linha aparece com "provedor não reconhecido por esta Central", e Retomar e
Finalizar atuação ficam desligados nela, com o motivo no painel. Em Novo
coordenador, um projeto cujo coordenador tem provedor desconhecido e atuação
aberta não pode ser aberto por ali.

**Faixa de cotas.** Linha fixa no alto da janela, abaixo dos botões e acima dos
cartões de contagem, visível em todas as abas. Mostra, na ordem do `cotas.json`,
cada conta do agy (`agy principal`, `agy reserva`) com os grupos e o percentual
(`gemini-argon-wtu` como "Argon", `gemini` como "Gemini", os demais pelo
identificador), o Codex com o percentual do grupo `codex` e o Claude como "não
medido aqui". O `renova_em` aparece em horário local curto junto do grupo de menor
percentual de cada provedor, e "lido às HH:MM" vem do campo `gerado`. Só aparece
percentual que veio no JSON e passou por `numero_de_fora`; nada é estimado.

Grupo abaixo de 20% mostra o texto "abaixo de 20%", o glifo Ⅱ e a cor de alerta das
fichas. A cor nunca vai sozinha e não há cor por provedor. Grupo com `percentual`
nulo mostra "sem dado" e o motivo: cache ausente (`sem_cache`), cache vencido
(`cache_vencido`), consulta falhou (`consulta_falhou`) ou conta sem confiança
(`conta_sem_confianca`). Motivo desconhecido mostra só "sem dado".

Com Core sem o comando, erro, prazo esgotado, saída grande demais ou JSON inválido,
a faixa mostra "Cotas: sem dado" e o motivo curto, sem diálogo de erro. Sempre que
houver "sem dado", a faixa mostra como texto o comando que o dono roda no terminal:
`jangada-router cotas --atualizar --permitir-remoto`. A Central não roda esse comando.

A consulta é `jangada-router cotas`, a mesma do diálogo Novo coordenador, uma só
por vez. Roda ao abrir a Central e a cada 60 segundos, em segundo plano, sem shell,
sem `--atualizar` e sem `--permitir-remoto`. Durante uma nova consulta, a faixa
mantém a última leitura. Na simulação a faixa mostra "Cotas: sem dado" e a
Central não consulta o Core.

**Barras de cota.** A aba Indicadores tem um quarto cartão, Cotas, depois de Local
e agy. O destaque é a menor cota medida (ou "sem dado") e o apoio diz de qual conta
e grupo; o rodapé conta os grupos medidos e traz "lido às HH:MM". Com o cartão
escolhido, no lugar da tabela aparece uma barra horizontal por grupo de cada conta
do agy (Gemini, 3p, Argon, conforme a conta tiver) e do Codex. Cada linha traz o
rótulo, a barra preenchida no percentual e o número em texto ao lado, mais "renova
HH:MM" quando o Core informa; a barra nunca é a única forma de ler o número. O
Claude aparece como "não medido aqui", sem barra.

Abaixo de 20% a barra usa a cor de alerta das fichas e o texto ganha o glifo Ⅱ e
"abaixo de 20%". Grupo com só o último valor conhecido (`ultimo`) mostra a barra em
tom apagado e o texto como na faixa, por exemplo `95% (às 16:27)`, sem alerta. Grupo
sem dado mostra a barra vazia e "sem dado" com o motivo. Sem leitura nenhuma (Core
sem o comando, erro, prazo, simulação), no lugar das barras vai a mesma frase da
faixa. As cores vêm só das fichas dos dois temas, sem cor por provedor. As barras
usam a consulta da faixa: mudam quando a faixa muda, sem processo nem temporizador
próprios. Cada barra tem nome acessível com o texto inteiro da linha, e a área das
barras entra na ordem de foco depois do botão Atualizar.

Em janela pequena a faixa ocupa no máximo duas linhas. Se o texto completo não
cabe, ela usa uma forma resumida (o menor grupo de cada provedor e, por fim, a
menor cota com a contagem de "sem dado"). A dica de ferramenta sempre traz o texto
inteiro.

**Cota do Argon.** Ao abrir Novo coordenador, a Central usa a consulta de `jangada-router cotas`
da faixa (uma por vez; se há uma em andamento, espera por ela e não abre outra),
em segundo plano, sem shell, sem `--atualizar` e sem `--permitir-remoto`, com prazo de
30 segundos e limite de 1 MiB na saída. Esse comando só lê o que o Core já tem
em disco e nunca consulta o agy. A Central usa o grupo `gemini-argon-wtu` do
agy, da conta `principal`: se ela existe, só ela vale, e sem o grupo nela o
resultado é sem dado. Sem `principal`, vale a única conta do agy. Com `percentual` de 20 ou mais, a opção
fica ativa e mostra o valor. Abaixo de 20, a opção fica desligada com "Cota do
Argon abaixo de 20%" e a data de `renova_em`, quando o Core a informa. Sem o
grupo, com `percentual` nulo, com o comando ausente (Core anterior), com erro,
prazo esgotado ou JSON inválido, a opção continua disponível e o diálogo avisa
"Cota do Argon sem dado: o Core confere antes de abrir", seguido do comando que
o dono roda no terminal para atualizar:
`jangada-router cotas --atualizar --permitir-remoto`. A Central não roda esse comando.

**Abertura sem sessão.** Depois de "Abertura ou retomada solicitada", a Central
reconsulta a lista a cada segundo. Se em 20 segundos não aparecer coordenador
vivo daquele projeto e provedor, o aviso passa a "O Core não abriu o coordenador",
com a causa provável de cada provedor e o comando
`jangada-coordenador --projeto PASTA --provedor P` para rodar no terminal. Para o
agy a causa provável é cota ou catálogo do Argon: o Core confere os dois antes de
criar a sessão e, se falhar, só escreve o motivo na saída de erro. O prazo é só do relógio da Central e vence aos 20 segundos mesmo com uma
consulta da lista em curso. Se nenhuma lista válida, lida depois do pedido, chegou
antes do vencimento (consulta falhou, expirou ou veio inválida), o aviso passa a
"Não foi possível conferir se o Core abriu o coordenador", com o mesmo comando, e
não afirma que o Core não abriu. Uma consulta que termina depois do vencimento não
reabre o acompanhamento nem muda o aviso. A janela continua destacada e a Central
não captura essa saída. Um aviso de outra ação, posto nesse intervalo, não é
substituído.

**Finalizar atuação** exige confirmação com a sessão sem processo. Antes,
salve o estado e o diário e saia voluntariamente. A Central reconfere a atuação
e chama `jangada-coordenador --finalizar SESSAO`. O Core preserva as pendências
e arquiva o checkpoint. Com sessão viva, a Central orienta salvar e sair,
oferecendo **Ir para a janela**. Ela não envia instruções ao cliente nem usa
a API antiga `--fim`, que mata a sessão.

As janelas são lançadas por `QProcess.startDetached`, com argumentos separados
e canais independentes da Central, inclusive com Core anterior. A Central
informa a solicitação e atualiza a consulta; não acompanha a duração do cliente.
Fechar a Central, repetir uma ação ou atingir um prazo não encerra essas janelas.
Só a operação finita `--finalizar` tem captura de saída, prazo de 30 segundos
e encerramento do subprocesso ao vencer o prazo. Falha aparece na coluna;
sucesso atualiza a consulta. As ações bloqueiam tentativas simultâneas durante
a reconferência e a finalização. Seleção e rascunhos são preservados.
**Copiar e ir para a janela** continua copiando e focando, sem colar ou enviar.

A consulta `--coordenadores-json` continua na versão 1. A Central valida
`ciclo`, `atuacao_id` e o tipo booleano de `retomavel`. O Core informa a
disponibilidade da retomada; `False` mantém a lista atualizada e desabilita
Retomar, inclusive no diálogo Novo coordenador. `True` só habilita a ação
com ciclo aberto e sessão sem processo. Campos ausentes indicam Core anterior,
com aviso e sem as ações novas; as ações anteriores continuam disponíveis.
A simulação não consulta esses dados nem cria, retoma ou finaliza sessões reais.
