"""Map decisions and immediate acoustic energy into safe visual parameters."""

from __future__ import annotations

from .models import AcousticFeatures, DecisionResult, VisualState

_COLORS = {
    "happy": "#f4c95d", "excited": "#ff704d", "sad": "#567ca5", "angry": "#d94b4b",
    "anxious": "#ad78bd", "fearful": "#68758d", "tired": "#64748b", "calm": "#62b6a7",
    "uncertain": "#75849a",
}


class ReactionController:
    def create(self, decision: DecisionResult, features: AcousticFeatures) -> VisualState:
        energy = min(1.0, max(0.0, features.rms * 2.5))
        return VisualState(
            emotion=decision.emotion, theme_color=_COLORS.get(decision.emotion, _COLORS["uncertain"]),
            glow_intensity=0.15 + 0.7 * energy,
            animation_speed=0.65 + energy * 1.5,
            particle_count=round(4 + 14 * energy),
            motion_amplitude=0.1 + energy * 0.6,
            transition_seconds=0.5, energy_level=energy,
        )
