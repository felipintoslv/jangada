-- Regras de janelas. Os padrões de class e title são expressões regulares do
-- Hyprland (não padrões do Lua); por isso o ponto é escapado com \\.

hl.window_rule({
  name = "ignorar-maximizar",
  match = { class = ".*" },
  suppress_event = "maximize",
})

hl.window_rule({
  name = "corrigir-arrasto-xwayland",
  match = { class = "^$", title = "^$", xwayland = true, float = true, fullscreen = false, pin = false },
  no_focus = true,
})

-- Painel de agentes: sempre no workspace especial "agentes", sem roubar o foco.
hl.window_rule({
  name = "painel-agentes",
  match = { class = "^org\\.jangada\\.painel$" },
  workspace = "special:agentes silent",
})

-- Seletor de agentes (SUPER+SHIFT+A): janela flutuante no centro.
hl.window_rule({
  name = "lista-agentes",
  match = { class = "^org\\.jangada\\.lista$" },
  float = true,
  size = "1100 650",
  center = true,
})

-- Conversa de Pescador e Histórico: janela flutuante no centro.
hl.window_rule({
  name = "pescador",
  match = { class = "^org\\.jangada\\.pescador.*$" },
  float = true,
  size = "1150 720",
  center = true,
})

-- Monitor de sistema (btop/htop): janela flutuante no centro.
hl.window_rule({
  name = "monitor-sistema",
  match = { class = "^org\\.jangada\\.monitor$" },
  float = true,
  size = "1150 720",
  center = true,
})

-- Calendário interativo: janela flutuante no centro.
hl.window_rule({
  name = "calendario",
  match = { class = "^org\\.jangada\\.calendario$" },
  float = true,
  size = "760 540",
  center = true,
})

-- Janelas de agentes e do Jangada Shell: borda de outra cor para distinguir
-- dos terminais comuns.
hl.window_rule({
  name = "janela-agente",
  match = { class = "^org\\.jangada\\.(agente|shell)$" },
  tag = "+agente",
})

local cores = j.opcional("cores")
hl.window_rule({
  name = "borda-agente",
  match = { tag = "agente" },
  border_color = (cores and cores.borda_agente) or "rgba(e0a458ee)",
})

-- Diálogos pequenos e seletores flutuam.
hl.window_rule({
  name = "flutuar-dialogos",
  match = { class = "^(org\\.pulseaudio\\.pavucontrol|nm-connection-editor|blueman-manager)$" },
  float = true,
  size = "900 600",
  center = true,
})
