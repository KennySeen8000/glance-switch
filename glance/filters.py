"""Signal smoothing for the gaze point."""
from __future__ import annotations

import math

import numpy as np


def _alpha(dt: float, cutoff: float) -> float:
    tau = 1.0 / (2 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuro:
    """One Euro filter (Casiez et al.): smooth when still, responsive when moving.

    Calling it twice with the same timestamp returns the previous output, so the
    UI tick can run faster than the camera.
    """

    def __init__(self, min_cutoff: float = 0.6, beta: float = 0.004,
                 d_cutoff: float = 1.0, reset_after: float = 0.6):
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset_after = reset_after
        self.reset()

    def reset(self) -> None:
        self._t: float | None = None
        self._x: np.ndarray | None = None
        self._dx = 0.0

    def __call__(self, t: float, x) -> np.ndarray:
        x = np.asarray(x, dtype=float)
        if self._t is None or t - self._t > self.reset_after:
            self._t, self._x, self._dx = t, x, 0.0
            return x
        dt = t - self._t
        if dt <= 0:
            return self._x
        speed = float(np.linalg.norm(x - self._x)) / dt
        a_d = _alpha(dt, self.d_cutoff)
        self._dx = a_d * speed + (1 - a_d) * self._dx
        a = _alpha(dt, self.min_cutoff + self.beta * self._dx)
        self._x = a * x + (1 - a) * self._x
        self._t = t
        return self._x
