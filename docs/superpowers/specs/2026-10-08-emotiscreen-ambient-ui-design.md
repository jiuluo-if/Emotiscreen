# EmotiScreen 环境式情绪玻璃界面设计

## 目标

把静态安慰卡改为监听期间持续更新的毛玻璃情绪界面。稳定音频状态变化时，在同一个窗口里平滑改变主题色渐变、光晕和本地安慰短句；停止监听后渐隐。主界面的预览也使用同一情绪主题，不再画一张固定消息卡。

去掉浮层上的“只在值得回应时出现”和“不保存录音”脚注。隐私行为仍由实现保证：音频只在内存处理，不写文件、不上传。

## 设计与数据流

`SoundDeviceAudioInput` → 有界帧队列/环形缓冲 → `AcousticEmotionAnalyzer` → `AudioStateTracker`（连续两窗确认）→ `AudioFeedbackPolicy`（low/elevated/uncertain → 本地状态短句）→ `ComfortWindow.transition_state()`。实时监听开启时玻璃层常驻；状态稳定改变后渐变 tint/渐变光晕并淡换文字。DND/暂停停止状态更新，关闭/停止时渐隐。

状态词只表示声学唤醒度代理：`low_arousal` 使用冷色舒缓主题，`elevated` 使用暖色缓和主题，`uncertain` 使用中性色陪伴主题。它们不表示悲伤/开心等语义情绪。状态分数不是概率。

## 视觉实现

- 复用当前 Toplevel、拖动、无焦点和 Windows Acrylic；保持 macOS/Linux 半透明回退。
- 移除内层硬边白色卡片、平铺 icon/footer；改成无硬边玻璃面、持续流动的双色渐变、呼吸光晕和留白短句。
- 状态切换时整张玻璃面的渐变色平滑过渡约 0.8 秒，同时更换状态短句；同一窗口复用，不重建窗口。
- 取 TkAnimator `animate_color_transition` 的 RGB 插值/after 步进片段做连续主题渐变；以约 30 FPS 和单调时钟推进颜色漂移、光晕呼吸，避免回调抖动造成速度忽快忽慢。默认动效强度为 0.72，可用强度滑杆调整。
- 静态模式/系统减少动态效果时直接切色，不做动画。DND/暂停/停止优先于新的状态反馈。

## 会话上下文

应用每次启动创建全新的内存上下文；关闭时销毁，不落盘。总预算固定不超过2000单位：中文按字符计，英文按本地词/标点 token 计；超预算先删最旧 turn，单条超长时保留末尾。当前上下文保存开发面板手输文本、稳定声学状态摘要及本地回应；实时说话内容因 ASR 仍停用不会被伪造为转写。

## 开源代码采用

只适配开源项目中的少量片段：pyAudioAnalysis 特征；TkAnimator 透明度、脉冲与颜色插值；CTkMessagebox 拖动锚点；window-vibrancy Windows Acrylic FFI 结构。具体文件、许可证和 EmotiScreen 改动见 `docs/opensource-guidance.md` 与 `THIRD_PARTY_NOTICES.md`；不克隆完整项目/GUI/模型。

## 验收

- 麦克风 live 开启时看到常驻中性玻璃层；两窗确认后的 low/elevated/uncertain 转换会在同一浮层渐变换色并更换相应短句。
- RAVDESS 高唤醒→低唤醒片段能实际触发 support 主题；neutral/calm/sad 声学重叠作为限制明确呈现，不宣称离散情绪准确率。
- 启动时 context 为空；中文与英文连续 turn 总预算均不超过2000；旧 turn 被淘汰；结束/重新启动无历史残留。
- DND、暂停、静态模式、拖动、关闭、平台材质回退和 error handling 保持有效。
