# EmotiScreen V0.3

EmotiScreen 是一款本地桌面音频陪伴程序。用户明确开启监听后，程序在内存中分析短音频窗里的 RMS、能量变化、基频、过零率、频谱重心和有声比例；只有连续状态从高唤醒稳定切换到低唤醒时，屏幕右下角的安抚卡片才渐入显示，短暂停留后渐隐。启动时声音本来就低沉时只显示状态，不据此判定悲伤。

**当前实时音频链路不使用 ASR，也不把原始音频发送给 Clef 或其他服务。** 这是传统声学特征启发式，只估计声音低唤醒/活跃/不确定状态；无法从这些特征可靠区分悲伤、疲劳、平静或兴奋等语义情绪。低质量、静音、基频无效和不确定状态不触发回应。该功能不做心理诊断。

## 安装与运行

要求 Python 3.11+、Tkinter、NumPy。默认 `mock` 模式无需麦克风：

```powershell
python -m pip install -r requirements.txt
python main.py
```

主界面支持模拟对话、安抚窗口预览、主题、动效强度、减少动态效果、免打扰和中英文切换。

运行无麦克风的处理链路检查：

```powershell
python main.py --check
```

对本地测试 WAV 查看单段声学状态（不安装麦克风）：

```powershell
python main.py --audio-file path\to\sample.wav
```

目前只接受单/双声道、16-bit PCM、最长10秒的 WAV。孤立 WAV 只显示状态估计；安抚反馈需要实时窗口中稳定的高唤醒→低唤醒变化。

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

本机另对 RAVDESS Actor 01 的 24 段 16 kHz 语音做了探索性检查：中性 4/4、平静 7/8、悲伤 4/4 被归入低唤醒；开心 4/8 为高唤醒、2/8 低唤醒、2/8 不确定。按样本顺序连续送入状态跟踪器时，高唤醒转低唤醒产生了 1 次 support。**这些数值不是情绪准确率**：中性/平静/悲伤在纯声学特征上重叠明显，当前只能检测唤醒度变化，不能确认语义情绪。支持弹窗只在持续状态从高唤醒切换到低唤醒时出现；孤立 WAV 试听显示估计结果，不单独触发安抚。评估只用一名演员和四类样本，需更多说话人和真实自发表达才能判断分类效果。

## 项目结构

本地声学计算和窗口交互只挑选 pyAudioAnalysis、TkAnimator、CTkMessagebox 等开源代码中的小段实现并按本项目约束修改；没有克隆完整仓库、GUI 或权重。出处、许可证和适配范围见 [`docs/opensource-guidance.md`](docs/opensource-guidance.md)。

- `emotionscreen/core/audio.py`：麦克风输入和有界音频缓冲。
- `emotionscreen/core/acoustic.py`：纯 Python/NumPy 声学特征与粗略状态估计。
- `emotionscreen/core/audio_runtime.py`：后台音频分析和最新窗口替换。
- `emotionscreen/core/audio_policy.py`：规则分、重复、冷却、DND、暂停和窗口冲突门控。
- `emotionscreen/core/decision.py`、`runtime.py`：开发面板手工文本的 Mock/Clef 情境链路，不用于音频。
- `emotionscreen/ui/comfort_window.py`、`glass.py`：可拖动安抚卡片、渐入渐隐和平台材质回退。
- `emotionscreen/ui/window.py`：显式采音、后台分析到窗口显示的 Tk 主界面。

Windows 尝试系统 Acrylic；macOS 和 Linux 使用明确标注的半透明卡片回退。系统减少动态效果或静态模式开启时直接显示，不播放渐入动画。
