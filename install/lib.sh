#!/usr/bin/env bash
# Funções compartilhadas pelas etapas de instalação e pelos comandos jangada-*.
# Este arquivo é carregado com `source`; não executa nada sozinho.

JANGADA_PATH="${JANGADA_PATH:-$HOME/.local/share/jangada}"
JANGADA_CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/jangada"
JANGADA_ESTADO="${XDG_STATE_HOME:-$HOME/.local/state}/jangada"
JANGADA_SIMULAR="${JANGADA_SIMULAR:-0}"

export JANGADA_PATH JANGADA_CONFIG JANGADA_ESTADO

if [[ -t 1 ]]; then
  _cor_info=$'\e[36m'; _cor_ok=$'\e[32m'; _cor_aviso=$'\e[33m'; _cor_erro=$'\e[31m'; _cor_fim=$'\e[0m'
else
  _cor_info=""; _cor_ok=""; _cor_aviso=""; _cor_erro=""; _cor_fim=""
fi

info()  { printf '%s==>%s %s\n' "$_cor_info" "$_cor_fim" "$*"; }
ok()    { printf '%s ok%s %s\n' "$_cor_ok" "$_cor_fim" "$*"; }
aviso() { printf '%s !!%s %s\n' "$_cor_aviso" "$_cor_fim" "$*" >&2; }
erro()  { printf '%sERRO%s %s\n' "$_cor_erro" "$_cor_fim" "$*" >&2; }
morrer() { erro "$*"; exit 1; }

simulando() { [[ "$JANGADA_SIMULAR" == "1" ]]; }

# Executa um comando, ou apenas o mostra quando JANGADA_SIMULAR=1.
executar() {
  if simulando; then
    printf '   [simulação] %q' "$1"; shift
    (($#)) && printf ' %q' "$@"
    printf '\n'
    return 0
  fi
  "$@"
}

# Executa como root. Na simulação, apenas mostra.
como_root() {
  if [[ $EUID -eq 0 ]]; then
    executar "$@"
  else
    executar sudo "$@"
  fi
}

tem_comando() { command -v "$1" >/dev/null 2>&1; }

# Pergunta sim ou não. Resposta padrão no segundo argumento (s ou n).
# Sem terminal interativo, assume o padrão.
confirmar() {
  local pergunta="$1" padrao="${2:-n}" resposta opcoes="[s/N]"
  [[ "$padrao" == "s" ]] && opcoes="[S/n]"
  if [[ ! -t 0 ]] || simulando; then
    [[ "$padrao" == "s" ]]
    return
  fi
  read -r -p "$pergunta $opcoes " resposta
  resposta="${resposta:-$padrao}"
  [[ "${resposta,,}" == s* ]]
}

# Cria cópia de segurança com data ao lado do arquivo, se ele existir.
copia_seguranca() {
  local arquivo="$1" destino
  [[ -e "$arquivo" ]] || return 0
  destino="$arquivo.jangada-$(date +%Y%m%d-%H%M%S).bak"
  if [[ -w "$(dirname "$arquivo")" ]]; then
    executar cp -a "$arquivo" "$destino"
  else
    como_root cp -a "$arquivo" "$destino"
  fi
  info "cópia de segurança: $destino"
}

# Copia um arquivo modelo para o destino apenas se o destino ainda não existe.
copiar_se_ausente() {
  local origem="$1" destino="$2"
  if [[ -e "$destino" ]]; then
    ok "mantido (já existe): $destino"
    return 0
  fi
  executar mkdir -p "$(dirname "$destino")"
  executar cp "$origem" "$destino"
  ok "criado: $destino"
}

# Lê uma lista de pacotes, ignorando comentários e linhas vazias.
ler_lista() {
  sed -e 's/#.*//' -e 's/[[:space:]]*$//' "$1" | awk 'NF'
}

# Detecta o ajudante do AUR disponível (paru ou yay).
ajudante_aur() {
  if tem_comando paru; then echo paru
  elif tem_comando yay; then echo yay
  fi
}

# Instala pacotes: os que existem nos repositórios oficiais vão pelo pacman,
# os demais pelo ajudante do AUR. Pacotes já instalados são ignorados.
# Pacotes que não existem em lugar nenhum são listados, sem interromper.
instalar_pacotes() {
  local -a oficiais=() aur=() ausentes=()
  local pacote aur_cmd
  aur_cmd="$(ajudante_aur)"

  for pacote in "$@"; do
    if pacman -Qq "$pacote" >/dev/null 2>&1; then
      continue
    elif pacman -Si "$pacote" >/dev/null 2>&1; then
      oficiais+=("$pacote")
    elif [[ -n "$aur_cmd" ]] && "$aur_cmd" -Si "$pacote" >/dev/null 2>&1; then
      aur+=("$pacote")
    else
      ausentes+=("$pacote")
    fi
  done

  if ((${#oficiais[@]})); then
    info "pacman: ${oficiais[*]}"
    como_root pacman -S --needed --noconfirm "${oficiais[@]}"
  fi
  if ((${#aur[@]})); then
    info "AUR ($aur_cmd): ${aur[*]}"
    executar "$aur_cmd" -S --needed "${aur[@]}"
  fi
  if ((${#ausentes[@]})); then
    aviso "não encontrados nos repositórios nem no AUR: ${ausentes[*]}"
    aviso "confira os nomes em install/pacotes/ e instale manualmente se necessário"
  fi
  return 0
}

# Sistema de arquivos da raiz.
fs_raiz() { findmnt -no FSTYPE / 2>/dev/null; }

# Carregador de boot detectado: limine, grub, systemd-boot ou desconhecido.
carregador_boot() {
  if [[ -f /boot/limine.conf || -f /boot/limine/limine.conf || -f /boot/EFI/limine/limine.conf ]] \
     || pacman -Qq limine >/dev/null 2>&1; then
    echo limine
  elif [[ -f /boot/grub/grub.cfg ]] || pacman -Qq grub >/dev/null 2>&1; then
    echo grub
  elif [[ -d /boot/loader/entries || -d /efi/loader/entries \
          || -d /boot/EFI/systemd || -d /efi/EFI/systemd ]] \
     || { tem_comando bootctl && bootctl is-installed >/dev/null 2>&1; }; then
    # O bootctl precisa de root para abrir a partição EFI e responde
    # "Permission denied" para usuário comum, por isso o teste no sistema
    # de arquivos vem antes.
    echo systemd-boot
  else
    echo desconhecido
  fi
}

# Liga a skill do jangada em ~/.claude/skills/jangada, apontando para o
# repositório instalado: o jangada-update a atualiza junto com o resto. Um link
# antigo do jangada (outro JANGADA_PATH) é trocado; uma pasta ou link alheio
# com o mesmo nome fica como está, com aviso.
ligar_skill_claude() {
  local origem="$JANGADA_PATH/default/claude/skills/jangada"
  local destino="$HOME/.claude/skills/jangada" atual
  [[ -f "$origem/SKILL.md" ]] || { aviso "skill não encontrada em $origem"; return 0; }
  if [[ -L "$destino" ]]; then
    atual="$(readlink "$destino")"
    if [[ "$atual" == "$origem" ]]; then
      ok "skill do Claude Code já ligada: $destino"
      return 0
    fi
    if [[ "$atual" != */default/claude/skills/jangada ]]; then
      aviso "$destino aponta para $atual, que não é do jangada; mantido"
      return 0
    fi
  elif [[ -e "$destino" ]]; then
    aviso "$destino já existe e não é um link do jangada; mantido"
    return 0
  fi
  executar mkdir -p "$(dirname "$destino")"
  executar ln -sfn "$origem" "$destino"
  ok "skill do Claude Code ligada: $destino -> $origem"
}
