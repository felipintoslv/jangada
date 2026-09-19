-- Configuração principal da sessão jangada. Este arquivo é seu: o jangada o
-- cria uma única vez e nunca o sobrescreve.
--
-- Os padrões ficam no repositório (default/hypr) e são atualizados com
-- jangada-update. Os seus ajustes ficam nos arquivos desta pasta e são
-- carregados depois dos padrões, então prevalecem sobre eles.

dofile((os.getenv("JANGADA_PATH") or (os.getenv("HOME") .. "/.local/share/jangada")) .. "/default/hypr/bootstrap.lua")

-- Padrões do jangada.
require("default.hypr.jangada")

-- Ajustes pessoais.
require("monitores")
require("usuario")
