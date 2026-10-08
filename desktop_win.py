# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""pipeRun Windows additions: consented proxy transactions, no global process kills."""
import contextlib
import ctypes
import hashlib
import json
import os
import ssl
import subprocess
import time
from pathlib import Path

from desktop_storage import atomic_json

PROXY_NAMES = ("ProxyEnable", "ProxyServer", "ProxyOverride")


class ProxyProblem(ValueError):
    """Catalog-only failure; never expose network addresses or recovery contents."""
    def __init__(self, code, reason):
        self.code, self.proxy_reason = code, reason
        super().__init__(code)


class FileLockBusy(RuntimeError):
    """A held lock, distinct from disk/permission/other startup failures."""


class FileLock:
    """A per-user file lock released by Windows even after process termination."""
    def __init__(self, path, timeout=3):
        self.path, self.timeout, self.file = Path(path), timeout, None

    def __enter__(self):
        import msvcrt
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.file = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self.file.write(b"0")
            self.file.flush()
        deadline = time.monotonic() + self.timeout
        while True:
            self.file.seek(0)
            try:
                msvcrt.locking(self.file.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                if time.monotonic() >= deadline:
                    self.file.close()
                    self.file = None
                    raise FileLockBusy("pipeRun 已在运行，或网络设置正在恢复，请稍后重试")
                time.sleep(0.03)

    def __exit__(self, *args):
        import msvcrt
        if self.file:
            self.file.seek(0)
            msvcrt.locking(self.file.fileno(), msvcrt.LK_UNLCK, 1)
            self.file.close()
            self.file = None


class WindowsProxyBackend:
    path = r"Software\Microsoft\Windows\CurrentVersion\Internet Settings"

    def read(self, name):
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.path) as key:
            try:
                value, kind = winreg.QueryValueEx(key, name)
                return [kind, value]
            except FileNotFoundError:
                return None

    def write(self, name, entry):
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.path, 0, winreg.KEY_SET_VALUE) as key:
            if entry is None:
                try:
                    winreg.DeleteValue(key, name)
                except FileNotFoundError:
                    pass
            else:
                winreg.SetValueEx(key, name, 0, entry[0], entry[1])

    def notify(self):
        wininet = ctypes.WinDLL("wininet", use_last_error=True)
        from ctypes import wintypes
        wininet.InternetSetOptionW.argtypes = (wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        wininet.InternetSetOptionW.restype = wintypes.BOOL
        for option in (39, 37):
            if not wininet.InternetSetOptionW(None, option, None, 0):
                raise OSError("WinINet refresh failed")


class ProxyGuard:
    """Journal first; restore only the exact values this instance installed.

    Partial activation failures are recoverable. Unrelated user/network software
    changes are never overwritten. A watchdog checks owner_pid under the same lock.
    """
    def __init__(self, directory, backend=None, lock_factory=None):
        self.directory = Path(directory)
        self.journal = self.directory / "proxy_backup.json"
        self.backend = backend if backend is not None else WindowsProxyBackend()
        self.lock_factory = lock_factory or (lambda: FileLock(self.directory / "proxy-transaction.lock"))

    def activate(self, port, owner_pid=None):
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("代理端口无效")
        self.directory.mkdir(parents=True, exist_ok=True)
        with self.lock_factory():
            if self.journal.exists():
                raise ProxyProblem("E_PROXY_PENDING", "journal_pending")
            enabled = self.backend.read("ProxyEnable")
            pac = self.backend.read("AutoConfigURL")
            if enabled and enabled[1]:
                raise ProxyProblem("E_PROXY_ACTIVE", "system_proxy")
            if pac and pac[1]:
                raise ProxyProblem("E_PROXY_PAC", "pac")
            before = {name: self.backend.read(name) for name in PROXY_NAMES}
            if any(not self._valid_entry(entry) for entry in before.values()):
                raise ValueError("系统代理值类型不支持，未修改网络设置")
            overrides = before["ProxyOverride"][1] if before["ProxyOverride"] else ""
            if not isinstance(overrides, str):
                raise ValueError("系统代理排除列表格式不支持")
            after = {"ProxyEnable": [4, 1], "ProxyServer": [1, "127.0.0.1:" + str(port)],
                     "ProxyOverride": [1, overrides + ";<local>;127.0.0.1;localhost"]}
            report = {"schema": 1, "owner_pid": owner_pid or os.getpid(), "before": before,
                      "after": after, "applied": []}
            atomic_json(self.journal, report)
            try:
                # Endpoint before enabling: never point an enabled proxy at a stale port.
                for name in ("ProxyServer", "ProxyOverride", "ProxyEnable"):
                    # Record intent BEFORE the write, including a crash at either boundary.
                    report["applied"].append(name)
                    atomic_json(self.journal, report)
                    self.backend.write(name, after[name])
                self.backend.notify()
            except Exception:
                self._recover(owner_pid=report["owner_pid"])
                raise

    def preflight(self):
        """Read-only early check; activate repeats it under the transaction lock."""
        with self.lock_factory():
            if self.journal.exists():
                raise ProxyProblem("E_PROXY_PENDING", "journal_pending")
            enabled = self.backend.read("ProxyEnable")
            pac = self.backend.read("AutoConfigURL")
            if enabled and enabled[1]:
                raise ProxyProblem("E_PROXY_ACTIVE", "system_proxy")
            if pac and pac[1]:
                raise ProxyProblem("E_PROXY_PAC", "pac")
        return True

    def recover(self, owner_pid=None):
        with self.lock_factory():
            return self._recover(owner_pid)

    def diagnostic_status(self):
        """Read-only enums/booleans; no endpoint, PAC URL, PID or original values."""
        with self.lock_factory():
            enabled = self.backend.read("ProxyEnable")
            pac = self.backend.read("AutoConfigURL")
            result = {"schema": 1, "system_proxy_enabled": bool(enabled and enabled[1]),
                      "pac_configured": bool(pac and pac[1]), "recovery_record": self.journal.exists(),
                      "recovery_check": "absent", "changed_fields": []}
            if not result["recovery_record"]:
                return result
            try:
                report = self._read_report()
            except (ValueError, RuntimeError, UnicodeError):
                result["recovery_check"] = "invalid"
                return result
            result["changed_fields"] = [name for name in PROXY_NAMES if name in report["applied"] and
                self.backend.read(name) not in (report["before"][name], report["after"][name])]
            result["recovery_check"] = "conflict" if result["changed_fields"] else "recoverable"
            return result

    @staticmethod
    def _valid_entry(entry):
        return entry is None or (isinstance(entry, list) and len(entry) == 2 and
                ((entry[0] == 4 and type(entry[1]) is int) or
                 (entry[0] in (1, 2) and isinstance(entry[1], str))))

    def _read_report(self):
        report = json.loads(self.journal.read_text(encoding="utf-8"))
        if not isinstance(report, dict) or report.get("schema") != 1 or type(report.get("owner_pid")) is not int:
            raise RuntimeError("代理恢复记录损坏，请保留数据并联系维护者")
        before, after = report.get("before"), report.get("after")
        applied = report.get("applied")
        if (not isinstance(before, dict) or not isinstance(after, dict) or
                set(before) != set(PROXY_NAMES) or set(after) != set(PROXY_NAMES) or
                not isinstance(applied, list) or any(name not in PROXY_NAMES for name in applied)):
            raise RuntimeError("代理恢复记录格式无效")
        for entries in (before, after):
            for entry in entries.values():
                if not self._valid_entry(entry):
                    raise RuntimeError("代理恢复值格式无效")
        return report

    def _recover(self, owner_pid=None):
        if not self.journal.exists():
            return "clean"
        report = self._read_report()
        if owner_pid is not None and report["owner_pid"] != owner_pid:
            return "other-owner"
        before, after, applied = report["before"], report["after"], report["applied"]
        # All-or-nothing ownership check. Preserve third-party changes and journal.
        if any(self.backend.read(name) not in (before[name], after[name]) for name in applied):
            return "conflict"
        for name in ("ProxyEnable", "ProxyServer", "ProxyOverride"):
            if name in applied and self.backend.read(name) == after[name]:
                self.backend.write(name, before[name])
        self.backend.notify()
        self.journal.unlink()
        return "restored"


def ca_installed(ca):
    return any(kind == "x509_asn" and hashlib.sha256(cert).hexdigest() == ca.fingerprint
               for cert, kind, _trust in ssl.enum_certificates("ROOT"))


def confirm(message):
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32", use_last_error=True)
    user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    user32.MessageBoxW.restype = ctypes.c_int
    return user32.MessageBoxW(None, message, "pipeRun · 请确认", 0x00000004 | 0x00000020) == 6


def install_ca(ca):
    if ca_installed(ca):
        return True
    if not confirm("允许将此安装独有的 pipeRun CA 加入当前 Windows 用户的受信任根证书库吗？\n"
                   "用于本人乐跑抓号，仅解密 api2.lptiyu.com。其他 HTTPS 只转发。\n"
                   "根证书授权有安全影响，请只在本人控制的电脑上使用。\n"
                   "不会安装到全机证书库，也不会修改微信或清除登录数据。"):
        return False
    # Fixed Windows system executable; never use PATH or a shell to install a root.
    certutil = Path(os.environ["SystemRoot"]) / "System32" / "certutil.exe"
    result = subprocess.run([str(certutil), "-user", "-addstore", "Root", str(ca.cert_file)],
                            capture_output=True, timeout=40, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode or not ca_installed(ca):
        raise RuntimeError("当前用户证书安装失败；未启动抓号，也未修改系统代理")
    return True


def wait_for_parent(pid, ready=None):
    """Wait on a process HANDLE, not a reusable PID or a guessed process name."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = (wintypes.HANDLE, wintypes.DWORD)
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel.CloseHandle.restype = wintypes.BOOL
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # Process already exited.
            if ready:
                ready()
            return
        raise OSError("Cannot watch parent process")
    try:
        if ready:
            ready()
        while True:
            result = kernel.WaitForSingleObject(handle, 1000)
            if result == 0:
                return
            if result != 258:
                raise OSError("Cannot wait on parent process")
    finally:
        kernel.CloseHandle(handle)
