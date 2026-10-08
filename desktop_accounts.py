# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Local, reversible account reset. Caller must own the desktop instance lock."""
import datetime
import json
import os
import secrets
from pathlib import Path

from desktop_storage import atomic_json


def reset_accounts(directory):
    directory = Path(directory).resolve(strict=True)
    config = directory / "config.json"
    backups = directory / "account-backups"
    if config.is_symlink() or backups.is_symlink():
        raise ValueError("本机记录路径异常，已保留原文件")
    if (directory / "proxy_backup.json").exists():
        raise ValueError("网络恢复未完成，不能重置账号")
    if not config.exists():
        return  # A clean installation already has no accounts.
    original = config.read_bytes()
    data = json.loads(original.decode("utf-8-sig"))
    if not isinstance(data, dict) or data.get("version") != 2 or not isinstance(data.get("accounts"), dict):
        raise ValueError("本机记录格式损坏，已保留原文件")
    # The ledger is deliberately not cleared, even when credentials are removed.
    ledger = directory / "mobile_jobs.json"
    if ledger.exists() and not isinstance(json.loads(ledger.read_text(encoding="utf-8")), dict):
        raise ValueError("本机记录账本损坏，已保留原文件")
    if not data["accounts"] and not data.get("active") and not data.get("account") and not data.get("auth"):
        return
    backups.mkdir(exist_ok=True)
    backup = backups / (datetime.datetime.now().strftime("%Y%m%d-%H%M%S-%f") + "-" + secrets.token_hex(4) + ".json")
    assert backup.resolve().is_relative_to(directory)
    with backup.open("xb") as handle:
        handle.write(original)
        handle.flush()
        os.fsync(handle.fileno())
    data.update(active="", accounts={})
    data.pop("account", None)
    data.pop("auth", None)
    atomic_json(config, data)
