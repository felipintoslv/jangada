# Interface, temas e atalhos

## Interface

| Interface | Componentes | Condição |
|---|---|---|
| `JANGADA_INTERFACE=componentes` | waybar, fuzzel e mako, com cores do matugen | configuração padrão |
| `JANGADA_INTERFACE=noctalia` | Noctalia já instalado, preservando suas personalizações | exige a interface antiga `qs -c noctalia-shell` |

A escolha fica em `~/.config/jangada/jangada.conf`. A integração ainda usa
Quickshell; a incompatibilidade registrada com o Noctalia 5.x permanece
pendente em [revisao/PENDENCIAS.md](../revisao/PENDENCIAS.md#o-que-só-pode-ser-confirmado-no-desktop).
Até essa adaptação, use `componentes` se a instalação não oferecer a
interface antiga.


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
Cada sessão representa uma tarefa. Pendências aparecem primeiro, seguidas
por interrupções, trabalho em andamento e turnos encerrados.

A consulta automática roda a cada dois segundos, preservando a seleção.
Uma falha preserva os últimos dados e o histórico, com aviso de erro; as ações
sobre sessões ficam desabilitadas até a próxima consulta bem-sucedida.
O detalhe mostra última atividade, saída recente do terminal e até 50 mudanças
observadas nesta janela. O histórico começa ao abrir a central, fica em memória
e recomeça quando a execução da sessão muda. Sessões que saem da lista deixam
de ser acompanhadas. A coluna Atualização usa a data
publicada pelo agente, sem tratar uma consulta recente como atividade recente.

**Turno encerrado** corresponde ao estado `concluido` dos hooks.
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
permitem escolher revisor, delegação e consultar a configuração de isolamento. O isolamento é obrigatório.
Alterar um controle seleciona o modo Personalizado; recolher a área preserva as escolhas.
**Nova pasta**, no formulário, cria a pasta de um projeto novo em
`JANGADA_PROJETOS` e a deixa selecionada; a pasta nasce sem repositório Git.
**Painel de indicadores** e **Conversa de Pescador** abrem os aplicativos
existentes.
Aprovações nativas e envio de respostas ficam fora desta versão.

Na Waybar, `custom/agentes` passa a contar tarefas, andamento, pendências e
interrupções. O contador consulta a cada dez segundos, com atualização imediata
pelo sinal dos hooks. Clique abre ou foca a central existente; botão direito abre
Nova tarefa. O sinal 10 continua reservado aos estados das sessões.
Falhas aparecem como erro, sem um zero que pareça uma consulta bem-sucedida.
O consumo do Claude saiu da dica da barra; continua disponível no painel
de indicadores e em `jangada-consumo --curto`.

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
