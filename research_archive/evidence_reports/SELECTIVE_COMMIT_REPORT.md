# Adrianic Selective Commit Controller Study

## Objective
Test a fully transparent permanent-memory decision layer on top of the multi-slot complex
memory bank.

The controller has three explicit outcomes:

\[
\boxed{\text{INCLUDE}\;|\;\text{EXCLUDE}\;|\;\text{HOLD}}
\]

No learned black-box policy is used.

## Architecture

A new observation first enters a provisional candidate buffer rather than consuming a
permanent memory slot immediately.

For candidate \(c\), the controller measures:

- support / recurrence \(n_c\),
- consistency or stability \(S_c\),
- novelty relative to existing permanent memories \(N_c\),
- finite-bank replacement utility.

The tested rule is approximately:

\[
\text{INCLUDE if }
n_c\ge 3,\qquad
S_c\ge 0.90,\qquad
N_c\ge 0.06.
\]

A one-off experience remains HOLD and expires if it never earns additional support.
An experience already represented by an existing slot is EXCLUDE as redundant.
Unstable repeated candidates can be EXCLUDE rather than consolidated.

HOLD is not amnesia: provisional candidates remain available as short-term memory while
the controller decides whether they deserve permanent storage.

## Stability calibration

The original 0.80 stability threshold was too permissive. Controlled vector perturbations
showed:

    condition  median_stability      p10      p90  pass_at_0.80
  stable_0.05          0.995863 0.993941 0.997172         1.000
moderate_0.20          0.935824 0.907342 0.955707         1.000
unstable_0.35          0.816172 0.742461 0.870450         0.614

A threshold near 0.90 retained all low-noise candidates in this diagnostic while rejecting
about 98% of the high-variance candidates. This is a model-specific calibration, not a
universal constant.

## Permanent-memory benchmark

The benchmark contains:

- 8 high-value recurring memories,
- 8 lower-frequency recurring memories,
- one-off transient experiences,
- an 8-slot permanent bank.

The always-commit baseline writes every miss immediately.
The selective controller requires evidence before permanent consolidation.

Fresh held-out results across 100 seeds:

   policy  top_hit  secondary_hit  weighted_utility  top8_retention  transient_commits  permanent_writes  useful_slots  hits_per_write
immediate 0.895484       0.122563          0.663608         0.83375             241.78            481.93          7.52         0.00138
selective 0.958912       0.446569          0.805209         0.88000               0.00             40.09          8.00         0.02055

Headline comparison:

                          metric  always_commit  selective_commit  relative_change
       weighted useful-hit score       0.663608          0.805209         0.213380
             top-memory hit rate       0.895484          0.958912         0.070830
       secondary-memory hit rate       0.122563          0.446569         2.643581
permanent writes per 1200 events     481.930000         40.090000        -0.916814
               transient commits     241.780000          0.000000        -1.000000
                 top-8 retention       0.833750          0.880000         0.055472

The selective controller:

- improved the weighted useful-memory score from
  **0.664 to 0.805**,
- improved top-memory hit rate from
  **0.895 to 0.959**,
- improved secondary-memory hit rate from
  **0.123 to 0.447**,
- reduced permanent writes from about
  **481.9 to 40.1 per 1,200 events**,
- reduced transient permanent commits from
  **241.8 to 0** in this benchmark.

Permanent-write reduction:

**91.68%**

Thus the gain is not merely lower write activity; after tuning, the selective controller
also kept the useful memories available more often.

## Why provisional HOLD matters

A controller that requires recurrence but provides no provisional memory pays an avoidable
recall penalty while an experience is being evaluated.

Allowing HOLD candidates to remain temporarily retrievable separates:

- **short-term availability**
from
- **long-term consolidation**.

That is a useful architectural distinction independent of any biological analogy.

## Parameter sweep

The best tested region used:

- 3 supporting encounters,
- novelty threshold approximately 0.06,
- stability threshold approximately 0.90.

Top sweep results:

 support  novelty  top_hit  secondary_hit  top8_retention  transient_commits  writes  useful_slots  utility_score
       3     0.06 0.958807       0.444129        0.878125                0.0  40.325           8.0       0.784241
       3     0.10 0.958775       0.444129        0.878125                0.0  40.325           8.0       0.784219
       3     0.14 0.890959       0.469453        0.856250                0.0  37.250           8.0       0.745882
       2     0.06 0.948901       0.376823        0.884375                0.0  82.450           8.0       0.736053
       2     0.10 0.943880       0.383346        0.875000                0.0  81.875           8.0       0.734782
       2     0.14 0.874756       0.388582        0.843750                0.0  69.675           8.0       0.694066
       2     0.18 0.855643       0.381195        0.837500                0.0  65.975           8.0       0.680321
       3     0.18 0.763082       0.471400        0.781250                0.0  29.525           8.0       0.660815
       3     0.22 0.739209       0.468419        0.768750                0.0  27.550           8.0       0.644197
       2     0.22 0.770482       0.391126        0.803125                0.0  58.525           8.0       0.627413

The result is not monotonic: excessive novelty thresholds reject useful nearby memories,
while a support count of only 2 writes more aggressively.

## Distribution-shift check

The same selective rule was tested with transient-event fractions of roughly 10%, 20%,
and 35%:

           mix    policy  weighted  top_hit  secondary_hit     writes  transient_commits
          base immediate  0.662295 0.888603       0.134241 483.616667         237.416667
          base selective  0.819580 0.960299       0.491234  49.600000           0.000000
high_transient immediate  0.642033 0.852647       0.150600 659.366667         417.050000
high_transient selective  0.813744 0.941242       0.516249  46.316667           0.000000
 low_transient immediate  0.673448 0.894516       0.157623 393.250000         118.016667
 low_transient selective  0.827073 0.958343       0.520777  64.783333           0.000000

The selective controller retained its advantage across all three mixes in this synthetic
workload and made zero transient permanent commits in the tested runs.

## Interpretation

Within this numerical memory benchmark, permanent storage benefits from being an explicit
decision rather than an automatic consequence of observation.

The controller now has concrete operational meanings for:

### INCLUDE
The experience is recurrent, stable enough, sufficiently novel, and worth allocating or
replacing a permanent slot.

### EXCLUDE
The experience is already represented, or is too inconsistent to justify consolidation.

### HOLD
There is not yet enough evidence to decide. The candidate can remain provisionally
available without consuming a permanent slot.

This is the first tested version of a memory architecture in which **uncertainty and
selective consolidation are distinct from forgetting**.

## Current limitations

- The task is synthetic and uses controlled vortex-derived address vectors.
- 'Value' is represented by future recurrence/usefulness in the benchmark, not semantic value.
- The controller does not yet predict utility from consequences; it estimates utility from
  recurrence, stability, novelty, use count and recency.
- The benchmark labels are used only for scoring; the decision rule itself operates on vectors.
- Stable-but-harmful information and rare-but-important information are not yet represented.
- The next test should introduce consequence-based value so a rare event can still earn storage
  when its measured downstream utility is high.

## Recommended next memory-only extension

Add an explicit glass-box value term:

\[
V_c =
w_r R_c +
w_n N_c +
w_s S_c +
w_u U_c
-
w_i I_c,
\]

where:

- \(R_c\): recurrence evidence,
- \(N_c\): novelty,
- \(S_c\): stability,
- \(U_c\): measured downstream utility,
- \(I_c\): predicted interference / slot cost.

Then commit only when \(V_c\) crosses a visible threshold, while logging every component
that caused INCLUDE, EXCLUDE or HOLD.
