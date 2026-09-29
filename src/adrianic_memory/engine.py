from __future__ import annotations

from dataclasses import asdict
from typing import Any
import json
import numpy as np

from .bank import AddressableMemoryBank
from .consolidation import SelectiveCommitController
from .evidence import EvidenceGraph
from .types import CandidateSignals, CommitDecision, Decision, MemorySlot, RetrievalResult


class AdrianicMemoryEngine:
    """Narrow integrated memory API.

    The engine deliberately composes only mechanisms whose interfaces can be
    reconstructed without altering the underlying research claims. Developmental
    factor birth/prune and semantic reasoning remain optional experiment modules.
    """

    def __init__(self, bank: AddressableMemoryBank, commit: SelectiveCommitController | None = None, evidence: EvidenceGraph | None = None):
        self.bank = bank
        self.commit_controller = commit or SelectiveCommitController()
        self.evidence = evidence or EvidenceGraph()
        self.audit_log: list[dict[str, Any]] = []

    def retrieve(self, address: np.ndarray) -> RetrievalResult:
        result = self.bank.retrieve(address)
        self.audit_log.append({"event": "retrieve", "status": result.status.value, "audit": result.audit})
        return result

    def evaluate_candidate(self, signals: CandidateSignals) -> CommitDecision:
        repl = self.bank.replacement_candidate() if len(self.bank) >= self.bank.capacity else None
        decision = self.commit_controller.decide(signals, bank_full=len(self.bank) >= self.bank.capacity, replacement_candidate=repl)
        self.audit_log.append({
            "event": "commit_decision",
            "decision": decision.decision.value,
            "reasons": decision.reasons,
            "value_score": decision.value_score,
            "replacement_slot_id": decision.replacement_slot_id,
            "replacement_margin": decision.replacement_margin,
        })
        return decision

    def commit(self, slot: MemorySlot, decision: CommitDecision) -> bool:
        if decision.decision != Decision.INCLUDE:
            return False
        if decision.replacement_slot_id is None:
            self.bank.allocate(slot)
        else:
            self.bank.replace(decision.replacement_slot_id, slot)
        self.audit_log.append({"event": "commit_applied", "slot_id": slot.slot_id, "replaced": decision.replacement_slot_id})
        return True

    def export_audit(self, path: str) -> None:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.audit_log, f, indent=2)
