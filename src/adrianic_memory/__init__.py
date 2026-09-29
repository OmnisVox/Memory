from .types import *
from .complex_field import ComplexMemoryField, ComplexFieldConfig
from .bank import AddressableMemoryBank, scaled_distance
from .timescale import SourceOfSurpriseController, TriageDecision, phase_invariant_overlap
from .evidence import EvidenceGraph, SourceState
from .consolidation import SelectiveCommitController, ValueWeights, ComparativeReplacementConfig
from .engine import AdrianicMemoryEngine
from .relational import RelationalMemory

__version__ = "0.3.0-canonical-reconstruction"

from .parity import DualParityGuard, ParitySyndrome, RepairResult
from .roles import V316_PERSISTENT_ROLES, V315_RECORDED_WINNER, enumerate_v315_allocations, load_v315_results
from .dependency import ResidualDependencyLearner, LatentCommonCauseModel, DependencyEdge

from .verification import RobustAnchorFilter, AnchorFilterResult
from .templates import DualRepresentationCandidate, TemplateStatus, finite_loop_winding
from .causal import CausalAblationLedger, CausalLedgerEntry
