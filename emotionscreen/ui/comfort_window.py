"""情绪渐变玻璃浮层；只适配 TkAnimator 和 CTkMessagebox 中的少量片段。"""

from __future__ import annotations

from dataclasses import replace
import math
import tkinter as tk
import time
from typing import Callable

from ..core.i18n import text
from ..core.models import ResponseEvent
from .glass import (
    emotion_palette,
    apply_glass,
    interpolate_color,
    prepare_no_activate,
    set_glass_opacity,
    show_no_activate,
    window_scale_factor,
)

_KEY_COLOR = "#010203"
_ACTION_STATE = {"support": "low_arousal", "acknowledge": "elevated", "celebrate": "elevated", "listen": "uncertain"}
_STATE_PHRASE = {
    "low_arousal": "audio_low_phrase",
    "elevated": "audio_elevated_phrase",
    "uncertain": "audio_uncertain_phrase",
}
_STATE_LABEL = {
    "low_arousal": "audio_state_low",
    "elevated": "audio_state_elevated",
    "uncertain": "audio_state_uncertain",
}


class ComfortWindow:
    WIDTH = 520
    HEIGHT = 280
    GLASS_COLUMNS = 128
    CORNER_RADIUS = 34

    def __init__(
        self,
        root: tk.Misc,
        *,
        language: str = "zh-CN",
        reduced_motion: bool = False,
        motion_strength: float = 0.72,
        theme: str = "system",
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.language = language
        self.reduced_motion = reduced_motion
        self.motion_strength = min(1.0, max(0.0, motion_strength))
        self.theme = "light" if theme == "system" else theme
        self.on_dismiss = on_dismiss
        self.window = tk.Toplevel(root, takefocus=False)
        self.window.withdraw()
        self.window.overrideredirect(True)
        try:
            self.window.attributes("-topmost", True)
        except tk.TclError:
            pass
        self.window.title("EmotiScreen")
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+0+0")
        self.visible = False
        self.persistent = False
        self._hiding = False
        self._native_blur = False
        self._hide_after: str | None = None
        self._fade_after: str | None = None
        self._theme_after: str | None = None
        self._motion_after: str | None = None
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._current_event: ResponseEvent | None = None
        self._state = "uncertain"
        self._palette = emotion_palette(self._state, self.theme)
        self._fade_steps = 10
        self._phase = 0.0
        self._motion_last_at = time.monotonic()
        self._gradient_ids: list[tuple[int, float]] = []
        self._glow_ids: list[tuple[int, float, float, float, float]] = []
        self._state_id: int | None = None
        self._phrase_id: int | None = None
        self._caption_id: int | None = None
        self._close_id: int | None = None
        self._transition_old_ids: tuple[int, int] | None = None
        self._transition_new_ids: tuple[int, int] | None = None
        self.canvas = tk.Canvas(self.window, width=self.WIDTH, height=self.HEIGHT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._configure_material()
        self._build_glass("uncertain", text(_STATE_PHRASE["uncertain"], self.language))
        for widget in (self.window, self.canvas):
            widget.bind("<ButtonPress-1>", self._begin_drag, add="+")
            widget.bind("<B1-Motion>", self._drag, add="+")

    @property
    def native_blur(self) -> bool:
        return self._native_blur

    @property
    def state(self) -> str:
        return self._state

    def _configure_material(self) -> None:
        try:
            self.window.configure(bg=_KEY_COLOR)
            self.window.attributes("-transparentcolor", _KEY_COLOR)
            self.canvas.configure(bg=_KEY_COLOR)
            report = apply_glass(self.window)
            self._native_blur = report.native_blur
        except (tk.TclError, RuntimeError):
            self._native_blur = False
        if not self._native_blur:
            self._use_glass_fallback()
        self._set_alpha(0.98)

    def _set_alpha(self, value: float, tint: str | None = None) -> None:
        if self._native_blur:
            set_glass_opacity(self.window, value, tint or self._palette.tint)
            return
        try:
            self.window.attributes("-alpha", value)
        except tk.TclError:
            pass

    def _use_glass_fallback(self) -> None:
        background = "#202A38" if self.theme == "dark" else "#E9EEF5"
        self.canvas.configure(bg=background)
        self.window.configure(bg=background)

    def _column_y_bounds(self, x_center: float) -> tuple[float, float]:
        edge_distance = min(x_center, self.WIDTH - x_center)
        radius = self.CORNER_RADIUS
        if edge_distance >= radius:
            inset = 0.0
        else:
            dx = radius - edge_distance
            inset = radius - math.sqrt(max(0.0, radius * radius - dx * dx))
        return inset, self.HEIGHT - inset

    def _build_glass(self, state: str, phrase: str) -> None:
        self.canvas.delete("all")
        self._gradient_ids.clear()
        self._glow_ids.clear()
        self._state = state
        self._palette = emotion_palette(state, self.theme)
        self._draw_gradient(self._palette)

        glow_a = self.canvas.create_oval(
            self.WIDTH - 205, 18, self.WIDTH + 28, 251,
            fill=interpolate_color(self._palette.end, self._palette.accent, 0.28), outline="",
        )
        glow_b = self.canvas.create_oval(
            -104, self.HEIGHT - 126, 142, self.HEIGHT + 74,
            fill=interpolate_color(self._palette.start, self._palette.end, 0.24), outline="",
        )
        self._glow_ids = [
            (glow_a, self.WIDTH - 88, 134, 116.0, 116.0),
            (glow_b, 18, self.HEIGHT - 25, 123.0, 100.0),
        ]
        self._state_id = self.canvas.create_text(
            38, 47, anchor="w", text=text(_STATE_LABEL[state], self.language),
            fill=self._palette.muted, font=("Segoe UI", 10, "bold"),
        )
        self._phrase_id = self.canvas.create_text(
            36, 127, anchor="w", text=phrase, width=self.WIDTH - 100,
            fill=self._palette.text, font=("Microsoft YaHei UI", 24, "bold"),
        )
        self._caption_id = self.canvas.create_text(
            38, self.HEIGHT - 34, anchor="w", text=text("ambient_caption", self.language),
            fill=self._palette.muted, font=("Segoe UI", 8),
        )
        self._close_id = self.canvas.create_text(
            self.WIDTH - 32, 32, text="×", fill=self._palette.text, font=("Segoe UI", 18),
        )
        self.canvas.tag_bind(self._close_id, "<Button-1>", lambda _event: self.dismiss())

    def _draw_gradient(self, palette) -> None:
        self._gradient_ids = []
        for index in range(self.GLASS_COLUMNS):
            fraction = index / max(1, self.GLASS_COLUMNS - 1)
            x0 = self.WIDTH * index / self.GLASS_COLUMNS
            x1 = self.WIDTH * (index + 1) / self.GLASS_COLUMNS + 1
            y0, y1 = self._column_y_bounds((x0 + x1) / 2)
            color = interpolate_color(palette.start, palette.end, fraction)
            item = self.canvas.create_rectangle(
                x0, y0, x1, y1, fill=color, outline=color,
                tags=("glass_gradient",),
            )
            self._gradient_ids.append((item, fraction))
        self.canvas.tag_lower("glass_gradient")

    def _apply_palette(self, palette) -> None:
        self._palette = palette
        for item, fraction in self._gradient_ids:
            color = interpolate_color(palette.start, palette.end, fraction)
            self.canvas.itemconfigure(item, fill=color, outline=color)
        if self._state_id is not None:
            self.canvas.itemconfigure(self._state_id, fill=palette.muted)
        if self._caption_id is not None:
            self.canvas.itemconfigure(self._caption_id, fill=palette.muted)
        if self._close_id is not None:
            self.canvas.itemconfigure(self._close_id, fill=palette.text)
        if self._glow_ids:
            self.canvas.itemconfigure(
                self._glow_ids[0][0], fill=interpolate_color(palette.end, palette.accent, 0.28)
            )
            self.canvas.itemconfigure(
                self._glow_ids[1][0], fill=interpolate_color(palette.start, palette.end, 0.24)
            )

    def _fade_message(self, event: ResponseEvent, state: str, source_palette, target_palette) -> None:
        if self._transition_new_ids:
            for item in self._transition_new_ids:
                self.canvas.delete(item)
        if self._transition_old_ids:
            for item in self._transition_old_ids:
                self.canvas.delete(item)
        self._transition_old_ids = (self._state_id, self._phrase_id)
        new_state = self.canvas.create_text(
            38, 47, anchor="w", text=text(_STATE_LABEL[state], self.language),
            fill=source_palette.start, font=("Segoe UI", 10, "bold"),
        )
        new_phrase = self.canvas.create_text(
            36, 127, anchor="w", text=event.phrase, width=self.WIDTH - 100,
            fill=source_palette.start, font=("Microsoft YaHei UI", 24, "bold"),
        )
        self._transition_new_ids = (new_state, new_phrase)

    def _transition_to(self, event: ResponseEvent, state: str) -> None:
        if self._theme_after:
            self._cancel_timer(self._theme_after)
            self._theme_after = None
            self._finish_theme_transition()
        source_palette = self._palette
        target_palette = emotion_palette(state, self.theme)
        self._current_event = event
        if state == self._state and source_palette == target_palette and self._phrase_id is not None:
            self.canvas.itemconfigure(self._phrase_id, text=event.phrase)
            if self._state_id is not None:
                self.canvas.itemconfigure(self._state_id, text=text(_STATE_LABEL[state], self.language))
            if self._caption_id is not None:
                self.canvas.itemconfigure(self._caption_id, text=text("ambient_caption", self.language))
            return
        self._fade_message(event, state, source_palette, target_palette)
        self._state = state
        self._theme_source = source_palette
        self._theme_target = target_palette
        self._theme_target_state = state
        self._theme_started_at = time.monotonic()
        self._theme_duration = 0.8
        if self.reduced_motion:
            self._finish_theme_transition()
        else:
            self._animate_theme_transition()

    def _animate_theme_transition(self) -> None:
        raw_progress = min(1.0, (time.monotonic() - self._theme_started_at) / self._theme_duration)
        progress = raw_progress * raw_progress * (3 - 2 * raw_progress)
        source = self._theme_source
        target = self._theme_target
        palette = type(source)(
            start=interpolate_color(source.start, target.start, progress),
            end=interpolate_color(source.end, target.end, progress),
            tint=interpolate_color(source.tint, target.tint, progress),
            accent=interpolate_color(source.accent, target.accent, progress),
            text=interpolate_color(source.text, target.text, progress),
            muted=interpolate_color(source.muted, target.muted, progress),
        )
        self._apply_palette(palette)
        middle_start = interpolate_color(source.start, target.start, progress)
        middle_end = interpolate_color(source.end, target.end, progress)
        phrase_background = interpolate_color(middle_start, middle_end, 0.12)
        if self._transition_old_ids and self._transition_new_ids:
            old_state, old_phrase = self._transition_old_ids
            new_state, new_phrase = self._transition_new_ids
            if progress < 0.5:
                fade = progress * 2
                old_color = interpolate_color(source.text, phrase_background, fade)
                self.canvas.itemconfigure(old_state, fill=old_color)
                self.canvas.itemconfigure(old_phrase, fill=old_color)
                self.canvas.itemconfigure(new_state, fill=phrase_background)
                self.canvas.itemconfigure(new_phrase, fill=phrase_background)
            else:
                fade = (progress - 0.5) * 2
                new_color = interpolate_color(phrase_background, target.text, fade)
                self.canvas.itemconfigure(old_state, fill=phrase_background)
                self.canvas.itemconfigure(old_phrase, fill=phrase_background)
                self.canvas.itemconfigure(new_state, fill=interpolate_color(phrase_background, target.muted, fade))
                self.canvas.itemconfigure(new_phrase, fill=new_color)
        if raw_progress >= 1.0:
            self._finish_theme_transition()
            return
        self._theme_after = self.root.after(33, self._animate_theme_transition)

    def _finish_theme_transition(self) -> None:
        target = getattr(self, "_theme_target", self._palette)
        state = getattr(self, "_theme_target_state", self._state)
        self._apply_palette(target)
        if self._native_blur:
            set_glass_opacity(self.window, 0.94, target.tint)
        if self._transition_old_ids:
            for item in self._transition_old_ids:
                if item is not None:
                    self.canvas.delete(item)
        if self._transition_new_ids:
            self._state_id, self._phrase_id = self._transition_new_ids
        self._transition_old_ids = None
        self._transition_new_ids = None
        self._state = state
        self._theme_after = None

    def show(self, event: ResponseEvent) -> None:
        if event.action == "listen" and not event.persistent:
            return
        state = event.state or _ACTION_STATE.get(event.action, "uncertain")
        if state not in _STATE_LABEL:
            state = "uncertain"
        self._current_event = event
        self.language = event.language
        self.persistent = event.persistent
        self._fade_steps = 10 + round(self.motion_strength * 4)
        self._cancel_timer(self._hide_after)
        self._hide_after = None
        if self._hiding:
            self._cancel_timer(self._fade_after)
            self._fade_after = None
            self._hiding = False
        if self.visible:
            self._transition_to(event, state)
            show_no_activate(self.window)
        else:
            if self._theme_after:
                self._cancel_timer(self._theme_after)
                self._theme_after = None
            self._build_glass(state, event.phrase)
            if self._native_blur:
                set_glass_opacity(self.window, 0.96, self._palette.tint)
            self.window.update_idletasks()
            x, y = self._place_bottom_right()
            self.visible = True
            try:
                prepare_no_activate(self.window)
                self._set_alpha(0.03 if not self.reduced_motion else 0.98)
                show_no_activate(self.window, x=x, y=y, width=self.WIDTH, height=self.HEIGHT)
            except tk.TclError:
                self.window.deiconify()
            if self.reduced_motion:
                self._set_alpha(0.98, self._palette.tint)
            else:
                self._fade_in(0)
            self._start_motion()
        if not event.persistent:
            self._hide_after = self.root.after(round(event.duration_seconds * 1000), self.hide)

    def show_audio_state(self, state: str, language: str = "zh-CN") -> None:
        if state not in _STATE_LABEL:
            state = "uncertain"
        action = {"low_arousal": "support", "elevated": "acknowledge", "uncertain": "listen"}[state]
        phrase = text(_STATE_PHRASE[state], language)
        event = ResponseEvent(action, phrase, "gentle", f"audio-{state}", 0.0, language, state=state, persistent=True)
        self.show(event)

    def _place_bottom_right(self) -> tuple[int, int]:
        self.window.update_idletasks()
        scale = window_scale_factor(self.window)
        screen_width = round(self.window.winfo_screenwidth() / scale)
        screen_height = round(self.window.winfo_screenheight() / scale)
        x = screen_width - self.WIDTH - 30
        y = screen_height - self.HEIGHT - 50
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self.window.update_idletasks()
        return x, y

    def _fade_in(self, step: int) -> None:
        if not self.visible or step >= self._fade_steps:
            self._set_alpha(0.96, self._palette.tint)
            self._fade_after = None
            return
        opacity = 0.96 * (step + 1) / self._fade_steps
        self._set_alpha(opacity, self._palette.tint)
        self._fade_after = self.root.after(28, lambda: self._fade_in(step + 1))

    def hide(self) -> None:
        self._cancel_timer(self._hide_after)
        self._hide_after = None
        self.persistent = False
        if not self.visible:
            return
        if self._theme_after:
            self._cancel_timer(self._theme_after)
            self._finish_theme_transition()
        if self.reduced_motion:
            self._finish_hide()
            return
        self._cancel_timer(self._fade_after)
        self._fade_after = None
        self._hiding = True
        self._fade_out(0)

    def _fade_out(self, step: int) -> None:
        if step >= self._fade_steps:
            self._finish_hide()
            return
        self._set_alpha(max(0.02, 0.96 * (1 - (step + 1) / self._fade_steps)), self._palette.tint)
        self._fade_after = self.root.after(28, lambda: self._fade_out(step + 1))

    def _finish_hide(self) -> None:
        self.visible = False
        self._cancel_timer(self._motion_after)
        self._motion_after = None
        self._fade_after = None
        self._hiding = False
        self.window.withdraw()
        self._set_alpha(0.96, self._palette.tint)

    def dismiss(self) -> None:
        self._cancel_timer(self._hide_after)
        self._cancel_timer(self._fade_after)
        self._cancel_timer(self._motion_after)
        self._hide_after = self._fade_after = self._motion_after = None
        self._hiding = False
        if self._theme_after:
            self._cancel_timer(self._theme_after)
            self._finish_theme_transition()
        self._finish_hide()
        if self.on_dismiss:
            self.on_dismiss()

    def set_language(self, language: str) -> None:
        self.language = language
        if self._current_event is not None:
            if self._current_event.persistent:
                phrase_key = _STATE_PHRASE.get(self._state, _STATE_PHRASE["uncertain"])
            else:
                phrase_key = self._current_event.action
            self.show(replace(self._current_event, phrase=text(phrase_key, language), language=language))

    def set_reduced_motion(self, enabled: bool) -> None:
        self.reduced_motion = enabled
        if enabled and self.visible:
            self._cancel_timer(self._fade_after)
            self._cancel_timer(self._motion_after)
            self._fade_after = self._motion_after = None
            if self._theme_after:
                self._cancel_timer(self._theme_after)
                self._finish_theme_transition()
            self._set_alpha(0.96, self._palette.tint)
        elif not enabled and self.visible:
            self._start_motion()

    def set_motion_strength(self, value: float) -> None:
        self.motion_strength = min(1.0, max(0.0, value))
        if self.visible:
            self._start_motion()

    def set_theme(self, theme: str) -> None:
        self.theme = "light" if theme == "system" else theme
        if not self._native_blur:
            self._use_glass_fallback()
        if self._current_event is not None:
            self.show(self._current_event)

    def _use_glass_fallback(self) -> None:
        background = "#1D2838" if self.theme == "dark" else "#E8EEF4"
        self.canvas.configure(bg=background)
        self.window.configure(bg=background)

    def _begin_drag(self, event) -> None:
        self._drag_origin = (event.x_root, event.y_root, self.window.winfo_x(), self.window.winfo_y())

    def _drag(self, event) -> None:
        if self._drag_origin is None:
            return
        start_x, start_y, window_x, window_y = self._drag_origin
        self.window.geometry(f"+{window_x + event.x_root - start_x}+{window_y + event.y_root - start_y}")

    def _cancel_timer(self, timer_id: str | None) -> None:
        if timer_id:
            try:
                self.root.after_cancel(timer_id)
            except tk.TclError:
                pass

    def _start_motion(self) -> None:
        self._cancel_timer(self._motion_after)
        self._motion_after = None
        if self.visible and not self.reduced_motion and self.motion_strength > 0:
            self._motion_last_at = time.monotonic()
            self._animate_motion()

    def _animate_motion(self) -> None:
        if not self.visible or self.reduced_motion or self.motion_strength <= 0 or not self._glow_ids:
            self._motion_after = None
            return
        now = time.monotonic()
        elapsed = max(0.0, min(0.1, now - self._motion_last_at))
        self._motion_last_at = now
        self._phase += elapsed * (2 * math.pi / 5.4)
        drift = 0.16 * self.motion_strength * math.sin(self._phase)
        for item, fraction in self._gradient_ids:
            amount = max(0.0, min(1.0, fraction + drift))
            color = interpolate_color(self._palette.start, self._palette.end, amount)
            self.canvas.itemconfigure(item, fill=color, outline=color)
        for index, (item, center_x, center_y, radius_x, radius_y) in enumerate(self._glow_ids):
            phase = self._phase + index * math.pi / 2
            scale = 1.0 + 0.10 * self.motion_strength * math.sin(phase)
            rx, ry = radius_x * scale, radius_y * scale
            self.canvas.coords(item, center_x - rx, center_y - ry, center_x + rx, center_y + ry)
        self._motion_after = self.root.after(33, self._animate_motion)

    def close(self) -> None:
        self._cancel_timer(self._hide_after)
        self._cancel_timer(self._fade_after)
        self._cancel_timer(self._theme_after)
        self._cancel_timer(self._motion_after)
        self.window.destroy()
