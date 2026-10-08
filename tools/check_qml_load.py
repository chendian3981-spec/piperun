# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Compile/link QML types only: no component.create(), window, controller or private data."""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    os.environ["QT_QPA_PLATFORM"] = "offscreen"
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlComponent, QQmlEngine
    sys.path.insert(0, str(ROOT))
    from desktop_version import UI_ENTRY
    application = QGuiApplication([])
    engine = QQmlEngine()
    names = (UI_ENTRY, "RetroButton.qml", "RetroPalette.qml", "RetroCube.qml", "RetroWordmark.qml", "RetroStars.qml", "RetroStatusMark.qml", "RetroTypewriter.qml", "RetroLogLine.qml")
    for name in names:
        component = QQmlComponent(engine, QUrl.fromLocalFile(str(ROOT / "desktop_ui" / name)))
        if component.status() != QQmlComponent.Status.Ready:
            for error in component.errors():
                print(error.toString(), file=sys.stderr)
            raise RuntimeError("QML component could not be loaded: " + name)
    print("QML component load/link OK; no components instantiated, no windows or business operations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
