# -*- coding: utf-8 -*-
# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Verify the retained upstream core against its original source fingerprints."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "SOURCE_SNAPSHOT.json"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    expected = json.loads(MANIFEST.read_text(encoding="utf-8"))["sha256"]
    problems = []
    for name, sha in expected.items():
        source = ROOT / name
        if not source.is_file() or digest(source) != sha:
            problems.append("冻结源不一致：" + name)
    for problem in problems:
        print("[FAIL]", problem)
    if problems:
        return 1
    print("[OK] Frozen upstream core: {} retained files unchanged".format(len(expected)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
