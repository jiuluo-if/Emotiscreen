"""仅供开发面板使用的固定转写场景。实时音频不进入文本转写。"""

from __future__ import annotations

from .models import TranscriptSegment


class MockTranscriptProvider:
    """固定场景文本只供测试，不按词语猜测事件或情绪。"""

    SCENARIOS = {
        "user_achievement": {
            "zh-CN": "我刚刚通过了考试。",
            "en": "I just passed my exam.",
        },
        "user_praise": {
            "zh-CN": "老师说我最近进步很大。",
            "en": "My teacher said I have made a lot of progress.",
        },
        "user_sadness": {
            "zh-CN": "我今天有点难过。",
            "en": "I feel a little sad today.",
        },
        "small_progress": {
            "zh-CN": "今天终于完成了一小步。",
            "en": "I finally made a little progress today.",
        },
        "ordinary_chat": {
            "zh-CN": "晚上吃什么？",
            "en": "What should I eat tonight?",
        },
        "sarcasm": {
            "zh-CN": "我可真厉害，又把钥匙忘办公室了。",
            "en": "I'm so brilliant; I left my keys at work again.",
        },
        "other_person": {
            "zh-CN": "我朋友刚拿到了奖学金。",
            "en": "My friend just got a scholarship.",
        },
        "incomplete": {
            "zh-CN": "我终于……",
            "en": "I finally…",
        },
        "uncertain": {
            "zh-CN": "结果还没确定。",
            "en": "The result is not certain yet.",
        },
    }

    def scenario(self, scenario_id: str, language: str = "zh-CN") -> TranscriptSegment:
        try:
            text = self.SCENARIOS[scenario_id][language]
        except KeyError as exc:
            raise ValueError(f"unknown mock transcript scenario or language: {scenario_id}/{language}") from exc
        return TranscriptSegment(text=text, language=language, source="mock")
