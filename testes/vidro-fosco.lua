-- Exercita os módulos reais com eventos e valores efetivos imitados.
local raiz = arg[1] or "."
package.path = raiz .. "/?.lua;" .. package.path
local configs, eventos, regras, camadas, janelas
local function iniciar(desligado)
  configs, eventos, regras, camadas, janelas = {}, {}, {}, {}, {}
  j = { conf = { JANGADA_VIDRO = desligado and "0" or "1" }, opcional = function() end,
    interface = function() return "componentes" end }
  hl = {
    config = function(t)
      local function mesclar(origem, prefixo)
        for k, v in pairs(origem) do
          local chave = prefixo == "" and k or prefixo .. "." .. k
          if type(v) == "table" then mesclar(v, chave) else configs[chave] = v end
        end
      end
      mesclar(t, "")
    end,
    get_config = function(k) assert(configs[k] ~= nil); return configs[k] end,
    get_windows = function() return janelas end,
    window_rule = function(t) regras[t.name] = t end,
    layer_rule = function(t) camadas[t.match.namespace] = t end,
    on = function(e, f) assert(not eventos[e]); eventos[e] = f end,
    curve = function() end, animation = function() end,
  }
  package.loaded['default.hypr.vidro'] = nil
  dofile(raiz .. '/shell/hyprland/aparencia.lua')
end
local function blur() return configs['decoration.blur.enabled'] end
local function janela(endereco, classe, tela)
  return { address = endereco, class = classe, mapped = true, fullscreen = tela or 0, tags = {} }
end
iniciar(false)
assert(configs['decoration.active_opacity'] == 0.88)
assert(configs['decoration.inactive_opacity'] == 0.78)
for k, v in pairs({ size = 10, passes = 3, noise = 0.02, contrast = 1.0,
  brightness = 0.6, vibrancy = 0.2, vibrancy_darkness = 0.5,
  popups = true, ignore_opacity = true }) do
  assert(configs['decoration.blur.' .. k] == v, k)
end
for _, ns in ipairs({ 'waybar', 'launcher', 'notifications' }) do
  assert(camadas['^' .. ns .. '$'].blur and camadas['^' .. ns .. '$'].ignore_alpha == 0.3)
end
for _, nome in ipairs({ 'vidro-tela-cheia', 'vidro-video', 'vidro-video-separado', 'vidro-jogo' }) do
  assert(regras[nome].opacity == '1 override 1 override 1 override')
  assert(regras[nome].force_rgbx and regras[nome].no_blur)
end
assert(not regras['vidro-video'].match.class:find('firefox', 1, true))
local navegador = janela('1', 'firefox')
janelas = { navegador }
eventos['window.open'](); assert(blur())
navegador.fullscreen = 2
eventos['window.fullscreen'](); assert(not blur())
local game = janela('2', 'steam_app_123')
janelas[2] = game
eventos['window.open']()
navegador.fullscreen = 0
eventos['window.fullscreen'](); assert(not blur())
eventos['window.close'](game); assert(blur())
eventos['window.update_rules'](); assert(blur())
janelas[2] = nil
eventos['window.destroy'](game)
-- Os valores pessoais são definidos após os padrões, antes do primeiro evento.
hl.config({ decoration = { active_opacity = 0.94, blur = { size = 7, passes = 1, enabled = false } } })
navegador.fullscreen = 2
eventos['window.fullscreen'](); assert(not blur())
navegador.fullscreen = 0
eventos['window.fullscreen'](); assert(not blur())
assert(configs['decoration.active_opacity'] == 0.94 and configs['decoration.blur.size'] == 7)
-- Recarga durante suspensão: o valor novo substitui a fotografia anterior.
hl.config({ decoration = { blur = { enabled = true } } })
navegador.fullscreen = 2
eventos['window.fullscreen']()
hl.config({ decoration = { blur = { enabled = false } } })
eventos['config.reloaded'](); assert(not blur())
navegador.fullscreen = 0
eventos['window.fullscreen'](); assert(not blur())
-- Jogo pessoal e mudança de classe; maximizar não equivale a tela cheia.
hl.config({ decoration = { blur = { enabled = true } } })
game = janela('3', 'meu-jogo'); game.tags = { 'vidro-jogo*' }; janelas[2] = game
eventos['window.update_rules'](); assert(not blur())
game.tags = {}; game.class = 'gamescope'
eventos['window.class'](); assert(not blur())
game.class = 'terminal'; game.fullscreen = 1
eventos['window.class'](); assert(blur())
-- Recarga com janela já aberta em tela cheia.
navegador.fullscreen = 2
eventos['config.reloaded'](); assert(not blur())
navegador.fullscreen = 0
eventos['window.fullscreen'](); assert(blur())
iniciar(true)
eventos['config.reloaded']()
assert(not blur() and configs['decoration.active_opacity'] == 1 and configs['decoration.inactive_opacity'] == 1)
assert(regras['vidro-desligado'].force_rgbx)
for _, camada in pairs(camadas) do assert(not camada.blur) end
janelas = { janela('4', 'gamescope', 2) }
eventos['window.open'](); eventos['window.close'](janelas[1]); assert(not blur())
print('ok: padrões, exceções, camadas, jogos simultâneos, fechamento, recarga, valores pessoais e vidro desligado')
