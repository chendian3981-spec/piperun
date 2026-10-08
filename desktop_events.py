# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Structured desktop progress and bounded, privacy-safe diagnostic events."""
import copy
import datetime
import json
import socket
import ssl
import threading
import time
from pathlib import Path

from desktop_version import BUILD
from desktop_storage import atomic_json
from lepao.accounts import AccountError

STAGES = {
    "ui": "操作", "precheck": "检查电脑网络", "ca": "电脑连接授权", "consent": "临时网络授权",
    "watchdog": "准备网络保护", "proxy": "准备账号连接", "capture": "获取本人账号", "cleanup": "恢复正常网络",
    "auth": "检查登录信息", "rules": "检查使用规则", "quota": "检查今日次数", "clock": "准备时间",
    "generate": "准备测试记录", "package": "整理记录", "upload": "上传记录文件",
    "submit": "提交记录", "verify": "结果复核", "done": "任务结束",
}
CODES = {
    "start": "正在处理。", "ok": "", "waiting": "还在处理，请稍等。不会自动重复提交。",
    "boot": "软件已准备好。跟着编号步骤操作即可，不会自动获取账号或提交。",
    "scope": "原作者 dan-cun · github.com/dan-cun/lepao3 · LRL-1.0 非商业研究许可。",
    "request": "正在连接服务，检查本步骤的信息。不会保存你的登录密钥。",
    "response": "已收到服务返回的信息。", "capture_ready": "倒计时开始。请在「数体智慧体育」小程序里登录本人账号一次；不是登录微信，不必重启小程序。",
    "capture_sample": "正在获取账号，请按页面提示操作。", "identity_pending": "已收到登录信息，正在核对是不是本人账号。",
    "identity_other": "发现另一个账号的信息，没有保存。请登录当前选择的本人账号。",
    "identity_matched": "已找到本人账号。请停留在当前页面，不要再次登录，等软件保存。", "credential_saved": "账号登录信息已保存。正在恢复网络，完成后可开始检查。",
    "tls_ok": "已与服务建立安全连接。", "request_ok": "已收到一条账号相关信息。",
    "capture_timeout": "倒计时已结束，正在恢复网络。没找到账号时可再试；请在获取期间完成一次小程序内的本人账号登录。",
    "tls_rejected": "微信没有接受本机连接证书，已停止获取。请导出诊断，不要反复安装同一证书。",
    "ca_present": "本机连接证书已安装。是否能够连接，还需要等待微信确认。",
    "cancelled": "操作已取消；没有自动重试。", "restored": "网络设置已恢复。",
    "consent_ready": "提交确认已准备，有效期 5 分钟；尚未提交或上传。",
    "source": "记录来自模板/算法生成，并非实际运动采集；只应在获许可的测试范围内使用。",
    "dryrun_ok": "检查已通过。没有上传，也没有提交；需要提交时再由你确认。",
    "sample_retry": "正在重新准备测试记录。只是电脑本地计算，不会重复提交。",
    "write_start": "正在上传并提交。请不要强制关闭或再次提交，完成后会继续查询结果。",
    "accepted": "服务已收到记录，但还不代表有效。正在查询最终结果。",
    "valid": "服务端复核：记录有效。", "invalid": "服务端复核：记录无效，不会自动补交。",
    "pending": "最终结果还没出来。请稍后查询，不要重复提交。",
    "verify_wait": "稍等后会再查一次结果，期间不会再次提交。",
    "exported": "问题诊断文件已保存，不含登录密钥。需要反馈时请手动发送，不会自动上传。",
    "stop_requested": "已收到停止请求，正在等当前连接结束。上传和提交不能中途取消。",
    "E_INPUT": "请检查姓名/别名和学号是否填完整。不需要填写登录密钥。",
    "E_DUPLICATE": "账号已登记。请选择已有账号，不需要重复登记。",
    "E_MEMBER": "请先登记并选择本人账号。",
    "E_BUSY": "还有一步或授权弹窗没有结束。请先等待，或点击停止获取/停止检查。",
    "E_WRITING": "提交、上传或后续复核正在进行。请等待，不要强退或再次提交；无法确认时先到官方小程序核查。",
    "E_PROXY": "已有系统代理/PAC或恢复记录冲突。暂停原代理或核对原设置，不会强行覆盖。",
    "E_PROXY_ACTIVE": "电脑已开启其他代理。请打开 Windows 设置→网络和 Internet→代理，核对“使用代理服务器”。本次没有改动网络。",
    "E_PROXY_PAC": "电脑仍填有代理脚本地址。请打开 Windows 设置→网络和 Internet→代理，核对“使用设置脚本”。本次没有改动网络。",
    "E_PROXY_PENDING": "发现未完成的代理恢复记录。先点击恢复网络；若仍冲突，请导出诊断，不要重置账号。",
    "proxy_unchanged": "本次没有改动网络，账号获取已停止。",
    "E_CA": "证书安装未完成。确认当前用户证书授权；企业策略禁止时请联系管理员。",
    "E_WATCHDOG": "网络保护还没准备好，本次没有开始获取账号。请重新打开软件再试。",
    "E_AUTH": "登录信息已失效或不可用。请重新获取账号，并在倒计时内完成一次「数体智慧体育」小程序登录。",
    "E_DRYRUN": "请先点“开始检查”。本次打开软件后检查通过，10 分钟内才能查看提交确认。",
    "E_CONFIRM": "提交确认无效、已取消或超过 5 分钟。重新准备，不会自动提交。",
    "E_ATTEMPT": "今天已有提交尝试。先复核或在官方小程序核对，不要重复提交。",
    "E_QUOTA": "当天额度已满，已停止本次提交。",
    "E_TIMEOUT": "网络等待超时。检查网络；如果已进入写入阶段，先复核，禁止直接重试。",
    "E_DNS": "没有找到服务地址。请检查电脑是否能上网；公司或校园网络可能有限制，不要反复安装证书。",
    "E_TLS": "安全连接检查没有通过。请核对电脑日期和网络限制，不要关闭安全检查。",
    "E_NETWORK": "网络连接失败。检查联网状态及原代理；提交结果可能不确定时先复核。",
    "E_PERMISSION": "文件或系统操作被拒绝。选择可写目录，核对安全软件/企业策略，不要关闭防护。",
    "E_DISK": "磁盘空间不足。释放空间后再试；不要删除账号或证书数据。",
    "E_RESPONSE": "服务返回的信息无法确认，或不是本人账号。已停止，请导出诊断；不会自动重复提交。",
    "E_GENERATE": "测试记录暂时不符合规则。若还没开始上传，可重新检查；不要更改官方规则。",
    "E_EXPORT": "诊断保存失败。请选桌面或下载目录的 ZIP 文件，不能覆盖应用私有数据。",
    "E_STATE": "本机记录文件损坏。已停止且保留原文件；先在官方小程序核对，不要清空数据以绕过防重复。",
    "E_RECOVERY": "网络恢复未完成。请导出诊断并核对系统代理；反复点击或重置账号不能解决，不会强行覆盖。",
    "E_UNKNOWN": "操作未完成。查看当前阶段并导出脱敏诊断；未自动重试提交。",
    "E_UI": "界面组件未能加载。请使用修复版软件；不需要重新获取账号、安装证书或重置数据。",
    "E_INTERNAL": "客户端内部错误。请导出脱敏诊断并更新版本，不要反复重装或清空数据。",
    "accounts_reset": "账号已初始化，请重新登记。证书、网络恢复记录和提交账本已保留。",
}
NUMBERS = frozenset(("remaining", "connections", "target", "tls_ok", "tls_failed", "requests",
                     "certificate_rejected", "attempt", "round", "wait_seconds", "elapsed", "duration_ms",
                     "point_count", "distance_m", "used_seconds", "line"))
NUMBER_LABELS = dict(zip(("remaining", "connections", "target", "tls_ok", "tls_failed", "requests", "certificate_rejected",
                         "attempt", "round", "wait_seconds", "elapsed", "duration_ms", "point_count", "distance_m", "used_seconds"),
                        ("剩余(s)", "连接", "目标连接", "TLS成功", "TLS失败", "业务请求", "证书拒绝", "本地尝试",
                         "复核轮次", "等待(s)", "累计耗时(s)", "请求耗时(ms)", "样本点数", "样本距离(m)", "样本用时(s)")))
NUMBER_LABELS["line"] = "源码行"
OPERATIONS = {"add": "添加账号", "capture": "开始获取账号", "capture-stop": "停止获取", "build": "开始检查",
              "watch": "结果复核", "stop-job": "停止只读", "desktop-recover": "恢复网络", "desktop-exit": "退出",
              "prepare-submit": "准备提交", "submit": "确认提交", "reset-accounts": "重置账号",
              "export": "导出诊断", "snapshot": "状态刷新", "ui": "界面"}
ENUM_FIELDS = {
    "operation": frozenset(OPERATIONS),
    "exception": frozenset("AccountError UserError ProxyProblem ValueError RuntimeError TypeError AttributeError KeyError NameError IndexError JSONDecodeError FileNotFoundError PermissionError OSError TimeoutError gaierror SSLError other".split()),
    "proxy_reason": frozenset("system_proxy pac journal_pending journal_conflict other_owner".split()),
    "source": frozenset("desktop_gui desktop_qt desktop_app desktop_accounts desktop_win desktop_jobs desktop_events desktop_console desktop_tutorial desktop_progress desktop_bridge desktop_storage desktop_capture desktop_ca accounts auth state pipeline other".split()),
    "method": frozenset("get_term_list get_school_info before_run get_term_run_record get_timestamp get_oss_sts stop_run record_detail".split()),
    "response_kind": frozenset("object array number string boolean null other".split()),
    "response_check": frozenset("shape identity quota_items expired request".split()),
}


def safe_context(values):
    return {k: v for k, v in values.items() if k in ENUM_FIELDS and isinstance(v, str) and v in ENUM_FIELDS[k]}


def fault_context(exc, operation="ui"):
    """Only catalog names and first-party source line numbers; no text, locals or paths."""
    result = {"operation": operation, "exception": type(exc).__name__}
    if hasattr(exc, "proxy_reason"):
        result["proxy_reason"] = exc.proxy_reason
    trace = exc.__traceback__
    while trace:
        source = Path(trace.tb_frame.f_code.co_filename).stem
        if source in ENUM_FIELDS["source"] and source != "other":
            result.update(source=source, line=trace.tb_lineno)
        trace = trace.tb_next
    return {**safe_context(result), **({"line": result["line"]} if "line" in result else {})}


def classify(exc):
    """Only return catalog identifiers; never retain arbitrary exception text."""
    if isinstance(getattr(exc, "code", None), str) and exc.code in CODES:
        return exc.code
    if isinstance(exc, json.JSONDecodeError):
        return "E_STATE"
    if isinstance(exc, (TypeError, AttributeError, KeyError, NameError, IndexError)):
        return "E_INTERNAL"
    if isinstance(exc, (TimeoutError, socket.timeout)):
        return "E_TIMEOUT"
    if isinstance(exc, socket.gaierror):
        return "E_DNS"
    if isinstance(exc, ssl.SSLError):
        return "E_TLS"
    if isinstance(exc, PermissionError):
        return "E_PERMISSION"
    if isinstance(exc, OSError):
        return "E_DISK" if exc.errno == 28 else "E_NETWORK"
    if getattr(exc, "code", None) in (101, "101"):
        return "E_AUTH"
    if getattr(exc, "code", None) == 3:
        return "E_QUOTA"
    if getattr(exc, "code", None) == 9:
        return "cancelled"
    text = str(exc) if isinstance(exc, (ValueError, RuntimeError, AccountError)) else ""
    for words, code in (
        (("已有提交尝试", "重复提交"), "E_ATTEMPT"), (("今日干跑", "只读验收", "10 分钟"), "E_DRYRUN"),
        (("确认无效", "确认已", "确认过期", "逐次确认"), "E_CONFIRM"),
        (("成员已存在", "重复登记"), "E_DUPLICATE"), (("未登记", "选择本人", "成员不存在", "成员表为空"), "E_MEMBER"),
        (("凭证", "token", "已消耗"), "E_AUTH"), (("已有任务", "已有抓号", "请等", "授权窗口"), "E_BUSY"),
        (("响应", "身份", "打卡点"), "E_RESPONSE"), (("恢复未完成",), "E_RECOVERY"),
        (("本机记录", "记录文件损坏"), "E_STATE"),
        (("守护",), "E_WATCHDOG"), (("代理", "PAC"), "E_PROXY"), (("证书安装",), "E_CA"),
        (("额度",), "E_QUOTA"), (("ZIP", "私有", "应用数据"), "E_EXPORT"),
        (("必填", "输入", "格式"), "E_INPUT"), (("响应", "身份", "打卡点"), "E_RESPONSE"),
    ):
        if any(word in text for word in words):
            return code
    return "E_UNKNOWN"


class EventLog:
    MAX_EVENTS = 500

    def __init__(self, directory=None):
        self.directory = Path(directory) if directory is not None else None
        self.lock = threading.RLock()
        self.events, self.seq = [], 0
        self.started = time.monotonic()
        self.clock = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8)))
        self.stage = "ui"
        self.last_write = 0
        self.previous = None
        if self.directory:
            path = self.directory / "desktop-events.json"
            try:
                if path.is_file() and path.stat().st_size <= 512 * 1024:
                    self.previous = self.sanitize(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, OSError):
                pass

    @classmethod
    def sanitize(cls, raw):
        if not isinstance(raw, dict) or not isinstance(raw.get("events"), list):
            return None
        out = {"schema": 1, "build": raw.get("build") if raw.get("build") in ("desktop-0.3.0-test", "desktop-0.4.0-test", "desktop-0.4.1-test", "desktop-0.4.2-test", "desktop-0.4.3-test", "desktop-0.4.4-test", "desktop-0.4.5-test", "desktop-0.4.6-test", "desktop-0.4.7-test", "desktop-0.4.8-test", "desktop-0.4.9-test", "desktop-0.4.10-test", "desktop-0.4.11-test", "desktop-0.4.12-test", "desktop-0.4.13-test", "desktop-0.4.14-test", "desktop-0.4.15-test", "desktop-0.5.0-terminal-test", "desktop-0.5.1-terminal-test", "desktop-0.5.2-terminal-test", "desktop-0.6.0-studio-test", "desktop-0.7.0-retro-test", "desktop-0.7.1-retro-test", "desktop-0.7.2-retro-test", "desktop-0.7.3-retro-test", "desktop-0.7.4-retro-test", "desktop-0.7.5-retro-test", "desktop-0.7.6-retro-test", "desktop-0.7.7-retro-test", "desktop-0.7.8-retro-test", "desktop-1.0.0") else "unknown", "events": []}
        for event in raw["events"][-cls.MAX_EVENTS:]:
            if (isinstance(event, dict) and isinstance(event.get("stage"), str) and isinstance(event.get("code"), str) and
                event.get("stage") in STAGES and event.get("code") in CODES and
                event.get("level") in ("INFO", "WARN", "ERROR")):
                clean = {k: event[k] for k in ("stage", "code", "level")}
                clean.update({k: v for k, v in event.items() if k in NUMBERS | {"ms", "seq"} and type(v) is int and 0 <= v < 2 ** 31})
                clean.update(safe_context(event))
                out["events"].append(clean)
        return out

    def emit(self, stage, code, level="INFO", **values):
        if not isinstance(stage, str) or not isinstance(code, str) or stage not in STAGES or code not in CODES or level not in ("INFO", "WARN", "ERROR"):
            return
        safe = {k: v for k, v in values.items() if k in NUMBERS and type(v) is int and 0 <= v < 2 ** 31}
        safe.update(safe_context(values))
        with self.lock:
            self.seq += 1
            self.stage = stage
            event = {"seq": self.seq, "ms": int((time.monotonic() - self.started) * 1000),
                     "stage": stage, "code": code, "level": level, **safe}
            self.events.append(event)
            self.events = self.events[-self.MAX_EVENTS:]
            now = time.monotonic()
            if self.directory and (now - self.last_write >= 1 or level != "INFO" or code in
                                   ("valid", "invalid", "pending", "restored", "dryrun_ok", "write_start")):
                try:
                    self.directory.mkdir(parents=True, exist_ok=True)
                    atomic_json(self.directory / "desktop-events.json", self.snapshot())
                    self.last_write = now
                except OSError:
                    pass  # Log persistence must not break network recovery.

    def snapshot(self):
        with self.lock:
            return {"schema": 1, "build": BUILD, "events": copy.deepcopy(self.events),
                    "dropped": max(0, self.seq - len(self.events))}

    def since(self, seq):
        return [event for event in self.snapshot()["events"] if event["seq"] > seq]


def render(event, started=None, details=True):
    # User-facing time follows the client's Asia/Shanghai timezone, not host defaults.
    timezone = datetime.timezone(datetime.timedelta(hours=8))
    moment = started or datetime.datetime.now(timezone)
    label = moment.strftime("%H:%M:%S.%f")[:-3]
    if not details:
        counters = " · ".join(label + "=" + str(event[key]) for key, label in
            (("remaining", "剩余秒数"), ("elapsed", "已等待秒数"), ("duration_ms", "用时毫秒"),
             ("requests", "收到信息条数")) if key in event)
        error = "（错误码：" + event["code"] + "）" if event["level"] == "ERROR" else ""
        return "[{}] [{}] {}{}{}".format(label, STAGES[event["stage"]], CODES[event["code"]], error,
            " · " + counters if counters else "")
    suffix = " · ".join(NUMBER_LABELS[k] + "=" + str(event[k]) for k in sorted(NUMBERS) if k in event)
    context = safe_context(event)
    if context:
        detail = " / ".join(OPERATIONS.get(v, v) if k == "operation" else v for k, v in context.items())
        suffix = detail + (" · " + suffix if suffix else "")
    return "[{}] [{}] [{}] {} {}{}".format(label, event["level"], STAGES[event["stage"]], event["code"],
                                          CODES[event["code"]], " · " + suffix if suffix else "")
