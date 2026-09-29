from __future__ import annotations

from dataclasses import dataclass
from collections import deque
import numpy as np


@dataclass(frozen=True)
class AnchorFilterResult:
    value: float
    flagged: bool
    disagreement: float
    threshold: float
    routine_anchor: float
    verifier_consensus: float


class RobustAnchorFilter:
    """Cross-check a routine verification anchor against an independent consensus.

    This is a faithful interface reconstruction of the recovered Evidence Graph v3
    anchor filter.  It keeps a running disagreement history and uses a robust
    median+MAD threshold.  Flagged anchors are replaced by verifier consensus;
    unflagged anchors are blended with it.

    Historical benchmark configuration:
      warmup=40, history_window=300, threshold_sigma=2.8,
      blend_anchor=0.70, MAD normalizer=1.4826.

    The source benchmark also exposed a failure boundary: when corrupted anchors
    become common enough, the running baseline can begin normalizing corruption.
    """

    def __init__(
        self,
        warmup: int = 40,
        history_window: int = 300,
        threshold_sigma: float = 2.8,
        blend_anchor: float = 0.70,
        initial_threshold: float = 1.0,
    ):
        self.warmup = int(warmup)
        self.history = deque(maxlen=int(history_window))
        self.threshold_sigma = float(threshold_sigma)
        self.blend_anchor = float(blend_anchor)
        self.initial_threshold = float(initial_threshold)

    def _threshold(self) -> float:
        if len(self.history) <= self.warmup:
            return self.initial_threshold
        arr = np.asarray(self.history, dtype=float)
        med = float(np.median(arr))
        mad = float(np.median(np.abs(arr - med))) + 1e-6
        return med + self.threshold_sigma * 1.4826 * mad

    def filter(self, routine_anchor: float, verifier_consensus: float) -> AnchorFilterResult:
        a = float(routine_anchor)
        v = float(verifier_consensus)
        disagreement = abs(a - v)
        threshold = self._threshold()
        flagged = disagreement > threshold
        value = v if flagged else self.blend_anchor * a + (1.0 - self.blend_anchor) * v
        self.history.append(disagreement)
        return AnchorFilterResult(value, flagged, disagreement, threshold, a, v)
