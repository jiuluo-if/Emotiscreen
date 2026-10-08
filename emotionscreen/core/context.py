"""只在内存中保存有界的短期转写上下文。"""

from __future__ import annotations

from collections import deque
from dataclasses import replace
import re
import threading

from .models import TranscriptSegment

_TEXT_TOKEN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]|[\w]+(?:['’][\w]+)*|[^\w\s]", re.UNICODE)


class ConversationContext:
    """仅本次进程使用的短期上下文，按中文字符和英文词法 token 计量。"""

    def __init__(self, max_units: int = 2_000) -> None:
        if max_units < 1:
            raise ValueError("max_units must be positive")
        self.max_units = max_units
        self._turns: deque[tuple[TranscriptSegment, int]] = deque()
        self._used_units = 0
        self._revision = 0
        self._lock = threading.Lock()

    @staticmethod
    def _token_spans(text: str) -> list[tuple[int, int]]:
        return [match.span() for match in _TEXT_TOKEN.finditer(text)]

    @classmethod
    def _fit_turn(cls, segment: TranscriptSegment, max_units: int) -> tuple[TranscriptSegment, int]:
        spans = cls._token_spans(segment.text)
        if len(spans) > max_units:
            segment = replace(segment, text=segment.text[spans[-max_units][0] :].lstrip())
            spans = cls._token_spans(segment.text)
        return segment, len(spans)

    @property
    def revision(self) -> int:
        with self._lock:
            return self._revision

    @property
    def used_units(self) -> int:
        with self._lock:
            return self._used_units

    def append(self, segment: TranscriptSegment) -> int:
        if not segment.is_final:
            raise ValueError("only final transcript segments can enter decision context")
        if not segment.text.strip():
            raise ValueError("transcript text must not be empty")
        segment, units = self._fit_turn(segment, self.max_units)
        with self._lock:
            while self._turns and self._used_units + units > self.max_units:
                _, removed_units = self._turns.popleft()
                self._used_units -= removed_units
            self._turns.append((segment, units))
            self._used_units += units
            self._revision += 1
            return self._revision

    def snapshot(self) -> tuple[TranscriptSegment, ...]:
        with self._lock:
            return tuple(segment for segment, _ in self._turns)
