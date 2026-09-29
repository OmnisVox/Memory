# Extracted verbatim code cells from Developmental_Agent_Informational_Softwalls_Lab_v10.ipynb
# Generated for inspection; notebook remains canonical experimental source.


# %% [notebook cell 1]
# =========================================
# 1. Imports, profiles, and output folders
# =========================================
import os, sys, json, math, random, copy, zipfile, hashlib, platform, itertools
from pathlib import Path
from dataclasses import dataclass, field
from collections import deque
from datetime import datetime

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from IPython.display import display

RUN_PROFILE = os.environ.get("V10_PROFILE", "standard")  # smoke | standard | deep
BASE_SEED = 314159

PROFILES = {
    "smoke": {
        "train_steps": 1050,
        "transfer_frozen_steps": 240,
        "transfer_adapt_steps": 520,
        "seeds": 2,
        "bootstrap_samples": 500,
        "replay_size": 850,
        "refit_every": 130,
        "source_seed_chunk": 150,
        "source_seed_warmup": 260,
        "risk_horizon": 32,
        "representation_horizons": [1, 4, 16, 64, 256],
        "min_factor_dim": 1,
        "v9_hard_cap": 7,
        "max_factor_dim": 12,
        "factor_cv_folds": 3,
        "factor_windows": 4,
        "factor_sparsity": 0.18,
        "persistence_floor": 0.06,
        "v9_birth_margin": 0.0020,
        "v9_growth_structure_floor": 0.38,
        "prune_margin": 0.004,
        "structure_patience": 2,
        "mass_learning_rate": 0.27,
        "growth_probe_width": 3,
        "softwall_center": 0.28,
        "softwall_scale": 0.12,
        "complexity_price": 0.0018,
        "drag_relief": 0.88,
        "max_structure_step": 2,
        "family_block": 60,
    },
    "standard": {
        "train_steps": 3200,
        "transfer_frozen_steps": 800,
        "transfer_adapt_steps": 2400,
        "seeds": 8,
        "bootstrap_samples": 5000,
        "replay_size": 2500,
        "refit_every": 260,
        "source_seed_chunk": 260,
        "source_seed_warmup": 520,
        "risk_horizon": 48,
        "representation_horizons": [1, 4, 16, 64, 256, 512, 1024],
        "min_factor_dim": 1,
        "v9_hard_cap": 10,
        "max_factor_dim": 18,
        "factor_cv_folds": 4,
        "factor_windows": 7,
        "factor_sparsity": 0.16,
        "persistence_floor": 0.05,
        "v9_birth_margin": 0.0015,
        "v9_growth_structure_floor": 0.36,
        "prune_margin": 0.0035,
        "structure_patience": 2,
        "mass_learning_rate": 0.22,
        "growth_probe_width": 4,
        "softwall_center": 0.27,
        "softwall_scale": 0.11,
        "complexity_price": 0.0015,
        "drag_relief": 0.90,
        "max_structure_step": 2,
        "family_block": 120,
    },
    "deep": {
        "train_steps": 16000,
        "transfer_frozen_steps": 3000,
        "transfer_adapt_steps": 10000,
        "seeds": 24,
        "bootstrap_samples": 20000,
        "replay_size": 9000,
        "refit_every": 700,
        "source_seed_chunk": 700,
        "source_seed_warmup": 1200,
        "risk_horizon": 72,
        "representation_horizons": [1, 4, 16, 64, 256, 1024, 2048],
        "min_factor_dim": 1,
        "v9_hard_cap": 10,
        "max_factor_dim": 24,
        "factor_cv_folds": 5,
        "factor_windows": 10,
        "factor_sparsity": 0.14,
        "persistence_floor": 0.04,
        "v9_birth_margin": 0.0012,
        "v9_growth_structure_floor": 0.32,
        "prune_margin": 0.0030,
        "structure_patience": 3,
        "mass_learning_rate": 0.18,
        "growth_probe_width": 5,
        "softwall_center": 0.25,
        "softwall_scale": 0.10,
        "complexity_price": 0.0012,
        "drag_relief": 0.92,
        "max_structure_step": 3,
        "family_block": 260,
    },
}

if RUN_PROFILE not in PROFILES:
    raise ValueError(f"Unknown V10_PROFILE={RUN_PROFILE!r}; expected one of {list(PROFILES)}")

cfg = PROFILES[RUN_PROFILE]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
base = Path("/content") if Path("/content").exists() else Path("/mnt/data") if Path("/mnt/data").exists() else Path(".")
ROOT = base / f"informational_softwalls_v10_{RUN_PROFILE}_{timestamp}"
DATA, FIG, REPORT, CHECKPOINTS = ROOT/"data", ROOT/"figures", ROOT/"report", ROOT/"checkpoints"
for folder in [ROOT, DATA, FIG, REPORT, CHECKPOINTS]: folder.mkdir(parents=True, exist_ok=True)

np.random.seed(BASE_SEED); random.seed(BASE_SEED)
print("Run profile:", RUN_PROFILE)
print("Source-development steps:", cfg["train_steps"])
print("Frozen-transfer steps:", cfg["transfer_frozen_steps"])
print("Adaptive-transfer steps:", cfg["transfer_adapt_steps"])
print("Seeds:", cfg["seeds"])
print("Representation horizons:", cfg["representation_horizons"])
print("Old v9 hard cap:", cfg["v9_hard_cap"])
print("v10 compute guardrail:", cfg["max_factor_dim"])
print("Output directory:", ROOT)



# %% [notebook cell 2]
# ==============================================
# 2. Events, hidden reality, and observed sensors
# ==============================================
ACTIONS = ["ignore", "analyze", "act", "act_analyze", "queue_analysis"]
CORE_NAMES = [
    "information_magnitude",
    "information_weight",
    "change_rate",
    "temporal_pressure",
    "irreversibility",
    "confidence",
    "novelty",
    "recurrence",
]
NUISANCE_NAMES = ["sensor_alpha", "sensor_beta", "sensor_gamma"]
OBSERVATION_NAMES = CORE_NAMES + NUISANCE_NAMES
HIDDEN_FACTORS = ["true_weight", "true_urgency", "true_learning"]
TARGET_FAMILIES = ["nuisance_flip", "delay_warp", "resource_sparse", "long_chain"]

SOURCE_PROFILES = {
    "dense_research":       dict(weight=.62, urgency=.12, learning=.92, complexity=.92, recurrence=.22),
    "safety_alarm":         dict(weight=.92, urgency=.92, learning=.20, complexity=.22, recurrence=.18),
    "slow_systemic_shift":  dict(weight=.88, urgency=.24, learning=.66, complexity=.55, recurrence=.62),
    "novel_anomaly":        dict(weight=.48, urgency=.48, learning=.88, complexity=.82, recurrence=.08),
    "recurring_noise":      dict(weight=.22, urgency=.28, learning=.20, complexity=.38, recurrence=.92),
    "resource_opportunity": dict(weight=.70, urgency=.36, learning=.58, complexity=.50, recurrence=.45),
    "fast_low_value":       dict(weight=.24, urgency=.90, learning=.18, complexity=.18, recurrence=.12),
}
SOURCE_NAMES = list(SOURCE_PROFILES)
SOURCE_PROBS = np.array([.18, .13, .17, .15, .14, .13, .10], dtype=float)
SOURCE_PROBS /= SOURCE_PROBS.sum()

TARGET_PROFILES = {
    "quiet_critical":       dict(weight=.95, urgency=.13, learning=.46, complexity=.38, recurrence=.30),
    "flash_noise":          dict(weight=.14, urgency=.95, learning=.14, complexity=.24, recurrence=.08),
    "dense_emergency":      dict(weight=.86, urgency=.84, learning=.90, complexity=.94, recurrence=.17),
    "slow_opportunity":     dict(weight=.70, urgency=.09, learning=.95, complexity=.86, recurrence=.46),
    "uncertain_hazard":     dict(weight=.77, urgency=.69, learning=.58, complexity=.90, recurrence=.06),
    "recurring_reversal":   dict(weight=.55, urgency=.35, learning=.65, complexity=.54, recurrence=.95),
    "sparse_catastrophe":   dict(weight=.98, urgency=.97, learning=.32, complexity=.50, recurrence=.02),
}
TARGET_NAMES = list(TARGET_PROFILES)
TARGET_PROBS = np.array([.16, .16, .16, .16, .15, .15, .06], dtype=float)
TARGET_PROBS /= TARGET_PROBS.sum()


def clip01(value):
    return float(np.clip(value, 0.0, 1.0))


def sigmoid(value):
    return float(1.0 / (1.0 + np.exp(-np.clip(value, -20.0, 20.0))))


def softmax(values):
    values = np.asarray(values, dtype=float)
    values = values - np.max(values)
    exp = np.exp(np.clip(values, -40.0, 40.0))
    return exp / np.maximum(exp.sum(), 1e-12)


@dataclass
class Event:
    event_id: int
    t: int
    phase: str
    regime: str
    world_family: str
    source: str

    information_magnitude: float
    information_weight: float
    change_rate: float
    time_to_consequence: float
    reversibility: float
    confidence: float
    novelty: float
    recurrence: float
    nuisance: tuple

    true_weight: float
    true_urgency: float
    true_learning: float
    complexity: float

    action_effectiveness: float
    analysis_effectiveness: float
    action_cost: float
    analysis_cost: float
    interruption_cost: float
    action_window: int


@dataclass
class WorldState:
    safety: float = .82
    resources: float = .80
    competence: float = .18
    uncertainty: float = .75
    pending: list = field(default_factory=list)
    analysis_queue: list = field(default_factory=list)
    lifetime: int = 0



# %% [notebook cell 3]
# =============================================================
# 3. Shared source world and the unseen transfer world families
# =============================================================
def generate_stream(seed, train_steps, frozen_steps, adapt_steps):
    """Create one exogenous stream shared by every representation fork.

    World-family labels, source labels, regimes, and hidden factors are retained
    only for evaluation. The policy sees numeric observations and internal state.
    """
    rng = np.random.default_rng(seed)
    total_steps = train_steps + frozen_steps + adapt_steps
    events = []

    for t in range(total_steps):
        if t < train_steps:
            phase = "train"
            fraction = t / train_steps
            if fraction < .35:
                regime = "source_balanced"
            elif fraction < .60:
                regime = "source_scarcity"
            elif fraction < .82:
                regime = "source_hazard_shift"
            else:
                regime = "source_nuisance_decorrelation"
            world_family = "source"
            source = rng.choice(SOURCE_NAMES, p=SOURCE_PROBS)
            profile = SOURCE_PROFILES[source].copy()

            if regime == "source_hazard_shift":
                if source == "fast_low_value":
                    profile.update(weight=.82, learning=.42)
                elif source == "dense_research":
                    profile.update(urgency=.60)
                elif source == "recurring_noise":
                    profile.update(weight=.53, learning=.61)
        else:
            phase_index = t - train_steps
            phase = "transfer_frozen" if phase_index < frozen_steps else "transfer_adapt"
            family_index = (phase_index // cfg["family_block"]) % len(TARGET_FAMILIES)
            world_family = TARGET_FAMILIES[family_index]
            source = rng.choice(TARGET_NAMES, p=TARGET_PROBS)
            profile = TARGET_PROFILES[source].copy()

            if world_family == "nuisance_flip":
                regime = "target_nuisance_reversal"
            elif world_family == "delay_warp":
                regime = "target_delay_shift"
            elif world_family == "resource_sparse":
                regime = "target_sparse_hazard" if (source == "sparse_catastrophe" or rng.random() < .22) else "target_resource_pressure"
            else:
                regime = "target_long_chain"

            if regime == "target_sparse_hazard" and source == "sparse_catastrophe":
                profile.update(weight=.995, urgency=.995)
            if world_family == "delay_warp" and source == "quiet_critical":
                profile.update(urgency=.24)

        index = (SOURCE_NAMES + TARGET_NAMES).index(source)
        wave = .07 * math.sin(2 * math.pi * t / 431.0 + index)
        true_weight = clip01(rng.normal(profile["weight"] + .22 * wave, .10))
        true_urgency = clip01(rng.normal(profile["urgency"] - .18 * wave, .10))
        true_learning = clip01(rng.normal(profile["learning"] + .14 * wave, .11))
        complexity = clip01(rng.normal(profile["complexity"], .09))
        recurrence = clip01(rng.normal(profile["recurrence"], .08))

        if world_family == "source":
            confidence = clip01(rng.normal(.78 - .28 * complexity + .12 * recurrence, .09))
            magnitude = clip01(.58 * complexity + .30 * true_learning + rng.normal(0, .10))
            weight_obs = clip01(true_weight + rng.normal(0, .15))
            change = clip01(true_urgency + rng.normal(0, .14))
            reversibility = clip01(1.0 - .72 * true_urgency + rng.normal(0, .11))
            delay = max(.08, float(rng.lognormal(np.log(.30 + 8.5 * (1 - true_urgency)), .20)))
        elif world_family == "nuisance_flip":
            confidence = clip01(rng.normal(.68 - .22 * complexity + .08 * recurrence, .12))
            magnitude = clip01(.48 * complexity + .34 * true_learning + .10 * true_urgency + rng.normal(0, .13))
            weight_obs = clip01(.82 * true_weight + .18 * true_learning + rng.normal(0, .17))
            change = clip01(.82 * true_urgency + .18 * complexity + rng.normal(0, .16))
            reversibility = clip01(1.0 - .65 * true_urgency + rng.normal(0, .14))
            delay = max(.08, float(rng.lognormal(np.log(.45 + 9.0 * (1 - true_urgency)), .24)))
        elif world_family == "delay_warp":
            confidence = clip01(rng.normal(.61 - .18 * complexity + .08 * recurrence, .13))
            magnitude = clip01(.39 * complexity + .39 * true_learning + .22 * true_urgency + rng.normal(0, .14))
            weight_obs = clip01(.67 * true_weight + .17 * true_learning + .16 * (1 - true_urgency) + rng.normal(0, .18))
            change = clip01(.54 * true_urgency + .26 * complexity + .20 * (1 - true_weight) + rng.normal(0, .18))
            reversibility = clip01(1.0 - .52 * true_urgency - .13 * true_weight + rng.normal(0, .16))
            # Long-delay cases deliberately scramble the old mapping between apparent
            # change and when consequences actually arrive.
            delay = max(.08, float(rng.lognormal(np.log(.75 + 15.5 * (1 - true_urgency)), .31)))
        elif world_family == "resource_sparse":
            confidence = clip01(rng.normal(.58 - .16 * complexity + .06 * recurrence, .14))
            magnitude = clip01(.36 * complexity + .34 * true_learning + .30 * true_urgency + rng.normal(0, .15))
            weight_obs = clip01(.60 * true_weight + .22 * true_learning + .18 * (1 - true_urgency) + rng.normal(0, .20))
            change = clip01(.62 * true_urgency + .22 * complexity + .16 * (1 - true_weight) + rng.normal(0, .19))
            reversibility = clip01(1.0 - .54 * true_urgency - .14 * true_weight + rng.normal(0, .16))
            delay = max(.08, float(rng.lognormal(np.log(.55 + 10.0 * (1 - true_urgency)), .28)))
        else:
            # Long-chain family: local observations remain noisy and only weakly reveal
            # which moderate-looking events will matter much later.
            confidence = clip01(rng.normal(.56 - .12 * complexity + .08 * recurrence, .14))
            magnitude = clip01(.30 * complexity + .32 * true_learning + .20 * true_weight + .18 * true_urgency + rng.normal(0, .16))
            weight_obs = clip01(.48 * true_weight + .18 * true_learning + .18 * recurrence + .16 * (1 - true_urgency) + rng.normal(0, .20))
            change = clip01(.38 * true_urgency + .24 * complexity + .20 * (1 - recurrence) + rng.normal(0, .20))
            reversibility = clip01(.84 - .30 * true_weight - .24 * true_urgency + rng.normal(0, .15))
            delay = max(.08, float(rng.lognormal(np.log(4.0 + 70.0 * (1 - true_urgency)), .34)))

        novelty = clip01(.62 * complexity + .24 * (1 - recurrence) + rng.normal(0, .10))

        # Accidental nuisance correlations exist early in source development, weaken
        # late in source development, and reverse/decorrelate in unseen families.
        if world_family == "source" and regime != "source_nuisance_decorrelation":
            nuisance_alpha = clip01(.72 * true_weight + .20 * true_learning + rng.normal(0, .15))
            nuisance_beta = clip01(.70 * true_urgency + .18 * complexity + rng.normal(0, .15))
            nuisance_gamma = clip01(.55 * recurrence + .25 * confidence + rng.normal(0, .18))
        elif world_family == "source":
            nuisance_alpha = clip01(rng.beta(2.0, 2.0))
            nuisance_beta = clip01(.55 * (1 - true_urgency) + rng.normal(0, .20))
            nuisance_gamma = clip01(rng.beta(1.8, 2.4))
        elif world_family == "nuisance_flip":
            nuisance_alpha = clip01(.76 * (1 - true_weight) + rng.normal(0, .12))
            nuisance_beta = clip01(.76 * (1 - true_urgency) + rng.normal(0, .12))
            nuisance_gamma = clip01(.68 * novelty + rng.normal(0, .16))
        elif world_family == "delay_warp":
            nuisance_alpha = clip01(.55 * true_urgency + rng.normal(0, .22))
            nuisance_beta = clip01(rng.beta(1.5, 2.1))
            nuisance_gamma = clip01(.55 * (1 - true_learning) + rng.normal(0, .20))
        elif world_family == "resource_sparse":
            nuisance_alpha = clip01(rng.beta(2.0, 2.0))
            nuisance_beta = clip01(rng.beta(1.6, 2.2))
            nuisance_gamma = clip01(rng.beta(2.4, 1.7))
        else:
            # Nuisance channels look temptingly structured but drift on a slower cycle.
            nuisance_alpha = clip01(.42 * true_learning + .30 * math.sin(2 * math.pi * t / 173.0) + .30 + rng.normal(0, .18))
            nuisance_beta = clip01(.44 * (1 - true_weight) + .25 * recurrence + rng.normal(0, .19))
            nuisance_gamma = clip01(.45 * confidence + .28 * (1 - true_urgency) + rng.normal(0, .18))

        if world_family == "long_chain":
            action_window = max(12, int(round(18 + 150 * (1 - true_urgency))))
        elif world_family == "delay_warp":
            action_window = max(1, int(round(1 + 17 * (1 - true_urgency))))
        else:
            action_window = max(1, int(round(1 + 11 * (1 - true_urgency))))
        action_effectiveness = clip01(rng.normal(.75 + .13 * confidence, .07))
        analysis_effectiveness = clip01(rng.normal(.63 + .20 * complexity, .07))
        scarcity = 1.70 if regime == "source_scarcity" else (1.62 if world_family == "resource_sparse" else (1.12 if world_family == "long_chain" else (1.20 if world_family != "source" else 1.0)))
        action_cost = max(.02, float(rng.normal((.07 + .10 * complexity) * scarcity, .018)))
        analysis_cost = max(.015, float(rng.normal((.05 + .09 * complexity) * scarcity, .016)))
        interruption_cost = max(0.0, float(rng.normal(.05 * (1 - true_urgency), .012)))

        events.append(Event(
            event_id=t, t=t, phase=phase, regime=regime, world_family=world_family, source=source,
            information_magnitude=magnitude, information_weight=weight_obs, change_rate=change,
            time_to_consequence=delay, reversibility=reversibility, confidence=confidence,
            novelty=novelty, recurrence=recurrence,
            nuisance=(nuisance_alpha, nuisance_beta, nuisance_gamma),
            true_weight=true_weight, true_urgency=true_urgency, true_learning=true_learning,
            complexity=complexity, action_effectiveness=action_effectiveness,
            analysis_effectiveness=analysis_effectiveness, action_cost=action_cost,
            analysis_cost=analysis_cost, interruption_cost=interruption_cost,
            action_window=action_window,
        ))

    return events



# %% [notebook cell 4]
# ====================================================
# 4. Structural dynamics and endogenous goal learning
# ====================================================
def world_deficits(world):
    pending_pressure = min(1.0, sum(item["hazard"] for item in world.pending) / 3.5)
    queue_pressure = min(1.0, len(world.analysis_queue) / 8.0)
    return np.array([
        1 - world.safety,
        1 - world.resources,
        1 - world.competence,
        world.uncertainty,
        pending_pressure,
        queue_pressure,
    ], dtype=float)


def observed_channels(event):
    return np.array([
        event.information_magnitude,
        event.information_weight,
        event.change_rate,
        1.0 / (1.0 + event.time_to_consequence),
        1.0 - event.reversibility,
        event.confidence,
        event.novelty,
        event.recurrence,
        *event.nuisance,
    ], dtype=float)


class RiskLearner:
    """Learns which internal deficits predict collapse over a delayed horizon."""
    def __init__(self, horizon):
        self.weights = np.array([.70, .70, .08, .05, .12, .03], dtype=float)
        self.initial_weights = self.weights.copy()
        self.bias = -2.20
        self.learning_rate = .028
        self.horizon = horizon
        self.buffer = []

    def risk(self, deficits):
        return sigmoid(self.bias + float(self.weights @ deficits))

    def update(self, deficits, t, collapsed, enabled=True):
        if not enabled:
            return 0
        self.buffer.append((deficits.copy(), t))
        labeled = []
        if collapsed:
            for sample, sample_t in self.buffer:
                age = t - sample_t
                if age <= self.horizon:
                    labeled.append((sample, max(.25, 1.0 - age / self.horizon)))
            self.buffer = []
        else:
            while self.buffer and t - self.buffer[0][1] >= self.horizon:
                sample, _ = self.buffer.pop(0)
                labeled.append((sample, 0.0))
        for sample, label in labeled:
            prediction = self.risk(sample)
            error = label - prediction
            self.bias += self.learning_rate * .35 * error
            self.weights += self.learning_rate * error * sample
            self.weights = np.clip(self.weights, 0.0, 4.0)
            self.bias = float(np.clip(self.bias, -6.0, 2.0))
        return len(labeled)


def apply_action(world, event, action_index):
    expired_harm = 0.0
    remaining = []
    for item in world.pending:
        item["steps_left"] -= 1
        if item["steps_left"] <= 0:
            expired_harm += item["hazard"]
            world.safety = clip01(world.safety - item["hazard"] * .10)
        else:
            remaining.append(item)
    world.pending = remaining

    queued_learning = 0.0
    queued_cost = 0.0
    if world.analysis_queue and world.resources > .04:
        item = world.analysis_queue.pop(0)
        queued_cost = item["cost"] * .90
        queued_learning = item["learning"] * .75 * (.65 + .35 * world.competence)
        world.resources = clip01(world.resources - queued_cost * .10)
        world.competence = clip01(world.competence + .052 * queued_learning * (1 - world.competence))
        world.uncertainty = clip01(world.uncertainty - .065 * queued_learning)

    if event.regime == "source_scarcity":
        recovery = .007
    elif event.world_family == "resource_sparse":
        recovery = .0065
    elif event.phase != "train":
        recovery = .009
    else:
        recovery = .013
    world.resources = clip01(world.resources + recovery)

    hazard_scale = 1.18 if event.regime == "target_sparse_hazard" else (1.10 if event.phase != "train" else 1.05)
    hazard = hazard_scale * event.true_weight * (.30 + .70 * event.true_urgency)
    acted = action_index in (2, 3)
    analyzed = action_index in (1, 3)
    queued = action_index == 4

    prevented = 0.0
    residual_harm = 0.0
    immediate_cost = 0.0
    immediate_learning = 0.0

    if analyzed:
        immediate_learning = event.true_learning * event.analysis_effectiveness * (.62 + .38 * world.competence)
        immediate_cost += event.analysis_cost
        world.resources = clip01(world.resources - event.analysis_cost * .10)
        world.competence = clip01(world.competence + .057 * immediate_learning * (1 - world.competence))
        world.uncertainty = clip01(world.uncertainty - .085 * immediate_learning)

    if acted:
        effectiveness = event.action_effectiveness * (.66 + .34 * world.competence) * (1.06 if analyzed else 1.0)
        prevented = min(hazard, hazard * effectiveness)
        residual_harm = hazard - prevented
        immediate_cost += event.action_cost + event.interruption_cost
        world.resources = clip01(world.resources - (event.action_cost + event.interruption_cost) * .12)
        world.safety = clip01(world.safety - residual_harm * .07)
    else:
        world.pending.append({"steps_left": event.action_window, "hazard": hazard})

    if queued:
        world.analysis_queue.append({
            "learning": event.true_learning * event.analysis_effectiveness,
            "cost": event.analysis_cost,
        })

    world.uncertainty = clip01(world.uncertainty + .006 + .012 * event.novelty - .018 * (analyzed or queued_learning > 0))
    world.lifetime += 1
    collapsed = world.safety <= .045 or world.resources <= .035

    return {
        "expired_harm": expired_harm,
        "queued_learning": queued_learning,
        "queued_cost": queued_cost,
        "hazard": hazard,
        "prevented_harm": prevented,
        "residual_harm": residual_harm,
        "immediate_cost": immediate_cost,
        "immediate_learning": immediate_learning,
        "acted": acted,
        "analyzed": analyzed,
        "queued": queued,
        "collapsed": collapsed,
    }



# %% [notebook cell 5]
# ==========================================================
# 5. Shared developmental history and consequence annotation
# ==========================================================
class CommonDevelopmentAgent:
    """Raw-observation agent used only to create one shared developmental history per seed."""
    def __init__(self, seed):
        self.rng = np.random.default_rng(seed)
        self.risk = RiskLearner(cfg["risk_horizon"])
        self.context_dim = 6 + 1 + len(OBSERVATION_NAMES)
        self.transition_model = np.zeros((len(ACTIONS), 6, self.context_dim), dtype=float)
        self.action_visits = np.zeros(len(ACTIONS), dtype=int)
        self.total_actions = 0
        self.replay = []

    def context(self, deficits, observed):
        return np.concatenate([deficits, [1.0], observed])

    def choose_action(self, world, event):
        deficits = world_deficits(world)
        observed = observed_channels(event)
        context = self.context(deficits, observed)
        scores = []
        for action_index in range(len(ACTIONS)):
            predicted = np.clip(deficits + self.transition_model[action_index] @ context, 0.0, 1.0)
            exploration = .07 * math.sqrt(math.log(self.total_actions + 2) / (self.action_visits[action_index] + 1))
            scores.append(-self.risk.risk(predicted) + exploration)
        epsilon = max(.03, .32 * math.exp(-self.total_actions / 750.0))
        action_index = int(self.rng.integers(len(ACTIONS))) if self.rng.random() < epsilon else int(np.argmax(scores))
        self.action_visits[action_index] += 1
        self.total_actions += 1
        return action_index, deficits, observed, self.risk.risk(deficits)

    def observe(self, item):
        context = self.context(item["before"], item["observed"])
        delta = item["after"] - item["before"]
        action_index = item["action_index"]
        error = delta - self.transition_model[action_index] @ context
        self.transition_model[action_index] += .024 * np.outer(error, context)
        self.transition_model[action_index] = np.clip(self.transition_model[action_index], -.8, .8)
        self.replay.append(item)


def annotate_consequence_targets(items, horizons):
    """Attach future consequence vectors using episode-local cumulative sums.

    Targets contain only experienced state changes and outcomes. Hidden factors and
    evaluation-only family labels never enter the target.
    """
    if not items:
        return items
    by_episode = {}
    for index, item in enumerate(items):
        by_episode.setdefault(item["episode_id"], []).append(index)

    outcome_keys = ["expired_harm", "prevented_harm", "residual_harm", "step_cost", "learning_gain", "collapsed"]
    for indices in by_episode.values():
        before = np.vstack([items[index]["before"] for index in indices])
        after = np.vstack([items[index]["after"] for index in indices])
        outcomes = np.array([[float(items[index][key]) for key in outcome_keys] for index in indices], dtype=float)
        cumulative = np.vstack([np.zeros((1, outcomes.shape[1])), np.cumsum(outcomes, axis=0)])
        episode_length = len(indices)
        for local_index, global_index in enumerate(indices):
            horizon_targets = {}
            for horizon in horizons:
                end_local = min(episode_length - 1, local_index + horizon - 1)
                deficit_change = after[end_local] - before[local_index]
                aggregate_outcomes = cumulative[end_local + 1] - cumulative[local_index]
                horizon_targets[horizon] = np.concatenate([deficit_change, aggregate_outcomes])
            items[global_index]["horizon_targets"] = horizon_targets
    return items


def develop_shared_history(seed, events):
    agent = CommonDevelopmentAgent(seed + 5000)
    world = WorldState()
    rows, lifetimes = [], []
    episode_id = 0

    for t, event in enumerate(events[:cfg["train_steps"]]):
        action_index, before, observed, predicted_risk = agent.choose_action(world, event)
        outcome = apply_action(world, event, action_index)
        after = world_deficits(world)
        step_cost = outcome["immediate_cost"] + outcome["queued_cost"]
        learning_gain = outcome["immediate_learning"] + outcome["queued_learning"]
        agent.observe({
            "t": t, "episode_id": episode_id,
            "before": before.copy(), "after": after.copy(), "observed": observed.copy(),
            "action_index": action_index,
            "expired_harm": outcome["expired_harm"], "prevented_harm": outcome["prevented_harm"],
            "residual_harm": outcome["residual_harm"], "step_cost": step_cost,
            "learning_gain": learning_gain, "collapsed": float(outcome["collapsed"]),
            "hidden": np.array([event.true_weight, event.true_urgency, event.true_learning]),
        })
        agent.risk.update(after, t, outcome["collapsed"], enabled=True)
        rows.append({
            "seed": seed, "t": t, "regime": event.regime, "action": ACTIONS[action_index],
            "predicted_risk": predicted_risk, "collapsed": outcome["collapsed"],
            "safety": world.safety, "resources": world.resources,
            "competence": world.competence, "uncertainty": world.uncertainty,
        })
        if outcome["collapsed"]:
            lifetimes.append(world.lifetime)
            episode_id += 1
            world = WorldState()

    if world.lifetime:
        lifetimes.append(world.lifetime)
    annotate_consequence_targets(agent.replay, cfg["representation_horizons"])
    summary = {
        "seed": seed,
        "source_collapses": int(sum(row["collapsed"] for row in rows)),
        "source_mean_lifetime": float(np.mean(lifetimes)),
        "source_final_safety": world.safety,
        "source_final_resources": world.resources,
        "source_final_competence": world.competence,
        "source_goal_drift": float(np.abs(agent.risk.weights - agent.risk.initial_weights).sum()),
        "replay_samples": len(agent.replay),
    }
    return agent, world, pd.DataFrame(rows), summary, episode_id



# %% [notebook cell 6]
# ======================================================================
# 6. v10 representation forks — informational softwalls / earned capacity
# ======================================================================
REPRESENTATIONS = [
    "collapsed_scalar",
    "raw_channels",
    "hand_factorized",
    "v8_smallest_sufficient_factors",
    "seed_one_factor",
    "seed_v9_hardwall",
    "seed_softwall_linear",
    "seed_softwall_full",
    "seed_softwall_no_prune",
    "seed_softwall_random_geometry",
]

FACTOR_REPRESENTATIONS = {
    "v8_smallest_sufficient_factors", "seed_one_factor", "seed_v9_hardwall",
    "seed_softwall_linear", "seed_softwall_full", "seed_softwall_no_prune",
    "seed_softwall_random_geometry",
}
SEED_REPRESENTATIONS = FACTOR_REPRESENTATIONS - {"v8_smallest_sufficient_factors"}
SOFTWALL_REPRESENTATIONS = {
    "seed_softwall_linear", "seed_softwall_full", "seed_softwall_no_prune", "seed_softwall_random_geometry"
}
NONLINEAR_REPRESENTATIONS = {"seed_softwall_full", "seed_softwall_no_prune", "seed_softwall_random_geometry"}

HAND_CORE_GROUPS_EVAL_ONLY = np.array([0, 1, 2, 2, 2, 3, 3, 3], dtype=int)


def hand_factor_values(observed):
    observed = np.asarray(observed, dtype=float)
    return np.array([observed[0], observed[1], np.mean(observed[2:5]), np.mean(observed[5:8])], dtype=float)


def stable_invsqrt(matrix, ridge=1e-6):
    values, vectors = np.linalg.eigh(matrix)
    return vectors @ np.diag(1.0 / np.sqrt(np.maximum(values, ridge))) @ vectors.T


def fit_ridge(x, y, ridge=.15):
    x, y = np.asarray(x,float), np.asarray(y,float)
    return np.linalg.solve(x.T@x + ridge*np.eye(x.shape[1]), x.T@y)


def varimax(loadings, gamma=1.0, max_iter=80, tol=1e-6):
    phi=np.asarray(loadings,float); p,k=phi.shape
    if k<=1: return phi.copy()
    rotation=np.eye(k); previous=0.0
    for _ in range(max_iter):
        rotated=phi@rotation
        grad=rotated**3-(gamma/max(p,1))*rotated@np.diag(np.diag(rotated.T@rotated))
        u,s,vh=np.linalg.svd(phi.T@grad,full_matrices=False); rotation=u@vh
        objective=float(s.sum())
        if previous>0 and objective<=previous*(1+tol): break
        previous=objective
    return phi@rotation


def adjusted_rand_index(labels_a, labels_b):
    a=np.asarray(labels_a); b=np.asarray(labels_b)
    _,a=np.unique(a,return_inverse=True); _,b=np.unique(b,return_inverse=True)
    table=np.zeros((a.max()+1,b.max()+1),dtype=int)
    for i,j in zip(a,b): table[i,j]+=1
    choose2=lambda v: float(np.sum(np.asarray(v,float)*(np.asarray(v,float)-1)/2))
    n=len(a); total=n*(n-1)/2
    if total<=0: return 0.0
    index=choose2(table.ravel()); rows=choose2(table.sum(axis=1)); cols=choose2(table.sum(axis=0))
    expected=rows*cols/total; maximum=.5*(rows+cols)
    return float((index-expected)/(maximum-expected)) if abs(maximum-expected)>1e-12 else 0.0


def align_rows_to_previous(new_basis, old_basis, old_count):
    new_basis=np.asarray(new_basis,float).copy()
    if old_count<=0 or len(new_basis)==0: return new_basis
    old=np.asarray(old_basis[:old_count],float); used=set(); ordered=[]
    for old_row in old:
        best_j,best_score=None,-1.0
        for j,new_row in enumerate(new_basis):
            if j in used: continue
            score=abs(float(old_row@new_row)/max(np.linalg.norm(old_row)*np.linalg.norm(new_row),1e-9))
            if score>best_score: best_j,best_score=j,score
        if best_j is None: break
        row=new_basis[best_j].copy()
        if float(old_row@row)<0: row*=-1
        ordered.append(row); used.add(best_j)
    ordered.extend([new_basis[j].copy() for j in range(len(new_basis)) if j not in used])
    return np.vstack(ordered) if ordered else new_basis


# Generic nonlinear substrate. These features contain no semantic labels and are never
# hand-ranked. They merely remove the old assumption that useful latent dimensionality
# cannot exceed the raw-sensor rank.
RAW_FEATURE_NAMES = [f"raw:{name}" for name in OBSERVATION_NAMES]
SQUARE_FEATURE_NAMES = [f"signed_square:{name}" for name in OBSERVATION_NAMES]
PAIR_FEATURE_NAMES = [f"interaction:{OBSERVATION_NAMES[i]}*{OBSERVATION_NAMES[j]}" for i in range(len(OBSERVATION_NAMES)) for j in range(i+1,len(OBSERVATION_NAMES))]
GENERIC_FEATURE_NAMES = RAW_FEATURE_NAMES + SQUARE_FEATURE_NAMES + PAIR_FEATURE_NAMES


def generic_feature_map(x):
    x=np.asarray(x,float); one=x.ndim==1
    if one: x=x[None,:]
    raw=x
    square=x*np.abs(x)
    pairs=np.column_stack([x[:,i]*x[:,j] for i in range(x.shape[1]) for j in range(i+1,x.shape[1])])
    out=np.concatenate([raw,square,pairs],axis=1)
    out=np.clip(out,-8.0,8.0)
    return out[0] if one else out


def feature_nuisance_mask(names):
    nuisance=set(NUISANCE_NAMES); mask=[]
    for name in names:
        mask.append(any(token in name for token in nuisance))
    return np.asarray(mask,dtype=bool)


class RepresentationFork:
    def __init__(self, representation, replay, frozen_risk, seed):
        self.name=representation; self.rng=np.random.default_rng(seed); self.risk=copy.deepcopy(frozen_risk)
        self.is_factor=representation in FACTOR_REPRESENTATIONS
        self.is_seed=representation in SEED_REPRESENTATIONS
        self.uses_nonlinear=representation in NONLINEAR_REPRESENTATIONS
        self.feature_names = GENERIC_FEATURE_NAMES if self.uses_nonlinear else RAW_FEATURE_NAMES
        self.substrate_dim=len(self.feature_names)
        self.nuisance_feature_mask=feature_nuisance_mask(self.feature_names)

        self.dim = cfg["max_factor_dim"] if self.is_factor else (4 if representation in {"collapsed_scalar","hand_factorized"} else len(OBSERVATION_NAMES))
        self.context_dim=6+1+self.dim
        self.transition_model=np.zeros((len(ACTIONS),6,self.context_dim),float)
        self.action_visits=np.zeros(len(ACTIONS),int); self.total_actions=cfg["train_steps"]
        self.buffer=deque(maxlen=cfg["replay_size"])

        self.factor_loadings=np.zeros((cfg["max_factor_dim"],self.substrate_dim),float)
        random_initial=self.rng.normal(0,1,(self.substrate_dim,cfg["max_factor_dim"]))
        self.random_master_basis=np.linalg.qr(random_initial)[0].T[:cfg["max_factor_dim"]]
        self.factor_count_selected=1 if self.is_seed else cfg["min_factor_dim"]
        self.active_dim=self.factor_count_selected if self.is_factor else self.dim
        self.factor_mass=np.zeros(cfg["max_factor_dim"],float); self.factor_mass[0]=.65
        self.factor_age=np.zeros(cfg["max_factor_dim"],int)
        self.factor_cv_error=np.nan; self.factor_candidate_scores=[]; self.source_factor_candidate_scores=[]
        self.channel_weights=np.ones(self.substrate_dim,float); self.source_channel_weights=self.channel_weights.copy()
        self.association_singulars=np.zeros(cfg["max_factor_dim"],float)
        self.structure_events=[]; self.structure_state_history=[]; self.representation_churn=[]
        self.birth_evidence=0; self.prune_evidence=0; self.structure_refit_index=0; self.refit_count=0
        self.informational_drag=0.0; self.softwall_dim=1; self.desired_dim=1; self.complexity_price=cfg["complexity_price"]
        self.tail_share=0.0; self.direct_gain=0.0
        self.obs_mean=np.full(len(OBSERVATION_NAMES),.5); self.obs_std=np.full(len(OBSERVATION_NAMES),.3)
        self.ood_center=1.0; self.ood_scale=.25

        if self.is_seed:
            self._develop_seed_from_history(copy.deepcopy(replay))
        elif representation=="v8_smallest_sufficient_factors":
            self.buffer.extend(copy.deepcopy(replay[-cfg["replay_size"]:]))
            self.refit_models(initial_fit=True,stage="source_end",t=cfg["train_steps"]-1)
        else:
            self.buffer.extend(copy.deepcopy(replay[-cfg["replay_size"]:]))
            self.refit_models(initial_fit=True,stage="source_end",t=cfg["train_steps"]-1)

        self.source_factor_loadings=self.factor_loadings.copy(); self.source_factor_count=int(self.factor_count_selected)
        self.source_factor_mass=self.factor_mass.copy(); self.source_factor_cv_error=float(self.factor_cv_error) if np.isfinite(self.factor_cv_error) else np.nan
        self.source_factor_candidate_scores=copy.deepcopy(self.factor_candidate_scores)
        self.source_channel_weights=self.channel_weights.copy(); self.source_structure_event_count=len(self.structure_events)
        self.source_informational_drag=float(self.informational_drag); self.source_softwall_dim=int(self.softwall_dim)

    def _develop_seed_from_history(self,replay):
        if not replay: return
        warm=min(cfg["source_seed_warmup"],len(replay)); self.buffer.extend(copy.deepcopy(replay[:warm]))
        self.refit_models(initial_fit=True,stage="source_seed",t=replay[warm-1]["t"])
        for start in range(warm,len(replay),cfg["source_seed_chunk"]):
            chunk=replay[start:start+cfg["source_seed_chunk"]]; self.buffer.extend(copy.deepcopy(chunk))
            self.refit_models(initial_fit=False,stage="source_seed",t=chunk[-1]["t"])

    def _normalize(self,observed): return (np.asarray(observed,float)-self.obs_mean)/(self.obs_std+1e-6)
    def _substrate(self,normalized): return generic_feature_map(normalized) if self.uses_nonlinear else np.asarray(normalized,float)

    def represent(self,observed):
        observed=np.asarray(observed,float)
        if self.name=="collapsed_scalar":
            score=float(observed.mean()); return np.array([score,observed.std(),observed.max(),score**2])
        if self.name=="hand_factorized": return hand_factor_values(observed)
        if self.name=="raw_channels": return observed.copy()
        normalized=self._normalize(observed); substrate=self._substrate(normalized)
        z=self.factor_loadings@substrate
        scale=np.sqrt(np.clip(self.factor_mass,.05,3.0)); z=z*scale; z[self.factor_count_selected:]=0.0
        return z

    def representation_uncertainty(self,observed):
        normalized=self._normalize(observed); distance=float(np.sqrt(np.mean(normalized**2)))
        structural=.10*float(self.informational_drag)
        if self.is_factor:
            mass=self.factor_mass[:max(1,self.factor_count_selected)]
            structural+=.08*float(np.std(mass)/max(np.mean(mass),.1))
        return clip01(sigmoid((distance-self.ood_center)/max(self.ood_scale,.05))+structural)

    def context(self,deficits,observed): return np.concatenate([deficits,[1.0],self.represent(observed)])

    def _valid_targets(self,items):
        valid=[]; per={h:[] for h in cfg["representation_horizons"]}
        for index,item in enumerate(items):
            targets=item.get("horizon_targets",{})
            if all(h in targets for h in cfg["representation_horizons"]):
                valid.append(index)
                for h in cfg["representation_horizons"]: per[h].append(targets[h])
        return np.asarray(valid,int),{h:np.vstack(rows) if rows else np.empty((0,0)) for h,rows in per.items()}

    def _standardize_targets(self,matrices):
        return {h:(m-m.mean(axis=0))/np.maximum(m.std(axis=0),.03) for h,m in matrices.items()}

    def _action_expand(self,items,valid_indices,targets):
        expanded=np.zeros((len(valid_indices),len(ACTIONS)*targets.shape[1])); width=targets.shape[1]
        for row,item_index in enumerate(valid_indices):
            a=items[item_index]["action_index"]; expanded[row,a*width:(a+1)*width]=targets[row]
        return expanded

    def _multi_horizon_target(self,items,valid_indices,standardized):
        combined=np.concatenate([standardized[h] for h in cfg["representation_horizons"]],axis=1)
        return self._action_expand(items,valid_indices,combined)

    def _persistent_feature_weights(self,x,target):
        windows=np.array_split(np.arange(len(x)),cfg["factor_windows"]); strengths=[]; directions=[]
        for idx in windows:
            if len(idx)<18: continue
            xw=x[idx]-x[idx].mean(axis=0); yw=target[idx]-target[idx].mean(axis=0)
            cross=xw.T@yw/max(len(idx),1); strength=np.linalg.norm(cross,axis=1); direction=cross/np.maximum(strength[:,None],1e-9)
            strengths.append(strength); directions.append(direction)
        if len(strengths)<2: return np.ones(x.shape[1])
        strengths=np.vstack(strengths); directions=np.stack(directions); relative=np.median(strengths,axis=0)
        relative/=max(float(relative.max()),1e-8); persistence=np.zeros(x.shape[1])
        for c in range(x.shape[1]):
            sims=[float(directions[i,c]@directions[j,c]) for i in range(len(directions)) for j in range(i+1,len(directions))]
            persistence[c]=max(0.0,float(np.median(sims))) if sims else 0.0
        weights=np.sqrt(np.clip(relative*persistence,0,1)); weights=np.where(weights<cfg["persistence_floor"],.02,weights)
        return np.clip(weights,.02,1.0)

    def _cca_basis(self,x,target,weights,max_dim):
        xeff=x*weights; cxx=xeff.T@xeff/len(xeff)+.16*np.eye(xeff.shape[1]); invx=stable_invsqrt(cxx)
        block_dim=target.shape[1]//len(ACTIONS); blocks=[]
        for a in range(len(ACTIONS)):
            y=target[:,a*block_dim:(a+1)*block_dim]; cyy=y.T@y/len(y)+.20*np.eye(block_dim)
            cxy=xeff.T@y/len(xeff); blocks.append(invx@cxy@stable_invsqrt(cyy))
        whitened=np.concatenate(blocks,axis=1); left,singulars,_=np.linalg.svd(whitened,full_matrices=False)
        take=min(max_dim,left.shape[1],x.shape[1]); basis=left[:,:take].T@invx@np.diag(weights)
        basis/=np.maximum(np.linalg.norm(basis,axis=1,keepdims=True),1e-8)
        return basis,singulars[:take]

    def _sparsify(self,dense,masses=None):
        rotated=varimax(dense.T).T; sparse=rotated.copy(); masses=np.ones(len(sparse)) if masses is None else masses
        for row in range(len(sparse)):
            maximum=float(np.max(np.abs(sparse[row]))); threshold=cfg["factor_sparsity"]*maximum/math.sqrt(max(float(masses[row]),.18))
            threshold=float(np.clip(threshold,.07*maximum,.40*maximum)); sparse[row,np.abs(sparse[row])<threshold]=0.0
            if not np.any(np.abs(sparse[row])>0): sparse[row,int(np.argmax(np.abs(rotated[row])))]=rotated[row,int(np.argmax(np.abs(rotated[row])))]
            sparse[row]/=max(float(np.linalg.norm(sparse[row])),1e-9)
        return sparse

    def _factor_cv_error(self,z,target,items,valid_indices):
        n=len(z); folds=np.arange(n)%cfg["factor_cv_folds"]; actions=np.array([items[i]["action_index"] for i in valid_indices],int)
        onehot=np.eye(len(ACTIONS))[actions]; pieces=[]
        for a in range(len(ACTIONS)):
            gate=onehot[:,[a]]; pieces.extend([gate,gate*z])
        design=np.concatenate(pieces,axis=1); errors=[]
        for fold in range(cfg["factor_cv_folds"]):
            train,test=folds!=fold,folds==fold
            if train.sum()<design.shape[1]+8 or test.sum()<4: continue
            beta=fit_ridge(design[train],target[train],ridge=.25); pred=design[test]@beta
            errors.append(float(np.mean((target[test]-pred)**2)))
        if not errors: return np.inf,np.inf
        return float(np.mean(errors)),float(np.std(errors,ddof=1)/math.sqrt(len(errors))) if len(errors)>1 else 0.0

    def _usage_from_basis(self,x,target,basis):
        if len(basis)==0: return np.empty(0)
        z=x@basis.T; design=np.column_stack([np.ones(len(z)),z]); beta=fit_ridge(design,target,ridge=.22)
        usage=np.std(z,axis=0)*np.linalg.norm(beta[1:],axis=1)
        if not np.isfinite(usage).all() or float(usage.max(initial=0))<=1e-12: return np.ones(len(basis))
        return usage/max(float(usage.max()),1e-12)

    def _base_geometry(self,x,target):
        weights=self._persistent_feature_weights(x,target); self.channel_weights=weights
        dense,singulars=self._cca_basis(x,target,weights,cfg["max_factor_dim"])
        self.association_singulars[:]=0; self.association_singulars[:len(singulars)]=singulars
        return dense,singulars

    def _candidate(self,dense,k,x,target,items,valid_indices):
        k=int(np.clip(k,1,min(cfg["max_factor_dim"],len(dense))))
        masses=np.ones(k); masses[:min(k,len(self.factor_mass))]=np.maximum(self.factor_mass[:min(k,len(self.factor_mass))],.35)
        basis=self._sparsify(dense[:k],masses)
        if self.is_seed and self.refit_count: basis=align_rows_to_previous(basis,self.factor_loadings,min(self.factor_count_selected,k))
        z=x@basis.T; error,se=self._factor_cv_error(z,target,items,valid_indices)
        return {"basis":basis,"cv_error":error,"cv_se":se,"association_sum":float(np.sum(self.association_singulars[:k]))}

    def _record_state(self,stage,t,old_k,new_k,event):
        self.structure_state_history.append({
            "representation":self.name,"stage":stage,"t":int(t) if t is not None else -1,"refit_index":int(self.structure_refit_index),
            "event":event,"old_dim":int(old_k),"new_dim":int(new_k),"informational_drag":float(self.informational_drag),
            "softwall_dim":int(self.softwall_dim),"desired_dim":int(self.desired_dim),"complexity_price":float(self.complexity_price),
            "tail_share":float(self.tail_share),"direct_gain":float(self.direct_gain),"cv_error":float(self.factor_cv_error) if np.isfinite(self.factor_cv_error) else np.nan,
        })
        if event!="stable": self.structure_events.append(self.structure_state_history[-1].copy())

    def _install_basis(self,basis,k,x,target,stage,t,event,old_k):
        learned=basis.copy(); installed=self.random_master_basis[:k].copy() if self.name=="seed_softwall_random_geometry" else learned
        usage=self._usage_from_basis(x,target,learned); lr=cfg["mass_learning_rate"]; new_mass=self.factor_mass.copy()
        if k:
            target_mass=.35+1.85*usage; new_mass[:k]=(1-lr)*np.maximum(new_mass[:k],.35)+lr*target_mass; new_mass[:k]=np.clip(new_mass[:k],.18,2.8)
        new_mass[k:]=0.0; self.factor_age[:k]+=1; self.factor_age[k:]=0
        old=self.factor_loadings.copy(); self.factor_loadings[:]=0; self.factor_loadings[:k]=installed; self.factor_mass=new_mass
        self.factor_count_selected=self.active_dim=k
        common=min(old_k,k)
        if common: self.representation_churn.append(float(np.mean(np.linalg.norm(old[:common]-self.factor_loadings[:common],axis=1))))
        self._record_state(stage,t,old_k,k,event)

    def _apply_v9_hardwall(self,dense,x,target,items,valid_indices,stage,t):
        old_k=int(self.factor_count_selected); cap=min(cfg["v9_hard_cap"],len(dense)); k=min(old_k,cap)
        current=self._candidate(dense,k,x,target,items,valid_indices); denom=max(abs(current["cv_error"]),1e-8)
        grow_signal=False
        if self.name!="seed_one_factor" and k<cap:
            grow=self._candidate(dense,k+1,x,target,items,valid_indices)
            relative_gain=(current["cv_error"]-grow["cv_error"])/denom
            added=max(0.0,grow["association_sum"]-current["association_sum"]); first=max(float(self.association_singulars[0]),1e-8)
            residual=added/first; noninferior=grow["cv_error"]<=current["cv_error"]+.5*max(current["cv_se"],grow["cv_se"],1e-6)
            grow_signal=(relative_gain>cfg["v9_birth_margin"]) or (residual>cfg["v9_growth_structure_floor"] and noninferior)
        self.birth_evidence=self.birth_evidence+1 if grow_signal else max(0,self.birth_evidence-1)
        prune_signal=False
        if k>1 and self.name!="seed_one_factor":
            pr=self._candidate(dense,k-1,x,target,items,valid_indices); prune_signal=((pr["cv_error"]-current["cv_error"])/denom)<cfg["prune_margin"]
        self.prune_evidence=self.prune_evidence+1 if prune_signal else max(0,self.prune_evidence-1)
        event="stable"
        if self.name!="seed_one_factor" and self.birth_evidence>=cfg["structure_patience"] and k<cap: k+=1; event="birth"; self.birth_evidence=self.prune_evidence=0
        elif self.name!="seed_one_factor" and self.prune_evidence>=cfg["structure_patience"] and k>1: k-=1; event="prune"; self.birth_evidence=self.prune_evidence=0
        chosen=self._candidate(dense,k,x,target,items,valid_indices); self.factor_cv_error=float(chosen["cv_error"])
        self.informational_drag=0.0; self.softwall_dim=cap; self.desired_dim=k; self.complexity_price=cfg["complexity_price"]; self.tail_share=0.0; self.direct_gain=0.0
        self.factor_candidate_scores=[{"factor_count":k,"cv_error":chosen["cv_error"],"cv_se":chosen["cv_se"],"score":np.nan}]
        self._install_basis(chosen["basis"],k,x,target,stage,t,event,old_k)

    def _apply_softwall(self,dense,singulars,x,target,items,valid_indices,stage,t):
        old_k=int(np.clip(self.factor_count_selected,1,len(dense))); current=self._candidate(dense,old_k,x,target,items,valid_indices)
        denom=max(abs(float(current["cv_error"])),1e-8); max_dim=min(cfg["max_factor_dim"],len(dense))
        probe_k=min(max_dim,old_k+cfg["growth_probe_width"]); probe=self._candidate(dense,probe_k,x,target,items,valid_indices)
        self.direct_gain=max(0.0,(current["cv_error"]-probe["cv_error"])/denom)
        total=float(np.sum(np.maximum(singulars,0)))+1e-9; self.tail_share=float(np.sum(np.maximum(singulars[old_k:probe_k],0))/total)
        active_mass=self.factor_mass[:old_k]; mass_pressure=float(np.clip(np.mean(active_mass)/2.2,0,1)) if len(active_mass) else 0.0
        gain_pressure=float(np.clip(self.direct_gain/.025,0,1)); tail_pressure=float(np.clip(self.tail_share/.16,0,1))
        self.informational_drag=float(np.clip(.48*tail_pressure+.42*gain_pressure+.10*mass_pressure,0,1))

        logistic=1/(1+math.exp(-(self.informational_drag-cfg["softwall_center"])/max(cfg["softwall_scale"],1e-6)))
        self.softwall_dim=int(np.clip(1+math.ceil((max_dim-1)*logistic),1,max_dim))
        self.complexity_price=float(cfg["complexity_price"]*(1-cfg["drag_relief"]*self.informational_drag))
        self.complexity_price=max(self.complexity_price,cfg["complexity_price"]*.05)

        lo=max(1,min(old_k-2,self.softwall_dim)); hi=min(max_dim,max(self.softwall_dim,old_k+min(cfg["growth_probe_width"],3)))
        counts=set(range(lo,hi+1)); counts.update([1,old_k,self.softwall_dim,probe_k]); counts=sorted(k for k in counts if 1<=k<=max_dim)
        candidates={k:self._candidate(dense,k,x,target,items,valid_indices) for k in counts}
        scores=[]
        for k,cand in candidates.items():
            relative_error=cand["cv_error"]/denom
            score=relative_error+self.complexity_price*(k-1)
            scores.append({"factor_count":k,"cv_error":cand["cv_error"],"cv_se":cand["cv_se"],"score":score})
        self.factor_candidate_scores=scores
        allowed=[row for row in scores if row["factor_count"]<=self.softwall_dim]
        if not allowed: allowed=[min(scores,key=lambda r:r["factor_count"])]
        desired=min(allowed,key=lambda r:r["score"])["factor_count"]
        self.desired_dim=int(desired)

        grow_signal=desired>old_k; prune_signal=desired<old_k and self.name!="seed_softwall_no_prune"
        self.birth_evidence=self.birth_evidence+1 if grow_signal else max(0,self.birth_evidence-1)
        self.prune_evidence=self.prune_evidence+1 if prune_signal else max(0,self.prune_evidence-1)
        k=old_k; event="stable"
        if self.birth_evidence>=cfg["structure_patience"] and desired>old_k:
            step=min(cfg["max_structure_step"],desired-old_k); k=min(old_k+step,self.softwall_dim); event="birth"; self.birth_evidence=self.prune_evidence=0
        elif self.prune_evidence>=cfg["structure_patience"] and desired<old_k and self.name!="seed_softwall_no_prune":
            step=min(cfg["max_structure_step"],old_k-desired); k=max(1,old_k-step); event="prune"; self.birth_evidence=self.prune_evidence=0
        if self.softwall_dim<k and self.name!="seed_softwall_no_prune": k=max(self.softwall_dim,1); event="prune"
        chosen=candidates.get(k) or self._candidate(dense,k,x,target,items,valid_indices); self.factor_cv_error=float(chosen["cv_error"])
        self._install_basis(chosen["basis"],k,x,target,stage,t,event,old_k)

    def _discover_v8(self,dense,x,target,items,valid_indices):
        cap=min(cfg["v9_hard_cap"],len(dense)); candidates={k:self._candidate(dense,k,x,target,items,valid_indices) for k in range(1,cap+1)}
        rows=[{"factor_count":k,"cv_error":c["cv_error"],"cv_se":c["cv_se"],"score":np.nan} for k,c in candidates.items()]
        best=min(rows,key=lambda r:r["cv_error"]); threshold=best["cv_error"]+best["cv_se"]
        chosen=min([r for r in rows if r["cv_error"]<=threshold],key=lambda r:r["factor_count"]); k=chosen["factor_count"]
        self.factor_loadings[:]=0; self.factor_loadings[:k]=candidates[k]["basis"]; self.factor_count_selected=self.active_dim=k
        self.factor_mass[:]=0; self.factor_mass[:k]=1.0; self.factor_cv_error=float(chosen["cv_error"]); self.factor_candidate_scores=rows
        self.softwall_dim=cap; self.desired_dim=k

    def discover_representation(self,items,normalized,stage,t):
        valid,matrices=self._valid_targets(items)
        if len(valid)<90: return
        raw=normalized[valid]; substrate=self._substrate(raw); standardized=self._standardize_targets(matrices); target=self._multi_horizon_target(items,valid,standardized)
        dense,singulars=self._base_geometry(substrate,target)
        if len(dense)<1: return
        if self.name=="v8_smallest_sufficient_factors": self._discover_v8(dense,substrate,target,items,valid); return
        if self.name in {"seed_one_factor","seed_v9_hardwall"}: self._apply_v9_hardwall(dense,substrate,target,items,valid,stage,t); return
        if self.name in SOFTWALL_REPRESENTATIONS: self._apply_softwall(dense,singulars,substrate,target,items,valid,stage,t); return

    def refit_models(self,initial_fit=False,stage="transfer",t=None):
        items=list(self.buffer); annotate_consequence_targets(items,cfg["representation_horizons"])
        if items:
            obs=np.vstack([item["observed"] for item in items]); self.obs_mean=obs.mean(axis=0); self.obs_std=np.maximum(obs.std(axis=0),.05)
            normalized=(obs-self.obs_mean)/self.obs_std; distances=np.sqrt(np.mean(normalized**2,axis=1))
            self.ood_center=float(np.median(distances)); self.ood_scale=float(max(np.median(np.abs(distances-self.ood_center))*1.4826,.08))
            if self.is_factor:
                self.structure_refit_index+=1; self.discover_representation(items,normalized,stage,t)
        ridge=.18 if self.name=="raw_channels" else .10
        for a in range(len(ACTIONS)):
            ai=[item for item in items if item["action_index"]==a]
            if len(ai)<18: continue
            x=np.vstack([self.context(item["before"],item["observed"]) for item in ai]); y=np.vstack([item["after"]-item["before"] for item in ai])
            self.transition_model[a]=fit_ridge(x,y,ridge=ridge).T
        self.refit_count+=1

    def choose_action(self,world,event):
        deficits=world_deficits(world); observed=observed_channels(event); context=self.context(deficits,observed); rep_unc=self.representation_uncertainty(observed)
        scores=[]
        for a in range(len(ACTIONS)):
            predicted=np.clip(deficits+self.transition_model[a]@context,0,1)
            exploration=.045*math.sqrt(math.log(self.total_actions+2)/(self.action_visits[a]+1)); info_bonus=.020*rep_unc if a in (1,3,4) else 0.0
            scores.append(-self.risk.risk(predicted)+exploration+info_bonus)
        a=int(self.rng.integers(len(ACTIONS))) if self.rng.random()<.02 else int(np.argmax(scores)); self.action_visits[a]+=1; self.total_actions+=1
        return a,deficits,observed,self.risk.risk(deficits),rep_unc

    def observe(self,item): self.buffer.append(item)

    def nuisance_loading_fraction(self,source=True):
        if not self.is_factor: return np.nan
        matrix=self.source_factor_loadings if source else self.factor_loadings; count=self.source_factor_count if source else self.factor_count_selected
        active=np.abs(matrix[:max(1,count)]); total=float(active.sum()); nuisance=float(active[:,self.nuisance_feature_mask].sum())
        return nuisance/max(total,1e-12)

    def hand_group_ari(self,source=True):
        if not self.is_factor or self.uses_nonlinear or self.name=="seed_softwall_random_geometry": return np.nan
        matrix=self.source_factor_loadings if source else self.factor_loadings; count=self.source_factor_count if source else self.factor_count_selected
        active=matrix[:max(1,count),:len(CORE_NAMES)]; labels=[]
        for channel in range(len(CORE_NAMES)):
            col=np.abs(active[:,channel]); labels.append(-1 if float(col.max())<.04 else int(np.argmax(col)))
        return adjusted_rand_index(HAND_CORE_GROUPS_EVAL_ONLY,labels)

    def mass_entropy(self):
        m=self.factor_mass[:max(1,self.factor_count_selected)]
        if m.sum()<=0:return 0.0
        p=m/m.sum(); return float(-np.sum(p*np.log(np.maximum(p,1e-12)))/max(math.log(len(p)),1e-12)) if len(p)>1 else 0.0

    def support_size(self):
        if not self.is_factor:return np.nan
        return float(np.sum(np.abs(self.factor_loadings[:self.factor_count_selected])>1e-10))



# %% [notebook cell 7]
# =====================================================
# 7. Paired transfer + developmental-structure diagnostics
# =====================================================
def ridge_probe(train_x,train_y,test_x,test_y,ridge=.10):
    train_x,train_y,test_x,test_y=map(lambda z:np.asarray(z,float),(train_x,train_y,test_x,test_y))
    tr=np.column_stack([np.ones(len(train_x)),train_x]); te=np.column_stack([np.ones(len(test_x)),test_x])
    beta=np.linalg.solve(tr.T@tr+ridge*np.eye(tr.shape[1]),tr.T@train_y); pred=te@beta
    den=np.sum((test_y-test_y.mean(axis=0))**2,axis=0); num=np.sum((test_y-pred)**2,axis=0)
    return 1.0-num/np.maximum(den,1e-9)


def action_entropy(actions):
    counts=pd.Series(actions).value_counts(normalize=True).values
    return float(-np.sum(counts*np.log(np.maximum(counts,1e-12)))/math.log(len(ACTIONS)))


def horizon_probe_errors(fork,items):
    items=copy.deepcopy(list(items)); annotate_consequence_targets(items,cfg["representation_horizons"]); out=[]
    for h in cfg["representation_horizons"]:
        valid=[item for item in items if h in item.get("horizon_targets",{})]
        if len(valid)<70: continue
        z=np.vstack([fork.represent(item["observed"]) for item in valid]); y=np.vstack([item["horizon_targets"][h] for item in valid])
        split=max(35,int(.72*len(valid)))
        if split>=len(valid)-10: continue
        beta=fit_ridge(np.column_stack([np.ones(split),z[:split]]),y[:split],ridge=.20)
        pred=np.column_stack([np.ones(len(valid)-split),z[split:]])@beta; scale=np.maximum(y[split:].std(axis=0),.03)
        out.append({"horizon":h,"normalized_rmse":float(np.sqrt(np.mean(((y[split:]-pred)/scale)**2)))})
    return out


def run_seed(seed):
    events=generate_stream(seed,cfg["train_steps"],cfg["transfer_frozen_steps"],cfg["transfer_adapt_steps"])
    common_agent,common_world,source_trace,source_summary,source_episode_id=develop_shared_history(seed,events)
    event_frames=[]; summaries=[]; matrices=[]; factor_scores=[]; structure_rows=[]; state_rows=[]; horizon_rows=[]

    for representation in REPRESENTATIONS:
        print("running",seed,representation)
        world=copy.deepcopy(common_world); fork=RepresentationFork(representation,common_agent.replay,common_agent.risk,seed+7000)
        source_factor_loadings=fork.source_factor_loadings.copy() if fork.is_factor else None; source_factor_count=int(fork.source_factor_count) if fork.is_factor else None
        source_items=common_agent.replay[-min(cfg["replay_size"],len(common_agent.replay)):]
        source_probe_x=np.vstack([fork.represent(item["observed"]) for item in source_items])
        source_probe_y=np.vstack([item["hidden"] for item in source_items]); source_hand_y=np.vstack([hand_factor_values(item["observed"]) for item in source_items])
        for row in fork.structure_events: structure_rows.append({"seed":seed,**row})
        for row in fork.structure_state_history: state_rows.append({"seed":seed,**row})
        for c in fork.source_factor_candidate_scores: factor_scores.append({"seed":seed,"representation":representation,"stage":"source_end",**c})
        if representation in {"seed_softwall_full","seed_v9_hardwall","v8_smallest_sufficient_factors","raw_channels","hand_factorized"}:
            for hp in horizon_probe_errors(fork,source_items): horizon_rows.append({"seed":seed,"representation":representation,"stage":"source_end",**hp})

        rows=[]; lifetimes=[]; episode_id=source_episode_id
        for transfer_index,event in enumerate(events[cfg["train_steps"]:]):
            t=cfg["train_steps"]+transfer_index; learning_enabled=event.phase=="transfer_adapt"
            action_index,before,observed,predicted_risk,rep_unc=fork.choose_action(world,event); outcome=apply_action(world,event,action_index); after=world_deficits(world)
            step_cost=outcome["immediate_cost"]+outcome["queued_cost"]; learning_gain=outcome["immediate_learning"]+outcome["queued_learning"]
            if learning_enabled:
                fork.observe({"t":t,"episode_id":episode_id,"before":before.copy(),"after":after.copy(),"observed":observed.copy(),"action_index":action_index,
                             "expired_harm":outcome["expired_harm"],"prevented_harm":outcome["prevented_harm"],"residual_harm":outcome["residual_harm"],"step_cost":step_cost,
                             "learning_gain":learning_gain,"collapsed":float(outcome["collapsed"]),"hidden":np.array([event.true_weight,event.true_urgency,event.true_learning])})
                adaptive_index=transfer_index-cfg["transfer_frozen_steps"]+1
                if adaptive_index>0 and adaptive_index%cfg["refit_every"]==0:
                    ev0=len(fork.structure_events); st0=len(fork.structure_state_history); fork.refit_models(stage="transfer_adapt",t=t)
                    for row in fork.structure_events[ev0:]: structure_rows.append({"seed":seed,**row})
                    for row in fork.structure_state_history[st0:]: state_rows.append({"seed":seed,**row})
            structural_value=(outcome["prevented_harm"]-outcome["expired_harm"]-outcome["residual_harm"]-.35*step_cost+.15*learning_gain-2.0*int(outcome["collapsed"]))
            vector=fork.represent(observed); eval_hand=hand_factor_values(observed)
            row={"seed":seed,"representation":representation,"t":t,"transfer_index":transfer_index,"phase":event.phase,"world_family":event.world_family,"regime":event.regime,
                 "action":ACTIONS[action_index],"predicted_risk":predicted_risk,"representation_uncertainty":rep_unc,"active_dim":fork.active_dim,
                 "informational_drag":fork.informational_drag,"softwall_dim":fork.softwall_dim,"desired_dim":fork.desired_dim,"complexity_price":fork.complexity_price,
                 "factor_mass_entropy":fork.mass_entropy() if fork.is_factor else np.nan,"factor_support_size":fork.support_size(),"collapsed":outcome["collapsed"],
                 "safety":world.safety,"resources":world.resources,"competence":world.competence,"uncertainty":world.uncertainty,"expired_harm":outcome["expired_harm"],
                 "prevented_harm":outcome["prevented_harm"],"residual_harm":outcome["residual_harm"],"step_cost":step_cost,"learning_gain":learning_gain,"structural_value":structural_value,
                 "true_weight":event.true_weight,"true_urgency":event.true_urgency,"true_learning":event.true_learning}
            for i,v in enumerate(vector): row[f"rep_{i}"]=v
            for i,v in enumerate(eval_hand): row[f"eval_hand_{i}"]=v
            rows.append(row)
            if outcome["collapsed"]: lifetimes.append(world.lifetime); episode_id+=1; world=WorldState()
        if world.lifetime: lifetimes.append(world.lifetime)
        frame=pd.DataFrame(rows)
        if representation in {"seed_softwall_full","seed_v9_hardwall","v8_smallest_sufficient_factors","raw_channels","hand_factorized"}:
            for hp in horizon_probe_errors(fork,list(fork.buffer)): horizon_rows.append({"seed":seed,"representation":representation,"stage":"transfer_end",**hp})

        frozen=frame[frame.phase=="transfer_frozen"]; rep_cols=[c for c in frame.columns if c.startswith("rep_")]; hand_cols=[f"eval_hand_{i}" for i in range(4)]
        hidden_r2=ridge_probe(source_probe_x,source_probe_y,frozen[rep_cols].values,frozen[HIDDEN_FACTORS].values)
        hand_r2=ridge_probe(source_probe_x,source_hand_y,frozen[rep_cols].values,frozen[hand_cols].values)
        family_means=frozen.groupby("world_family").structural_value.mean()
        rep_struct=[r for r in structure_rows if r["seed"]==seed and r["representation"]==representation]
        births=sum(r["event"]=="birth" for r in rep_struct); prunes=sum(r["event"]=="prune" for r in rep_struct)
        source_births=sum(r["event"]=="birth" and r["stage"]=="source_seed" for r in rep_struct); transfer_births=sum(r["event"]=="birth" and r["stage"]=="transfer_adapt" for r in rep_struct)
        source_prunes=sum(r["event"]=="prune" and r["stage"]=="source_seed" for r in rep_struct); transfer_prunes=sum(r["event"]=="prune" and r["stage"]=="transfer_adapt" for r in rep_struct)
        summary={**source_summary,"representation":representation,"transfer_mean_lifetime":float(np.mean(lifetimes)),"refit_count":fork.refit_count,
                 "probe_r2_weight":float(hidden_r2[0]),"probe_r2_urgency":float(hidden_r2[1]),"probe_r2_learning":float(hidden_r2[2]),"probe_r2_mean":float(np.mean(hidden_r2)),
                 "hand_probe_r2_mean":float(np.mean(hand_r2)),"mean_active_dim":float(frame.active_dim.mean()),"min_active_dim":int(frame.active_dim.min()),"max_active_dim":int(frame.active_dim.max()),
                 "source_factor_count":int(source_factor_count) if fork.is_factor else np.nan,"final_factor_count":int(fork.factor_count_selected) if fork.is_factor else np.nan,
                 "source_informational_drag":float(fork.source_informational_drag) if fork.is_factor else np.nan,"final_informational_drag":float(fork.informational_drag) if fork.is_factor else np.nan,
                 "source_softwall_dim":int(fork.source_softwall_dim) if fork.is_factor else np.nan,"final_softwall_dim":int(fork.softwall_dim) if fork.is_factor else np.nan,
                 "mean_informational_drag":float(frame.informational_drag.mean()) if fork.is_factor else np.nan,"mean_softwall_dim":float(frame.softwall_dim.mean()) if fork.is_factor else np.nan,
                 "wall_utilization":float((frame.active_dim/np.maximum(frame.softwall_dim,1)).mean()) if representation in SOFTWALL_REPRESENTATIONS else np.nan,
                 "source_nuisance_loading_fraction":float(fork.nuisance_loading_fraction(True)) if fork.is_factor else np.nan,"final_nuisance_loading_fraction":float(fork.nuisance_loading_fraction(False)) if fork.is_factor else np.nan,
                 "source_hand_group_ari":float(fork.hand_group_ari(True)) if fork.is_factor else np.nan,"final_hand_group_ari":float(fork.hand_group_ari(False)) if fork.is_factor else np.nan,
                 "frozen_family_value_sd":float(family_means.std(ddof=0)),"births":int(births),"prunes":int(prunes),"source_births":int(source_births),"source_prunes":int(source_prunes),
                 "transfer_births":int(transfer_births),"transfer_prunes":int(transfer_prunes),"mean_representation_churn":float(np.mean(fork.representation_churn)) if fork.representation_churn else 0.0,
                 "action_entropy":action_entropy(frame.action)}
        for phase in ["transfer_frozen","transfer_adapt"]:
            part=frame[frame.phase==phase]; summary.update({f"{phase}_value":float(part.structural_value.sum()),f"{phase}_collapses":int(part.collapsed.sum()),
                f"{phase}_expired_harm":float(part.expired_harm.sum()),f"{phase}_cost":float(part.step_cost.sum())})
        summary["transfer_total_value"]=summary["transfer_frozen_value"]+summary["transfer_adapt_value"]
        adaptive=frame[frame.phase=="transfer_adapt"]; q=max(1,len(adaptive)//4); summary["adaptation_gain"]=float(adaptive.structural_value.iloc[-q:].mean()-adaptive.structural_value.iloc[:q].mean())
        summaries.append(summary); event_frames.append(frame)

        if fork.is_factor:
            for stage,matrix,count,names in [("source_end",fork.source_factor_loadings,fork.source_factor_count,fork.feature_names),("transfer_end",fork.factor_loadings,fork.factor_count_selected,fork.feature_names)]:
                for latent in range(min(int(count),matrix.shape[0])):
                    for j,name in enumerate(names): matrices.append({"seed":seed,"representation":representation,"stage":stage,"latent_dimension":latent,"feature":name,"loading":float(matrix[latent,j])})
        for c in fork.factor_candidate_scores: factor_scores.append({"seed":seed,"representation":representation,"stage":"transfer_end",**c})

    return pd.concat(event_frames,ignore_index=True),pd.DataFrame(summaries),pd.DataFrame(matrices),pd.DataFrame(factor_scores),pd.DataFrame(structure_rows),pd.DataFrame(state_rows),pd.DataFrame(horizon_rows),source_trace


all_events=[]; all_summaries=[]; all_matrices=[]; all_scores=[]; all_structure=[]; all_states=[]; all_horizon=[]; all_source=[]
for offset in range(cfg["seeds"]):
    seed=BASE_SEED+offset; outputs=run_seed(seed)
    e,s,m,fs,se,st,h,src=outputs; all_events.append(e); all_summaries.append(s); all_matrices.append(m); all_scores.append(fs); all_structure.append(se); all_states.append(st); all_horizon.append(h); all_source.append(src)
    pd.concat(all_summaries,ignore_index=True).to_csv(CHECKPOINTS/"completed_runs.csv",index=False)

results=pd.concat(all_events,ignore_index=True); run_summary=pd.concat(all_summaries,ignore_index=True)
representation_matrices=pd.concat(all_matrices,ignore_index=True) if any(not x.empty for x in all_matrices) else pd.DataFrame()
factor_selection=pd.concat(all_scores,ignore_index=True) if any(not x.empty for x in all_scores) else pd.DataFrame()
structure_events=pd.concat(all_structure,ignore_index=True) if any(not x.empty for x in all_structure) else pd.DataFrame()
structure_states=pd.concat(all_states,ignore_index=True) if any(not x.empty for x in all_states) else pd.DataFrame()
horizon_diagnostics=pd.concat(all_horizon,ignore_index=True) if any(not x.empty for x in all_horizon) else pd.DataFrame(); source_traces=pd.concat(all_source,ignore_index=True)

results.to_csv(DATA/"transfer_events.csv.gz",index=False,compression="gzip"); run_summary.to_csv(DATA/"run_summary.csv",index=False)
representation_matrices.to_csv(DATA/"representation_matrices.csv",index=False); factor_selection.to_csv(DATA/"factor_selection.csv",index=False)
structure_events.to_csv(DATA/"structure_events.csv",index=False); structure_states.to_csv(DATA/"structure_states.csv",index=False)
horizon_diagnostics.to_csv(DATA/"horizon_diagnostics.csv",index=False); source_traces.to_csv(DATA/"shared_source_traces.csv.gz",index=False,compression="gzip")
print("Transfer event rows:",len(results)); print("Representation runs:",len(run_summary)); print("Structure events:",len(structure_events)); print("Structure states:",len(structure_states))



# %% [notebook cell 8]
# =============================================
# 8. Paired statistics and long-horizon tests
# =============================================
def paired_bootstrap(frame,treatment,control,metric,samples=None,seed=BASE_SEED+991):
    samples=samples or cfg["bootstrap_samples"]; pivot=frame.pivot(index="seed",columns="representation",values=metric)
    diffs=(pivot[treatment]-pivot[control]).dropna().values; rng=np.random.default_rng(seed+sum(ord(c) for c in treatment+control+metric))
    if len(diffs)==0:return {"comparison":f"{treatment} - {control}","metric":metric,"mean_difference":np.nan,"ci_low":np.nan,"ci_high":np.nan,"n":0}
    boot=np.array([np.mean(diffs[rng.integers(0,len(diffs),len(diffs))]) for _ in range(samples)])
    return {"comparison":f"{treatment} - {control}","metric":metric,"mean_difference":float(np.mean(diffs)),"ci_low":float(np.percentile(boot,2.5)),"ci_high":float(np.percentile(boot,97.5)),"n":len(diffs)}

main="seed_softwall_full"
controls=["collapsed_scalar","raw_channels","hand_factorized","v8_smallest_sufficient_factors","seed_one_factor","seed_v9_hardwall","seed_softwall_linear","seed_softwall_no_prune","seed_softwall_random_geometry"]
paired_rows=[]
for control in controls:
    if control==main: continue
    for metric in ["transfer_frozen_value","transfer_total_value","adaptation_gain"]: paired_rows.append(paired_bootstrap(run_summary,main,control,metric))
paired=pd.DataFrame(paired_rows); paired.to_csv(DATA/"paired_comparisons.csv",index=False)

# Longest-horizon NRMSE: lower is better, so report control - main as positive improvement.
max_h=max(cfg["representation_horizons"]); hr=horizon_diagnostics[(horizon_diagnostics.stage=="transfer_end")&(horizon_diagnostics.horizon==max_h)]
long_rows=[]
for control in ["raw_channels","hand_factorized","v8_smallest_sufficient_factors","seed_v9_hardwall"]:
    p=hr.pivot(index="seed",columns="representation",values="normalized_rmse")
    if main not in p or control not in p: continue
    d=(p[control]-p[main]).dropna().values; rng=np.random.default_rng(BASE_SEED+1700+sum(map(ord,control)))
    if len(d):
        b=np.array([np.mean(d[rng.integers(0,len(d),len(d))]) for _ in range(cfg["bootstrap_samples"])])
        long_rows.append({"comparison":f"{control} RMSE - {main} RMSE","horizon":max_h,"mean_improvement":float(np.mean(d)),"ci_low":float(np.percentile(b,2.5)),"ci_high":float(np.percentile(b,97.5)),"n":len(d)})
long_horizon=pd.DataFrame(long_rows); long_horizon.to_csv(DATA/"long_horizon_comparisons.csv",index=False)

means=run_summary.groupby("representation").mean(numeric_only=True)
display(means[["transfer_frozen_value","transfer_total_value","adaptation_gain","source_factor_count","final_factor_count","mean_informational_drag","mean_softwall_dim","wall_utilization","births","prunes"]].sort_values("transfer_frozen_value",ascending=False))
display(paired)
if not long_horizon.empty: display(long_horizon)



# %% [notebook cell 9]
# =============================================
# 9. Figures — behavior, drag, sidewalls, horizon
# =============================================
def savefig(name):
    path=FIG/f"{name}.png"; plt.tight_layout(); plt.savefig(path,dpi=160); plt.close(); return path

order=means.transfer_frozen_value.sort_values(ascending=False).index
plt.figure(figsize=(12,5)); plt.bar(order,means.loc[order,"transfer_frozen_value"]); plt.xticks(rotation=50,ha="right"); plt.ylabel("Frozen-transfer structural value"); plt.title("v10 zero-shot transfer"); savefig("01_frozen_transfer_value")

factor_means=means.loc[[r for r in REPRESENTATIONS if r in FACTOR_REPRESENTATIONS],["source_factor_count","final_factor_count"]]
plt.figure(figsize=(11,5)); x=np.arange(len(factor_means)); plt.plot(x,factor_means.source_factor_count.values,marker="o",label="source"); plt.plot(x,factor_means.final_factor_count.values,marker="o",label="transfer end"); plt.xticks(x,factor_means.index,rotation=50,ha="right"); plt.ylabel("Active factors"); plt.title("Developmental capacity change"); plt.legend(); savefig("02_factor_counts")

main_frame=results[results.representation==main]
traj=main_frame.groupby("transfer_index")[["active_dim","softwall_dim","informational_drag"]].mean()
plt.figure(figsize=(11,5)); plt.plot(traj.index,traj.active_dim,label="active factors"); plt.plot(traj.index,traj.softwall_dim,label="soft sidewall"); plt.xlabel("Transfer step"); plt.ylabel("Dimension"); plt.title("v10 capacity breathes with informational drag"); plt.legend(); savefig("03_softwall_trajectory")

plt.figure(figsize=(7,5)); plt.scatter(main_frame.informational_drag,main_frame.active_dim,s=8,alpha=.25); plt.xlabel("Informational drag"); plt.ylabel("Active factors"); plt.title("Earned complexity: drag vs active dimension"); savefig("04_drag_vs_dimension")

if not structure_events.empty:
    counts=structure_events.groupby(["representation","event"]).size().unstack(fill_value=0)
    plt.figure(figsize=(11,5)); counts.plot(kind="bar",ax=plt.gca()); plt.ylabel("Count"); plt.title("Birth / prune events"); plt.xticks(rotation=50,ha="right"); savefig("05_structure_events")

if not hr.empty:
    hp=hr.groupby("representation").normalized_rmse.mean().sort_values()
    plt.figure(figsize=(10,5)); plt.bar(hp.index,hp.values); plt.xticks(rotation=50,ha="right"); plt.ylabel("Normalized RMSE (lower better)"); plt.title(f"Longest-horizon consequence prediction: {max_h} steps"); savefig("06_long_horizon_rmse")

nuis=means.loc[[r for r in means.index if r in FACTOR_REPRESENTATIONS],"final_nuisance_loading_fraction"].dropna().sort_values()
plt.figure(figsize=(10,5)); plt.bar(nuis.index,nuis.values); plt.xticks(rotation=50,ha="right"); plt.ylabel("Nuisance-linked loading fraction"); plt.title("Does learned geometry reject accidental structure?"); savefig("07_nuisance_loading")

adapt=means.adaptation_gain.sort_values(ascending=False)
plt.figure(figsize=(11,5)); plt.bar(adapt.index,adapt.values); plt.axhline(0,linewidth=1); plt.xticks(rotation=50,ha="right"); plt.ylabel("Adaptation gain / event"); plt.title("Post-transfer adaptation"); savefig("08_adaptation_gain")
print("Saved figures:",len(list(FIG.glob("*.png"))))



# %% [notebook cell 10]
# ==========================================
# 10. Automated interpretation and decision
# ==========================================
def cmp(control,metric="transfer_frozen_value"):
    r=paired[(paired.comparison==f"{main} - {control}")&(paired.metric==metric)]
    return None if r.empty else r.iloc[0]

vs_raw=cmp("raw_channels"); vs_hand=cmp("hand_factorized"); vs_v9=cmp("seed_v9_hardwall"); vs_linear=cmp("seed_softwall_linear"); vs_one=cmp("seed_one_factor"); vs_random=cmp("seed_softwall_random_geometry"); vs_no_prune=cmp("seed_softwall_no_prune")
main_rows=run_summary[run_summary.representation==main]
capacity_dynamic=bool((main_rows.max_active_dim-main_rows.min_active_dim).mean()>0 or main_rows.births.sum()+main_rows.prunes.sum()>0)
wall_not_fixed=bool(main_rows.mean_softwall_dim.std(ddof=0)>0 or (structure_states[structure_states.representation==main].softwall_dim.nunique()>1 if not structure_states.empty else False))

checks={
    "structural constraints only":True,
    "no route / correct-action / semantic labels":True,
    "shared paired streams":True,
    "capacity actually changes":capacity_dynamic,
    "soft sidewall actually moves":wall_not_fixed,
    "main beats random geometry":bool(vs_random is not None and vs_random.ci_low>0),
    "main beats one-factor seed":bool(vs_one is not None and vs_one.ci_low>0),
    "main beats old v9 hardwall":bool(vs_v9 is not None and vs_v9.ci_low>0),
    "nonlinear substrate beats linear softwall":bool(vs_linear is not None and vs_linear.ci_low>0),
    "main beats raw":bool(vs_raw is not None and vs_raw.ci_low>0),
}

# Strong freeze requires the adaptive-boundary claims themselves, not merely decent behavior.
freeze=all([checks["capacity actually changes"],checks["soft sidewall actually moves"],checks["main beats random geometry"],checks["main beats one-factor seed"],checks["main beats old v9 hardwall"],checks["main beats raw"]])
decision="FREEZE ADAPTIVE CAPACITY MECHANISM" if freeze else "CONTINUE TESTING"

print("=== V10 INTERPRETATION ===")
for k,v in checks.items(): print(("PASS" if v else "FAIL"),"-",k)
print("\nDecision:",decision)
if vs_hand is not None:
    print(f"Main vs hand factorization: {vs_hand.mean_difference:+.4f} [{vs_hand.ci_low:+.4f}, {vs_hand.ci_high:+.4f}]")
if vs_v9 is not None:
    print(f"Main vs old v9 hardwall: {vs_v9.mean_difference:+.4f} [{vs_v9.ci_low:+.4f}, {vs_v9.ci_high:+.4f}]")
if vs_linear is not None:
    print(f"Main vs linear softwall: {vs_linear.mean_difference:+.4f} [{vs_linear.ci_low:+.4f}, {vs_linear.ci_high:+.4f}]")
print("Mean source/final factors:",float(main_rows.source_factor_count.mean()),"->",float(main_rows.final_factor_count.mean()))
print("Mean informational drag:",float(main_rows.mean_informational_drag.mean()),"Mean sidewall:",float(main_rows.mean_softwall_dim.mean()))

report_lines=[
    "# v10 — Informational Softwalls and Earned Capacity", "", f"Decision: **{decision}**", "",
    "The representation begins as a one-factor seed. Capacity is not assigned a target size. Instead, a semantics-free informational-drag estimate changes the effective sidewall and the price of additional factors.", "",
    "## Freeze checks", *[f"- {'PASS' if v else 'FAIL'} — {k}" for k,v in checks.items()], "",
    "## Discipline", "A higher factor count is not treated as success. A birth is useful only if consequence prediction or behavior improves under paired transfer. The hand-factor control remains evaluation-only."
]
(REPORT/"summary.md").write_text("\n".join(report_lines))



# %% [notebook cell 11]
# =================================
# 11. Manifest, hashes, and one ZIP
# =================================
def sha256_file(path):
    digest=hashlib.sha256()
    with open(path,"rb") as handle:
        for chunk in iter(lambda:handle.read(1024*1024),b""): digest.update(chunk)
    return digest.hexdigest()

manifest={
    "experiment":"Developmental Agent v10 — Informational Softwalls and Earned Capacity",
    "timestamp":timestamp,"run_profile":RUN_PROFILE,"base_seed":BASE_SEED,"profile":cfg,"representations":REPRESENTATIONS,
    "main_branch":"seed_softwall_full",
    "structural_rules":{
        "semantic_labels_to_policy":False,"correct_action_labels":False,"route_labels":False,"hidden_factors_to_policy":False,
        "capacity_target_given":False,"informational_drag_uses_only_experienced_consequences":True,
        "nonlinear_substrate":"generic raw + signed-square + pairwise interactions; no semantic ranking",
    },
    "outputs":{},"decision":decision,"checks":checks,
}
for path in sorted(ROOT.rglob("*")):
    if path.is_file() and path.name!="manifest.json": manifest["outputs"][str(path.relative_to(ROOT))]={"bytes":path.stat().st_size,"sha256":sha256_file(path)}
manifest_path=ROOT/"manifest.json"; manifest_path.write_text(json.dumps(manifest,indent=2))

zip_path=base/f"informational_softwalls_v10_{RUN_PROFILE}_{timestamp}.zip"
with zipfile.ZipFile(zip_path,"w",zipfile.ZIP_DEFLATED) as z:
    for path in sorted(ROOT.rglob("*")):
        if path.is_file(): z.write(path,path.relative_to(ROOT.parent))
print("Results ZIP:",zip_path)
print("Manifest:",manifest_path)

