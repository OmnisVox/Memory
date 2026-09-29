# Canonical Adrianic Memory Architecture

Version: **0.4.0 canonical reconstruction**

This project is a lineage-preserving reconstruction. It does not assume that the
latest historical notebook automatically contains every earlier capability.

## Architectural rule

Every mechanism is assigned one of three provenance states:

- **ORIGINAL EXECUTABLE** — surviving source code is preserved and can be run.
- **RECONSTRUCTED** — the mechanism is reimplemented from surviving equations/specs,
  with an explicit statement that numerical benchmark equivalence is not claimed.
- **EVIDENCE ONLY** — the surviving bundle contains results/specification but not the
  executable implementation; results are preserved but not silently recreated.

## Layer map

```text
semantic / environment proposals
            |
            v
+------------------------------+
|  relational / semantic layer |  optional plugin lineage
+------------------------------+
            |
            v
+------------------------------+
| evidence + trust arbitration |  reliability, bias, provenance,
| dependency/common-cause      |  verified consequences, VALUE_UNRESOLVED
+------------------------------+
            |
            v
+------------------------------+
| selective consolidation      |  INCLUDE / EXCLUDE / HOLD
| + replacement comparison     |  consequence-aware permanent writes
+------------------------------+
            |
            v
+------------------------------+
| finite addressable bank      |  transparent address distance,
| + ambiguity refusal          |  HOLD_UNRESOLVED
+------------------------------+
            |
            v
+------------------------------+
| integrity + redundancy       |  working + Bank A + Bank B +
|                              |  confidence + parity P/Q
+------------------------------+
            |
            v
+------------------------------+
| complex dynamical memory     |  slow complex chi field,
| + learn/recall timescales    |  fast recall / slow learning
+------------------------------+
            |
            v
 active dynamical state / task behavior
```

A separate **developmental controller** decides what internal structure/capacity
earns permanence. It is not forced into the ordinary recall path.


## Semantic-governance boundary and retraction

The memory architecture can expose candidate hypotheses and consume externally computed
evidence, but **v5.0 is not positive validation of semantic consequence governance**. Its
consequence observation was a unique deterministic code of the correct retained hypothesis.
That claim is retracted under R-001.

The architecture remains modular: a future semantic proposer may feed the evidence layer only
through a repaired, non-answer-bearing observation model. Semantic priors must be compared
directly against uniform and shuffled priors under matched evidence.

The repaired design precedent lives earlier in the lineage: v4.0-v4.2 use corpus-statistic evidence, while v4.3-v4.8 use measured, noisy, many-to-one consequence/factor evidence rather than answer-bearing codes. These versions are clean with respect to R-001, but their preserved headline runs are local smoke/proxy runs; see `docs/V4_EVIDENCE_BOUNDARIES.md`.

v4.9 remains a separate legitimate but narrow randomized binary symmetric-decoy consequence-arbitration benchmark, not an independent semantic-grounding validation.

## 1. Complex dynamical memory

Source lineage: v3.1 complex-memory patch and later memory-timescale studies.

The original extension preserves phase-sensitive state in a slow complex memory
field `chi`, with a restorative channel from memory back into the active field.

Canonical implementation:
`src/adrianic_memory/complex_field.py`

Status: **RECONSTRUCTED from equations**.

Boundary: this module implements the memory term, not the complete historical PDE
simulator, so historical numerical plots are not claimed reproducible from this
class alone.

## 2. Learn/recall timescale separation

Source lineage: Memory Timescale & Interference Study.

Historical benchmark:
- approximately 24:1 recall-update cadence versus learning-update cadence was the
  best tested schedule in that benchmark;
- source-of-surprise logic freezes learning when the active state looks corrupted,
  freezes recall when memory looks corrupted, and uses symmetric repair when both
  are unreliable.

Canonical implementation:
`src/adrianic_memory/timescale.py`

Status: **RECONSTRUCTED from report/equations**.

## 3. Addressable multi-slot bank

Source lineage: `adrianic_multislot_memory.zip`.

Historical evidence:
- core geometry + global moments formed the best tested compact 12-D address;
- mean exact retrieval across the reported corruption battery was ~0.9983;
- worst corruption-class accuracy was ~0.9931;
- ambiguity was explicitly allowed to return `HOLD_UNRESOLVED`;
- the controlled family was tested to 48 slots.

Canonical implementation:
`src/adrianic_memory/bank.py`

Status: **PARTIAL RECONSTRUCTION**.

Important boundary: the exact historical 12-D field-to-address extractor source code
is not present in the recovered bundle. The canonical bank therefore accepts an
externally computed address vector rather than pretending to reproduce that extractor.

## 4. Seven-role persistent layout

Source lineage: v3.15 and v3.16.

v3.15 fixed:
- active
- working
- Bank A
- Bank B

It then searched all 20 choices of three flexible roles from:
- derivative
- predictor
- spin
- confidence
- parity P
- parity Q

The recovered fault-coupled development and held-out winner is:

`confidence + parityP + parityQ`

v3.16 therefore defines seven persistent roles:
1. active
2. working
3. Bank A
4. Bank B
5. confidence / source trust
6. parity P
7. parity Q

Derivative, prediction, and phase-velocity quantities become transient computations
rather than permanent slots.

Canonical definitions:
`src/adrianic_memory/roles.py`

Status:
- v3.15 original numerical search: **EVIDENCE ONLY** (result/spec bundle recovered;
  executable search code absent)
- role definitions: **DIRECTLY RECOVERED FROM SPEC**
- canonical role constants: **RECONSTRUCTED INTERFACE**

## 5. Dual parity integrity guard

Source lineage: v3.15/v3.16 and v3.8.

Default checksums:
- `P = z0 + z1 + z2 + z3`
- `Q = z0 - z1 + 2 z2 - 2 z3`

The Q coefficients make a single-coordinate corruption locatable from the syndrome
ratio when the stored parity channels remain trustworthy.

Canonical implementation:
`src/adrianic_memory/parity.py`

Status: **RECONSTRUCTED from surviving executable v3.8 logic**.

Scientific boundary: parity is hand-designed error-control redundancy. The project
does not claim that the system invented parity.

## 6. Behavioral consolidation

Source lineage: v3.16.

Durable checkpoints are accepted only when confidence, reward/consequence stability,
context stability, novelty, and checkpoint timing justify them. Bank A/B are written
one at a time and parity is re-encoded after accepted checkpoints.

v3.16 includes behavioral controls with working-memory wipes, misleading transient
cues, and durable-bank damage.

Status: **EVIDENCE ONLY** for the exact v3.16 task implementation because the recovered
bundle does not contain the executable benchmark source.

The general transparent commit mechanism is implemented separately in the canonical
project from later memory-only selective-commit studies.

## 7. Selective permanent memory

Source lineage: Selective Commit Controller Study + messy-world memory study.

Core decision:
`INCLUDE | EXCLUDE | HOLD`

Canonical implementation:
`src/adrianic_memory/consolidation.py`

Historical selective-commit benchmark:
- useful-memory performance improved versus always-commit;
- permanent writes fell from roughly 482 to 40 per 1,200 events in the reported run;
- tested transient permanent commits fell to zero.

Messy-world extensions added:
- delayed consequence value
- recent utility
- slow reconsolidation
- utility reversal
- poisoning tests
- interference cost

Status: **RECONSTRUCTED from reports/patches**, with historical thresholds left explicit
rather than treated as universal constants.

## 8. Trust-calibrated evidence

Source lineage: trust calibration, v3.18, v3.19.

Per-source state includes:
- reliability
- signed bias
- provenance group

Verified outcomes update reliability and bias. Uncertain value must produce
`VALUE_UNRESOLVED`, which in turn keeps a memory candidate in HOLD.

Canonical implementation:
`src/adrianic_memory/evidence.py`

Status: **RECONSTRUCTED from equations and surviving v3.18/v3.19 executable code**.

Original runnable research:
- `experiments/v3_18_trust_adaptation/run_v318.py`
- `experiments/v3_19_evidence_graph/run_v319.py`

## 9. Learned dependency graph

Source lineage: v3.20.

The historical experiment did not receive provenance labels in its main controller.
It inferred source families from verified residual correlation; the specification
uses a 0.72 correlation threshold in that benchmark.

Canonical implementation:
`src/adrianic_memory/dependency.py::ResidualDependencyLearner`

Status: **RECONSTRUCTED FROM SPEC**, because the recovered v3.20 bundle does not include
its executable source.

The canonical class deliberately exposes the threshold and minimum-sample count.

## 10. Latent common-cause factors

Source lineage: v3.21.

The experiment extends pairwise dependency detection into low-rank residual factors
and tests up to three leading covariance eigenvectors.

Canonical implementation:
`src/adrianic_memory/dependency.py::LatentCommonCauseModel`

Status: **RECONSTRUCTED INTERFACE**, with the original runnable v3.21 script preserved at:
`experiments/v3_21_latent_common_cause/run_v321.py`

The canonical class does not claim exact numerical equivalence to that benchmark.

## 11. Developmental structural controller

Source lineage:
- v3.8 parity/coalition structural plasticity
- Developmental Agent v10 informational softwalls
- Developmental Agent v11 action-conditioned structural induction

This layer is intentionally separated from ordinary memory access.

The surviving experiments include:
- provisional structural HOLD
- leave-one-edge-out consequence testing
- coalition rescue for super-additive motifs
- earned factor/capacity changes
- growth/pruning events
- consequence-delayed structural valuation
- action-conditioned structural induction

Status: **ORIGINAL EXECUTABLE EXPERIMENTS**, preserved under `experiments/`.

They are not yet flattened into one production class because doing so without a
separate validation pass would repeat the historical integration mistake.

## 12. Relational sidecar

Source lineage: relational-memory sidecar patch.

Purpose:
- preserve sparse identity/relationship edges alongside dynamical/episodic memory;
- bridge exact identities across observed relations;
- track support and downstream reliability;
- do not assume semantic relation-composition rules that were not observed.

Canonical implementation:
`src/adrianic_memory/relational.py`

Status: **ORIGINAL PATCH ADAPTED INTO PACKAGE**.

## 13. Semantic / deterministic reasoning layer

Source lineage: v4.x and v5.x.

This layer proposes/uses semantic identities, relation structures, progressive recall,
consequence arbitration, and later semantic-coupling experiments.

It is intentionally **not the memory core**.

Preserved under:
- `evidence/semantic_reasoning_lineage/`
- `experiments/v5_3_plus/`

The newest semantic-coupling experiments retain fresh per-edge constraint semantics
and are not used to redefine the memory architecture.

## Integration contract

The canonical production path is:

1. observation / semantic proposal
2. evidence assessment
3. unresolved-or-resolved value
4. selective commit decision
5. explicit allocation/replacement
6. transparent retrieval with ambiguity refusal
7. optional integrity repair
8. audit log

Developmental structure change is a separate outer loop:

1. propose structural candidate
2. observe consequences
3. compare against baseline/ablation
4. HOLD / retain / prune
5. freeze accepted structure for evaluation

That separation is deliberate.

## 13. Honest address resolution

Source lineage: Evidence Graph v3 + field replacement reintegration.

A resolver must satisfy both:
- absolute proximity: best normalized distance below a configured `max_distance`;
- relative confidence: best-vs-second-best margin above `min_margin`.

Canonical implementation:
`src/adrianic_memory/bank.py`

Status: **RECONSTRUCTED from surviving field patch/report**.

Recovered benchmark calibration for the controlled 24-member vortex family:
`max_distance = 0.20`, `min_margin = 0.035`.  These are not universal constants.

## 14. Comparative full-bank replacement

Source lineage: causal ablation → field replacement gate.

The causal ledger showed that corrected evidence usually changed trust but only a
subset of those changes survived commit thresholds and finite-slot competition.
The full-bank decision therefore became explicitly comparative: a candidate must
beat the expected retained value of the slot it would destroy.

Canonical implementation:
`src/adrianic_memory/consolidation.py::ComparativeReplacementConfig`

Status: **RECONSTRUCTED from surviving patch/report**.

Recovered calibrations differ by benchmark:
- abstract causal-ablation benchmark: best tested margin ~0.16;
- complex-field benchmark: best tested margin ~0.28.

That disagreement is preserved as evidence that the margin is calibration-dependent.

## 15. Dual address/template representation

Source lineage: field replacement gate.

The recovered field integration found that arithmetic averaging was useful for the
phase-agnostic address vector but destructive for the phase-sensitive complex recall
template.  The canonical architecture therefore keeps them separate:

- averaged robust address state;
- best topology-qualified raw complex template.

A candidate can be address-ready while remaining template-unresolved.

Canonical implementation:
`src/adrianic_memory/templates.py::DualRepresentationCandidate`

Status: **RECONSTRUCTED interface**, with original field integration source and final
result tables preserved separately.

## 16. Imperfect-anchor cross-checking and causal logging

Source lineage: Evidence Graph v3 + causal ablation.

Evidence Graph v3 introduced a direct routine-anchor cross-check against independently
trust-weighted verifier consensus using a running median/MAD disagreement threshold.
The synthetic benchmark sharply reduced verification MAE, but did **not** by itself
solve end-to-end memory utility.  That negative result is part of the architecture:
better verification must be traced through trust, commit, replacement, slot state,
and future utility rather than assumed to propagate automatically.

Canonical modules:
- `src/adrianic_memory/verification.py::RobustAnchorFilter`
- `src/adrianic_memory/causal.py::CausalAblationLedger`

Status:
- anchor-filter logic: **RECONSTRUCTED from surviving executable source**;
- causal-ledger schema: **RECONSTRUCTED logging interface**;
- original branch-cloning causal experiment: **EVIDENCE ONLY** because source was not
  present in the recovered ZIP.

## 17. Robust topological recall validation

Source lineage: field replacement gate.

The recovered report rejects exact global microscopic plaquette equality as a robust
recall criterion near amplitude zeros.  Finite-loop winding around recovered cores is
used instead.

Canonical implementation:
`src/adrianic_memory/templates.py::finite_loop_winding`

Status: **RECONSTRUCTED from surviving patch/report**.
