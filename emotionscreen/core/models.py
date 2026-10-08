"""情境回应流水线使用的不可变值对象。"""

from __future__ import annotations

from dataclasses import dataclass, field
import time


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    language: str = "zh-CN"
    speaker: str = "user"
    is_final: bool = True
    source: str = "mock"
    created_at: float = field(default_factory=time.monotonic, compare=False)


@dataclass(frozen=True)
class DecisionRequest:
    context: tuple[TranscriptSegment, ...]
    context_revision: int
    scenario_id: str | None = None


@dataclass(frozen=True)
class DecisionResult:
    relevance: str = "uncertain"
    event_status: str = "uncertain"
    attitude: str = "explicit"
    event_relation: str = "uncertain"
    response: str = "none"
    intensity: str = "none"
    timing: str = "suppress"
    event_id: str | None = None
    probabilities: dict[str, dict[str, float]] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    source: str = "mock"
    context_revision: int = 0
    latency_ms: float = 0.0
    created_at: float = field(default_factory=time.monotonic, compare=False)
    note: str = ""


@dataclass(frozen=True)
class ResponseEvent:
    action: str
    phrase: str
    intensity: str
    event_id: str
    duration_seconds: float
    language: str
    state: str | None = None
    persistent: bool = False
