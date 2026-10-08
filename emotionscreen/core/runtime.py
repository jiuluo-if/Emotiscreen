"""单在途决策线程与过期上下文丢弃。"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import threading

from .context import ConversationContext
from .decision import DecisionProvider
from .models import DecisionRequest, DecisionResult, ResponseEvent, TranscriptSegment
from .policy import ResponsePolicy


@dataclass(frozen=True)
class DecisionEnvelope:
    request: DecisionRequest
    result: DecisionResult


class LatestDecisionWorker:
    def __init__(self, provider: DecisionProvider) -> None:
        self._provider = provider
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="emotiscreen-decision")
        self._future: Future[DecisionEnvelope] | None = None
        self._pending: DecisionRequest | None = None
        self._lock = threading.Lock()
        self._closed = False
        self.last_error: str | None = None

    def submit(self, request: DecisionRequest) -> None:
        with self._lock:
            if self._closed:
                return
            if self._future is None:
                self._future = self._executor.submit(self._run, request)
            else:
                self._pending = request

    def _run(self, request: DecisionRequest) -> DecisionEnvelope:
        return DecisionEnvelope(request, self._provider.decide(request))

    def poll(self) -> list[DecisionEnvelope]:
        completed: list[DecisionEnvelope] = []
        with self._lock:
            if self._future is not None and self._future.done():
                try:
                    completed.append(self._future.result())
                    self.last_error = None
                except Exception as exc:
                    self.last_error = str(exc)
                self._future = None
                if self._pending is not None and not self._closed:
                    request, self._pending = self._pending, None
                    self._future = self._executor.submit(self._run, request)
        return completed

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._pending = None
        self._executor.shutdown(wait=False, cancel_futures=True)


class ConversationRuntime:
    def __init__(
        self,
        provider: DecisionProvider,
        *,
        context: ConversationContext | None = None,
        policy: ResponsePolicy | None = None,
    ) -> None:
        self.context = context or ConversationContext()
        self.policy = policy or ResponsePolicy()
        self.worker = LatestDecisionWorker(provider)
        self.last_error: str | None = None
        self.last_decision: DecisionResult | None = None

    def switch_provider(self, provider: DecisionProvider) -> None:
        self.worker.close()
        self.worker = LatestDecisionWorker(provider)
        self.last_error = None
        self.last_decision = None

    def ingest(self, segment: TranscriptSegment, scenario_id: str | None = None) -> DecisionRequest | None:
        if not segment.is_final:
            return None
        revision = self.context.append(segment)
        request = DecisionRequest(self.context.snapshot(), revision, scenario_id)
        self.worker.submit(request)
        return request

    def poll(
        self,
        *,
        language: str = "zh-CN",
        dnd: bool = False,
        paused: bool = False,
        popup_active: bool = False,
        listening: bool = False,
    ) -> list[ResponseEvent]:
        events: list[ResponseEvent] = []
        current_revision = self.context.revision
        for envelope in self.worker.poll():
            if envelope.request.context_revision != current_revision:
                continue
            if envelope.result.context_revision != envelope.request.context_revision:
                continue
            self.last_decision = envelope.result
            event = self.policy.evaluate(
                envelope.result,
                envelope.request,
                latest_context_revision=current_revision,
                language=language,
                dnd=dnd,
                paused=paused,
                popup_active=popup_active,
                listening=listening,
            )
            if event is not None and event.action != "listen":
                events.append(event)
        self.last_error = self.worker.last_error
        return events

    def close(self) -> None:
        self.worker.close()
