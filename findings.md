# 工作发现

- 目标需求是 EmotiScreen V0.3 情境陪伴窗口，当前仓库原来是 V1.0 声学能量/颜色可视化，已检查代码后替换不匹配的决策与 UI 路径。
- 本机模型位于 `F:\codex\model\Clef-Flash-Q4_K_M.gguf`，配套程序为 `F:\codex\model\llama\llama-server.exe`。CLI 直接文本生成不是 Clef 的运行方式；实际接口是 llama.cpp `/v1/systemone`。
- 用本机模型的直接短请求曾因为 `--ubatch-size 512` 小于 617 输入 token 而返回 500；增至 1024 后接口正常。本机服务设置只绑定 `127.0.0.1`，未使用网络下载或云端 API。
- 本机 System One 实测：成绩→celebrate；普通闲聊→none；反话态度→sarcastic且静默；他人成绩→relevance=other且静默；未完成语句→incomplete/wait；难过→support。模型概率尚未校准。
- llama.cpp 的 choice `confidence` 与概率分布单独保留；`ResponsePolicy` 另外要求 attitude=explicit，避免明确反话导致弹窗。
- 开源桌面材质调研见 `docs/opensource-guidance.md`：`window-vibrancy` 提供 Windows Acrylic/macOS Vibrancy，Linux 依赖合成器；当前选择保留 Python/Tk 的增量改造，Windows 原生尝试、其他平台回退。
- 模型服务器已停止；模型文件不复制进 Git 仓库。

## 本次音频到窗口链路验证

- 用户明确要求停用 ASR；实时链路改为本地 NumPy 特征和连续状态跟踪，不把音频交给 Clef 或云端。
- 参考并只适配了 pyAudioAnalysis 的短帧能量、零交叉、谱特征/自相关片段；Tk 动画参考 TkAnimator；拖动/关闭交互参考 CTkMessagebox；Windows Acrylic 结构参考 window-vibrancy 0.7.1。源码文件、许可证及本地差异记在 `docs/opensource-guidance.md` 与 `THIRD_PARTY_NOTICES.md`，未克隆上游库。
- 从 Zenodo 官方 RAVDESS 16k 归档临时取到了 Actor 01 前缀的 24 个 WAV（中性4、平静8、开心8、悲伤4），未把语料写入仓库。
- 当前规则在这24段上的状态数：中性4/4低唤醒；平静7/8低唤醒；开心2/8低唤醒、4/8高唤醒、2/8不确定；悲伤4/4低唤醒。说明它只反映声学唤醒度，不能区分中性/平静/悲伤；情绪分类准确率未知。
- 单段 WAV 试听只报告状态。实时反馈须连续两个窗确认“高唤醒→低唤醒”转换，避免一开始较安静就误弹。用 RAVDESS 开心强度→悲伤片段驱动 Tk 窗口，实际得到 support 卡片并观察到 `popup_visible=True`。
- 特征分析曾因绝对 RMS 门槛拒绝 16k 录音；用 pyAudioAnalysis 的去直流/峰值归一化思路消除录音增益依赖，并补上低增益回归测试。
