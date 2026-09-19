-- Executa a configuração do jangada com uma imitação da API "hl" do Hyprland,
-- para achar erros de execução (funções inexistentes, variáveis nulas) sem
-- precisar do Hyprland. Não valida se as opções existem no Hyprland real.
--
-- Uso: lua5.4 testes/simular-hypr.lua <raiz-do-repositorio>

local raiz = arg[1] or "."
local registro = { binds = 0, regras = 0, configs = 0, envs = 0, eventos = 0 }

local function imitacao(nome)
  return setmetatable({}, {
    __index = function(_, k) return imitacao(nome .. "." .. k) end,
    __call = function(_, ...) return { dispatcher = nome, args = { ... } } end,
  })
end

hl = {
  dsp = imitacao("hl.dsp"),
  config = function(t) assert(type(t) == "table", "hl.config espera tabela"); registro.configs = registro.configs + 1 end,
  env = function(k, v) assert(type(k) == "string" and type(v) == "string", "hl.env(" .. tostring(k) .. ")"); registro.envs = registro.envs + 1 end,
  bind = function(teclas, acao, opcoes)
    assert(type(teclas) == "string", "hl.bind: teclas")
    assert(type(acao) == "table", "hl.bind: ação inválida para " .. teclas)
    assert(opcoes == nil or type(opcoes) == "table", "hl.bind: opções")
    registro.binds = registro.binds + 1
  end,
  unbind = function() end,
  window_rule = function(t)
    assert(type(t.match) == "table", "window_rule sem match: " .. tostring(t.name))
    for campo, valor in pairs(t.match) do
      if type(valor) == "string" and valor:find("%%") then
        error("window_rule " .. t.name .. ": padrão com % (Lua) em " .. campo .. "; use regex do Hyprland")
      end
    end
    registro.regras = registro.regras + 1
  end,
  layer_rule = function() end,
  curve = function() end,
  animation = function(t) assert(t.leaf, "animation sem leaf") end,
  gesture = function() end,
  monitor = function(t) assert(t.output, "monitor sem output") end,
  exec_cmd = function(c) assert(type(c) == "string", "exec_cmd") end,
  on = function(evento, f)
    assert(type(f) == "function")
    registro.eventos = registro.eventos + 1
    f() -- executa o corpo para achar erros dentro dele
  end,
}

-- O Hyprland inclui a pasta da configuração principal no caminho de módulos.
package.path = raiz .. "/config/hypr/?.lua;" .. package.path
os.getenv_original = os.getenv
local env_falso = { JANGADA_PATH = raiz, XDG_CONFIG_HOME = arg[2] }
os.getenv = function(k) return env_falso[k] or os.getenv_original(k) end

dofile(raiz .. "/config/hypr/hyprland.lua")

print(string.format("ok: %d atalhos, %d regras, %d blocos de config, %d variáveis, %d eventos",
  registro.binds, registro.regras, registro.configs, registro.envs, registro.eventos))
