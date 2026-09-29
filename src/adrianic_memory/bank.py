from __future__ import annotations

import time
import numpy as np

from .types import MemorySlot, RetrievalResult, RetrievalStatus


def scaled_distance(a: np.ndarray, b: np.ndarray, scales: np.ndarray) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    scales = np.asarray(scales, dtype=float)
    if a.shape != b.shape or a.shape != scales.shape:
        raise ValueError("address and scale shapes must match")
    safe = np.where(np.abs(scales) > 1e-12, scales, 1.0)
    return float(np.sqrt(np.mean(((a - b) / safe) ** 2)))


class AddressableMemoryBank:
    """Transparent finite memory bank with honest refusal.

    Resolution can require both:
      * an absolute best-match distance below ``max_distance``; and
      * a best-vs-second-best margin above ``min_margin``.

    This matters because a large relative margin is not evidence that the nearest
    slot is actually close to the query.  The recovered field-reintegration
    benchmark calibrated ``max_distance=0.20`` and ``min_margin=0.035`` for its
    particular 24-member vortex family.  Those values are intentionally *not*
    universal defaults here.

    The bank accepts externally computed address vectors.  The historical 12-D
    core-geometry + global-moments extractor is preserved in the evidence/experiment
    archive rather than silently generalized into the core API.
    """

    def __init__(
        self,
        capacity: int,
        scales: np.ndarray,
        min_margin: float = 0.06,
        max_distance: float | None = None,
    ):
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        self.capacity = int(capacity)
        self.scales = np.asarray(scales, dtype=float)
        self.min_margin = float(min_margin)
        self.max_distance = None if max_distance is None else float(max_distance)
        self.slots: list[MemorySlot] = []

    def __len__(self) -> int:
        return len(self.slots)

    def retrieve(self, address: np.ndarray) -> RetrievalResult:
        if not self.slots:
            return RetrievalResult(
                RetrievalStatus.EMPTY, None, None, None, None,
                {"reason": "bank_empty"},
            )

        q = np.asarray(address, dtype=float)
        ds = np.array([scaled_distance(q, s.address, self.scales) for s in self.slots])
        order = np.argsort(ds)
        best_i = int(order[0])
        best = float(ds[best_i])
        second = float(ds[order[1]]) if len(order) > 1 else float("inf")
        margin = second - best

        if self.max_distance is not None and best >= self.max_distance:
            return RetrievalResult(
                RetrievalStatus.HOLD_UNRESOLVED, None, best, second, margin,
                {
                    "reason": "best_address_beyond_absolute_distance",
                    "max_distance": self.max_distance,
                },
            )

        if len(order) > 1 and margin <= self.min_margin:
            return RetrievalResult(
                RetrievalStatus.HOLD_UNRESOLVED, None, best, second, margin,
                {"reason": "address_margin_below_threshold", "min_margin": self.min_margin},
            )

        slot = self.slots[best_i]
        slot.usage_count += 1
        slot.last_access = time.time()
        return RetrievalResult(
            RetrievalStatus.FOUND, slot, best, second, margin,
            {"reason": "best_address_clear"},
        )

    def allocate(self, slot: MemorySlot) -> None:
        if len(self.slots) >= self.capacity:
            raise RuntimeError("bank is full; replacement requires an explicit commit decision")
        if slot.address.shape != self.scales.shape:
            raise ValueError("slot address shape must match bank scales")
        self.slots.append(slot)

    def replacement_candidate(
        self,
        alpha: float = 0.02,
        now: float | None = None,
    ) -> MemorySlot | None:
        """Return the weakest retained slot under the transparent retention proxy.

        R_j = U_j * sqrt(log(1+n_j)) / (1 + alpha * age_j)

        ``estimated_future_utility`` is the slot's current U_j estimate.  This is
        the retained-slot side of the recovered comparative-replacement gate.  The
        method only proposes a candidate; it never replaces automatically.
        """
        if not self.slots:
            return None
        now = time.time() if now is None else float(now)

        def retention_value(s: MemorySlot) -> float:
            age = max(0.0, now - s.last_access)
            support = np.sqrt(np.log1p(max(0, int(s.usage_count))))
            return float(s.estimated_future_utility) * float(support) / (1.0 + float(alpha) * age)

        return min(self.slots, key=retention_value)

    def replace(self, slot_id: str, new_slot: MemorySlot) -> None:
        for i, slot in enumerate(self.slots):
            if slot.slot_id == slot_id:
                if new_slot.address.shape != self.scales.shape:
                    raise ValueError("slot address shape must match bank scales")
                self.slots[i] = new_slot
                return
        raise KeyError(slot_id)
