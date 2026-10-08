import pytest

from emotionscreen.core.decision import ClefDecisionProvider, DecisionError, MockDecisionProvider
from emotionscreen.core.models import AcousticFeatures


def test_mock_provider_is_reproducible_and_explicitly_marked():
    features = AcousticFeatures(sample_rate=16_000)
    first = MockDecisionProvider(seed=9).decide(features)
    second = MockDecisionProvider(seed=9).decide(features)

    assert first.emotion == second.emotion
    assert first.probabilities == second.probabilities
    assert first.source == "mock"
    assert sum(first.probabilities.values()) == pytest.approx(1.0)


def test_clef_provider_parses_choice_without_confusing_confidence_and_probability():
    payload = {
        "choices": {
            "emotion": {
                "selected": "calm",
                "probabilities": {"calm": 0.7, "happy": 0.3},
                "confidence": 0.82,
            },
            "arousal": {"selected": "low"},
            "screen_mode": {"selected": "breathing"},
        }
    }
    provider = ClefDecisionProvider("http://localhost:8080", transport=lambda *_: payload)

    result = provider.decide(AcousticFeatures(sample_rate=16_000))

    assert result.source == "clef"
    assert result.emotion == "calm"
    assert result.probabilities["calm"] == 0.7
    assert result.confidence == 0.82


@pytest.mark.parametrize(
    "emotion_choice",
    [
        {"selected": "calm", "probabilities": {"calm": 2.0}},
        {"selected": "calm", "probabilities": {"calm": 0.2}},
        {"selected": "calm", "probabilities": {"calm": True}},
        {"selected": "not_a_class", "probabilities": {"not_a_class": 1.0}},
    ],
)
def test_clef_provider_rejects_invalid_probability_or_emotion(emotion_choice):
    payload = {
        "choices": {
            "emotion": emotion_choice,
            "arousal": {"selected": "low"},
            "screen_mode": {"selected": "breathing"},
        }
    }
    provider = ClefDecisionProvider("http://localhost:8080", transport=lambda *_: payload)

    with pytest.raises(DecisionError):
        provider.decide(AcousticFeatures(sample_rate=16_000))


def test_clef_provider_rejects_missing_fields():
    provider = ClefDecisionProvider("http://localhost:8080", transport=lambda *_: {})

    with pytest.raises(DecisionError, match="choices"):
        provider.decide(AcousticFeatures(sample_rate=16_000))


@pytest.mark.parametrize(
    "choices",
    [
        {"emotion": {"selected": "calm", "probabilities": {"happy": 1.0}}},
        {"emotion": {"selected": "calm", "probabilities": {"calm": 1.0}}, "arousal": {"selected": "extreme"}},
        {"emotion": {"selected": "calm", "probabilities": {"calm": 1.0}}, "arousal": {"selected": []}},
        {"emotion": {"selected": "calm", "probabilities": {"calm": 1.0}}, "screen_mode": {"selected": "flash"}},
    ],
)
def test_clef_provider_rejects_inconsistent_or_unsupported_choices(choices):
    choices.setdefault("arousal", {"selected": "low"})
    choices.setdefault("screen_mode", {"selected": "breathing"})
    provider = ClefDecisionProvider("http://localhost:8080", transport=lambda *_: {"choices": choices})

    with pytest.raises(DecisionError):
        provider.decide(AcousticFeatures(sample_rate=16_000))


def test_clef_provider_reports_timeout_as_decision_error():
    def timeout(*_):
        raise TimeoutError("timed out")

    provider = ClefDecisionProvider("http://localhost:8080", transport=timeout)

    with pytest.raises(DecisionError, match="timed out"):
        provider.decide(AcousticFeatures(sample_rate=16_000))
