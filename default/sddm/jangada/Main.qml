// Tela de login do jangada. Imita o menu do SUPER+Esc (fuzzel): uma caixa
// centralizada com linhas de pergunta ("usuário > ", "senha > ") e uma lista
// de ações logo abaixo. Setas escolhem a ação, Enter executa. Digitar a senha
// volta a seleção para "Entrar", para que Enter nunca desligue por engano.
import QtQuick 2.15

Rectangle {
    id: raiz
    width: 1920
    height: 1080
    color: config.cor_tela || "#141311"

    // Fonte medida numa tela de 1080 linhas e ampliada em telas maiores, para
    // que o 4K não mostre uma caixa minúscula.
    readonly property real escala: Math.max(1, height / 1080)
    readonly property real tamanhoFonte: (Number(config.tamanho) || 12) * 4 / 3 * escala
    readonly property string fonte: config.fonte || "JetBrainsMono Nerd Font"

    readonly property color corCaixa: config.cor_caixa || "#f2211f1d"
    readonly property color corTexto: config.cor_texto || "#e6e2de"
    readonly property color corDestaque: config.cor_destaque || "#e6d9be"
    readonly property color corSelecao: config.cor_selecao || "#c9bda3"
    readonly property color corTextoSelecao: config.cor_texto_selecao || "#37301d"
    readonly property color corBorda: config.cor_borda || "#e6d9be"
    readonly property color corErro: config.cor_erro || "#ffb4ab"

    // Só há uma sessão (o jangada-sddm restringe o diretório de sessões), mas
    // o índice lembrado pelo SDDM é respeitado se existir.
    readonly property int indiceSessao: sessionModel.lastIndex >= 0 ? sessionModel.lastIndex : 0

    property int selecionado: 0
    property string mensagem: ""
    property bool entrando: false

    readonly property var acoes: {
        var lista = [{ icone: 0xF0342, rotulo: "Entrar", acao: "entrar" }];
        if (sddm.canSuspend)
            lista.push({ icone: 0xF0904, rotulo: "Suspender", acao: "suspender" });
        if (sddm.canReboot)
            lista.push({ icone: 0xF0709, rotulo: "Reiniciar", acao: "reiniciar" });
        if (sddm.canPowerOff)
            lista.push({ icone: 0xF0425, rotulo: "Desligar", acao: "desligar" });
        return lista;
    }

    function executar(indice) {
        var acao = acoes[indice].acao;
        if (acao === "entrar") {
            if (campoUsuario.text === "") {
                campoUsuario.forceActiveFocus();
                return;
            }
            mensagem = "";
            entrando = true;
            sddm.login(campoUsuario.text, campoSenha.text, indiceSessao);
        } else if (acao === "suspender") {
            sddm.suspend();
        } else if (acao === "reiniciar") {
            sddm.reboot();
        } else if (acao === "desligar") {
            sddm.powerOff();
        }
    }

    function mover(passo) {
        selecionado = (selecionado + passo + acoes.length) % acoes.length;
    }

    Connections {
        target: sddm
        function onLoginFailed() {
            entrando = false;
            mensagem = "senha incorreta";
            campoSenha.text = "";
            campoSenha.forceActiveFocus();
        }
        function onLoginSucceeded() {
            mensagem = "";
        }
    }

    // Papel de parede montado para a proporção desta tela, como o jangada-tema
    // faz na área de trabalho (o SDDM abre uma cópia do tema em cada tela). A
    // figura aparece inteira e o espaço que sobra é completado conforme o
    // ajuste: "espelho" reflete a borda da figura, "desfoque" usa a própria
    // imagem ampliada e escurecida, "cor" deixa a cor de fundo do tema e
    // "cobrir" amplia a figura até cobrir a tela, cortando o excesso.
    readonly property string ajuste: config.ajuste || "espelho"
    readonly property real proporcaoFigura: figura.implicitHeight > 0 ? figura.implicitWidth / figura.implicitHeight : width / height
    readonly property bool telaMaisLarga: width / height > proporcaoFigura

    Item {
        id: fundo
        anchors.fill: parent

        // Fundo do desfoque: a imagem é carregada com 48 pixels de largura e
        // ampliada com suavização, o que já a deixa borrada. Um MultiEffect
        // aqui dentro, aninhado no desfoque geral da tela, fazia o greeter
        // mostrar a figura ampliada e cortada.
        Image {
            anchors.fill: parent
            source: config.fundo || ""
            sourceSize.width: 48
            fillMode: Image.PreserveAspectCrop
            smooth: true
            asynchronous: true
            visible: ajuste === "desfoque" || ajuste === "espelho"
        }

        Rectangle {
            anchors.fill: parent
            color: "black"
            opacity: 0.4
            visible: ajuste === "desfoque" || ajuste === "espelho"
        }

        Image {
            id: figura
            anchors.centerIn: parent
            width: ajuste === "cobrir" ? parent.width : (telaMaisLarga ? parent.height * proporcaoFigura : parent.width)
            height: ajuste === "cobrir" ? parent.height : (telaMaisLarga ? parent.height : parent.width / proporcaoFigura)
            source: config.fundo || ""
            fillMode: ajuste === "cobrir" ? Image.PreserveAspectCrop : Image.Stretch
            asynchronous: true
        }

        // Faixas refletidas dos dois lados da figura (ou de cima e de baixo,
        // numa tela mais alta que a imagem). Cada faixa mostra a figura
        // espelhada inteira, alinhada pela borda que encosta nela, e corta o
        // resto. Se a faixa for maior que a figura, o desfoque de baixo cobre
        // o que faltar.
        Repeater {
            model: ajuste === "espelho" ? 2 : 0
            delegate: Item {
                required property int index
                readonly property bool antes: index === 0
                clip: true
                x: telaMaisLarga ? (antes ? 0 : figura.x + figura.width) : 0
                y: telaMaisLarga ? 0 : (antes ? 0 : figura.y + figura.height)
                width: telaMaisLarga ? (antes ? figura.x : raiz.width - x) : raiz.width
                height: telaMaisLarga ? raiz.height : (antes ? figura.y : raiz.height - y)

                Image {
                    width: figura.width
                    height: figura.height
                    x: telaMaisLarga && antes ? parent.width - width : 0
                    y: !telaMaisLarga && antes ? parent.height - height : 0
                    source: config.fundo || ""
                    mirror: telaMaisLarga
                    mirrorVertically: !telaMaisLarga
                    asynchronous: true
                }
            }
        }
    }

    // Véu sobre a figura, para a caixa se destacar. O fundo não passa por
    // desfoque: o MultiEffect sobre um item composto (camada) não acompanha o
    // redimensionamento da janela e chegou a mostrar a figura ampliada e
    // cortada. Imagens simples não têm esse problema.
    Rectangle {
        anchors.fill: parent
        color: "black"
        opacity: 0.25
    }

    Text {
        id: relogio
        anchors.horizontalCenter: parent.horizontalCenter
        anchors.bottom: caixa.top
        anchors.bottomMargin: 24 * escala
        color: corTexto
        font.family: fonte
        font.pixelSize: tamanhoFonte * 4
        text: Qt.formatTime(new Date(), "HH:mm")

        Timer {
            interval: 1000
            running: true
            repeat: true
            onTriggered: relogio.text = Qt.formatTime(new Date(), "HH:mm")
        }
    }

    TextMetrics {
        id: medida
        font.family: fonte
        font.pixelSize: tamanhoFonte
        text: "M"
    }

    Rectangle {
        id: caixa
        anchors.centerIn: parent
        // Mesmas medidas do fuzzel.ini: 45 colunas, margens de 16 e 12, raio 8.
        width: medida.advanceWidth * 45 + 32 * escala
        height: coluna.implicitHeight + 24 * escala
        color: corCaixa
        border.color: corBorda
        border.width: Math.round(2 * escala)
        radius: 8 * escala

        Column {
            id: coluna
            x: 16 * escala
            y: 12 * escala
            width: caixa.width - 32 * escala
            spacing: 6 * escala

            Text {
                width: parent.width
                color: corDestaque
                font.family: fonte
                font.pixelSize: tamanhoFonte
                text: sddm.hostName ? "jangada @ " + sddm.hostName : "jangada"
                elide: Text.ElideRight
            }

            Row {
                width: parent.width
                Text {
                    id: rotuloUsuario
                    color: corTexto
                    font.family: fonte
                    font.pixelSize: tamanhoFonte
                    text: "usuário > "
                }
                TextInput {
                    id: campoUsuario
                    width: parent.width - rotuloUsuario.width
                    color: corTexto
                    selectionColor: corSelecao
                    selectedTextColor: corTextoSelecao
                    font.family: fonte
                    font.pixelSize: tamanhoFonte
                    text: userModel.lastUser
                    clip: true
                    KeyNavigation.tab: campoSenha
                    Keys.onUpPressed: mover(-1)
                    Keys.onDownPressed: mover(1)
                    Keys.onReturnPressed: selecionado === 0 ? campoSenha.forceActiveFocus() : executar(selecionado)
                    Keys.onEnterPressed: selecionado === 0 ? campoSenha.forceActiveFocus() : executar(selecionado)
                }
            }

            Row {
                width: parent.width
                Text {
                    id: rotuloSenha
                    color: corTexto
                    font.family: fonte
                    font.pixelSize: tamanhoFonte
                    text: "senha > "
                }
                TextInput {
                    id: campoSenha
                    width: parent.width - rotuloSenha.width
                    color: corTexto
                    font.family: fonte
                    font.pixelSize: tamanhoFonte
                    echoMode: TextInput.Password
                    passwordCharacter: "•"
                    clip: true
                    enabled: !entrando
                    KeyNavigation.tab: campoUsuario
                    onTextChanged: {
                        selecionado = 0;
                        mensagem = "";
                    }
                    Keys.onUpPressed: mover(-1)
                    Keys.onDownPressed: mover(1)
                    Keys.onReturnPressed: executar(selecionado)
                    Keys.onEnterPressed: executar(selecionado)
                    Keys.onEscapePressed: {
                        text = "";
                        selecionado = 0;
                    }
                }
            }

            Repeater {
                model: acoes
                delegate: Rectangle {
                    required property int index
                    required property var modelData
                    width: coluna.width
                    height: rotuloAcao.implicitHeight + 6 * escala
                    radius: 4 * escala
                    color: index === selecionado ? corSelecao : "transparent"

                    Text {
                        id: rotuloAcao
                        anchors.verticalCenter: parent.verticalCenter
                        x: 6 * escala
                        color: index === selecionado ? corTextoSelecao : corTexto
                        font.family: fonte
                        font.pixelSize: tamanhoFonte
                        text: String.fromCodePoint(modelData.icone) + "  " + modelData.rotulo
                    }

                    MouseArea {
                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onEntered: selecionado = index
                        onClicked: executar(index)
                    }
                }
            }

            Text {
                width: parent.width
                visible: text !== ""
                color: entrando && mensagem === "" ? corDestaque : corErro
                font.family: fonte
                font.pixelSize: tamanhoFonte
                text: {
                    if (mensagem !== "")
                        return mensagem;
                    if (entrando)
                        return "entrando…";
                    return keyboard.capsLock ? "caps lock ativado" : "";
                }
            }
        }
    }

    Component.onCompleted: {
        if (campoUsuario.text === "")
            campoUsuario.forceActiveFocus();
        else
            campoSenha.forceActiveFocus();
    }
}
