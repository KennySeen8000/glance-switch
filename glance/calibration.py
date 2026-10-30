"""Full-screen calibration: look at dots, fit the model, measure it, check it live."""
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
from .i18n import t
from .tracker import Tracker
from .win32 import Rect

log = logging.getLogger(__name__)

BG = "#0b0d12"
FG = "#e8ecf4"
MUTED = "#8a93a6"
ACCENT = "#4f8cff"
OK = "#3ccf8e"
WARN = "#f5a524"

# Validation targets as monitor fractions: deliberately off the calibration grid.
_VALIDATION_LAYOUT = ((0.5, 0.5), (0.2, 0.22), (0.8, 0.22), (0.8, 0.78), (0.2, 0.78),
                      (0.5, 0.2), (0.5, 0.8), (0.15, 0.5), (0.85, 0.5))


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


def validation_points(monitors: list[Rect], count: int) -> list[tuple[float, float]]:
    count = max(0, min(count, len(_VALIDATION_LAYOUT)))
    return [(mon.left + fx * mon.width, mon.top + fy * mon.height)
            for mon in sorted(monitors, key=lambda r: (r.left, r.top))
            for fx, fy in _VALIDATION_LAYOUT[:count]]


@dataclass
class CalibrationResult:
    data: gaze.CalibrationData
    model: gaze.GazeModel


@dataclass
class _Measured:
    target: tuple[float, float]
    features: np.ndarray


class CalibrationSession:
    MOVE_S = 0.35     # dot glides to the next target (smooth pursuit helps the eyes land)
    SETTLE_S = 0.6    # ignore the saccade and the first fixation wobble
    COLLECT_S = 0.9
    MIN_SAMPLES = 5
    TICK_MS = 16

    def __init__(self, root: tk.Tk, tracker: Tracker, monitors: list[Rect], layout: str,
                 cols: int, rows: int, validation: int,
                 on_done: Callable[[CalibrationResult | None], None]):
        self.tracker = tracker
        self.monitors = monitors
        self.layout = layout
        self.on_done = on_done
        self.virtual = Rect.union(monitors)
        self.primary = next((m for m in monitors if m.contains(0, 0)), monitors[0])
        self.cal_points = grid_points(monitors, cols, rows)
        self.val_points = validation_points(monitors, validation)

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

        self.state = "intro"  # intro -> calibrate -> validate -> review (or failed)
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
        self.measured: list[_Measured] = []
        self.targets: list[tuple[float, float]] = []
        self.index = 0
        self.retries: dict[int, int] = {}
        self.point_start = 0.0
        self.prev_point = self._center(self.primary)
        self.collected = 0
        self.model: gaze.GazeModel | None = None
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
            return t("face_ok"), OK
        if status == "no_camera":
            return t("face_no_camera"), WARN
        if status == "dark":
            return t("face_dark"), WARN
        if status == "starting":
            return t("face_starting"), MUTED
        return t("face_missing"), WARN

    # --- input -----------------------------------------------------------

    def _on_key(self, event) -> None:
        key = event.keysym.lower()
        if key == "escape":
            self._finish(None)
        elif self.state == "intro" and key in ("space", "return"):
            if self.tracker.status == "ok":
                self._begin("calibrate", self.cal_points)
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
        total = len(self.cal_points) + len(self.val_points)
        seconds = math.ceil(total * (self.SETTLE_S + self.COLLECT_S))
        self._text(cx, cy - 120, t("calib_title"), 30, weight="bold")
        self._text(cx, cy - 50, t("calib_intro"), 15, MUTED)
        self._text(cx, cy + 40, t("calib_length", points=total, seconds=seconds), 13, MUTED)
        self._text(cx, cy + 110, t("calib_start_keys"), 15)

    def _update_intro(self) -> None:
        self.canvas.delete("face")
        cx, cy = self._center(self.primary)
        line, color = self._face_line()
        self._text(cx, cy + 170, line, 13, color, tag="face")

    def _begin(self, state: str, targets: list[tuple[float, float]]) -> None:
        self.state = state
        self.canvas.delete("all")
        self.targets = targets
        self.index = 0
        self.retries = {}
        self.point_start = time.monotonic()
        if state == "validate":
            cx, cy = self._center(self.primary)
            self._text(cx, cy - 60, t("calib_validate_hint"), 15, MUTED, tag="hint")
            self.top.after(1400, lambda: self.canvas.delete("hint"))

    def _update_points(self, now: float) -> None:
        target = self.targets[self.index]
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

        color = ACCENT if self.state == "calibrate" else OK
        lx, ly = self._local(x, y)
        self.canvas.create_oval(lx - radius, ly - radius, lx + radius, ly + radius,
                                fill=color, outline="", tags="dot")
        self.canvas.create_oval(lx - 3, ly - 3, lx + 3, ly + 3, fill="#ffffff", outline="",
                                tags="dot")
        if progress > 0:
            r = 24
            self.canvas.create_arc(lx - r, ly - r, lx + r, ly + r, start=90,
                                   extent=-359.9 * progress, style="arc", outline=FG, width=2,
                                   tags="dot")
        self.canvas.delete("face")
        if self.tracker.status != "ok":
            line, color = self._face_line()
            cx, cy = self._center(self.primary)
            self._text(cx, cy, line, 14, color, tag="face")

        if t >= self.SETTLE_S + self.COLLECT_S:
            self._collect(target)

    def _point_features(self) -> np.ndarray | None:
        """Steady-fixation frames of the current point, outliers removed."""
        t0 = self.point_start + self.SETTLE_S
        rows = [s.features for s in self.tracker.window(t0, t0 + self.COLLECT_S)
                if s.features is not None and not s.blink]
        if len(rows) < self.MIN_SAMPLES:
            return None
        F = np.asarray(rows)
        med = np.median(F, axis=0)
        spread = np.median(np.abs(F - med), axis=0) + 1e-9
        keep = (np.abs(F - med) / spread < 4).all(axis=1)
        return F[keep] if keep.sum() >= self.MIN_SAMPLES else F

    def _collect(self, target) -> None:
        F = self._point_features()
        if F is None and self.retries.get(self.index, 0) < 1:
            self.retries[self.index] = 1
            self.point_start = time.monotonic()
            self.prev_point = target
            return
        if F is not None:
            if self.state == "calibrate":
                self.data.add(F, target, self.index)
                self.collected += 1
            else:
                self.measured.append(_Measured(target, F))
        self.prev_point = target
        self.index += 1
        self.point_start = time.monotonic()
        if self.index < len(self.targets):
            return
        if self.state == "calibrate":
            self._fit_calibration()
        else:
            self._finish_validation()

    def _fit_calibration(self) -> None:
        needed = max(6, int(len(self.cal_points) * 0.6))
        if self.collected < needed:
            self._fail(t("calib_too_few", measured=self.collected, total=len(self.cal_points)))
            return
        try:
            self.model = self.data.fit()
        except (ValueError, np.linalg.LinAlgError):
            log.exception("Calibration fit failed")
            self._fail(t("calib_fit_failed"))
            return
        log.info("Calibrated: %d points, cv error %.0f px, lambda %g",
                 self.collected, self.model.cv_error, self.model.lam)
        if self.val_points:
            self._begin("validate", self.val_points)
        else:
            self._show_review(self.model.cv_error, None)

    def _finish_validation(self) -> None:
        assert self.model is not None
        if len(self.measured) < max(2, len(self.val_points) // 2):
            # Not enough fresh points: fall back to the cross-validated estimate.
            self._show_review(self.model.cv_error, None)
            return
        errors = []
        axis = []
        for m in self.measured:
            pred = self.model.predict(m.features)
            d = pred - np.asarray(m.target)
            errors.append(float(np.mean(np.linalg.norm(d, axis=1))))
            axis.append(np.mean(np.abs(d), axis=0))
        measured = float(np.mean(errors))
        dx, dy = np.mean(axis, axis=0)
        log.info("Validation: %.0f px on %d fresh points (horizontal %.0f, vertical %.0f)",
                 measured, len(self.measured), dx, dy)
        # The fresh points are good training data too: refit with everything.
        base = len(self.cal_points)
        for i, m in enumerate(self.measured):
            self.data.add(m.features, m.target, base + i)
        self.data.validation_error = measured
        try:
            self.model = self.data.fit()
        except (ValueError, np.linalg.LinAlgError):
            log.warning("Refit with validation points failed; keeping the first model",
                        exc_info=True)
        self._show_review(measured, (dx, dy))

    def _show_review(self, err: float, axis: tuple[float, float] | None) -> None:
        self.result = CalibrationResult(self.data, self.model)
        self.state = "review"
        self.canvas.delete("all")
        cx, cy = self._center(self.primary)
        quality = t("quality_excellent" if err < 120 else "quality_good" if err < 200
                    else "quality_acceptable" if err < 300 else "quality_low")
        label = t("accuracy_measured" if axis else "accuracy_estimated")
        self._text(cx, cy - 100, t("calib_done"), 26, weight="bold")
        self._text(cx, cy - 50, f"{label} ≈ {err:.0f} px  ({quality})", 16,
                   OK if err < 200 else WARN)
        if axis:
            self._text(cx, cy - 18, f"horizontal ≈ {axis[0]:.0f} px  ·  vertical ≈ {axis[1]:.0f} px",
                       12, MUTED)
        self._text(cx, cy + 20, t("calib_follow"), 14, MUTED)
        self._text(cx, cy + 70, t("calib_review_keys"), 15)

    def _fail(self, reason: str) -> None:
        self.state = "failed"
        self.canvas.delete("all")
        cx, cy = self._center(self.primary)
        self._text(cx, cy - 40, t("calib_failed"), 24, WARN, "bold")
        self._text(cx, cy + 10, reason + "\n" + t("calib_failed_hint"),
                   14, MUTED)
        self._text(cx, cy + 80, t("calib_failed_keys"), 15)

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
            elif self.state in ("calibrate", "validate"):
                self._update_points(now)
            elif self.state == "review":
                self._update_review()
        except Exception:
            log.exception("Calibration tick failed")
            self._finish(None)
            return
        self._job = self.top.after(self.TICK_MS, self._tick)
