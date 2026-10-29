"""Click-through, never-focused layer over every monitor.

Draws the optional gaze dot and the short flash around a newly focused window.
"""
from __future__ import annotations

import tkinter as tk

from . import win32
from .win32 import Rect

KEY = "#010203"  # painted pixels of this colour are fully transparent
ACCENT = "#4f8cff"


class Overlay:
    FLASH_MS = 260

    def __init__(self, root: tk.Tk, bounds: Rect):
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.configure(bg=KEY)
        self.top.attributes("-topmost", True)
        self.top.attributes("-transparentcolor", KEY)
        self.canvas = tk.Canvas(self.top, bg=KEY, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        self.bounds = bounds
        self._apply_geometry()
        self.top.update_idletasks()
        self.hwnd = win32.toplevel_hwnd(self.top.winfo_id())
        win32.make_click_through(self.hwnd)
        self._dot: tuple[int, int] | None = None
        self._flash_job: str | None = None

    def _apply_geometry(self) -> None:
        b = self.bounds
        self.top.geometry(f"{b.width}x{b.height}+{b.left}+{b.top}")

    def relayout(self, bounds: Rect) -> None:
        if bounds != self.bounds:
            self.bounds = bounds
            self._apply_geometry()

    def keep_on_top(self) -> None:
        win32.keep_topmost(self.hwnd)

    def show_dot(self, x: float, y: float, progress: float = 0.0) -> None:
        cx, cy = int(x - self.bounds.left), int(y - self.bounds.top)
        self.canvas.delete("dot")
        r = 10
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=ACCENT, width=3, tags="dot")
        if progress > 0:
            r2 = r + 6
            self.canvas.create_arc(cx - r2, cy - r2, cx + r2, cy + r2, start=90,
                                   extent=-359.9 * progress, style="arc", outline="#ffffff",
                                   width=2, tags="dot")
        self._dot = (cx, cy)

    def hide_dot(self) -> None:
        if self._dot is not None:
            self.canvas.delete("dot")
            self._dot = None

    def flash(self, rect: Rect) -> None:
        self.canvas.delete("flash")
        if self._flash_job:
            self.top.after_cancel(self._flash_job)
        x0, y0 = rect.left - self.bounds.left, rect.top - self.bounds.top
        x1, y1 = x0 + rect.width, y0 + rect.height
        self.canvas.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline=ACCENT, width=4,
                                     tags="flash")
        self._flash_job = self.top.after(self.FLASH_MS, self._end_flash)

    def _end_flash(self) -> None:
        self.canvas.delete("flash")
        self._flash_job = None

    def destroy(self) -> None:
        self.top.destroy()
