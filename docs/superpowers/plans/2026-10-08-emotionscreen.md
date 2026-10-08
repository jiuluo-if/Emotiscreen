# EmotionScreen 实施计划

> **执行说明：** 本计划按任务分步实施；每个模块先写测试，再补最小实现。

**目标：** 搭建无模型、无麦克风也能运行的桌面应用骨架，并为真实音频和 Clef 留下可替换接口。

**架构：** Python 包将配置、音频/特征、决策提供器、平滑、视觉映射、运行调度和 Tk 界面分开。界面主线程只处理显示与交互，网络推理在后台执行。

**技术栈：** Python 3.11+、NumPy、Tkinter、urllib、pytest；真实麦克风可选安装 sounddevice。

**设计文档：** `EmotionScreen/docs/superpowers/specs/2026-10-08-emotionscreen-design.md`

## 全局约束

- 默认模拟模式，不要求目标设备才能演示。
- 不保存或上传采集到的音频。
- 不添加其他 AI 模型或训练流程。
- Clef 响应契约未知时拒绝解析，不得伪造概率或 confidence。
- 音频回调不执行推理或界面操作。

---

### 任务 1：配置和核心数据结构

**文件：** `config.json`、`emotionscreen/config.py`、`emotionscreen/core/models.py`、`tests/test_config.py`

- [x] 覆盖默认值、参数范围、错误模式和配置读取。
- [x] 实现配置数据类和校验，以及声学特征、决策结果、视觉状态数据结构。
- [x] 运行对应测试。

### 任务 2：声学特征与决策提供器

**文件：** `emotionscreen/core/features.py`、`emotionscreen/core/decision.py`、`tests/test_features.py`、`tests/test_decision.py`

- [x] 使用静音、正弦波、噪声与无效数组编写确定性测试。
- [x] 实现 NumPy 特征提取、固定种子模拟提供器、Clef JSON 传输和严格响应解析。
- [x] 覆盖无效概率、缺失字段和超时错误。

### 任务 3：情绪平滑与视觉映射

**文件：** `emotionscreen/core/smoothing.py`、`emotionscreen/core/controller.py`、对应测试文件

- [x] 覆盖连续确认、保持时间、不确定回退和情绪映射。
- [x] 实现平滑器和视觉状态映射。

### 任务 4：运行调度与桌面界面

**文件：** `emotionscreen/core/audio.py`、`emotionscreen/core/runtime.py`、`emotionscreen/ui/window.py`、`main.py`、`tests/test_runtime.py`

- [x] 验证模拟音频显式启动、音频环形缓冲和单请求/仅保留最新快照。
- [x] 实现可选 sounddevice 输入、后台单请求调度和 Tk 控件/动画。
- [x] 验证暂停、关闭与运行时错误不会阻塞界面。

### 任务 5：配置、文档与交付验证

**文件：** `requirements*.txt`、`README.md`、`.gitignore` 和架构文档

- [x] 提供中文安装、启动、模拟/真实模式和隐私说明。
- [x] 执行自动化测试、编译检查、无窗口模拟链路和 Tk 界面初始化/关闭检查。
- [ ] 完成代码审查并核对 Git 交付状态；当前工作区尚无 Git 仓库和远端。
