# EmotiScreen V0.3

EmotiScreen 是一款本地桌面音频陪伴程序。用户明确开启监听后，程序在内存中分析短音频窗里的 RMS、能量变化、基频、过零率、频谱重心和有声比例。监听期间右下角保持一个环境式毛玻璃浮层，连续音频状态从 low_arousal、elevated 到 uncertain 变化时，色彩渐变和本地安慰短句会在同一窗口里平滑切换；停止监听后浮层渐隐。

**当前实时音频链路不使用 ASR，也不把原始音频发送给 Clef 或其他服务。** 这是传统声学特征启发式，只估计声音低唤醒/活跃/不确定状态；无法从这些特征可靠区分悲伤、疲劳、平静或兴奋等语义情绪。低质量、静音、基频无效和不确定状态会显示中性陪伴主题，不触发悲伤/庆祝等定向回应。该功能不做心理诊断。

## 安装与运行

要求 Python 3.11+、Tkinter、NumPy。默认 `mock` 模式无需麦克风：

```powershell
python -m pip install -r requirements.txt
python main.py
```

主界面支持模拟对话、安抚窗口预览、主题、动效强度、减少动态效果、免打扰和中英文切换。live 监听期间浮层不设自动超时，即使一段时间没有新的状态变化也会保持显示；手动关闭后会暂时隐藏，恢复监听或关闭免打扰时重新出现，暂停、停止或免打扰时则渐隐。

运行无麦克风的处理链路检查：

```powershell
python main.py --check
```

对本地测试 WAV 查看单段声学状态（不安装麦克风）：

```powershell
python main.py --audio-file path\to\sample.wav
```

目前只接受单/双声道、16-bit PCM、最长10秒的 WAV。孤立 WAV 按单段状态显示临时氛围窗；实时监听时则在每次稳定状态变化后持续切换主题。

开发测试：

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest tests/test_pipeline.py tests/test_runtime.py tests/test_config_ui.py -q
```

## 本地麦克风分析

安装麦克风依赖：

```powershell
python -m pip install sounddevice
```

把配置中的 `mode` 设为 `live`，`decision.provider` 设为 `acoustic`，然后启动程序并点击“开始监听”。麦克风只在点击后打开；“暂停”“停止”“免打扰”和关闭窗口会抑制或停止后续处理。

```json
{
  "mode": "live",
  "audio": {
    "sample_rate": 16000,
    "channels": 1,
    "frame_ms": 32,
    "window_seconds": 2.0,
    "device": null
  },
  "decision": {
    "provider": "acoustic",
    "clef_base_url": "http://127.0.0.1:8080",
    "timeout_seconds": 5.0
  }
}
```

音频回调只写入有界内存队列；特征计算在单个后台线程运行，繁忙时只保留最新窗口。程序不录音、不写文件、不保留长期特征。`sounddevice` 不可用或设备启动失败时，界面显示错误并保持静默。

## Clef 的用途

本地 Clef GGUF 与 llama.cpp 可继续用于开发面板中的手工文本情境测试，但当前不接收实时声音，也不参与实时音频情绪分析。Clef 服务必须绑定本机 loopback；远端 URL 会被配置校验拒绝。

## 开源测试音频与限制

可从 [RAVDESS 官方语音数据集](https://zenodo.org/records/1188976) 取得测试音频；作者提供的 [16 kHz 语音压缩包](https://zenodo.org/records/11063852) 更便于本地试跑。其语音由演员表演录制，标签包含中性、平静、开心、悲伤、愤怒、恐惧、厌恶和惊讶。数据使用 CC BY-NC-SA 4.0，需按原始 Zenodo 记录署名；商业使用需另行取得许可。RAVDESS 的表演式英语语音结果不能外推到日常对话或中文语音。

声学状态是可观察信号的粗略代理，不是“正确读心”。界面中的规则分是阈值分数，不是概率。当前规则未在足够多说话人、环境和真实自发表达上校准，因此不报告普适准确率；实际情绪分类准确率标记为未知。`--check` 使用合成信号证明数组处理、策略和回应对象可连通，不代表真实情绪识别准确。

本机另对 RAVDESS Actor 01 的 24 段 16 kHz 语音做了探索性检查：中性 4/4、平静 7/8、悲伤 4/4 被归入低唤醒；开心 4/8 为高唤醒、2/8 低唤醒、2/8 不确定。按样本顺序连续送入状态跟踪器时，高唤醒转低唤醒切到了 support 主题。**这些数值不是情绪准确率**：中性/平静/悲伤在纯声学特征上重叠明显，当前只能检测唤醒度变化，不能确认语义情绪。评估只用一名演员和四类样本，需更多说话人和真实自发表达才能判断分类效果。

## 会话上下文

上下文只保存在当前进程内存；每次启动从空记录开始，关闭应用即清空。总量硬限制2000单位：中文按字符，英文按单词/标点 token 计，超过后从最旧对话开始淘汰，超长单条保留末尾。上下文保存手工输入、稳定声学状态摘要和已显示的安慰短句。由于当前停用 ASR，实时语音不会被伪造为逐字对话文本。

## 项目结构

本地声学计算和窗口交互只挑选 pyAudioAnalysis、TkAnimator、CTkMessagebox 等开源代码中的小段实现并按本项目约束修改；没有克隆完整仓库、GUI 或权重。出处、许可证和适配范围见 [`docs/opensource-guidance.md`](docs/opensource-guidance.md)。当前 UI/声音状态设计见 [`ambient UI 设计说明`](docs/superpowers/specs/2026-10-08-emotiscreen-ambient-ui-design.md)。

- `emotionscreen/core/audio.py`：麦克风输入和有界音频缓冲。
- `emotionscreen/core/acoustic.py`：纯 Python/NumPy 声学特征与粗略状态估计。
- `emotionscreen/core/audio_runtime.py`：后台音频分析和最新窗口替换。
- `emotionscreen/core/audio_policy.py`：规则分、重复、冷却、DND、暂停和窗口冲突门控。
- `emotionscreen/core/decision.py`、`runtime.py`：开发面板手工文本的 Mock/Clef 情境链路，不用于音频。
- `emotionscreen/ui/comfort_window.py`、`glass.py`：常驻渐变毛玻璃浮层、状态短句切换、可拖动窗口和平台材质回退。
- `emotionscreen/ui/window.py`：显式采音、后台分析到窗口显示的 Tk 主界面。

Windows 尝试系统 Acrylic；macOS 和 Linux 使用明确标注的半透明渐变回退。默认动效强度为 0.72：浮层底色持续流动、光晕呼吸；状态切换时整片渐变用约 0.8 秒平滑换色。动画按实际时间推进，目标约 30 FPS，可通过强度滑杆调节；系统减少动态效果或静态模式开启时直接切换主题。
