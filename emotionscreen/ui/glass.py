"""平台玻璃材质支持；Windows ctypes 结构适配自 window-vibrancy 0.7.1。

上游源码和许可证见 `THIRD_PARTY_NOTICES.md`。
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import re
import sys
import tkinter as tk


@dataclass(frozen=True)
class MaterialReport:
    platform: str
    native_blur: bool
    description: str


@dataclass(frozen=True)
class EmotionPalette:
    start: str
    end: str
    tint: str
    accent: str
    text: str
    muted: str


_LIGHT_EMOTION_PALETTES = {
    "low_arousal": EmotionPalette("#668DBA", "#A69CCB", "#7188A6", "#D5E7F4", "#F5F8FD", "#E3EAF5"),
    "elevated": EmotionPalette("#D68B5D", "#C96F7D", "#9C705B", "#FFE0B7", "#FFF8EF", "#F4E2D5"),
    "uncertain": EmotionPalette("#6F9E94", "#849BB8", "#738F93", "#D0E8DF", "#F5FBF9", "#E3EFEB"),
}
_DARK_EMOTION_PALETTES = {
    "low_arousal": EmotionPalette("#253B56", "#40385F", "#24384C", "#8EACCA", "#F1F6FB", "#CDD8E5"),
    "elevated": EmotionPalette("#523B2D", "#603842", "#49342D", "#D9A57A", "#FFF6ED", "#E8D3C3"),
    "uncertain": EmotionPalette("#29423F", "#34465F", "#2B4144", "#91BDB2", "#F1F8F5", "#CEDFD9"),
}


def emotion_palette(state: str, theme: str = "light") -> EmotionPalette:
    palettes = _DARK_EMOTION_PALETTES if theme == "dark" else _LIGHT_EMOTION_PALETTES
    return palettes.get(state, palettes["uncertain"])


def interpolate_color(start: str, end: str, progress: float) -> str:
    """插值两个 RGB 颜色；适配 TkAnimator 的颜色过渡片段。"""
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", start) or not re.fullmatch(r"#[0-9a-fA-F]{6}", end):
        raise ValueError("colors must be #RRGGBB")
    amount = max(0.0, min(1.0, float(progress)))
    start_rgb = tuple(int(start[index : index + 2], 16) for index in (1, 3, 5))
    end_rgb = tuple(int(end[index : index + 2], 16) for index in (1, 3, 5))
    channels = tuple(round(a + (b - a) * amount) for a, b in zip(start_rgb, end_rgb))
    return "#" + "".join(f"{channel:02X}" for channel in channels)


def apply_glass(window) -> MaterialReport:
    if sys.platform != "win32":
        platform = "macOS" if sys.platform == "darwin" else "Linux/其他系统"
        return MaterialReport(sys.platform, False, f"{platform} 使用半透明卡片回退；未启用原生背景模糊。")
    try:
        if sys.getwindowsversion().build < 17763:
            return MaterialReport("win32", False, "Windows 版本不支持 Acrylic，已回退为半透明卡片。")
        window.update_idletasks()
        hwnd = _root_hwnd(window.winfo_id())
        if not _set_windows_acrylic(hwnd):
            return MaterialReport("win32", False, "Windows Acrylic 不可用，已回退为半透明卡片。")
        _set_windows_rounded_corners(hwnd)
        return MaterialReport("win32", True, "Windows 原生 Acrylic 已启用。")
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError) as exc:
        return MaterialReport("win32", False, f"Windows Acrylic 调用失败，已回退为半透明卡片：{exc}")


def _root_hwnd(hwnd: int) -> int:
    user32 = ctypes.windll.user32
    user32.GetAncestor.argtypes = (ctypes.c_void_p, ctypes.c_uint)
    user32.GetAncestor.restype = ctypes.c_void_p
    return int(user32.GetAncestor(ctypes.c_void_p(hwnd), 2) or hwnd)


def _set_windows_acrylic(hwnd: int) -> bool:
    class AccentPolicy(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_uint),
            ("AnimationId", ctypes.c_int),
        ]

    class WindowCompositionAttributeData(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.c_void_p),
            ("SizeOfData", ctypes.c_size_t),
        ]

    # window-vibrancy uses AccentFlags=0 for acrylic (state 4).
    accent = AccentPolicy(4, 0, 0xD9212A38, 0)  # ACCENT_ENABLE_ACRYLICBLURBEHIND
    data = WindowCompositionAttributeData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
    function = ctypes.windll.user32.SetWindowCompositionAttribute
    function.argtypes = (ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData))
    function.restype = ctypes.c_int
    return bool(function(ctypes.c_void_p(hwnd), ctypes.byref(data)))


def _set_windows_rounded_corners(hwnd: int) -> None:
    preference = ctypes.c_int(2)  # DWMWCP_ROUND
    function = ctypes.windll.dwmapi.DwmSetWindowAttribute
    function.argtypes = (ctypes.c_void_p, ctypes.c_uint, ctypes.c_void_p, ctypes.c_uint)
    function.restype = ctypes.c_long
    function(ctypes.c_void_p(hwnd), 33, ctypes.byref(preference), ctypes.sizeof(preference))


def set_glass_opacity(window, opacity: float, tint: str = "#212A38") -> bool:
    """调整 Acrylic tint 的 alpha/color，不把原生毛玻璃改成 layered Tk 窗口。"""
    if sys.platform != "win32":
        return False

    class AccentPolicy(ctypes.Structure):
        _fields_ = [
            ("AccentState", ctypes.c_int),
            ("AccentFlags", ctypes.c_int),
            ("GradientColor", ctypes.c_uint),
            ("AnimationId", ctypes.c_int),
        ]

    class WindowCompositionAttributeData(ctypes.Structure):
        _fields_ = [
            ("Attribute", ctypes.c_int),
            ("Data", ctypes.c_void_p),
            ("SizeOfData", ctypes.c_size_t),
        ]

    try:
        if sys.getwindowsversion().build < 17763:
            return False
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", tint):
            return False
        alpha = max(1, round(max(0.0, min(1.0, opacity)) * 255))
        red, green, blue = (int(tint[index : index + 2], 16) for index in (1, 3, 5))
        gradient = (alpha << 24) | (blue << 16) | (green << 8) | red
        accent = AccentPolicy(4, 0, gradient, 0)
        data = WindowCompositionAttributeData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
        function = ctypes.windll.user32.SetWindowCompositionAttribute
        function.argtypes = (ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData))
        function.restype = ctypes.c_int
        hwnd = _root_hwnd(window.winfo_id())
        return bool(function(ctypes.c_void_p(hwnd), ctypes.byref(data)))
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError, tk.TclError):
        return False


def window_scale_factor(window) -> float:
    """返回 Windows 显示缩放比例，用于把屏幕像素换算为 Tk 窗口坐标。"""
    if sys.platform != "win32":
        return 1.0
    try:
        hwnd = _root_hwnd(window.winfo_id())
        user32 = ctypes.windll.user32
        user32.MonitorFromWindow.argtypes = (ctypes.c_void_p, ctypes.c_uint)
        user32.MonitorFromWindow.restype = ctypes.c_void_p
        monitor = user32.MonitorFromWindow(ctypes.c_void_p(hwnd), 2)  # MONITOR_DEFAULTTONEAREST
        scale = ctypes.c_int(100)
        function = ctypes.windll.shcore.GetScaleFactorForMonitor
        function.argtypes = (ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))
        function.restype = ctypes.c_long
        if monitor and function(monitor, ctypes.byref(scale)) == 0 and scale.value >= 100:
            return scale.value / 100
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError, tk.TclError):
        pass
    return 1.0


def prepare_no_activate(window) -> None:
    """尽量让提示窗置顶显示，但不成为键盘前台窗口。"""
    if sys.platform != "win32":
        window.attributes("-topmost", True)
        return
    try:
        user32 = ctypes.windll.user32
        hwnd = _root_hwnd(window.winfo_id())
        get_style = getattr(user32, "GetWindowLongPtrW", user32.GetWindowLongW)
        set_style = getattr(user32, "SetWindowLongPtrW", user32.SetWindowLongW)
        pointer_size = ctypes.sizeof(ctypes.c_void_p)
        long_ptr = ctypes.c_ssize_t if pointer_size == 8 else ctypes.c_long
        get_style.argtypes = (ctypes.c_void_p, ctypes.c_int)
        get_style.restype = long_ptr
        set_style.argtypes = (ctypes.c_void_p, ctypes.c_int, long_ptr)
        set_style.restype = long_ptr
        style = get_style(ctypes.c_void_p(hwnd), -20)  # GWL_EXSTYLE
        set_style(ctypes.c_void_p(hwnd), -20, style | 0x08000000)  # WS_EX_NOACTIVATE
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError):
        window.attributes("-topmost", True)


def show_no_activate(window, *, x: int | None = None, y: int | None = None, width: int | None = None, height: int | None = None) -> None:
    if sys.platform != "win32":
        window.deiconify()
        return
    try:
        # Keep Tk's window state in sync before issuing the no-activate Win32 show.
        window.deiconify()
        window.update_idletasks()
        hwnd = _root_hwnd(window.winfo_id())
        user32 = ctypes.windll.user32
        user32.ShowWindow.argtypes = (ctypes.c_void_p, ctypes.c_int)
        user32.ShowWindow.restype = ctypes.c_int
        user32.SetWindowPos.argtypes = (
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
            ctypes.c_int, ctypes.c_int, ctypes.c_uint,
        )
        user32.SetWindowPos.restype = ctypes.c_int
        user32.ShowWindow(ctypes.c_void_p(hwnd), 4)  # SW_SHOWNOACTIVATE
        user32.SetWindowPos(
            ctypes.c_void_p(hwnd), ctypes.c_void_p(-1),
            window.winfo_x() if x is None else x,
            window.winfo_y() if y is None else y,
            window.winfo_width() if width is None else width,
            window.winfo_height() if height is None else height,
            0x0010 | 0x0040,
        )
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError):
        window.deiconify()


def should_reduce_motion(*, user_static_mode: bool = False) -> bool:
    if user_static_mode:
        return True
    if sys.platform == "win32":
        try:
            enabled = ctypes.c_int(1)
            ok = ctypes.windll.user32.SystemParametersInfoW(0x1042, 0, ctypes.byref(enabled), 0)
            return bool(ok and not enabled.value)
        except (AttributeError, OSError, ValueError, ctypes.ArgumentError):
            return False
    return False
