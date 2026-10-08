"""只在内存中保存有界的短期转写上下文。"""

from __future__ import annotations

from collections import deque
import threading

from .models import TranscriptSegment


class ConversationContext:
    def __init__(self, max_turns: int = 6) -> None:
        if max_turns < 1:
            raise ValueError("max_turns must be positive")
        self._turns: deque[TranscriptSegment] = deque(maxlen=max_turns)
        self._revision = 0
        self._lock = threading.Lock()

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    def append(self, segment: TranscriptSegment) -> int:
        if not segment.is_final:
            raise ValueError("only final transcript segments can enter decision context")
        if not segment.text.strip():
            raise ValueError("transcript text must not be empty")
        with self._lock:
            self._turns.append(segment)
            self._revision += 1
            return self._revision

    def snapshot(self) -> tuple[TranscriptSegment, ...]:
        with self._lock:
            return tuple(self._turns)
