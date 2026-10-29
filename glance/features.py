"""Turn raw face landmarks into the gaze features the model consumes."""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

# (image-left corner, image-right corner, upper lid, lower lid, iris centre)
# in the 478-point MediaPipe face mesh. Both eyes are ordered left-to-right
# in image space so their horizontal ratios share a sign.
RIGHT_EYE = (33, 133, 159, 145, 468)
LEFT_EYE = (362, 263, 386, 374, 473)
FEATURE_NAMES = ("yaw", "pitch", "eye_x", "eye_y", "head_x", "head_y", "head_z")
BLINK_OPENNESS = 0.12


@dataclass(frozen=True)
class FaceMeasure:
    yaw: float
    pitch: float
    eye_x: float
    eye_y: float
    head: tuple[float, float, float]
    openness: float

    @property
    def blinking(self) -> bool:
        return self.openness < BLINK_OPENNESS

    def vector(self, eye: tuple[float, float] | None = None) -> np.ndarray:
        ex, ey = eye if eye is not None else (self.eye_x, self.eye_y)
        return np.array([self.yaw, self.pitch, ex, ey, *self.head], dtype=float)


def head_pose(matrix) -> tuple[float, float, tuple[float, float, float]]:
    """Yaw/pitch (radians) and translation from MediaPipe's face transform."""
    m = np.asarray(matrix, dtype=float).reshape(4, 4)
    forward = m[:3, 2]
    yaw = math.atan2(forward[0], forward[2])
    pitch = math.atan2(-forward[1], math.hypot(forward[0], forward[2]))
    tx, ty, tz = (float(v) for v in m[:3, 3])
    return yaw, pitch, (tx, ty, tz)


def eye_metrics(pts: np.ndarray, idx) -> tuple[float, float, float] | None:
    """Iris position inside the eye, normalised by eye width, plus openness."""
    left, right, top, bottom, iris = (pts[i] for i in idx)
    axis = right - left
    width = float(math.hypot(axis[0], axis[1]))
    if width < 1e-6:
        return None
    u = axis / width
    n = np.array([-u[1], u[0]])
    x = float(np.dot(iris - left, u)) / width
    y = float(np.dot(iris - (top + bottom) / 2, n)) / width
    gap = bottom - top
    openness = float(math.hypot(gap[0], gap[1])) / width
    return x, y, openness


def measure(pts: np.ndarray, matrix) -> FaceMeasure | None:
    """`pts` are landmark positions in pixels (so the aspect ratio is right)."""
    if len(pts) < 478:
        return None
    right = eye_metrics(pts, RIGHT_EYE)
    left = eye_metrics(pts, LEFT_EYE)
    if right is None or left is None:
        return None
    yaw, pitch, head = head_pose(matrix)
    return FaceMeasure(
        yaw=yaw,
        pitch=pitch,
        eye_x=(right[0] + left[0]) / 2,
        eye_y=(right[1] + left[1]) / 2,
        head=head,
        openness=min(right[2], left[2]),
    )
