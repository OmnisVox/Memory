import json
from pathlib import Path
import numpy as np

from adrianic_memory.bank import AddressableMemoryBank
from adrianic_memory.consolidation import SelectiveCommitController
from adrianic_memory.dependency import ResidualDependencyLearner
from adrianic_memory.evidence import EvidenceGraph
from adrianic_memory.parity import DualParityGuard
from adrianic_memory.roles import enumerate_v315_allocations, load_v315_results, V315_RECORDED_WINNER
from adrianic_memory.types import CandidateSignals, Decision, MemorySlot, ValueStatus


def test_v315_search_space_has_20_allocations():
    assert len(enumerate_v315_allocations()) == 20


def test_v315_original_result_matches_recorded_winner():
    root = Path(__file__).resolve().parents[1]
    p = root / "evidence" / "extracted" / "adrianic_v3_15_optimal_seven_slots"
    results = next(p.rglob("results.json"))
    w = load_v315_results(results)
    assert w.trio == V315_RECORDED_WINNER
    assert abs(w.heldout_score - 0.8600740846476203) < 1e-12


def test_dual_parity_repairs_single_coordinate_fault():
    guard = DualParityGuard()
    z = np.array([0.2, -0.4, 1.1, 0.7])
    p, q = guard.encode(z)
    corrupted = z.copy()
    corrupted[2] += 0.9
    repaired = guard.repair_single(corrupted, p, q)
    assert repaired.success
    assert repaired.corrected_index == 2
    assert np.allclose(repaired.repaired, z)


def test_bank_refuses_ambiguous_address():
    bank = AddressableMemoryBank(2, scales=np.ones(2), min_margin=0.1)
    bank.allocate(MemorySlot("a", np.array([0.0, 0.0])))
    bank.allocate(MemorySlot("b", np.array([0.0, 0.1])))
    result = bank.retrieve(np.array([0.0, 0.05]))
    assert result.status.value == "HOLD_UNRESOLVED"


def test_selective_commit_preserves_hold_for_unresolved_value():
    ctl = SelectiveCommitController()
    s = CandidateSignals(
        support=5, stability=0.99, novelty=0.5,
        downstream_utility=None, value_status=ValueStatus.VALUE_UNRESOLVED
    )
    assert ctl.decide(s).decision == Decision.HOLD


def test_dependency_learner_finds_correlated_aliases():
    learner = ResidualDependencyLearner(threshold=0.7, min_samples=20)
    rng = np.random.default_rng(4)
    for _ in range(60):
        x = rng.normal()
        learner.update({"A": x, "B": x + rng.normal(0, 0.05), "C": rng.normal()})
    groups = learner.groups()
    assert any({"A", "B"}.issubset(g) for g in groups)


def test_evidence_dependency_can_be_applied():
    graph = EvidenceGraph()
    graph.ensure_source("A")
    graph.ensure_source("B")
    graph.apply_dependency_strengths({("A","B"): 0.9, ("B","A"): 0.9})
    assert graph.dependencies[("A","B")] == 0.9


def test_bank_refuses_far_query_even_with_clear_margin():
    bank = AddressableMemoryBank(2, scales=np.ones(2), min_margin=0.01, max_distance=0.20)
    bank.allocate(MemorySlot("a", np.array([0.0, 0.0])))
    bank.allocate(MemorySlot("b", np.array([1.0, 1.0])))
    result = bank.retrieve(np.array([0.5, 0.0]))
    assert result.status.value == "HOLD_UNRESOLVED"
    assert result.audit["reason"] == "best_address_beyond_absolute_distance"


def test_comparative_replacement_is_resource_allocation_decision():
    import time
    ctl = SelectiveCommitController(replacement_margin=0.28)
    retained = MemorySlot(
        "old",
        np.array([0.0, 0.0]),
        estimated_future_utility=1.0,
        usage_count=1,
        last_access=time.time(),
    )
    weak = CandidateSignals(
        support=3, stability=0.99, novelty=0.5,
        downstream_utility=0.5, confidence=1.0,
    )
    strong = CandidateSignals(
        support=3, stability=0.99, novelty=0.5,
        downstream_utility=2.0, confidence=1.0,
    )
    assert ctl.decide(weak, bank_full=True, replacement_candidate=retained).decision == Decision.HOLD
    assert ctl.decide(strong, bank_full=True, replacement_candidate=retained).decision == Decision.INCLUDE


def test_anchor_filter_flags_large_disagreement_after_stable_history():
    from adrianic_memory.verification import RobustAnchorFilter
    filt = RobustAnchorFilter(warmup=2, history_window=20, initial_threshold=0.1)
    for _ in range(4):
        r = filt.filter(1.0, 1.0)
        assert not r.flagged
    out = filt.filter(3.0, 1.0)
    assert out.flagged
    assert out.value == 1.0


def test_dual_representation_does_not_average_complex_templates():
    from adrianic_memory.templates import DualRepresentationCandidate, TemplateStatus
    good = np.array([[1+0j, 1j], [-1+0j, -1j]])
    other = -good
    c = DualRepresentationCandidate.from_observation(
        np.array([0.0, 0.0]), good, 0.9, min_template_quality=0.5
    )
    c.update_address(np.array([0.2, 0.0]))
    c.consider_template(other, 0.8, min_template_quality=0.5)
    assert c.template_status == TemplateStatus.TEMPLATE_READY
    assert np.array_equal(c.best_template, good)
    assert np.allclose(c.mean_address, np.array([0.1, 0.0]))


def test_finite_loop_winding_recovers_unit_winding():
    from adrianic_memory.templates import finite_loop_winding
    field = np.ones((2, 2), dtype=complex)
    loop = [(0, 0), (0, 1), (1, 1), (1, 0)]
    phases = [0.0, np.pi/2, np.pi, -np.pi/2]
    for idx, phase in zip(loop, phases):
        field[idx] = np.exp(1j * phase)
    assert abs(finite_loop_winding(field, loop) - 1.0) < 1e-12


def test_causal_ledger_exports_schema(tmp_path):
    from adrianic_memory.causal import CausalAblationLedger, CausalLedgerEntry
    led = CausalAblationLedger()
    led.append(CausalLedgerEntry("e1", 0.5, 0.1, True, trust_path_distance=0.02))
    p = tmp_path / "ledger.csv"
    led.export_csv(p)
    text = p.read_text()
    assert "raw_anchor_error" in text
    assert "0.5" in text
