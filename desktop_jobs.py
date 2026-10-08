# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Desktop runner: progress, conservative write ledger and explicit read-only verification."""
import datetime
import json
import math
import re
import time
from pathlib import Path

from desktop_events import classify, fault_context
from desktop_progress import clear_check, clear_review, login_required, signature, mark_submitted
from lepao.auth import AuthState
from lepao.pipeline import Pipeline
from lepao.state import LocalState
from lepao.v3api import V3Error
from desktop_storage import atomic_json


class DesktopState(LocalState):
    """Atomic desktop ledger writes; corrupt evidence must never silently disappear."""
    def __init__(self, path):
        file = Path(path)
        self.path, self.dir = str(file), str(file.parent)
        file.parent.mkdir(parents=True, exist_ok=True)
        self.data = {"dryruns": [], "submissions": [], "watch_log": []}
        if file.exists():
            try:
                value = json.loads(file.read_text(encoding="utf-8"))
                if not isinstance(value, dict) or any(not isinstance(value.get(k, []), list) or any(not isinstance(x, dict) for x in value.get(k, [])) for k in self.data):
                    raise ValueError()
                self.data.update(value)
            except (ValueError, UnicodeError):
                raise ValueError("本机记录文件损坏") from None

    def _persist(self):
        atomic_json(self.path, self.data)

METHODS = {
    "get_term_list": "auth", "get_school_info": "auth", "before_run": "rules",
    "get_term_run_record": "quota", "get_timestamp": "clock", "get_oss_sts": "upload",
    "stop_run": "submit", "record_detail": "verify",
}


def response_kind(value):
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, (int, float)):
        return "number"
    return "string" if isinstance(value, str) else "other"


class ClientView:
    def __init__(self, client, platform, writable=False, expected_uid=None):
        self.client, self.platform, self.writable = client, platform, writable
        self.submitted = False
        self.expected_uid = expected_uid

    def __getattr__(self, name):
        if name not in METHODS:
            raise ValueError("不允许未登记的业务操作")
        stage = METHODS[name]
        def call(*args, **kwargs):
            if self.platform.job_stop.is_set() and not self.writable:
                raise V3Error(9, "read-only task cancelled")
            if name in ("get_oss_sts", "stop_run") and not self.writable:
                raise ValueError("只读任务禁止上传和提交")
            if name == "stop_run":
                if self.submitted:
                    raise ValueError("禁止重复提交")
                self.submitted = True
            if name == "get_oss_sts" and self.writable:
                self.platform.write_started = True
                self.platform.ui_events.emit("upload", "write_start", "WARN")
            self.platform.ui_events.emit(stage, "request", method=name)
            began = time.monotonic()
            kind, check = "other", "request"
            try:
                result = getattr(self.client, name)(*args, **kwargs)
                kind, check = response_kind(result), "shape"
                # getTermList may decrypt directly to a JSON array. Do not impose
                # object-only validation on this endpoint or relax other methods.
                term_array = name == "get_term_list" and isinstance(result, list)
                if term_array and any(not isinstance(item, dict) for item in result):
                    raise ValueError("学期列表响应格式无效")
                if name != "get_timestamp" and not isinstance(result, dict) and not term_array:
                    raise ValueError("业务响应格式无效")
                if isinstance(result, dict) and str(result.get("status")) == "101":
                    check = "expired"
                    raise V3Error(101, "credential expired")
                if isinstance(result, dict) and self.expected_uid is not None and result.get("uid") is not None and str(result["uid"]) != str(self.expected_uid):
                    check = "identity"
                    raise ValueError("业务响应身份不符")
                if name == "get_term_run_record":
                    check = "quota_items"
                    if not isinstance(result, dict) or not isinstance(result.get("list"), list):
                        raise ValueError("当天额度响应格式无效")
                    for record in result["list"]:
                        try:
                            valid = isinstance(record, dict) and math.isfinite(float(record["distance"])) and float(record["distance"]) >= 0 and int(record["start_time"]) >= 0
                        except (ValueError, TypeError, KeyError, OverflowError):
                            valid = False
                        if not valid:
                            raise ValueError("当天额度响应格式无效")
                self.platform.ui_events.emit(stage, "response", method=name, response_kind=kind,
                                             duration_ms=int((time.monotonic() - began) * 1000))
                return result
            except Exception as exc:
                if classify(exc) == "E_AUTH":
                    invalidate = getattr(self.platform, "invalidate_login", None)
                    if callable(invalidate):
                        invalidate()
                self.platform.ui_events.emit(stage, classify(exc), "ERROR", method=name,
                    response_kind=kind, response_check=check, **fault_context(exc, self.platform.job_kind or "build"))
                exc._desktop_reported = True
                raise
        return call


class AuthView:
    def __init__(self, auth, platform, writable=False):
        self.auth, self.platform, self.writable = auth, platform, writable

    def __getattr__(self, name):
        return getattr(self.auth, name)

    def make_client(self, pace=0.0):
        return ClientView(self.auth.make_client(pace=pace), self.platform, self.writable, expected_uid=self.auth.uid)


class ProgressPipeline(Pipeline):
    def __init__(self, auth, state, policy, platform):
        super().__init__(auth, state, dict(policy, max_per_day=1), verbose=False, stop_event=platform.job_stop)
        self.platform = platform

    def _config(self, client):
        # The frozen upstream ignores non-101 V3Errors at this gate. Desktop must
        # fail closed on every probe failure, not treat a public school query as auth.
        client.get_term_list()
        school = client.get_school_info()
        if not isinstance(school, dict) or not isinstance(school.get("school_name"), str) or not school["school_name"].strip():
            raise ValueError("学校信息响应格式无效")
        self.log("[0] 凭证预检通过")
        self._sleep(self.rnd.uniform(0.6, 1.5))
        return self._before(client)

    def log(self, message):
        # Recognize fixed markers only; never send original logs (identity/response/body) to the UI.
        for prefix, stage, code in (("[0]", "auth", "ok"), ("[1]", "rules", "ok"),
                                    ("[2]", "quota", "ok"), ("[3]", "clock", "ok"),
                                    ("[4.", "generate", "sample_retry"), ("[6]", "package", "ok"),
                                    ("[6b]", "upload", "response"), ("[7] stopRun", "submit", "start"),
                                    ("[7] 响应", "submit", "response"), ("[8]", "verify", "response"),
                                    ("[dry-run]", "done", "dryrun_ok")):
            if str(message).startswith(prefix):
                attempt = re.match(r"\[4\.(\d{1,2})\]", str(message))
                self.platform.ui_events.emit(stage, code, **({"attempt": int(attempt.group(1)) + 1} if attempt else {}))
                return
        if str(message).startswith("[FATAL]"):
            # An earlier client error already has a safe category; do not overwrite it with a generic one.
            if not self.platform.ui_events.events or self.platform.ui_events.events[-1]["level"] != "ERROR":
                self.platform.ui_events.emit(self.platform.ui_events.stage, "E_GENERATE" if self.platform.ui_events.stage == "generate" else "E_UNKNOWN", "ERROR")

    def _gen_track(self, *args, **kwargs):
        self.platform.ui_events.emit("generate", "start")
        result = super()._gen_track(*args, **kwargs)
        self.platform.ui_events.emit("generate", "ok", point_count=len(result[0]), distance_m=round(result[3] * 1000), used_seconds=int(result[2]))
        return result


def watch(bridge, platform, auth, state, record_id):
    client = ClientView(auth.make_client(pace=0.8), platform, expected_uid=auth.uid)
    for index in range(3):
        bridge._job["message"] = "正在只读复核记录（{}/3）…".format(index + 1)
        platform.ui_events.emit("verify", "start", round=index + 1)
        detail = client.record_detail(record_id)
        if not isinstance(detail, dict):
            raise ValueError("复核响应格式无效")
        if detail.get("uid") is not None and str(detail["uid"]) != str(auth.uid):
            raise ValueError("复核响应身份不符")
        status, reason = str(detail.get("record_status")), str(detail.get("record_failed_reason") or "")
        state.log_watch(record_id, status, reason)
        positive = not reason.strip() or ("有效" in reason and not any(x in reason for x in ("无效", "异常", "不")))
        if status == "1" and positive:
            platform.ui_events.emit("verify", "valid")
            return "复核通过：服务端判定记录有效。"
        if status == "5" or (status == "1" and not positive):
            platform.ui_events.emit("verify", "invalid", "WARN")
            return "服务端判定记录无效。请在官方小程序查看具体原因；不会自动补交。"
        if index < 2:
            platform.ui_events.emit("verify", "verify_wait", wait_seconds=45)
            if platform.job_stop.wait(45):
                raise V3Error(9, "verification cancelled")
    platform.ui_events.emit("verify", "pending", "WARN")
    return "记录已受理，服务端尚未终判。稍后点击复核，不要重复提交。"


def run_pending(bridge, platform):
    with bridge._lock:
        pending, bridge._pending_run = bridge._pending_run, None
    if pending is None:
        return
    member, kind, attempt_key = pending
    if kind == "build":
        with bridge._lock:
            clear_check(bridge, platform, member)
    platform.job_kind, platform.write_started = kind, False
    platform.job_member = member
    platform.ui_events.emit("auth" if kind != "watch" else "verify", "start")
    try:
        with bridge._lock:
            reg = bridge.AccountRegistry(bridge._config_path())
            auth = AuthState(reg, member)
            if not auth.token or not auth.uid or (auth.consumed_at and kind != "watch"):
                raise ValueError("凭证缺失或已消耗")
            state = DesktopState(str(bridge._data_dir / "state.json"))
        if kind == "watch":
            clear_review(bridge, member)
            records = [x for x in state.data.get("submissions", []) if str(x.get("uid")) == str(auth.uid) and x.get("record_id")]
            records += [x for key, x in sorted(bridge._attempts.items()) if key.endswith(":" + str(auth.uid)) and x.get("record_id")]
            if not records:
                raise ValueError("没有可复核的本机记录。请先到官方小程序核对，禁止重复提交。")
            bridge._job["message"] = watch(bridge, platform, auth, state, records[-1]["record_id"])
            bridge._job.update(reviewed_member=member, reviewed_record=records[-1]["record_id"],
                               reviewed_login=signature(auth), reviewed_day=bridge._auth_fingerprint(auth)[0])
            return
        pipeline = ProgressPipeline(AuthView(auth, platform, kind == "submit"), state, reg.merged_policy(member), platform)
        result, code = pipeline.run(submit=kind == "submit")
        if kind == "submit":
            with bridge._lock:
                if code in (2, 3) and not platform.write_started:
                    bridge._attempts.pop(attempt_key, None)
                else:
                    bridge._attempts[attempt_key] = {"exit": code, "record_id": (result or {}).get("record_id"),
                                                    "write_started": platform.write_started, "at": datetime.datetime.now().isoformat()}
                atomic_json(bridge._data_dir / "mobile_jobs.json", bridge._attempts)
            if isinstance(result, dict) and result.get("record_id"):
                with bridge._lock:
                    mark_submitted(bridge, platform, member, auth, result["record_id"])
                platform.ui_events.emit("verify", "accepted")
                clear_review(bridge, member)
                bridge._job["message"] = watch(bridge, platform, auth, state, result["record_id"])
                bridge._job.update(reviewed_member=member, reviewed_record=result["record_id"],
                                   reviewed_login=signature(auth), reviewed_day=bridge._auth_fingerprint(auth)[0])
            else:
                code_name = "E_AUTH" if code == 2 and not platform.write_started else "E_QUOTA" if code == 3 and not platform.write_started else "E_ATTEMPT"
                if code_name == "E_AUTH":
                    with bridge._lock:
                        login_required(bridge, platform, member, auth)
                platform.ui_events.emit("done", code_name, "WARN")
                bridge._job["message"] = "凭证失效或额度已满，未进入写入。" if code_name in ("E_AUTH", "E_QUOTA") else "提交结果不确定。先到官方小程序核查，不要直接重试。"
        elif code == 0:
            with bridge._lock:
                bridge._dryrun_ok[member] = bridge._auth_fingerprint(auth)
                platform.checked_at[member] = time.monotonic()
                platform.checked_login[member] = signature(auth)
                platform.previews[member] = {"distance": round(float(result.get("stopRun_biz", {}).get("distance", 0)), 2),
                                            "used_time": int(result.get("stopRun_biz", {}).get("used_time", 0)),
                                            "points": int(result.get("track_points", 0))}
            platform.ui_events.emit("done", "dryrun_ok")
            bridge._job["message"] = "只读验收通过。样本来自生成模板，并非实际运动采集；未上传、未提交。"
        else:
            category = {2: "E_AUTH", 3: "E_QUOTA", 9: "cancelled"}.get(code, "E_UNKNOWN")
            if category == "E_AUTH":
                with bridge._lock:
                    login_required(bridge, platform, member, auth)
            platform.ui_events.emit("done", category, "WARN")
            bridge._job["message"] = "只读任务已停止。" if code == 9 else "只读验收未完成。请查看实时日志的阶段与错误提示。"
    except Exception as exc:
        if classify(exc) == "E_AUTH":
            with bridge._lock:
                if "auth" in locals():
                    login_required(bridge, platform, member, auth)
        if getattr(exc, "_desktop_reported", False) is not True:
            platform.ui_events.emit(platform.ui_events.stage, classify(exc), "ERROR",
                                    **fault_context(exc, kind))
        bridge._job["message"] = ("操作未完成。已保留本次提交尝试，请先核查，不要重试。" if kind == "submit"
                                  else "操作未完成，请查看错误码和下一步建议。")
    finally:
        bridge._job["running"] = False
        platform.job_kind = ""
        platform.job_member = ""
