import numpy as np
import pytest
import wave
from dataclasses import replace

from emotionscreen.core.acoustic import AcousticEmotionAnalyzer, AudioStateTracker
from emotionscreen.core.audio import load_pcm_wav
from emotionscreen.core.audio_policy import AudioFeedbackPolicy
from emotionscreen.core.context import ConversationContext
from emotionscreen.core.decision import ClefDecisionProvider, DecisionError, MockDecisionProvider
from emotionscreen.core.models import DecisionRequest, DecisionResult, TranscriptSegment
from emotionscreen.core.policy import ResponsePolicy


def test_short_context_and_mock_scenarios_fail_closed():
    context = ConversationContext(max_units=2)
    context.append(TranscriptSegment("old", language="en"))
    context.append(TranscriptSegment("middle", language="en"))
    revision = context.append(TranscriptSegment("latest", language="en"))
    assert revision == 3 and [turn.text for turn in context.snapshot()] == ["middle", "latest"]
    assert context.used_units == 2 and ConversationContext(max_units=2).snapshot() == ()
    with pytest.raises(ValueError):
        context.append(TranscriptSegment("partial", is_final=False))

    expected = {
        "user_achievement": "celebrate", "user_praise": "acknowledge", "user_sadness": "support",
        "small_progress": "acknowledge", "ordinary_chat": "none", "sarcasm": "celebrate",
        "other_person": "celebrate", "incomplete": "none", "uncertain": "support",
    }
    policy = ResponsePolicy(clock=lambda: 100.0)
    for index, (scenario_id, expected_action) in enumerate(expected.items()):
        request = DecisionRequest((TranscriptSegment("fixture text"),), 1, scenario_id)
        result = MockDecisionProvider().decide(request)
        event = policy.evaluate(result, request, latest_context_revision=1, now=100.0 + index * 100)
        if expected_action == "none" or scenario_id in {"sarcasm", "other_person", "incomplete", "uncertain"}:
            assert event is None
        else:
            assert event is not None and event.action == expected_action
    arbitrary = DecisionRequest((TranscriptSegment("arbitrary manual text"),), 1)
    assert MockDecisionProvider().decide(arbitrary).response == "none"


def test_session_context_counts_cjk_characters_and_english_lexical_tokens():
    chinese = ConversationContext(max_units=5)
    chinese.append(TranscriptSegment("甲乙丙", language="zh-CN"))
    chinese.append(TranscriptSegment("丁戊己", language="zh-CN"))
    assert [turn.text for turn in chinese.snapshot()] == ["丁戊己"]
    assert chinese.used_units == 3

    english = ConversationContext(max_units=4)
    english.append(TranscriptSegment("one two", language="en"))
    english.append(TranscriptSegment("three, four five", language="en"))
    assert [turn.text for turn in english.snapshot()] == ["three, four five"]
    assert english.used_units == 4

    oversized = ConversationContext(max_units=3)
    oversized.append(TranscriptSegment("one two three four", language="en"))
    assert oversized.snapshot()[0].text == "two three four"


def test_audio_state_transition_from_elevated_to_low_drives_support_and_silence_stays_quiet():
    sample_rate = 16_000
    seconds = 1.5
    time_axis = np.arange(round(sample_rate * seconds), dtype=np.float32) / sample_rate
    voice_like_tone = 0.08 * (
        np.sin(2 * np.pi * 125 * time_axis)
        + 0.3 * np.sin(2 * np.pi * 250 * time_axis)
        + 0.1 * np.sin(2 * np.pi * 375 * time_axis)
    )
    activated_tone = 0.08 * (
        np.sin(2 * np.pi * 200 * time_axis)
        + 0.3 * np.sin(2 * np.pi * 400 * time_axis)
        + 0.1 * np.sin(2 * np.pi * 600 * time_axis)
    )

    analyzer = AcousticEmotionAnalyzer()
    analysis = analyzer.analyze(voice_like_tone, sample_rate)
    activated = analyzer.analyze(activated_tone, sample_rate)
    tracker = AudioStateTracker(confirmations=2)
    policy = AudioFeedbackPolicy()
    assert tracker.update(activated) is None
    high_transition = tracker.update(activated)
    assert high_transition is not None and high_transition.state == "elevated"
    high_event = policy.evaluate(high_transition)
    assert high_event is not None and high_event.state == "elevated" and high_event.action == "acknowledge" and high_event.persistent
    assert tracker.update(analysis) is None
    low_transition = tracker.update(analysis)
    event = policy.evaluate(low_transition)

    assert analysis.quality == "usable"
    assert analysis.state == "low_arousal"
    assert event is not None and event.action == "support" and event.state == "low_arousal" and event.persistent
    assert policy.evaluate(low_transition).state == "low_arousal"
    assert AudioFeedbackPolicy().evaluate(low_transition, dnd=True) is None
    silence = analyzer.analyze(np.zeros_like(voice_like_tone), sample_rate)
    assert silence.state == "uncertain"
    assert tracker.update(silence) is None
    silence_transition = tracker.update(silence)
    neutral_event = policy.evaluate(silence_transition)
    assert neutral_event is not None and neutral_event.action == "listen" and neutral_event.state == "uncertain" and neutral_event.persistent


def test_public_wav_sample_can_enter_the_same_audio_pipeline(tmp_path):
    sample_rate = 16_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    signal = 0.08 * np.sin(2 * np.pi * 125 * time_axis)
    wav_path = tmp_path / "sample.wav"
    with wave.open(str(wav_path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(sample_rate)
        stream.writeframes((signal * 32767).astype("<i2").tobytes())

    samples, rate = load_pcm_wav(wav_path)
    analysis = AcousticEmotionAnalyzer().analyze(samples, rate)
    assert rate == sample_rate and analysis.quality == "usable" and analysis.state == "low_arousal"


def test_wav_loader_rejects_samples_longer_than_ten_seconds(tmp_path):
    wav_path = tmp_path / "long.wav"
    with wave.open(str(wav_path), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(16_000)
        stream.writeframes(np.zeros(16_000 * 10 + 1, dtype="<i2").tobytes())

    with pytest.raises(ValueError, match="10 seconds"):
        load_pcm_wav(wav_path)


def test_continuous_audio_state_changes_require_stable_consecutive_windows():
    sample_rate = 16_000
    time_axis = np.arange(sample_rate, dtype=np.float32) / sample_rate
    tone = 0.08 * np.sin(2 * np.pi * 125 * time_axis)
    low = AcousticEmotionAnalyzer().analyze(tone, sample_rate)
    elevated = replace(low, state="elevated", score=0.75)
    tracker = AudioStateTracker(confirmations=2)

    assert tracker.update(low) is None
    entered_low = tracker.update(low)
    assert entered_low is not None and entered_low.previous_state == "uncertain" and entered_low.state == "low_arousal"
    assert tracker.update(low) is None
    assert tracker.update(elevated) is None
    entered_elevated = tracker.update(elevated)
    assert entered_elevated is not None and entered_elevated.state == "elevated"


def test_acoustic_state_is_stable_when_microphone_gain_changes():
    sample_rate = 16_000
    time_axis = np.arange(round(sample_rate * 1.5), dtype=np.float32) / sample_rate
    voice_like = (
        np.sin(2 * np.pi * 125 * time_axis)
        + 0.3 * np.sin(2 * np.pi * 250 * time_axis)
        + 0.1 * np.sin(2 * np.pi * 375 * time_axis)
    )
    analyzer = AcousticEmotionAnalyzer()

    normal = analyzer.analyze(0.08 * voice_like, sample_rate)
    quiet = analyzer.analyze(0.002 * voice_like, sample_rate)

    assert normal.quality == quiet.quality == "usable"
    assert normal.state == quiet.state == "low_arousal"


def test_policy_dedupes_suppresses_dnd_and_does_not_queue_overlapping_events():
    provider = MockDecisionProvider()
    policy = ResponsePolicy()
    first = DecisionRequest((TranscriptSegment("exam passed"),), 1, "user_achievement")
    second = DecisionRequest((TranscriptSegment("teacher praised me"),), 2, "user_praise")
    assert policy.evaluate(provider.decide(first), first, latest_context_revision=1, now=100) is not None
    assert policy.evaluate(provider.decide(second), second, latest_context_revision=2, popup_active=True, now=101) is None
    assert policy.evaluate(provider.decide(second), second, latest_context_revision=2, now=110) is None
    assert policy.evaluate(provider.decide(first), first, latest_context_revision=1, now=120) is None

    dnd_policy = ResponsePolicy()
    assert dnd_policy.evaluate(provider.decide(first), first, latest_context_revision=1, dnd=True, now=100) is None
    assert dnd_policy.evaluate(provider.decide(first), first, latest_context_revision=1, now=110) is None


def test_sarcastic_or_ambiguous_attitude_fails_closed_even_if_response_is_supportive():
    request = DecisionRequest((TranscriptSegment("I am so brilliant; I forgot my keys again."),), 1, "user_sadness")
    result = MockDecisionProvider().decide(request)
    result = result.__class__(**{**result.__dict__, "attitude": "sarcastic"})

    assert ResponsePolicy().evaluate(result, request, latest_context_revision=1) is None
    inconsistent = result.__class__(**{**result.__dict__, "attitude": "explicit", "intensity": "none"})
    assert ResponsePolicy().evaluate(inconsistent, request, latest_context_revision=1) is None


def test_clef_marked_repeat_of_a_prior_event_is_suppressed():
    request = DecisionRequest((TranscriptSegment("I got the scholarship"), TranscriptSegment("I got the scholarship again")), 2)
    result = DecisionResult(
        relevance="user", event_status="confirmed", attitude="explicit", event_relation="same_event",
        response="celebrate", intensity="gentle", timing="now", source="clef", context_revision=2,
    )

    assert ResponsePolicy().evaluate(result, request, latest_context_revision=2) is None


def test_clef_systemone_schema_and_stats_are_parsed_without_fabrication():
    choices = {
        "relevance": "user", "event_status": "confirmed", "response": "celebrate",
        "attitude": "explicit", "event_relation": "new_event", "intensity": "gentle", "timing": "now",
    }
    response = {"event_id": "event-1", "answers": {
        name: {"type": "choice", "choice": value, "probabilities": {value: 1.0}, "confidence": 0.9}
        for name, value in choices.items()
    }}
    captured = {}

    def transport(url, payload, timeout):
        captured.update(url=url, payload=payload, timeout=timeout)
        return response

    context = ConversationContext()
    context.append(TranscriptSegment("I passed my exam", language="en"))
    request = DecisionRequest(context.snapshot(), context.revision, "user_achievement")
    result = ClefDecisionProvider("http://127.0.0.1:18080", timeout_seconds=7, transport=transport).decide(request)

    assert captured["url"] == "http://127.0.0.1:18080/v1/systemone" and captured["timeout"] == 7
    assert captured["payload"]["questions"]["response"]["type"] == "choice"
    assert "I passed my exam" in captured["payload"]["state"]
    assert result.source == "clef" and result.response == "celebrate" and result.event_id == "event-1"
    assert result.confidence["response"] == 0.9

    with pytest.raises(DecisionError):
        ClefDecisionProvider("http://127.0.0.1", transport=lambda *_: {"answers": {}}).decide(request)
    with pytest.raises(DecisionError, match="offline"):
        ClefDecisionProvider("http://127.0.0.1", transport=lambda *_: (_ for _ in ()).throw(ConnectionError("offline"))).decide(request)
    with pytest.raises(DecisionError, match="loopback"):
        ClefDecisionProvider("https://example.com")
