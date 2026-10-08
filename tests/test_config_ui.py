import json

import pytest

from emotionscreen.config import ConfigError, load_config
from emotionscreen.ui.glass import apply_glass, should_reduce_motion


def test_mock_defaults_config_validation_and_platform_fallback(tmp_path, monkeypatch):
    config = load_config(tmp_path / "missing.json")
    assert config.mode == "mock" and config.transcript.provider == "mock" and config.ui.language == "zh-CN"
    assert not hasattr(config.transcript, "asr_engine")

    live = tmp_path / "live.json"
    live.write_text(json.dumps({"mode": "live", "decision": {"provider": "acoustic"}}), encoding="utf-8")
    assert load_config(live).decision.provider == "acoustic"

    invalid = tmp_path / "bad.json"
    invalid.write_text(json.dumps({"ui": {"language": "fr"}}), encoding="utf-8")
    with pytest.raises(ConfigError):
        load_config(invalid)

    remote = tmp_path / "remote.json"
    remote.write_text(json.dumps({"mode": "live", "decision": {"provider": "acoustic", "clef_base_url": "https://example.com"}}), encoding="utf-8")
    with pytest.raises(ConfigError, match="loopback"):
        load_config(remote)

    monkeypatch.setattr("emotionscreen.ui.glass.sys.platform", "darwin")
    assert apply_glass(None).native_blur is False
    assert should_reduce_motion(user_static_mode=True) is True
