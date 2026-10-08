import json
from types import SimpleNamespace

import pytest

from emotionscreen.config import ConfigError, load_config
from emotionscreen.ui.window import EmotionWindow
from emotionscreen.ui.glass import apply_glass, emotion_palette, interpolate_color, should_reduce_motion


def test_mock_defaults_config_validation_and_platform_fallback(tmp_path, monkeypatch):
    config = load_config(tmp_path / "missing.json")
    assert config.mode == "mock" and config.transcript.provider == "mock" and config.ui.language == "zh-CN"
    assert config.ui.motion_strength == 0.72
    assert config.context.max_units == 2000
    assert not hasattr(config.transcript, "asr_engine")

    live = tmp_path / "live.json"
    live.write_text(json.dumps({"mode": "live", "decision": {"provider": "acoustic"}}), encoding="utf-8")
    assert load_config(live).decision.provider == "acoustic"

    invalid = tmp_path / "bad.json"
    invalid.write_text(json.dumps({"ui": {"language": "fr"}}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(invalid)

    invalid_context = tmp_path / "invalid-context.json"
    invalid_context.write_text(json.dumps({"context": {"max_units": 2001}}), encoding="utf-8")
    with pytest.raises(ConfigError, match="max_units"):
        load_config(invalid_context)

    remote = tmp_path / "remote.json"
    remote.write_text(json.dumps({"mode": "live", "decision": {"provider": "acoustic", "clef_base_url": "https://example.com"}}), encoding="utf-8")
    with pytest.raises(ConfigError, match="loopback"):
        load_config(remote)

    monkeypatch.setattr("emotionscreen.ui.glass.sys.platform", "darwin")
    assert apply_glass(None).native_blur is False
    assert should_reduce_motion(user_static_mode=True) is True


def test_glass_theme_color_interpolates_between_emotion_endpoints():
    assert interpolate_color("#102030", "#90A0B0", 0.0) == "#102030"
    assert interpolate_color("#102030", "#90A0B0", 0.5) == "#506070"
    assert interpolate_color("#102030", "#90A0B0", 1.0) == "#90A0B0"
    assert emotion_palette("low_arousal").start != emotion_palette("elevated").start
    assert emotion_palette("unknown").start == emotion_palette("uncertain").start


def test_live_listening_restores_missing_overlay_but_respects_manual_dismissal():
    class Overlay:
        visible = False
        persistent = False

        def __init__(self):
            self.shown = []

        def show_audio_state(self, state, language):
            self.shown.append((state, language))
            self.visible = True
            self.persistent = True

    app = SimpleNamespace(
        config=SimpleNamespace(mode="live"),
        _listening=True,
        _paused=False,
        _dnd=False,
        _audio_overlay_dismissed=False,
        _audio_state="elevated",
        _language="zh-CN",
        comfort=Overlay(),
    )

    EmotionWindow._ensure_live_audio_overlay(app)
    assert app.comfort.shown == [("elevated", "zh-CN")]

    app.comfort.visible = False
    app._audio_overlay_dismissed = True
    EmotionWindow._ensure_live_audio_overlay(app)
    assert app.comfort.shown == [("elevated", "zh-CN")]
