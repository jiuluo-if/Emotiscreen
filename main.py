"""Launch EmotionScreen, or run its model-free pipeline check headlessly."""

from __future__ import annotations

import argparse
from pathlib import Path

from emotionscreen.config import ConfigError, load_config
from emotionscreen.core.audio import MockAudioInput
from emotionscreen.core.decision import MockDecisionProvider
from emotionscreen.core.features import FeatureExtractor


def run_mock_check(config) -> int:
    audio = MockAudioInput(config.audio.sample_rate, config.audio.frame_ms, config.decision.seed)
    audio.start()
    frames = [audio.read_frame() for _ in range(round(1_000 / config.audio.frame_ms))]
    audio.stop()
    import numpy as np

    samples = np.concatenate(frames)
    features = FeatureExtractor().extract(samples, config.audio.sample_rate)
    result = MockDecisionProvider(seed=config.decision.seed).decide(features)
    print(f"Mock pipeline OK | rms={features.rms:.3f} | f0={features.f0_hz} | emotion={result.emotion} | source={result.source}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Local voice expression visualization demo")
    parser.add_argument("--config", type=Path, default=Path(__file__).with_name("config.json"))
    parser.add_argument("--check", action="store_true", help="run a model-free mock pipeline check without opening Tk")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
    except ConfigError as exc:
        parser.error(str(exc))
    if args.check:
        return run_mock_check(config)
    from emotionscreen.ui.window import EmotionWindow

    EmotionWindow(config).run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
