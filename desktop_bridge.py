# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Desktop-only native action bridge. No web UI, HTTP control server or VPN."""
import datetime
import hashlib
import json
import os
import secrets
import threading
import time
from pathlib import Path

from desktop_storage import DesktopRegistry as AccountRegistry, atomic_json
from lepao.auth import AuthState

_data_dir = None
_lock = threading.RLock()
_platform = None
_capture = None
_diagnostics = None
_diagnostic_mode = False
_capture_requested = False
_capture_lock = threading.Lock()
_native_message = ""
_job = {"running": False, "message": ""}
_pending_run = None
_confirmation = None
_dryrun_ok = {}
_attempts = {}

def _config_path():
    return str(_data_dir / "config.json")

def _initialize(files_dir):
    global _data_dir, _attempts, _diagnostics
    _data_dir = Path(files_dir).resolve()
    _data_dir.mkdir(parents=True, exist_ok=True)
    from desktop_diagnostics import DiagnosticRecorder
    _diagnostics = DiagnosticRecorder(_data_dir / "diagnostics", build=getattr(_platform, "diagnostic_build", "desktop-1.0.0"))
    config = _data_dir / "config.json"
    if not config.exists():
        skeleton = {
            "version": 2, "active": "", "accounts": {},
            "environment": {
                "api_host": "api2.lptiyu.com", "api_proxy": "",
                "h5_base": "/bdlp_h5_fitness_test/public/index.php",
                "oss_host": "lptiyu-data.oss-cn-hangzhou.aliyuncs.com",
                "app_key": "wxb2043232183dac7f",
            },
            "policy": {"max_per_day": 1, "style": "template",
                       "dist_lo": 2.03, "dist_hi": 2.35,
                       "pace_lo": 185, "pace_hi": 560},
            "runtime": {"spacing_min": 5, "spacing_max": 10},
        }
        atomic_json(config, skeleton)
    os.environ["LEPAO2_CONFIG"] = str(config)
    os.environ["LEPAO_LICENSE_FILE"] = str(Path(__file__).resolve().parent / "LICENSE")
    ledger = _data_dir / "mobile_jobs.json"
    # Invalid ledgers must fail closed, rather than silently enabling a duplicate submit.
    _attempts = json.loads(ledger.read_text(encoding="utf-8")) if ledger.exists() else {}
    if not isinstance(_attempts, dict):
        raise ValueError("提交账本格式损坏，请先核查真实记录")

def _ca():
    from desktop_ca import CertificateAuthority
    global _certificate_authority
    if globals().get("_certificate_authority") is None:
        _certificate_authority = CertificateAuthority(_data_dir / "certificates")
    return _certificate_authority

def capture_arm():
    with _capture_lock:
        if not _capture:
            raise ValueError("请先启动本机代理")
        _capture.arm()

def capture_end():
    with _capture_lock:
        if _capture:
            _capture.close()

def capture_status():
    with _capture_lock:
        status = _capture.snapshot() if _capture else {"active": False, "listening": False, "message": "尚未开始抓号"}
        return json.dumps(status)

def set_diagnostic_mode(enabled):
    global _diagnostic_mode
    _diagnostic_mode = bool(enabled)

def diagnostic_begin():
    if _diagnostics:
        _diagnostics.begin()

def _diagnostic_emit(event, **values):
    if _diagnostics:
        _diagnostics.emit(event, **values)

def native_status(message, mode=None):
    global _native_message, _capture_requested
    _native_message = str(message)
    if mode == "":
        _capture_requested = False

def _auth_fingerprint(auth):
    return (datetime.date.today().isoformat(), auth.uid, hashlib.sha256(auth.token.encode()).hexdigest())

def _attempt_key(auth):
    return "{}:{}".format(datetime.date.today().isoformat(), auth.uid)

def job_failed(message):
    global _pending_run
    with _lock:
        _pending_run = None
        _job.update(running=False, message=str(message))

def _launch_job(member, kind, attempt_key=None):
    global _pending_run
    _job.update(running=True, message={"build": "干跑进行中…", "submit": "正在提交，随后自动复核…",
                                     "watch": "正在复核最近记录…"}[kind])
    _pending_run = (member, kind, attempt_key)
    if _platform:
        _platform.startRun()
    else:
        _job["running"] = False
        _pending_run = None
        raise ValueError("Desktop runner is not initialized")

def _action(action, form):
    global _confirmation, _capture_requested
    allowed = {"add", "capture", "capture-stop", "build", "prepare-submit", "submit", "watch", "desktop-recover", "desktop-exit"}
    if action not in allowed:
        raise ValueError("未知操作")
    if _diagnostic_mode and action in ("prepare-submit", "submit"):
        raise ValueError("提交需要单独确认")
    if action in ("desktop-recover", "desktop-exit"):
        if _job["running"]:
            raise ValueError("请等待当前任务结束")
        return _platform.recoverOrExit(action == "desktop-exit")
    if action == "capture-stop":
        _platform.stopCapture()
        return "正在停止获取账号并恢复网络。"
    if action == "capture":
        member = form.get("member", "")
        listening = json.loads(capture_status()).get("listening")
        with _lock:
            if _capture_requested or listening:
                raise ValueError("已有获取任务或正在等待授权")
            if member not in AccountRegistry(_config_path()).keys():
                raise ValueError("成员学号未登记")
            if _job["running"]:
                raise ValueError("请等待当前任务结束")
            _capture_requested = True
        try:
            _platform.startCapture(member)
        except Exception:
            _capture_requested = False
            raise
        return "请完成授权，倒计时内在小程序里登录本人账号一次。"
    if action in ("build", "prepare-submit", "submit", "watch"):
        member = form.get("member", "")
        # Read capture status before taking the registry lock (consistent lock order).
        if _capture_requested or json.loads(capture_status()).get("listening"):
            raise ValueError("请先结束抓号代理，再执行干跑")
        with _lock:
            if member not in AccountRegistry(_config_path()).keys():
                raise ValueError("成员学号未登记")
            if _job["running"]:
                raise ValueError("已有任务正在执行")
            reg = AccountRegistry(_config_path())
            auth = AuthState(reg, member)
            if not auth.token or not auth.uid:
                raise ValueError("请先抓号或导入本人凭证")
            if action in ("prepare-submit", "submit"):
                if _dryrun_ok.get(member) != _auth_fingerprint(auth):
                    raise ValueError("请先用当前凭证完成今日干跑")
                if _attempt_key(auth) in _attempts:
                    raise ValueError("今天已有提交尝试，请先复核或在小程序核查结果")
                if action == "prepare-submit":
                    _confirmation = {"member": member, "uid": auth.uid, "nonce": secrets.token_urlsafe(24),
                                     "fingerprint": _auth_fingerprint(auth),
                                     "expires": time.monotonic() + 300}
                    return "请核对下方提交确认。"
                if (not _confirmation or time.monotonic() >= _confirmation["expires"] or
                    _confirmation["fingerprint"] != _auth_fingerprint(auth) or
                    _confirmation["member"] != member or form.get("confirmed") != "yes" or
                    not secrets.compare_digest(form.get("nonce", ""), _confirmation["nonce"])):
                    raise ValueError("提交确认无效或已过期，请重新准备提交")
                _confirmation = None
                attempt_key = _attempt_key(auth)
                _attempts[attempt_key] = {"exit": None, "at": datetime.datetime.now().isoformat()}
                atomic_json(_data_dir / "mobile_jobs.json", _attempts)
            _launch_job(member, "submit" if action == "submit" else action,
                        attempt_key if action == "submit" else None)
        return "任务已开始。"
    if _capture_requested or json.loads(capture_status()).get("listening"):
        raise ValueError("请先结束抓号代理再修改成员或凭证")
    with _lock:
        if _job["running"]:
            raise ValueError("请等待干跑结束后修改成员或凭证")
        reg = AccountRegistry(_config_path())
        if action == "add":
            name = form.get("name", "")
            member = form.get("student_num", "")
            if not name or not member:
                raise ValueError("姓名与学号必填")
            reg.add(name, member)
            return "已登记成员。"
        raise ValueError("未知操作")
