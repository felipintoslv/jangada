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

-- Escolha da GPU. Fica toda no jangada-sessao, que define AQ_DRM_DEVICES antes
-- de o compositor subir. Aqui não dá para repetir: o valor precisa do
-- /dev/dri/cardN resolvido a partir do caminho de /dev/dri/by-path, cujo
-- endereço PCI tem ":", que é o separador da lista do aquamarine. A
-- configuração não sonda o sistema, e de todo modo o backend já escolheu a
-- placa quando ela é lida. Quem inicia o Hyprland à mão deve chamar
-- jangada-sessao, ou exportar AQ_DRM_DEVICES antes.
