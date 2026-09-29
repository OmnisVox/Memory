# v4.x Evidence Boundaries

Date audited: 2026-08-03

This note prevents Retraction R-001 (v5.0) from being projected backward onto a mechanically different v4.x lineage. The audit here is an **information-flow / evidence-generation audit**, not a complete statistical re-derivation of every v4.x headline.

## Retraction boundary

The v5.0 hash-as-answer-key mechanism does **not** occur in v4.0-v4.9. R-001 starts at v5.0 in this lineage.

## Family A — v4.0-v4.2: corpus-statistic evidence

These versions compute memory/evidence value from corpus-derived statistics rather than semantic target labels. The recurring signals are:

- `recurrence`;
- `cross_context`;
- `predictability`.

The signals are standardized and mutually discounted when correlated. v4.0 states the intended boundary directly: **“Correlated signals discount each other; no semantic labels are used.”**

These are measurements on the observed corpus/model behavior. The evidence channel is not generated from the hidden semantic answer.

**Classification:** mechanism-clean with respect to R-001.

## Family B — v4.3-v4.8: measured consequence evidence

v4.3 is the transition into the graph/factor consequence family: its evidence controller uses measured predictive consequences and explicitly excludes semantic/fact/chain labels from the evidence layer.

v4.4-v4.8 make the multi-consequence form explicit. Their candidate evidence includes:

- `gain_early_mid`;
- `gain_mid_final`;
- `future_support`;
- `context_gain`.

The gain terms are measured changes in model sequence loss across training checkpoints; `future_support` is measured support in later corpus windows; `context_gain` is measured continuation/usefulness improvement. The observations are therefore noisy, continuous, many-to-one, and correlated rather than a unique code of the hypothesis being inferred. The dependency-discounting / factor machinery exists precisely to handle that correlation.

**Classification:** mechanism-clean with respect to R-001. This family is the most relevant historical template for repairing v5.0 with non-oracular consequence evidence.

## v4.9 — legitimate narrow binary arbitration

v4.9 is also clean of the v5.0 defect. `opaque_token(seed, i, prefix)` is an opaque name generator based on the seed/index, not a hash of candidate hypothesis identity. Two structurally symmetric lanes receive independently generated opaque forecasts; a randomized preference determines which terminal's forecast is matched by the environment.

The benchmark deliberately makes consequence agreement the only informative asymmetry and includes `ShuffledTrust`, `FrozenTrust`, and `CoherenceOnlyTrust` controls.

**Supported narrow claim:** consequence-sensitive arbitration can break a deliberately constructed two-way structural tie where coherence-only, frozen, and shuffled trust do not.

**Not supported by v4.9:** arbitration among many semantic hypotheses, natural-language semantic grounding, or independent validation of the later v5.0 semantic-governance claim.

## Preserved-run boundary: proxy evidence

The preserved headline evidence for v4.0-v4.8 is local smoke/proxy evidence, not the notebooks' intended full Shakespeare/KJV interference runs. The notebooks contain full-run paths/instructions, but the natural-corpus headline runs are not preserved in the recovered evidence supplied here.

This distinction must accompany any citation of v4.x results. “Verified local proxy” means the local mechanics ran as reported; it does **not** mean the full natural-corpus experiment was reproduced or preserved.

Observed preserved-run scale in the recovered notebooks:

| version | preserved evidence characterization | reported seed scale |
|---|---|---:|
| v4.0 | local smoke/proxy path; full Colab mode specified separately | smoke path defaults to 3 |
| v4.1 | local proxy verification | 3 |
| v4.2 | local verified proxy test | 3 |
| v4.3 | local proxy verification | 3 |
| v4.4 | local proxy verification | 8 |
| v4.5 | local proxy verification | 8 |
| v4.6 | local proxy verification | 8 |
| v4.7 | local first look | 3 |
| v4.8 | fresh local verification / proxy mode in runner | 3 |
| v4.9 | clean synthetic symmetric-decoy run | 8 |

The later three-seed results (notably v4.3, v4.7, v4.8) should be treated as exploratory/first-pass evidence unless independently replicated at larger scale. v4.4-v4.6 have eight-seed local proxy evidence, which is stronger but remains proxy evidence.

## Scope of this audit

Checked here: whether the evidence/observation is generated from or bijective with the hidden answer being inferred, plus preserved proxy/full-mode boundaries and obvious seed counts.

Not claimed here: a fresh derivation of each notebook's statistical test, paired structure, calibration, or headline number. Those require claim-specific audits.
