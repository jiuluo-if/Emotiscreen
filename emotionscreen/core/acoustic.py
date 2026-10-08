"""pyAudioAnalysis-inspired short-term features and conservative state estimates.

Selected formulas adapt pyAudioAnalysis ShortTermFeatures.py (Apache-2.0); see
docs/opensource-guidance.md. The package itself is not vendored or cloned.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class AcousticFeatures:
    rms: float
    rms_variation: float
    median_pitch_hz: float | None
    pitch_range_hz: float | None
    voiced_ratio: float
    activity_ratio: float
    spectral_centroid_hz: float
    spectral_flux: float
    zero_crossing_rate: float


@dataclass(frozen=True)
class AcousticAnalysis:
    state: str
    score: float
    quality: str
    features: AcousticFeatures
    note: str


@dataclass(frozen=True)
class AudioStateTransition:
    previous_state: str
    state: str
    analysis: AcousticAnalysis


_EMPTY_FEATURES = AcousticFeatures(0.0, 0.0, None, None, 0.0, 0.0, 0.0, 0.0, 0.0)


class AcousticEmotionAnalyzer:
    """Estimates low/elevated vocal arousal from short-time signal features."""

    # Use a shorter frame than pyAudioAnalysis' file-analysis default for live latency.
    FRAME_SECONDS = 0.04
    MIN_SECONDS = 0.6

    def analyze(self, samples: np.ndarray, sample_rate: int) -> AcousticAnalysis:
        if sample_rate < 8_000 or sample_rate > 192_000:
            raise ValueError("sample_rate must be between 8000 and 192000 Hz")
        audio = np.asarray(samples, dtype=np.float32).reshape(-1)
        if audio.size == 0 or not np.isfinite(audio).all():
            return self._uncertain("音频为空或包含无效数值")
        input_peak = float(np.max(np.abs(audio)))
        if input_peak < 1e-5:
            return self._uncertain("输入电平不足")
        if input_peak >= 0.999:
            return self._uncertain("音频可能削波")

        # Adapt pyAudioAnalysis dc_normalize: remove DC and scale to peak 1.
        # This makes prosodic thresholds insensitive to microphone gain.
        audio = audio - float(np.mean(audio))
        normalized_peak = float(np.max(np.abs(audio)))
        if normalized_peak < 1e-5:
            return self._uncertain("输入电平不足")
        audio = audio / normalized_peak
        frame_size = round(sample_rate * self.FRAME_SECONDS)
        if audio.size < max(frame_size * 8, round(sample_rate * self.MIN_SECONDS)):
            return self._uncertain("音频过短，暂不判断")

        frame_count = audio.size // frame_size
        frames = audio[: frame_count * frame_size].reshape(frame_count, frame_size)
        centered = frames - frames.mean(axis=1, keepdims=True)
        # Adapted from pyAudioAnalysis energy(frame): mean square per short frame.
        frame_energy = np.mean(centered * centered, axis=1)
        rms = np.sqrt(frame_energy)
        mean_rms = float(np.mean(rms))
        active = rms >= max(0.02, mean_rms * 0.20)
        active_rms = rms[active]
        rms_variation = float(np.std(active_rms) / max(float(np.mean(active_rms)), 1e-8)) if active_rms.size else 0.0

        pitches: list[float] = []
        centroids: list[float] = []
        crossings: list[float] = []
        normalized_spectra: list[np.ndarray] = []
        for frame, frame_rms, is_active in zip(centered, rms, active):
            crossings.append(self._zero_crossing_rate(frame))
            spectrum = np.abs(np.fft.rfft(frame * np.hanning(frame_size)))
            frequencies = np.fft.rfftfreq(frame_size, 1.0 / sample_rate)
            spectrum_sum = float(spectrum.sum())
            if spectrum_sum > 1e-9:
                normalized_spectra.append(spectrum / spectrum_sum)
                # Formula follows pyAudioAnalysis spectral_centroid_spread.
                centroids.append(float(np.dot(spectrum, frequencies) / spectrum_sum))
            if is_active:
                pitch = self._pitch(frame, sample_rate)
                if pitch is not None:
                    pitches.append(pitch)

        voiced_ratio = len(pitches) / max(1, int(np.count_nonzero(active)))
        spectral_flux = (
            float(np.mean([np.sum((current - previous) ** 2) for previous, current in zip(normalized_spectra, normalized_spectra[1:])]))
            if len(normalized_spectra) > 1 else 0.0
        )
        features = AcousticFeatures(
            rms=mean_rms,
            rms_variation=rms_variation,
            median_pitch_hz=float(np.median(pitches)) if pitches else None,
            pitch_range_hz=float(np.percentile(pitches, 90) - np.percentile(pitches, 10)) if pitches else None,
            voiced_ratio=float(voiced_ratio),
            activity_ratio=float(np.mean(active)),
            spectral_centroid_hz=float(np.mean(centroids)) if centroids else 0.0,
            spectral_flux=spectral_flux,
            zero_crossing_rate=float(np.mean(crossings)) if crossings else 0.0,
        )

        if mean_rms < 0.03 or features.activity_ratio < 0.15 or voiced_ratio < 0.40:
            return AcousticAnalysis("uncertain", 0.0, "unusable", features, "语音能量或有声帧不足")

        pitch = features.median_pitch_hz
        pitch_range = features.pitch_range_hz
        if pitch is None or pitch_range is None:
            return AcousticAnalysis("uncertain", 0.0, "unusable", features, "未检测到稳定基频")

        if pitch <= 135:
            score = min(0.85, 0.70 + (135 - pitch) / 1_000)
            return AcousticAnalysis("low_arousal", score, "usable", features, "中位基频落在低唤醒范围")
        if pitch >= 170:
            return AcousticAnalysis("elevated", 0.72, "usable", features, "中位基频落在较高唤醒范围")
        return AcousticAnalysis("uncertain", 0.40, "usable", features, "声学特征不足以区分状态")

    @staticmethod
    def _zero_crossing_rate(frame: np.ndarray) -> float:
        # Adapted from pyAudioAnalysis ShortTermFeatures.zero_crossing_rate.
        if frame.size < 2:
            return 0.0
        return float(np.sum(np.abs(np.diff(np.sign(frame)))) / (2.0 * (frame.size - 1)))

    @staticmethod
    def _pitch(frame: np.ndarray, sample_rate: int) -> float | None:
        signal = frame - float(np.mean(frame))
        signal = np.diff(signal, prepend=signal[0])
        energy = float(np.dot(signal, signal))
        if energy <= 1e-8:
            return None
        # Adapted from pyAudioAnalysis ShortTermFeatures.harmonic autocorrelation;
        # this version bounds lag to vocal F0 and rejects low-clarity peaks.
        correlation = np.correlate(signal, signal, mode="full")[len(signal) - 1 :]
        correlation /= max(float(correlation[0]), 1e-8)
        min_lag = max(1, int(sample_rate / 400))
        max_lag = min(len(correlation) - 1, int(sample_rate / 65))
        if max_lag <= min_lag:
            return None
        lag = min_lag + int(np.argmax(correlation[min_lag : max_lag + 1]))
        if correlation[lag] < 0.35:
            return None
        return sample_rate / lag

    @staticmethod
    def _uncertain(note: str) -> AcousticAnalysis:
        return AcousticAnalysis("uncertain", 0.0, "unusable", _EMPTY_FEATURES, note)


class AudioStateTracker:
    """Debounces changing acoustic windows before exposing a stable state."""

    def __init__(self, confirmations: int = 2) -> None:
        if confirmations < 1:
            raise ValueError("confirmations must be positive")
        self.confirmations = confirmations
        self.state = "uncertain"
        self._candidate = "uncertain"
        self._count = 0

    def update(self, analysis: AcousticAnalysis, *, required_confirmations: int | None = None) -> AudioStateTransition | None:
        candidate = analysis.state if analysis.quality == "usable" and analysis.score >= 0.70 else "uncertain"
        if candidate == self.state:
            self._candidate = candidate
            self._count = 0
            return None
        if candidate == self._candidate:
            self._count += 1
        else:
            self._candidate = candidate
            self._count = 1
        required = self.confirmations if required_confirmations is None else required_confirmations
        if required < 1:
            raise ValueError("required_confirmations must be positive")
        if self._count < required:
            return None
        previous = self.state
        self.state = candidate
        self._count = 0
        return AudioStateTransition(previous, candidate, analysis)

    def reset(self) -> None:
        self.state = "uncertain"
        self._candidate = "uncertain"
        self._count = 0
