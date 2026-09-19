# shellcheck shell=bash
# Etapa 20: snapshots automáticos com snapper e snap-pac, só em raiz btrfs.
# Retenção curta (5 snapshots numerados, sem linha do tempo), como no Omarchy.

if [[ "$(fs_raiz)" != "btrfs" ]]; then
  aviso "raiz não é btrfs; snapshots não serão configurados"
  aviso "sem snapshots, a proteção contra quebras fica limitada ao git dos dotfiles"
else
  mapfile -t _pacotes < <(ler_lista "$JANGADA_PATH/install/pacotes/snapshots.txt")
  case "$(carregador_boot)" in
    limine)  _pacotes+=(limine-snapper-sync) ;;
    grub)    _pacotes+=(grub-btrfs) ;;
    *)       aviso "carregador $(carregador_boot): não haverá entrada de boot para snapshots; a restauração será feita por live USB" ;;
  esac
  instalar_pacotes "${_pacotes[@]}"
  unset _pacotes

  if [[ -f /etc/snapper/configs/root ]]; then
    ok "snapper já configurado para /"
  else
    # Em instalações feitas com archinstall, /.snapshots costuma já existir como
    # subvolume montado. O snapper se recusa a criar a configuração nesse caso,
    # então o procedimento padrão é desmontar, deixar o snapper criar e depois
    # trocar o subvolume criado pelo que já existia.
    if mountpoint -q /.snapshots 2>/dev/null; then
      info "/.snapshots já é um subvolume montado; aplicando o procedimento padrão"
      como_root umount /.snapshots
      como_root rmdir /.snapshots
      como_root snapper -c root create-config /
      como_root btrfs subvolume delete /.snapshots
      como_root mkdir /.snapshots
      como_root mount -a
      como_root chmod 750 /.snapshots
    else
      # Uma pasta /.snapshots vazia e não montada também impede o snapper.
      # Só é removida se estiver vazia; com conteúdo, a instalação para.
      if [[ -e /.snapshots ]]; then
        como_root rmdir /.snapshots \
          || morrer "/.snapshots existe, não está montado e não está vazio; confira com 'sudo btrfs subvolume list /' antes de seguir"
      fi
      como_root snapper -c root create-config /
    fi
  fi

  copia_seguranca /etc/snapper/configs/root
  como_root install -m 0644 "$JANGADA_PATH/default/snapper/root" /etc/snapper/configs/root
  como_root systemctl disable --now snapper-timeline.timer || true
  como_root systemctl enable --now snapper-cleanup.timer

  case "$(carregador_boot)" in
    limine) como_root systemctl enable --now limine-snapper-sync.service || aviso "limine-snapper-sync não habilitado" ;;
    grub)   como_root systemctl enable --now grub-btrfsd.service || aviso "grub-btrfsd não habilitado" ;;
  esac
  ok "snapshots configurados; snap-pac cria um par antes e depois de cada pacman"
fi
