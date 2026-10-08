# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Fresh bridge instances with no shared live application globals."""
import importlib.util
from pathlib import Path

def isolated_bridge():
    source = Path(__file__).resolve().parents[1] / "desktop_bridge.py"
    spec = importlib.util.spec_from_file_location("piperun_test_bridge", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
