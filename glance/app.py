"""Wires tracking, the gaze model and window focus together."""
from __future__ import annotations

import logging
import math
import os
import queue
import time
import tkinter as tk

import numpy as np

from . import DISPLAY_NAME, startup, win32
from .activity import Activity
from .calibration import CalibrationResult, CalibrationSession
from .config import Settings, data_dir, face_model_bytes
from .decider import Decider
from .filters import OneEuro
from .hotkeys import HotkeyThread
from .model import CalibrationData, GazeModel
from .overlay import Overlay
from .preview import Preview
from .tracker import Tracker
from .tray import Tray
from .win32 import Rect, Window

log = logging.getLogger(__name__)

STALE_SAMPLE_S = 0.4
WINDOW_CACHE_S = 0.25
LAYOUT_CHECK_S = 2.0
REFIT_EVERY_CLICKS = 5
# Ring of offsets (unit circle) used to vote for the window under the gaze.
_RING = [(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, 8, endpoint=False)]


def vote(windows: list[Window], x: float, y: float, radius: float) -> tuple[Window | None, float]:
    """Pick the window under a fuzzy gaze point and how sure we are of it.

    The centre counts double; hits on non-target surfaces (taskbar, desktop)
    vote for "nothing".
    """
    weights: dict[int | None, float] = {}
    by_hwnd: dict[int, Window] = {}
    samples = [((x, y), 2.0)] + [((x + dx * radius, y + dy * radius), 1.0) for dx, dy in _RING]
    for (px, py), w in samples:
        win = win32.hit_test(windows, px, py)
        key = win.hwnd if win is not None and win.target else None
        if key is not None:
            by_hwnd[key] = win
        weights[key] = weights.get(key, 0.0) + w
    total = sum(weights.values())
    best = max(weights, key=weights.get)
    return (by_hwnd.get(best) if best is not None else None), weights[best] / total


class App:
    TICK_MS = 33

    def __init__(self):
        self.settings = Settings.load()
        self.root = tk.Tk()
        self.root.withdraw()
        self.commands: queue.Queue[str] = queue.Queue()
        self.own_pid = os.getpid()

        self.monitors = win32.monitors()
        self.layout = win32.layout_signature(self.monitors)
        self.virtual = Rect.union(self.monitors)

        self.calib_path = data_dir() / "calibration.json"
        self.data: CalibrationData | None = CalibrationData.load(self.calib_path)
        self.model: GazeModel | None = None
        if self.data is not None:
            try:
                self.model = self.data.fit()
            except (ValueError, np.linalg.LinAlgError):
                log.warning("Stored calibration is unusable", exc_info=True)
                self.data = None

        self.tracker = Tracker(self.settings, face_model_bytes())
        self.activity = Activity()
        self.decider = Decider()
        self._apply_timing()
        self.filter = OneEuro()
        self.overlay = Overlay(self.root, self.virtual)
        self.tray = Tray(self)
        self.hotkeys = HotkeyThread(
            {self.settings.hotkey_toggle: "toggle", self.settings.hotkey_calibrate: "calibrate"},
            self.post,
        )

        self.preview: Preview | None = None
        self.calibration: CalibrationSession | None = None
        self.gaze: np.ndarray | None = None
        self.candidate: Window | None = None
        self.confidence = 0.0
        self.block_reason = ""
        self.switches = 0
        self._clicks_since_fit = 0
        self._windows: list[Window] = []
        self._windows_at = 0.0
        self._layout_at = 0.0
        self._topmost_at = 0.0
        self._quitting = False

    # --- lifecycle -------------------------------------------------------

    def run(self) -> None:
        self.tracker.start()
        self.hotkeys.start()
        self.tray.start()
        if self.model is None:
            self.root.after(1500, self._first_run)
        elif self.data.layout != self.layout:
            self.root.after(1500, lambda: self.tray.notify(
                "Tus pantallas han cambiado. Recalibra para mejor precisión."))
        self.root.after(self.TICK_MS, self._tick)
        log.info("%s running (%d monitor(s): %s)", DISPLAY_NAME, len(self.monitors), self.layout)
        self.root.mainloop()
        self.tracker.join(timeout=2.0)  # lets it release the camera
        self.root.destroy()

    def _first_run(self) -> None:
        self.tray.notify("Vamos a calibrar la mirada. Tarda unos 20 segundos.")
        self.start_calibration()

    def post(self, command: str) -> None:
        """Thread-safe: tray and hotkey threads talk to the UI thread through here."""
        self.commands.put(command)

    def quit(self) -> None:
        if self._quitting:
            return
        self._quitting = True
        log.info("Quitting")
        self.tracker.stop()
        self.hotkeys.stop()
        self.tray.stop()
        self.root.quit()

    # --- commands --------------------------------------------------------

    def _drain_commands(self) -> None:
        while True:
            try:
                command = self.commands.get_nowait()
            except queue.Empty:
                return
            try:
                self._run_command(command)
            except Exception:
                log.exception("Command %r failed", command)
            self.tray.refresh_menu()

    def _run_command(self, command: str) -> None:
        s = self.settings
        if command == "toggle":
            s.enabled = not s.enabled
            s.save()
            self.decider.reset()
        elif command == "calibrate":
            self.start_calibration()
        elif command == "preview":
            if self.preview is not None:
                self.preview.close()
            else:
                self.preview = Preview(self.root, self.tracker, self.status_lines,
                                       self._preview_closed)
        elif command.startswith("toggle:"):
            attr = command.split(":", 1)[1]
            setattr(s, attr, not getattr(s, attr))
            s.save()
        elif command.startswith("dwell:"):
            s.dwell_ms = int(command.split(":", 1)[1])
            s.save()
            self._apply_timing()
        elif command == "startup":
            startup.set_enabled(not startup.is_enabled())
        elif command == "open_folder":
            os.startfile(data_dir())
        elif command == "quit":
            self.quit()

    def _apply_timing(self) -> None:
        s = self.settings
        self.decider.dwell_s = s.dwell_ms / 1000
        self.decider.cooldown_s = s.cooldown_ms / 1000
        self.decider.min_confidence = s.min_confidence

    def _preview_closed(self) -> None:
        self.preview = None
        self.tray.refresh_menu()

    # --- calibration -----------------------------------------------------

    def start_calibration(self) -> None:
        if self.calibration is not None:
            return
        previous = win32.foreground()
        self.overlay.hide_dot()
        self.decider.reset()
        s = self.settings

        def done(result: CalibrationResult | None) -> None:
            self.calibration = None
            if result is not None:
                self.data, self.model = result.data, result.model
                self.data.save(self.calib_path)
                self.filter.reset()
                self.tray.notify(f"Calibración guardada (precisión ≈ {result.model.cv_error:.0f} px).")
            if previous:
                self.activity.ignore_injected(time.monotonic())
                win32.activate(previous)

        self.calibration = CalibrationSession(self.root, self.tracker, self.monitors, self.layout,
                                              s.calibration_cols, s.calibration_rows, done)
        self.calibration.start()

    def _learn_from_clicks(self, clicks: list[tuple[int, int]], now: float) -> None:
        """A click is a free calibration sample: people look where they click."""
        if self.model is None or self.data is None:
            return
        tolerance = max(250.0, 3 * (self.model.cv_error if self.model.cv_error == self.model.cv_error
                                    else 150.0))
        for point in clicks:
            f = self.tracker.median_features(now - 0.35, now - 0.05)
            if f is None:
                continue
            predicted = self.model.predict(f)
            if np.hypot(*(predicted - point)) > tolerance:
                continue  # probably clicked without looking
            self.data.add_click(f, point)
            self._clicks_since_fit += 1
        if self._clicks_since_fit >= REFIT_EVERY_CLICKS:
            self._clicks_since_fit = 0
            try:
                self.model = self.data.fit()
                self.data.save(self.calib_path)
                log.info("Refit with %d click samples, cv error %.0f px",
                         self.data.click_count, self.model.cv_error)
            except (ValueError, np.linalg.LinAlgError):
                log.warning("Refit from clicks failed", exc_info=True)

    # --- main loop -------------------------------------------------------

    def _tick(self) -> None:
        if self._quitting:
            return
        try:
            self._step()
        except Exception:
            log.exception("Tick failed")
        self.root.after(self.TICK_MS, self._tick)

    def _step(self) -> None:
        now = time.monotonic()
        self._drain_commands()
        if self._quitting:
            return
        self._check_layout(now)
        clicks = self.activity.poll(now)
        self._update_tray()
        if self.calibration is not None:
            return

        self.gaze = self._estimate_gaze(now)
        if clicks and self.settings.learn_from_clicks:
            self._learn_from_clicks(clicks, now)

        if self.gaze is None or not self.settings.enabled:
            self.candidate, self.confidence = None, 0.0
            self.decider.reset()
            self.overlay.hide_dot()
            return

        x, y = self.gaze
        windows = self._current_windows(now)
        self.candidate, self.confidence = vote(windows, x, y, self._vote_radius())
        self.block_reason = self._blocked_reason(now)
        cand = self.candidate.hwnd if self.candidate and not self.block_reason else None
        target = self.decider.update(now, cand, self.confidence, win32.foreground())

        if self.settings.show_gaze_dot or self.preview is not None:
            self.overlay.show_dot(x, y, self.decider.progress(now))
        else:
            self.overlay.hide_dot()

        if target is not None:
            self._switch_to(target, now)

    def _estimate_gaze(self, now: float) -> np.ndarray | None:
        sample = self.tracker.latest()
        if self.model is None or sample is None or sample.features is None:
            return None
        if now - sample.t > STALE_SAMPLE_S:
            return None
        raw = self.model.predict(sample.features)
        v = self.virtual
        raw = np.clip(raw, (v.left, v.top), (v.right - 1, v.bottom - 1))
        return self.filter(sample.t, raw)

    def _vote_radius(self) -> float:
        err = self.model.cv_error if self.model else float("nan")
        return 60.0 if err != err else min(160.0, max(40.0, 0.6 * err))

    def _current_windows(self, now: float) -> list[Window]:
        if now - self._windows_at > WINDOW_CACHE_S:
            self._windows = win32.list_windows(self.own_pid)
            self._windows_at = now
        return self._windows

    def _blocked_reason(self, now: float) -> str:
        s, a = self.settings, self.activity
        if a.buttons_down:
            return "botón del ratón pulsado"
        if now - a.last_mouse < s.mouse_grace_ms / 1000:
            return "usando el ratón"
        if now - a.last_key < s.typing_grace_ms / 1000:
            return "escribiendo"
        if s.pause_on_fullscreen and win32.is_fullscreen(win32.foreground()):
            return "app a pantalla completa"
        return ""

    def _switch_to(self, hwnd: int, now: float) -> None:
        win = next((w for w in self._windows if w.hwnd == hwnd), None)
        self.activity.ignore_injected(now)
        if win32.activate(hwnd):
            self.switches += 1
            log.debug("Focused %r", win.title if win else hwnd)
            if win is not None and self.settings.flash_on_switch:
                self.overlay.flash(win.rect)
            self._windows_at = 0.0  # z-order changed

    def _check_layout(self, now: float) -> None:
        if now - self._topmost_at > 3.0:
            self._topmost_at = now
            self.overlay.keep_on_top()
        if now - self._layout_at < LAYOUT_CHECK_S:
            return
        self._layout_at = now
        monitors = win32.monitors()
        layout = win32.layout_signature(monitors)
        if layout == self.layout:
            return
        log.info("Monitor layout changed: %s -> %s", self.layout, layout)
        self.monitors, self.layout = monitors, layout
        self.virtual = Rect.union(monitors)
        self.overlay.relayout(self.virtual)
        self.tray.notify("Tus pantallas han cambiado. Recalibra para mejor precisión.")

    # --- status ----------------------------------------------------------

    def _status(self) -> tuple[str, str]:
        if not self.settings.enabled:
            return "off", f"{DISPLAY_NAME}: en pausa"
        status = self.tracker.status
        if status == "no_camera":
            return "warn", f"{DISPLAY_NAME}: no se puede abrir la cámara"
        if status == "dark":
            return "warn", f"{DISPLAY_NAME}: la cámara se ve negra (¿tapa de privacidad?)"
        if self.model is None:
            return "warn", f"{DISPLAY_NAME}: falta calibrar"
        if status == "no_face":
            return "warn", f"{DISPLAY_NAME}: no se detecta tu cara"
        if status == "starting":
            return "warn", f"{DISPLAY_NAME}: iniciando cámara…"
        return "ok", f"{DISPLAY_NAME}: activo"

    def _update_tray(self) -> None:
        self.tray.set_state(*self._status())

    def status_lines(self) -> list[str]:
        sample = self.tracker.latest()
        m = sample.measure if sample else None
        lines = [
            f"Estado     {self._status()[1]}",
            f"Cámara     {self.tracker.status}  ·  {self.tracker.fps:4.1f} fps",
        ]
        if m is not None:
            lines.append(f"Cabeza     yaw {math.degrees(m.yaw):+6.1f}°  pitch {math.degrees(m.pitch):+6.1f}°"
                         f"  ·  ojos {m.eye_x:.3f}, {m.eye_y:+.3f}{'  (parpadeo)' if sample.blink else ''}")
        else:
            lines.append("Cabeza     —")
        if self.gaze is not None:
            lines.append(f"Mirada     x {self.gaze[0]:6.0f}  y {self.gaze[1]:6.0f}")
        else:
            lines.append("Mirada     —")
        if self.candidate is not None:
            title = self.candidate.title[:48]
            lines.append(f"Ventana    {title}  ({self.confidence:.0%})")
        else:
            lines.append("Ventana    —")
        lines.append(f"Bloqueo    {self.block_reason or '—'}")
        if self.model is not None:
            lines.append(f"Modelo     error ≈ {self.model.cv_error:.0f} px  ·  "
                         f"{self.data.click_count if self.data else 0} clics aprendidos  ·  "
                         f"{self.switches} cambios")
        return lines
