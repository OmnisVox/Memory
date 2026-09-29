from __future__ import annotations

from dataclasses import asdict, dataclass
import csv
from pathlib import Path


@dataclass
class CausalLedgerEntry:
    """Audit schema recovered from the verification→memory causal-ablation study.

    The original causal-ablation ZIP contains the result ledger but not executable
    branch-cloning source.  This class therefore standardizes logging only; it does
    not claim to recreate that experiment.
    """

    event_id: str
    raw_anchor_error: float
    corrected_anchor_error: float
    anchor_changed: bool
    trust_path_distance: float = 0.0
    immediate_slot_state_changed: bool = False
    future_decision_path_changed: bool = False
    horizon_slot_state_changed: bool = False
    horizon_utility_delta: float = 0.0
    metadata: str = ""


class CausalAblationLedger:
    def __init__(self):
        self.entries: list[CausalLedgerEntry] = []

    def append(self, entry: CausalLedgerEntry) -> None:
        self.entries.append(entry)

    def to_rows(self) -> list[dict]:
        return [asdict(e) for e in self.entries]

    def export_csv(self, path: str | Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        rows = self.to_rows()
        fields = list(CausalLedgerEntry.__dataclass_fields__)
        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            writer.writerows(rows)
