# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""pipeRun Windows standalone client. Normal launch never starts account traffic."""
import argparse
import contextlib
import ctypes
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import desktop_bridge as bridge
from desktop_win import FileLock, FileLockBusy, ProxyGuard, ProxyProblem, ca_installed, confirm, install_ca, wait_for_parent
from desktop_capture import CaptureSession
from desktop_storage import atomic_json
from desktop_version import BUILD
from desktop_events import EventLog, classify, fault_context
from desktop_progress import login_required, login_saved


def data_directory():
    return Path(os.environ["LOCALAPPDATA"]) / "pipeRun" / "desktop"


def child_command(*args):
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve()), *args]


def start_watchdog(directory):
    ready = Path(directory) / ("watchdog-ready-" + str(os.getpid()) + ".json")
    if ready.exists():
        ready.unlink()
    child = subprocess.Popen(child_command("--watchdog", str(os.getpid())),
                             creationflags=subprocess.CREATE_NO_WINDOW,
                             env=dict(os.environ, PYINSTALLER_RESET_ENVIRONMENT="1"))
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if ready.exists():
            ready.unlink()
            return child
        if child.poll() is not None:
            break
        time.sleep(0.05)
    # No proxy was changed; do not silently run without crash protection.
    raise RuntimeError("网络恢复守护未就绪，未启动抓号；请重新打开客户端")


class DesktopPlatform:
    desktop = True
    diagnostic_build = BUILD

    def __init__(self, directory, guard=None):
        self.directory = Path(directory)
        self.guard = guard or ProxyGuard(directory)
        self.stop_event = threading.Event()
        self.exit_event = threading.Event()
        self.operation = threading.RLock()
        self.worker = None
        self.watchdog = None
        self.ui_events = EventLog(self.directory / "diagnostics")
        self.job_stop = threading.Event()
        self.job_kind = ""
        self.write_started = False
        self.checked_at = {}
        self.checked_login = {}
        self.required_login = {}
        self.previews = {}
        self.capture_member = ""
        self.job_member = ""

    def invalidate_login(self):
        if not self.job_member:
            return
        with bridge._lock:
            auth = bridge.AuthState(bridge.AccountRegistry(bridge._config_path()), self.job_member)
            login_required(bridge, self, self.job_member, auth)

    def installCa(self):
        self.ui_events.emit("ca", "start")
        installed = install_ca(bridge._ca())
        self.ui_events.emit("ca", "ca_present" if installed else "cancelled", "INFO" if installed else "WARN")
        bridge.native_status("本机 CA 已安装；不代表微信一定信任。" if installed else "已取消证书安装，未修改代理。")
        return installed

    def startCapture(self, member):
        # Called only after the native controller and bridge validate the member.
        with self.operation:
            if self.worker and self.worker.is_alive():
                raise ValueError("已有抓号任务")
            with bridge._lock:
                auth = bridge.AuthState(bridge.AccountRegistry(bridge._config_path()), str(member))
                login_required(bridge, self, str(member), auth)
                self.capture_member = str(member)
            self.stop_event.clear()
            self.worker = threading.Thread(target=self._capture, args=(str(member),), daemon=True)
            self.worker.start()

    def _capture(self, member):
        relay_started = False
        bridge.diagnostic_begin()
        try:
            self.ui_events.emit("precheck", "start")
            self.guard.preflight()
            self.ui_events.emit("precheck", "ok")
            self.ui_events.emit("ca", "start")
            ca = bridge._ca()
            if not ca_installed(ca) and not self.installCa():
                return
            self.ui_events.emit("ca", "ca_present")
            if self.stop_event.is_set():
                return
            self.ui_events.emit("consent", "start")
            if not confirm("允许在本次抓号期间临时修改当前 Windows 用户的系统代理吗？\n"
                           "可能影响其他应用联网；仅目标域名 HTTPS 被解密，不保存流量正文。\n"
                           "保存本人凭证、60 秒超时或点击停止后恢复；不会强制退出微信。\n"
                           "等倒计时出现后，在「数体智慧体育」小程序内登录本人账号一次。不是登录微信，不必重启小程序。"):
                self.ui_events.emit("consent", "cancelled", "WARN")
                bridge.native_status("已取消本次代理授权；未启动抓号。", "")
                return
            if self.stop_event.is_set():
                return
            with self.operation:
                if self.stop_event.is_set():
                    return
                if not self.watchdog or self.watchdog.poll() is not None:
                    self.ui_events.emit("watchdog", "start")
                    self.watchdog = start_watchdog(self.directory)
                    self.ui_events.emit("watchdog", "ok")
                with bridge._capture_lock:
                    bridge._capture = CaptureSession(bridge._config_path(), ca, bridge._lock,
                                                    window=60, stable=8, diagnostic=self.capture_event)
                    relay_started = True
                    port = bridge._capture.begin(member, armed=False)
                self.ui_events.emit("proxy", "start")
                self.guard.activate(port)
                bridge.capture_arm()
                bridge.native_status("倒计时开始，请在「数体智慧体育」小程序内登录本人账号一次；不是登录微信，不必重启小程序。", "")
                bridge._diagnostic_emit("desktop_start", force=True, ca_installed=True)
                self.ui_events.emit("capture", "capture_ready")
            while not self.stop_event.wait(0.5):
                if self.watchdog.poll() is not None:
                    raise RuntimeError("网络恢复守护已退出，已提前结束抓号")
                status = json.loads(bridge.capture_status())
                bridge._diagnostic_emit("desktop_sample", force=True, **status)
                if not status.get("active"):
                    break
        except Exception as exc:
            code = classify(exc)
            self.ui_events.emit(self.ui_events.stage, code, "ERROR", **fault_context(exc, "capture"))
            # User-facing messages are fixed; never publish raw OS/network exceptions.
            from desktop_events import CODES
            bridge.native_status("抓号未完成：" + code + " · " + CODES[code], "")
        finally:
            try:
                if relay_started:
                    self._finish()
                else:
                    # Preflight/consent refused: this attempt installed no proxy.
                    # Do not recover an older owner's journal or leave ghost capture state.
                    bridge._capture_requested = False
                    self.ui_events.emit("cleanup", "proxy_unchanged")
            except Exception as exc:
                self.ui_events.emit("cleanup", "E_RECOVERY", "ERROR", **fault_context(exc, "capture"))
                bridge.native_status("网络恢复未完成。请点击「恢复网络设置」；不要强制退出程序。", "")

    def capture_event(self, event, **values):
        if event == "credential_saved" and self.capture_member:
            with bridge._lock:
                login_saved(bridge, self, self.capture_member)
        bridge._diagnostic_emit(event, **values)
        code = {"tls_ok": "tls_ok", "request_ok": "request_ok", "identity_pending": "identity_pending",
                "identity_other": "identity_other", "identity_matched": "identity_matched",
                "credential_saved": "credential_saved", "capture_timeout": "capture_timeout",
                "capture_incompatible": "tls_rejected", "credential_save_failed": "E_PERMISSION"}.get(event)
        if code:
            self.ui_events.emit("capture", code, "WARN" if code in ("tls_rejected", "identity_other", "E_PERMISSION") else "INFO", **values)

    def _finish(self):
        with self.operation:
            self.ui_events.emit("cleanup", "start")
            result = self.guard.recover(owner_pid=os.getpid())
            if result in ("conflict", "other-owner"):
                raise ProxyProblem("E_RECOVERY", "journal_conflict" if result == "conflict" else "other_owner")
            bridge.capture_end()
            bridge._diagnostic_emit("desktop_stop", force=True, active=False, listening=False, outcome="ended")
            bridge._capture_requested = False
            self.ui_events.emit("cleanup", "restored")
            if bridge._native_message.startswith("代理已就绪"):
                bridge.native_status("获取已结束，电脑网络已恢复。看到“账号已连接”后，点“开始检查”。", "")

    def stopCapture(self):
        self.stop_event.set()
        self._finish()

    def recoverOrExit(self, exit_program=False):
        if (not self.worker or not self.worker.is_alive()) and not json.loads(bridge.capture_status()).get("listening"):
            # Explicit recovery of an older crashed instance, while main holds
            # the single-instance lock. No active capture may change owners here.
            if self.guard.recover() == "conflict":
                raise ProxyProblem("E_RECOVERY", "journal_conflict")
        self.stopCapture()
        if exit_program:
            if self.worker and self.worker.is_alive():
                # Give normal capture cleanup time to finish. A still-open consent
                # dialog remains blocked rather than being killed or auto-approved.
                self.worker.join(timeout=1)
            if self.worker and self.worker.is_alive():
                raise ValueError("正在关闭抓号授权窗口，请先完成或取消弹窗，再退出")
            # Let the native event loop display the result before destroying its window.
            threading.Timer(0.8, self.exit_event.set).start()
            return "网络设置已恢复，程序即将退出。"
        bridge.native_status("网络设置已恢复。", "")
        return "网络设置已恢复。"

    def startRun(self):
        from desktop_jobs import run_pending
        self.job_stop.clear()
        try:
            threading.Thread(target=run_pending, args=(bridge, self), daemon=True).start()
        except Exception:
            bridge._pending_run = None
            bridge._job["running"] = False
            raise

    def stopRun(self):
        if self.job_kind == "submit" or self.write_started:
            raise ValueError("提交写入不允许中途取消；请等待并复核结果，禁止重复提交")
        self.job_stop.set()
        self.ui_events.emit("ui", "stop_requested", "WARN")


def watchdog(pid):
    directory = data_directory()
    ready = directory / ("watchdog-ready-" + str(pid) + ".json")
    try:
        wait_for_parent(pid, ready=lambda: atomic_json(ready, {"ready": True}))
        result = ProxyGuard(directory).recover(owner_pid=pid)
        return 0 if result != "conflict" else 2
    finally:
        if ready.exists():
            ready.unlink()


def diagnose():
    """User-initiated, offline support check; never reads accounts or writes proxy/CA stores."""
    import datetime
    import zipfile
    from desktop_selfcheck import run
    destination = data_directory() / "support" / datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    destination.mkdir(parents=True, exist_ok=False)
    os.environ["LEPAO_RUNNER_DIR"] = str(destination)
    result = run()
    archive = destination / "pipeRun-offline-diagnostic.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as bundle:
        bundle.write(destination / "selfcheck.json", "offline-selfcheck.json")
    from ctypes import wintypes
    user32 = ctypes.WinDLL("user32")
    user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
    user32.MessageBoxW(None, ("离线启动自检通过。" if result == 0 else "离线启动自检未通过。") +
                      "\n未安装证书、未修改代理、未连接乐跑服务。\n已生成脱敏 ZIP，可手动发回。", "pipeRun 自检", 0)
    os.startfile(str(destination))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--selfcheck", action="store_true")
    parser.add_argument("--diagnose", action="store_true")
    parser.add_argument("--reset-accounts", action="store_true", help="重置本机登记及凭证；保留证书和提交账本")
    parser.add_argument("--watchdog", type=int)
    args = parser.parse_args(argv)
    if args.selfcheck:
        from desktop_selfcheck import run
        return run()
    if os.name != "nt":
        raise RuntimeError("此客户端只支持 Windows 10/11 x64")
    if args.watchdog is not None:
        return watchdog(args.watchdog)
    if args.diagnose:
        return diagnose()
    directory = data_directory()
    with contextlib.ExitStack() as instance_context:
        try:
            instance_context.enter_context(FileLock(directory / "instance.lock", timeout=0))
        except FileLockBusy:
            if args.reset_accounts:
                raise  # CLI reset must never bypass the instance lock.
            from desktop_instance import activate_existing, notify_already_open
            try:
                activated = activate_existing(directory)
            except Exception:
                activated = False
            if not activated:
                notify_already_open()
            return 0
        if args.reset_accounts:
            from desktop_accounts import reset_accounts
            reset_accounts(directory)
            return 0
        platform = DesktopPlatform(directory)
        recovered = platform.guard.recover()
        bridge.set_diagnostic_mode(True)  # Ordinary actions stay locked; native confirmation is separate.
        bridge._platform = platform
        bridge._initialize(str(directory))
        if recovered == "conflict":
            bridge.native_status("检测到上次代理恢复冲突。请先自行核对系统代理，再点击恢复网络设置。", "")
        else:
            bridge.native_status("先登记本人账号，再抓号和只读验收；模板生成记录需要逐次确认才会上传/提交。", "")
        try:
            from desktop_gui import run
            run(bridge, platform)
        finally:
            platform.stopCapture()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        if os.name == "nt" and "--selfcheck" not in sys.argv and "--watchdog" not in sys.argv:
            # Errors must be visible in a --windowed build, without a console.
            from ctypes import wintypes
            user32 = ctypes.WinDLL("user32")
            user32.MessageBoxW.argtypes = (wintypes.HWND, wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.UINT)
            from desktop_events import CODES
            code = classify(exc)
            user32.MessageBoxW(None, "启动/退出未完成：" + code + " · " + CODES[code] +
                               "\n可运行 diagnose.cmd 离线自检。如果此前已有提交尝试，请先在官方小程序核对，不要直接重试。", "pipeRun", 0x10)
        raise SystemExit(1)
