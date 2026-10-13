8. Subagentes (delegação ao agy):
   - Para explorar código ou registros, ler documentos, pesquisar na web,
     conferir regras e testes, auditar segurança, analisar arquitetura,
     otimizar desempenho ou revisar redação, use primeiro
     `jangada-delegar PAPEL "pedido" --destino agy --permitir-remoto`, com
     escopo e fontes autorizados nesta tarefa em `--arquivos`.
     Os papéis incluem explorador, leitor, pesquisador, verificador,
     auditor, arquiteto, otimizador, redator e supervisor.
   - Agy é o destino padrão também para leitor e redator e sessões sem perfil.
     A preferência global não autoriza compartilhar dados confidenciais.
     Use `--permitir-remoto` somente com autorização para as fontes da tarefa.
   - Na recusa por acesso, confiança, cota ou autorização, registre e informe
     o bloqueio. A investigação pode continuar nesta sessão, mas o apoio não
     foi concluído. Não encaminhe automaticamente ao Ollama ou ao Claude.
