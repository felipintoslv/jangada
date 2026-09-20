# shellcheck shell=bash
# Etapa 40: configuração da sessão jangada (Hyprland em Lua, barra, cores).
# Tudo vai para ~/.config/jangada; ~/.config/hypr não é tocado.

copiar_se_ausente "$JANGADA_PATH/config/hypr/hyprland.lua" "$JANGADA_CONFIG/hypr/hyprland.lua"
copiar_se_ausente "$JANGADA_PATH/config/hypr/monitores.lua" "$JANGADA_CONFIG/hypr/monitores.lua"
copiar_se_ausente "$JANGADA_PATH/config/hypr/usuario.lua"   "$JANGADA_CONFIG/hypr/usuario.lua"
copiar_se_ausente "$JANGADA_PATH/config/jangada.conf"       "$JANGADA_CONFIG/jangada.conf"

# A folha de estilo da barra importa as cores geradas e a base do repositório.
# O caminho absoluto do repositório é gravado aqui porque CSS não expande variáveis.
if [[ ! -e "$JANGADA_CONFIG/waybar/style.css" ]]; then
  executar mkdir -p "$JANGADA_CONFIG/waybar"
  if simulando; then
    info "[simulação] criaria $JANGADA_CONFIG/waybar/style.css"
  else
    sed "s|@JANGADA_PATH@|$JANGADA_PATH|g" "$JANGADA_PATH/default/waybar/style.css.modelo" \
      >"$JANGADA_CONFIG/waybar/style.css"
  fi
  ok "criado: $JANGADA_CONFIG/waybar/style.css"
fi

# Cores iniciais, até que um papel de parede seja escolhido com jangada-tema.
if [[ ! -e "$JANGADA_CONFIG/hypr/cores.lua" ]]; then
  executar "$JANGADA_PATH/bin/jangada-tema" --cor "#4f8fba" || aviso "não foi possível gerar as cores iniciais"
fi

# Sessão no gerenciador de login. O arquivo aponta para o caminho absoluto do
# lançador porque arquivos .desktop não expandem ~ nem variáveis.
_sessao=/usr/share/wayland-sessions/jangada.desktop
_conteudo="[Desktop Entry]
Name=jangada
Comment=Hyprland com a configuração jangada
Exec=$JANGADA_PATH/bin/jangada-sessao
Type=Application
DesktopNames=Hyprland"
if [[ -f "$_sessao" ]] && [[ "$(cat "$_sessao")" == "$_conteudo" ]]; then
  ok "sessão já registrada: $_sessao"
else
  copia_seguranca "$_sessao"
  if simulando; then
    info "[simulação] gravaria $_sessao"
  else
    printf '%s\n' "$_conteudo" | como_root tee "$_sessao" >/dev/null
  fi
  ok "sessão registrada: $_sessao"
fi
unset _sessao _conteudo

# Serviços e locale que a barra usa, sem mexer em nenhum dos dois. Ligar o
# NetworkManager numa máquina que já usa outro gerenciador de rede derruba a
# conexão, e gerar locale escreve em /etc: as duas coisas ficam para quem
# instala decidir.
if ! systemctl is-enabled NetworkManager.service >/dev/null 2>&1; then
  aviso "NetworkManager não está habilitado; o módulo de rede da barra e o jangada-rede ficam sem dados. Para ligar: sudo systemctl enable --now NetworkManager"
fi
if ! systemctl is-enabled bluetooth.service >/dev/null 2>&1; then
  aviso "serviço bluetooth não está habilitado; o módulo fica igual a um rádio desligado. Para ligar: sudo systemctl enable --now bluetooth"
fi
if ! locale -a 2>/dev/null | grep -qiE '^pt_BR\.?utf-?8$'; then
  aviso "locale pt_BR.UTF-8 não está gerado; o relógio da barra cai para o formato do sistema. Para gerar: descomente a linha em /etc/locale.gen e rode sudo locale-gen"
fi
