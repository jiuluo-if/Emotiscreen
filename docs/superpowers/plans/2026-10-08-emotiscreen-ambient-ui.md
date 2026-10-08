# EmotiScreen 环境式玻璃界面与会话预算实施计划

> 本轮直接在 `main` 上实施，不创建分支或工作区。

**目标：** 把固定弹出卡改为监听期间情绪主题渐变玻璃层，并将本次启动会话历史限制为2000中文字符/英文词法 token。

**架构：** `ConversationContext` 在内存保存有界 turns；`AudioStateTracker` 为连续状态变化去抖；`AudioFeedbackPolicy` 为 low/elevated/uncertain 生成本地短句；`ComfortWindow` 常驻显示主题玻璃层，复用 Tk `after` 平滑更新渐变与文字，停止监听后渐隐。

**技术栈：** Python 3.11+、NumPy、Tkinter、可选 sounddevice；英文 token 使用标准库词法分割，不依赖网络、ASR或新模型。

**设计文档：** `docs/superpowers/specs/2026-10-08-emotiscreen-ambient-ui-design.md`

## 全局约束

- 麦克风只在用户明确开始监听后开启；音频与上下文仅驻留内存，启动清空，不写盘/不上云。
- 会话上下文总预算 `max_units=2000`；中文按字符，英文按单词/标点 token。
- 状态是低/高唤醒等粗声学代理，不伪装成离散语义情绪。
- 适配上游必要片段，保留来源/许可证，不克隆完整仓库。
- 测试只覆盖预算淘汰、状态到主题/短句映射和渐变端点等关键行为。
- 使用邮箱 `2966684515@qq.com`，提交格式 `English: 中文内容`，维护完成推送 main。

---

## 任务 1：有界会话上下文

**涉及文件：** `emotionscreen/core/context.py`、`emotionscreen/config.py`、`config.json`、`tests/test_pipeline.py`、`tests/test_config_ui.py`

**接口：** `ConversationContext(max_units=2000)` 提供 `append(segment)`、`snapshot()`、`used_units`；每条 turn 按本地词法规则计费，超额淘汰最旧 turn，单条超长保留末尾。

- [x] 用精简回归覆盖中文字符上限、英文词法 token、旧 turn 淘汰、超长 turn 截尾和新实例为空。
- [x] 实现离线 token 计数和有界内存 deque；`ContextConfig.max_units` 默认2000且不能配置超过2000。
- [x] UI 在状态转换时保存简短声学摘要和显示过的回应；手工文本仍保存原文，实时说话不生成假转写。
- [x] 跑 context/config 目标测试。

## 任务 2：状态驱动的主题和短句

**涉及文件：** `emotionscreen/core/audio_policy.py`、`emotionscreen/core/i18n.py`、`tests/test_pipeline.py`

**接口：** `AudioFeedbackPolicy.evaluate(transition, ...) -> ResponseEvent | None`；low→support、elevated→calming acknowledge、uncertain→neutral companion。

- [x] 测试三种状态 transition 映射及 DND/paused 门控。
- [x] 去掉音频状态上的30秒去重/冷却，让每次已去抖状态变化都能更新 UI。
- [x] 短句提供 zh-CN/en 两套本地文案，不含旧 footer 句子。

## 任务 3：环境式玻璃窗与动态换色

**涉及文件：** `emotionscreen/ui/comfort_window.py`、`emotionscreen/ui/glass.py`、`emotionscreen/ui/window.py`、`tests/test_config_ui.py`

- [x] 用无硬边背景渐变、柔和光晕和留白短句取代内部白色圆角卡片/footer。
- [x] 用 TkAnimator RGB 插值、步进与正弦脉冲片段驱动浮层底色流动和光晕呼吸；状态切换时整张背景 0.8 秒平滑换色并更换短句，窗口复用。
- [x] live start 显示中性色主题，之后各稳定状态主动切换；stop/DND/pause 平滑隐藏，reduced-motion 直接切换。
- [x] 主窗口预览同步当前主题，拖动和关闭继续可用。
- [x] 用纯色插值测试和真实 Tk 展示检查渐变、状态切换和静态模式。

## 任务 4：文档、公开语料复验与推送

**涉及文件：** `README.md`、`docs/superpowers/specs/2026-10-08-emotiscreen-ambient-ui-design.md`、`docs/opensource-guidance.md`、`THIRD_PARTY_NOTICES.md`

- [x] 更新上下文预算、冷/暖主题、常驻监听状态和启动重置说明。
- [x] 用临时 RAVDESS 高→低音频序列验证主题/短句切换；结果只说明状态代理，不声称语义情绪准确率。
- [x] 跑最少相关 pytest、compileall、`main.py --check` 和 diff 检查。
- [x] 审核差异，以指定邮箱提交并推送 main；推送 SHA 将与 `git ls-remote` 核对。
