#!/usr/bin/env bash
# Instalação e configuração da camada de agentes do jangada no macOS.
#
# Uso:
#   ./install-macos.sh                   instala dependências e configura o ambiente
#   JANGADA_SIMULAR=1 ./install-macos.sh mostra o que seria feito, sem executar
set -euo pipefail

JANGADA_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
export JANGADA_PATH
# shellcheck source=install/lib.sh
source "$JANGADA_PATH/install/lib.sh"

[[ "$(uname -s)" == "Darwin" ]] || {
  aviso "este script foi preparado para macOS."
  aviso "no Arch Linux, utilize ./install.sh para a instalação completa."
  if ! simulando; then
    exit 1
  fi
}

simulando && aviso "modo simulação: nenhum comando será executado"

# 1. Verificação do Homebrew
if ! tem_comando brew; then
  aviso "o gerenciador de pacotes Homebrew não foi encontrado."
  info "instale o Homebrew executando no terminal:"
  echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  morrer "instale o Homebrew e execute este instalador novamente"
fi

# Garante Homebrew no PATH caso ainda não esteja na sessão atual
if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

# 2. Instalação de pacotes necessários
info "verificando dependências no Homebrew..."
pacotes_necessarios=(bash tmux fzf jq coreutils)
pacotes_para_instalar=()

for p in "${pacotes_necessarios[@]}"; do
  if ! brew list "$p" >/dev/null 2>&1; then
    pacotes_para_instalar+=("$p")
  fi
done

if ((${#pacotes_para_instalar[@]})); then
  info "instalando via brew: ${pacotes_para_instalar[*]}"
  executar brew install "${pacotes_para_instalar[@]}"
else
  ok "todas as ferramentas básicas já estão instaladas via brew"
fi

# 3. Pastas do jangada
info "preparando diretórios do usuário..."
executar mkdir -p "$JANGADA_CONFIG/agentes"
executar mkdir -p "$JANGADA_ESTADO/agentes"
executar mkdir -p "$HOME/.local/share/jangada-worktrees"
executar mkdir -p "$HOME/Projetos"

# 4. Arquivos de configuração padrão
info "configurando preferências..."
copiar_se_ausente "$JANGADA_PATH/config/jangada.conf" "$JANGADA_CONFIG/jangada.conf"

for perfil_padrao in "$JANGADA_PATH"/default/agentes/*.conf; do
  [[ -f "$perfil_padrao" ]] || continue
  nome_perfil="$(basename "$perfil_padrao")"
  copiar_se_ausente "$perfil_padrao" "$JANGADA_CONFIG/agentes/$nome_perfil"
done

# 5. Integração com a shell do usuário (zsh como padrão no macOS)
rc_usuario="$HOME/.zshrc"
[[ ! -f "$rc_usuario" && -f "$HOME/.bashrc" ]] && rc_usuario="$HOME/.bashrc"

info "configurando shell em $rc_usuario..."
bloco_inicio="# === Jangada Agentes (início) ==="
bloco_fim="# === Jangada Agentes (fim) ==="

if [[ -f "$rc_usuario" ]] && grep -qF "$bloco_inicio" "$rc_usuario"; then
  ok "shell já possui integração com o jangada"
else
  copia_seguranca "$rc_usuario"
  if simulando; then
    info "[simulação] adicionaria variáveis e funções do jangada a $rc_usuario"
  else
    {
      printf '\n%s\n' "$bloco_inicio"
      if [[ -d /opt/homebrew/bin ]]; then
        printf 'eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null)"\n'
      elif [[ -d /usr/local/bin ]]; then
        printf 'eval "$(/usr/local/bin/brew shellenv 2>/dev/null)"\n'
      fi
      printf 'export PATH="%s/bin:$PATH"\n' "$JANGADA_PATH"
      printf '[ -f "%s/shell/jangada-shell.sh" ] && source "%s/shell/jangada-shell.sh"\n' "$JANGADA_PATH" "$JANGADA_PATH"
      printf '%s\n' "$bloco_fim"
    } >>"$rc_usuario"
    ok "integração adicionada a $rc_usuario"
  fi
fi

# 6. Hooks e skills de agentes
if tem_comando claude || [[ -d "$HOME/.claude" ]]; then
  info "configurando Claude Code..."
  mesclar_hooks_claude
  ligar_skill_claude
fi

if tem_comando agy || [[ -d "$HOME/.gemini" ]]; then
  info "configurando Antigravity (agy)..."
  mesclar_hooks_agy
fi

# 7. Atalho para Raycast
pasta_raycast="$HOME/.config/raycast/commands"
executar mkdir -p "$pasta_raycast"
script_raycast="$pasta_raycast/novo-agente.sh"
if [[ ! -f "$script_raycast" ]]; then
  if simulando; then
    info "[simulação] criaria comando do Raycast em $script_raycast"
  else
    cat <<'EOF' >"$script_raycast"
#!/usr/bin/env bash
# Required parameters:
# @raycast.schemaVersion 1
# @raycast.title Novo Agente
# @raycast.mode silent
#
# Optional parameters:
# @raycast.icon 🤖
# @raycast.packageName Jangada
#
# Documentation:
# @raycast.description Abre uma nova sessão de agente do Jangada
# @raycast.author Jangada

if [[ -x /opt/homebrew/bin/brew ]]; then
  eval "$(/opt/homebrew/bin/brew shellenv)"
elif [[ -x /usr/local/bin/brew ]]; then
  eval "$(/usr/local/bin/brew shellenv)"
fi

JANGADA_DIR="${JANGADA_PATH:-$HOME/.local/share/jangada}"
export PATH="$JANGADA_DIR/bin:$PATH"

jangada-agente --janela
EOF
    chmod +x "$script_raycast"
    ok "comando do Raycast criado em $script_raycast"
  fi
fi

# 8. Criar aplicativo macOS clicável (Spotlight e Dock) via osascript
if tem_comando osacompile; then
  pasta_apps="$HOME/Applications"
  executar mkdir -p "$pasta_apps"
  app_agente="$pasta_apps/Novo Agente.app"
  if [[ ! -e "$app_agente" ]]; then
    if simulando; then
      info "[simulação] compilaria aplicativo $app_agente"
    else
      osacompile -e 'do shell script "PATH=/opt/homebrew/bin:/usr/local/bin:$PATH '"$JANGADA_PATH"'/bin/jangada-agente --janela >/dev/null 2>&1 &"' -o "$app_agente" 2>/dev/null || true
      if [[ -e "$app_agente" ]]; then
        ok "aplicativo criado: $app_agente (disponível no Spotlight e Dock)"
      fi
    fi
  fi
fi

ok "instalação no macOS concluída com sucesso"
info "recarregue seu terminal com: source $rc_usuario"
info "ou execute diretamente: jangada-agente"
