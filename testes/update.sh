#!/usr/bin/env bash
# Testa, em repositórios temporários, o que chega à cópia instalada: o
# jangada-update só aplica commits novos da origem com confirmação e, com
# allowed_signers, só os assinados, que o jangada-assinar assina, chamado
# também pelo --integrar; o
# jangada-agente-fim --integrar não atualiza a cópia instalada nem roda o git
# com fsmonitor ou ganchos do repositório do agente; o install.sh recusa a
# cópia de trabalho e os worktrees. pacman, checkupdates,
# sudo, paru e tmux são substituídos por scripts falsos.
#
# Uso: testes/update.sh
set -uo pipefail
export LC_ALL=C.UTF-8
cd "$(dirname "$0")/.." || exit 1
repo_jangada="$PWD"
falhas=0
ok()    { printf 'ok    %s\n' "$*"; }
falha() { printf 'FALHA %s\n' "$*"; falhas=$((falhas + 1)); }
conferir() { local d="$1"; shift; if "$@"; then ok "$d"; else falha "$d"; fi; }

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

# Nada da configuração do git do usuário (assinatura, ganchos) entra no teste.
export GIT_CONFIG_GLOBAL="$tmp/gitconfig" GIT_CONFIG_NOSYSTEM=1
: >"$GIT_CONFIG_GLOBAL"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export HOME="$tmp/home" XDG_CONFIG_HOME="$tmp/home/.config" XDG_STATE_HOME="$tmp/home/.local/state"
mkdir -p "$HOME" "$XDG_CONFIG_HOME" "$XDG_STATE_HOME"
unset HYPRLAND_INSTANCE_SIGNATURE JANGADA_SESSAO JANGADA_REPO JANGADA_SIMULAR

# Comandos do sistema falsos: registram a chamada e não alteram nada.
falsos="$tmp/falsos"; mkdir -p "$falsos"
registro="$tmp/chamadas"
cat >"$falsos/pacman" <<EOF
#!/bin/sh
echo "pacman \$*" >>"$registro"
case "\$1" in -Q*) exit 1 ;; esac
exit 0
EOF
cat >"$falsos/sudo" <<EOF
#!/bin/sh
echo "sudo \$*" >>"$registro"
exec "\$@"
EOF
cat >"$falsos/checkupdates" <<'EOF'
#!/bin/sh
exit 2
EOF
cat >"$falsos/paru" <<EOF
#!/bin/sh
echo "paru \$*" >>"$registro"
exit 0
EOF
cat >"$falsos/yay" <<EOF
#!/bin/sh
echo "yay \$*" >>"$registro"
exit 0
EOF
cat >"$falsos/tmux" <<'EOF'
#!/bin/sh
for a in "$@"; do [ "$a" = has-session ] && exit 1; done
exit 0
EOF
chmod +x "$falsos"/*
export PATH="$falsos:$PATH"

# Origem (a cópia de trabalho) com o bin/ atual e sem migrações; a cópia
# instalada é um clone dela, como na máquina.
origem="$tmp/origem"; instalado="$tmp/instalado"
mkdir -p "$origem/migrations"
cp -r "$repo_jangada/bin" "$origem/"
echo "migrações" >"$origem/migrations/README.md"
git -C "$origem" init --quiet -b main
git -C "$origem" add -A
git -C "$origem" commit --quiet -m "feat(base): início"
git clone --quiet "$origem" "$instalado"
export JANGADA_PATH="$instalado"

marca="$HOME/migracao-nova"
cat >"$origem/migrations/900-teste.sh" <<'EOF'
touch "$HOME/migracao-nova"
EOF
git -C "$origem" add -A
git -C "$origem" commit --quiet -m $'feat(teste): migração \e[2Jnova'
novo="$(git -C "$origem" rev-parse HEAD)"
antes="$(git -C "$instalado" rev-parse HEAD)"

atualizar() { (cd "$tmp" && "$instalado/bin/jangada-update") >"$tmp/saida" 2>&1; rc=$?; }
head_instalado() { git -C "$instalado" rev-parse HEAD; }

echo "== jangada-update"

atualizar <<<n
conferir "resposta n: termina sem erro ($rc)" test "$rc" -eq 0
conferir "resposta n: cópia instalada não avança" test "$(head_instalado)" = "$antes"
conferir "resposta n: migração nova não roda" test ! -e "$marca"
conferir "resposta n: pacman -Syu roda mesmo assim" grep -q 'sudo pacman -Syu' "$registro"
conferir "mostra o commit novo" grep -q 'migração \[2Jnova' "$tmp/saida"
conferir "assunto sem o caractere ESC" bash -c '! grep -q $'"'"'\e'"'"' "$1"' _ "$tmp/saida"
conferir "destaca a mudança em migrations/" grep -q '^   migrations/900-teste.sh' "$tmp/saida"
conferir "avisa que não aplicou" grep -q 'não aplicadas' "$tmp/saida"
conferir "checkupdates sem atualização não é falha" bash -c '! grep -q "checkupdates falhou" "$1"' _ "$tmp/saida"

atualizar </dev/null
conferir "sem terminal: termina sem erro ($rc)" test "$rc" -eq 0
conferir "sem terminal: cópia instalada não avança" test "$(head_instalado)" = "$antes"
conferir "sem terminal: migração nova não roda" test ! -e "$marca"

atualizar <<<s
conferir "resposta s: termina sem erro ($rc)" test "$rc" -eq 0
conferir "resposta s: cópia instalada avança" test "$(head_instalado)" = "$novo"
conferir "resposta s: migração nova roda" test -e "$marca"

# A origem reescrita (não avança em linha reta) é recusada como antes.
git -C "$origem" commit --quiet --amend -m "fix(teste): reescrito"
atualizar <<<s
conferir "origem reescrita: termina sem erro ($rc)" test "$rc" -eq 0
conferir "origem reescrita: cópia instalada não muda" test "$(head_instalado)" = "$novo"
conferir "origem reescrita: explica a recusa" grep -q 'não avança em linha reta' "$tmp/saida"

echo "== jangada-agente-fim --integrar"

# Sessão de agente num worktree da origem, com um commit a integrar.
git -C "$origem" reset --quiet --hard "$novo"
# O caminho é o que o jangada-agente cria: $JANGADA_WORKTREES/REPO/NOME.
wt="$HOME/.local/share/jangada-worktrees/origem/x"
git -C "$origem" worktree add --quiet -b agente/x "$wt" main
echo "tarefa" >"$wt/tarefa.txt"
git -C "$wt" add tarefa.txt
git -C "$wt" commit --quiet -m "feat(teste): tarefa"
mkdir -p "$XDG_STATE_HOME/jangada/agentes"
jq -n --arg w "$wt" --arg r "$origem" \
  '{worktree: $w, ramo: "agente/x", base: "main", raiz: $r, estado: "concluido"}' \
  >"$XDG_STATE_HOME/jangada/agentes/x.json"
git -C "$instalado" fetch --quiet origin
antes_fim="$(head_instalado)"

# O que o agente poderia gravar no .git comum: fsmonitor e ganchos.
alerta="$tmp/executou-codigo-do-agente"
printf '#!/bin/sh\ntouch "%s"\n' "$alerta" >"$tmp/fsmonitor.sh"
mkdir -p "$tmp/ganchos"
for h in pre-merge-commit post-merge post-checkout reference-transaction; do
  cp "$tmp/fsmonitor.sh" "$tmp/ganchos/$h"
done
chmod +x "$tmp/fsmonitor.sh" "$tmp/ganchos"/*
git -C "$origem" config core.fsmonitor "$tmp/fsmonitor.sh"
git -C "$origem" config core.hooksPath "$tmp/ganchos"

printf 's\n' | (cd "$tmp" && "$repo_jangada/bin/jangada-agente-fim" --integrar x) >"$tmp/saida" 2>&1
rc=$?
git -C "$origem" config --unset core.fsmonitor
git -C "$origem" config --unset core.hooksPath
conferir "integra sem erro ($rc)" test "$rc" -eq 0
conferir "ramo integrado na origem" grep -q 'feat(teste): tarefa' <(git -C "$origem" log --oneline main)
conferir "ramo apagado depois da integração" test -z "$(git -C "$origem" branch --list agente/x)"
conferir "worktree removido" test ! -d "$wt"
conferir "cópia instalada não é atualizada" test "$(head_instalado)" = "$antes_fim"
conferir "pede para rodar jangada-update" grep -q 'rode jangada-update' "$tmp/saida"
conferir "fsmonitor e ganchos do repositório não rodam" test ! -e "$alerta"

echo "== assinaturas"

# A cópia instalada alcança a origem antes de as assinaturas valerem; o que
# já foi enviado a um remoto (o GitHub, na máquina) não é reescrito.
atualizar <<<s
remoto="$tmp/remoto.git"
git init --quiet --bare "$remoto"
git -C "$origem" remote add github "$remoto"
git -C "$origem" push --quiet -u github main 2>/dev/null
mkdir -p "$HOME/.ssh" "$XDG_CONFIG_HOME/jangada"
ssh-keygen -q -t ed25519 -N '' -C t -f "$HOME/.ssh/id_ed25519"
ssh-keygen -q -t ed25519 -N '' -C outra -f "$tmp/outra"
printf 't@t namespaces="git" %s\n' "$(cat "$HOME/.ssh/id_ed25519.pub")" >"$XDG_CONFIG_HOME/jangada/allowed_signers"
assinar() { (cd "$tmp" && "$repo_jangada/bin/jangada-assinar" "$origem") >"$tmp/saida" 2>&1; rc=$?; }
assinatura() { git -C "$origem" -c gpg.ssh.allowedSignersFile="$XDG_CONFIG_HOME/jangada/allowed_signers" log -1 --format=%G? "$1"; }

echo c1 >"$origem/c1.txt"
git -C "$origem" add c1.txt
git -C "$origem" commit --quiet -m "feat(teste): sem assinatura"
antes_ass="$(head_instalado)"
atualizar <<<s
conferir "sem assinatura: a cópia instalada não avança" test "$(head_instalado)" = "$antes_ass"
conferir "sem assinatura: diz o commit e o jangada-assinar" \
  bash -c 'grep -q "sem assinatura válida" "$1" && grep -q "feat(teste): sem assinatura" "$1"' _ "$tmp/saida"

assinar </dev/null
conferir "assinar sem terminal: não assina ($rc)" [ "$rc" -ne 0 ]
conferir "assinar sem terminal: o commit segue sem assinatura" [ "$(assinatura HEAD)" != G ]
assinar <<<s
conferir "assinar: termina sem erro ($rc)" [ "$rc" -eq 0 ]
conferir "assinar: mostra o commit" grep -q "feat(teste): sem assinatura" "$tmp/saida"
conferir "assinar: o commit tem assinatura válida" [ "$(assinatura HEAD)" = G ]
conferir "assinar: sem commit enviado por assinar, não avisa" bash -c '! grep -q "já enviados" "$1"' _ "$tmp/saida"
conferir "assinar: o já enviado não muda" [ "$(git -C "$origem" rev-parse "main@{upstream}")" = "$(git -C "$remoto" rev-parse main)" ]
c1="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "assinar de novo: nada a assinar" grep -q "nada a assinar" "$tmp/saida"
atualizar <<<s
conferir "assinado: a cópia instalada avança" test "$(head_instalado)" = "$c1"

# Assinado por uma chave fora do allowed_signers vale como sem assinatura, e
# o jangada-assinar só reescreve dali em diante.
echo c2 >"$origem/c2.txt"
git -C "$origem" add c2.txt
git -C "$origem" -c gpg.format=ssh -c user.signingkey="$tmp/outra" commit --quiet -S -m "feat(teste): outra chave"
atualizar <<<s
conferir "outra chave: a cópia instalada não avança" test "$(head_instalado)" = "$c1"
assinar <<<s
conferir "outra chave: assinar só reescreve o commit dela" \
  bash -c '[ "$(git -C "$1" rev-parse HEAD^)" = "$2" ] && ! grep -q "feat(teste): sem assinatura" "$3"' _ "$origem" "$c1" "$tmp/saida"
atualizar <<<s
conferir "outra chave, depois de assinar: a cópia instalada avança" \
  test "$(head_instalado)" = "$(git -C "$origem" rev-parse HEAD)"

# Commit enviado sem assinatura: o assinar não o reescreve e o update não
# passa dele; o aviso diz o commit e o comando que avança a cópia instalada.
# Dois ramos sem assinatura unidos por um merge assinado: o destino do
# comando é a origem, que descende dos dois.
git -C "$origem" branch enviado
echo e1 >"$origem/e1.txt"
git -C "$origem" add e1.txt
git -C "$origem" commit --quiet -m "feat(teste): enviado sem assinatura"
git -C "$origem" switch --quiet enviado
echo e2 >"$origem/e2.txt"
git -C "$origem" add e2.txt
git -C "$origem" commit --quiet -m "feat(teste): enviado no outro ramo"
git -C "$origem" switch --quiet main
git -C "$origem" -c gpg.format=ssh -c user.signingkey="$HOME/.ssh/id_ed25519" \
  merge --quiet --no-ff -S -m "Integra enviado" enviado
git -C "$origem" branch --quiet -D enviado
git -C "$origem" push --quiet github main 2>/dev/null
e1="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "enviado sem assinatura: avisa e diz o commit" \
  bash -c 'grep -q "já enviados sem assinatura" "$1" && grep -q "feat(teste): enviado sem assinatura" "$1" &&
    grep -q "feat(teste): enviado no outro ramo" "$1" && ! grep -q "Integra enviado" "$1"' _ "$tmp/saida"
conferir "enviado sem assinatura: não reescreve" [ "$(git -C "$origem" rev-parse HEAD)" = "$e1" ]
# Caminho da cópia instalada com espaço e caracteres do shell: o comando do
# aviso sai com escape e só avança essa cópia.
especial="$tmp/inst alada;\$(touch alerta-escape)"
git clone --quiet "$origem" "$especial"
git -C "$especial" reset --quiet --hard "$(head_instalado)"
(cd "$tmp" && JANGADA_PATH="$especial" "$repo_jangada/bin/jangada-assinar" "$origem") >"$tmp/saida-especial" 2>&1 <<<s
conferir "enviado sem assinatura, caminho com espaço e \$(): o comando do aviso avança só essa cópia" \
  bash -c 'cd "$5" && eval "$(grep -o "git -C .* merge --ff-only [0-9a-f]*" "$1")" >/dev/null 2>&1
    [ "$(git -C "$2" rev-parse HEAD)" = "$3" ] && [ "$(git -C "$4" rev-parse HEAD)" != "$3" ] && [ ! -e alerta-escape ]' \
  _ "$tmp/saida-especial" "$especial" "$e1" "$instalado" "$tmp"
avanco="$(grep -o 'git -C .* merge --ff-only [0-9a-f]*' "$tmp/saida")"
conferir "enviado sem assinatura: o comando do aviso avança a cópia instalada" \
  bash -c 'eval "$1" >/dev/null 2>&1 && [ "$(git -C "$2" rev-parse HEAD)" = "$3" ]' _ "$avanco" "$instalado" "$e1"
assinar <<<s
conferir "enviado sem assinatura, cópia instalada avançada: não avisa mais" \
  bash -c '! grep -q "já enviados" "$1"' _ "$tmp/saida"

# Vários commits sem assinatura: o primeiro é achado sem cortar a saída do
# git log, que morreria por SIGPIPE e encerraria o script sem mensagem.
for i in $(seq 20); do
  echo "$i" >"$origem/lote.txt"
  git -C "$origem" add lote.txt
  git -C "$origem" commit --quiet -m "feat(teste): lote $i"
done
assinar <<<s
conferir "vários sem assinatura: assina todos ($rc)" \
  bash -c '[ "$1" -eq 0 ] && grep -q "^assinados" "$2"' _ "$rc" "$tmp/saida"
conferir "vários sem assinatura: o mais antigo tem assinatura válida" [ "$(assinatura HEAD~19)" = G ]
atualizar <<<s

# Merge do jangada-agente-fim --integrar: o ramo saiu de antes de um commit
# já assinado, que fica como está; o commit do ramo e o merge são assinados.
git -C "$origem" branch agente/m
echo m1 >"$origem/m1.txt"
git -C "$origem" add m1.txt
git -C "$origem" commit --quiet -m "feat(teste): antes do merge"
assinar <<<s
m1="$(git -C "$origem" rev-parse HEAD)"
git -C "$origem" checkout --quiet agente/m
echo m2 >"$origem/m2.txt"
git -C "$origem" add m2.txt
git -C "$origem" commit --quiet -m "feat(teste): no ramo"
git -C "$origem" checkout --quiet main
git -C "$origem" merge --quiet --no-ff -m "Integra agente/m" agente/m
arvore_m="$(git -C "$origem" rev-parse 'HEAD^{tree}')"
assinar <<<s
conferir "merge: assina sem erro ($rc)" [ "$rc" -eq 0 ]
conferir "merge: continua merge, com a mesma árvore" \
  bash -c '[ "$(git -C "$1" rev-list --parents -1 HEAD | wc -w)" -eq 3 ] && [ "$(git -C "$1" rev-parse "HEAD^{tree}")" = "$2" ]' _ "$origem" "$arvore_m"
conferir "merge: o merge e o commit do ramo têm assinatura válida" [ "$(assinatura HEAD)$(assinatura HEAD^2)" = GG ]
conferir "merge: o já assinado antes do ramo não muda" [ "$(git -C "$origem" rev-parse HEAD^)" = "$m1" ]
git -C "$origem" branch --quiet -D agente/m
m_assinado="$(git -C "$origem" rev-parse HEAD)"
atualizar <<<s
conferir "merge assinado: a cópia instalada avança" test "$(head_instalado)" = "$m_assinado"

# O --integrar chama o jangada-assinar depois de apagar o ramo: a primeira
# resposta confirma o merge, a segunda a assinatura.
integrar_y() {
  git -C "$origem" worktree add --quiet -b agente/y "$wt_y" main
  echo "$1" >"$wt_y/y.txt"
  git -C "$wt_y" add y.txt
  git -C "$wt_y" commit --quiet -m "feat(teste): tarefa y $1"
  jq -n --arg w "$wt_y" --arg r "$origem" \
    '{worktree: $w, ramo: "agente/y", base: "main", raiz: $r, estado: "concluido"}' \
    >"$XDG_STATE_HOME/jangada/agentes/y.json"
  printf '%s\n' s "$2" | (cd "$tmp" && "$repo_jangada/bin/jangada-agente-fim" --integrar y) >"$tmp/saida" 2>&1
  rc=$?
}
wt_y="$HOME/.local/share/jangada-worktrees/origem/y"
integrar_y a s
conferir "integrar com allowed_signers: termina sem erro ($rc)" [ "$rc" -eq 0 ]
conferir "integrar com allowed_signers: o merge e o commit do ramo têm assinatura válida" \
  [ "$(assinatura HEAD)$(assinatura HEAD^2)" = GG ]
conferir "integrar com allowed_signers: ramo apagado" test -z "$(git -C "$origem" branch --list agente/y)"
integrar_y b n
conferir "integrar sem confirmar a assinatura: encerra a sessão e avisa ($rc)" \
  bash -c '[ "$1" -eq 0 ] && grep -q "sessão encerrada: y" "$2" && grep -q "ficou sem assinatura" "$2"' _ "$rc" "$tmp/saida"
conferir "integrar sem confirmar a assinatura: o merge fica sem assinatura" [ "$(assinatura HEAD)" != G ]
git -C "$origem" reset --quiet --hard "$m_assinado"

# De dentro da própria sessão a limpeza segue sem terminal: avisa e não assina.
JANGADA_SESSAO=y integrar_y c s
registro_y="$XDG_STATE_HOME/jangada/agentes/fim-y.log"
for _ in $(seq 50); do
  grep -q "sessão encerrada: y" "$registro_y" 2>/dev/null && break
  sleep 0.2
done
conferir "integrar de dentro da sessão: termina sem erro e avisa ($rc)" \
  bash -c '[ "$1" -eq 0 ] && grep -q "ficou sem assinatura" "$2"' _ "$rc" "$tmp/saida"
conferir "integrar de dentro da sessão: a limpeza termina sem chamar o jangada-assinar" \
  bash -c 'grep -q "sessão encerrada: y" "$1" && ! grep -q "assinar" "$1"' _ "$registro_y"
conferir "integrar de dentro da sessão: o merge fica sem assinatura" [ "$(assinatura HEAD)" != G ]
git -C "$origem" reset --quiet --hard "$m_assinado"

# Merge com alteração feita à mão: refazê-lo perderia a alteração, então nada
# é assinado e o ramo volta ao que era.
git -C "$origem" branch agente/n
echo n1 >"$origem/n1.txt"
git -C "$origem" add n1.txt
git -C "$origem" commit --quiet -m "feat(teste): base do merge alterado"
git -C "$origem" checkout --quiet agente/n
echo n2 >"$origem/n2.txt"
git -C "$origem" add n2.txt
git -C "$origem" commit --quiet -m "feat(teste): ramo do merge alterado"
git -C "$origem" checkout --quiet main
git -C "$origem" merge --quiet --no-ff --no-commit agente/n >/dev/null 2>&1
echo extra >"$origem/n3.txt"
git -C "$origem" add n3.txt
git -C "$origem" commit --quiet -m "Integra agente/n"
antes_n="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "merge alterado à mão: recusa ($rc)" \
  bash -c '[ "$1" -ne 0 ] && grep -q "mudou o conteúdo" "$2"' _ "$rc" "$tmp/saida"
conferir "merge alterado à mão: o ramo volta ao que era" [ "$(git -C "$origem" rev-parse HEAD)" = "$antes_n" ]
# Um commit posterior desfaz a alteração: a árvore final seria a mesma, mas o
# merge refeito não. O commit traz outro arquivo para não ficar vazio no
# rebase, que pararia nele.
git -C "$origem" rm --quiet n3.txt
echo n4 >"$origem/n4.txt"
git -C "$origem" add n4.txt
git -C "$origem" commit --quiet -m "feat(teste): desfaz a alteração do merge"
antes_n="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "merge alterado à mão e desfeito depois: recusa ($rc)" \
  bash -c '[ "$1" -ne 0 ] && grep -q "mudou o conteúdo" "$2"' _ "$rc" "$tmp/saida"
conferir "merge alterado à mão e desfeito depois: o ramo volta ao que era" [ "$(git -C "$origem" rev-parse HEAD)" = "$antes_n" ]
git -C "$origem" reset --quiet --hard "$m_assinado"
git -C "$origem" branch --quiet -D agente/n
# Dois merges que trocariam de árvore ao serem refeitos: o primeiro
# acrescenta x.txt à mão, o segundo traz o mesmo x.txt do ramo e o tira à mão.
# O conjunto das árvores fica igual; a de cada commit, não.
git -C "$origem" branch agente/p
git -C "$origem" branch agente/q
git -C "$origem" checkout --quiet agente/p
echo p >"$origem/p.txt"
git -C "$origem" add p.txt
git -C "$origem" commit --quiet -m "feat(teste): ramo p"
git -C "$origem" checkout --quiet agente/q
echo x >"$origem/x.txt"
git -C "$origem" add x.txt
git -C "$origem" commit --quiet -m "feat(teste): ramo q"
git -C "$origem" checkout --quiet main
git -C "$origem" merge --quiet --no-ff --no-commit agente/p >/dev/null 2>&1
echo x >"$origem/x.txt"
git -C "$origem" add x.txt
git -C "$origem" commit --quiet -m "Integra agente/p"
git -C "$origem" merge --quiet --no-ff --no-commit agente/q >/dev/null 2>&1
git -C "$origem" rm --quiet -f x.txt
git -C "$origem" commit --quiet -m "Integra agente/q"
antes_pq="$(git -C "$origem" rev-parse HEAD)"
assinar <<<s
conferir "merges que trocariam de árvore: recusa ($rc)" \
  bash -c '[ "$1" -ne 0 ] && grep -q "mudou o conteúdo" "$2"' _ "$rc" "$tmp/saida"
conferir "merges que trocariam de árvore: o ramo volta ao que era" [ "$(git -C "$origem" rev-parse HEAD)" = "$antes_pq" ]
git -C "$origem" reset --quiet --hard "$m_assinado"
git -C "$origem" branch --quiet -D agente/p agente/q

# O gpg.ssh.program do repositório não roda na assinatura nem na conferência.
printf '#!/bin/sh\ntouch "%s"\nexit 1\n' "$alerta" >"$tmp/programa.sh"
chmod +x "$tmp/programa.sh"
git -C "$origem" config gpg.ssh.program "$tmp/programa.sh"
git -C "$instalado" config gpg.ssh.program "$tmp/programa.sh"
echo c3 >"$origem/c3.txt"
git -C "$origem" add c3.txt
git -C "$origem" commit --quiet -m "feat(teste): terceiro"
assinar <<<s
atualizar <<<s
conferir "gpg.ssh.program do repositório: assina e aplica" test "$(head_instalado)" = "$(git -C "$origem" rev-parse HEAD)"
conferir "gpg.ssh.program do repositório: não roda" test ! -e "$alerta"
git -C "$origem" config --unset gpg.ssh.program
git -C "$instalado" config --unset gpg.ssh.program

# Sem a chave (como no isolamento, com o ~/.ssh oculto), recusa com o motivo.
mv "$HOME/.ssh" "$HOME/.ssh-fora"
echo c4 >"$origem/c4.txt"
git -C "$origem" add c4.txt
git -C "$origem" commit --quiet -m "feat(teste): sem chave"
assinar <<<s
conferir "sem a chave: recusa ($rc)" [ "$rc" -ne 0 ]
conferir "sem a chave: indica o terminal comum" grep -q "terminal comum" "$tmp/saida"
mv "$HOME/.ssh-fora" "$HOME/.ssh"
git -C "$origem" reset --quiet --hard HEAD^
rm -f "$XDG_CONFIG_HOME/jangada/allowed_signers"

echo "== install.sh só da cópia instalada"

# Cópia só com o install.sh, a lib, a configuração e uma etapa que só marca
# que rodou.
inst="$tmp/inst"; mkdir -p "$inst/install" "$inst/bin"
cp "$repo_jangada/install.sh" "$inst/"
echo 'touch "$HOME/etapa-rodou"' >"$inst/install/00-teste.sh"
cp "$repo_jangada/install/lib.sh" "$inst/install/"
cp "$repo_jangada/bin/jangada-config" "$inst/bin/"
git -C "$inst" init --quiet -b main
git -C "$inst" add -A
git -C "$inst" commit --quiet -m "feat(base): instalação"
instalar() { env -u JANGADA_PATH "$@" >"$tmp/saida" 2>&1; }
mkdir -p "$XDG_CONFIG_HOME/jangada"

instalar "$inst/install.sh"; rc=$?
conferir "instala de um clone comum ($rc)" test "$rc" -eq 0
conferir "a etapa rodou" test -e "$HOME/etapa-rodou"
rm -f "$HOME/etapa-rodou"

printf 'JANGADA_REPO=%s\n' "$inst" >"$XDG_CONFIG_HOME/jangada/jangada.conf"
instalar "$inst/install.sh"; rc=$?
conferir "recusa a cópia de trabalho ($rc)" test "$rc" -ne 0
conferir "diz por que recusou" grep -q 'cópia de trabalho (JANGADA_REPO)' "$tmp/saida"
conferir "nenhuma etapa rodou" test ! -e "$HOME/etapa-rodou"
instalar env JANGADA_SIMULAR=1 "$inst/install.sh"; rc=$?
conferir "simula na cópia de trabalho ($rc)" test "$rc" -eq 0
conferir "a simulação avisa" grep -q 'só a simulação roda daqui' "$tmp/saida"
rm -f "$XDG_CONFIG_HOME/jangada/jangada.conf"

git -C "$inst" worktree add --quiet -b agente/inst "$tmp/inst-wt" main
instalar "$tmp/inst-wt/install.sh"; rc=$?
conferir "recusa um worktree ($rc)" test "$rc" -ne 0

mkdir -p "$HOME/.local/share/jangada-worktrees"
git clone --quiet "$inst" "$HOME/.local/share/jangada-worktrees/copia"
instalar "$HOME/.local/share/jangada-worktrees/copia/install.sh"; rc=$?
conferir "recusa um clone em JANGADA_WORKTREES ($rc)" test "$rc" -ne 0

if ((falhas)); then
  echo "--- última saída"; cat "$tmp/saida"
  echo "$falhas falha(s)"
  exit 1
fi
echo "tudo certo"
