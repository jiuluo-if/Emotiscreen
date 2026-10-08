"""Shared immutable data structures passed between application modules."""

from __future__ import annotations

from dataclasses import dataclass, field
import time

EMOTIONS = ("happy", "excited", "sad", "angry", "anxious", "fearful", "tired", "calm", "uncertain")


@dataclass(frozen=True)
class AcousticFeatures:
    sample_rate: int = 16_000
    rms: float = 0.0
    peak: float = 0.0
    energy_change: float = 0.0
    f0_hz: float | None = None
    f0_voiced_ratio: float = 0.0
    pitch_range_hz: float | None = None
    voiced_ratio: float = 0.0
    pause_ratio: float = 1.0
    rhythm_rate_hz: float = 0.0
    spectral_centroid_hz: float = 0.0
    spectral_flux: float = 0.0
    zero_crossing_rate: float = 0.0
    quality: str = "unknown"
    quality_flags: tuple[str, ...] = ()
    captured_at: float = field(default_factory=time.monotonic, compare=False)


@dataclass(frozen=True)
class DecisionResult:
    emotion: str
    probabilities: dict[str, float]
    confidence: float | None
    source: str
    arousal: str = "unknown"
    screen_mode: str = "breathing"
    latency_ms: float = 0.0
    created_at: float = field(default_factory=time.monotonic, compare=False)
    note: str = ""


@dataclass(frozen=True)
class VisualState:
    emotion: str = "uncertain"
    theme_color: str = "#75849a"
    glow_intensity: float = 0.0
    animation_speed: float = 1.0
    particle_count: int = 0
    motion_amplitude: float = 0.0
    transition_seconds: float = 0.5
    energy_level: float = 0.0
