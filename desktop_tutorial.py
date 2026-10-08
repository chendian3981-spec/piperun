# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---
"""Short desktop onboarding; reading this is not submission consent."""

TITLE = "第一次用，照着这几步来"
INTRO = "先登录电脑版微信，下面都只操作本人账号。"
STEPS = [
    {"title": "[1] 添加账号", "body": "称呼随你填，学号要和小程序里一致。", "important": False},
    {"title": "[2] 先启动，再登录小程序", "body": "先点「获取账号」，按电脑弹窗完成授权。\n等倒计时出现后，在「数体智慧体育」小程序里登录本人账号一次就行。\n不是登录微信，也不用重启小程序。", "important": True},
    {"title": "[3] 检查账号", "body": "等登录信息已保存、网络已恢复，再点「检查账号」。这一步不上传，也不提交。", "important": False},
    {"title": "[4] 确认提交", "body": "先看清账号和说明，只在获许可测试范围内确认。不确定就取消。", "important": False},
    {"title": "[5] 查看结果", "body": "结果没出来就先去官方小程序核查，别重复提交。", "important": False},
]
TIP = "报错时导出「诊断 ZIP」发回就好，别发账号配置或证书。"
DISCLAIMER = ("本软件免费提供，源码公开，采用 LRL-1.0 非商业研究许可，禁止商用或牟利。"
              "不提供代打卡；记录由模板生成，并非实际运动采集，不保证有效。"
              "请遵守学校及平台规定，使用前阅读项目许可和免责声明。")
ATTRIBUTION = "pipeRun 衍生版 · 原作者 dan-cun\nhttps://github.com/dan-cun/lepao3\n乐跑研究协议 1.0 / LRL-1.0 · 非商业授权"
