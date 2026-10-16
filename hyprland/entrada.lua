-- Teclado, mouse e touchpad. Ajustes pessoais vão em ~/.config/jangada/hypr/usuario.lua.

hl.config({
  input = {
    kb_layout = "br",
    kb_variant = "abnt2",
    follow_mouse = 1,
    sensitivity = 0,
    touchpad = {
      natural_scroll = true,
    },
  },
})

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
