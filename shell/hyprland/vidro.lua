-- A chave global de desfoque também controla camadas e pré-cálculo do fundo.
-- Só ela muda durante a suspensão; os demais ajustes pessoais permanecem.
local desligado = j.conf.JANGADA_VIDRO == "0"

local function opaca(nome, match)
  hl.window_rule({
    name = nome,
    match = match,
    opacity = "1 override 1 override 1 override",
    opaque = true,
    force_rgbx = true,
    no_blur = true,
  })
end

opaca("vidro-tela-cheia", { fullscreen = true })
opaca("vidro-video", { class = "^(mpv|vlc|org\\.videolan\\.VLC|com\\.github\\.celluloid_player\\.Celluloid)$" })
opaca("vidro-video-separado", {
  class = "^(firefox|org\\.mozilla\\.firefox|chromium|chromium-browser|google-chrome|google-chrome-stable)$",
  title = "^(Picture-in-Picture|Picture in picture|Picture-in-picture)$",
})
opaca("vidro-jogo", { class = "^(steam_app_[0-9]+|gamescope)$" })
opaca("vidro-jogo-pessoal", { tag = "vidro-jogo" })
if j.interface() == "componentes" then
  for _, namespace in ipairs({ "waybar", "launcher", "notifications" }) do
    hl.layer_rule({ match = { namespace = "^" .. namespace .. "$" }, blur = not desligado, ignore_alpha = 0.3 })
  end
end

local suspenso = false
local anterior
local fechadas = {}

local function jogo(w)
  if (w.class or ""):match("^steam_app_%d+$") or w.class == "gamescope" then
    return true
  end
  for _, tag in ipairs(w.tags or {}) do
    if tag == "vidro-jogo" or tag == "vidro-jogo*" then return true end
  end
  return false
end

local function atualizar()
  local necessario = false
  for _, w in ipairs(hl.get_windows()) do
    if w.mapped and not fechadas[w.address]
      and ((w.fullscreen or 0) >= 2 or jogo(w)) then
      necessario = true
      break
    end
  end
  if desligado then
    if hl.get_config("decoration.blur.enabled")
      or hl.get_config("decoration.active_opacity") ~= 1
      or hl.get_config("decoration.inactive_opacity") ~= 1 then
      hl.config({ decoration = { active_opacity = 1, inactive_opacity = 1, blur = { enabled = false } } })
    end
  elseif necessario and not suspenso then
    anterior = hl.get_config("decoration.blur.enabled")
    hl.config({ decoration = { blur = { enabled = false } } })
    suspenso = true
  elseif not necessario and suspenso then
    hl.config({ decoration = { blur = { enabled = anterior } } })
    suspenso = false
  end
end

-- config.reloaded ocorre depois de usuario.lua, inclusive numa recarga em jogo.
hl.on("config.reloaded", function()
  if desligado then opaca("vidro-desligado", { class = ".*" }) end
  suspenso = false
  atualizar()
end)
hl.on("hyprland.start", function() atualizar() end)
for _, evento in ipairs({ "window.fullscreen", "window.class", "window.update_rules" }) do
  hl.on(evento, function() atualizar() end)
end
-- A janela pode continuar mapeada durante a animação de fechamento.
hl.on("window.open", function(w)
  if w then fechadas[w.address] = nil end
  atualizar()
end)
hl.on("window.close", function(w)
  if w then fechadas[w.address] = true end
  atualizar()
end)
hl.on("window.destroy", function(w)
  if w and w.address then fechadas[w.address] = nil end
  atualizar()
end)
