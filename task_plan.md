# EmotiScreen 当前任务计划

## 目标

取消本地 ASR 实时链路，复用开源音频特征和 Tk 动效实现片段，完成连续音频窗 → 状态跟踪 → 策略反馈 → 安抚窗口渐入/渐隐；新增组件保持在现有 Python/Tkinter 架构内，不克隆完整上游仓库。

## 工作项

- [x] 检查项目状态、原始需求、本地 model 目录及已有改动。
- [x] 搜索 pyAudioAnalysis、TkAnimator、CTkMessagebox、window-vibrancy 官方仓库/许可证，建立本地适配出处表。
- [x] 写音频特征→反馈与稳定状态切换的精简回归测试。
- [x] 保留短帧能量、自相关基频、过零率、谱重心/通量的 NumPy 适配实现。
- [x] 接入单 worker 连续分析、连续窗口状态确认、WAV 输入和保守安抚门控。
- [x] 将拖动、渐入渐隐、低幅脉冲机制按开源片段适配到原生 Tk Canvas/Toplevel。
- [x] 在临时目录分析 RAVDESS Actor 01 的24段真实16 kHz WAV，并逐类记录低/高唤醒状态；结果显示无法把 neutral/calm/sad 区分为语义情绪，准确率仍未知。
- [x] 复验相关目标测试、启动检查、编译和 Tk 实际音频状态切换到安抚窗口的生命周期。
- [x] 审核差异与音频→反馈→UI 临界路径。
- [ ] 按指定邮箱提交、推送 main、确认远端 SHA。

## 约束

- 不调用 ASR，不把实时声音交给 Clef 或云端。
- AudioStateTracker 稳定切换后才触发 UI；不确定/低质量要静默。
- 不复制开源完整仓库、完整 GUI、预训练权重或测试语料。
- 有效维护按 AGENTS.md 要求以 `English: 中文内容` 提交并推送。
