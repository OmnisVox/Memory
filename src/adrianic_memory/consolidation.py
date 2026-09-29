from __future__ import annotations

from dataclasses import dataclass
import math
import time

from .types import CandidateSignals, CommitDecision, Decision, ValueStatus, MemorySlot


@dataclass
class ValueWeights:
    recurrence: float = 1.0
    stability: float = 1.0
    novelty: float = 1.0
    downstream_utility: float = 1.0
    consequence: float = 1.0
    interference: float = 1.0


@dataclass
class ComparativeReplacementConfig:
    """Transparent full-bank replacement comparison.

    Candidate proxy recovered from the complex-field replacement study:
      C_c = U_c (0.65 + 0.35 S_c) (0.75 + 0.25 Q_c)

    where S_c is normalized support and Q_c is confidence.

    Retained-slot proxy:
      R_j = U_j sqrt(log(1+n_j)) / (1 + alpha * age_j)

    The margin is calibration-dependent.  The abstract causal-ablation benchmark
    favored 0.16, while the field-level benchmark favored 0.28.  Therefore the
    canonical default remains 0.0 and callers must opt into a calibrated margin.
    """
    support_reference: float = 3.0
    retained_age_alpha: float = 0.02

    def candidate_value(self, s: CandidateSignals) -> float | None:
        if s.downstream_utility is None:
            return None
        support = min(max(float(s.support) / max(self.support_reference, 1e-12), 0.0), 1.0)
        confidence = min(max(float(s.confidence), 0.0), 1.0)
        return (
            float(s.downstream_utility)
            * (0.65 + 0.35 * support)
            * (0.75 + 0.25 * confidence)
        )

    def retained_value(self, slot: MemorySlot, now: float | None = None) -> float:
        now = time.time() if now is None else float(now)
        age = max(0.0, now - float(slot.last_access))
        support = math.sqrt(math.log1p(max(0, int(slot.usage_count))))
        return (
            float(slot.estimated_future_utility)
            * support
            / (1.0 + self.retained_age_alpha * age)
        )


class SelectiveCommitController:
    """Transparent INCLUDE / EXCLUDE / HOLD controller.

    Defaults preserve the calibrated selective-commit thresholds reported in the
    source study: support >= 3, stability >= .90, novelty >= .06.
    """

    def __init__(
        self,
        min_support: int = 3,
        min_stability: float = 0.90,
        min_novelty: float = 0.06,
        value_weights: ValueWeights | None = None,
        min_value: float | None = None,
        replacement_margin: float = 0.0,
        replacement: ComparativeReplacementConfig | None = None,
    ):
        self.min_support = int(min_support)
        self.min_stability = float(min_stability)
        self.min_novelty = float(min_novelty)
        self.value_weights = value_weights or ValueWeights()
        self.min_value = min_value
        self.replacement_margin = float(replacement_margin)
        self.replacement = replacement or ComparativeReplacementConfig()

    def value_score(self, s: CandidateSignals) -> float | None:
        if s.downstream_utility is None:
            return None
        w = self.value_weights
        return (
            w.recurrence * s.recurrence
            + w.stability * s.stability
            + w.novelty * s.novelty
            + w.downstream_utility * s.downstream_utility
            + w.consequence * s.consequence
            - w.interference * s.interference
        )

    def decide(
        self,
        signals: CandidateSignals,
        bank_full: bool = False,
        replacement_candidate: MemorySlot | None = None,
        now: float | None = None,
    ) -> CommitDecision:
        reasons: list[str] = []
        if signals.value_status == ValueStatus.VALUE_UNRESOLVED:
            return CommitDecision(Decision.HOLD, ["VALUE_UNRESOLVED"])
        if signals.redundant:
            return CommitDecision(Decision.EXCLUDE, ["already_represented"])
        if signals.support < self.min_support:
            return CommitDecision(Decision.HOLD, ["insufficient_recurrence_support"])
        if signals.stability < self.min_stability:
            return CommitDecision(Decision.EXCLUDE, ["repeated_but_unstable"])
        if signals.novelty < self.min_novelty:
            return CommitDecision(Decision.EXCLUDE, ["insufficient_novelty"])

        score = self.value_score(signals)
        if self.min_value is not None:
            if score is None:
                return CommitDecision(Decision.HOLD, ["value_required_but_not_measured"])
            if score < self.min_value:
                return CommitDecision(Decision.HOLD, ["value_below_commit_threshold"], score)

        if bank_full:
            if replacement_candidate is None:
                return CommitDecision(Decision.HOLD, ["bank_full_no_replacement_candidate"], score)
            candidate_value = self.replacement.candidate_value(signals)
            if candidate_value is None:
                return CommitDecision(Decision.HOLD, ["bank_full_future_utility_unresolved"], score)
            retained_value = self.replacement.retained_value(replacement_candidate, now=now)
            margin = candidate_value - retained_value - float(signals.interference)
            if margin <= self.replacement_margin:
                return CommitDecision(
                    Decision.HOLD,
                    ["counterfactual_replacement_margin_not_met"],
                    score,
                    replacement_candidate.slot_id,
                    margin,
                )
            reasons.append("counterfactual_replacement_margin_met")
            return CommitDecision(
                Decision.INCLUDE,
                reasons,
                score,
                replacement_candidate.slot_id,
                margin,
            )

        reasons.append("selective_commit_criteria_met")
        return CommitDecision(Decision.INCLUDE, reasons, score)
