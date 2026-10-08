"""Conservative feedback gate for acoustic estimates."""

from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
import time
from typing import Callable

from .acoustic import AudioStateTransition
from .i18n import response_phrase
from .models import ResponseEvent


class AudioFeedbackPolicy:
    def __init__(
        self,
        *,
        cooldown_seconds: float = 30.0,
        dedupe_seconds: float = 600.0,
        duration_seconds: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cooldown_seconds = cooldown_seconds
        self.dedupe_seconds = dedupe_seconds
        self.duration_seconds = min(4.0, max(2.0, duration_seconds))
        self._clock = clock
        self._last_shown = float("-inf")
        self._seen: OrderedDict[str, float] = OrderedDict()

    def evaluate(
        self,
        transition: AudioStateTransition | None,
        *,
        language: str = "zh-CN",
        listening: bool = True,
        dnd: bool = False,
        paused: bool = False,
        popup_active: bool = False,
        now: float | None = None,
    ) -> ResponseEvent | None:
        current = self._clock() if now is None else now
        if transition is None:
            return None
        analysis = transition.analysis
        entered_low_from_elevated = transition.previous_state == "elevated" and transition.state == "low_arousal"
        if (
            analysis.quality != "usable"
            or analysis.state != "low_arousal"
            or analysis.score < 0.70
            or transition.state != "low_arousal"
            or not entered_low_from_elevated
            or not listening
            or dnd
            or paused
            or popup_active
        ):
            return None
        self._expire(current)
        key = self._event_key(analysis)
        if key in self._seen or current - self._last_shown < self.cooldown_seconds:
            return None
        self._seen[key] = current
        if len(self._seen) > 256:
            self._seen.popitem(last=False)
        self._last_shown = current
        return ResponseEvent(
            action="support",
            phrase=response_phrase("support", language),
            intensity="gentle",
            event_id=key,
            duration_seconds=self.duration_seconds,
            language=language,
        )

    def _expire(self, now: float) -> None:
        while self._seen:
            _, seen_at = next(iter(self._seen.items()))
            if now - seen_at <= self.dedupe_seconds:
                break
            self._seen.popitem(last=False)

    @staticmethod
    def _event_key(analysis: AcousticAnalysis) -> str:
        features = analysis.features
        identity = (
            analysis.state,
            round(features.rms, 3),
            round(features.rms_variation, 2),
            round(features.median_pitch_hz or 0, 0),
            round(features.pitch_range_hz or 0, 0),
        )
        return sha256(repr(identity).encode("utf-8")).hexdigest()
