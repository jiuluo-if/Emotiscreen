"""Latest-only decision worker, isolated from the GUI/event loop."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading

from .decision import DecisionProvider
from .models import AcousticFeatures, DecisionResult


class SingleFlightDecider:
    def __init__(self, provider: DecisionProvider) -> None:
        self.provider = provider
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emotion-decision")
        self._future: Future[DecisionResult] | None = None
        self._pending: AcousticFeatures | None = None
        self._lock = threading.Lock()
        self.last_error: str | None = None
        self._closed = False

    def submit(self, features: AcousticFeatures) -> None:
        with self._lock:
            if self._closed:
                return
            if self._future is None:
                self._future = self._executor.submit(self.provider.decide, features)
            else:
                self._pending = features

    def poll(self) -> list[DecisionResult]:
        completed: list[DecisionResult] = []
        with self._lock:
            if self._future is not None and self._future.done():
                try:
                    completed.append(self._future.result())
                    self.last_error = None
                except Exception as exc:  # surfaced to the UI without killing its event loop
                    self.last_error = str(exc)
                self._future = None
                if self._pending is not None and not self._closed:
                    latest = self._pending
                    self._pending = None
                    self._future = self._executor.submit(self.provider.decide, latest)
        return completed

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._pending = None
        self._executor.shutdown(wait=False, cancel_futures=True)
