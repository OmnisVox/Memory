from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
import numpy as np


@dataclass(frozen=True)
class DependencyEdge:
    source_i: str
    source_j: str
    correlation: float
    samples: int


class ResidualDependencyLearner:
    """Transparent verified-residual dependency learner.

    Inspired by v3.20: pairwise source dependence is estimated from verified
    residual correlations rather than supplied provenance labels.

    This is a clean reconstruction interface, not a claim of byte-identical
    equivalence to the historical v3.20 benchmark implementation (which is not
    present in the surviving bundle).
    """

    def __init__(self, threshold: float = 0.72, min_samples: int = 12, max_history: int = 512):
        self.threshold = float(threshold)
        self.min_samples = int(min_samples)
        self.max_history = int(max_history)
        self._pairs: dict[tuple[str, str], deque[tuple[float, float]]] = defaultdict(
            lambda: deque(maxlen=self.max_history)
        )

    def update(self, residuals: dict[str, float]) -> None:
        names = sorted(residuals)
        for i, a in enumerate(names):
            for b in names[i + 1 :]:
                self._pairs[(a, b)].append((float(residuals[a]), float(residuals[b])))

    @staticmethod
    def _corr(samples: deque[tuple[float, float]]) -> float:
        if len(samples) < 2:
            return 0.0
        arr = np.asarray(samples, dtype=float)
        if np.std(arr[:, 0]) < 1e-12 or np.std(arr[:, 1]) < 1e-12:
            return 0.0
        return float(np.corrcoef(arr[:, 0], arr[:, 1])[0, 1])

    def edges(self) -> list[DependencyEdge]:
        out = []
        for (a, b), samples in sorted(self._pairs.items()):
            if len(samples) < self.min_samples:
                continue
            c = self._corr(samples)
            if c > self.threshold:
                out.append(DependencyEdge(a, b, c, len(samples)))
        return out

    def dependency_strengths(self) -> dict[tuple[str, str], float]:
        strengths: dict[tuple[str, str], float] = {}
        for edge in self.edges():
            strengths[(edge.source_i, edge.source_j)] = edge.correlation
            strengths[(edge.source_j, edge.source_i)] = edge.correlation
        return strengths

    def groups(self) -> list[set[str]]:
        # Connected components of thresholded dependency graph.
        graph: dict[str, set[str]] = defaultdict(set)
        for e in self.edges():
            graph[e.source_i].add(e.source_j)
            graph[e.source_j].add(e.source_i)
        seen: set[str] = set()
        groups: list[set[str]] = []
        for node in sorted(graph):
            if node in seen:
                continue
            stack = [node]
            comp = set()
            while stack:
                x = stack.pop()
                if x in seen:
                    continue
                seen.add(x)
                comp.add(x)
                stack.extend(graph[x] - seen)
            groups.append(comp)
        return groups


class LatentCommonCauseModel:
    """Low-rank residual factor detector inspired by v3.21.

    Complete verified residual vectors are retained. Leading covariance
    eigenvectors are inspected; source families are reported when multiple
    sources exceed the loading threshold on a retained factor.

    Thresholds are explicit project configuration and are not universal.
    """

    def __init__(
        self,
        sources: list[str],
        max_factors: int = 3,
        loading_threshold: float = 0.45,
        min_factor_fraction: float = 0.08,
        max_history: int = 512,
    ):
        self.sources = list(sources)
        self.max_factors = int(max_factors)
        self.loading_threshold = float(loading_threshold)
        self.min_factor_fraction = float(min_factor_fraction)
        self.history = deque(maxlen=int(max_history))

    def update(self, residuals: dict[str, float]) -> bool:
        if any(s not in residuals for s in self.sources):
            return False
        self.history.append([float(residuals[s]) for s in self.sources])
        return True

    def factors(self) -> list[dict]:
        if len(self.history) < max(4, len(self.sources)):
            return []
        x = np.asarray(self.history, dtype=float)
        x = x - x.mean(axis=0, keepdims=True)
        cov = np.cov(x, rowvar=False)
        vals, vecs = np.linalg.eigh(cov)
        order = np.argsort(vals)[::-1]
        total = float(np.maximum(vals, 0).sum()) + 1e-12
        out = []
        for idx in order[: self.max_factors]:
            val = float(max(vals[idx], 0.0))
            frac = val / total
            if frac < self.min_factor_fraction:
                continue
            v = vecs[:, idx]
            family = [s for s, loading in zip(self.sources, v) if abs(float(loading)) >= self.loading_threshold]
            if len(family) < 2:
                continue
            out.append({
                "variance_fraction": frac,
                "family": family,
                "loadings": {s: float(l) for s, l in zip(self.sources, v)},
            })
        return out
