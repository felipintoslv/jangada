# jangada

[![verificar](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml/badge.svg)](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml)

Configuração de Arch Linux com Hyprland em Lua (0.55 ou mais novo),
com área de trabalho e ferramentas para abrir, acompanhar e revisar
sessões de agentes de IA. Usa waybar, fuzzel, mako e cores do matugen.

## O que é o Shell

O Shell é a camada de área de trabalho do jangada: sessão Hyprland, barra,
temas, menus, atalhos, tema de login e a Central de Tarefas (PyQt6). O
jangada tem dois repositórios: o Shell (este) e o
[Core](https://github.com/felipintoslv/jangada-core) (sessões de agentes,
isolamento, revisão e delegação), **instalado separadamente**. Os indicadores
de consumo e revisão ficam na aba Indicadores da Central. O Shell chama os
comandos do Core só pelo nome, via `PATH`, e funciona sem ele, sem os dados de
sessões. A raiz do Core, quando a Central precisa dela, vem de
`JANGADA_CORE_PATH`.

## Princípios

- **Isolamento:** sessão própria; configuração em `~/.config/jangada`,
  instalação em `~/.local/share/jangada` e estado em `~/.local/state/jangada`.
  As outras sessões e suas configurações são preservadas.
- **Cópia antes de alterar:** arquivos existentes recebem cópia de segurança;
  ajustes pessoais são criados somente quando ausentes.
- **Instalação repetível:** cada etapa pode rodar novamente e respeita a simulação.
- **Padrões separados dos ajustes:** padrões no repositório; preferências
  pessoais em `~/.config/jangada`.

## Instalação

Em cada máquina, faça o inventário antes de instalar:

```sh
git clone https://github.com/felipintoslv/jangada.git ~/.local/share/jangada
cd ~/.local/share/jangada
bin/jangada-mapear
JANGADA_SIMULAR=1 ./install.sh
./install.sh
```

Confira a simulação antes de aplicar. Depois, encerre a sessão atual e
escolha **jangada** no gerenciador de login. A instalação efetiva recusa
worktrees e a cópia de desenvolvimento, que são graváveis pelo agente.

Consulte [instalação e uso](docs/instalacao-e-uso.md) para importar ajustes
do niri, escolher GPU e preparar outras máquinas.
A interface alternativa do Noctalia ainda exige `qs -c noctalia-shell`;
use `componentes` quando essa interface antiga não estiver disponível.

## Estrutura

| Pasta | Conteúdo |
|---|---|
| `bin/` | comandos do Shell (`jangada-shell-config`, `jangada-sistema-update`, `jangada-shell-migrar`, barra, tema, menus) |
| `hyprland/`, `waybar/`, `temas/`, `menus/`, `integracoes/` | configuração e interface |
| `install/`, `config/`, `migrations/` | instalação, modelos pessoais e migrações |
| `docs/` | guias por assunto; `docs/historico/` guarda estudos e planos encerrados |
| `testes/` | verificação estática e testes (`testes/verificar.sh`) |

## Documentação

Antes de alterar arquivos, leia o guia do assunto da tarefa e as regras do
[AGENTS.md](AGENTS.md). Para desenvolver, rode `testes/verificar.sh` e
`jangada-validar`; veja as condições em [boas práticas](docs/boas-praticas.md).

| Assunto | Documento |
|---|---|
| Instalação, GPU, várias máquinas e assinatura | [Instalação e uso](docs/instalacao-e-uso.md) |
| Comandos disponíveis | [Comandos](docs/comandos.md) |
| Interface, temas, login, atalhos e Central de Tarefas | [Interface](docs/interface.md) |
| Abas e botões da Central: real, simulado ou ausente | [O que funciona na Central](docs/central-o-que-funciona.md) |
| Abertura, revisão, encerramento, worktrees e skills | [Ciclo da tarefa](docs/ciclo-da-tarefa.md) |
| Permissões, credenciais e modelo de ameaça | [Isolamento](docs/isolamento.md) |
| Papéis, Ollama, agy e fila persistente | [Subagentes e delegação](docs/subagentes-e-delegacao.md) |
| Codex como executor e revisor | [Codex](docs/codex.md) |
| Registro de provedores | [Provedores](docs/provedores.md) |
| Atualização e migrações | [Atualização e migrações](docs/atualizacao-e-migracoes.md) |
| Indicadores e diagnóstico do sistema | [O que funciona na Central](docs/central-o-que-funciona.md) e [Vigia](docs/vigia/README.md) |
| Campos e limites dos registros | [Registros](docs/registros.md) |
| Código, testes, textos e commits | [Boas práticas](docs/boas-praticas.md) |
| Transparência e desfoque | [Vidro fosco](docs/vidro-fosco.md) |
| Teclado da bandeja e escalas | [Teclado na Waybar](docs/teclado-waybar.md) |
| Estudos, auditorias e planos encerrados | [Histórico](docs/historico/README.md) |
