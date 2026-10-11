# Vidro fosco

O padrão usa opacidade 0,88 na janela ativa e 0,78 nas demais. O desfoque
usa tamanho 10, três passadas, ruído 0,02, contraste 1, brilho 0,6,
vibrância 0,2 e vibrância escura 0,5. Inclui menus sobrepostos e ignora a
opacidade da janela ao calcular o desfoque.

Waybar, Fuzzel e Mako usam fundos com opacidade 0,88 e regras para os
espaços de nomes `waybar`, `launcher` e `notifications`. Texto, seleção,
foco e avisos continuam nas cores do tema gerado. Na barra, estados com
fundo preenchido usam o par primária/texto primário, inclusive urgência.
O Noctalia mantém sua própria aparência; o recurso não escreve nele.

## Desligar ou ajustar

Em `~/.config/jangada/jangada.conf`:

```sh
JANGADA_VIDRO=0
```

Depois execute `jangada-vidro`. Ele ajusta os fundos, recarrega apenas os
processos identificados da interface desta sessão e recarrega o compositor.
Menus já abertos precisam ser reabertos. Desligado, os fundos das cápsulas
da barra, menus e notificações ficam opacos; o desfoque global é desligado.
A regra de janelas ignora também a transparência própria de aplicativos,
como o Ghostty, sem alterar suas configurações.

Para ligar e ajustar os fundos:

```sh
JANGADA_VIDRO=1
JANGADA_VIDRO_ALPHA=0.88
```

`JANGADA_VIDRO_ALPHA` aceita valores entre 0 e 1. Valores abaixo de 0,3
ficam abaixo do limite das regras de desfoque das camadas. O contraste
verificado nos testes vale para 0,88, não para qualquer valor escolhido.

Opacidade das janelas e intensidade do desfoque ficam em
`~/.config/jangada/hypr/usuario.lua`, carregado depois dos padrões:

```lua
hl.config({ decoration = {
  active_opacity = 0.94,
  inactive_opacity = 0.86,
  blur = { size = 7, passes = 2, brightness = 0.75 },
} })
```

Execute `jangada-vidro` depois de editar as preferências. O desligamento
prevalece sobre os valores de transparência; ao ligar, os ajustes pessoais
voltam a valer. Para ajustes temporários feitos via `hyprctl eval`, evite
mudar `decoration.blur.enabled` durante uma suspensão: a saída restaura o
valor fotografado na entrada. Prefira editar `usuario.lua` e recarregar.

O comando mantém cores e outras opções de Fuzzel e Mako, alterando apenas
linhas de fundo hexadecimal. Na folha pessoal da barra, mantém o conteúdo
e acrescenta um bloco delimitado com o fundo das cápsulas. Cada alteração
recebe cópia `.jangada-DATA.bak`; repetir sem mudança não cria outra cópia.
Uma personalização posterior pode sobrepor o fundo por especificidade CSS.
Nesse caso, ajuste esse seletor pessoal para que use a opacidade desejada.
`jangada-vidro --arquivos` ajusta apenas arquivos, sem recarregar processos.
`JANGADA_SIMULAR=1 jangada-vidro` mostra a operação sem gravar ou recarregar.

Ao gerar outro tema, `jangada-tema` faz cópias dos arquivos afetados e
reaplica as preferências de vidro. A regeneração continua substituindo os
modelos de cores; alterações pessoais neles ficam nas cópias de segurança.

## Vídeo e jogos

Janelas em tela cheia usam opacidade 1, ignoram alpha próprio e não recebem
desfoque. O mesmo vale para MPV, VLC e Celluloid, e para janelas separadas
de vídeo com títulos `Picture-in-Picture`, `Picture in picture` ou
`Picture-in-picture`, nos navegadores Firefox, Chromium e Google Chrome.
Títulos traduzidos ou outros aplicativos podem exigir regra pessoal.
Uma página com vídeo embutido continua translúcida: o compositor não recebe
um sinal confiável que distinga esse vídeo do restante da página.
Use tela cheia, uma janela separada ou uma regra explícita para esse caso.

O desfoque global, incluindo camadas e menus sobrepostos, fica suspenso
quando existe qualquer janela mapeada em tela cheia, Steam
(`steam_app_ID`) ou Gamescope. A suspensão é conservadora: vale também
quando a janela está em outro espaço de trabalho. Maximizar não conta como
tela cheia. O cliente Steam e navegadores comuns não contam como jogos.

Para um jogo que não se identifica por esses padrões, obtenha a classe
com `hyprctl clients` e acrescente em `usuario.lua`:

```lua
hl.window_rule({ match = { class = "^classe-real-do-jogo$" }, tag = "+vidro-jogo" })
```

A regra da etiqueta torna o jogo opaco e a etiqueta participa da suspensão.
Não é possível reconhecer automaticamente todo jogo sem identificação.

Eventos de abertura, fechamento, tela cheia e mudanças de regras ou classe
atualizam a suspensão. Não há processo auxiliar ou consulta periódica.
Com várias janelas, o desfoque só volta quando a última sair da condição.
Só `decoration.blur.enabled` é alterado: o valor efetivo anterior é
restaurado, inclusive quando já era falso. Uma recarga durante o jogo
fotografa os novos ajustes pessoais e suspende novamente.

A API retorna `window.fullscreen` como número: 0 normal, 1 maximizado,
2 tela cheia, 3 ambos. A renderização do Hyprland 0.55 verifica a chave
global no desfoque de janelas, camadas, menus sobrepostos e pré-cálculo:
[API Lua](https://wiki.hypr.land/0.55.0/Configuring/Advanced-and-Cool/Expanding-functionality/),
[propriedades da janela](https://github.com/hyprwm/Hyprland/blob/v0.55.0/src/config/lua/objects/LuaWindow.cpp),
[renderização](https://github.com/hyprwm/Hyprland/blob/v0.55.0/src/render/Renderer.cpp),
[pré-cálculo](https://github.com/hyprwm/Hyprland/blob/v0.55.0/src/render/OpenGL.cpp).
Isso interrompe o trabalho de desfoque; não promete liberar toda memória
já reservada pelo compositor ou resolver esgotamento de memória de vídeo.

## Atualização de instalações existentes

Os módulos Lua e o estilo base são versionados e chegam pela atualização.
Os arquivos gerados existentes de Fuzzel e Mako não recebem modelos novos
sozinhos; por isso há a migração `202610111800-vidro-fosco.sh`.

Ela compara o conteúdo integral com o modelo anterior, permitindo apenas
as cores geradas. Só modelos intactos e o estilo padrão da Waybar são
adaptados, com cópia de segurança. Arquivos personalizados permanecem
intactos e recebem aviso. Não regenera cores ou papel de parede, não
reescreve `usuario.lua` nem preferências existentes, e não recarrega a
sessão. Arquivos ausentes de preferências ou estilo são criados com
`copiar_se_ausente`; Fuzzel e Mako ausentes esperam a próxima geração de tema.

O padrão da barra vale quando a folha pessoal importa a base. Uma folha
que substitui toda a base conserva sua aparência. Quem tiver arquivos
personalizados pode aplicar `jangada-vidro` para adaptar apenas os fundos,
conferindo antes `JANGADA_SIMULAR=1 jangada-vidro`.

## Verificações

`testes/vidro-fosco.lua` verifica os valores, regras e transições com a API
imitada, incluindo fechamento e recarga durante suspensão. O teste Python
confere cópias, repetibilidade, simulação e preservação de arquivos pessoais.
Com Matugen instalado, mede contraste estático para fontes azul e creme,
modos claro e escuro, fundos branco e preto, texto comum, foco, seleção e
urgência. A composição usa alpha 0,88, sem depender do desfoque para passar.
Essa conta não substitui inspeção visual da renderização.

Antes de integrar ou aplicar, o coordenador precisa aprovar e executar,
fora do isolamento do autor, contra este worktree:

```sh
testes/aninhado.sh --sem-usuario
testes/aninhado.sh
```

Cada execução confere `hyprctl configerrors` na instância aninhada. Para
uma configuração pessoal alternativa, use `XDG_CONFIG_HOME` descartável
com `jangada/hypr/usuario.lua` e preferências próprias. Teste também vidro
ligado, desligado e recarga durante jogo, conferindo a chave global de
desfoque antes, durante e depois, sempre com a assinatura da instância
aninhada. Abra MPV, vídeo separado do navegador, tela cheia e duas janelas
de jogo; feche uma de cada vez. Inspecione barra, menus e notificações sobre
fundos claros e escuros, incluindo seleção, foco e urgência.

O aninhado não inicia os componentes de `inicio.lua`. A inspeção deles
exige lançamentos separados na instância de teste, com configuração
descartável e sem disputar o serviço de notificações da sessão principal.
O aninhado usa Wayland, sem DRM real. Consumo e memória de vídeo exigem
medição posterior na máquina, com aprovação do dono. Testes pulados por
falta de compositor não contam como testes gráficos aprovados.
