# EmotiScreen 当前进度

## 本轮交付

- 实时音频不使用 ASR；用户点击开始后，`sounddevice` 将短帧送入有界内存缓冲，由单个后台 worker 用 NumPy 声学特征分析，再由状态跟踪器和反馈策略驱动 Tk 浮层。
- live 监听期间浮层不设自动超时；UI 周期会恢复意外隐藏的浮层。用户手动关闭、暂停、停止或免打扰仍可隐藏。
- 监听时玻璃浮层常驻，底色沿双色渐变缓慢流动、光晕呼吸；稳定状态切换时整片渐变约 0.8 秒平滑换色并更新本地短句。默认动效强度 0.72，静态模式可关闭动画。
- Windows 浮层位置会按显示缩放系数换算，避免 150% 缩放下窗口移出屏幕。浮层可拖动，不抢键盘焦点；暂停、免打扰、停止和关闭仍可控制。
- 会话文本仅留在当前进程内存，总预算最多 2000 单位：中文按字符，英文按本地词法 token；启动为空，关闭即清除。
- 开源实现只取 pyAudioAnalysis 的声学统计、TkAnimator 的颜色插值/步进/正弦脉冲、CTkMessagebox 的拖动锚点和 window-vibrancy 的 Acrylic FFI 结构。来源、许可证与修改位置列于 `THIRD_PARTY_NOTICES.md` 和 `docs/opensource-guidance.md`，没有克隆完整仓库或引入完整上游 GUI。

## 验证证据

- 精简相关测试：17 passed。
- `python main.py --check`：Mock 情境管线通过；合成音频验证 `elevated → low_arousal → support`。
- `python -m compileall -q emotionscreen main.py`：通过。
- Windows Tk 窗口实测：RAVDESS Actor 01 高强度 happy WAV 经后台分析为 elevated (0.720)，连续两窗确认后切到低强度 sad WAV 的 low_arousal (0.706)，反馈依次为 acknowledge 与 support；玻璃浮层持续显示并换色。
- 两次相隔 0.8 秒的屏幕采样在浮层所在区域检测到 31,246 个变化像素；运行窗口保持可交互。
- `git diff --check`：通过。

## 已知边界

- 当前声学规则是唤醒度代理，不是语义情绪识别；Actor 01 的 RAVDESS 探索样本显示 neutral、calm、sad 存在重叠。准确率仍未知，不作悲伤/开心等分类承诺。
- 尚未在目标设备上验证真实麦克风、驱动差异或连续长时监听；实时录音仅在用户主动开始后启用。

## 发布状态

- 当前分支为 `main`。本轮按要求使用邮箱 `2966684515@qq.com` 和“英文前缀：中文内容”提交，并推送到 `origin/main`；SHA 以 Git 提交记录和远端核验结果为准。
