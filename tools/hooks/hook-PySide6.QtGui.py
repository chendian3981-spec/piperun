# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Keep Windows platforms and basic icon codecs; no unused PDF/virtual keyboard plugins."""
from PyInstaller.utils.hooks.qt import add_qt6_dependencies

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
allowed = {"qwindows.dll", "qminimal.dll", "qoffscreen.dll", "qgif.dll", "qico.dll", "qjpeg.dll", "qsvg.dll", "qsvgicon.dll"}
binaries = [(source, target) for source, target in binaries
            if "/plugins/" not in source.replace("\\", "/") or source.replace("\\", "/").split("/")[-1].lower() in allowed]
