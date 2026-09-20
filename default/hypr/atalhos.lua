-- Atalhos de teclado. Para trocar um atalho, use hl.unbind(teclas) em
-- ~/.config/jangada/hypr/usuario.lua e registre o novo com j.atalho().

local SUPER = "SUPER"
local lancador

if j.interface() == "noctalia" then
  lancador = "qs -c noctalia-shell ipc call launcher toggle"
else
  lancador = "fuzzel --config " .. j.config .. "/fuzzel/fuzzel.ini"
end

-- Programas
j.atalho(SUPER .. " + RETURN", "Terminal", j.cmd("jangada-terminal"))
j.atalho(SUPER .. " + SPACE", "Lançador de aplicativos", lancador)
j.atalho(SUPER .. " + ESCAPE", "Menu jangada", j.cmd("jangada-menu"))
j.atalho(SUPER .. " + V", "Histórico da área de transferência", j.cmd("jangada-menu", "area-transferencia"))
j.atalho(SUPER .. " + SLASH", "Mostrar todos os atalhos", j.cmd("jangada-atalhos"))
j.atalho(SUPER .. " + CTRL + L", "Bloquear a tela", j.cmd("jangada-bloquear"))

-- Agentes
j.atalho(SUPER .. " + A", "Novo agente", j.cmd("jangada-agente", "--janela"))
j.atalho(SUPER .. " + SHIFT + A", "Lista de agentes", j.cmd("jangada-agentes", "--janela"))
j.atalho(SUPER .. " + CTRL + A", "Painel de agentes", j.cmd("jangada-agentes", "--painel"))

-- Sessão
j.atalho(SUPER .. " + CTRL + R", "Recarregar e mostrar erros", j.cmd("jangada-recarregar"))
j.atalho(SUPER .. " + CTRL + T", "Trocar papel de parede e cores", j.cmd("jangada-tema", "--escolher"))

-- Janelas
j.atalho(SUPER .. " + W", "Fechar janela", hl.dsp.window.close())
j.atalho(SUPER .. " + F", "Tela cheia", hl.dsp.window.fullscreen({ mode = "fullscreen" }))
j.atalho(SUPER .. " + ALT + F", "Largura total", hl.dsp.window.fullscreen({ mode = "maximized" }))
j.atalho(SUPER .. " + T", "Alternar flutuante", hl.dsp.window.float({ action = "toggle" }))
j.atalho(SUPER .. " + J", "Alternar divisão", hl.dsp.layout("togglesplit"))

local direcoes = {
  { tecla = "LEFT", d = "l", nome = "à esquerda" },
  { tecla = "RIGHT", d = "r", nome = "à direita" },
  { tecla = "UP", d = "u", nome = "acima" },
  { tecla = "DOWN", d = "d", nome = "abaixo" },
}
for _, x in ipairs(direcoes) do
  j.atalho(SUPER .. " + " .. x.tecla, "Foco " .. x.nome, hl.dsp.focus({ direction = x.d }))
  j.atalho(SUPER .. " + SHIFT + " .. x.tecla, "Trocar janela " .. x.nome, hl.dsp.window.swap({ direction = x.d }))
end

-- Workspaces 1 a 10 (tecla 0 corresponde ao 10)
for i = 1, 10 do
  local tecla = tostring(i % 10)
  j.atalho(SUPER .. " + " .. tecla, "Workspace " .. i, hl.dsp.focus({ workspace = tostring(i) }))
  j.atalho(SUPER .. " + SHIFT + " .. tecla, "Mover para workspace " .. i, hl.dsp.window.move({ workspace = tostring(i) }))
end

j.atalho(SUPER .. " + TAB", "Próximo workspace", hl.dsp.focus({ workspace = "e+1" }))
j.atalho(SUPER .. " + SHIFT + TAB", "Workspace anterior", hl.dsp.focus({ workspace = "e-1" }))
j.atalho(SUPER .. " + S", "Rascunho (workspace especial)", hl.dsp.workspace.toggle_special("rascunho"))
j.atalho(SUPER .. " + SHIFT + S", "Mover para o rascunho", hl.dsp.window.move({ workspace = "special:rascunho", follow = false }))

-- Mouse
j.atalho(SUPER .. " + mouse:272", "Arrastar janela com o mouse", hl.dsp.window.drag(), { mouse = true })
j.atalho(SUPER .. " + mouse:273", "Redimensionar janela com o mouse", hl.dsp.window.resize(), { mouse = true })

-- Captura de tela
j.atalho("PRINT", "Capturar região", j.cmd("jangada-captura", "regiao"))
j.atalho("SHIFT + PRINT", "Capturar tela inteira", j.cmd("jangada-captura", "tela"))

-- Teclas de mídia (funcionam com a tela bloqueada)
local midia = { locked = true, repeating = true }
j.atalho("XF86AudioRaiseVolume", "Aumentar o volume", "wpctl set-volume -l 1 @DEFAULT_AUDIO_SINK@ 5%+", midia)
j.atalho("XF86AudioLowerVolume", "Diminuir o volume", "wpctl set-volume @DEFAULT_AUDIO_SINK@ 5%-", midia)
j.atalho("XF86AudioMute", "Mudo", "wpctl set-mute @DEFAULT_AUDIO_SINK@ toggle", { locked = true })
j.atalho("XF86AudioMicMute", "Mudo do microfone", "wpctl set-mute @DEFAULT_AUDIO_SOURCE@ toggle", { locked = true })
j.atalho("XF86MonBrightnessUp", "Aumentar o brilho", "brightnessctl -e4 -n2 set 5%+", midia)
j.atalho("XF86MonBrightnessDown", "Diminuir o brilho", "brightnessctl -e4 -n2 set 5%-", midia)
j.atalho("XF86AudioPlay", "Tocar ou pausar", "playerctl play-pause", { locked = true })
j.atalho("XF86AudioPause", "Tocar ou pausar", "playerctl play-pause", { locked = true })
j.atalho("XF86AudioNext", "Próxima faixa", "playerctl next", { locked = true })
j.atalho("XF86AudioPrev", "Faixa anterior", "playerctl previous", { locked = true })
