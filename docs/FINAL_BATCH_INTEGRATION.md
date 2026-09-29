# Final Batch Integration — Evidence Graph v3, Causal Ablation, Field Replacement

Date: 2026-08-03
Canonical target: 0.3.0 checkpoint

## Sources

- `adrianic_evidence_graph_v3.zip`
- `adrianic_causal_ablation.zip`
- `adrianic_field_replacement_gate.zip`

The original ZIPs are preserved unchanged under `evidence/original_bundles/`.

## What changed in the canonical runtime

### 1. Honest address resolution

The previous core could reject an ambiguous nearest-neighbor match by margin, but it
could still accept a query that was far away from every stored memory if one slot was
merely less bad than the others.

The bank now optionally requires both:

- `best_distance < max_distance`
- `second_distance - best_distance > min_margin`

The recovered field benchmark used 0.20 and 0.035 for one controlled vortex family.
Those are calibration results, not universal defaults.

### 2. Comparative replacement

The recovered causal ledger shows:

- corrected anchors changed trust state for essentially every changed anchor;
- only a minority propagated into different permanent slot state;
- finite-capacity competition could make a locally better value estimate cause a
  globally worse storage decision.

The canonical replacement decision therefore compares candidate future value with the
retained value of the slot that would be destroyed.

Recovered benchmark margins differed:

- abstract benchmark: best tested ~0.16
- field benchmark: best tested ~0.28

The runtime exposes the margin rather than hard-coding either as universal.

### 3. Address state is not recall-template state

The field reintegration exposed phase smearing when damaged complex observations were
arithmetically averaged into a permanent template.

The canonical candidate now keeps:

- an averaged robust address vector;
- the best topology-qualified raw complex template.

A memory may therefore be address-ready while the template remains unresolved.

### 4. Robust routine-anchor cross-check

The recovered original `anchor_filter_test.py` uses a running median/MAD disagreement
threshold between a routine anchor and independently trust-weighted verifier consensus.

Local rerun reproduced the preserved aggregate exactly.

At 20% routine-anchor corruption in the supplied synthetic benchmark:

- precision ~0.9805
- recall ~0.7853
- false positive rate ~0.0039
- raw MAE ~0.3859
- filtered MAE ~0.1054
- error reduction ~72.65%

Important negative result: improved verification accuracy did not by itself improve the
full end-to-end memory objective. The architecture therefore keeps verification,
trust, commit, replacement, and future utility as separately logged causal stages.

### 5. Causal-ablation ledger

The causal-ablation ZIP preserves detailed result ledgers but not the executable source
for cloning controller state and replaying the same 50-event future on raw-vs-corrected
branches.

The canonical project adds a logging schema only. It does not label a reconstructed
branch-cloning experiment as original source.

### 6. Robust topological recall validation

Finite-loop winding is exposed as a reusable validation primitive. Exact global
microscopic plaquette equality is not treated as a robust topological criterion near
amplitude zeros.

## Validation status

- canonical regression suite: 13/13 passing
- canonical Python compile check: pass
- all preserved original ZIP integrity checks: pass
- v3.15 recorded winner check: pass
- recovered Evidence Graph v3 anchor-filter rerun: exact aggregate reproduction
- recovered field replacement integration base: started but did not finish within the
  local 45-second execution window; no pass/fail conclusion is drawn

## Remaining source gaps

- exact v3.15 search runner
- exact v3.16/v3.17 behavioral runner
- exact v3.20 learned-dependency runner
- causal-ablation branch-cloning runner
- final topology-qualified field-replacement runner

Those gaps are explicitly preserved rather than filled by undocumented reconstruction.
