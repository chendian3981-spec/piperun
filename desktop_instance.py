# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Current-user, activation-only named pipe. No business commands or TCP listener."""
import ctypes
import hashlib
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer
from PySide6.QtNetwork import QLocalServer, QLocalSocket

ACTIVATE = b"activate\n"


def endpoint(directory):
    digest = hashlib.sha256(str(Path(directory).resolve()).casefold().encode("utf-8")).hexdigest()[:32]
    return "pipeRun-window-" + digest


def activate_existing(directory):
    application = QCoreApplication.instance() or QCoreApplication([])
    socket = QLocalSocket()
    try:
        socket.connectToServer(endpoint(directory))
        if not socket.waitForConnected(400):
            return False
        application.processEvents()
        socket.write(ACTIVATE)
        socket.flush()
        if socket.bytesToWrite() and not socket.waitForBytesWritten(400) and socket.bytesToWrite():
            return False
        return True
    finally:
        socket.disconnectFromServer()
        # Keep the local application alive through the bounded client operation.
        _ = application


def notify_already_open():
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")
    user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    user32.MessageBoxW.restype = ctypes.c_int
    user32.MessageBoxW(None, "pipeRun 已经打开或正在启动。\n请从任务栏回到原来的窗口，无需再次打开。\n不会重复获取账号或提交。",
                      "pipeRun · 已经打开", 0x40)


def serve_activation(directory, window, model):
    server = QLocalServer(model)
    server.setSocketOptions(QLocalServer.SocketOption.UserAccessOption)
    server.setMaxPendingConnections(8)
    if not server.listen(endpoint(directory)):
        return server  # Ordinary startup still works; duplicate launch gets the soft fallback.

    def accept():
        while server.hasPendingConnections():
            socket = server.nextPendingConnection()
            socket.setReadBufferSize(32)
            timeout = QTimer(socket)
            timeout.setSingleShot(True)
            timeout.timeout.connect(lambda sock=socket: sock.abort())
            timeout.start(800)
            buffer = bytearray()

            def receive(sock=socket, data=buffer, timer=timeout):
                data.extend(bytes(sock.read(32)))
                if len(data) > len(ACTIVATE) or not ACTIVATE.startswith(data):
                    sock.abort()
                    return
                if bytes(data) == ACTIVATE:
                    timer.stop()
                    # Only window visibility/notification; never routes through Controller.action.
                    from PySide6.QtGui import QWindow
                    if window.visibility() == QWindow.Visibility.Minimized:
                        window.showNormal()
                    else:
                        window.show()
                    window.raise_()
                    window.requestActivate()
                    window.alert(1500)
                    model.reopened.emit()
                    sock.disconnectFromServer()
            socket.readyRead.connect(receive)
            socket.disconnected.connect(socket.deleteLater)
            receive()
    server.newConnection.connect(accept)
    return server
