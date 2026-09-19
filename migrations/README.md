# Migrações

Cada arquivo `AAAAMMDDHHMM-descricao.sh` é um script bash aplicado uma única vez
por `jangada-migrar` (chamado pelo `jangada-update`), em ordem de nome.

Regras:

1. A migração deve poder rodar de novo sem estragar nada, porque uma falha no
   meio faz com que ela seja tentada outra vez.
2. Nunca apagar arquivos do usuário: mover para uma cópia `.bak` com data.
3. Explicar no topo do arquivo o que mudou e por quê (por exemplo, a opção do
   Hyprland que foi renomeada e a versão em que isso aconteceu).
4. Numa instalação nova, todas as migrações existentes são marcadas como
   aplicadas (etapa `install/90-migracoes.sh`), porque os padrões já estão atualizados.
