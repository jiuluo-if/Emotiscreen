"""Temporal confirmation and hold rules for emotion decisions."""

from __future__ import annotations

from dataclasses import replace

from .models import DecisionResult


class EmotionSmoother:
    def __init__(self, *, alpha: float = 0.35, min_hold_seconds: float = 1.5, confirm_count: int = 2, max_age_seconds: float = 8.0, uncertain_fallback: str = "calm") -> None:
        self.alpha = min(1.0, max(0.0, alpha))
        self.min_hold_seconds = max(0.0, min_hold_seconds)
        self.confirm_count = max(1, confirm_count)
        self.max_age_seconds = max_age_seconds
        self.uncertain_fallback = uncertain_fallback
        self._current: DecisionResult | None = None
        self._changed_at = 0.0
        self._candidate: str | None = None
        self._candidate_count = 0
        self._ema: dict[str, float] = {}

    def update(self, result: DecisionResult) -> DecisionResult:
        if result.emotion == "uncertain":
            if self._current is not None:
                return self._current
            if self.uncertain_fallback == "uncertain":
                return result
            fallback = replace(
                result,
                emotion=self.uncertain_fallback,
                probabilities={},
                confidence=None,
                note="Uncertain result; showing configured visual fallback without a model probability.",
            )
            self._current = fallback
            self._changed_at = result.created_at
            return fallback
        if result.source not in {"mock", "clef"}:
            return self._current or replace(result, emotion="uncertain", note="Unknown decision source")
        if self._current is None:
            self._current = result
            self._changed_at = result.created_at
            self._ema = dict(result.probabilities)
            return result
        if result.created_at - self._current.created_at > self.max_age_seconds:
            return self._current
        for emotion, probability in result.probabilities.items():
            self._ema[emotion] = self.alpha * probability + (1 - self.alpha) * self._ema.get(emotion, 0.0)
        if result.emotion == self._current.emotion:
            self._candidate = None
            self._candidate_count = 0
            self._current = replace(result, probabilities=dict(self._ema))
            return self._current
        if result.emotion == self._candidate:
            self._candidate_count += 1
        else:
            self._candidate = result.emotion
            self._candidate_count = 1
        if self._candidate_count >= self.confirm_count and result.created_at - self._changed_at >= self.min_hold_seconds:
            self._current = replace(result, probabilities=dict(self._ema))
            self._changed_at = result.created_at
            self._candidate = None
            self._candidate_count = 0
        return self._current
