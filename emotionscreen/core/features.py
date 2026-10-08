"""Lightweight, model-free acoustic feature extraction using NumPy."""

from __future__ import annotations

import numpy as np

from .models import AcousticFeatures


class FeatureExtractor:
    def __init__(self, *, silence_rms: float = 0.008, frame_ms: int = 25, hop_ms: int = 10) -> None:
        self.silence_rms = silence_rms
        self.frame_ms = frame_ms
        self.hop_ms = hop_ms

    def extract(self, samples: np.ndarray, sample_rate: int) -> AcousticFeatures:
        if not isinstance(sample_rate, int) or sample_rate < 1:
            raise ValueError("sample_rate must be a positive integer")
        signal = np.asarray(samples, dtype=np.float64).reshape(-1)
        if signal.size == 0:
            raise ValueError("samples must not be empty")
        invalid = ~np.isfinite(signal)
        flags: list[str] = []
        if invalid.any():
            signal = np.nan_to_num(signal, nan=0.0, posinf=0.0, neginf=0.0)
            flags.append("invalid_samples")
        signal = np.clip(signal, -1.0, 1.0)
        rms = float(np.sqrt(np.mean(np.square(signal))))
        peak = float(np.max(np.abs(signal)))
        if peak >= 0.999:
            flags.append("clipping")

        frame_size = max(16, round(sample_rate * self.frame_ms / 1000))
        hop = max(1, round(sample_rate * self.hop_ms / 1000))
        frames = [signal[start : start + frame_size] for start in range(0, max(1, len(signal) - frame_size + 1), hop)]
        frames = [frame for frame in frames if len(frame) == frame_size]
        if not frames and len(signal) >= 16:
            frames = [signal[: min(len(signal), frame_size)]]
        frame_rms = np.asarray([np.sqrt(np.mean(frame * frame)) for frame in frames], dtype=float)
        active = frame_rms >= self.silence_rms
        voiced_ratio = float(np.mean(active)) if active.size else 0.0
        pause_ratio = 1.0 - voiced_ratio

        pitches: list[float] = []
        voiced_frames = 0
        min_lag = max(2, int(sample_rate / 500))
        max_lag = max(min_lag + 1, int(sample_rate / 70))
        for frame, is_active in zip(frames, active):
            if not is_active or len(frame) < min_lag + 2:
                continue
            centered = frame - np.mean(frame)
            fft_size = 1 << (2 * len(centered) - 1).bit_length()
            transformed = np.fft.rfft(centered, n=fft_size)
            corr = np.fft.irfft(transformed * transformed.conjugate(), n=fft_size)[: len(centered)]
            upper = min(max_lag, len(corr) - 1)
            if upper <= min_lag:
                continue
            lag = min_lag + int(np.argmax(corr[min_lag : upper + 1]))
            clarity = float(corr[lag] / max(corr[0], 1e-12))
            if clarity >= 0.35:
                pitches.append(sample_rate / lag)
                voiced_frames += 1
        f0 = float(np.median(pitches)) if pitches else None
        pitch_range = float(np.percentile(pitches, 90) - np.percentile(pitches, 10)) if len(pitches) > 1 else (0.0 if pitches else None)
        f0_ratio = voiced_frames / max(1, len(frames))

        window = np.hanning(len(signal))
        spectrum = np.abs(np.fft.rfft(signal * window))
        frequencies = np.fft.rfftfreq(len(signal), 1 / sample_rate)
        spectrum_sum = float(spectrum.sum())
        centroid = float(np.dot(frequencies, spectrum) / spectrum_sum) if spectrum_sum > 1e-12 else 0.0
        frame_spectra = []
        for frame in frames:
            frame_spectra.append(np.abs(np.fft.rfft(frame * np.hanning(len(frame)))))
        flux = 0.0
        if len(frame_spectra) > 1:
            normalized = [item / max(float(np.linalg.norm(item)), 1e-12) for item in frame_spectra]
            flux = float(np.mean([np.linalg.norm(np.maximum(current - previous, 0.0)) for previous, current in zip(normalized, normalized[1:])]))
        zcr = float(np.mean(np.abs(np.diff(np.signbit(signal))))) if len(signal) > 1 else 0.0
        midpoint = max(1, len(signal) // 2)
        first_rms = float(np.sqrt(np.mean(signal[:midpoint] ** 2)))
        second_rms = float(np.sqrt(np.mean(signal[midpoint:] ** 2))) if midpoint < len(signal) else first_rms
        energy_change = second_rms - first_rms
        rhythm = float(np.count_nonzero(np.diff(active.astype(int)) == 1) / max(len(signal) / sample_rate, 1e-9))

        if rms < self.silence_rms:
            flags.append("low_signal")
        if f0 is None:
            flags.append("pitch_unavailable")
        if len(signal) < frame_size:
            flags.append("short_window")
        quality = "poor" if invalid.any() or rms < self.silence_rms else ("limited" if flags else "good")
        return AcousticFeatures(
            sample_rate=sample_rate, rms=rms, peak=peak, energy_change=energy_change,
            f0_hz=f0, f0_voiced_ratio=f0_ratio, pitch_range_hz=pitch_range,
            voiced_ratio=voiced_ratio, pause_ratio=pause_ratio, rhythm_rate_hz=rhythm,
            spectral_centroid_hz=centroid, spectral_flux=flux, zero_crossing_rate=zcr,
            quality=quality, quality_flags=tuple(dict.fromkeys(flags)),
        )
