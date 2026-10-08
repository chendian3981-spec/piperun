# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Bundled native UI. No browser, local web server or online dependency download."""
import json
import io
import os
import re
import secrets
import tempfile
import threading
import time
import zipfile
from pathlib import Path

from desktop_version import VERSION, WINDOW_TITLE
from desktop_events import CODES, EventLog, classify, fault_context
from desktop_progress import checked as check_current, usable, reviewed, submitted, clear_check, clear_review


class UserError(ValueError):
    def __init__(self, code, reported=False):
        self.code = code if code in CODES else "E_UNKNOWN"
        self.reported = reported
        super().__init__(self.code + " · " + CODES[self.code])


class Controller:
    # Ordinary actions cannot submit. Writes require the separate native confirmation flow.
    ACTIONS = frozenset(("add", "capture", "capture-stop", "build", "watch", "stop-job", "desktop-recover", "desktop-exit"))

    def __init__(self, bridge, platform):
        self.bridge, self.platform = bridge, platform
        self.events = getattr(platform, "ui_events", None)
        if not isinstance(self.events, EventLog):
            self.events = EventLog()
            platform.ui_events = self.events
        self.action_lock = threading.RLock()
        for name in ("checked_at", "checked_login", "required_login", "previews", "submission_receipts"):
            if not isinstance(getattr(platform, name, None), dict):
                setattr(platform, name, {})
        self.prepared = None
        self.events.emit("ui", "boot")
        self.events.emit("ui", "scope")

    def action(self, action, form=None):
        if action not in self.ACTIONS:
            raise ValueError("此入口不允许提交；请通过原生二次确认窗口操作")
        try:
            with self.action_lock:
                self.bridge.set_diagnostic_mode(True)
                form = dict(form or {})
                if action == "add":
                    form = {k: str(form.get(k, "")).strip() for k in ("name", "student_num")}
                    if not 1 <= len(form["name"]) <= 40 or any(ord(c) < 32 for c in form["name"]) or not re.fullmatch(r"[A-Za-z0-9_-]{1,32}", form["student_num"]):
                        raise UserError("E_INPUT")
                if action in ("build", "watch"):
                    self._account(form.get("member", ""), consumed_ok=action == "watch")
                    with self.bridge._lock:
                        if action == "build":
                            clear_check(self.bridge, self.platform, form["member"])
                        else:
                            clear_review(self.bridge, form["member"])
                if action == "stop-job":
                    self.platform.stopRun()
                    return CODES["stop_requested"]
                if action in ("desktop-exit", "desktop-recover") and self.bridge._job["running"]:
                    raise UserError("E_WRITING" if getattr(self.platform, "job_kind", "") == "submit" else "E_BUSY")
                self.events.emit("ui", "start", operation=action)
                result = self.bridge._action(action, form)
                if action not in ("capture", "build", "watch"):
                    self.events.emit("ui", "ok", operation=action)
                return result
        except Exception as exc:
            code = exc.code if isinstance(exc, UserError) else classify(exc)
            self.events.emit("ui", code, "ERROR", **fault_context(exc, action))
            raise UserError(code, reported=True) from None

    def _account(self, member, consumed_ok=False):
        with self.bridge._lock:
            reg = self.bridge.AccountRegistry(self.bridge._config_path())
            if member not in reg.keys():
                raise UserError("E_MEMBER")
            auth = self.bridge.AuthState(reg, member)
            if not usable(self.platform, member, auth, consumed_ok):
                raise UserError("E_AUTH")
            return reg, auth

    def _confirmation_action(self, action, form):
        # Only a validated native confirmation may temporarily open the submit gate.
        # Restore the ordinary read-only action gate on every return/error path.
        previous = self.bridge._diagnostic_mode
        self.bridge.set_diagnostic_mode(False)
        try:
            return self.bridge._action(action, form)
        finally:
            self.bridge.set_diagnostic_mode(previous)

    def prepare_submission(self, member):
        with self.action_lock:
            try:
                reg, auth = self._account(member)
                if not check_current(self.bridge, self.platform, member, auth):
                    raise UserError("E_DRYRUN")
                self._confirmation_action("prepare-submit", {"member": member})
                confirmation = self.bridge._confirmation
                self.prepared = {"member": member, "nonce": confirmation["nonce"], "expires": confirmation["expires"]}
                preview = getattr(self.platform, "previews", {}).get(member, {})
                self.events.emit("submit", "source", "WARN")
                self.events.emit("submit", "consent_ready")
                return {**self.prepared, "name": reg.acc(member).get("name", "本人"),
                        "preview": dict(preview), "source": "模板/算法生成，非实际运动采集"}
            except Exception as exc:
                self.cancel_confirmation()
                code = exc.code if isinstance(exc, UserError) else classify(exc)
                self.events.emit("submit", code, "ERROR", **fault_context(exc, "prepare-submit"))
                raise UserError(code, reported=True) from None

    def cancel_confirmation(self):
        with self.action_lock:
            if self.prepared and self.bridge._confirmation and self.bridge._confirmation.get("nonce") == self.prepared["nonce"]:
                self.bridge._confirmation = None
            self.prepared = None

    def submit_confirmation(self, nonce, acknowledged=False):
        with self.action_lock:
            try:
                prepared = self.prepared
                if (acknowledged is not True or not prepared or time.monotonic() >= prepared["expires"] or
                    not isinstance(nonce, str) or not secrets.compare_digest(nonce, prepared["nonce"])):
                    raise UserError("E_CONFIRM")
                _, auth = self._account(prepared["member"])
                if not check_current(self.bridge, self.platform, prepared["member"], auth):
                    raise UserError("E_DRYRUN")
                self.events.emit("auth", "start")
                result = self._confirmation_action("submit", {"member": prepared["member"], "nonce": nonce, "confirmed": "yes"})
                return result
            except Exception as exc:
                code = exc.code if isinstance(exc, UserError) else classify(exc)
                self.events.emit("submit", code, "ERROR", **fault_context(exc, "submit"))
                raise UserError(code, reported=True) from None
            finally:
                self.cancel_confirmation()

    def reset_accounts(self, acknowledged=False):
        with self.action_lock:
            try:
                if acknowledged is not True:
                    raise UserError("E_CONFIRM")
                if (self.prepared or self.bridge._job["running"] or self.bridge._capture_requested or
                        json.loads(self.bridge.capture_status()).get("listening")):
                    raise UserError("E_BUSY")
                if (Path(self.platform.directory) / "proxy_backup.json").exists():
                    raise UserError("E_RECOVERY")
                from desktop_accounts import reset_accounts
                self.events.emit("ui", "start", operation="reset-accounts")
                with self.bridge._lock:
                    reset_accounts(self.platform.directory)
                    self.bridge._dryrun_ok.clear()
                    self.bridge._confirmation = None
                    self.bridge._job["message"] = ""
                    self.platform.checked_at.clear()
                    self.platform.checked_login.clear()
                    self.platform.required_login.clear()
                    self.platform.previews.clear()
                    self.platform.submission_receipts.clear()
                    for field in ("reviewed_member", "reviewed_record", "reviewed_login", "reviewed_day"):
                        self.bridge._job.pop(field, None)
                self.events.emit("ui", "accounts_reset", operation="reset-accounts")
                return CODES["accounts_reset"]
            except Exception as exc:
                code = classify(exc)
                self.events.emit("ui", code, "ERROR", **fault_context(exc, "reset-accounts"))
                raise UserError(code, reported=True) from None

    def snapshot(self):
        capture = json.loads(self.bridge.capture_status())
        recovery_journal = getattr(self.platform.guard, "journal", None)
        with self.bridge._lock:
            reg = self.bridge.AccountRegistry(self.bridge._config_path())
            job = dict(self.bridge._job)
            members = []
            for key in reg.keys():
                account = reg.acc(key)
                auth = account.get("auth") or {}
                state = self.bridge.AuthState(reg, key)
                ready = usable(self.platform, key, state)
                attempt = self.bridge._attempts.get(self.bridge._attempt_key(state), {}) if account.get("uid") else {}
                attempted = bool(account.get("uid") and self.bridge._attempt_key(state) in self.bridge._attempts)
                checked_now = check_current(self.bridge, self.platform, key, state)
                verified = ready and checked_now
                members.append({"key": key, "name": account.get("name") or "本人",
                                "ready": ready, "consumed": bool(auth.get("consumed_at")),
                                "has_token": bool(auth.get("token") and account.get("uid")),
                                "can_watch": usable(self.platform, key, state, consumed_ok=True),
                                "attempted": attempted, "can_submit": bool(verified and not attempted),
                                "checked": bool(checked_now),
                                "submitted": submitted(self.bridge, self.platform, key, state, attempt.get("record_id")),
                                "reviewed": reviewed(self.bridge, self.platform, key, state, attempt.get("record_id"))})
        capture["message"] = friendly_capture(capture.get("message"))
        return {"members": members, "capture": capture, "job": job,
                "recovery_pending": isinstance(recovery_journal, Path) and recovery_journal.exists(),
                "pending": bool(self.bridge._capture_requested),
                "native": self.bridge._native_message, "stage": self.events.stage,
                "job_kind": getattr(self.platform, "job_kind", "") if getattr(self.platform, "job_kind", "") in ("build", "submit", "watch") else ""}

    def export(self, destination):
        destination = Path(destination)
        if destination.suffix.lower() != ".zip":
            raise ValueError("请保存为 ZIP 文件")
        # Never allow an export to replace application private state.
        private = Path(self.platform.directory).resolve()
        if destination.resolve().is_relative_to(private):
            raise ValueError("请保存到桌面或下载目录，不要覆盖应用数据")
        if self.bridge._capture_requested or json.loads(self.bridge.capture_status()).get("listening"):
            raise ValueError("请等抓号结束后再导出诊断包")
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w", zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("desktop-events.json", json.dumps(self.events.snapshot(), ensure_ascii=False, indent=2))
            try:
                network = self.platform.guard.diagnostic_status()
                if not isinstance(network, dict):
                    network = {"schema": 1, "available": False, "error": "E_INTERNAL"}
            except Exception as exc:
                network = {"schema": 1, "available": False, "error": classify(exc)}
            archive.writestr("network-precheck.json", json.dumps(network, ensure_ascii=False, indent=2))
            if self.events.previous is not None:
                archive.writestr("desktop-previous.json", json.dumps(self.events.previous, ensure_ascii=False, indent=2))
            try:
                capture_report = self.bridge._diagnostics.snapshot()
            except ValueError:
                capture_report = None
            if capture_report is not None:
                archive.writestr("diagnostic.json", json.dumps(capture_report, ensure_ascii=False, indent=2))
            archive.writestr("README.txt", "pipeRun sanitized diagnostics. Fixed event codes, relative times and numeric counters only.\n"
                             "No identity, token, nonce, CA/key, request/response, endpoint or full exception. No automatic upload.\n")
        fd, temporary = tempfile.mkstemp(prefix=".piperun-export-", suffix=".tmp", dir=destination.parent)
        try:
            with os.fdopen(fd, "wb") as output:
                output.write(payload.getvalue())
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, destination)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        self.events.emit("ui", "exported")
        return "脱敏诊断已保存，请手动发回；不会自动上传。"


def friendly_capture(message):
    # Display fixed Windows recovery guidance rather than raw capture exceptions.
    message = str(message or "")
    if "微信连续拒绝" in message:
        return ("微信连续拒绝本机代理证书，已停止捕获。请确认网络已恢复，再重新进入小程序。"
                "不要反复重装 CA 或清除账号数据；请导出诊断 ZIP。")
    return message.replace("关闭 VPN", "恢复网络").replace("关闭VPN", "恢复网络")




def run(bridge, platform):
    from desktop_qt import run as run_workbench
    return run_workbench(Controller(bridge, platform))
