# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""In-memory login-scoped progress. Never deletes attempts or writes credentials."""
import hashlib
import time


def signature(auth):
    # issued_at distinguishes a newly captured login even if the token repeats.
    return (auth.uid, hashlib.sha256(auth.token.encode()).hexdigest(), auth.issued_at)


def clear_check(bridge, platform, member):
    bridge._dryrun_ok.pop(member, None)
    for name in ("checked_at", "checked_login", "previews"):
        values = getattr(platform, name, None)
        if isinstance(values, dict):
            values.pop(member, None)
    confirmation = bridge._confirmation
    if isinstance(confirmation, dict) and confirmation.get("member") == member:
        bridge._confirmation = None


def clear_review(bridge, member):
    if bridge._job.get("reviewed_member") == member:
        for name in ("reviewed_member", "reviewed_record", "reviewed_login", "reviewed_day"):
            bridge._job.pop(name, None)


def login_required(bridge, platform, member, auth):
    clear_check(bridge, platform, member)
    clear_review(bridge, member)
    clear_submission(platform, member)
    values = getattr(platform, "required_login", None)
    if not isinstance(values, dict):
        platform.required_login = values = {}
    values[member] = signature(auth)


def login_saved(bridge, platform, member):
    clear_check(bridge, platform, member)
    clear_review(bridge, member)
    clear_submission(platform, member)
    values = getattr(platform, "required_login", None)
    if isinstance(values, dict):
        values.pop(member, None)


def usable(platform, member, auth, consumed_ok=False):
    values = getattr(platform, "required_login", {})
    needs_login = isinstance(values, dict) and values.get(member) == signature(auth)
    return bool(auth.uid and auth.token and (consumed_ok or not auth.consumed_at) and not needs_login)


def clear_submission(platform, member):
    # UI receipts are session-only. Never remove or modify the durable attempt ledger.
    values = getattr(platform, "submission_receipts", None)
    if isinstance(values, dict):
        values.pop(member, None)


def mark_submitted(bridge, platform, member, auth, record_id):
    if not record_id:
        return
    values = getattr(platform, "submission_receipts", None)
    if not isinstance(values, dict):
        platform.submission_receipts = values = {}
    values[member] = (signature(auth), bridge._auth_fingerprint(auth)[0], record_id)


def submitted(bridge, platform, member, auth, record_id):
    values = getattr(platform, "submission_receipts", {})
    return bool(record_id and usable(platform, member, auth, consumed_ok=True) and
                isinstance(values, dict) and values.get(member) ==
                (signature(auth), bridge._auth_fingerprint(auth)[0], record_id))


def checked(bridge, platform, member, auth, now=None):
    stamps = getattr(platform, "checked_at", {})
    logins = getattr(platform, "checked_login", {})
    age = (time.monotonic() if now is None else now) - stamps.get(member, float("-inf")) if isinstance(stamps, dict) else float("inf")
    return bool(usable(platform, member, auth) and 0 <= age <= 600 and
                isinstance(logins, dict) and logins.get(member) == signature(auth) and
                bridge._dryrun_ok.get(member) == bridge._auth_fingerprint(auth))


def reviewed(bridge, platform, member, auth, record_id):
    job = bridge._job
    return bool(record_id and usable(platform, member, auth, consumed_ok=True) and
                job.get("reviewed_member") == member and job.get("reviewed_record") == record_id and
                job.get("reviewed_login") == signature(auth) and
                job.get("reviewed_day") == bridge._auth_fingerprint(auth)[0])
