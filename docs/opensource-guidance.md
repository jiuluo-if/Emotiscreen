# 开源实现调研与选型记录

## 本地 Clef 推理：llama.cpp

参考 [ggml-org/llama.cpp 的 server 文档](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)。该项目将 Clef 作为 typed decision model，通过 `/v1/systemone` 接收 `state` 与 `questions`，返回 `answers` 中的 `choice`、`probabilities` 和 `confidence`。文档也说明 Clef 的多个问题会联合判断；整个输入需要放进一个 physical batch，超出 `--ubatch-size` 时服务会拒绝请求。EmotiScreen 的请求格式、严格解析和本机 llama.cpp 对接按此接口实现。

本机验证使用 `F:\codex\model\Clef-Flash-Q4_K_M.gguf`、`F:\codex\model\llama\llama-server.exe`（0.6.0-dev build 11429），仅监听 `127.0.0.1`。本地服务返回可解析的五类选择与概率；本机测试中的成绩、普通闲聊、反话、他人成绩、未完成语句和难过样例都经过 ResponsePolicy 校验。模型概率未经校准，样例结果不代表现实分类准确率。正确入口是 `/v1/systemone`，不是把 Clef 当普通文本生成模型调用 `/v1/chat/completions`。

## 原生毛玻璃：tauri-apps/window-vibrancy

参考 [tauri-apps/window-vibrancy](https://github.com/tauri-apps/window-vibrancy)。它提供 Windows Acrylic/Mica 和 macOS Vibrancy/Liquid Glass；项目明确注明 Linux 的模糊效果由桌面合成器决定。该项目还指出某些 Windows 版本下 Acrylic 窗口在拖动/缩放时有性能限制，应避免持续移动或高频重绘。

当前项目是已有 Python/Tkinter 桌面程序，因此保留轻量单进程架构：Windows 通过原生窗口 API 实际尝试 Acrylic；macOS/Linux 使用易读的半透明卡片回退，不把普通 Canvas 透明度说成系统模糊。Tauri 2 + Rust + TypeScript 可作为未来需要跨平台原生材质一致性时的迁移路径，本轮不引入第二套 UI/IPC 体系。

## 系统通知插件

参考 [tauri-apps/plugins-workspace 的 notification 插件](https://github.com/tauri-apps/plugins-workspace/tree/v2/plugins/notification)。系统通知插件适合标准通知，但 EmotiScreen 需要可拖动、可关闭、数秒自动隐藏并呈现特定材质的浮层，因此保留自绘 ComfortWindow；普通通知不替代这里的窗口。

## 本轮实际采用的上游代码片段

本项目继续以当前 EmotiScreen 代码为宿主，只取用小段算法和交互模式；没有克隆上游仓库，也没有把其完整 GUI、模型或依赖树放进来。

| 上游项目与源码 | 许可证 | 借用点 | EmotiScreen 的本地改动 |
|---|---|---|---|
| [pyAudioAnalysis `ShortTermFeatures.py`](https://github.com/tyiannak/pyAudioAnalysis/blob/master/pyAudioAnalysis/ShortTermFeatures.py) | Apache-2.0 | 短帧能量、过零率、频谱重心/通量和自相关基频的计算思路 | 仅采用实时陪伴需要的少量统计；保留 NumPy，删除 MFCC/分类器/文件批处理等路径；音频只驻留在内存；质量不足则输出 uncertain。源码概览见 [feature extraction 文档](https://github.com/tyiannak/pyAudioAnalysis/wiki/3.-feature-extraction)。 |
| [TkAnimator `tk_animations.py`](https://github.com/itsDevlune/TkAnimator/blob/main/tk_animations.py) | MIT | `animate_fade_in`/`animate_fade_out` 的分步透明度插值，`animate_pulse` 的正弦缓动思路 | 只把相关步进/曲线用于 Tk Toplevel 与 Canvas glow；用可取消的 `after` 驱动，适配 Acrylic 透明度、关闭/暂停和系统减少动态效果，不带入动画库其他效果。 |
| [CTkMessagebox `ctkmessagebox.py`](https://github.com/Akascape/CTkMessagebox/blob/main/CTkMessagebox/ctkmessagebox.py) | CC0-1.0 | `oldxyset`/`move_window` 的按下锚点与根坐标拖动方式、淡入淡出时长配置思路 | 适配到原生 Tk Canvas 的卡片拖动；沿用项目自己的关闭控件、无焦点和窗口位置，不引入 CustomTkinter/Pillow，也不复制消息框布局。 |
| [window-vibrancy 0.7.1 `src/windows.rs`](https://docs.rs/crate/window-vibrancy/0.7.1/source/src/windows.rs) 与 [README](https://github.com/tauri-apps/window-vibrancy) | Apache-2.0/MIT 双许可 | Windows `ACCENT_POLICY`/`WINDOWCOMPOSITIONATTRIBDATA` 结构、Acrylic state/flags、版本门槛及平台材质能力 | 将 FFI 声明翻译到 Python ctypes，保留 Acrylic 渐变 alpha 和无效 API 回退；没有复制 Rust/Tauri crate。 |
| [llama.cpp server README](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md) | MIT | Clef System One 的本机 `state/questions` 接口约束 | 只用于开发面板里的手工文本决策；实时音频不进入 Clef，也不走 ASR。 |

实现中的对应位置：`emotionscreen/core/acoustic.py`、`emotionscreen/ui/comfort_window.py`、`emotionscreen/ui/glass.py`。音频链路和跨平台窗口仍由 EmotiScreen 自己的线程、状态和策略边界管理。

## 代码采用边界

- 不复制完整仓库、完整 GUI、预训练权重或数据集到本项目。
- 只抽取适配当前 Python/Tkinter 流程的计算片段；上游出处和许可证留在本文件与源码注释中。
- 上游库的准确率不能代表 EmotiScreen 的准确率；音频情绪边界须用独立标注的语料验证。
