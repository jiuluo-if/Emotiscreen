from emotionscreen.core.models import DecisionResult
from emotionscreen.core.smoothing import EmotionSmoother


def result(emotion, *, at, source="mock"):
    return DecisionResult(
        emotion=emotion,
        probabilities={emotion: 1.0},
        confidence=1.0,
        source=source,
        created_at=at,
    )


def test_smoother_requires_confirmation_before_switching():
    smoother = EmotionSmoother(confirm_count=2, min_hold_seconds=0)

    assert smoother.update(result("calm", at=1.0)).emotion == "calm"
    assert smoother.update(result("happy", at=2.0)).emotion == "calm"
    assert smoother.update(result("happy", at=3.0)).emotion == "happy"


def test_uncertain_decision_does_not_overwrite_current_emotion():
    smoother = EmotionSmoother(confirm_count=1, min_hold_seconds=0)
    smoother.update(result("calm", at=1.0))

    state = smoother.update(result("uncertain", at=2.0))

    assert state.emotion == "calm"


def test_initial_uncertain_decision_uses_fallback_without_claiming_confidence():
    smoother = EmotionSmoother(uncertain_fallback="calm")

    state = smoother.update(result("uncertain", at=1.0))

    assert state.emotion == "calm"
    assert state.confidence is None
