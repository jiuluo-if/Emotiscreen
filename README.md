# EmotionScreen V1.0

EmotionScreen 是一个可迁移的 Python 桌面程序骨架，用于实验语音驱动的颜色与动画反馈。默认模拟模式不需要麦克风、Clef 服务或 GPU，也不会保存音频。情绪结果只是实验性的表达估计，不是心理诊断。

## 运行演示

运行环境：Python 3.11 或更高版本、Tkinter、NumPy。

```powershell
python -m pip install -r requirements.txt
python main.py
```

窗口默认以模拟模式启动。点击“Start listening”后，程序生成可复现的模拟音频；可使用模拟情绪选择器预览情绪效果。“Switch Mock / Live”用于切换输入源和决策服务。切换到 Live 不会自动打开麦克风，必须由用户再次点击启动。监听状态会显示在界面上，随时可以暂停或停止。

无需打开窗口即可验证完整模拟链路：

```powershell
python main.py --check
```

运行自动化测试：

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

## 目标设备上的 Live 配置

在目标设备编辑 `config.json`，例如：

```json
{
  "mode": "live",
  "audio": { "sample_rate": 16000, "channels": 1, "frame_ms": 32, "window_seconds": 2.0, "device": null },
  "decision": { "provider": "clef", "clef_base_url": "http://127.0.0.1:8080", "timeout_seconds": 5, "interval_ms": 1000, "seed": 42 }
}
```

在目标设备安装可选麦克风依赖：`python -m pip install sounddevice`。只有用户点击启动后才开始采音。音频只保留在有界内存缓冲区内，本程序不会将音频写入磁盘或上传。请在目标系统确认麦克风权限和设备选择。

## Clef 接入边界

当前适配器会向 `{clef_base_url}/v1/systemone` 发送 JSON 请求，预期响应包含 `choices.emotion.selected`、`choices.emotion.probabilities`、可选的 `choices.emotion.confidence`、`choices.arousal.selected` 和 `choices.screen_mode.selected`。适配器会检查类别、概率取值与总和、confidence 范围，并将 confidence 与候选概率分开保存。

**此请求与响应结构尚未在目标 Clef 服务上验证。** 将 Live 模式视为正式接入前，请先核实目标设备上的 System One 契约，并用实际响应样例更新 `emotionscreen/core/decision.py` 和测试。未知或格式错误的响应会显示为错误；程序不会伪造概率，也不会自动重试或重放请求。

## 模块说明

- `emotionscreen/config.py`：JSON 默认值和参数范围校验。
- `emotionscreen/core/audio.py`：模拟输入、可选 sounddevice 输入、有界环形缓冲区。
- `emotionscreen/core/features.py`：RMS、峰值、能量变化、自相关基频、有声/停顿比例、节奏代理、频谱重心/通量、过零率和质量标记。
- `emotionscreen/core/decision.py`：固定随机种子的模拟提供器和严格校验的 Clef 适配器。
- `emotionscreen/core/smoothing.py`：连续确认、最短保持时间、过期结果和不确定结果处理。
- `emotionscreen/core/controller.py`：将情绪和即时声音能量映射为视觉参数。
- `emotionscreen/core/runtime.py`：单后台工作线程、单个执行中请求和可替换的最新待处理特征。
- `emotionscreen/ui/window.py`：Tkinter 界面与动画。

## 当前限制与后续联调

- 尚未使用带标签的数据集评估分类准确率；模拟结果和单元测试通过均不能证明真实情绪识别有效。
- 真实麦克风输入和设备选择需要在目标操作系统及音频硬件上验证。
- 将真实 Clef System One 响应格式加入适配器和测试后，才能确认 Live 决策已接通。
- 当前声学特征是轻量信号处理代理，不是完整的 GeMAPS/eGeMAPS 实现；阈值需用目标音频校准。
- 透明桌面覆盖层未实现，配置中保持关闭。
- 性能数据须在目标设备上实际测量，包括采音丢帧、特征耗时、决策 P50/P95 和界面帧率；当前没有性能保证。
