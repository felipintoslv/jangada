# monitor/

Módulo Monitor da modularização 3.0: painel de indicadores, consumo,
subagentes e diagnóstico. O plano está em
[docs/modularizacao-3.0](../docs/modularizacao-3.0/README.md).

Esta pasta foi criada na tarefa M3-11 e ainda não tem código. Os arquivos
chegam na Onda C, um commit por mudança de pasta, com link relativo no
caminho antigo (`bin/`, `default/`). O destino de cada arquivo está em
[01-inventario.md](../docs/modularizacao-3.0/01-inventario.md).

| Subpasta prevista | Conteúdo | Tarefa |
|---|---|---|
| `monitor/bin` | `jangada-painel`, `jangada-consumo`, `jangada-subagentes`, `jangada-verificar` | M3-17 |
| `monitor/painel` | painel em Python e R | M3-17 |

O Git não guarda pasta vazia: cada subpasta passa a existir com o primeiro
arquivo movido.

Regras do módulo
([02-arquitetura.md](../docs/modularizacao-3.0/02-arquitetura.md) e
[03-contratos.md](../docs/modularizacao-3.0/03-contratos.md)):

1. O Monitor só lê. Ele não chama comando que altera estado (K9).
2. Os dados vêm das consultas de leitura do Core (K5) e dos registros com
   formato testado (K7).
3. Os comandos continuam públicos em `bin/` (K1).
4. `testes/verificar.sh` e `testes/regra1.sh` examinam `monitor/bin`.
