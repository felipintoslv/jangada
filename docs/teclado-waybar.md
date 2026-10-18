# Teclado na bandeja com escalas 1 e 2

O contorno troca somente `input-keyboard-symbolic` de 32px do Breeze na
busca de ícones da Waybar. A identidade do item foi confirmada por D-Bus;
verificar o resultado gráfico nas duas escalas continua sendo requisito da entrega.

## Evidência e causa

Em 11/10/2026, a máquina tinha Waybar 0.15.0-3, Fcitx5 5.1.23-1,
Breeze Icons 6.30.0-1, GTK 3.24.52-2 e librsvg 2.63.2-1.
As capturas autorizadas mostram teclado no HDMI-A-2, escala 1, e quadrado
na posição correspondente no DP-3, escala 2. Elas comprovam o defeito
inicial, sem comprovar o resultado do contorno.

A leitura do coordenador no host, em 11/10/2026, identificou o objeto
`:1.39/StatusNotifierItem`, com `Id=Fcitx`,
`IconName=input-keyboard-symbolic`, `IconThemePath` vazio e `Title=Input Method`.
O outro item registrado era o Steam. A versão consultada foi Waybar 0.15.0.
O registro original está em `.jangada/diagnostico-coordenador.md`, linhas 1 a 9,
fora da entrega. Esses dados confirmam que o Fcitx publica o nome do
recurso defeituoso e usa a busca do tema GTK, sem caminho próprio.

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
O nome publicado pelo item real coincide com esse recurso.

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
Os processos iniciados pela Waybar herdam essa busca, inclusive nos cliques.
O ambiente do terminal e da sessão principal conserva a busca original.

O tema escolhido, os demais recursos, os nomes e imagens publicados pelo
Fcitx5 continuam os mesmos. Cliques, menu e rolagem seguem no item nativo.
O tamanho lógico permanece 16. Não há dependência nova nem migração:
nenhum arquivo pessoal precisa mudar. O contorno vale na próxima partida
pelo lançador atualizado, mesmo com `config.jsonc` pessoal.

Para comparar ou reverter numa instância de teste, execute a Waybar
diretamente com a busca original, sem passar pelo lançador.
A sessão principal não foi alterada. Esta entrega contorna um recurso
externo; não modifica a implementação da Waybar nem o Breeze instalado.

## Conferência da identidade por D-Bus

Para repetir a leitura do coordenador, obtenha os itens da bandeja
fora do isolamento, sem mudar a sessão:

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

Confirme `Id=Fcitx`, `IconName=input-keyboard-symbolic` e `IconThemePath`
vazio no estado defeituoso. Os endereços do barramento podem mudar.
Se as propriedades diferirem, investigue antes de aplicar esse diagnóstico.

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

## Verificação reproduzível

Execute `jangada-filtrar -- testes/barra.sh`,
`jangada-filtrar -- testes/contratos-interface.sh`,
`jangada-filtrar -- testes/interface.sh` e
`jangada-filtrar -- env --default-signal=INT,QUIT testes/verificar.sh`.
O teste específico roda dentro de `barra.sh` e confere a estrutura do SVG;
a recoloração é uma conferência manual adicional, não um teste automatizado.

Para reproduzir a recoloração sem compositor, use GTK 3 com os módulos
Python já instalados na máquina investigada. No worktree, em terminal
com suporte a barramento privado, execute:

```sh
env GIO_USE_VFS=local dbus-run-session -- python3 - <<'PY'
from pathlib import Path
from tempfile import TemporaryDirectory
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

color = Gdk.RGBA()
color.parse("#e8e5e3")
with TemporaryDirectory() as temp:
    icons = Path(temp) / "icons"
    overlay = icons / "breeze"
    (overlay / "devices/32").mkdir(parents=True)
    (overlay / "index.theme").symlink_to("/usr/share/icons/breeze/index.theme")
    (overlay / "devices/32/input-keyboard-symbolic.svg").symlink_to(
        Path("waybar/icones/input-keyboard-symbolic.svg").resolve())
    for corrected in (False, True):
        theme = Gtk.IconTheme.new()
        theme.set_custom_theme("breeze")
        if corrected:
            theme.set_search_path([str(icons)] + theme.get_search_path())
        for size in (16, 32):
            info = theme.lookup_icon("input-keyboard-symbolic", size,
                                     Gtk.IconLookupFlags.FORCE_SIZE)
            pixbuf, symbolic = info.load_symbolic(color, None, None, None)
            pixels = pixbuf.get_pixels()
            stride = pixbuf.get_rowstride()
            channels = pixbuf.get_n_channels()
            assert symbolic and pixbuf.get_has_alpha()
            clear = sum(pixels[y * stride + x * channels + channels - 1] == 0
                        for y in range(pixbuf.get_height())
                        for x in range(pixbuf.get_width()))
            print(corrected, size, info.get_filename(), clear)
            if corrected:
                assert clear > 0
PY
```

Nas versões investigadas, o original tem 170 pixels transparentes em 16px
e zero em 32px. Com o contorno, o segundo valor passa a 733.
Confira também os caminhos de `fcitx`, `fcitx-pinyin`, `input-keyboard` e
`network-wireless-symbolic`: devem permanecer os mesmos antes e depois.
Essa reprodução não substitui os testes gráficos de estados e ações.
