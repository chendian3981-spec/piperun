# pipeRun 1.0.0 · Windows

免费提供、源码公开的 Windows 10/11 x64 客户端，只保留当前像素控制台电脑版。
原作者 **dan-cun** · 原始仓库 https://github.com/dan-cun/lepao3 。
本项目为衍生版，采用 **LRL-1.0 非商业研究许可**：仅供学习、不可牟利。
使用、修改、再发布须保留 [LICENSE](LICENSE)、[NOTICE](NOTICE)、[免责声明](DISCLAIMER.md) 和源文件声明。

## 下载使用

从 Releases 下载 `pipeRun-desktop-1.0.0.zip`，解压后打开 `pipeRun.exe`。
运行环境、界面、字体均内置，不需要 Python、Java、Node、WebView2 或代理软件，不在线下载依赖。
仍需电脑版微信、本人登录和正常网络；证书及临时代理授权须自己确认。

1. 添加账号，学号必须与小程序一致。
2. 先点「获取账号」，完成授权。倒计时出现后，在「数体智慧体育」小程序内登录一次，不是登录微信。
3. 等凭证保存和网络恢复后，点「检查账号」。只读检查不上传、不提交。
4. 仅在获许可测试范围内核对生成模板及账号后确认；两项确认默认不勾。
5. 查看结果。结果不明先到官方小程序核查，别重复提交。

教程可从「F1 说明 / 设置 → 快速上手」重新打开。支持鼠标、1–5、上下、Enter、Tab、Esc。
重新获取登录后检查、提交、查看的完成状态刷新，但当天防重复尝试账本不会清除。
记录由模板生成，**并非实际运动采集**，不保证有效。禁止商用、牟利及代打卡。
问题反馈只发送程序导出的脱敏诊断，不要发送账号配置、证书或私钥。

## 构建最新版

以下仅供开发者，运行 EXE 的普通用户不用配置环境。
Windows x64 / Python 3.14：

```powershell
py -3.14 -m pip install -r requirements-desktop.txt
py -3.14 tools/build_desktop.py --skip-selfcheck
```

产物统一在 `release/`：最新版 EXE、完整分发 ZIP、源码 ZIP、构建说明及 SHA256SUMS.txt。
该目录和 `build/` 均不会提交到 Git。去掉 `--skip-selfcheck` 可加做离线依赖自检；
离线自检不会读取账号、联网、安装证书或修改系统代理，不等于真实业务验收。

仓库只含当前桌面入口、Retro 界面、抓号/证书/存储/诊断、网络恢复、提交保护、
依赖字体及许可、冻结上游核心和构建校验。没有手机工程、VPN、网页控制台、旧版界面或旧版 EXE。
核心 `desktop_*.py` 已独立，不依赖本仓库之外的旧 pipeRun 目录。
历史兼容的本机账本文件名仍为 `mobile_jobs.json`，这不是手机端模块，请勿删除它来重复提交。

可选快速离线回归：

```powershell
py -3.14 -m unittest discover -s tests
```

当前验证限源码导入、离线状态测试、界面类型加载和打包完整性。
真实业务及干净 Windows 电脑验收仍待使用者完成。发布附件说明见 [RELEASING.md](RELEASING.md)。
