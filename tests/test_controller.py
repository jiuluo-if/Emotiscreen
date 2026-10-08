from emotionscreen.core.controller import ReactionController
from emotionscreen.core.models import AcousticFeatures, DecisionResult


def test_reaction_controller_maps_emotion_and_fast_energy():
    state = ReactionController().create(
        DecisionResult("happy", {"happy": 1.0}, 0.9, "mock"),
        AcousticFeatures(rms=0.5, sample_rate=16_000),
    )

    assert state.emotion == "happy"
    assert state.energy_level > 0
    assert state.theme_color.startswith("#")
