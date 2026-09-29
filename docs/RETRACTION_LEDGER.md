# Retraction Ledger

Date opened: 2026-08-03

This ledger records **claim-level retractions**, not architecture deletion. A failed or
confounded experiment can invalidate an empirical claim without refuting the design it
was intended to test.

## R-001 — v5.0 semantic consequence governance

**Origin:** `Adrianic_v5_0_SemanticProposal_ConsequenceGovernance_*`

**Status:** EMPIRICAL CLAIM RETRACTED. ARCHITECTURE REMAINS OPEN / UNREFUTED.

### Defect

v5.0 defines a deterministic forecast code from `(case_id, candidate_label)` and then,
when evidence is clean, generates the external observation using the forecast code of
the case's grounded/correct label. The update rule awards trust by exact forecast-string
agreement.

Therefore the evidence channel is a per-case bijection onto the hypothesis being inferred.
The comment that no *relation class* receives a privileged consequence symbol is true but
insufficient: the **correct label for each case is privileged** because the observation is
constructed from that label's unique code.

The required control is not shuffled trust. Shuffling destroys the answer-bearing code
along with the trust assignment. The required control is to keep the same retained
hypotheses and same evidence stream while removing the semantic prior.

### Claims retracted at v5.0

The supplied v5.0 experiment does **not** demonstrate that:

1. a transformer is successfully acting as a proposal generator rather than a truth source;
2. consequence evidence rescues transformer-misranked semantic hypotheses;
3. shuffled trust demonstrates a legitimate causal contribution from consequence evidence;
4. adaptive-vs-frozen performance after the grounding shift demonstrates learned semantic
   re-grounding.

Those four claims are measured through the answer-bearing evidence construction.

### Measurement that survives

The semantic proposal model's own held-out proposal coverage is independent of the
consequence channel and remains a valid measurement for this artifact:

- top-1 semantic accuracy: **0.2609375** pooled;
- top-5 semantic coverage: **0.7671875** pooled.

This supports only the narrow statement that retaining multiple plausible parses materially
increases coverage on this synthetic held-out semantic task.

### Architecture not retracted

The proposed architecture — a proposal generator feeding an evidence-weighted arbitration
layer — is **not refuted** by this finding. The experiment failed to test that architecture
cleanly. A repaired many-to-one or otherwise non-answer-bearing evidence model may give the
semantic prior a genuine disambiguation/tiebreaking role. That remains an empirical question.

### Stronger finding under the missing control

A no-retraining replay over the original retained v5.0 proposals shows that replacing the
transformer proposal probabilities with a uniform prior improves governed covered-case
accuracy at every tested evidence-noise level.

Researcher-supplied audit:

| noise | semantic prior | uniform prior | semantic - uniform | semantic wins | Wilcoxon p |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.9663 | 1.0000 | -3.37 pp | 0/8 | 0.031 |
| 0.15 | 0.8088 | 1.0000 | -19.12 pp | 0/8 | 0.008 |
| 0.30 | 0.6750 | 0.9801 | -30.51 pp | 0/8 | 0.008 |

Canonical source-exact replay (preserving the original script's random-number consumption,
including the post-shift phase) gives:

| noise | semantic prior | uniform prior | semantic - uniform | semantic wins | ties | exact p |
|---:|---:|---:|---:|---:|---:|---:|
| 0.00 | 0.966301 | 1.000000 | -3.3699 pp | 0/8 | 2 | 0.03125 |
| 0.15 | 0.784456 | 1.000000 | -21.5544 pp | 0/8 | 0 | 0.0078125 |
| 0.30 | 0.667044 | 0.976414 | -30.9370 pp | 0/8 | 0 | 0.0078125 |

The noisy values differ slightly between the two replay implementations because their RNG
streams are consumed differently. The clean result is identical, and both implementations
show the same qualitative inversion at every noise level. Neither replay is elevated to a
new unquestioned base; both are retained as audit evidence.

### Blast radius

**Retracted/contaminated claims currently identified:**

- v5.0 semantic proposal + consequence governance;
- v5.1 entity/coreference semantic-governance claims using the same evidence construction;
- v5.2 pre-repair reports that inherit the same base;
- v5.3 progressive-recall conclusions that depend on `common_v51.py` governance;
- v5.5 ontology-growth conclusions to the extent their consequence channel depends on the
  inherited answer-bearing construction.

`Adrianic_v5_3_and_later_code_pack.zip` explicitly describes `common_v51.py` as the
"verified v5.1 ... consequence-governance base". v5.3 imports its `forecast_code`; the
shared base contains the same SHA-256 `(case_id, hypothesis)` bijection. This is the
propagation mechanism.

**Claim-level audit still required:** v5.4 learned mention-role proposal imports
`evaluate_governance` from `common_v51.py`, but its mention-role subclaim and its downstream
governance subclaim must be separated before assigning a blanket retraction.

### Clean / separate lineage boundary

**R-001 stops at v5.0. Nothing in v4.x inherits the v5.0 hash-as-answer-key mechanism.**

The v4.x evidence lineage separates into two mechanically different families:

- **v4.0-v4.2:** corpus-statistic evidence (`recurrence`, `cross_context`, `predictability`) with correlation-based mutual discounting and no semantic labels in evidence generation;
- **v4.3-v4.8:** measured consequence/factor evidence. v4.3 is the transition into this family; v4.4-v4.8 explicitly use the multi-consequence channels `gain_early_mid`, `gain_mid_final`, `future_support`, and `context_gain`. These are noisy, continuous, many-to-one measurements rather than answer codes.

v4.9 is also clean of R-001. Its opaque tokens name objects/forecasts rather than encode the candidate hypothesis. It deliberately constructs two structurally symmetric alternatives and randomizes which terminal receives matching downstream consequence evidence. Its `ShuffledTrust`, `FrozenTrust`, and `CoherenceOnlyTrust` controls support a **narrow binary tie-breaking claim**. It must not be cited as evidence for arbitration among many semantic hypotheses.

A separate evidence-strength boundary applies: the preserved v4.0-v4.8 headline runs are local smoke/proxy runs; the intended full Shakespeare/KJV interference runs are not preserved in the supplied evidence. Later local seed counts are also modest (v4.3/v4.7/v4.8: 3; v4.4-v4.6: 8). See `docs/V4_EVIDENCE_BOUNDARIES.md`.

The memory runtime package and the separately repaired coupled lineage are not retracted by R-001.

### Open question

The sharpest unresolved question is now: **with non-oracular, many-to-one consequence
evidence, does a semantic prior help, hurt, or become neutral?**

The v5.0 oracle control says the semantic prior is net harmful when evidence already uniquely
encodes the answer. That does not predict its contribution once the evidence channel is
repaired. A repaired experiment must test semantic vs shuffled/uniform priors under matched
non-oracular evidence and report the comparison directly.

### Process lesson

This defect had unusually high leverage because it lived in a small shared helper with a
reassuring fairness comment and was later centralized in a dependency described as a
"verified base." Future shared-base promotion requires an explicit **information-flow audit**:
for every generated observation, target, reward, checksum, or consequence, ask whether it is
computable from, bijective with, or otherwise leaks the hidden answer being evaluated.
