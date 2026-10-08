"""Explicit-start audio sources. Audio callback code only copies into a bounded queue."""

from __future__ import annotations

from collections import deque
import math
import queue
import threading

import numpy as np


class MockAudioInput:
    def __init__(self, sample_rate: int = 16_000, frame_ms: int = 32, seed: int = 42) -> None:
        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_size = round(sample_rate * frame_ms / 1000)
        self._rng = np.random.default_rng(seed)
        self._sample_cursor = 0
        self.is_running = False

    def start(self) -> None:
        self.is_running = True

    def read_frame(self) -> np.ndarray:
        if not self.is_running:
            raise RuntimeError("audio input must be started before reading")
        positions = np.arange(self.frame_size) + self._sample_cursor
        seconds = positions / self.sample_rate
        envelope = 0.12 + 0.07 * (1 + math.sin(seconds[0] * 0.8))
        tone = np.sin(2 * np.pi * (180 + 60 * math.sin(seconds[0] * 0.3)) * seconds)
        self._sample_cursor += self.frame_size
        return (envelope * tone + self._rng.normal(0, 0.005, self.frame_size)).astype(np.float32)

    def stop(self) -> None:
        self.is_running = False


class SoundDeviceAudioInput:
    """Optional microphone source. Install sounddevice only on the target device."""

    def __init__(self, sample_rate: int, frame_ms: int, device: int | str | None = None, channels: int = 1) -> None:
        self.sample_rate, self.frame_ms, self.device, self.channels = sample_rate, frame_ms, device, channels
        self._frames: queue.Queue[np.ndarray] = queue.Queue(maxsize=4)
        self._stream = None
        self.is_running = False
        self.dropped_frames = 0
        self.last_audio_status = ""

    def start(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("Live audio needs the optional 'sounddevice' package") from exc

        def on_audio(indata, frames, time_info, status):
            if status:
                self.last_audio_status = str(status)
            copied = np.asarray(indata, dtype=np.float32).mean(axis=1)
            try:
                self._frames.put_nowait(copied)
            except queue.Full:
                try:
                    self._frames.get_nowait()
                except queue.Empty:
                    pass
                self.dropped_frames += 1
                self._frames.put_nowait(copied)

        blocksize = round(self.sample_rate * self.frame_ms / 1000)
        self._stream = sd.InputStream(samplerate=self.sample_rate, channels=self.channels, blocksize=blocksize, device=self.device, callback=on_audio)
        self._stream.start()
        self.is_running = True

    def read_frame(self, timeout: float = 0.1) -> np.ndarray:
        if not self.is_running:
            raise RuntimeError("audio input is not running")
        try:
            return self._frames.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError("no microphone frame arrived") from exc

    def stop(self) -> None:
        stream, self._stream = self._stream, None
        self.is_running = False
        try:
            if stream is not None:
                stream.stop()
        finally:
            try:
                if stream is not None:
                    stream.close()
            finally:
                while True:
                    try:
                        self._frames.get_nowait()
                    except queue.Empty:
                        break


class AudioRingBuffer:
    def __init__(self, capacity_samples: int) -> None:
        if capacity_samples < 1:
            raise ValueError("capacity_samples must be positive")
        self.capacity_samples = capacity_samples
        self._samples: deque[np.ndarray] = deque()
        self._size = 0
        self._lock = threading.Lock()

    def append(self, frame: np.ndarray) -> None:
        data = np.asarray(frame, dtype=np.float32).reshape(-1).copy()
        if len(data) > self.capacity_samples:
            data = data[-self.capacity_samples :]
        with self._lock:
            self._samples.append(data)
            self._size += len(data)
            while self._samples and self._size > self.capacity_samples:
                removed = self._samples.popleft()
                self._size -= len(removed)

    def snapshot(self) -> np.ndarray:
        with self._lock:
            return np.concatenate(tuple(self._samples)) if self._samples else np.empty(0, dtype=np.float32)
