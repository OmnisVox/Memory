import numpy as np
from adrianic_memory import (
    AddressableMemoryBank, AdrianicMemoryEngine, CandidateSignals,
    DualParityGuard, MemorySlot, SelectiveCommitController
)

bank = AddressableMemoryBank(capacity=2, scales=np.ones(3), min_margin=0.05)
engine = AdrianicMemoryEngine(bank, SelectiveCommitController())

slot = MemorySlot("m1", np.array([0.1, 0.2, 0.3]), estimated_future_utility=0.7)
signals = CandidateSignals(
    support=4, stability=0.97, novelty=0.3,
    recurrence=0.8, downstream_utility=0.9, consequence=0.5, interference=0.05
)
decision = engine.evaluate_candidate(signals)
engine.commit(slot, decision)
print("commit:", decision.decision.value)
print("retrieve:", engine.retrieve(np.array([0.11, 0.19, 0.31])).status.value)

guard = DualParityGuard()
z = np.array([0.2, -0.4, 1.1, 0.7])
p, q = guard.encode(z)
broken = z.copy(); broken[1] += 0.6
repair = guard.repair_single(broken, p, q)
print("parity repair:", repair.success, repair.corrected_index)
