# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Build only the current Windows client and its allowlisted source/release ZIPs."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from desktop_version import VERSION, BUILD, UI_ENTRY

NOTICES = ("LICENSE", "LICENSE.md", "NOTICE", "DISCLAIMER.md", "SECURITY.md", "CONTRIBUTING.md",
           "README.md", "RELEASING.md", "release.manifest.json", "release.meta.json")

def source_files():
    names = set(NOTICES) | {"requirements-desktop.txt", ".gitignore", "SOURCE_SNAPSHOT.json",
                            "tools/desktop_diagnose.cmd", "tools/desktop_quickstart.txt",
                            "data/真实轨迹_035明文.json"}
    for pattern in ("desktop_*.py", "lepao/*.py", "desktop_ui/Retro*.qml", "assets/*",
                    "third_party/desktop/**/*", "tools/*.py", "tools/hooks/*.py", "tests/*.py"):
        names.update(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern)
                     if p.is_file() and "__pycache__" not in p.parts)
    files = [(ROOT / name, name) for name in sorted(names)]
    if any(not p.is_file() or p.is_symlink() for p, _ in files):
        raise RuntimeError("Missing or indirect build/source input")
    return files

def dependency_notices():
    files = [(Path(sys.base_prefix) / "LICENSE.txt", "third_party/desktop/python/LICENSE.txt")]
    files += [(p, p.relative_to(ROOT).as_posix()) for p in (ROOT / "third_party/desktop").rglob("*") if p.is_file()]
    for package in ("pycryptodome", "cffi", "pycparser", "brotli", "setuptools", "packaging",
                    "typing_extensions", "altgraph", "pefile", "pywin32-ctypes", "pyinstaller",
                    "pyinstaller-hooks-contrib", "PySide6-Essentials", "shiboken6"):
        dist = metadata.distribution(package)
        for entry in dist.files or ():
            name = Path(str(entry)).name.lower()
            if name.startswith(("license", "copying", "authors")) and Path(str(entry)).suffix.lower() not in (".py", ".pyc"):
                p = Path(dist.locate_file(entry))
                if p.is_file():
                    files.append((p, "third_party/desktop/" + package + "/" + str(entry).replace("\\", "/")))
    if any(not p.is_file() for p, _ in files):
        raise RuntimeError("Missing dependency license")
    return files

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-selfcheck", action="store_true", help="Build only; leave offline acceptance marked not_run.")
    parser.add_argument("--output", type=Path, default=ROOT / "release", help="Output directory (default: release).")
    options = parser.parse_args()
    inputs = source_files()
    for tool, extra in (("apply_headers.py", ["--check"]), ("verify_release.py", []),
                        ("check_snapshot.py", []), ("check_qml_load.py", [])):
        subprocess.run([sys.executable, "-B", "-X", "utf8", "tools/" + tool, *extra], cwd=ROOT, check=True)
    output = options.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    args = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--clean", "--onefile", "--windowed",
            "--name", "pipeRun", "--icon", str(ROOT / "assets/pipeRun.ico"),
            "--distpath", str(output), "--workpath", str(ROOT / "build/desktop"),
            "--specpath", str(ROOT / "build/desktop"), "--additional-hooks-dir", str(ROOT / "tools/hooks"),
            "--hidden-import", "desktop_gui", "--hidden-import", "desktop_selfcheck",
            "--hidden-import", "lepao._buildstamp"]
    for name in (*NOTICES, "assets/pipeRun.ico", "assets/pipeRun.png", "data/真实轨迹_035明文.json"):
        p = ROOT / name
        args += ["--add-data", str(p) + os.pathsep + str(Path(name).parent)]
    for p in sorted((ROOT / "desktop_ui").glob("Retro*.qml")):
        args += ["--add-data", str(p) + os.pathsep + "desktop_ui"]
    licenses = dependency_notices()
    for p, target in licenses:
        args += ["--add-data", str(p) + os.pathsep + str(Path(target).parent)]
    env = dict(os.environ, PATH=os.pathsep.join((sys.base_prefix, str(Path(sys.base_prefix) / "Scripts"),
                                               str(Path(os.environ["SystemRoot"]) / "System32"))))
    subprocess.run([*args, "desktop_app.py"], cwd=ROOT, env=env, check=True)
    exe = output / "pipeRun.exe"
    report = {"schema": 1, "status": "not_run", "ok": None,
              "scope": "Build/link only; no frozen runtime or real business acceptance.",
              "real_requests": 0, "system_proxy_writes": 0, "certificate_installs": 0}
    if not options.skip_selfcheck:
        with tempfile.TemporaryDirectory(prefix="piperun-frozen-") as directory:
            portable = Path(directory) / "中文 空目录"
            portable.mkdir()
            standalone = portable / "pipeRun.exe"
            shutil.copy2(exe, standalone)
            env = dict(os.environ, LEPAO_RUNNER_DIR=directory, LOCALAPPDATA=str(Path(directory) / "fresh-user"),
                       PATH=str(Path(os.environ["SystemRoot"]) / "System32"))
            for key in ("PYTHONHOME", "PYTHONPATH", "QT_PLUGIN_PATH", "QML_IMPORT_PATH", "QML2_IMPORT_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH"):
                env.pop(key, None)
            subprocess.run([str(standalone), "--selfcheck"], cwd=portable, env=env, check=True, timeout=45)
            report = json.loads((Path(directory) / "selfcheck.json").read_text(encoding="utf-8"))
            if not report.get("ok"):
                raise RuntimeError("Offline frozen check failed")
    metadata_out = {"schema": 1, "client": BUILD, "desktop_only": True, "ui_entry": UI_ENTRY,
                    "os": "Windows 10/11 x64", "python": sys.version.split()[0],
                    "runtime_downloads": False, "android_included": False, "legacy_ui_included": False,
                    "window_title": "pipeRun " + VERSION + " · 测试版",
                    "exe_sha256": hashlib.sha256(exe.read_bytes()).hexdigest(),
                    "offline_selfcheck_passed": report.get("ok"),
                    "clean_windows_vm_tested": False, "live_submit_tested": False}
    for name, value in (("desktop-build.json", metadata_out), ("offline-selfcheck.json", report)):
        (output / name).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    source_zip = output / "piperunv1.0-source.zip"
    with zipfile.ZipFile(source_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        for p, name in inputs:
            archive.write(p, "piperunv1.0/" + name)
    release_zip = output / ("pipeRun-desktop-" + VERSION + ".zip")
    with zipfile.ZipFile(release_zip, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(exe, "pipeRun/pipeRun.exe")
        for name in (*NOTICES, "desktop-build.json", "offline-selfcheck.json"):
            p = output / name if name.endswith("build.json") or name == "offline-selfcheck.json" else ROOT / name
            archive.write(p, "pipeRun/" + name)
        archive.write(ROOT / "tools/desktop_diagnose.cmd", "pipeRun/diagnose.cmd")
        archive.write(ROOT / "tools/desktop_quickstart.txt", "pipeRun/START-HERE.txt")
        for p, name in licenses:
            archive.write(p, "pipeRun/" + name)
        for p, name in inputs:
            archive.write(p, "pipeRun/source/" + name)
    items = (exe, release_zip, source_zip, output / "desktop-build.json", output / "offline-selfcheck.json")
    (output / "SHA256SUMS.txt").write_text("".join(hashlib.sha256(p.read_bytes()).hexdigest() + "  " + p.name + "\n" for p in items), encoding="utf-8")
    for package in (source_zip, release_zip):
        subprocess.run([sys.executable, "-B", "tools/verify_release.py", "--zip", str(package)], cwd=ROOT, check=True)
    print("EXE:", exe)
    print("ZIP:", release_zip)
    print("SOURCE:", source_zip)
    print("SHA256:", metadata_out["exe_sha256"])

if __name__ == "__main__":
    main()
