import threading
import time

import numpy as np

from emotionscreen.core.audio import AudioRingBuffer, MockAudioInput
from emotionscreen.core.models import AcousticFeatures, DecisionResult
from emotionscreen.core.runtime import SingleFlightDecider


def test_mock_audio_requires_explicit_start_and_returns_fixed_frames():
    audio = MockAudioInput(sample_rate=1_000, frame_ms=20, seed=3)

    try:
        audio.read_frame()
        assert False, "reading before start must fail"
    except RuntimeError:
        pass

    audio.start()
    frame = audio.read_frame()
    audio.stop()

    assert frame.shape == (20,)
    assert np.isfinite(frame).all()
    assert not audio.is_running


def test_audio_ring_buffer_keeps_tail_when_a_single_frame_exceeds_capacity():
    buffer = AudioRingBuffer(capacity_samples=4)

    buffer.append(np.array([1, 2, 3, 4, 5, 6]))

    np.testing.assert_array_equal(buffer.snapshot(), np.array([3, 4, 5, 6], dtype=np.float32))


def test_single_flight_decider_keeps_only_the_latest_pending_snapshot():
    entered = threading.Event()
    release = threading.Event()
    received = []

    class Provider:
        def decide(self, features):
            received.append(features.rms)
            if len(received) == 1:
                entered.set()
                release.wait(timeout=2)
            return DecisionResult("calm", {"calm": 1.0}, 1.0, "mock")

    decider = SingleFlightDecider(Provider())
    decider.submit(AcousticFeatures(rms=1.0))
    assert entered.wait(timeout=1)
    decider.submit(AcousticFeatures(rms=2.0))
    decider.submit(AcousticFeatures(rms=3.0))

    assert received == [1.0]
    release.set()
    deadline = time.monotonic() + 1
    while len(received) < 2 and time.monotonic() < deadline:
        decider.poll()
        time.sleep(0.01)

    assert received == [1.0, 3.0]
    decider.close()
