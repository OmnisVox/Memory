from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import json
from pathlib import Path


FIXED_ROLES = ("active", "working", "bankA", "bankB")
V315_CANDIDATES = ("derivative", "predictor", "spin", "confidence", "parityP", "parityQ")
V315_RECORDED_WINNER = ("confidence", "parityP", "parityQ")
V316_PERSISTENT_ROLES = (
    "active",
    "working",
    "bankA",
    "bankB",
    "confidence",
    "parityP",
    "parityQ",
)


@dataclass(frozen=True)
class SearchWinner:
    trio: tuple[str, str, str]
    development_score: float | None
    heldout_score: float | None


def enumerate_v315_allocations() -> list[tuple[str, str, str]]:
    """All 20 ways to choose three flexible roles from the six v3.15 candidates."""
    return [tuple(x) for x in combinations(V315_CANDIDATES, 3)]


def load_v315_results(results_json: str | Path) -> SearchWinner:
    """Read the surviving original v3.15 result artifact without reconstructing its benchmark."""
    data = json.loads(Path(results_json).read_text(encoding="utf-8"))
    fc = data["fault_coupled_search"]
    ranked = fc["ranked"][0]
    held = fc["heldout"][0]
    trio = tuple(ranked["trio"].split("+"))
    if held["trio"] != ranked["trio"]:
        raise ValueError("development and held-out winners disagree")
    return SearchWinner(
        trio=trio,
        development_score=float(ranked["score"]),
        heldout_score=float(held["heldout_score"]),
    )
