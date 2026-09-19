-- Prepara o caminho de módulos Lua do jangada. Carregado com dofile() pelo
-- hyprland.lua do usuário, antes de qualquer require().
--
-- Ordem de busca: ~/.config/jangada/hypr (ajustes do usuário, já incluído pelo
-- Hyprland por ser a pasta da configuração principal) e depois o repositório
-- (padrões em default/hypr, acessados como "default.hypr.<nome>").

local home = os.getenv("HOME")
local jangada = os.getenv("JANGADA_PATH")
if jangada == nil or jangada == "" then
  jangada = home .. "/.local/share/jangada"
end

-- Ao recarregar (hyprctl reload), o Lua mantém os módulos em cache. Limpa os
-- módulos do jangada e do usuário para que as mudanças nos arquivos valham.
local prefixos = { "default.hypr", "monitores", "usuario", "cores" }
local descartar = {}
for modulo in pairs(package.loaded) do
  for _, p in ipairs(prefixos) do
    if modulo == p or modulo:sub(1, #p + 1) == p .. "." then
      table.insert(descartar, modulo)
    end
  end
end
for _, modulo in ipairs(descartar) do
  package.loaded[modulo] = nil
end

local entrada = jangada .. "/?.lua;"
if not package.path:find(entrada, 1, true) then
  package.path = entrada .. package.path
end

JANGADA_PATH = jangada
