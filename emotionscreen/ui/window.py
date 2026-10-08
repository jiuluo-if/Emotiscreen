"""主控制窗口：简洁控制 + 可选开发面板。"""

from __future__ import annotations

from dataclasses import replace
import tkinter as tk
from tkinter import ttk
from pathlib import Path
import time

import numpy as np

from ..config import AppConfig
from ..core.acoustic import AudioStateTracker
from ..core.audio import AudioRingBuffer, SoundDeviceAudioInput, load_pcm_wav
from ..core.audio_policy import AudioFeedbackPolicy
from ..core.audio_runtime import AudioAnalysisWorker
from ..core.context import ConversationContext
from ..core.decision import ClefDecisionProvider, MockDecisionProvider
from ..core.i18n import text
from ..core.models import DecisionResult, ResponseEvent, TranscriptSegment
from ..core.policy import ResponsePolicy
from ..core.runtime import ConversationRuntime
from ..core.transcript import MockTranscriptProvider
from .comfort_window import ComfortWindow
from .glass import emotion_palette, interpolate_color, should_reduce_motion


_SCENARIOS = (
    "user_achievement", "user_praise", "user_sadness", "small_progress", "ordinary_chat",
    "sarcasm", "other_person", "incomplete", "uncertain",
)
_AUDIO_STATE_LABEL = {
    "low_arousal": "audio_state_low",
    "elevated": "audio_state_elevated",
    "uncertain": "audio_state_uncertain",
}


class EmotionWindow:
    def __init__(self, config: AppConfig, *, audio_file: Path | None = None) -> None:
        self.config = config
        self.root = tk.Tk()
        screen_height = self.root.winfo_screenheight()
        window_height = max(620, min(820, screen_height - 90))
        self.root.geometry(f"820x{window_height}")
        self.root.minsize(660, min(680, window_height))
        self._closed = False
        self._after_id: str | None = None
        self._listening = False
        self._paused = False
        self._dnd = False
        self._developer_mode = False
        self._provider_name = "mock" if config.mode == "live" else config.decision.provider
        self._language = config.ui.language
        self._theme = "light" if config.ui.theme == "system" else config.ui.theme
        self._static = config.ui.reduced_motion or should_reduce_motion()
        self._motion_strength = config.ui.motion_strength
        self._preview_action = "support"
        self._preview_state = "uncertain"
        self._audio_state = "uncertain"
        self._audio_overlay_dismissed = False
        self._audio: SoundDeviceAudioInput | None = None
        self._audio_buffer: AudioRingBuffer | None = None
        self._audio_worker: AudioAnalysisWorker | None = None
        self._audio_states = AudioStateTracker(confirmations=2)
        self._last_audio_submit = 0.0
        self._audio_file_preview = False
        self._transcripts = MockTranscriptProvider()
        self._context = ConversationContext(max_units=config.context.max_units)
        self._policy = ResponsePolicy(
            cooldown_seconds={
                "celebrate": config.response.celebrate_cooldown_seconds,
                "support": config.response.support_cooldown_seconds,
                "acknowledge": config.response.acknowledge_cooldown_seconds,
            },
            dedupe_seconds=config.response.dedupe_seconds,
            duration_seconds=config.response.duration_seconds,
        )
        self._audio_policy = AudioFeedbackPolicy()
        self.runtime = self._new_runtime(self._provider_name)
        self._build_ui()
        # Map the main window first so the initially withdrawn toast cannot become the first active top-level.
        self.root.update_idletasks()
        self.root.update()
        self.comfort = ComfortWindow(
            self.root,
            language=self._language,
            reduced_motion=self._static,
            motion_strength=self._motion_strength,
            theme=self._theme,
            on_dismiss=self._on_comfort_dismiss,
        )
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self._apply_theme()
        self._refresh_text()
        self._schedule_tick()
        if audio_file is not None:
            self.root.after(250, lambda: self.analyze_audio_file(audio_file))

    def _new_runtime(self, provider_name: str) -> ConversationRuntime:
        provider = (
            ClefDecisionProvider(self.config.decision.clef_base_url, timeout_seconds=self.config.decision.timeout_seconds)
            if provider_name == "clef"
            else MockDecisionProvider()
        )
        return ConversationRuntime(provider, context=self._context, policy=self._policy)

    def _build_ui(self) -> None:
        self.style = ttk.Style(self.root)
        try:
            self.style.theme_use("clam")
        except tk.TclError:
            pass
        self.style.configure("Title.TLabel", font=("Microsoft YaHei UI", 24, "bold"))
        self.style.configure("Tagline.TLabel", foreground="#687486")
        self.style.configure("Eyebrow.TLabel", font=("Segoe UI", 8, "bold"), foreground="#74839A")
        self.style.configure("Primary.TButton", font=("Microsoft YaHei UI", 10, "bold"), padding=(18, 11), borderwidth=0)
        self.style.configure("Soft.TButton", font=("Microsoft YaHei UI", 10), padding=(14, 10), borderwidth=0)
        self.style.configure("Stage.TFrame", padding=14, borderwidth=0)
        self.widgets: dict[str, tk.Widget] = {}
        outer = ttk.Frame(self.root, padding=(30, 26, 30, 22))
        outer.pack(fill="both", expand=True)
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 18))
        self.brand_mark = tk.Canvas(header, width=48, height=48, highlightthickness=0, bd=0)
        self.brand_mark.pack(side="left", padx=(0, 13))
        self.brand_mark.create_oval(3, 3, 45, 45, fill="#667FA0", outline="")
        self.brand_mark.create_text(24, 23, text="e", fill="#FFFFFF", font=("Georgia", 25, "bold"))
        title_area = ttk.Frame(header)
        title_area.pack(side="left", fill="x", expand=True)
        self.widgets["title"] = ttk.Label(title_area, style="Title.TLabel")
        self.widgets["title"].pack(anchor="w")
        self.widgets["tagline"] = ttk.Label(title_area, style="Tagline.TLabel")
        self.widgets["tagline"].pack(anchor="w", pady=(0, 1))
        self.header_status_var = tk.StringVar()
        ttk.Label(header, textvariable=self.header_status_var, style="Eyebrow.TLabel").pack(side="right", anchor="n", pady=7)

        status = ttk.Frame(outer)
        status.pack(fill="x", pady=(0, 12))
        self.status_dot = tk.Canvas(status, width=18, height=18, highlightthickness=0, bd=0)
        self.status_dot.pack(side="left", padx=(0, 8))
        self.status_dot.create_oval(4, 4, 14, 14, fill="#A6AFBC", outline="", tags="dot")
        self.status_var = tk.StringVar()
        ttk.Label(status, textvariable=self.status_var).pack(side="left", fill="x", expand=True)
        self.provider_status_var = tk.StringVar()
        ttk.Label(status, textvariable=self.provider_status_var, foreground="#718096").pack(side="right")

        controls = ttk.Frame(outer)
        controls.pack(fill="x", pady=(0, 18))
        self.start_button = ttk.Button(controls, command=self.start_listening, style="Primary.TButton")
        self.start_button.pack(side="left")
        self.pause_button = ttk.Button(controls, command=self.toggle_pause, style="Soft.TButton")
        self.pause_button.pack(side="left", padx=(9, 0))
        self.stop_button = ttk.Button(controls, command=self.stop_listening, style="Soft.TButton")
        self.stop_button.pack(side="left")
        self.dnd_var = tk.BooleanVar(value=False)
        self.dnd_button = ttk.Checkbutton(controls, variable=self.dnd_var, command=self.toggle_dnd, style="Soft.TButton")
        self.dnd_button.pack(side="right")

        preview = ttk.Frame(outer, style="Stage.TFrame")
        preview.pack(fill="x", expand=False)
        stage_height = min(270, max(205, self.root.winfo_screenheight() - 570))
        self.preview_canvas = tk.Canvas(preview, height=stage_height, highlightthickness=0, bd=0)
        self.preview_canvas.pack(fill="x", expand=False)
        self.preview_canvas.bind("<Configure>", self._draw_preview)
        self.preview_button = ttk.Button(preview, command=self.preview_response, style="Soft.TButton")
        self.preview_button.pack(anchor="e", pady=(10, 0))

        settings = ttk.Frame(outer)
        settings.pack(fill="x", pady=(16, 0))
        self.lang_label = ttk.Label(settings)
        self.lang_label.grid(row=0, column=0, sticky="w")
        self.language_var = tk.StringVar(value=self._language)
        self.language_box = ttk.Combobox(settings, textvariable=self.language_var, values=("zh-CN", "en"), state="readonly", width=10)
        self.language_box.grid(row=0, column=1, padx=(8, 20), sticky="w")
        self.language_box.bind("<<ComboboxSelected>>", self._change_language)
        self.theme_label = ttk.Label(settings)
        self.theme_label.grid(row=0, column=2, sticky="w")
        self.theme_var = tk.StringVar(value=self._theme)
        self.theme_box = ttk.Combobox(settings, textvariable=self.theme_var, values=("light", "dark"), state="readonly", width=9)
        self.theme_box.grid(row=0, column=3, padx=8, sticky="w")
        self.theme_box.bind("<<ComboboxSelected>>", self._change_theme)
        self.static_var = tk.BooleanVar(value=self._static)
        self.static_button = ttk.Checkbutton(settings, variable=self.static_var, command=self.toggle_static)
        self.static_button.grid(row=1, column=0, columnspan=2, sticky="w", pady=(10, 0))
        self.motion_label = ttk.Label(settings)
        self.motion_label.grid(row=1, column=2, sticky="w", pady=(10, 0))
        self.motion_scale = ttk.Scale(settings, from_=0.0, to=1.0, command=self._change_strength)
        self.motion_scale.set(self._motion_strength)
        self.motion_scale.grid(row=1, column=3, sticky="ew", pady=(10, 0))
        settings.columnconfigure(3, weight=1)

        self.developer_var = tk.BooleanVar(value=False)
        self.developer_toggle = ttk.Checkbutton(outer, variable=self.developer_var, command=self.toggle_developer)
        self.developer_toggle.pack(anchor="w", pady=(12, 0))
        self.developer_panel = ttk.LabelFrame(outer, padding=12)
        self.scenario_var = tk.StringVar(value="user_achievement")
        self.scenario_box = ttk.Combobox(self.developer_panel, textvariable=self.scenario_var, values=_SCENARIOS, state="readonly", width=25)
        self.scenario_box.grid(row=0, column=1, sticky="ew", padx=8)
        self.scenario_label = ttk.Label(self.developer_panel)
        self.scenario_label.grid(row=0, column=0, sticky="w")
        self.simulate_button = ttk.Button(self.developer_panel, command=self.simulate_scenario)
        self.simulate_button.grid(row=0, column=2, padx=4)
        self.text_label = ttk.Label(self.developer_panel)
        self.text_label.grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.transcript_var = tk.StringVar()
        self.transcript_entry = ttk.Entry(self.developer_panel, textvariable=self.transcript_var)
        self.transcript_entry.grid(row=1, column=1, sticky="ew", padx=8, pady=(10, 0))
        self.submit_button = ttk.Button(self.developer_panel, command=self.submit_text)
        self.submit_button.grid(row=1, column=2, padx=4, pady=(10, 0))
        self.provider_label = ttk.Label(self.developer_panel)
        self.provider_label.grid(row=2, column=0, sticky="w", pady=(10, 0))
        self.provider_var = tk.StringVar(value=self._provider_name)
        self.provider_box = ttk.Combobox(self.developer_panel, textvariable=self.provider_var, values=("mock", "clef"), state="readonly", width=12)
        self.provider_box.grid(row=2, column=1, sticky="w", padx=8, pady=(10, 0))
        self.provider_box.bind("<<ComboboxSelected>>", self._change_provider)
        self.decision_label = ttk.Label(self.developer_panel)
        self.decision_label.grid(row=3, column=0, sticky="nw", pady=(10, 0))
        self.decision_var = tk.StringVar(value="—")
        ttk.Label(self.developer_panel, textvariable=self.decision_var, wraplength=540).grid(row=3, column=1, columnspan=2, sticky="w", padx=8, pady=(10, 0))
        self.api_var = tk.StringVar(value="")
        ttk.Label(self.developer_panel, textvariable=self.api_var, foreground="#A14B42", wraplength=580).grid(row=4, column=0, columnspan=3, sticky="w", pady=(8, 0))
        self.material_var = tk.StringVar(value="")
        ttk.Label(self.developer_panel, textvariable=self.material_var, wraplength=580).grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self.developer_panel.columnconfigure(1, weight=1)

    def _selected_scenario(self) -> str:
        selected = self.scenario_box.get()
        for scenario in _SCENARIOS:
            if selected in {scenario, text(scenario, self._language)}:
                return scenario
        return "user_achievement"

    @staticmethod
    def _state_for_action(action: str) -> str:
        return {"support": "low_arousal", "acknowledge": "elevated", "celebrate": "elevated"}.get(action, "uncertain")

    def _refresh_context_status(self, *, rule_score: float | None = None) -> None:
        if not hasattr(self, "provider_status_var"):
            return
        count = f"{self._context.used_units}/{self._context.max_units}"
        if self.config.mode == "live":
            label_key = _AUDIO_STATE_LABEL.get(self._audio_state, "audio_state_uncertain")
            label = text(label_key, self._language)
            if rule_score is not None:
                label += f" · {text('rule_score', self._language)} {rule_score:.0%}"
        else:
            label = text("mock_mode" if self._provider_name == "mock" else "clef_mode", self._language)
        self.provider_status_var.set(f"{label} · {count}")

    def _ensure_live_audio_overlay(self) -> None:
        if (
            self.config.mode != "live"
            or not self._listening
            or self._paused
            or self._dnd
            or self._audio_overlay_dismissed
        ):
            return
        if not self.comfort.visible or not self.comfort.persistent:
            self.comfort.show_audio_state(self._audio_state, self._language)

    def _schedule_tick(self) -> None:
        if not self._closed:
            self._after_id = self.root.after(33, self._tick)

    def _tick(self) -> None:
        if self._closed:
            return
        if self._listening and not self._paused and self._audio is not None and self._audio_buffer is not None:
            try:
                self._audio_buffer.append(self._audio.read_frame(timeout=0.002))
                self._maybe_submit_audio()
            except TimeoutError:
                pass
            except Exception as exc:
                self.api_var.set(str(exc))
                self.stop_listening()
        if self._audio_worker is not None:
            for result in self._audio_worker.poll():
                analysis = result.analysis
                audio_is_active = (self._listening and not self._paused) or self._audio_file_preview
                transition = (
                    self._audio_states.update(
                        analysis,
                        required_confirmations=1 if self._audio_file_preview else None,
                    )
                    if audio_is_active else None
                )
                self.decision_var.set(
                    f"稳定状态 {self._audio_states.state} · 当前窗 {analysis.state} · "
                    f"quality {analysis.quality} · 规则分 {analysis.score:.0%} · {analysis.note}"
                )
                self._audio_state = self._audio_states.state
                self._refresh_context_status(rule_score=analysis.score)
                if transition is not None:
                    state_summary = TranscriptSegment(
                        text=text(
                            _AUDIO_STATE_LABEL.get(transition.state, "audio_state_uncertain"),
                            self._language,
                        ),
                        language=self._language,
                        speaker="user",
                        source="acoustic",
                    )
                    self._context.append(state_summary)
                    self._audio_state = transition.state
                    event = self._audio_policy.evaluate(
                        transition,
                        language=self._language,
                        listening=self._listening or self._audio_file_preview,
                        dnd=self._dnd,
                        paused=self._paused,
                    )
                    if event is not None:
                        self._preview_action = event.action
                        self._audio_state = event.state or self._audio_state
                        self._preview_state = self._audio_state
                        if self._audio_file_preview:
                            event = replace(event, persistent=False, duration_seconds=4.0)
                        self._draw_preview()
                        if not self._audio_overlay_dismissed or self._audio_file_preview:
                            self.comfort.show(event)
                            self._context.append(
                                TranscriptSegment(
                                    text=event.phrase,
                                    language=self._language,
                                    speaker="assistant",
                                    source="assistant",
                                )
                            )
                    self._refresh_context_status(rule_score=analysis.score)
                self._audio_file_preview = False
            if self._audio_worker.last_error:
                self.provider_status_var.set("分析失败")
                self.api_var.set(f"声学分析失败：{self._audio_worker.last_error}")
                self._audio_file_preview = False
        for event in self.runtime.poll(
            language=self._language,
            dnd=self._dnd,
            paused=self._paused,
            popup_active=self.comfort.visible and not self.comfort.persistent,
            listening=self._listening,
        ):
            self._preview_action = event.action
            self._audio_state = self._state_for_action(event.action)
            self._preview_state = self._audio_state
            if self._listening and self.config.mode == "live":
                event = replace(event, persistent=True, state=self._audio_state)
            self._draw_preview()
            self.comfort.show(event)
            self._context.append(
                TranscriptSegment(
                    text=event.phrase,
                    language=self._language,
                    speaker="assistant",
                    source="assistant",
                )
            )
            self._refresh_context_status()
        decision = self.runtime.last_decision
        if self._developer_mode and decision is not None:
            confidence = decision.confidence.get("response") if decision.confidence else None
            confidence_text = "—" if confidence is None else f"{confidence:.0%}"
            self.decision_var.set(
                f"{decision.source} · {decision.relevance} · {decision.event_status} · {decision.attitude} · {decision.event_relation} · "
                f"{decision.response}/{decision.intensity}/{decision.timing} · confidence {confidence_text} · {decision.latency_ms:.0f} ms"
            )
        if self.runtime.last_error:
            error = self.runtime.last_error
            status = f"{text('api_offline', self._language)} {error}"
            if self._provider_name == "clef":
                self.provider_var.set("mock")
                self._change_provider()
            self.api_var.set(status)
        self._ensure_live_audio_overlay()
        self._schedule_tick()

    def _maybe_submit_audio(self) -> None:
        if self._audio_worker is None or self._audio_buffer is None:
            return
        now = time.monotonic()
        interval = self.config.audio.window_seconds
        if now - self._last_audio_submit < interval:
            return
        samples = self._audio_buffer.snapshot()
        if len(samples) < self.config.audio.sample_rate * interval:
            return
        self._last_audio_submit = now
        self._audio_worker.submit(samples, self.config.audio.sample_rate)

    def analyze_audio_file(self, path: str | Path) -> None:
        try:
            samples, sample_rate = load_pcm_wav(path)
            if self._audio_worker is not None:
                self._audio_worker.close()
            self._audio_worker = AudioAnalysisWorker()
            self._audio_file_preview = True
            self._audio_states.reset()
            self.provider_status_var.set("WAV · 分析中")
            self._audio_worker.submit(samples, sample_rate)
        except Exception as exc:
            self._audio_file_preview = False
            self.provider_status_var.set("WAV · 失败")
            self.api_var.set(f"WAV 分析失败：{exc}")

    def start_listening(self) -> None:
        if self._listening:
            return
        if self.config.mode == "live":
            try:
                if self._audio_worker is not None:
                    self._audio_worker.close()
                self._audio = SoundDeviceAudioInput(
                    self.config.audio.sample_rate, self.config.audio.frame_ms,
                    self.config.audio.device, self.config.audio.channels,
                )
                self._audio_buffer = AudioRingBuffer(round(self.config.audio.sample_rate * self.config.audio.window_seconds))
                self._audio_worker = AudioAnalysisWorker()
                self._audio.start()
                self._audio_states.reset()
            except Exception as exc:
                self.api_var.set(f"麦克风/声学分析启动失败：{exc}")
                if self._audio_worker is not None:
                    self._audio_worker.close()
                    self._audio_worker = None
                if self._audio is not None:
                    try:
                        self._audio.stop()
                    except Exception:
                        pass
                return
        self._listening = True
        self._paused = False
        if self.config.mode == "live":
            self._audio_state = "uncertain"
            self._preview_state = "uncertain"
            self._audio_overlay_dismissed = False
            self.comfort.show_audio_state("uncertain", self._language)
            self._draw_preview()
        self._refresh_status()

    def toggle_pause(self) -> None:
        if not self._listening:
            return
        self._paused = not self._paused
        if self._paused and self._audio is not None:
            self._audio.stop()
            self._audio_states.reset()
            self._audio_state = "uncertain"
            self._preview_state = "uncertain"
            self.comfort.hide()
            self._draw_preview()
        elif not self._paused and self._audio is not None:
            try:
                self._audio.start()
                self._audio_buffer = AudioRingBuffer(round(self.config.audio.sample_rate * self.config.audio.window_seconds))
                self._last_audio_submit = 0.0
                self._audio_states.reset()
                self._audio_state = "uncertain"
                self._preview_state = "uncertain"
                self._audio_overlay_dismissed = False
                self.comfort.show_audio_state("uncertain", self._language)
                self._draw_preview()
            except Exception as exc:
                self.api_var.set(f"麦克风恢复失败：{exc}")
                self.stop_listening()
                return
        self._refresh_text()

    def stop_listening(self) -> None:
        self._listening = False
        self._paused = False
        if self.config.mode == "live":
            self._audio_states.reset()
            self._audio_state = "uncertain"
            self._preview_state = "uncertain"
            self.comfort.hide()
            self._draw_preview()
        if self._audio is not None:
            try:
                self._audio.stop()
            except Exception as exc:
                self.api_var.set(f"麦克风停止失败：{exc}")
        self._refresh_text()

    def toggle_dnd(self) -> None:
        self._dnd = self.dnd_var.get()
        if self._dnd:
            self.comfort.hide()
        elif self._listening and not self._paused and self.config.mode == "live":
            self._audio_overlay_dismissed = False
            self.comfort.show_audio_state(self._audio_states.state, self._language)
        self._refresh_status()

    def toggle_static(self) -> None:
        self._static = self.static_var.get()
        self.comfort.set_reduced_motion(self._static)

    def toggle_developer(self) -> None:
        self._developer_mode = self.developer_var.get()
        if self._developer_mode:
            self.developer_panel.pack(fill="x", pady=(6, 0))
        else:
            self.developer_panel.pack_forget()

    def _change_language(self, _event=None) -> None:
        self._language = self.language_var.get()
        self.comfort.set_language(self._language)
        self._refresh_text()

    def _change_theme(self, _event=None) -> None:
        self._theme = self.theme_var.get()
        self._apply_theme()

    def _change_strength(self, value: str) -> None:
        self._motion_strength = float(value)
        if hasattr(self, "comfort"):
            self.comfort.set_motion_strength(self._motion_strength)

    def _change_provider(self, _event=None) -> None:
        selected = self.provider_var.get()
        if selected == self._provider_name:
            return
        self._provider_name = selected
        self.runtime.switch_provider(
            ClefDecisionProvider(self.config.decision.clef_base_url, timeout_seconds=self.config.decision.timeout_seconds)
            if selected == "clef"
            else MockDecisionProvider()
        )
        self._refresh_context_status()
        self.api_var.set("")

    def simulate_scenario(self) -> None:
        scenario_id = self._selected_scenario()
        segment = self._transcripts.scenario(scenario_id, self._language if self._provider_name == "mock" else self.config.transcript.language)
        self.transcript_var.set(segment.text)
        self._submit_segment(segment, scenario_id)

    def submit_text(self) -> None:
        value = self.transcript_var.get().strip()
        if not value:
            return
        source = "manual" if self._provider_name == "clef" else "mock"
        segment = TranscriptSegment(value, language=self._language, source=source)
        self._submit_segment(segment, None)

    def _submit_segment(self, segment: TranscriptSegment, scenario_id: str | None) -> None:
        request = self.runtime.ingest(segment, scenario_id)
        if request is not None:
            self.decision_var.set(f"context #{request.context_revision} · {self._provider_name} · {segment.text}")
            self._refresh_context_status()

    def preview_response(self) -> None:
        action = self._preview_action
        self._preview_state = self._state_for_action(action)
        event = ResponseEvent(action, text(action, self._language), "gentle", "preview", 3.0, self._language)
        self._draw_preview()
        self.comfort.show(event)

    def _on_comfort_dismiss(self) -> None:
        self._audio_overlay_dismissed = True

    def _refresh_text(self) -> None:
        if not hasattr(self, "widgets"):
            return
        t = lambda key: text(key, self._language)
        self.root.title(t("app_title"))
        self.widgets["title"].configure(text="EmotiScreen")
        self.widgets["tagline"].configure(text=t("tagline"))
        self.start_button.configure(text=t("start"))
        self.pause_button.configure(text=t("resume" if self._paused else "pause"))
        self.stop_button.configure(text=t("stop"))
        self.dnd_button.configure(text=t("dnd"))
        self.preview_button.configure(text=t("preview"))
        self.lang_label.configure(text=t("language"))
        self.theme_label.configure(text=t("theme"))
        self.static_button.configure(text=t("static"))
        self.motion_label.configure(text=t("strength"))
        self.developer_toggle.configure(text=t("developer"))
        self.scenario_label.configure(text=t("decision"))
        self.simulate_button.configure(text=t("simulate"))
        self.text_label.configure(text=t("user_input"))
        self.submit_button.configure(text=t("simulate"))
        self.provider_label.configure(text=t("api_status"))
        self.decision_label.configure(text=t("decision"))
        self._refresh_material_label()
        self._refresh_scenario_names()
        self._refresh_status()
        self._draw_preview()

    def _refresh_scenario_names(self) -> None:
        self.scenario_box.configure(values=[text(scenario, self._language) for scenario in _SCENARIOS])
        scenario_id = self.scenario_var.get()
        if scenario_id not in _SCENARIOS:
            scenario_id = _SCENARIOS[0]
            self.scenario_var.set(scenario_id)
        self.scenario_box.set(text(scenario_id, self._language))

    def _refresh_status(self) -> None:
        if self._dnd:
            status = text("status_dnd", self._language)
        elif self._paused:
            status = text("status_paused", self._language)
        elif not self._listening:
            status = text("status_stopped", self._language)
        elif self.config.mode == "live":
            status = text("status_live", self._language)
        else:
            status = text("status_mock", self._language)
        self.status_var.set(status)
        if hasattr(self, "header_status_var"):
            if self.config.mode == "live":
                mode_label = "PAUSED" if self._paused else "LIVE AUDIO" if self._listening else "LIVE READY"
            else:
                mode_label = "MOCK" if self._provider_name == "mock" else "CLEF"
            self.header_status_var.set("• " + mode_label)
        color = "#C7A96B" if self._dnd else "#76A891" if self._listening and not self._paused else "#A6AFBC"
        self.status_dot.itemconfigure("dot", fill=color)
        if hasattr(self, "provider_status_var"):
            self._refresh_context_status()

    def _draw_preview(self, _event=None) -> None:
        if not hasattr(self, "preview_canvas"):
            return
        self.preview_canvas.delete("all")
        width = max(300, min(self.preview_canvas.winfo_width(), max(360, self.root.winfo_width() - 60)))
        height = max(250, self.preview_canvas.winfo_height())
        dark = self._theme == "dark"
        background = "#1E2938" if dark else "#E9EEF4"
        self.preview_canvas.configure(bg=background)
        palette = emotion_palette(self._preview_state, self._theme)
        columns = 100
        for index in range(columns):
            amount = index / max(1, columns - 1)
            x0 = width * index / columns
            x1 = width * (index + 1) / columns + 1
            self.preview_canvas.create_rectangle(
                x0, 0, x1, height,
                fill=interpolate_color(palette.start, palette.end, amount), outline="",
            )
        self.preview_canvas.create_oval(
            width - 230, -25, width + 10, 215,
            fill=interpolate_color(palette.end, palette.accent, 0.28), outline="",
        )
        self.preview_canvas.create_oval(
            -90, height - 160, 170, height + 90,
            fill=interpolate_color(palette.start, palette.end, 0.24), outline="",
        )
        self.preview_canvas.create_text(
            30, 28, anchor="w", text=text("preview_caption", self._language).upper(),
            fill=palette.muted, font=("Segoe UI", 8, "bold"),
        )
        self.preview_canvas.create_text(
            30, 76, anchor="w",
            text=text(_AUDIO_STATE_LABEL.get(self._preview_state, "audio_state_uncertain"), self._language),
            fill=palette.text, font=("Segoe UI", 10, "bold"),
        )
        phrase_key = {
            "low_arousal": "audio_low_phrase",
            "elevated": "audio_elevated_phrase",
            "uncertain": "audio_uncertain_phrase",
        }.get(self._preview_state, "audio_uncertain_phrase")
        self.preview_canvas.create_text(
            30, 130, anchor="w", width=max(260, width - 80), text=text(phrase_key, self._language),
            fill=palette.text, font=("Microsoft YaHei UI", 23, "bold"),
        )

    def _apply_theme(self) -> None:
        dark = self._theme == "dark"
        background = "#1B222D" if dark else "#F5F7FA"
        foreground = "#E9EDF3" if dark else "#263445"
        self.root.configure(bg=background)
        self.style.configure("TFrame", background=background)
        self.style.configure("TLabelframe", background=background, foreground=foreground)
        self.style.configure("TLabelframe.Label", background=background, foreground=foreground)
        self.style.configure("TLabel", background=background, foreground=foreground)
        self.style.configure("Title.TLabel", background=background, foreground=foreground)
        self.style.configure("Tagline.TLabel", background=background, foreground="#A0AABA" if dark else "#687486")
        self.style.configure("Stage.TFrame", background="#202A38" if dark else "#EEF2F7", borderwidth=0)
        primary_bg = "#91A8C7" if dark else "#4C6A8E"
        primary_fg = "#15202D" if dark else "#FFFFFF"
        soft_bg = "#2D3949" if dark else "#E5EAF1"
        soft_fg = "#E8EDF4" if dark else "#40536B"
        self.style.configure("Primary.TButton", background=primary_bg, foreground=primary_fg, padding=(18, 11), borderwidth=0)
        self.style.map("Primary.TButton", background=[("active", "#6682A7" if dark else "#395B80")])
        self.style.configure("Soft.TButton", background=soft_bg, foreground=soft_fg, padding=(14, 10), borderwidth=0)
        self.style.map("Soft.TButton", background=[("active", "#3B4A5D" if dark else "#D8E0EA")])
        if hasattr(self, "comfort"):
            self.comfort.set_theme(self._theme)
        self._refresh_material_label()
        self._draw_preview()

    def _refresh_material_label(self) -> None:
        if hasattr(self, "material_var") and hasattr(self, "comfort"):
            material_key = "native_acrylic" if self.comfort.native_blur else "fallback_glass"
            self.material_var.set(text(material_key, self._language))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.stop_listening()
        self.runtime.close()
        if self._audio_worker is not None:
            self._audio_worker.close()
        self.comfort.close()
        if self._after_id:
            try:
                self.root.after_cancel(self._after_id)
            except tk.TclError:
                pass
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
