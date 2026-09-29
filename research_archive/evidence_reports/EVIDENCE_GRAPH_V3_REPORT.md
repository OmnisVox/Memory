# Evidence Graph v3 — Imperfect Anchors, Adaptive Adversary, and Field Reintegration

## What was attempted

This round combined three tests:

1. routine verification anchors that can themselves be wrong,
2. an adaptive adversary that changes its attack according to current trust and common-cause alarms,
3. reintegration of the memory-address layer with the complex vortex-field representation.

The evidence test is still synthetic. It is not a term-for-term simulation of the original nonlinear field operator.

## 1. Imperfect-anchor end-to-end test

Routine anchors were corrupted on 0%, 5%, 10%, or 20% of checks. The adversary observed effective source trust and switched among targeted attacks, correlated C-cluster attacks, and low-and-slow bias.

Aggregate results:

 anchor_corrupt policy  utility_capture  post_capture  writes  unresolved  junk_slots  anchor_trust    rho_A    rho_E  common_faults  E_faults
           0.00  naive         0.819028      0.773419    66.1        45.2         4.3      0.705039 0.680590 0.674347            0.0       0.0
           0.00 robust         0.818197      0.762271    80.9        51.1         4.6      0.705039 0.499802 0.513924            0.1       0.5
           0.05  naive         0.820340      0.777338    59.4        92.1         4.3      0.705039 0.650676 0.653217            0.0       0.0
           0.05 robust         0.820852      0.767146    81.0        55.7         4.8      0.705039 0.495946 0.520919            0.1       0.4
           0.10  naive         0.830032      0.793076    55.1       116.6         4.2      0.696820 0.646179 0.648770            0.0       0.0
           0.10 robust         0.818926      0.760927    82.6        56.1         4.5      0.696820 0.537265 0.544802            0.1       0.3
           0.20  naive         0.849916      0.826300    43.9       164.8         3.5      0.696820 0.607351 0.612166            0.0       0.0
           0.20 robust         0.813662      0.752011    81.5        53.1         4.4      0.696820 0.546616 0.536065            0.1       0.3

### Important negative result

The first robust anchor layer did **not** outperform the naive controller in end-to-end utility capture.

Worse, the naive controller appeared to improve as more routine anchors were corrupted. That is a red flag, not a success. In this synthetic workload, bad anchor feedback accidentally reduced memory churn and acted like a crude regularizer. Therefore utility capture alone is confounded and cannot be used to claim that corrupted verification improved the system.

A gated robust variant also failed to improve the end-to-end metric:

 anchor_corrupt  utility_capture  post_capture  writes  unresolved  verify_unresolved  junk_slots  anchor_trust    rho_A    rho_E
           0.10         0.808474      0.758185 70.1250     41.6250             6.9375      4.1875      0.704220 0.528901 0.500306
           0.20         0.812454      0.764274 70.1875     41.3750             8.5000      4.0000      0.698662 0.539965 0.535781
           0.35         0.813875      0.764450 70.6875     40.6875            10.8125      4.1250      0.698662 0.535990 0.526711

A second cross-checked end-to-end variant likewise remained around 0.81 utility capture:

 anchor_corrupt  utility_capture  post_capture  writes  unresolved  junk_slots    rho_A    rho_E  flags
           0.10         0.810177      0.763306 68.8125     40.8125      4.3125 0.501379 0.488115  9.750
           0.20         0.806830      0.757225 66.9375     40.9375      4.2500 0.466374 0.485283 10.875
           0.35         0.806632      0.757598 67.5625     41.2500      4.2500 0.489006 0.489671 12.250

So the honest conclusion is:

> imperfect anchors are **not solved** at the full memory-controller level yet.

## 2. Direct anchor-error detection

The failure above motivated isolating the verification problem itself.

A routine anchor was compared with a separately trust-weighted verifier consensus. A running robust disagreement threshold (median + MAD) flagged anomalous routine anchors. Flagged anchors were replaced by the verifier consensus; unflagged anchors were blended with it.

Results across 30 seeds:

 corrupt_prob  precision   recall  false_positive_rate  raw_mae  filtered_mae  error_reduction
         0.05   0.710770 0.862965             0.018739 0.124420      0.080375         0.350437
         0.10   0.885432 0.844147             0.012088 0.211894      0.086712         0.589079
         0.20   0.980484 0.785271             0.003865 0.385931      0.105380         0.726487
         0.35   0.995433 0.612493             0.001485 0.652945      0.167225         0.743738

At 20% corrupted routine anchors:

- corruption-flag precision was about 0.980,
- recall was about 0.785,
- false-positive rate was about 0.0039,
- verification MAE fell from 0.386 to 0.105.

That is roughly a 72.6% reduction in verification error.

At 35% corruption the detector remained very precise, but recall fell substantially. In other words, once bad anchors become common enough, a running robust baseline begins to normalize the corruption itself.

This is a useful failure boundary.

## 3. Why lower anchor error did not yet improve memory utility

The direct filter clearly improved verification accuracy, but that improvement did not propagate into the full memory benchmark.

This means the remaining bottleneck is downstream of anchor filtering. Likely contributors in this synthetic controller are:

- source-trust updates are still too sensitive to the verification schedule,
- memory replacement/commit thresholds can turn reduced verification noise into increased write churn,
- the utility-capture objective rewards some accidental conservative behavior,
- the adversary changes tactics as trust changes, so improving one evidence channel changes the attack distribution.

The correct next step is therefore not to tune the anchor filter until the final metric looks good. It is to add causal ablations between:

anchor error -> source trust -> commit count -> slot composition -> final utility.

## 4. Complex-field reintegration

The first field reintegration omitted the previously validated dropout-aware inpainting stage, and 35% random pixel dropout collapsed exact addressing to about 17%.

That reproduced an earlier known failure mode.

After restoring deterministic zero-dropout repair before the 12-D field-vector extractor, the result became:

corruption  address_accuracy   margin
   dropout               1.0 0.396572
     mixed               1.0 0.374917
phase_wipe               1.0 0.398226

All three tested corruption classes reached 100% exact addressing in this controlled 12-memory vortex-family benchmark.

This is **not** arbitrary-memory capacity. It shows that the transparent field-derived address vector still works when the known damage-repair stage is present.

## 5. What this round actually established

1. An adaptive adversary can expose coupling between verification, source trust, and memory policy that simpler static tests miss.
2. Treating imperfect routine anchors as just another scalar trust problem is insufficient.
3. Direct cross-checking can detect bad anchors with high precision and sharply reduce verification error.
4. Better verification accuracy does not automatically imply better end-to-end memory utility.
5. The benchmark objective itself can be confounded by accidental regularization, so intermediate causal metrics are necessary.
6. The complex-field address layer remains robust after restoring dropout-aware preprocessing.

## 6. Strong next architecture test

The next defensible test is a **causal ablation ledger** for every verification event:

- raw anchor error,
- whether the anchor was filtered,
- source-trust delta caused by that event,
- dependency-edge delta,
- candidate commit-score delta,
- whether a slot was written/replaced,
- change in later recall utility.

That would tell us exactly where improved evidence quality is being lost before it becomes improved memory behavior.

After that causal path is stable, the evidence controller can be driven directly from the field-derived memory vectors instead of synthetic event labels.
