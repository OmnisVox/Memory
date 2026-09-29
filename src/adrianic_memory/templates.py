from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import numpy as np


class TemplateStatus(str, Enum):
    TEMPLATE_UNRESOLVED = "TEMPLATE_UNRESOLVED"
    TEMPLATE_READY = "TEMPLATE_READY"


@dataclass
class DualRepresentationCandidate:
    """Separate robust address accumulation from topology-sensitive template storage.

    Address vectors may be averaged because they are deliberately robust/phase-
    agnostic.  Complex templates are *not* arithmetic-averaged.  The best raw
    observation that passes the supplied topology-quality threshold is retained.
    """

    mean_address: np.ndarray
    observations: int = 1
    best_template: np.ndarray | None = None
    best_template_quality: float = float("-inf")
    template_status: TemplateStatus = TemplateStatus.TEMPLATE_UNRESOLVED

    @classmethod
    def from_observation(
        cls,
        address: np.ndarray,
        template: np.ndarray | None = None,
        template_quality: float | None = None,
        min_template_quality: float = 0.50,
    ) -> "DualRepresentationCandidate":
        obj = cls(np.asarray(address, dtype=float).copy())
        if template is not None and template_quality is not None:
            obj.consider_template(template, template_quality, min_template_quality)
        return obj

    def update_address(self, address: np.ndarray) -> None:
        address = np.asarray(address, dtype=float)
        if address.shape != self.mean_address.shape:
            raise ValueError("address shape changed within candidate")
        self.observations += 1
        self.mean_address += (address - self.mean_address) / float(self.observations)

    def consider_template(
        self,
        template: np.ndarray,
        quality: float,
        min_template_quality: float = 0.50,
    ) -> bool:
        quality = float(quality)
        if quality < float(min_template_quality):
            return False
        if self.best_template is None or quality > self.best_template_quality:
            self.best_template = np.asarray(template).copy()
            self.best_template_quality = quality
            self.template_status = TemplateStatus.TEMPLATE_READY
            return True
        return False


def finite_loop_winding(field: np.ndarray, loop: list[tuple[int, int]]) -> float:
    """Compute robust finite-loop phase winding around a supplied closed loop.

    ``loop`` is an ordered list of (row, column) indices.  The closing segment from
    the final point back to the first is included automatically.
    """
    psi = np.asarray(field)
    if psi.ndim != 2:
        raise ValueError("field must be a 2-D complex array")
    if len(loop) < 3:
        raise ValueError("loop must contain at least three points")
    vals = np.asarray([psi[r, c] for r, c in loop], dtype=complex)
    nxt = np.roll(vals, -1)
    increments = np.angle(nxt * np.conj(vals))
    return float(np.sum(increments) / (2.0 * np.pi))
