-- Aparência. As cores vêm de ~/.config/jangada/hypr/cores.lua, gerado pelo
-- jangada-tema com o matugen. Sem esse arquivo, valem as cores abaixo.

local cores = j.opcional("cores") or {
  borda_ativa = "rgba(4f8fbaee)",
  borda_inativa = "rgba(595959aa)",
  sombra = "rgba(1a1a1aee)",
}

hl.config({
  general = {
    gaps_in = 4,
    gaps_out = 8,
    border_size = 2,
    col = {
      active_border = cores.borda_ativa,
      inactive_border = cores.borda_inativa,
    },
    resize_on_border = true,
    allow_tearing = false,
    layout = "dwindle",
  },

  decoration = {
    rounding = 8,
    active_opacity = j.conf.JANGADA_VIDRO == "0" and 1.0 or 0.88,
    inactive_opacity = j.conf.JANGADA_VIDRO == "0" and 1.0 or 0.78,
    shadow = {
      enabled = true,
      range = 6,
      render_power = 3,
      color = cores.sombra,
    },
    blur = {
      enabled = j.conf.JANGADA_VIDRO ~= "0",
      size = 10,
      passes = 3,
      noise = 0.02,
      contrast = 1.0,
      brightness = 0.6,
      vibrancy = 0.2,
      vibrancy_darkness = 0.5,
      popups = true,
      ignore_opacity = true,
    },
  },

  animations = {
    enabled = true,
  },

  dwindle = {
    preserve_split = true,
  },

  misc = {
    force_default_wallpaper = 0,
    disable_hyprland_logo = true,
  },
})

hl.curve("suave", { type = "bezier", points = { { 0.23, 1 }, { 0.32, 1 } } })
hl.animation({ leaf = "global", enabled = true, speed = 8, bezier = "default" })
hl.animation({ leaf = "windows", enabled = true, speed = 4, bezier = "suave", style = "popin 90%" })
hl.animation({ leaf = "fade", enabled = true, speed = 3, bezier = "suave" })
hl.animation({ leaf = "workspaces", enabled = true, speed = 3, bezier = "suave", style = "slide" })

require("default.hypr.vidro")
