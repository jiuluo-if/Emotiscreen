import threading
import time

import numpy as np

from emotionscreen.core.audio_runtime import AudioAnalysisWorker
from emotionscreen.core.decision import MockDecisionProvider
from emotionscreen.core.models import DecisionRequest, TranscriptSegment
from emotionscreen.core.runtime import ConversationRuntime


def test_outdated_clef_result_is_dropped_and_latest_context_is_used():
    entered = threading.Event()
    release = threading.Event()
    mock = MockDecisionProvider()

    class SlowFirst:
        def decide(self, request: DecisionRequest):
            if request.context_revision == 1:
                entered.set()
                release.wait(timeout=2)
            return mock.decide(request)

    runtime = ConversationRuntime(SlowFirst())
    runtime.ingest(TranscriptSegment("exam passed"), "user_achievement")
    assert entered.wait(timeout=1)
    runtime.ingest(TranscriptSegment("teacher praised me"), "user_praise")
    release.set()
    deadline = time.monotonic() + 2
    events = []
    try:
        while not events and time.monotonic() < deadline:
            events.extend(runtime.poll())
            time.sleep(0.01)
        assert len(events) == 1 and events[0].action == "acknowledge"
    finally:
        runtime.close()


def test_clef_disconnect_can_switch_back_to_mock_without_crashing():
    class Offline:
        def decide(self, _request):
            raise ConnectionError("Clef offline")

    runtime = ConversationRuntime(Offline())
    runtime.ingest(TranscriptSegment("hello"), "ordinary_chat")
    deadline = time.monotonic() + 1
    try:
        while runtime.last_error is None and time.monotonic() < deadline:
            runtime.poll()
            time.sleep(0.01)
        assert "offline" in runtime.last_error
        runtime.switch_provider(MockDecisionProvider())
        runtime.ingest(TranscriptSegment("exam passed"), "user_achievement")
        deadline = time.monotonic() + 1
        events = []
        while not events and time.monotonic() < deadline:
            events.extend(runtime.poll())
            time.sleep(0.01)
        assert len(events) == 1 and events[0].action == "celebrate"
    finally:
        runtime.close()


def test_audio_analysis_worker_returns_only_latest_snapshot():
    sample_rate = 16_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    audio = 0.08 * np.sin(2 * np.pi * 125 * time_axis)
    worker = AudioAnalysisWorker()
    try:
        revision = worker.submit(audio, sample_rate)
        deadline = time.monotonic() + 2
        result = []
        while not result and time.monotonic() < deadline:
            result = worker.poll()
            time.sleep(0.01)
        assert len(result) == 1 and result[0].revision == revision
        assert result[0].analysis.quality == "usable"
    finally:
        worker.close()
