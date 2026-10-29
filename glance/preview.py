"""Camera preview window with live diagnostics."""
from __future__ import annotations

import tkinter as tk
from typing import Callable

import cv2
from PIL import Image, ImageTk

from .features import LEFT_EYE, RIGHT_EYE
from .tracker import Tracker

WIDTH = 640


class Preview:
    REFRESH_MS = 66

    def __init__(self, root: tk.Tk, tracker: Tracker, status_lines: Callable[[], list[str]],
                 on_close: Callable[[], None]):
        self.tracker = tracker
        self.status_lines = status_lines
        self.on_close = on_close
        self.top = tk.Toplevel(root)
        self.top.title("Glance Switch · Vista previa")
        self.top.configure(bg="#0b0d12")
        self.top.resizable(False, False)
        self.top.protocol("WM_DELETE_WINDOW", self.close)
        self.image_label = tk.Label(self.top, bg="#000000", width=WIDTH, height=WIDTH * 9 // 16)
        self.image_label.pack(padx=8, pady=(8, 4))
        self.info = tk.Label(self.top, bg="#0b0d12", fg="#e8ecf4", font=("Consolas", 10),
                             justify="left", anchor="w")
        self.info.pack(fill="x", padx=10, pady=(0, 8))
        self._photo = None
        self._job: str | None = None
        self.tracker.want_frame = True
        self._refresh()

    def _refresh(self) -> None:
        packet = self.tracker.frame
        if packet is not None:
            frame, pts = packet
            frame = frame.copy()
            if pts is not None:
                for eye in (RIGHT_EYE, LEFT_EYE):
                    for i in eye[:4]:
                        cv2.circle(frame, (int(pts[i][0]), int(pts[i][1])), 2, (180, 180, 180), -1)
                    ix, iy = pts[eye[4]]
                    cv2.circle(frame, (int(ix), int(iy)), 4, (255, 140, 79), -1)
            h, w = frame.shape[:2]
            frame = cv2.resize(frame, (WIDTH, int(h * WIDTH / w)))
            frame = cv2.flip(frame, 1)  # mirror, like looking into a mirror
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            self._photo = ImageTk.PhotoImage(Image.fromarray(rgb))
            self.image_label.configure(image=self._photo, width=rgb.shape[1], height=rgb.shape[0])
        self.info.configure(text="\n".join(self.status_lines()))
        self._job = self.top.after(self.REFRESH_MS, self._refresh)

    def close(self) -> None:
        self.tracker.want_frame = False
        self.tracker.frame = None
        if self._job:
            self.top.after_cancel(self._job)
        self.top.destroy()
        self.on_close()
