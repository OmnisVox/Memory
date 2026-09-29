from __future__ import annotations

from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class ParitySyndrome:
    delta_p: float
    delta_q: float
    magnitude: float


@dataclass(frozen=True)
class RepairResult:
    repaired: np.ndarray
    success: bool
    corrected_index: int | None
    syndrome_before: ParitySyndrome
    syndrome_after: ParitySyndrome


class DualParityGuard:
    """Deterministic P/Q integrity guard from the v3.15/v3.8 lineage.

    Default four-state checksums:
        P = z0 + z1 + z2 + z3
        Q = z0 - z1 + 2 z2 - 2 z3

    This is hand-designed redundancy. It is not claimed as spontaneously learned.
    It can locate a single-coordinate corruption when the syndrome ratio matches
    one of the unique Q coefficients closely enough.
    """

    def __init__(
        self,
        q_coefficients: np.ndarray | None = None,
        detect_threshold: float = 0.08,
        ratio_tolerance: float = 0.15,
        post_repair_tolerance: float = 0.12,
    ):
        self.q = np.asarray(
            [1.0, -1.0, 2.0, -2.0] if q_coefficients is None else q_coefficients,
            dtype=float,
        )
        if self.q.ndim != 1 or len(set(np.round(self.q, 12))) != len(self.q):
            raise ValueError("q_coefficients must be a 1-D vector of unique values")
        self.p = np.ones_like(self.q)
        self.detect_threshold = float(detect_threshold)
        self.ratio_tolerance = float(ratio_tolerance)
        self.post_repair_tolerance = float(post_repair_tolerance)

    def encode(self, state: np.ndarray) -> tuple[float, float]:
        z = np.asarray(state, dtype=float)
        if z.shape != self.q.shape:
            raise ValueError("state shape must match parity coefficients")
        return float(self.p @ z), float(self.q @ z)

    def syndrome(self, observed: np.ndarray, stored_p: float, stored_q: float) -> ParitySyndrome:
        z = np.asarray(observed, dtype=float)
        if z.shape != self.q.shape:
            raise ValueError("observed shape must match parity coefficients")
        dp = float(stored_p - self.p @ z)
        dq = float(stored_q - self.q @ z)
        return ParitySyndrome(dp, dq, float(np.hypot(dp, dq)))

    def repair_single(self, observed: np.ndarray, stored_p: float, stored_q: float) -> RepairResult:
        z = np.asarray(observed, dtype=float).copy()
        before = self.syndrome(z, stored_p, stored_q)
        if before.magnitude <= self.detect_threshold:
            return RepairResult(z, True, None, before, before)
        if abs(before.delta_p) <= 1e-12:
            return RepairResult(z, False, None, before, before)

        ratio = before.delta_q / before.delta_p
        j = int(np.argmin(np.abs(self.q - ratio)))
        if abs(float(self.q[j] - ratio)) > self.ratio_tolerance:
            return RepairResult(z, False, None, before, before)

        # P coefficient is 1 for every coordinate.
        z[j] += before.delta_p
        after = self.syndrome(z, stored_p, stored_q)
        success = after.magnitude < self.post_repair_tolerance
        return RepairResult(z, success, j if success else None, before, after)
