"""Single background worker that keeps only the newest audio snapshot."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import threading

import numpy as np

from .acoustic import AcousticAnalysis, AcousticEmotionAnalyzer


@dataclass(frozen=True)
class AudioAnalysisResult:
    revision: int
    analysis: AcousticAnalysis


class AudioAnalysisWorker:
    def __init__(self, analyzer: AcousticEmotionAnalyzer | None = None) -> None:
        self._analyzer = analyzer or AcousticEmotionAnalyzer()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emotiscreen-audio")
        self._future: Future[AudioAnalysisResult] | None = None
        self._pending: tuple[int, np.ndarray, int] | None = None
        self._lock = threading.Lock()
        self._revision = 0
        self._closed = False
        self.last_error: str | None = None

    def submit(self, samples: np.ndarray, sample_rate: int) -> int:
        snapshot = np.asarray(samples, dtype=np.float32).reshape(-1).copy()
        with self._lock:
            if self._closed:
                return self._revision
            self._revision += 1
            job = (self._revision, snapshot, sample_rate)
            if self._future is None:
                self._future = self._executor.submit(self._run, job)
            else:
                self._pending = job
            return self._revision

    def _run(self, job: tuple[int, np.ndarray, int]) -> AudioAnalysisResult:
        revision, samples, sample_rate = job
        return AudioAnalysisResult(revision, self._analyzer.analyze(samples, sample_rate))

    def poll(self) -> list[AudioAnalysisResult]:
        with self._lock:
            if self._future is None or not self._future.done():
                return []
            future, self._future = self._future, None
            try:
                result = future.result()
                self.last_error = None
            except Exception as exc:
                self.last_error = str(exc)
                result = None
            if self._pending is not None and not self._closed:
                job, self._pending = self._pending, None
                self._future = self._executor.submit(self._run, job)
                return []
            if result is None or result.revision != self._revision:
                return []
            return [result]

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._pending = None
        self._executor.shutdown(wait=False, cancel_futures=True)
