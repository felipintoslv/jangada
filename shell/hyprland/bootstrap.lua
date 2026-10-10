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

-- O Hyprland roda com a pasta atual em $HOME, e o caminho padrão do Lua
-- procura primeiro em ./ quando a pasta da configuração vem depois dele: um
-- ~/usuario.lua ou ~/cores.lua seria carregado no lugar do arquivo do jangada.
local function sem_pasta_atual(caminho)
  local itens = {}
  for item in caminho:gmatch("[^;]+") do
    if item:sub(1, 2) ~= "./" then itens[#itens + 1] = item end
  end
  return table.concat(itens, ";")
end
package.path = sem_pasta_atual(package.path)
package.cpath = sem_pasta_atual(package.cpath)

local entrada = jangada .. "/?.lua;"
if not package.path:find(entrada, 1, true) then
  package.path = entrada .. package.path
end

JANGADA_PATH = jangada
