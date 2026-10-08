# 第三方代码来源与许可

EmotiScreen 只采用少量声学计算、动画和交互代码片段。项目没有复制完整上游仓库、完整界面、模型权重或无关依赖。

## pyAudioAnalysis

- 来源文件：`pyAudioAnalysis/ShortTermFeatures.py`，作者 Theodoros Giannakopoulos，Apache License 2.0。
- 上游源码：[ShortTermFeatures.py](https://github.com/tyiannak/pyAudioAnalysis/blob/master/pyAudioAnalysis/ShortTermFeatures.py)
- 本地适配：[`emotionscreen/core/acoustic.py`](emotionscreen/core/acoustic.py) 中短帧能量、过零率、频谱重心/通量和自相关特征的计算片段。只保留短时本地分析需要的部分；不包含上游分类器、训练流程、MFCC 特征组或整套依赖。
- 许可证副本：[`licenses/Apache-2.0-pyAudioAnalysis.txt`](licenses/Apache-2.0-pyAudioAnalysis.txt)

## TkAnimator

- 来源文件：`tk_animations.py`，作者 itsDevlune，MIT License，Copyright (c) 2025 itsDevLune。
- 上游源码：[tk_animations.py](https://github.com/itsDevlune/TkAnimator/blob/main/tk_animations.py)
- 本地适配：[`emotionscreen/ui/glass.py`](emotionscreen/ui/glass.py) 的 RGB 颜色线性插值；[`emotionscreen/ui/comfort_window.py`](emotionscreen/ui/comfort_window.py) 的分步透明度、情绪渐变和正弦呼吸光晕。由本项目可取消的 Tk `after` 回调调度，基于单调时钟按约 30 FPS 推进，并响应减少动态效果设置。没有复制或依赖 TkAnimator 动画库本身。
- 许可证副本：[`licenses/MIT-TkAnimator.txt`](licenses/MIT-TkAnimator.txt)

## CTkMessagebox

- 来源文件：`CTkMessagebox/ctkmessagebox.py`，作者 Akash Bora，CC0-1.0。
- 上游源码：[ctkmessagebox.py](https://github.com/Akascape/CTkMessagebox/blob/main/CTkMessagebox/ctkmessagebox.py)
- 本地适配：[`emotionscreen/ui/comfort_window.py`](emotionscreen/ui/comfort_window.py) 中按下时记录指针锚点、再按屏幕坐标移动窗口的交互片段。浮层仍使用本项目的原生 Tk Canvas；没有引入 CustomTkinter、Pillow 或复制消息框布局。

## window-vibrancy

- 来源文件：window-vibrancy 0.7.1 的 `src/windows.rs`，Apache-2.0/MIT 双许可。
- 上游源码：[windows.rs](https://docs.rs/crate/window-vibrancy/0.7.1/source/src/windows.rs)
- 项目说明：[window-vibrancy README](https://github.com/tauri-apps/window-vibrancy)
- 本地适配：[`emotionscreen/ui/glass.py`](emotionscreen/ui/glass.py) 将 Windows composition 结构、Acrylic 状态/标志和系统版本回退逻辑改写为 Python ctypes。没有复制或打包 Rust/Tauri crate。
- 本项目选用的许可证副本：[`licenses/MIT-window-vibrancy.txt`](licenses/MIT-window-vibrancy.txt)

## llama.cpp

- 上游接口说明：[llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)，MIT License。
- 现有本机 Clef 适配器仅按其 System One 接口服务于手工文本开发面板；实时音频不会进入 Clef，也不经过 ASR。

具体来源、许可证和修改边界另见[开源实现调研与选型记录](docs/opensource-guidance.md)。上游项目的性能或准确率不代表 EmotiScreen 的效果；音频状态仍需使用独立标注语料验证。
