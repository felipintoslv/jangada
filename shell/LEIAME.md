# shell/

Módulo Shell da modularização 3.0: área de trabalho (Hyprland, Waybar,
temas, menus) e integração com Bash e Zsh. O plano está em
[docs/modularizacao-3.0](../docs/modularizacao-3.0/README.md).

`jangada.sh` e `jangada-shell.sh` já existiam e ficam onde estão: o
`~/.bashrc` e o `~/.zshrc` do usuário guardam esses caminhos (K2). O módulo
cresce ao redor deles na Onda C, um commit por mudança de pasta, com link
relativo no caminho antigo (`bin/`, `default/`). O destino de cada arquivo
está em [01-inventario.md](../docs/modularizacao-3.0/01-inventario.md).

| Subpasta prevista | Conteúdo |
|---|---|
| `shell/bin` | 25 comandos |
| `shell/hyprland` | configuração Lua do Hyprland, com os atalhos |
| `shell/waybar` | barra |
| `shell/temas` | matugen, tela de login, logo e fastfetch |
| `shell/menus` | Central de Tarefas e janela de conversa |
| `shell/integracoes` | snapper e R |

As subpastas chegam nas tarefas M3-12 a M3-15. O Git não guarda pasta
vazia: cada uma passa a existir com o primeiro arquivo movido.

Regras do módulo
([02-arquitetura.md](../docs/modularizacao-3.0/02-arquitetura.md) e
[03-contratos.md](../docs/modularizacao-3.0/03-contratos.md)):

1. O Shell usa o Core só por comandos públicos e pelas ações do núcleo (K1).
2. O Shell não lê arquivo de estado do Core direto (K9).
3. Os comandos continuam públicos em `bin/` (K1).
4. `testes/verificar.sh` e `testes/regra1.sh` examinam `shell/bin`.
