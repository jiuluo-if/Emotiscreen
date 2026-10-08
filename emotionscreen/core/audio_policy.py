"""Map stable acoustic states to a persistent local theme and short phrase."""

from __future__ import annotations

from .acoustic import AudioStateTransition
from .i18n import text
from .models import ResponseEvent

_STATE_COPY = {
    "low_arousal": ("support", "audio_low_phrase", "gentle"),
    "elevated": ("acknowledge", "audio_elevated_phrase", "subtle"),
    "uncertain": ("listen", "audio_uncertain_phrase", "subtle"),
}


class AudioFeedbackPolicy:
    """为每次已确认的声学状态变化创建一个常驻界面事件。"""

    def evaluate(
        self,
        transition: AudioStateTransition | None,
        *,
        language: str = "zh-CN",
        listening: bool = True,
        dnd: bool = False,
        paused: bool = False,
    ) -> ResponseEvent | None:
        if transition is None or not listening or dnd or paused:
            return None
        if transition.state not in _STATE_COPY:
            return None
        if transition.state != "uncertain":
            analysis = transition.analysis
            if analysis.quality != "usable" or analysis.score < 0.70:
                return None

        action, phrase_key, intensity = _STATE_COPY[transition.state]
        return ResponseEvent(
            action=action,
            phrase=text(phrase_key, language),
            intensity=intensity,
            event_id=f"audio-{transition.previous_state}-{transition.state}",
            duration_seconds=0.0,
            language=language,
            state=transition.state,
            persistent=True,
        )
