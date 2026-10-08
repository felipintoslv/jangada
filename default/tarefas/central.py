"""Entrada da central e reutilização da janela por soquete privado."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import socket as unix
import stat
import subprocess
import sys
import time

from dados import barra


def encaminhar(nome, nova=False):
    from PyQt6.QtCore import QCoreApplication
    from PyQt6.QtNetwork import QLocalSocket

    socket = QLocalSocket()
    socket.connectToServer(nome)
    if not socket.waitForConnected(500):
        return False
    socket.write(b'nova\n' if nova else b'mostrar\n')
    if not socket.waitForBytesWritten(500):
        return False
    prazo = time.monotonic() + 1
    while time.monotonic() < prazo:
        QCoreApplication.processEvents()
        if socket.bytesAvailable() or socket.waitForReadyRead(20):
            return bytes(socket.readAll()) == b'ok\n'
    return False


def receber(servidor, janela):
    from PyQt6.QtCore import QProcess

    while servidor.hasPendingConnections():
        socket = servidor.nextPendingConnection()
        buffer = bytearray()

        def ler(socket=socket, buffer=buffer):
            buffer.extend(bytes(socket.readAll()))
            if len(buffer) > 32:
                socket.disconnectFromServer()
                return
            if b'\n' not in buffer:
                return
            pedido = bytes(buffer).split(b'\n', 1)[0]
            if pedido not in (b'mostrar', b'nova'):
                socket.disconnectFromServer()
                return
            janela.showNormal()
            janela.raise_()
            janela.activateWindow()
            if os.environ.get('HYPRLAND_INSTANCE_SIGNATURE'):
                QProcess.startDetached('hyprctl', ['dispatch', 'focuswindow', f'pid:{os.getpid()}'])
            if pedido == b'nova':
                janela.nova_tarefa()
            socket.write(b'ok\n')
            socket.flush()
            socket.disconnectFromServer()

        socket.readyRead.connect(ler)
        socket.disconnected.connect(socket.deleteLater)
        if socket.bytesAvailable():
            ler()


def nome_soquete(jangada, estado, real):
    runtime = os.environ.get('XDG_RUNTIME_DIR')
    if not runtime or not Path(runtime).is_absolute():
        raise ValueError('XDG_RUNTIME_DIR deve indicar a pasta da sessão gráfica.')
    pasta = Path(runtime) / 'jangada-tarefas'
    pasta.mkdir(mode=0o700, exist_ok=True)
    dados = pasta.lstat()
    if not stat.S_ISDIR(dados.st_mode) or dados.st_uid != os.getuid() or dados.st_mode & 0o077:
        raise ValueError('A pasta do soquete deve pertencer ao usuário e ter permissão 0700.')
    identidade = f'{Path(__file__).resolve()}:{real}:{jangada}:{estado}'
    return str(pasta / hashlib.sha256(identidade.encode()).hexdigest()[:24])


def remover_soquete_morto(nome):
    try:
        dados = Path(nome).lstat()
    except FileNotFoundError:
        return
    if not stat.S_ISSOCK(dados.st_mode) or dados.st_uid != os.getuid():
        raise ValueError('O caminho do soquete está ocupado por outro arquivo.')
    with unix.socket(unix.AF_UNIX) as teste:
        teste.settimeout(0.5)
        try:
            teste.connect(nome)
        except ConnectionRefusedError:
            Path(nome).unlink()
            return
    raise ValueError('A central existente não confirmou o pedido.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--real', action='store_true')
    parser.add_argument('--jangada', type=Path)
    parser.add_argument('--estado', type=Path)
    parser.add_argument('--waybar', action='store_true')
    parser.add_argument('--mostrar', action='store_true')
    parser.add_argument('--nova', action='store_true')
    args = parser.parse_args()
    if args.waybar:
        print(json.dumps(barra(args), ensure_ascii=False))
        return
    try:
        from PyQt6.QtCore import QCoreApplication
        from PyQt6.QtNetwork import QLocalServer
        if args.mostrar:
            app = QCoreApplication(sys.argv[:1])
        else:
            from PyQt6.QtWidgets import QApplication
            app = QApplication(sys.argv[:1])
        jangada = Path(args.jangada or Path.home() / '.local/share/jangada').expanduser().resolve()
        estado = Path(args.estado or Path(os.environ.get('XDG_STATE_HOME', str(Path.home() / '.local/state'))) / 'jangada/agentes').expanduser().resolve()
        nome = nome_soquete(jangada, estado, args.real)
        if encaminhar(nome, args.nova):
            return
        remover_soquete_morto(nome)
        if args.mostrar:
            argumentos = [a for a in sys.argv[1:] if a != '--mostrar']
            subprocess.Popen([sys.executable, str(Path(__file__).resolve()), *argumentos],
                             start_new_session=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return
        servidor = QLocalServer(app)
        servidor.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
        if not servidor.listen(nome):
            if encaminhar(nome, args.nova):
                return
            raise ValueError('Não foi possível abrir o soquete da central.')
        from janela import Janela
        app.setApplicationName('org.jangada.tarefas')
        app.setDesktopFileName('org.jangada.tarefas')
        janela = Janela(args.real, jangada, estado)
        servidor.newConnection.connect(lambda: receber(servidor, janela))
        janela.show()
        if args.nova:
            janela.nova_tarefa()
        sys.exit(app.exec())
    except ImportError as erro:
        if (erro.name or '').startswith('PyQt6') or 'Qt6Svg' in str(erro):
            parser.exit(1, 'Central de tarefas: instale python-pyqt6 e qt6-svg.\n')
        parser.exit(1, f'Central de tarefas: falha ao importar {erro.name}: {erro}\n')
    except (OSError, ValueError) as erro:
        parser.exit(1, f'Central de tarefas: {erro}\n')


if __name__ == '__main__':
    main()
