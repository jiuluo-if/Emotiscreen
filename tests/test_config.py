import json

import pytest

from emotionscreen.config import ConfigError, load_config


def test_default_configuration_is_mock_and_uses_portable_audio_settings(tmp_path):
    config = load_config(tmp_path / "missing.json")

    assert config.mode == "mock"
    assert config.audio.sample_rate == 16_000
    assert config.audio.device is None
    assert config.decision.provider == "mock"


def test_configuration_rejects_out_of_range_values(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"audio": {"sample_rate": 0}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="sample_rate"):
        load_config(path)


def test_configuration_rejects_unknown_mode(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mode": "production"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="mode"):
        load_config(path)


def test_live_mode_requires_clef_provider(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mode": "live"}), encoding="utf-8")

    with pytest.raises(ConfigError, match="provider='clef'"):
        load_config(path)


def test_mock_mode_rejects_clef_provider(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"decision": {"provider": "clef"}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="mock mode requires"):
        load_config(path)


def test_configuration_rejects_non_numeric_sample_rate(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"audio": {"sample_rate": "fast"}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="audio.sample_rate"):
        load_config(path)


def test_configuration_requires_real_boolean_visual_options(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"visual": {"animation_enabled": "yes"}}), encoding="utf-8")

    with pytest.raises(ConfigError, match="visual.animation_enabled"):
        load_config(path)
