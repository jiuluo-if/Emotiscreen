"""默认隐藏的短时安慰卡片。"""

from __future__ import annotations

import tkinter as tk
from typing import Callable

from ..core.i18n import text
from ..core.models import ResponseEvent
from .glass import apply_glass, prepare_no_activate, set_glass_opacity, show_no_activate

_KEY_COLOR = "#010203"
_PALETTES = {
    "celebrate": ("#FFF1D8", "#B77432", "#E8B85F"),
    "support": ("#E8EDF7", "#627899", "#8299BB"),
    "acknowledge": ("#EBF1ED", "#5C8172", "#83A996"),
    "listen": ("#E8EDF7", "#627899", "#8299BB"),
}
_DARK_PALETTES = {
    "celebrate": ("#343039", "#FFE3B0", "#E8B85F"),
    "support": ("#2B3444", "#E2EAF7", "#8299BB"),
    "acknowledge": ("#2C3937", "#DCEDE5", "#83A996"),
    "listen": ("#2B3444", "#E2EAF7", "#8299BB"),
}


class ComfortWindow:
    WIDTH = 390
    HEIGHT = 210

    def __init__(
        self,
        root: tk.Misc,
        *,
        language: str = "zh-CN",
        reduced_motion: bool = False,
        motion_strength: float = 0.35,
        theme: str = "system",
        on_dismiss: Callable[[], None] | None = None,
    ) -> None:
        self.root = root
        self.language = language
        self.reduced_motion = reduced_motion
        self.motion_strength = min(1.0, max(0.0, motion_strength))
        self.theme = theme
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
        self._native_blur = False
        self._hide_after: str | None = None
        self._animation_after: str | None = None
        self._motion_after: str | None = None
        self._drag_origin: tuple[int, int, int, int] | None = None
        self._current_event: ResponseEvent | None = None
        self._fade_steps = 6
        self._phase = 0.0
        self._glow_id: int | None = None
        self._particle_ids: list[tuple[int, float, float, float]] = []
        self.canvas = tk.Canvas(self.window, width=self.WIDTH, height=self.HEIGHT, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self._configure_material()
        self._draw_card("acknowledge", "", "subtle")
        for widget in (self.window, self.canvas):
            widget.bind("<ButtonPress-1>", self._begin_drag, add="+")
            widget.bind("<B1-Motion>", self._drag, add="+")

    @property
    def native_blur(self) -> bool:
        return self._native_blur

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
            self._use_card_fallback()
        self._set_alpha(0.98)

    def _set_alpha(self, value: float) -> None:
        if self._native_blur:
            set_glass_opacity(self.window, value)
            return
        try:
            self.window.attributes("-alpha", value)
        except tk.TclError:
            pass

    def _use_card_fallback(self) -> None:
        background = "#29313D" if self.theme == "dark" else "#E9EEF5"
        self.canvas.configure(bg=background)
        self.window.configure(bg=background)

    def _draw_card(self, action: str, phrase: str, intensity: str) -> None:
        self.canvas.delete("all")
        palettes = _DARK_PALETTES if self.theme == "dark" or self._native_blur else _PALETTES
        card_color, ink, accent = palettes.get(action, palettes["acknowledge"])
        card_id = self._draw_rounded_card(card_color)
        self.canvas.tag_bind(card_id, "<ButtonPress-1>", self._begin_drag)
        self.canvas.tag_bind(card_id, "<B1-Motion>", self._drag)
        icon = "♥" if action == "support" else "✦" if action == "celebrate" else "•"
        self.canvas.create_oval(30, 34, 72, 76, fill=accent, outline="")
        self.canvas.create_text(51, 55, text=icon, fill="#FFFFFF", font=("Segoe UI Symbol", 17, "bold"))
        self.canvas.create_text(88, 47, anchor="w", text=text(f"tag_{action}", self.language).upper(), fill=ink, font=("Segoe UI", 8, "bold"))
        self.canvas.create_text(
            32, 108, anchor="w", text=phrase, fill=ink,
            font=("Microsoft YaHei UI", 26 if intensity == "gentle" else 23, "bold"),
        )
        self.canvas.create_line(32, 146, self.WIDTH - 32, 146, fill=accent, width=1, stipple="gray50")
        self.canvas.create_text(32, 173, anchor="w", text=text("privacy_hint", self.language), fill=ink, font=("Microsoft YaHei UI", 8))
        close_id = self.canvas.create_text(self.WIDTH - 32, 28, text="×", fill=ink, font=("Segoe UI", 18))
        self.canvas.tag_bind(close_id, "<Button-1>", lambda _event: self.dismiss())
        self._glow_id = self.canvas.create_oval(318, 145, 362, 189, fill=accent, outline="", stipple="gray50")
        self._particle_ids = []
        if action == "celebrate":
            for x, y, phase in ((300, 92, 0.0), (340, 98, 2.0), (320, 120, 4.0)):
                item = self.canvas.create_text(x, y, text="✦", fill=accent, font=("Segoe UI Symbol", 10))
                self._particle_ids.append((item, x, y, phase))

    def _draw_rounded_card(self, color: str) -> int:
        radius = 22
        points = [
            radius, 0, self.WIDTH - radius, 0, self.WIDTH, 0,
            self.WIDTH, radius, self.WIDTH, self.HEIGHT - radius,
            self.WIDTH, self.HEIGHT, self.WIDTH - radius, self.HEIGHT,
            radius, self.HEIGHT, 0, self.HEIGHT, 0, self.HEIGHT - radius,
            0, radius, 0, 0,
        ]
        card = self.canvas.create_polygon(points, smooth=True, splinesteps=16, fill=color, outline="#FFFFFF", width=1, tags=("drag_region",))
        self.canvas.tag_lower(card)
        return card

    def show(self, event: ResponseEvent) -> None:
        if event.action == "listen":
            return
        self._current_event = event
        self._cancel_timer(self._animation_after)
        self._animation_after = None
        # Adapt TkAnimator's stepped alpha transition, using Tk.after instead
        # of CTkMessagebox's blocking sleep/update fade loop.
        self._fade_steps = 10 + round(self.motion_strength * 4)
        self.language = event.language
        self._draw_card(event.action, event.phrase, event.intensity)
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
            self._set_alpha(0.98)
        else:
            self._fade_in(0)
            self._start_motion()
        self._cancel_timer(self._hide_after)
        self._hide_after = self.root.after(round(event.duration_seconds * 1000), self.hide)

    def _place_bottom_right(self) -> tuple[int, int]:
        self.window.update_idletasks()
        screen_width = self.window.winfo_screenwidth()
        screen_height = self.window.winfo_screenheight()
        x = screen_width - self.WIDTH - 28
        y = screen_height - self.HEIGHT - 58
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}+{x}+{y}")
        self.window.update_idletasks()
        return x, y

    def _fade_in(self, step: int) -> None:
        if not self.visible or step >= self._fade_steps:
            self._set_alpha(0.98)
            return
        # Adapt the upstream opacity interpolation into a cancellable Tk callback.
        self._set_alpha(0.98 * (step + 1) / self._fade_steps)
        self._animation_after = self.root.after(28, lambda: self._fade_in(step + 1))

    def hide(self) -> None:
        self._hide_after = None
        if not self.visible:
            return
        if self.reduced_motion:
            self._finish_hide()
            return
        self._fade_out(0)

    def _fade_out(self, step: int) -> None:
        if step >= self._fade_steps:
            self._finish_hide()
            return
        self._set_alpha(max(0.0, 0.98 * (1 - (step + 1) / self._fade_steps)))
        self._animation_after = self.root.after(28, lambda: self._fade_out(step + 1))

    def _finish_hide(self) -> None:
        self.visible = False
        self._cancel_timer(self._motion_after)
        self._motion_after = None
        self.window.withdraw()
        self._set_alpha(0.98)
        self._animation_after = None

    def dismiss(self) -> None:
        self._cancel_timer(self._hide_after)
        self._cancel_timer(self._animation_after)
        self._hide_after = self._animation_after = None
        self._finish_hide()
        if self.on_dismiss:
            self.on_dismiss()

    def set_language(self, language: str) -> None:
        self.language = language

    def set_reduced_motion(self, enabled: bool) -> None:
        self.reduced_motion = enabled
        if enabled and self.visible:
            self._cancel_timer(self._animation_after)
            self._cancel_timer(self._motion_after)
            self._animation_after = self._motion_after = None
            self._set_alpha(0.98)
        elif not enabled and self.visible:
            self._start_motion()

    def set_motion_strength(self, value: float) -> None:
        self.motion_strength = min(1.0, max(0.0, value))
        if self.visible:
            self._start_motion()

    def _start_motion(self) -> None:
        self._cancel_timer(self._motion_after)
        self._motion_after = None
        if self.visible and not self.reduced_motion and self.motion_strength > 0:
            self._animate_motion()

    def _animate_motion(self) -> None:
        if not self.visible or self.reduced_motion or self.motion_strength <= 0 or self._glow_id is None:
            self._motion_after = None
            return
        import math

        # The low-amplitude sine pulse follows TkAnimator.animate_pulse's curve.
        self._phase += 0.12
        radius = 22 + 2 * self.motion_strength * math.sin(self._phase)
        self.canvas.coords(self._glow_id, 340 - radius, 167 - radius, 340 + radius, 167 + radius)
        for item, x, y, phase in self._particle_ids:
            offset = math.sin(self._phase + phase) * 5 * self.motion_strength
            self.canvas.coords(item, x, y + offset)
        self._motion_after = self.root.after(80, self._animate_motion)

    def set_theme(self, theme: str) -> None:
        self.theme = theme
        if not self._native_blur:
            self._use_card_fallback()
        if self.visible and self._current_event is not None:
            self._draw_card(self._current_event.action, self._current_event.phrase, self._current_event.intensity)

    def _begin_drag(self, event) -> None:
        # Drag anchor follows CTkMessagebox's oldxyset/move_window pattern.
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

    def close(self) -> None:
        self._cancel_timer(self._hide_after)
        self._cancel_timer(self._animation_after)
        self._cancel_timer(self._motion_after)
        self.window.destroy()
