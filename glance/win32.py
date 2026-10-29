"""Thin ctypes layer over the Win32 APIs Glance needs."""
from __future__ import annotations

import ctypes
import logging
from ctypes import wintypes as W
from dataclasses import dataclass
from typing import NamedTuple

log = logging.getLogger(__name__)

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
dwmapi = ctypes.WinDLL("dwmapi")


def _fn(dll, name, restype, *argtypes):
    f = getattr(dll, name)
    f.restype = restype
    f.argtypes = argtypes
    return f


GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_DISABLED = 0x08000000
WS_EX_TOPMOST = 0x00000008
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOOLWINDOW = 0x00000080
WS_EX_APPWINDOW = 0x00040000
WS_EX_LAYERED = 0x00080000
WS_EX_NOACTIVATE = 0x08000000
DWMWA_EXTENDED_FRAME_BOUNDS = 9
DWMWA_CLOAKED = 14
MONITOR_DEFAULTTONEAREST = 2
INPUT_MOUSE = 0
MOUSEEVENTF_MOVE = 0x0001
VK_LBUTTON, VK_RBUTTON, VK_MBUTTON = 0x01, 0x02, 0x04
HWND_TOPMOST = W.HWND(-1)
SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0010
WM_HOTKEY, WM_QUIT = 0x0312, 0x0012
MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
ERROR_ALREADY_EXISTS = 183
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000

# Desktop and shell surfaces: they hide what is behind them but never get focus.
SHELL_CLASSES = frozenset({
    "Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd",
    "NotifyIconOverflowWindow", "Windows.UI.Core.CoreWindow", "XamlExplorerHostIslandWindow",
})


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("mouseData", W.DWORD),
                ("dwFlags", W.DWORD), ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD),
                ("time", W.DWORD), ("dwExtraInfo", ctypes.c_size_t)]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [("uMsg", W.DWORD), ("wParamL", W.WORD), ("wParamH", W.WORD)]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT), ("ki", KEYBDINPUT), ("hi", HARDWAREINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", W.DWORD), ("u", _INPUTUNION)]


class LASTINPUTINFO(ctypes.Structure):
    _fields_ = [("cbSize", W.UINT), ("dwTime", W.DWORD)]


class MONITORINFO(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("rcMonitor", W.RECT), ("rcWork", W.RECT),
                ("dwFlags", W.DWORD)]


WNDENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
MONITORENUMPROC = ctypes.WINFUNCTYPE(W.BOOL, W.HMONITOR, W.HDC, ctypes.POINTER(W.RECT), W.LPARAM)

EnumWindows = _fn(user32, "EnumWindows", W.BOOL, WNDENUMPROC, W.LPARAM)
IsWindowVisible = _fn(user32, "IsWindowVisible", W.BOOL, W.HWND)
IsWindowEnabled = _fn(user32, "IsWindowEnabled", W.BOOL, W.HWND)
IsIconic = _fn(user32, "IsIconic", W.BOOL, W.HWND)
IsWindow = _fn(user32, "IsWindow", W.BOOL, W.HWND)
GetWindowTextLengthW = _fn(user32, "GetWindowTextLengthW", ctypes.c_int, W.HWND)
GetWindowTextW = _fn(user32, "GetWindowTextW", ctypes.c_int, W.HWND, W.LPWSTR, ctypes.c_int)
GetClassNameW = _fn(user32, "GetClassNameW", ctypes.c_int, W.HWND, W.LPWSTR, ctypes.c_int)
GetWindowLongW = _fn(user32, "GetWindowLongW", W.LONG, W.HWND, ctypes.c_int)
SetWindowLongW = _fn(user32, "SetWindowLongW", W.LONG, W.HWND, ctypes.c_int, W.LONG)
GetWindowRect = _fn(user32, "GetWindowRect", W.BOOL, W.HWND, ctypes.POINTER(W.RECT))
GetWindowThreadProcessId = _fn(user32, "GetWindowThreadProcessId", W.DWORD, W.HWND,
                               ctypes.POINTER(W.DWORD))
GetForegroundWindow = _fn(user32, "GetForegroundWindow", W.HWND)
SetForegroundWindow = _fn(user32, "SetForegroundWindow", W.BOOL, W.HWND)
BringWindowToTop = _fn(user32, "BringWindowToTop", W.BOOL, W.HWND)
AttachThreadInput = _fn(user32, "AttachThreadInput", W.BOOL, W.DWORD, W.DWORD, W.BOOL)
GetParent = _fn(user32, "GetParent", W.HWND, W.HWND)
GetCursorPos = _fn(user32, "GetCursorPos", W.BOOL, ctypes.POINTER(W.POINT))
GetAsyncKeyState = _fn(user32, "GetAsyncKeyState", W.SHORT, ctypes.c_int)
GetLastInputInfo = _fn(user32, "GetLastInputInfo", W.BOOL, ctypes.POINTER(LASTINPUTINFO))
SendInput = _fn(user32, "SendInput", W.UINT, W.UINT, ctypes.POINTER(INPUT), ctypes.c_int)
SetWindowPos = _fn(user32, "SetWindowPos", W.BOOL, W.HWND, W.HWND, ctypes.c_int, ctypes.c_int,
                   ctypes.c_int, ctypes.c_int, W.UINT)
MonitorFromWindow = _fn(user32, "MonitorFromWindow", W.HMONITOR, W.HWND, W.DWORD)
GetMonitorInfoW = _fn(user32, "GetMonitorInfoW", W.BOOL, W.HMONITOR, ctypes.POINTER(MONITORINFO))
EnumDisplayMonitors = _fn(user32, "EnumDisplayMonitors", W.BOOL, W.HDC, ctypes.POINTER(W.RECT),
                          MONITORENUMPROC, W.LPARAM)
RegisterHotKey = _fn(user32, "RegisterHotKey", W.BOOL, W.HWND, ctypes.c_int, W.UINT, W.UINT)
UnregisterHotKey = _fn(user32, "UnregisterHotKey", W.BOOL, W.HWND, ctypes.c_int)
GetMessageW = _fn(user32, "GetMessageW", W.BOOL, ctypes.POINTER(W.MSG), W.HWND, W.UINT, W.UINT)
PostThreadMessageW = _fn(user32, "PostThreadMessageW", W.BOOL, W.DWORD, W.UINT, W.WPARAM,
                         W.LPARAM)
MessageBoxW = _fn(user32, "MessageBoxW", ctypes.c_int, W.HWND, W.LPCWSTR, W.LPCWSTR, W.UINT)
GetCurrentThreadId = _fn(kernel32, "GetCurrentThreadId", W.DWORD)
GetCurrentProcessId = _fn(kernel32, "GetCurrentProcessId", W.DWORD)
GetTickCount = _fn(kernel32, "GetTickCount", W.DWORD)
CreateMutexW = _fn(kernel32, "CreateMutexW", W.HANDLE, W.LPVOID, W.BOOL, W.LPCWSTR)
OpenProcess = _fn(kernel32, "OpenProcess", W.HANDLE, W.DWORD, W.BOOL, W.DWORD)
CloseHandle = _fn(kernel32, "CloseHandle", W.BOOL, W.HANDLE)
QueryFullProcessImageNameW = _fn(kernel32, "QueryFullProcessImageNameW", W.BOOL, W.HANDLE,
                                 W.DWORD, W.LPWSTR, ctypes.POINTER(W.DWORD))
DwmGetWindowAttribute = _fn(dwmapi, "DwmGetWindowAttribute", W.LONG, W.HWND, W.DWORD,
                            W.LPVOID, W.DWORD)


class Rect(NamedTuple):
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top

    def contains(self, x: float, y: float) -> bool:
        return self.left <= x < self.right and self.top <= y < self.bottom

    @classmethod
    def of(cls, r: W.RECT) -> "Rect":
        return cls(r.left, r.top, r.right, r.bottom)

    @classmethod
    def union(cls, rects) -> "Rect":
        rects = list(rects)
        return cls(min(r.left for r in rects), min(r.top for r in rects),
                   max(r.right for r in rects), max(r.bottom for r in rects))


@dataclass(frozen=True)
class Window:
    hwnd: int
    rect: Rect
    title: str
    cls: str
    pid: int
    # False for windows that only hide what is behind them (taskbar, desktop...).
    target: bool


# --- process setup ---------------------------------------------------------

def set_dpi_awareness() -> None:
    """Work in physical pixels so window rects, cursor and Tk agree."""
    try:
        if user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):  # PER_MONITOR_AWARE_V2
            return
    except AttributeError:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except (AttributeError, OSError):
        user32.SetProcessDPIAware()


_mutex = None


def acquire_single_instance(name: str) -> bool:
    global _mutex
    _mutex = CreateMutexW(None, False, f"Local\\{name}.SingleInstance")
    return ctypes.get_last_error() != ERROR_ALREADY_EXISTS


def message_box(text: str, title: str) -> None:
    MessageBoxW(None, text, title, 0x40)  # MB_ICONINFORMATION


# --- monitors --------------------------------------------------------------

def monitors() -> list[Rect]:
    found: list[Rect] = []

    @MONITORENUMPROC
    def callback(hmon, _hdc, _rect, _data):
        info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
        if GetMonitorInfoW(hmon, ctypes.byref(info)):
            found.append(Rect.of(info.rcMonitor))
        return True

    EnumDisplayMonitors(None, None, callback, 0)
    return sorted(found) or [Rect(0, 0, 1920, 1080)]


def layout_signature(rects: list[Rect]) -> str:
    return ";".join(f"{r.left},{r.top},{r.width}x{r.height}" for r in sorted(rects))


def monitor_rect_of(hwnd: int) -> Rect | None:
    hmon = MonitorFromWindow(hwnd, MONITOR_DEFAULTTONEAREST)
    info = MONITORINFO(cbSize=ctypes.sizeof(MONITORINFO))
    if not hmon or not GetMonitorInfoW(hmon, ctypes.byref(info)):
        return None
    return Rect.of(info.rcMonitor)


# --- windows ---------------------------------------------------------------

def window_text(hwnd: int) -> str:
    length = GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""
    buf = ctypes.create_unicode_buffer(length + 1)
    GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def class_name(hwnd: int) -> str:
    buf = ctypes.create_unicode_buffer(256)
    GetClassNameW(hwnd, buf, 256)
    return buf.value


def window_rect(hwnd: int) -> Rect | None:
    """Visible frame bounds (without the invisible resize borders of Win10)."""
    r = W.RECT()
    if DwmGetWindowAttribute(hwnd, DWMWA_EXTENDED_FRAME_BOUNDS, ctypes.byref(r),
                             ctypes.sizeof(r)) != 0:
        if not GetWindowRect(hwnd, ctypes.byref(r)):
            return None
    rect = Rect.of(r)
    return rect if rect.width > 0 and rect.height > 0 else None


def is_cloaked(hwnd: int) -> bool:
    """Hidden by DWM: other virtual desktops, suspended UWP apps..."""
    cloaked = W.DWORD()
    hr = DwmGetWindowAttribute(hwnd, DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked))
    return hr == 0 and cloaked.value != 0


def window_pid(hwnd: int) -> int:
    pid = W.DWORD()
    GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def process_name(pid: int) -> str:
    handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = W.DWORD(1024)
        buf = ctypes.create_unicode_buffer(size.value)
        if QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value.rsplit("\\", 1)[-1]
        return ""
    finally:
        CloseHandle(handle)


def _inspect(hwnd: int, own_pid: int) -> Window | None:
    if not IsWindowVisible(hwnd) or IsIconic(hwnd) or is_cloaked(hwnd):
        return None
    ex = GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    if ex & WS_EX_TRANSPARENT:
        return None  # click-through overlays do not hide anything
    rect = window_rect(hwnd)
    if rect is None:
        return None
    title = window_text(hwnd)
    cls = class_name(hwnd)
    pid = window_pid(hwnd)
    tool = bool(ex & WS_EX_TOOLWINDOW) and not ex & WS_EX_APPWINDOW
    target = (
        pid != own_pid
        and bool(title)
        and cls not in SHELL_CLASSES
        and not tool
        and not ex & WS_EX_NOACTIVATE
        and bool(IsWindowEnabled(hwnd))
        and rect.width >= 120
        and rect.height >= 80
    )
    return Window(hwnd, rect, title, cls, pid, target)


def list_windows(own_pid: int) -> list[Window]:
    """Visible top-level windows, topmost first (EnumWindows is z-ordered)."""
    found: list[Window] = []

    @WNDENUMPROC
    def callback(hwnd, _):
        try:
            win = _inspect(hwnd, own_pid)
        except OSError:
            win = None
        if win is not None:
            found.append(win)
        return True

    EnumWindows(callback, 0)
    return found


def hit_test(windows: list[Window], x: float, y: float) -> Window | None:
    for win in windows:
        if win.rect.contains(x, y):
            return win
    return None


def foreground() -> int | None:
    return GetForegroundWindow() or None


def is_fullscreen(hwnd: int | None) -> bool:
    if not hwnd or class_name(hwnd) in SHELL_CLASSES:
        return False
    rect, mon = window_rect(hwnd), monitor_rect_of(hwnd)
    return rect is not None and mon is not None and rect == mon


def _poke_input() -> None:
    """Inject a zero-length mouse move.

    Windows only lets the process that received the last input event change
    the foreground window; this makes that process us.
    """
    inp = INPUT(type=INPUT_MOUSE)
    inp.u.mi = MOUSEINPUT(0, 0, 0, MOUSEEVENTF_MOVE, 0, 0)
    SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def activate(hwnd: int) -> bool:
    """Give `hwnd` keyboard focus without clicking on it."""
    if not IsWindow(hwnd) or IsIconic(hwnd):
        return False
    if GetForegroundWindow() == hwnd:
        return True
    _poke_input()
    SetForegroundWindow(hwnd)
    if GetForegroundWindow() == hwnd:
        return True
    # Fallback: share the input state of the current foreground thread.
    fg = GetForegroundWindow()
    me = GetCurrentThreadId()
    other = GetWindowThreadProcessId(fg, None) if fg else 0
    attached = bool(other and other != me and AttachThreadInput(me, other, True))
    try:
        BringWindowToTop(hwnd)
        SetForegroundWindow(hwnd)
    finally:
        if attached:
            AttachThreadInput(me, other, False)
    ok = GetForegroundWindow() == hwnd
    if not ok:
        log.debug("Could not focus %s (%s)", hwnd, window_text(hwnd))
    return ok


# --- input state -----------------------------------------------------------

def cursor_pos() -> tuple[int, int]:
    p = W.POINT()
    GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def last_input_tick() -> int:
    info = LASTINPUTINFO(cbSize=ctypes.sizeof(LASTINPUTINFO))
    GetLastInputInfo(ctypes.byref(info))
    return info.dwTime


def mouse_buttons() -> int:
    mask = 0
    for bit, vk in enumerate((VK_LBUTTON, VK_RBUTTON, VK_MBUTTON)):
        if GetAsyncKeyState(vk) & 0x8000:
            mask |= 1 << bit
    return mask


# --- our own Tk windows ----------------------------------------------------

def toplevel_hwnd(tk_widget_id: int) -> int:
    """Tk's winfo_id() is a child; the real top-level window is its parent."""
    return GetParent(tk_widget_id) or tk_widget_id


def make_click_through(hwnd: int) -> None:
    ex = GetWindowLongW(hwnd, GWL_EXSTYLE) & 0xFFFFFFFF
    ex |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
    SetWindowLongW(hwnd, GWL_EXSTYLE, ctypes.c_long(ex).value)


def keep_topmost(hwnd: int) -> None:
    SetWindowPos(hwnd, HWND_TOPMOST, 0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE)
