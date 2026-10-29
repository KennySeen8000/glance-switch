"""Full-screen calibration: look at dots, fit the model, check it live."""
from __future__ import annotations

import logging
import math
import time
import tkinter as tk
from dataclasses import dataclass
from typing import Callable

import numpy as np

from . import model as gaze
from . import win32
from .filters import OneEuro
from .tracker import Tracker
from .win32 import Rect

log = logging.getLogger(__name__)

BG = "#0b0d12"
FG = "#e8ecf4"
MUTED = "#8a93a6"
ACCENT = "#4f8cff"
OK = "#3ccf8e"
WARN = "#f5a524"


def grid_points(monitors: list[Rect], cols: int, rows: int,
                margin: float = 0.08) -> list[tuple[float, float]]:
    """Targets on each monitor, in a snake order so the eyes travel little."""
    points = []
    for mon in sorted(monitors, key=lambda r: (r.left, r.top)):
        for r in range(rows):
            order = range(cols) if r % 2 == 0 else reversed(range(cols))
            for c in order:
                fx = margin + (1 - 2 * margin) * (c / (cols - 1) if cols > 1 else 0.5)
                fy = margin + (1 - 2 * margin) * (r / (rows - 1) if rows > 1 else 0.5)
                points.append((mon.left + fx * mon.width, mon.top + fy * mon.height))
    return points


@dataclass
class CalibrationResult:
    data: gaze.CalibrationData
    model: gaze.GazeModel


class CalibrationSession:
    MOVE_S = 0.35     # dot glides to the next target (smooth pursuit helps the eyes land)
    SETTLE_S = 0.6    # ignore the saccade and the first fixation wobble
    COLLECT_S = 0.9
    MIN_SAMPLES = 5
    TICK_MS = 16

    def __init__(self, root: tk.Tk, tracker: Tracker, monitors: list[Rect], layout: str,
                 cols: int, rows: int, on_done: Callable[[CalibrationResult | None], None]):
        self.tracker = tracker
        self.monitors = monitors
        self.layout = layout
        self.on_done = on_done
        self.virtual = Rect.union(monitors)
        self.primary = next((m for m in monitors if m.contains(0, 0)), monitors[0])
        self.points = grid_points(monitors, cols, rows)

        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.attributes("-topmost", True)
        self.top.configure(bg=BG, cursor="none")
        v = self.virtual
        self.top.geometry(f"{v.width}x{v.height}+{v.left}+{v.top}")
        self.canvas = tk.Canvas(self.top, bg=BG, highlightthickness=0, bd=0)
        self.canvas.pack(fill="both", expand=True)
        for key in ("<Escape>", "<space>", "<Return>", "<KeyPress-r>", "<KeyPress-R>"):
            self.top.bind(key, self._on_key)

        self.state = "intro"
        self._job: str | None = None
        self._finished = False
        self._reset_run()

    # --- lifecycle -------------------------------------------------------

    def start(self) -> None:
        self.top.update_idletasks()
        self.top.focus_force()
        win32.activate(win32.toplevel_hwnd(self.top.winfo_id()))
        self.top.focus_set()
        self._draw_intro()
        self._tick()

    def _reset_run(self) -> None:
        self.data = gaze.CalibrationData.empty(self.layout)
        self.index = 0
        self.retries: dict[int, int] = {}
        self.point_start = 0.0
        self.prev_point = self._center(self.primary)
        self.collected = 0
        self.result: CalibrationResult | None = None
        self.filter = OneEuro()

    def _finish(self, result: CalibrationResult | None) -> None:
        if self._finished:
            return
        self._finished = True
        if self._job:
            self.top.after_cancel(self._job)
        self.top.destroy()
        self.on_done(result)

    # --- helpers ---------------------------------------------------------

    @staticmethod
    def _center(r: Rect) -> tuple[float, float]:
        return r.left + r.width / 2, r.top + r.height / 2

    def _local(self, x: float, y: float) -> tuple[float, float]:
        return x - self.virtual.left, y - self.virtual.top

    def _text(self, x, y, text, size=16, color=FG, weight="normal", tag="ui"):
        lx, ly = self._local(x, y)
        self.canvas.create_text(lx, ly, text=text, fill=color, font=("Segoe UI", size, weight),
                                tags=tag, justify="center")

    def _face_line(self) -> tuple[str, str]:
        status = self.tracker.status
        if status == "ok":
            return "● Cara detectada", OK
        if status == "no_camera":
            return "● No se puede abrir la cámara", WARN
        if status == "dark":
            return "● La cámara se ve negra: ¿está tapada la tapa de privacidad?", WARN
        if status == "starting":
            return "● Iniciando cámara…", MUTED
        return "● No se detecta tu cara: colócate frente a la cámara", WARN

    # --- input -----------------------------------------------------------

    def _on_key(self, event) -> None:
        key = event.keysym.lower()
        if key == "escape":
            self._finish(None)
        elif self.state == "intro" and key in ("space", "return"):
            if self.tracker.status == "ok":
                self._begin_points()
        elif self.state in ("review", "failed") and key == "r":
            self._reset_run()
            self.state = "intro"
            self._draw_intro()
        elif self.state == "review" and key in ("space", "return"):
            self._finish(self.result)

    # --- screens ---------------------------------------------------------

    def _draw_intro(self) -> None:
        self.canvas.delete("all")
        cx, cy = self._center(self.primary)
        self._text(cx, cy - 120, "Calibración", 30, weight="bold")
        self._text(cx, cy - 50,
                   "Sigue con la mirada el punto azul y míralo fijamente hasta que se cierre.\n"
                   "Mueve la cabeza con naturalidad, como cuando trabajas.", 15, MUTED)
        self._text(cx, cy + 40, f"{len(self.points)} puntos · unos "
                   f"{math.ceil(len(self.points) * (self.SETTLE_S + self.COLLECT_S))} segundos",
                   13, MUTED)
        self._text(cx, cy + 110, "Pulsa  Espacio  para empezar  ·  Esc  para cancelar", 15)

    def _update_intro(self) -> None:
        self.canvas.delete("face")
        cx, cy = self._center(self.primary)
        line, color = self._face_line()
        self._text(cx, cy + 170, line, 13, color, tag="face")

    def _begin_points(self) -> None:
        self.state = "points"
        self.canvas.delete("all")
        self.index = 0
        self.point_start = time.monotonic()

    def _update_points(self, now: float) -> None:
        target = self.points[self.index]
        t = now - self.point_start
        self.canvas.delete("dot")

        if t < self.MOVE_S:
            k = t / self.MOVE_S
            k = k * k * (3 - 2 * k)  # smoothstep
            x = self.prev_point[0] + (target[0] - self.prev_point[0]) * k
            y = self.prev_point[1] + (target[1] - self.prev_point[1]) * k
            radius, progress = 16, 0.0
        else:
            x, y = target
            hold = max(0.0, t - self.SETTLE_S)
            progress = min(1.0, hold / self.COLLECT_S)
            radius = 16 - 9 * progress

        lx, ly = self._local(x, y)
        self.canvas.create_oval(lx - radius, ly - radius, lx + radius, ly + radius,
                                fill=ACCENT, outline="", tags="dot")
        self.canvas.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill="#ffffff", outline="",
                                tags="dot")
        if progress > 0:
            r = 24
            self.canvas.create_arc(lx - r, ly - r, lx + r, ly + r, start=90,
                                   extent=-359.9 * progress, style="arc", outline=FG, width=2,
                                   tags="dot")
        if self.tracker.status != "ok":
            line, color = self._face_line()
            cx, cy = self._center(self.primary)
            self.canvas.delete("face")
            self._text(cx, cy, line, 14, color, tag="face")
        else:
            self.canvas.delete("face")

        if t >= self.SETTLE_S + self.COLLECT_S:
            self._collect(target)

    def _collect(self, target) -> None:
        t0 = self.point_start + self.SETTLE_S
        rows = [s.features for s in self.tracker.window(t0, t0 + self.COLLECT_S)
                if s.features is not None and not s.blink]
        if len(rows) >= self.MIN_SAMPLES:
            F = np.asarray(rows)
            # Drop the outlying frames (late saccades) before keeping the point.
            med = np.median(F, axis=0)
            spread = np.median(np.abs(F - med), axis=0) + 1e-9
            keep = (np.abs(F - med) / spread < 4).all(axis=1)
            if keep.sum() >= self.MIN_SAMPLES:
                F = F[keep]
            self.data.add(F, target, self.index)
            self.collected += 1
        elif self.retries.get(self.index, 0) < 1:
            self.retries[self.index] = 1
            self.point_start = time.monotonic()
            self.prev_point = target
            return
        self.prev_point = target
        self.index += 1
        self.point_start = time.monotonic()
        if self.index >= len(self.points):
            self._fit()

    def _fit(self) -> None:
        needed = max(6, int(len(self.points) * 0.6))
        if self.collected < needed:
            self._fail(f"Solo se pudieron medir {self.collected} de {len(self.points)} puntos.")
            return
        try:
            fitted = self.data.fit()
        except (ValueError, np.linalg.LinAlgError):
            log.exception("Calibration fit failed")
            self._fail("No se pudo calcular el modelo de mirada.")
            return
        self.result = CalibrationResult(self.data, fitted)
        log.info("Calibrated: %d points, cv error %.0f px, lambda %g",
                 self.collected, fitted.cv_error, fitted.lam)
        self.state = "review"
        self.canvas.delete("all")
        cx, cy = self._center(self.primary)
        err = fitted.cv_error
        quality = ("excelente" if err < 120 else "buena" if err < 200
                   else "aceptable" if err < 300 else "baja")
        self._text(cx, cy - 90, "Calibración completada", 26, weight="bold")
        self._text(cx, cy - 40, f"Precisión estimada ≈ {err:.0f} px  ({quality})", 16,
                   OK if err < 200 else WARN)
        self._text(cx, cy + 10, "Mira por la pantalla: el círculo sigue tu mirada.", 14, MUTED)
        self._text(cx, cy + 60, "Espacio  guardar   ·   R  repetir   ·   Esc  cancelar", 15)

    def _fail(self, reason: str) -> None:
        self.state = "failed"
        self.canvas.delete("all")
        cx, cy = self._center(self.primary)
        self._text(cx, cy - 40, "La calibración no salió bien", 24, WARN, "bold")
        self._text(cx, cy + 10, reason + "\nComprueba la luz y que la cámara te vea de frente.",
                   14, MUTED)
        self._text(cx, cy + 80, "R  repetir   ·   Esc  cancelar", 15)

    def _update_review(self) -> None:
        self.canvas.delete("dot")
        sample = self.tracker.latest()
        if self.result is None or sample is None or sample.features is None:
            return
        if time.monotonic() - sample.t > 0.4:
            return
        x, y = self.filter(sample.t, self.result.model.predict(sample.features))
        v = self.virtual
        x = min(max(x, v.left), v.right - 1)
        y = min(max(y, v.top), v.bottom - 1)
        lx, ly = self._local(x, y)
        r = 22
        self.canvas.create_oval(lx - r, ly - r, lx + r, ly + r, outline=ACCENT, width=3, tags="dot")

    # --- loop ------------------------------------------------------------

    def _tick(self) -> None:
        if self._finished:
            return
        try:
            now = time.monotonic()
            if self.state == "intro":
                self._update_intro()
            elif self.state == "points":
                self._update_points(now)
            elif self.state == "review":
                self._update_review()
        except Exception:
            log.exception("Calibration tick failed")
            self._finish(None)
            return
        self._job = self.top.after(self.TICK_MS, self._tick)
