"""Regression from face features to a point on the (virtual) screen."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

# Relative ridge strengths tried by cross-validation.
LAMBDAS = (1e-4, 1e-3, 3e-3, 1e-2, 3e-2, 0.1, 0.3, 1.0)
CLICK_GROUP_BASE = 100_000
MAX_CLICK_SAMPLES = 150
CLICK_WEIGHT = 4.0


def expand(features) -> np.ndarray:
    """Features plus the quadratic head-pose terms that capture screen curvature."""
    f = np.atleast_2d(np.asarray(features, dtype=float))
    yaw, pitch = f[:, 0], f[:, 1]
    return np.column_stack([f, yaw * yaw, pitch * pitch, yaw * pitch])


def _ridge(S: np.ndarray, Y: np.ndarray, w: np.ndarray, lam: float) -> np.ndarray:
    X = np.column_stack([np.ones(len(S)), S])
    penalty = lam * w.sum() * np.eye(X.shape[1])
    penalty[0, 0] = 0.0  # never shrink the intercept
    Xw = X * w[:, None]
    return np.linalg.solve(X.T @ Xw + penalty, Xw.T @ Y)


def _apply(S: np.ndarray, coef: np.ndarray) -> np.ndarray:
    return S @ coef[1:] + coef[0]


@dataclass
class GazeModel:
    mean: np.ndarray
    std: np.ndarray
    coef: np.ndarray
    lam: float
    cv_error: float  # mean leave-one-target-out error in pixels (nan if unknown)

    def predict(self, features) -> np.ndarray:
        f = np.asarray(features, dtype=float)
        out = _apply((expand(f) - self.mean) / self.std, self.coef)
        return out[0] if f.ndim == 1 else out


def fit(features, targets, groups, weights=None, lambdas=LAMBDAS) -> GazeModel:
    """Weighted ridge regression, choosing the strength by leave-one-group-out CV.

    A group is one calibration target (or one click), so CV measures how well
    the model generalises to screen positions it has never seen.
    """
    F = np.asarray(features, dtype=float)
    Y = np.asarray(targets, dtype=float)
    g = np.asarray(groups)
    w = np.ones(len(F)) if weights is None else np.asarray(weights, dtype=float)
    if len(F) < 3:
        raise ValueError("not enough samples to fit a gaze model")

    Z = expand(F)
    mean = Z.mean(axis=0)
    std = np.maximum(Z.std(axis=0), 1e-6)
    S = (Z - mean) / std

    unique = np.unique(g)
    best_lam, best_err = 0.1, float("nan")
    if len(unique) >= 4:
        for lam in lambdas:
            errs = []
            for group in unique:
                test = g == group
                coef = _ridge(S[~test], Y[~test], w[~test], lam)
                d = np.linalg.norm(_apply(S[test], coef) - Y[test], axis=1)
                errs.append(np.average(d, weights=w[test]))
            err = float(np.mean(errs))
            if not best_err <= err:  # also replaces the initial nan
                best_lam, best_err = lam, err

    coef = _ridge(S, Y, w, best_lam)
    return GazeModel(mean=mean, std=std, coef=coef, lam=best_lam, cv_error=best_err)


@dataclass
class CalibrationData:
    """Every sample the model is trained on: calibration targets and clicks."""
    features: np.ndarray
    targets: np.ndarray
    groups: np.ndarray
    weights: np.ndarray
    layout: str

    @classmethod
    def empty(cls, layout: str) -> "CalibrationData":
        return cls(np.zeros((0, 7)), np.zeros((0, 2)), np.zeros(0, dtype=int),
                   np.zeros(0), layout)

    @property
    def click_count(self) -> int:
        return int((self.groups >= CLICK_GROUP_BASE).sum())

    def add(self, features, targets, group: int, weight: float = 1.0) -> None:
        F = np.atleast_2d(np.asarray(features, dtype=float))
        T = np.broadcast_to(np.asarray(targets, dtype=float), (len(F), 2))
        self.features = np.vstack([self.features, F])
        self.targets = np.vstack([self.targets, T])
        self.groups = np.concatenate([self.groups, np.full(len(F), group, dtype=int)])
        self.weights = np.concatenate([self.weights, np.full(len(F), weight)])

    def add_click(self, features, point) -> None:
        clicks = self.groups[self.groups >= CLICK_GROUP_BASE]
        group = int(clicks.max()) + 1 if len(clicks) else CLICK_GROUP_BASE
        self.add(features, point, group, CLICK_WEIGHT)
        if len(clicks) + 1 > MAX_CLICK_SAMPLES:
            oldest = int(clicks.min())
            self._keep(self.groups != oldest)

    def _keep(self, mask: np.ndarray) -> None:
        self.features = self.features[mask]
        self.targets = self.targets[mask]
        self.groups = self.groups[mask]
        self.weights = self.weights[mask]

    def fit(self) -> GazeModel:
        return fit(self.features, self.targets, self.groups, self.weights)

    def save(self, path: Path) -> None:
        payload = {
            "version": 1,
            "layout": self.layout,
            "features": self.features.tolist(),
            "targets": self.targets.tolist(),
            "groups": self.groups.tolist(),
            "weights": self.weights.tolist(),
        }
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> "CalibrationData | None":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            data = cls(
                features=np.asarray(raw["features"], dtype=float).reshape(-1, 7),
                targets=np.asarray(raw["targets"], dtype=float).reshape(-1, 2),
                groups=np.asarray(raw["groups"], dtype=int),
                weights=np.asarray(raw["weights"], dtype=float),
                layout=str(raw["layout"]),
            )
        except (OSError, ValueError, KeyError):
            return None
        return data if len(data.features) else None
