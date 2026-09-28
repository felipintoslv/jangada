-- Funções auxiliares compartilhadas pelos módulos do jangada.
-- Expostas na tabela global "j" porque cada arquivo carregado com require()
-- tem escopo próprio.

j = j or {}

local home = os.getenv("HOME")
local config_home = os.getenv("XDG_CONFIG_HOME")
if config_home == nil or config_home == "" then
  config_home = home .. "/.config"
end

j.home = home
j.path = JANGADA_PATH or (home .. "/.local/share/jangada")
j.config = config_home .. "/jangada"
j.bin = j.path .. "/bin"

-- Lê ~/.config/jangada/jangada.conf (CHAVE=valor) sem executar nada.
local function ler_conf()
  local valores = {
    JANGADA_INTERFACE = "componentes",
  }
  local arquivo = io.open(j.config .. "/jangada.conf", "r")
  if arquivo then
    for linha in arquivo:lines() do
      -- A variável do for é constante a partir do Lua 5.5; o texto sem
      -- comentário vai para uma local própria.
      local texto = linha:match("^%s*#") and "" or linha
      local chave, valor = texto:match("^%s*(JANGADA_[%u_]+)=(.-)%s*$")
      if chave then
        valor = valor:gsub("^%$HOME", home):gsub("^~", home)
        valores[chave] = valor
      end
    end
    arquivo:close()
  end
  return valores
end

j.conf = ler_conf()

function j.interface()
  local i = j.conf.JANGADA_INTERFACE
  if i == "noctalia" then
    return "noctalia"
  end
  return "componentes"
end

-- Caminho completo de um comando jangada-*.
function j.cmd(nome, argumentos)
  local c = string.format("%q", j.bin .. "/" .. nome)
  if argumentos and argumentos ~= "" then
    c = c .. " " .. argumentos
  end
  return c
end

-- Carrega um módulo apenas se ele existir. Erros dentro do módulo aparecem normalmente.
function j.opcional(modulo)
  if package.searchpath(modulo, package.path) then
    return require(modulo)
  end
  return nil
end

-- Registra um atalho. "acao" pode ser um dispatcher (hl.dsp...) ou um texto,
-- que é executado como comando.
function j.atalho(teclas, descricao, acao, opcoes)
  local o = opcoes or {}
  if descricao then
    o.description = descricao
  end
  if type(acao) == "string" then
    acao = hl.dsp.exec_cmd(acao)
  end
  hl.bind(teclas, acao, o)
end

-- Executa um comando uma vez, quando a sessão começa.
function j.ao_iniciar(comando)
  hl.on("hyprland.start", function()
    hl.exec_cmd(comando)
  end)
end
