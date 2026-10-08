"""Small Tkinter UI for the mock/live demo."""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from dataclasses import replace

import numpy as np

from ..config import AppConfig
from ..core.audio import AudioRingBuffer, MockAudioInput, SoundDeviceAudioInput
from ..core.controller import ReactionController
from ..core.decision import ClefDecisionProvider, MockDecisionProvider
from ..core.features import FeatureExtractor
from ..core.models import AcousticFeatures, DecisionResult, EMOTIONS, VisualState
from ..core.runtime import SingleFlightDecider
from ..core.smoothing import EmotionSmoother


class EmotionWindow:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.root = tk.Tk()
        self.root.title("EmotionScreen — voice visualization demo")
        self.root.geometry("820x650")
        self.root.minsize(680, 540)
        self._running = False
        self._closed = False
        self._after_id: str | None = None
        self._last_feature_at = 0.0
        self._last_decision_at = 0.0
        self._features = AcousticFeatures(sample_rate=config.audio.sample_rate)
        self._visual_state = VisualState()
        self._configure_mode(config.mode)
        self._build_widgets()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._schedule()

    def _configure_mode(self, mode: str) -> None:
        if hasattr(self, "audio"):
            try:
                self.audio.stop()
            except Exception:
                pass
        if hasattr(self, "decider"):
            self.decider.close()
        provider_name = "mock" if mode == "mock" else "clef"
        self.config = replace(self.config, mode=mode, decision=replace(self.config.decision, provider=provider_name))
        if mode == "mock":
            self.audio = MockAudioInput(self.config.audio.sample_rate, self.config.audio.frame_ms, self.config.decision.seed)
            provider = MockDecisionProvider(seed=self.config.decision.seed)
        else:
            self.audio = SoundDeviceAudioInput(
                self.config.audio.sample_rate, self.config.audio.frame_ms,
                self.config.audio.device, self.config.audio.channels,
            )
            provider = ClefDecisionProvider(
                self.config.decision.clef_base_url, timeout_seconds=self.config.decision.timeout_seconds,
            )
        self.buffer = AudioRingBuffer(round(self.config.audio.sample_rate * self.config.audio.window_seconds))
        self.extractor = FeatureExtractor()
        self.decider = SingleFlightDecider(provider)
        self.smoother = EmotionSmoother(
            alpha=self.config.emotion.smoothing_alpha,
            min_hold_seconds=self.config.emotion.min_hold_ms / 1000,
            confirm_count=self.config.emotion.confirm_count,
            uncertain_fallback=self.config.emotion.uncertain_fallback,
        )
        self.controller = ReactionController()
        self._last_decision_at = 0.0

    def _build_widgets(self) -> None:
        outer = ttk.Frame(self.root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="EmotionScreen", font=("Segoe UI", 22, "bold")).pack(anchor="w")
        ttk.Label(
            outer,
            text="Experimental voice expression estimate · predictions are not psychological diagnoses",
            foreground="#5b6573",
        ).pack(anchor="w", pady=(2, 14))

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 12))
        self.start_button = ttk.Button(controls, text="Start listening", command=self.start)
        self.start_button.pack(side="left")
        ttk.Button(controls, text="Pause / resume", command=self.pause_resume).pack(side="left", padx=6)
        ttk.Button(controls, text="Stop", command=self.stop).pack(side="left")
        ttk.Button(controls, text="Switch Mock / Live", command=self.switch_mode).pack(side="right")

        status_frame = ttk.LabelFrame(outer, text="Runtime status", padding=10)
        status_frame.pack(fill="x")
        self.mode_var = tk.StringVar()
        self.audio_var = tk.StringVar(value="Stopped")
        self.api_var = tk.StringVar(value="Not connected (Mock mode)")
        ttk.Label(status_frame, textvariable=self.mode_var, width=32).grid(row=0, column=0, sticky="w", padx=4, pady=3)
        ttk.Label(status_frame, textvariable=self.audio_var).grid(row=0, column=1, sticky="w", padx=4, pady=3)
        ttk.Label(status_frame, textvariable=self.api_var).grid(row=1, column=0, columnspan=2, sticky="w", padx=4, pady=3)

        visual_frame = ttk.LabelFrame(outer, text="Live visual response", padding=10)
        visual_frame.pack(fill="both", expand=True, pady=12)
        self.canvas = tk.Canvas(visual_frame, height=210, background="#19212d", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.glow_circle = self.canvas.create_oval(0, 0, 0, 0, fill="#62b6a7", outline="")
        self.emotion_text = self.canvas.create_text(0, 0, text="uncertain", fill="white", font=("Segoe UI", 20, "bold"))
        self.energy_bar = self.canvas.create_rectangle(0, 0, 0, 0, fill="#62b6a7", outline="")
        self.canvas.bind("<Configure>", self._layout_canvas)

        details = ttk.LabelFrame(outer, text="Features and decision", padding=10)
        details.pack(fill="x")
        self.features_var = tk.StringVar(value="Waiting for audio")
        self.decision_var = tk.StringVar(value="No decision yet")
        self.error_var = tk.StringVar(value="")
        ttk.Label(details, textvariable=self.features_var).pack(anchor="w")
        ttk.Label(details, textvariable=self.decision_var, wraplength=760).pack(anchor="w", pady=(5, 0))
        ttk.Label(details, textvariable=self.error_var, foreground="#b42318", wraplength=760).pack(anchor="w", pady=(5, 0))

        manual = ttk.Frame(outer)
        manual.pack(fill="x", pady=(10, 0))
        ttk.Label(manual, text="Mock emotion:").pack(side="left")
        self.manual_emotion = tk.StringVar(value="calm")
        ttk.Combobox(manual, textvariable=self.manual_emotion, values=[e for e in EMOTIONS if e != "uncertain"], width=14, state="readonly").pack(side="left", padx=6)
        ttk.Button(manual, text="Apply simulated result", command=self.apply_manual_emotion).pack(side="left")
        self._refresh_mode_labels()

    def _refresh_mode_labels(self) -> None:
        source = "Mock (simulated; no microphone/API)" if self.config.mode == "mock" else "Live (microphone enabled by user)"
        self.mode_var.set(f"Mode: {source}")
        self.api_var.set("Clef provider configured; connection checked on first decision" if self.config.mode == "live" else "Clef API: not used")

    def _layout_canvas(self, event) -> None:
        center_x, center_y = event.width // 2, event.height // 2 - 10
        self.canvas.coords(self.emotion_text, center_x, center_y)
        self.canvas.coords(self.energy_bar, 18, event.height - 22, 18, event.height - 12)

    def _schedule(self) -> None:
        if not self._closed:
            self._after_id = self.root.after(round(1000 / self.config.visual.fps), self._tick)

    def _tick(self) -> None:
        if self._closed:
            return
        if self._running:
            try:
                frame = self.audio.read_frame(timeout=0.002) if self.config.mode == "live" else self.audio.read_frame()
                self.buffer.append(frame)
                # Fast path: direct frame energy drives the bar without waiting for Clef.
                frame_rms = float(np.sqrt(np.mean(np.asarray(frame, dtype=float) ** 2)))
                self._draw_energy(frame_rms)
                now = time.monotonic()
                if now - self._last_feature_at >= 0.25 and len(self.buffer.snapshot()) >= int(self.config.audio.sample_rate * 0.25):
                    self._features = self.extractor.extract(self.buffer.snapshot(), self.config.audio.sample_rate)
                    self._last_feature_at = now
                    self.features_var.set(
                        f"RMS {self._features.rms:.3f} · F0 {self._format_optional(self._features.f0_hz)} · "
                        f"voiced {self._features.voiced_ratio:.0%} · pause {self._features.pause_ratio:.0%} · "
                        f"centroid {self._features.spectral_centroid_hz:.0f} Hz · quality {self._features.quality}"
                    )
                    if now - self._last_decision_at >= self.config.decision.interval_ms / 1000:
                        self.decider.submit(self._features)
                        self._last_decision_at = now
            except TimeoutError:
                pass
            except Exception as exc:
                self._running = False
                self.error_var.set(f"Audio input: {exc}")
                self.audio_var.set("Audio input stopped")
                try:
                    self.audio.stop()
                except Exception:
                    pass
            for result in self.decider.poll():
                smoothed = self.smoother.update(result)
                self._visual_state = self.controller.create(smoothed, self._features)
                self.canvas.itemconfigure(self.emotion_text, text=smoothed.emotion)
                self.decision_var.set(self._format_decision(smoothed))
                self.error_var.set("")
            if self.decider.last_error:
                self.error_var.set(self.decider.last_error)
            self._draw_visual()
        self._schedule()

    @staticmethod
    def _format_optional(value: float | None) -> str:
        return "unavailable" if value is None else f"{value:.1f} Hz"

    @staticmethod
    def _format_decision(result: DecisionResult) -> str:
        top = sorted(result.probabilities.items(), key=lambda item: item[1], reverse=True)[:4]
        probability_text = ", ".join(f"{name} {value:.0%}" for name, value in top)
        confidence = "unknown" if result.confidence is None else f"{result.confidence:.0%}"
        return f"{result.source.upper()} · {probability_text} · confidence {confidence} · {result.latency_ms:.1f} ms"

    def _draw_energy(self, value: float) -> None:
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        end = 18 + max(0.0, min(1.0, value * 3)) * max(0, width - 36)
        self.canvas.coords(self.energy_bar, 18, height - 22, end, height - 12)
        self.canvas.itemconfigure(self.energy_bar, fill=self._visual_state.theme_color)

    def _draw_visual(self) -> None:
        if self.config.visual.animation_enabled:
            phase = (time.monotonic() * self._visual_state.animation_speed) % (2 * np.pi)
            width, height = self.canvas.winfo_width(), self.canvas.winfo_height()
            radius = 48 + 14 * self._visual_state.motion_amplitude * (0.5 + 0.5 * np.sin(phase))
            center_x, center_y = width // 2, height // 2 - 10
            self.canvas.coords(self.glow_circle, center_x - radius, center_y - radius, center_x + radius, center_y + radius)
            self.canvas.itemconfigure(self.glow_circle, fill=self._visual_state.theme_color)

    def start(self) -> None:
        try:
            self.audio.start()
            self._running = True
            self.audio_var.set("Listening — click Pause / Stop at any time" if self.config.mode == "live" else "Mock audio running")
            self.error_var.set("")
        except Exception as exc:
            self._running = False
            self.audio_var.set("Start failed")
            self.error_var.set(str(exc))

    def pause_resume(self) -> None:
        if self._running:
            self.stop()
            self.audio_var.set("Paused")
        else:
            self.start()

    def stop(self) -> None:
        self._running = False
        try:
            self.audio.stop()
            self.audio_var.set("Stopped")
        except Exception as exc:
            self.audio_var.set("Audio cleanup error")
            self.error_var.set(str(exc))

    def switch_mode(self) -> None:
        self.stop()
        self._configure_mode("live" if self.config.mode == "mock" else "mock")
        self._refresh_mode_labels()
        self.audio_var.set("Stopped")

    def apply_manual_emotion(self) -> None:
        if self.config.mode != "mock":
            messagebox.showinfo("Mock control", "Switch to Mock mode to apply a simulated emotion.", parent=self.root)
            return
        selected = self.manual_emotion.get()
        result = DecisionResult(selected, {selected: 1.0}, 1.0, "mock", note="Manually selected simulation")
        self._visual_state = self.controller.create(result, self._features)
        self.canvas.itemconfigure(self.emotion_text, text=result.emotion)
        self.decision_var.set(self._format_decision(result))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self._running = False
        try:
            self.audio.stop()
        except Exception:
            pass
        finally:
            try:
                self.decider.close()
            finally:
                if self._after_id is not None:
                    self.root.after_cancel(self._after_id)
                self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
