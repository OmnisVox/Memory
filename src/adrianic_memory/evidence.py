from __future__ import annotations

from dataclasses import dataclass, field
import math

from .types import EvidenceAssessment, ValueStatus


@dataclass
class SourceState:
    reliability: float = 0.5
    bias: float = 0.0
    provenance_group: str | None = None


class EvidenceGraph:
    """Trust-calibrated value evidence with dependency discounting.

    Equations follow the supplied trust/evidence patches. The unresolved thresholds
    are project configuration, because the source patches deliberately do not claim
    universal constants for them.
    """

    def __init__(
        self,
        reliability_lr: float = 0.08,
        bias_lr: float = 0.08,
        sigma_u: float = 0.25,
        gamma: float = 2.0,
        beta: float = 1.0,
        min_effective_reliability: float = 0.45,
        max_common_cause_risk: float = 0.45,
    ):
        self.reliability_lr = float(reliability_lr)
        self.bias_lr = float(bias_lr)
        self.sigma_u = float(sigma_u)
        self.gamma = float(gamma)
        self.beta = float(beta)
        self.min_effective_reliability = float(min_effective_reliability)
        self.max_common_cause_risk = float(max_common_cause_risk)
        self.sources: dict[str, SourceState] = {}
        self.dependencies: dict[tuple[str, str], float] = {}
        self.common_cause_risk = 0.0

    def ensure_source(self, source: str, provenance_group: str | None = None) -> SourceState:
        if source not in self.sources:
            self.sources[source] = SourceState(provenance_group=provenance_group)
        elif provenance_group is not None:
            self.sources[source].provenance_group = provenance_group
        return self.sources[source]

    def verify(self, source: str, reported_utility: float, verified_outcome: float) -> None:
        s = self.ensure_source(source)
        q = math.exp(-abs(float(reported_utility) - float(verified_outcome)) / self.sigma_u)
        s.reliability = (1.0 - self.reliability_lr) * s.reliability + self.reliability_lr * q
        s.bias = (1.0 - self.bias_lr) * s.bias + self.bias_lr * (float(reported_utility) - float(verified_outcome))

    def set_dependency(self, source_i: str, source_j: str, tendency: float) -> None:
        tendency = max(0.0, min(1.0, float(tendency)))
        self.dependencies[(source_i, source_j)] = tendency
        self.dependencies[(source_j, source_i)] = tendency

    def assess(self, reports: dict[str, float]) -> EvidenceAssessment:
        if not reports:
            return EvidenceAssessment(ValueStatus.VALUE_UNRESOLVED, None, 0.0, reasons=["no_value_reports"])

        names = list(reports)
        states = [self.ensure_source(n) for n in names]
        debiased = {n: float(reports[n]) - self.sources[n].bias for n in names}
        a = {n: max(self.sources[n].reliability, 0.0) ** self.gamma for n in names}
        total_a = sum(a.values()) + 1e-12
        abar = {n: a[n] / total_a for n in names}

        redundancy = {}
        for n in names:
            redundancy[n] = sum(self.dependencies.get((n, m), 0.0) * abar[m] for m in names if m != n)

        raw_w = {n: a[n] / (1.0 + self.beta * redundancy[n]) for n in names}

        # Enforce the provenance constraint: aliases in one causal group may not
        # multiply influence simply by appearing under multiple source identities.
        grouped: dict[str, list[str]] = {}
        for n in names:
            g = self.sources[n].provenance_group or f"__independent__:{n}"
            grouped.setdefault(g, []).append(n)
        for members in grouped.values():
            if len(members) > 1:
                group_total = sum(raw_w[n] for n in members)
                cap = max(raw_w[n] for n in members)
                if group_total > cap and group_total > 0:
                    factor = cap / group_total
                    for n in members:
                        raw_w[n] *= factor

        z = sum(raw_w.values()) + 1e-12
        weights = {n: raw_w[n] / z for n in names}
        utility = sum(weights[n] * debiased[n] for n in names)
        effective_rel = sum(weights[n] * self.sources[n].reliability for n in names)

        reasons = []
        if effective_rel < self.min_effective_reliability:
            reasons.append("effective_reliability_below_project_threshold")
        if self.common_cause_risk > self.max_common_cause_risk:
            reasons.append("common_cause_risk_above_project_threshold")
        status = ValueStatus.VALUE_UNRESOLVED if reasons else ValueStatus.RESOLVED
        return EvidenceAssessment(status, None if reasons else float(utility), float(effective_rel), weights, debiased, reasons)


    def apply_dependency_strengths(self, strengths: dict[tuple[str, str], float]) -> None:
        """Replace pairwise dependency weights from an external transparent learner."""
        self.dependencies.clear()
        for (a, b), value in strengths.items():
            if a == b:
                continue
            self.set_dependency(a, b, value)
