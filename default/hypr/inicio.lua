-- Programas iniciados com a sessão.

hl.on("hyprland.start", function()
  -- Repassa o ambiente da sessão ao systemd e ao D-Bus (portais, polkit, chaves).
  hl.exec_cmd("dbus-update-activation-environment --systemd --all")
  hl.exec_cmd("systemctl --user start hyprpolkitagent")

  -- Histórico da área de transferência, limitado às 100 últimas cópias: o
  -- banco guarda senhas e tokens copiados. O agente isolado não o enxerga.
  hl.exec_cmd("wl-paste --type text --watch cliphist -max-items 100 store")
  hl.exec_cmd("wl-paste --type image --watch cliphist -max-items 100 store")

  -- Bloqueio e suspensão por inatividade. O hypridle 0.1.7 aceita "-c" na linha
  -- de comando mas ignora o valor: ele só lê <XDG_CONFIG_HOME>/hypr/hypridle.conf.
  -- Por isso apontamos o XDG_CONFIG_HOME dele para a pasta do jangada, em vez de
  -- escrever em ~/.config/hypr, que a sessão não toca.
  hl.exec_cmd("env XDG_CONFIG_HOME=" .. string.format("%q", j.path .. "/default/hypridle") .. " hypridle")

  if j.interface() == "noctalia" then
    -- O Noctalia cuida de barra, notificações, lançador e papel de parede.
    hl.exec_cmd("qs -c noctalia-shell")
  else
    hl.exec_cmd(j.cmd("jangada-barra"))
    hl.exec_cmd("mako --config " .. string.format("%q", j.config .. "/mako/config"))
    hl.exec_cmd(j.cmd("jangada-tema", "--aplicar-papel"))
  end
end)
