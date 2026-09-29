from __future__ import annotations

from dataclasses import dataclass
import numpy as np


def phase_invariant_overlap(a: np.ndarray, b: np.ndarray, eps: float = 1e-12) -> float:
    a = np.asarray(a).ravel()
    b = np.asarray(b).ravel()
    den = np.linalg.norm(a) * np.linalg.norm(b) + eps
    return float(abs(np.vdot(a, b)) / den)


@dataclass
class TriageDecision:
    learn_gate: float
    recall_gate: float
    mode: str
    state_surprise: float
    memory_surprise: float
    disagreement: float


class SourceOfSurpriseController:
    """Glass-box triage from the memory-timescale study."""

    def __init__(self, delta: float = 0.08, disagreement_threshold: float = 0.08, damage_threshold: float = 0.25):
        self.delta = float(delta)
        self.disagreement_threshold = float(disagreement_threshold)
        self.damage_threshold = float(damage_threshold)

    def decide(self, psi_before, psi_now, chi_before, chi_now) -> TriageDecision:
        s_psi = 1.0 - phase_invariant_overlap(psi_before, psi_now)
        s_chi = 1.0 - phase_invariant_overlap(chi_before, chi_now)
        disagreement = 1.0 - phase_invariant_overlap(psi_now, chi_now)

        if s_psi > self.damage_threshold and s_chi > self.damage_threshold:
            return TriageDecision(1.0, 1.0, "symmetric_repair", s_psi, s_chi, disagreement)
        if s_psi > s_chi + self.delta and disagreement > self.disagreement_threshold:
            return TriageDecision(0.0, 1.0, "freeze_learning_recall_from_memory", s_psi, s_chi, disagreement)
        if s_chi > s_psi + self.delta and disagreement > self.disagreement_threshold:
            return TriageDecision(1.0, 0.0, "freeze_recall_reteach_memory", s_psi, s_chi, disagreement)
        return TriageDecision(1.0, 1.0, "normal_fast_recall_slow_learning", s_psi, s_chi, disagreement)

    @staticmethod
    def repair_interval(tau_learning: float, memory_surprise: float, t_min: float = 1.0, t_max: float = 5.0) -> float:
        return float(np.clip(tau_learning * (0.5 + 2.0 * memory_surprise), t_min, t_max))
