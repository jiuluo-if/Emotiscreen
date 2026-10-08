"""弹窗克制策略：确定性、相关性、去重、冷却和打扰状态。"""

from __future__ import annotations

from collections import OrderedDict
from hashlib import sha256
import time
from typing import Callable

from .i18n import response_phrase
from .models import DecisionRequest, DecisionResult, ResponseEvent

_ACTIONS = {"acknowledge", "celebrate", "support"}


class ResponsePolicy:
    def __init__(
        self,
        *,
        cooldown_seconds: dict[str, float] | None = None,
        dedupe_seconds: float = 600.0,
        duration_seconds: float = 3.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self.cooldowns = {"celebrate": 45.0, "support": 30.0, "acknowledge": 20.0}
        if cooldown_seconds:
            self.cooldowns.update(cooldown_seconds)
        self.dedupe_seconds = dedupe_seconds
        self.duration_seconds = min(4.0, max(2.0, duration_seconds))
        self._clock = clock
        self._seen: OrderedDict[str, float] = OrderedDict()
        self._last_shown: dict[str, float] = {}
        self._active_until = 0.0

    def evaluate(
        self,
        decision: DecisionResult,
        request: DecisionRequest,
        *,
        latest_context_revision: int,
        language: str = "zh-CN",
        dnd: bool = False,
        paused: bool = False,
        popup_active: bool = False,
        listening: bool = False,
        now: float | None = None,
    ) -> ResponseEvent | None:
        current_time = self._clock() if now is None else now
        if request.context_revision != latest_context_revision or decision.context_revision != request.context_revision:
            return None
        if decision.response == "listen":
            if dnd or paused or not listening:
                return None
            return ResponseEvent("listen", "", "subtle", "listen", 1.0, language)
        if (
            decision.source not in {"mock", "clef"}
            or decision.relevance != "user"
            or decision.event_status != "confirmed"
            or decision.attitude != "explicit"
            or decision.event_relation != "new_event"
            or decision.timing != "now"
            or decision.response not in _ACTIONS
            or decision.intensity not in {"subtle", "gentle"}
        ):
            return None

        event_key = self._event_key(decision, request)
        self._expire_seen(current_time)
        if event_key in self._seen:
            return None
        self._seen[event_key] = current_time
        if len(self._seen) > 256:
            self._seen.popitem(last=False)
        if dnd or paused or popup_active or current_time < self._active_until:
            return None
        previous = self._last_shown.get(decision.response)
        if previous is not None and current_time - previous < self.cooldowns.get(decision.response, 0.0):
            return None

        self._last_shown[decision.response] = current_time
        self._active_until = current_time + self.duration_seconds
        return ResponseEvent(
            action=decision.response,
            phrase=response_phrase(decision.response, language),
            intensity=decision.intensity,
            event_id=event_key,
            duration_seconds=self.duration_seconds,
            language=language,
        )

    def _expire_seen(self, now: float) -> None:
        while self._seen:
            _, seen_at = next(iter(self._seen.items()))
            if now - seen_at <= self.dedupe_seconds:
                break
            self._seen.popitem(last=False)

    @staticmethod
    def _event_key(decision: DecisionResult, request: DecisionRequest) -> str:
        if decision.event_id:
            return sha256(decision.event_id.encode("utf-8")).hexdigest()
        latest = request.context[-1] if request.context else None
        context = f"{latest.speaker}:{' '.join(latest.text.casefold().split())}" if latest else "empty-context"
        return sha256(context.encode("utf-8")).hexdigest()
