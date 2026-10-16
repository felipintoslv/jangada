# jangada

[![verificar](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml/badge.svg)](https://github.com/felipintoslv/jangada/actions/workflows/verificar.yml)

Configuração de Arch Linux com Hyprland em Lua (0.55 ou mais novo),
com área de trabalho e ferramentas para abrir, acompanhar e revisar
sessões de agentes de IA. Usa waybar, fuzzel, mako e cores do matugen.

## Princípios

- **Isolamento:** sessão própria; configuração em `~/.config/jangada`,
  instalação em `~/.local/share/jangada` e estado em `~/.local/state/jangada`.
  As outras sessões e suas configurações são preservadas.
- **Cópia antes de alterar:** arquivos existentes recebem cópia de segurança;
  ajustes pessoais são criados somente quando ausentes.
- **Instalação repetível:** cada etapa pode rodar novamente e respeita a simulação.
- **Padrões separados dos ajustes:** padrões em `core/`, `shell/` e `monitor/`;
  preferências pessoais em `~/.config/jangada`.
- **Revisão independente:** o agente trabalha no isolamento, testa e pede
  revisão antes de entregar. O usuário controla integração e envio ao remoto.

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
| `core/` | sessões, isolamento, revisão, delegação, fila e provedores |
| `shell/` | Hyprland, barra, temas, menus e integração com o terminal |
| `monitor/` | painel, consumo e diagnóstico |
| `install/`, `config/`, `migrations/` | instalação, modelos pessoais e migrações |
| `bin/`, `default/` | entradas compartilhadas e links de compatibilidade |
| `docs/` | guias por assunto e sínteses históricas |
| `testes/` | verificação estática, testes e sessão Hyprland aninhada |
| `revisao/`, `estudos/`, `benchmarking/` | auditorias, comparações e referências |

### Compatibilidade até v0.4.0

Os 73 links em `bin/` e `default/` permanecem nesta versão.
Sua remoção está prevista para **v0.4.0**, também registrada no
[CHANGELOG](CHANGELOG.md#planejado-para-v040).
Quem chama `bin/jangada-*` deverá usar o comando pelo PATH instalado ou
seu caminho em `core/bin/`, `shell/bin/` ou `monitor/bin/`.
Referências a `default/` deverão apontar ao arquivo no módulo correspondente;
consulte o [inventário de caminhos](docs/modularizacao-3.0/01-inventario.md).
Hoje, chamadas diretas aos módulos ainda não encontram `jangada-config`;
a retirada depende de adaptar essa resolução. Continue usando `bin/` até lá.

## Documentação

Antes de alterar arquivos, leia o guia do assunto da tarefa e as regras do
[AGENTS.md](AGENTS.md). Para desenvolver, rode `testes/verificar.sh` e
`jangada-validar`; veja as condições em [boas práticas](docs/boas-praticas.md).

| Assunto | Documento |
|---|---|
| Instalação, GPU, várias máquinas e assinatura | [Instalação e uso](docs/instalacao-e-uso.md) |
| Comandos disponíveis | [Comandos](docs/comandos.md) |
| Interface, temas, login, atalhos e Central de Tarefas | [Interface](docs/interface.md) |
| Abertura, revisão, encerramento, worktrees e skills | [Ciclo da tarefa](docs/ciclo-da-tarefa.md) |
| Permissões, credenciais e modelo de ameaça | [Isolamento](docs/isolamento.md) |
| Papéis, Ollama, agy e fila persistente | [Subagentes e delegação](docs/subagentes-e-delegacao.md) |
| Codex como executor e revisor | [Codex](docs/codex.md) |
| Registro de provedores | [Provedores](docs/provedores.md) |
| Atualização e migrações | [Atualização e migrações](docs/atualizacao-e-migracoes.md) |
| Painel, consumo e indicadores | [Painel](docs/painel.md) |
| Campos e limites dos registros | [Registros](docs/registros.md) |
| Código, testes, textos e commits | [Boas práticas](docs/boas-praticas.md) |
| Transparência e desfoque | [Vidro fosco](docs/vidro-fosco.md) |
| Teclado da bandeja e escalas | [Teclado na Waybar](docs/teclado-waybar.md) |
| Estado P0, limites P1 e evidências arquivadas | [Estabilização](docs/estabilizacao/README.md) |
| Divisão em módulos e contratos | [Modularização 3.0](docs/modularizacao-3.0/README.md) |
| Coordenação e consultas entre módulos | [Coordenação central](docs/coordenacao-central/README.md) |
| Evolução da interface | [Evolução 2.0](docs/evolucao-2.0/00-indice.md) |
| Proposta de diagnóstico, ainda sem implementação | [Inspector](docs/inspector/README.md) |
| Análise do painel em 30/09/2026 | [Análise](docs/analise-painel-20260930.md) |
| Proposta do painel, com implementação parcial | [Proposta](docs/proposta-atualizacao-painel.md) |

A correção P0 foi incorporada em `19f5569`; a validação P1 permanece
inconclusiva. O uso diário desde 19/09/2026 não comprova o ciclo completo
com modelos reais nem a portabilidade para uma segunda máquina.
Relatórios de ensaios descrevem a versão e o ambiente avaliados.
Logs, dados de validação e roteiros históricos estão no ramo
`arquivo/evidencias`, commit `7a9d1e5`; veja os índices de
[estabilização](docs/estabilizacao/README.md) e [revisões](revisao/README.md).
