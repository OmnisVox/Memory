# Adrianic Multi-Slot Memory Study

## Goal
Extend the validated single complex memory field into a transparent multi-slot memory bank,
then test capacity, addressing, corruption tolerance, ambiguity handling, and finite-capacity
replacement.

This study intentionally does **not** add oscillators or semantic interpretation. It tests
memory architecture only.

---

## 1. Memory-slot architecture

Each slot stores:

- complex dynamical template \(\chi_j(x,y)\),
- a transparent content vector \(\mathbf v_j\),
- usage count,
- recency,
- optional label/context metadata.

The recall primitive remains:

\[
\left.\frac{\partial\psi}{\partial t}\right|_{j}
=
\mu_R(\chi_j-\psi).
\]

The main new problem is **addressing**: given a damaged query, which slot should be recalled?

---

## 2. The vector structure was ablated rather than guessed

A 28-dimensional candidate vector was built from three interpretable groups:

1. defect-core geometry,
2. global amplitude moments,
3. a coarse spatial amplitude map.

Ablation on a 24-slot bank gave:

         group  mean_accuracy  worst_accuracy  mean_margin
  core+moments       0.998264        0.993056     0.278856
 core_geometry       0.997396        0.989583     0.384577
        all_28       0.940972        0.833333     0.127704
      core+map       0.940972        0.833333     0.140910
    coarse_map       0.747396        0.465278     0.089964
   moments+map       0.746528        0.465278     0.078569
global_moments       0.522569        0.090278     0.000715

The best representation was **core geometry + global moments**, a compact 12-D vector.

Mean exact retrieval accuracy across complete phase wipe, 50% dropout, amplitude noise,
and mixed corruption:

**0.9983**

Worst corruption-class accuracy:

**0.9931**

The larger 28-D vector was worse, showing that adding more state variables can reduce
retrieval quality when those variables are noisy. In this narrow benchmark, the useful
representation became *smaller* through ablation.

The current 12-D vector is:

\[
\mathbf v =
(x_1,y_1,x_2,y_2,x_c,y_c,d,
\bar x_A,\bar y_A,\Sigma_{xx},\Sigma_{yy},\Sigma_{xy}).
\]

The first seven terms describe the two recovered low-amplitude cores and their geometry.
The last five describe global amplitude location and covariance.

---

## 3. Dropout-aware preprocessing

Random pixel dropout initially confused defect-core detection.

A deterministic inpainting stage was added only when the exact-zero fraction exceeded
a threshold. Missing pixels are filled iteratively from valid neighboring amplitudes before
the vector is computed.

For the original 12-slot geometry descriptor, 50% dropout addressing improved from
approximately **16%** to **100%** in the tested seeds.

This improvement is specific to the synthetic dropout model, where erased pixels are exactly
zero; it should not be assumed to generalize to arbitrary sensor damage without further tests.

---

## 4. Capacity scaling

Using the compact robust vector, independent banks were tested up to 48 memories.

Capacity-scaling results:

 capacity corruption  accuracy  margin_median  margin_05
       12  amp_noise  0.968750       0.564395   0.030243
       12 dropout_50  1.000000       0.606668   0.350282
       12      mixed  1.000000       0.583266   0.396351
       12 phase_wipe  1.000000       0.607345   0.607345
       24  amp_noise  0.958333       0.320695   0.008775
       24 dropout_50  1.000000       0.362714   0.360416
       24      mixed  0.984375       0.335450   0.294407
       24 phase_wipe  1.000000       0.363832   0.363832
       36  amp_noise  0.927083       0.191018   0.000396
       36 dropout_50  1.000000       0.233573   0.231704
       36      mixed  0.989583       0.207983   0.169003
       36 phase_wipe  1.000000       0.234842   0.234842
       48  amp_noise  0.914062       0.144874   0.000031
       48 dropout_50  1.000000       0.186571   0.184693
       48      mixed  0.984375       0.160635   0.122516
       48 phase_wipe  1.000000       0.187823   0.187823

End-to-end 48-slot address-and-recall:

corruption  address_accuracy  final_target_overlap_median  final_target_overlap_05  final_selected_overlap_median
 amp_noise          0.912500                     0.999980                 0.994359                       0.999980
dropout_50          0.995833                     0.999959                 0.999959                       0.999959
     mixed          0.983333                     0.999929                 0.999918                       0.999929
phase_wipe          1.000000                     0.999949                 0.999912                       0.999949

The conservative end-to-end results at 48 slots were:

- complete phase wipe: address accuracy **1.0000**
- 50% dropout: **0.9958**
- mixed corruption: **0.9833**
- amplitude noise: **0.9125**

When the correct slot was selected, the existing dynamical recall primitive returned the
state to approximately unit overlap.

These 48 memories all belong to a controlled vortex-pair family. This is **not** a claim
of 48-slot capacity for arbitrary information.

---

## 5. Honest uncertainty: HOLD UNRESOLVED

A confidence margin is defined from the nearest two slot distances:

\[
\Delta_D = D_{(2)}-D_{(1)}.
\]

A held-out threshold was calibrated from addressing errors. If \(\Delta_D\) is too small,
the bank returns **HOLD UNRESOLVED** instead of choosing a slot.

Held-out 48-slot results:

corruption  resolution_rate  raw_accuracy  wrong_answer_rate  correct_answer_rate  precision_when_answered
 amp_noise         0.643750      0.927083           0.001042             0.642708                 0.998382
dropout_50         0.987500      0.998958           0.000000             0.987500                 1.000000
     mixed         0.917708      0.973958           0.000000             0.917708                 1.000000
phase_wipe         1.000000      1.000000           0.000000             1.000000                 1.000000

Under amplitude noise, the bank answered only about
**0.644**
of queries, but when it answered its precision was
**0.9984**.

For phase wipe, mixed corruption and 50% dropout, answered-query precision was 100% in this
held-out test.

This provides a direct glass-box mechanism for uncertainty rather than forcing a guess.

---

## 6. Fundamental ambiguity test

Two memories were constructed with identical amplitudes but opposite phase chirality.

Their amplitude difference was exactly zero, while their complex fields were distinct.

Results:

         query  target  trusted_phase  selected  held_unresolved  correct                        mode
      A_intact       0           True       0.0            False      1.0         phase_disambiguated
      B_intact       1           True       1.0            False      1.0         phase_disambiguated
  A_phase_wipe       0          False       NaN             True      NaN amplitude_only_hold_if_tied
  B_phase_wipe       1          False       NaN             True      NaN amplitude_only_hold_if_tied
A_random_phase       0          False       NaN             True      NaN amplitude_only_hold_if_tied
B_random_phase       1          False       NaN             True      NaN amplitude_only_hold_if_tied

With intact trustworthy phase, the phase signature distinguishes them.

After a complete phase wipe or randomized phase, the query contains no reliable information
that identifies which chirality was intended. The bank therefore returns **HOLD UNRESOLVED**.

This is not a failure of the selector; it is an information-theoretic ambiguity. A contextual
cue or prior-state metadata is required to resolve it.

---

## 7. Finite-capacity replacement

An 8-slot bank was exposed to a 24-memory demand stream with Zipf-like usage frequencies.

Replacement policies:

 policy  hit_rate  hit_rate_std  exact_retrieval  top8_retention
utility   0.72910      0.024930              1.0        0.815625
    lfu   0.72355      0.030669              1.0        0.765625
    lru   0.65795      0.028846              1.0        0.634375
   fifo   0.60280      0.027812              1.0        0.590625

The best tested transparent utility rule was:

\[
U_j = \frac{n_j}{1+\alpha\,a_j},
\]

where \(n_j\) is use count and \(a_j\) is time since last use.

It produced a mean hit rate of **0.7291**,
versus **0.6028** for FIFO.

Thus even simple explicit utility metadata improves which memories survive when capacity is
smaller than demand.

---

## 8. What this establishes

Within this numerical vortex-field benchmark:

1. Independent complex memory slots prevent the direct overwrite problem of one shared \(\chi\).
2. Multi-slot addressing is feasible with an explicit, interpretable state vector.
3. Ablation selected a compact 12-D representation over a noisier 28-D representation.
4. Up to 48 controlled-family memories were addressed with high accuracy under severe
   phase corruption and dropout.
5. Addressing—not the recall dynamics—is now the principal scaling bottleneck.
6. A confidence-margin rule allows the system to refuse ambiguous recalls.
7. Some ambiguities are fundamental: lost phase information cannot be recreated by the
   address vector without context.
8. A simple transparent utility score improves finite-slot replacement.

---

## 9. Current limitations

- The memory library consists of structured vortex-pair fields, not arbitrary semantic data.
- Core geometry is unusually informative for this family; other domains will require different
  state descriptors.
- Exact-zero dropout is easy to detect and inpaint compared with realistic noisy missing data.
- Capacity has not been measured beyond 48 controlled patterns.
- No semantic value, intention, cognition, or consciousness is implied by these tests.
- The bank does not yet decide *whether an experience is worth committing*; it only manages
  slots once a commit request exists.

---

## 10. Next memory-only step

Before adding oscillators, the highest-value extension is a selective commit controller:

\[
\text{INCLUDE} \;|\; \text{EXCLUDE} \;|\; \text{HOLD UNRESOLVED}.
\]

It can use transparent novelty, confidence, expected reuse, interference cost and available
capacity, while logging every reason for every decision.
