# EmotiScreen 音频分析到渐入安抚反馈实施计划

> 历史实施计划：初版V0.3验收已完成；后续 UI/连续主题/上下文任务见 `2026-10-08-emotiscreen-ambient-ui.md`。

> 本计划在当前会话中直接实施，使用复选框记录步骤。

**目标：** 从用户主动开启的本地音频输入，经 Python 声学分析与保守门控，驱动渐入安抚窗口；不使用 ASR。

**架构：** 从 pyAudioAnalysis 选取并改写短帧特征算法，NumPy 分析器输出质量标记与 fail-closed 状态；从 TkAnimator/CTkMessagebox 选取渐变/脉冲/拖动片段适配到当前窗口。Tk 主线程通过单后台 worker 投递音频快照，`AudioFeedbackPolicy` 管理回应节制，复用现有 `ComfortWindow`。

**技术栈：** Python 3.11+、NumPy、Tkinter、可选 sounddevice；不新增情绪模型、ASR、数据库或云依赖。

**设计文档：** `docs/superpowers/specs/2026-10-08-emotiscreen-v03-design.md`

## 全局约束

- 音频只在内存中处理，不写盘、不上传。
- 麦克风仅在用户明确启动后读取；暂停、停止和 DND 优先于迟到结果。
- 声学线索不是心理诊断或语义情绪真值；不确定时保持安静。
- 测试仅保留能证明音频分析、失败关闭、策略到弹窗链路的必要用例。
- GitHub 提交邮箱 `2966684515@qq.com`；提交信息采用 `English: 中文内容`；维护完成推送 main。

---

## 任务 1：声学特征与保守估计

**涉及文件：**
- Create: `emotionscreen/core/acoustic.py`
- Modify: `emotionscreen/core/models.py`
- Test: `tests/test_pipeline.py`

**接口：** `AcousticEmotionAnalyzer.analyze(samples: np.ndarray, sample_rate: int) -> AcousticAnalysis`; analysis 包含有效性、声学特征、粗粒度状态、未校准规则分和短说明。

- [x] 为稳定低频音、变调信号、静音、增益变化和过短片段写精简确定性测试，并先运行确认新增行为失败。
- [x] 从 `pyAudioAnalysis/ShortTermFeatures.py` 适配短帧能量、过零率、谱重心/通量与自相关基频；仅保留所需函数，不复制仓库/分类器，也不依赖 ASR/ML 模型。
- [x] 以显式阈值输出 `low_arousal` / `elevated` / `uncertain`；低质量、不确定、无基频结果不得进入回应。
- [x] 重跑该测试，检查有限值、范围和实际结果。

## 任务 2：音频回应门控和后台 worker

**涉及文件：**
- Create: `emotionscreen/core/audio_runtime.py`
- Modify: `emotionscreen/core/policy.py`
- Test: `tests/test_pipeline.py`、`tests/test_runtime.py`

**接口：** `AudioAnalysisWorker.submit(samples, sample_rate)`、`poll() -> list[AcousticAnalysis]`、`close()`；`AudioFeedbackPolicy.evaluate(analysis, ...) -> ResponseEvent | None`。

- [x] 测试连续窗口从高唤醒稳定切到低唤醒才得到短时 support 事件；启动即低唤醒、高唤醒/低规则分/静音、重复、冷却、DND、暂停和已有弹窗均不触发新事件。
- [x] 实现单线程最新任务 worker，复制提交数组、忙时只留最新快照，关闭时停止接收任务。
- [x] 重跑音频策略与 worker 的目标测试。

## 任务 3：麦克风、界面与渐入反馈

**涉及文件：**
- Modify: `emotionscreen/config.py`、`config.json`
- Modify: `emotionscreen/ui/window.py`、`emotionscreen/ui/comfort_window.py`
- Modify: `tests/test_config_ui.py`

- [x] 删除 ASR loader/adapter 及 UI ASR 轮询；`live` 改为麦克风+Python 分析，Mock 默认仍不启动麦克风。
- [x] 麦克风每个配置窗口提交一次快照，后台分析结果回到 Tk 主线程后执行音频策略并显示 ComfortWindow。
- [x] 适配 TkAnimator 的分步 alpha/脉冲曲线与 CTkMessagebox 的拖动锚点；改用可取消的 `after`，淡入可见、静态/系统减少动态效果时直接显示。
- [x] 运行相关配置与 UI 生命周期 smoke check；检查启动失败和关闭时释放输入/线程。

## 任务 4：公开音频验证、文档和交付

**涉及文件：**
- Modify: `README.md`、`docs/superpowers/specs/2026-10-08-emotiscreen-v03-design.md`
- Optional temporary files: `%TEMP%` only; never add dataset media to Git.

- [x] 从官方 RAVDESS 16 kHz 数据集临时提取24段 Actor 01 WAV，运行真实分析并记录状态覆盖；样本只从文件名取标签，未把标签送入算法。
- [x] 报告局限：neutral/calm/sad 多被归为低唤醒，语义情绪准确率未知；合成信号只验收技术链路。
- [x] 运行目标 pytest、`compileall`、`python main.py --check` 和 Tk 实际窗口转变验证；检查差异。
- [ ] 配置提交邮箱，使用 `English: 中文内容` 提交，推送 main 并核对远端 SHA。
