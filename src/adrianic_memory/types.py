from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Mapping, Optional
import time
import numpy as np


class Decision(str, Enum):
    INCLUDE = "INCLUDE"
    EXCLUDE = "EXCLUDE"
    HOLD = "HOLD"


class RetrievalStatus(str, Enum):
    FOUND = "FOUND"
    HOLD_UNRESOLVED = "HOLD_UNRESOLVED"
    EMPTY = "EMPTY"


class ValueStatus(str, Enum):
    RESOLVED = "RESOLVED"
    VALUE_UNRESOLVED = "VALUE_UNRESOLVED"


@dataclass
class EvidenceAssessment:
    status: ValueStatus
    utility: Optional[float]
    effective_reliability: float
    weights: dict[str, float] = field(default_factory=dict)
    debiased_reports: dict[str, float] = field(default_factory=dict)
    reasons: list[str] = field(default_factory=list)


@dataclass
class CandidateSignals:
    support: int
    stability: float
    novelty: float
    recurrence: float = 0.0
    downstream_utility: Optional[float] = None
    consequence: float = 0.0
    interference: float = 0.0
    confidence: float = 1.0
    redundant: bool = False
    value_status: ValueStatus = ValueStatus.RESOLVED


@dataclass
class CommitDecision:
    decision: Decision
    reasons: list[str]
    value_score: Optional[float] = None
    replacement_slot_id: Optional[str] = None
    replacement_margin: Optional[float] = None


@dataclass
class MemorySlot:
    slot_id: str
    address: np.ndarray
    template: Optional[np.ndarray] = None
    metadata: dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_access: float = field(default_factory=time.time)
    estimated_future_utility: float = 0.0


@dataclass
class RetrievalResult:
    status: RetrievalStatus
    slot: Optional[MemorySlot]
    best_distance: Optional[float]
    second_distance: Optional[float]
    margin: Optional[float]
    audit: dict[str, Any] = field(default_factory=dict)
