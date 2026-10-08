"""Platform glass support, adapting window-vibrancy's Windows FFI pattern.

The small ctypes translation is based on window-vibrancy 0.7.1
``src/windows.rs``; upstream and license are listed in THIRD_PARTY_NOTICES.md.
"""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
import sys
import tkinter as tk


@dataclass(frozen=True)
class MaterialReport:
    platform: str
    native_blur: bool
    description: str


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


def set_glass_opacity(window, opacity: float) -> bool:
    """调整 Acrylic tint 的 alpha，不把原生毛玻璃窗口改成 layered Tk 窗口。"""
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
        alpha = max(1, round(max(0.0, min(1.0, opacity)) * 255))
        accent = AccentPolicy(4, 0, (alpha << 24) | 0x00212A38, 0)
        data = WindowCompositionAttributeData(19, ctypes.cast(ctypes.pointer(accent), ctypes.c_void_p), ctypes.sizeof(accent))
        function = ctypes.windll.user32.SetWindowCompositionAttribute
        function.argtypes = (ctypes.c_void_p, ctypes.POINTER(WindowCompositionAttributeData))
        function.restype = ctypes.c_int
        hwnd = _root_hwnd(window.winfo_id())
        return bool(function(ctypes.c_void_p(hwnd), ctypes.byref(data)))
    except (AttributeError, OSError, ValueError, ctypes.ArgumentError, tk.TclError):
        return False


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
