# Atualização e migrações

O Shell roda de uma cópia instalada em `~/.local/share/jangada`
(`JANGADA_PATH`), que só avança pelo `jangada-sistema-update` e só depois de
você ver e aceitar os commits novos. Mudança que exige ajuste numa instalação
existente chega por uma migração, aplicada uma única vez pelo
`jangada-shell-migrar`. O Core tem comandos de atualização próprios; os dois
não se confundem pelo nome.

## Instalação inicial

O `install.sh` recusa root e roda `install/NN-*.sh` em ordem numérica:
00 verificações, 10 pacotes, 20 snapshots, 30 shell, 40 interface e 90, que
marca todas as migrações como aplicadas (uma instalação nova já recebe os
padrões atualizados).

- Com argumentos roda só as etapas com esse prefixo: `./install.sh 20 30`.
- `JANGADA_SIMULAR=1 ./install.sh` mostra o que seria feito.
- Da cópia de trabalho e de worktrees só a simulação roda.

## Como escrever uma etapa ou migração

As duas usam as funções de `install/lib.sh`: `executar`, `como_root`,
`copia_seguranca ARQ`, `copiar_se_ausente ORIGEM DESTINO` e `simulando`.
Regras de uma migração (`migrations/README.md`): nome
`AAAAMMDDHHMM-descricao.sh`; pode rodar de novo sem estragar nada; nunca
apaga arquivo do usuário (move para `.bak` com data); explica no topo o que
mudou e por quê; e o padrão do repositório é corrigido também, para a
instalação nova.

## jangada-sistema-update

1. Confere que a cópia instalada está limpa e busca a origem (`git fetch`).
2. Muda para o ramo de `JANGADA_CANAL`, se preciso.
3. Aplica só avanço rápido (`--ff-only`); origem reescrita é recusada.
4. Com `allowed_signers`, exige assinatura válida em cada commit novo.
5. Mostra os commits, os arquivos e um aviso quando mudam `migrations/`,
   `install/` ou `bin/`, e só aplica com `s`. Sem terminal, a resposta é não.
6. Atualiza os pacotes (pacman e AUR); se o conjunto do Hyprland muda, pede
   confirmação antes.
7. Roda o `jangada-shell-migrar` e, dentro do Hyprland, o `jangada-recarregar`.
8. Confere erros de mkinitcpio e dkms no `pacman.log` e chama o
   `jangada-gancho pos-update` do Core, se ele estiver no `PATH`.

Todo git sobre a cópia instalada passa por `jangada_git_seguro`, sem
fsmonitor nem ganchos da configuração do repositório.

Sem o Core no `PATH`, a atualização segue: o resumo de versão usa o commit e
os ganchos do usuário não rodam, com aviso.

### Atualizar somente o código

`jangada-sistema-update --somente-codigo` atualiza apenas o Git da cópia
instalada, com a mesma confirmação, conferência de assinaturas e avanço
rápido. Não executa pacotes, migrações, recarga nem ganchos. Recusa agentes
isolados, sessões no tmux do Jangada e processos que usam o código instalado.
Não há simulação: `JANGADA_SIMULAR=1` é recusado. As migrações pendentes se
conferem à parte:

```sh
JANGADA_SIMULAR=1 ~/.local/share/jangada/bin/jangada-shell-migrar
```

## jangada-shell-migrar

Pega um `flock` na pasta de marcas (60 s) e aplica `migrations/*.sh` em ordem
de nome. A marca de cada migração fica em `$JANGADA_ESTADO/migracoes/NOME`
(`~/.local/state/jangada/migracoes/`). Uma migração que falha para a sequência
com código 1. Em simulação a marca não é gravada, para a execução de verdade
não pular uma migração que nunca foi aplicada.

## Testes

| Arquivo | O que cobre |
|---|---|
| `testes/update.sh` | só aplica com `s`; sem terminal não aplica; migração nova roda e grava marca; origem reescrita recusada; com `allowed_signers`, commit sem assinatura ou com chave de fora não é aplicado; `install.sh` recusa a cópia de trabalho e os worktrees |
| `testes/update-codigo.py` | `--somente-codigo` em clones descartáveis, com comandos de sistema que falham se chamados |
| `testes/barra.sh` | migração que acrescenta o módulo de indicadores à barra |
| `testes/shell-core.sh` | o Shell com e sem comandos do Core no `PATH` |
| `.github/workflows/verificar.yml` | `testes/verificar.sh` e a simulação da instalação como usuário sem sudo |

Veja também as [boas práticas](boas-praticas.md).
