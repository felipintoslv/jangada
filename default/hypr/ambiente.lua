-- Variáveis de ambiente da sessão.

hl.env("JANGADA_PATH", j.path)
hl.env("XCURSOR_SIZE", "24")
hl.env("HYPRCURSOR_SIZE", "24")

-- Preferência por Wayland nos aplicativos que suportam.
hl.env("GDK_BACKEND", "wayland,x11,*")
hl.env("QT_QPA_PLATFORM", "wayland;xcb")
hl.env("ELECTRON_OZONE_PLATFORM_HINT", "wayland")
hl.env("MOZ_ENABLE_WAYLAND", "1")
hl.env("XDG_SESSION_TYPE", "wayland")
hl.env("XDG_CURRENT_DESKTOP", "Hyprland")
hl.env("XDG_SESSION_DESKTOP", "Hyprland")

-- Escolha da GPU. O jangada-sessao já define AQ_DRM_DEVICES antes de o
-- compositor subir, inclusive detectando a placa com monitor ligado. Aqui fica
-- a segunda linha de defesa, para quem inicia o Hyprland à mão: vale só o que
-- estiver escrito em JANGADA_GPU, porque a configuração não sonda o sistema.
local gpu = j.conf.JANGADA_GPU
if gpu and gpu ~= "" and (os.getenv("AQ_DRM_DEVICES") or "") == "" then
  hl.env("AQ_DRM_DEVICES", gpu)
end
