# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Collect only the local QML application's dependency graph, not unrelated Qt modules."""
import json
import subprocess
from pathlib import Path

import PySide6
from PySide6.QtCore import QLibraryInfo
from PyInstaller.utils.hooks.qt import add_qt6_dependencies, pyside6_library_info

hiddenimports, binaries, datas = add_qt6_dependencies(__file__)
binaries = [(source, target) for source, target in binaries if "/qmltooling/" not in source.replace("\\", "/")]
root = Path(__file__).resolve().parents[2]
source = Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.QmlImportsPath)).resolve()
scanner = Path(PySide6.__file__).parent / "qmlimportscanner.exe"
modules = json.loads(subprocess.check_output([str(scanner), "-rootPath", str(root / "desktop_ui"),
                                             "-importPath", str(source)], text=True, encoding="utf-8"))
seen = set()
for module in modules:
    if not module.get("path"):
        continue
    path = Path(module["path"]).resolve()
    if not path.is_relative_to(source) or path in seen or not (path / "qmldir").is_file():
        continue
    seen.add(path)
    plugin_binaries, plugin_datas = pyside6_library_info._process_qml_plugin(path / "qmldir")
    for entries, destination in ((plugin_binaries, binaries), (plugin_datas, datas)):
        destination.extend((str(file), str(Path(pyside6_library_info.qt_rel_dir) / "qml" / file.relative_to(source).parent))
                           for file in entries)
if not {"QtQuick", "QtQuick/Controls/Basic", "QtQuick/Layouts"} <= {x.relative_to(source).as_posix() for x in seen}:
    raise RuntimeError("Required local QML modules were not discovered")
