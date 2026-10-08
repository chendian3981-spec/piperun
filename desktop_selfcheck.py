# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Offline dependency/support check. No account reads, network, CA installs or OS proxy writes."""
import contextlib
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from desktop_storage import atomic_json
from desktop_version import BUILD, UI_ENTRY
from lepao._buildstamp import BUILD_ID


class MemoryProxyBackend:
    def __init__(self):
        self.values = {"ProxyEnable": [4, 0], "ProxyServer": [1, "unused-synthetic:8"]}

    def read(self, name):
        return self.values.get(name)

    def write(self, name, value):
        if value is None:
            self.values.pop(name, None)
        else:
            self.values[name] = value

    def notify(self):
        pass


def run():
    report = {"schema": 1, "client": BUILD, "ok": False,
              "license": {"build_id": BUILD_ID}, "checks": {},
              "scope": "offline dependencies, source QML linking and synthetic proxy journal only",
              "real_requests": 0, "system_proxy_writes": 0, "certificate_installs": 0,
              "live_business_tested": False}
    checks = report["checks"]
    try:
        from Crypto.Cipher import AES
        import brotli
        from lepao.transport import decode_body
        plain, key, iv = bytes(32), bytes(16), bytes(16)
        encrypted = AES.new(key, AES.MODE_CBC, iv).encrypt(plain)
        assert AES.new(key, AES.MODE_CBC, iv).decrypt(encrypted) == plain
        assert decode_body(brotli.compress(plain), "br") == plain
        checks["crypto_and_compression"] = True
        bundle = Path(__file__).resolve().parent
        manifest = json.loads((bundle / "release.manifest.json").read_text(encoding="utf-8"))
        for name in ("LICENSE", "NOTICE", "DISCLAIMER.md"):
            assert hashlib.sha256((bundle / name).read_bytes()).hexdigest() == manifest["sha256"][name]
        for name in ("data/真实轨迹_035明文.json", "assets/pipeRun.ico",
                     "third_party/desktop/fonts/fusion-pixel-10px-monospaced-zh_hans.otf"):
            assert (bundle / name).is_file()
        checks["notices_template_icon_font"] = True
        with tempfile.TemporaryDirectory(prefix="piperun-offline-") as temporary:
            from desktop_win import ProxyGuard
            backend = MemoryProxyBackend()
            original = dict(backend.values)
            guard = ProxyGuard(Path(temporary), backend, contextlib.nullcontext)
            guard.activate(8877, owner_pid=123)
            assert guard.recover(owner_pid=124) == "other-owner"
            assert guard.recover(owner_pid=123) == "restored"
            assert backend.values == original
        checks["synthetic_proxy_recovery_ownership"] = True
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PySide6.QtCore import QUrl
        from PySide6.QtGui import QGuiApplication, QFontDatabase, QIcon
        from PySide6.QtQml import QQmlEngine, QQmlComponent
        application = QGuiApplication.instance() or QGuiApplication([])
        engine = QQmlEngine()
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(bundle / "desktop_ui" / UI_ENTRY)))
        assert component.status() == QQmlComponent.Status.Ready
        font = bundle / "third_party/desktop/fonts/fusion-pixel-10px-monospaced-zh_hans.otf"
        assert QFontDatabase.addApplicationFont(str(font)) >= 0
        assert not QIcon(str(bundle / "assets/pipeRun.ico")).isNull()
        checks["qt_qml_link_font_icon"] = True
        if getattr(sys, "frozen", False):
            import PySide6
            assert Path(PySide6.__file__).resolve().is_relative_to(bundle)
            names = {p.name.lower() for p in bundle.rglob("*.dll")}
            assert {"qt6core.dll", "qt6gui.dll", "qt6qml.dll", "qt6quick.dll", "qwindows.dll"} <= names
            checks["bundled_qt_runtime"] = True
        report["ok"] = True
    except Exception as exc:
        report["error"] = type(exc).__name__
    destination = Path(os.environ.get("LEPAO_RUNNER_DIR", Path.cwd()))
    destination.mkdir(parents=True, exist_ok=True)
    atomic_json(destination / "selfcheck.json", report)
    return 0 if report["ok"] else 1
