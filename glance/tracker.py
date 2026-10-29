"""Camera capture and face tracking on a background thread.

Frames live only in memory: each one is analysed and then dropped (the most
recent one is kept only while the preview window is open).
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np
from mediapipe.tasks.python import BaseOptions, vision

from . import features
from .config import Settings

log = logging.getLogger(__name__)

DARK_FRAME_LEVEL = 8.0  # mean 0-255 brightness below which the picture is black


@dataclass(frozen=True)
class Sample:
    t: float  # time.monotonic() when the frame was captured
    features: np.ndarray | None
    measure: features.FaceMeasure | None = None
    blink: bool = False

    @property
    def face(self) -> bool:
        return self.measure is not None


class Tracker(threading.Thread):
    HISTORY_S = 4.0

    def __init__(self, settings: Settings, model_bytes: bytes):
        super().__init__(name="tracker", daemon=True)
        self._settings = settings
        self._model_bytes = model_bytes
        self._lock = threading.Lock()
        self._history: deque[Sample] = deque()
        self._stop_event = threading.Event()
        self._last_eye: tuple[float, float] | None = None
        self._last_ts_ms = 0
        self.status = "starting"  # starting | no_camera | dark | no_face | ok
        self.fps = 0.0
        self.want_frame = False
        # (bgr frame, landmark pixels or None) for the preview window.
        self.frame: tuple[np.ndarray, np.ndarray | None] | None = None

    # --- consumer API (any thread) ---------------------------------------

    def latest(self) -> Sample | None:
        with self._lock:
            return self._history[-1] if self._history else None

    def window(self, t0: float, t1: float) -> list[Sample]:
        with self._lock:
            return [s for s in self._history if t0 <= s.t <= t1]

    def median_features(self, t0: float, t1: float) -> np.ndarray | None:
        rows = [s.features for s in self.window(t0, t1)
                if s.features is not None and not s.blink]
        return np.median(rows, axis=0) if rows else None

    def stop(self) -> None:
        self._stop_event.set()

    # --- thread ----------------------------------------------------------

    def run(self) -> None:
        options = vision.FaceLandmarkerOptions(
            base_options=BaseOptions(model_asset_buffer=self._model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=0.5,
            min_face_presence_confidence=0.5,
            min_tracking_confidence=0.5,
            output_facial_transformation_matrixes=True,
        )
        with vision.FaceLandmarker.create_from_options(options) as landmarker:
            while not self._stop_event.is_set():
                cap = self._open_camera()
                if cap is None:
                    self.status = "no_camera"
                    self._stop_event.wait(3.0)
                    continue
                try:
                    self._capture_loop(cap, landmarker)
                except Exception:
                    log.exception("Tracker loop crashed; restarting camera")
                    self._stop_event.wait(1.0)
                finally:
                    cap.release()

    def _open_camera(self):
        s = self._settings
        cap = cv2.VideoCapture(s.camera_index, cv2.CAP_DSHOW)
        if not cap.isOpened():
            cap.release()
            return None
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, s.camera_width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, s.camera_height)
        cap.set(cv2.CAP_PROP_FPS, s.camera_fps)
        log.info("Camera %d opened at %dx%d", s.camera_index,
                 cap.get(cv2.CAP_PROP_FRAME_WIDTH), cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return cap

    def _capture_loop(self, cap, landmarker) -> None:
        interval = 1.0 / max(1, self._settings.camera_fps)
        last = 0.0
        failures = 0
        while not self._stop_event.is_set():
            # grab() is cheap and keeps the driver queue empty, so the frame we
            # decode is always the newest one (low latency).
            if not cap.grab():
                failures += 1
                if failures > 30:
                    self.status = "no_camera"
                    return
                time.sleep(0.03)
                continue
            failures = 0
            now = time.monotonic()
            if now - last < interval * 0.9:
                continue
            ok, frame = cap.retrieve()
            if not ok:
                continue
            if last:
                self.fps = 0.9 * self.fps + 0.1 / max(now - last, 1e-3)
            last = now
            self._process(landmarker, frame, now)

    def _process(self, landmarker, frame: np.ndarray, now: float) -> None:
        ts = max(int(now * 1000), self._last_ts_ms + 1)  # must be strictly increasing
        self._last_ts_ms = ts
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        result = landmarker.detect_for_video(mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb), ts)

        pts = None
        face = None
        if result.face_landmarks and result.facial_transformation_matrixes:
            h, w = frame.shape[:2]
            pts = np.array([(p.x * w, p.y * h) for p in result.face_landmarks[0]])
            face = features.measure(pts, result.facial_transformation_matrixes[0])

        sample = self._to_sample(now, face)
        with self._lock:
            self._history.append(sample)
            while self._history and now - self._history[0].t > self.HISTORY_S:
                self._history.popleft()
        if face:
            self.status = "ok"
        elif float(frame[::16, ::16].mean()) < DARK_FRAME_LEVEL:
            self.status = "dark"  # privacy shutter closed or no light
        else:
            self.status = "no_face"
        self.frame = (frame, pts) if self.want_frame else None

    def _to_sample(self, now: float, face: features.FaceMeasure | None) -> Sample:
        if face is None:
            return Sample(now, None)
        if face.blinking:
            # Closed lids make the iris estimate jump; hold the last open-eye value.
            vec = face.vector(self._last_eye) if self._last_eye else None
            return Sample(now, vec, face, blink=True)
        self._last_eye = (face.eye_x, face.eye_y)
        return Sample(now, face.vector(), face)
