import numpy as np

from emotionscreen.core.features import FeatureExtractor


def test_silence_has_zero_energy_and_no_claimed_pitch():
    features = FeatureExtractor().extract(np.zeros(32_000), sample_rate=16_000)

    assert features.rms == 0
    assert features.f0_hz is None
    assert features.voiced_ratio == 0
    assert features.pause_ratio == 1


def test_sine_wave_has_pitch_and_finite_spectral_features():
    sample_rate = 16_000
    t = np.arange(sample_rate) / sample_rate
    signal = 0.4 * np.sin(2 * np.pi * 220 * t)

    features = FeatureExtractor().extract(signal, sample_rate=sample_rate)

    assert features.f0_hz is not None
    assert abs(features.f0_hz - 220) < 8
    assert features.voiced_ratio > 0.8
    assert np.isfinite(features.spectral_centroid_hz)
    assert np.isfinite(features.zero_crossing_rate)


def test_deterministic_noise_has_finite_features_without_asserted_pitch():
    signal = np.random.default_rng(17).normal(0, 0.12, 16_000)

    features = FeatureExtractor().extract(signal, sample_rate=16_000)

    assert features.f0_hz is None
    assert "pitch_unavailable" in features.quality_flags
    assert np.isfinite(features.spectral_flux)


def test_invalid_samples_are_sanitized_and_quality_marked():
    features = FeatureExtractor().extract(np.array([0.0, np.nan, np.inf, -np.inf]), 16_000)

    assert np.isfinite(features.rms)
    assert "invalid_samples" in features.quality_flags
    assert features.f0_hz is None


def test_invalid_sample_rate_is_rejected():
    import pytest

    with pytest.raises(ValueError, match="sample_rate"):
        FeatureExtractor().extract(np.ones(128), sample_rate=0)
