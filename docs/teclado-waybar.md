# Teclado na bandeja com escalas 1 e 2

O contorno troca somente `input-keyboard-symbolic` de 32px do Breeze na
busca de ícones da Waybar. A confirmação gráfica e a identidade do item
da sessão principal ainda estão pendentes.

## Evidência e causa

Em 11/10/2026, a máquina tinha Waybar 0.15.0-3, Fcitx5 5.1.23-1,
Breeze Icons 6.30.0-1, GTK 3.24.52-2 e librsvg 2.63.2-1.
As capturas autorizadas mostram teclado no HDMI-A-2, escala 1, e quadrado
na posição correspondente no DP-3, escala 2. Elas comprovam o defeito
inicial, sem identificar o processo nem comprovar o resultado do contorno.

A [Waybar 0.15.0](https://github.com/Alexays/Waybar/blob/0.15.0/src/modules/sni/item.cpp#L393-L409)
multiplica `icon-size` pela escala e carrega o ícone simbolicamente.
Com tamanho lógico 16, solicita arquivos de 16 e 32px.
A consulta local de `Gtk.IconTheme.lookup_icon`, com tema `breeze`, selecionou:

- `/usr/share/icons/breeze/devices/16/input-keyboard-symbolic.svg`, sem retângulo de fundo;
- `/usr/share/icons/breeze/devices/32/input-keyboard-symbolic.svg`, com `rect` de 22x22, transformado para 32x32, e `fill="none"`.

O [GTK 3.24.52](https://github.com/GNOME/gtk/blob/3.24.52/gtk/gtkicontheme.c#L4298-L4339)
aplica `fill` com `!important` também a `rect`. Tanto `rsvg-convert` com
essa regra quanto `Gtk.IconInfo.load_symbolic` num barramento privado
tornaram os 1.024 pixels do segundo arquivo opacos; o desenho desapareceu.
O arquivo de 16px manteve 170 pixels transparentes.
Isso comprova a incompatibilidade desse recurso com a recoloração do GTK.
Sua ligação com o item das capturas depende da consulta abaixo.

O [Fcitx5 5.1.23](https://github.com/fcitx/fcitx5/blob/5.1.23/src/modules/notificationitem/notificationitem.cpp#L78-L104)
usa `input-keyboard-symbolic` fora do KDE quando o estado pede um teclado.
Outros estados podem publicar nomes diferentes ou `IconName` vazio com
`IconPixmap` textual. A opção `tray.icons` da versão instalada seleciona
por aplicativo, sem distinguir esses estados; por isso não foi usada.

## Contorno e personalizações

`jangada-barra` gera uma sobreposição em seu estado, com o índice original
dos temas `breeze` e `breeze-dark` e um SVG próprio de teclado, sem fundo.
Acrescenta essa busca imediatamente antes de `/usr/share` em `XDG_DATA_DIRS`.
Os caminhos pessoais anteriores e `XDG_DATA_HOME` mantêm sua prioridade.
Uma busca personalizada que exclua `/usr/share` permanece intacta.

O tema escolhido, os demais recursos, os nomes e imagens publicados pelo
Fcitx5 continuam os mesmos. Cliques, menu e rolagem seguem no item nativo.
O tamanho lógico permanece 16. Não há dependência nova nem migração:
nenhum arquivo pessoal precisa mudar. O contorno vale na próxima partida
pelo lançador atualizado, mesmo com `config.jsonc` pessoal.

Para comparar ou reverter numa instância de teste, execute a Waybar
diretamente com a busca original, sem passar pelo lançador.
A sessão principal não foi alterada. Esta entrega contorna um recurso
externo; não modifica a implementação da Waybar nem o Breeze instalado.

## Leituras necessárias fora do isolamento

O D-Bus e o Wayland reais estão inacessíveis nesta tarefa. O coordenador
precisa obter os itens da bandeja, sem mudar a sessão:

```sh
busctl --user get-property org.kde.StatusNotifierWatcher /StatusNotifierWatcher org.kde.StatusNotifierWatcher RegisteredStatusNotifierItems
```

Para cada endereço retornado, separe serviço e caminho, por exemplo
`:1.123/StatusNotifierItem`. Use os valores reais no comando seguinte:

```sh
for propriedade in Id IconName IconThemePath Status Menu ItemIsMenu; do
  busctl --user get-property :1.123 /StatusNotifierItem org.kde.StatusNotifierItem "$propriedade"
done
```

Confirmar `Id=Fcitx` e `IconName=input-keyboard-symbolic` no estado defeituoso.
Se forem diferentes, investigar antes de considerar o diagnóstico fechado.

## Reprodução gráfica sem tocar a sessão principal

1. Fora do isolamento, no worktree, execute
   `testes/aninhado.sh --sem-usuario --manter`. Anote somente a assinatura
   de teste impressa. Esse script não carrega o início da sessão pessoal.
2. Em outro terminal, selecione explicitamente essa assinatura em todas
   as chamadas de `hyprctl`. Crie duas saídas de teste com
   `hyprctl output create headless` e consulte `hyprctl monitors -j`.
   Acrescente ao Lua temporário impresso pelo script duas chamadas
   `hl.monitor({ output = "NOME_REAL", mode = "1920x1080@60", position = "auto", scale = 1 })`,
   usando escala 2 na segunda. Recarregue somente a instância de teste.
   Confira nomes, escalas e `configerrors` antes de continuar.
3. Obtenha o soquete Wayland da instância pelo registro temporário do
   compositor. Em um `dbus-run-session`, configure esse `WAYLAND_DISPLAY`,
   a assinatura de teste e diretórios temporários de configuração, estado
   e dados. Preserve os diretórios de dados do sistema como alternativa.
   Todos os processos seguintes pertencem a esse barramento privado.
4. Prepare `gtk-3.0/settings.ini` temporário com
   `[Settings]` e `gtk-icon-theme-name=breeze`. Use uma configuração Waybar
   temporária contendo somente `tray`, tamanho 16, e CSS próprio.
   Inicie um Fcitx5 de teste, sem `--replace`, com configuração descartável,
   e um editor nesse mesmo ambiente. Não reutilize o barramento principal.
5. Compare a Waybar direta com `JANGADA_PATH` apontando ao worktree e
   `bin/jangada-barra`. Registre capturas novas das duas barras e o
   `IconName` de cada estado. Confira teclado legível nas escalas 1 e 2,
   tamanho proporcional, estados de teclado e método alternativo, imagens
   textuais quando disponíveis, clique esquerdo, menu e rolagem.
6. Inclua outro aplicativo na bandeja de teste e confirme o mesmo ícone
   antes e depois. Encerre os processos de teste, o barramento privado e
   a instância aninhada. Não use encerramento global de Waybar ou Fcitx5.

## Verificação nesta tarefa

Passaram `testes/barra.sh`, `testes/contratos-interface.sh` e
`testes/interface.sh`. O teste específico roda dentro de `barra.sh`.
A consulta real de GTK, sem carregar imagens, confirmou que a sobreposição
troca apenas o teclado de 32px: teclado de 16px, `fcitx`, `fcitx-pinyin`,
`input-keyboard` e `network-wireless-symbolic` conservaram os caminhos.
No carregamento simbólico pelo GTK real, o recurso próprio manteve
733 pixels transparentes. A reprodução por `rsvg-convert` deu o mesmo resultado.
Isso não substitui o teste gráfico de estados e ações, que permanece pendente.

`testes/verificar.sh` terminou com código 1. A repetição autorizada fora
do sandbox interno, mantendo o isolamento do Jangada, levou 383 segundos.
Há uma pendência desta mudança: registrar `/usr/share/icons` entre as
leituras em `testes/regra1.sh`, arquivo fora do escopo inicial.
O registro foi solicitado ao coordenador e ainda não foi autorizado.
Outras falhas atingiram testes de agentes, isolamento, delegação e painel.
A falha de `agente-seletor.py` também ocorreu numa cópia da base sem
esta mudança. As demais não foram individualmente reproduzidas na base;
a suíte completa não está aprovada.
