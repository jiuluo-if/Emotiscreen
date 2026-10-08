"""Validated JSON configuration for EmotionScreen."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Raised when configuration cannot be used safely."""


@dataclass(frozen=True)
class AudioConfig:
    sample_rate: int = 16_000
    channels: int = 1
    frame_ms: int = 32
    window_seconds: float = 2.0
    device: int | str | None = None


@dataclass(frozen=True)
class DecisionConfig:
    provider: str = "mock"
    clef_base_url: str = "http://127.0.0.1:8080"
    timeout_seconds: float = 5.0
    interval_ms: int = 1_000
    seed: int = 42


@dataclass(frozen=True)
class VisualConfig:
    fps: int = 30
    animation_enabled: bool = True
    overlay_enabled: bool = False


@dataclass(frozen=True)
class EmotionConfig:
    smoothing_alpha: float = 0.35
    min_hold_ms: int = 1_500
    confirm_count: int = 2
    uncertain_fallback: str = "calm"


@dataclass(frozen=True)
class AppConfig:
    mode: str = "mock"
    audio: AudioConfig = field(default_factory=AudioConfig)
    decision: DecisionConfig = field(default_factory=DecisionConfig)
    visual: VisualConfig = field(default_factory=VisualConfig)
    emotion: EmotionConfig = field(default_factory=EmotionConfig)


def _merge_defaults(raw: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "mode": "mock",
        "audio": {"sample_rate": 16_000, "channels": 1, "frame_ms": 32, "window_seconds": 2.0, "device": None},
        "decision": {
            "provider": "mock", "clef_base_url": "http://127.0.0.1:8080", "timeout_seconds": 5.0,
            "interval_ms": 1_000, "seed": 42,
        },
        "visual": {"fps": 30, "animation_enabled": True, "overlay_enabled": False},
        "emotion": {"smoothing_alpha": 0.35, "min_hold_ms": 1_500, "confirm_count": 2, "uncertain_fallback": "calm"},
    }
    result = defaults
    for section, values in raw.items():
        if section not in result:
            raise ConfigError(f"unknown configuration section: {section}")
        if section == "mode":
            result[section] = values
            continue
        if not isinstance(values, dict):
            raise ConfigError(f"{section} must be an object")
        unknown = set(values) - set(result[section])
        if unknown:
            raise ConfigError(f"unknown {section} option(s): {', '.join(sorted(unknown))}")
        result[section] = {**result[section], **values}
    return result


def load_config(path: str | Path = "config.json") -> AppConfig:
    """Read config, falling back to portable defaults when the file is absent."""
    config_path = Path(path)
    try:
        raw = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"cannot read {config_path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError("configuration root must be an object")
    values = _merge_defaults(raw)
    try:
        audio = AudioConfig(**values["audio"])
        decision = DecisionConfig(**values["decision"])
        visual = VisualConfig(**values["visual"])
        emotion = EmotionConfig(**values["emotion"])
    except TypeError as exc:
        raise ConfigError(str(exc)) from exc
    cfg = AppConfig(mode=values["mode"], audio=audio, decision=decision, visual=visual, emotion=emotion)
    _validate(cfg)
    return cfg


def _validate(cfg: AppConfig) -> None:
    if not isinstance(cfg.mode, str) or cfg.mode not in {"mock", "live"}:
        raise ConfigError("mode must be 'mock' or 'live'")
    if not isinstance(cfg.decision.provider, str) or cfg.decision.provider not in {"mock", "clef"}:
        raise ConfigError("decision.provider must be 'mock' or 'clef'")
    if cfg.mode == "live" and cfg.decision.provider == "mock":
        raise ConfigError("live mode requires decision.provider='clef'")
    if cfg.mode == "mock" and cfg.decision.provider != "mock":
        raise ConfigError("mock mode requires decision.provider='mock'")
    for name, value in (
        ("visual.animation_enabled", cfg.visual.animation_enabled),
        ("visual.overlay_enabled", cfg.visual.overlay_enabled),
    ):
        if not isinstance(value, bool):
            raise ConfigError(f"{name} must be a boolean")
    if cfg.audio.device is not None and (not isinstance(cfg.audio.device, (str, int)) or isinstance(cfg.audio.device, bool)):
        raise ConfigError("audio.device must be a device name, index, or null")
    if not isinstance(cfg.decision.seed, int) or isinstance(cfg.decision.seed, bool):
        raise ConfigError("decision.seed must be an integer")
    for name, value, low, high in (
        ("audio.sample_rate", cfg.audio.sample_rate, 8_000, 192_000),
        ("audio.channels", cfg.audio.channels, 1, 2),
        ("audio.frame_ms", cfg.audio.frame_ms, 10, 100),
        ("visual.fps", cfg.visual.fps, 10, 60),
        ("emotion.confirm_count", cfg.emotion.confirm_count, 1, 20),
    ):
        if not isinstance(value, int) or isinstance(value, bool):
            raise ConfigError(f"{name} must be an integer")
        if not low <= value <= high:
            raise ConfigError(f"{name} must be between {low} and {high}")
    for name, value, low, high in (
        ("audio.window_seconds", cfg.audio.window_seconds, 0.25, 10.0),
        ("decision.timeout_seconds", cfg.decision.timeout_seconds, 0.1, 60.0),
        ("emotion.smoothing_alpha", cfg.emotion.smoothing_alpha, 0.0, 1.0),
    ):
        if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
            raise ConfigError(f"{name} must be a finite number")
        if not low <= value <= high:
            raise ConfigError(f"{name} must be between {low} and {high}")
    if not isinstance(cfg.decision.interval_ms, int) or isinstance(cfg.decision.interval_ms, bool):
        raise ConfigError("decision.interval_ms must be an integer")
    if not 100 <= cfg.decision.interval_ms <= 60_000:
        raise ConfigError("decision.interval_ms must be between 100 and 60000")
    if not isinstance(cfg.emotion.min_hold_ms, int) or isinstance(cfg.emotion.min_hold_ms, bool):
        raise ConfigError("emotion.min_hold_ms must be an integer")
    if not 0 <= cfg.emotion.min_hold_ms <= 60_000:
        raise ConfigError("emotion.min_hold_ms must be between 0 and 60000")
    if not isinstance(cfg.emotion.uncertain_fallback, str) or cfg.emotion.uncertain_fallback not in {"calm", "uncertain"}:
        raise ConfigError("emotion.uncertain_fallback must be 'calm' or 'uncertain'")
    if cfg.decision.provider == "clef" and (
        not isinstance(cfg.decision.clef_base_url, str)
        or not cfg.decision.clef_base_url.startswith(("http://", "https://"))
    ):
        raise ConfigError("decision.clef_base_url must use http:// or https://")
