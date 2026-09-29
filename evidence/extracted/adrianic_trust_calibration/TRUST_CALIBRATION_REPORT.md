# Adrianic Trust-Calibrated Memory Study

## Goal

Test whether the consequence-aware memory controller can learn **which value signals deserve trust**
instead of treating all claims of importance as equally reliable.

The tests include:

- a reliable value source,
- a noisy source,
- an adversarial source,
- a biased/bursty source,
- sparse objective verification,
- correlated colluding aliases,
- a source-quality reversal halfway through a run,
- disagreement-based confidence gating,
- and common-mode corruption where many sources are wrong together.

No learned neural policy is used. Every trust update is explicit.

## 1. Source reliability model

For source s with reported utility u_s and later verified outcome y, define

q_s = exp(-|u_s-y| / sigma).

Reliability is an exponential running estimate:

rho_s(t+1) = (1-eta) rho_s(t) + eta q_s.

A running signed bias estimate is also maintained:

b_s(t+1) = (1-eta)b_s(t) + eta(u_s-y).

The de-biased report is u_s - b_s.

For trust-weighted aggregation:

w_s is proportional to rho_s^gamma.

The best tested exponent in a small sweep was around gamma = 3, which made high-reliability
sources dominate without converting trust into a hard binary switch.

## 2. Main trust benchmark

Across 24 seeds:

              config  utility_capture  utility_std  wrong_recall_rate     writes  critical_slots  junk_slots  useful_slots  rare_critical_hit  frequent_junk_hit    rho_A    rho_B    rho_C    rho_D
 equal_g1.0_capFalse         0.670286     0.039185           0.179028 170.083333        2.583333       2.625         7.375           0.805872           0.523833 0.892865 0.757745 0.245503 0.552595
learned_g3.0_capTrue         0.779827     0.035714           0.145463  95.583333        2.958333       0.750         9.250           0.895130           0.229612 0.892865 0.757745 0.245503 0.552595
 oracle_g1.0_capTrue         0.825846     0.030322           0.090000  66.458333        2.958333       0.500         9.500           0.893674           0.085589 0.892865 0.757745 0.245503 0.552595

Mean true downstream utility capture:

- equal source weighting: **0.670**
- learned trust: **0.780**
- oracle source weights: **0.826**

Thus transparent learned trust recovered a substantial part of the oracle advantage.

The learned source reliabilities were approximately:

- A, strong source: **0.893**
- B, noisy source: **0.758**
- C, adversarial source: **0.246**
- D, biased/bursty source: **0.553**

The memory bank also held fewer junk memories and made fewer permanent writes than equal weighting.

## 3. How much verification is necessary?

 verify_prob  utility_capture  wrong_recall_rate   writes  critical_slots  junk_slots    rho_A    rho_C
        0.00         0.631229           0.178125 204.9375          2.5625      3.0000 0.500000 0.500000
        0.02         0.716025           0.177656 123.5625          2.8125      1.5000 0.863514 0.259214
        0.05         0.755447           0.172969  99.0000          2.8750      1.0000 0.890091 0.232665
        0.10         0.775246           0.142461  83.3750          2.8125      0.8125 0.892943 0.218540
        0.30         0.782209           0.139180  83.6875          3.0000      0.7500 0.901681 0.218283
        0.60         0.784053           0.136680  80.1250          2.8750      0.6875 0.885855 0.223254

With no objective verification, all sources remained near their identical initial trust and
utility capture was only about **0.631**.

Even **2% objective verification** raised capture to about
**0.716**.

At 10% it reached about
**0.775**,
and performance was already close to its plateau by 30%.

This is an important boundary: source trust cannot be grounded from source claims alone.
Some independent verification or equivalent external consequence signal is required.

## 4. Correlated-source collusion

Three adversarial aliases were added that shared the same underlying causal source.

If aliases are allowed to vote independently, copying one bad source creates artificial consensus.

A provenance rule was therefore added:

> Multiple identities sharing one provenance group receive approximately one source's total voting weight.

Results:

 verify_prob  provenance_cap  utility_capture  wrong_recall_rate  writes  junk_slots  critical_slots
        0.00           False         0.496381           0.175400   70.20        5.00            2.10
        0.00            True         0.539799           0.160000  152.80        4.55            1.95
        0.02           False         0.584482           0.170100  136.45        3.05            2.50
        0.02            True         0.668512           0.174267  128.85        1.90            2.60
        0.05           False         0.634555           0.178167  127.40        2.35            2.70
        0.05            True         0.710329           0.166933  108.55        1.35            2.85

At 2% verification, utility capture improved from about
**0.584**
without provenance control to about
**0.669**
with provenance grouping.

The average number of junk slots also fell.

So source count is not the same thing as independent evidence.

## 5. Source-quality reversal

Halfway through a stream, source A changed from reliable to misleading, while source B became reliable.

        config  pre_capture  early_post_capture  late_post_capture  rho_A_final  rho_B_final  writes
adaptive_trust     0.764844            0.796856           0.818244     0.252623     0.894567   113.1
         equal     0.653986            0.667693           0.625251     0.252623     0.894567   199.7
  trust_frozen     0.764844            0.771283           0.700761     0.893615     0.733888   205.8

A controller that learned trust initially and then froze it fell to late post-change utility capture of
about **0.701**.

Adaptive trust recovered to about
**0.818**.

Its final reliability estimates reversed appropriately:

- A fell to approximately **0.253**
- B rose to approximately **0.895**

Therefore **trust itself needs an adaptation timescale**.

## 6. Disagreement gating: a useful negative result

A simple rule was tested that withheld value feedback whenever the sources disagreed strongly.

That did **not** solve the problem. Overly aggressive confidence gating reduced useful consequence
evidence and allowed recurrence to regain too much influence.

The corrected rule is:

> Untrusted value evidence should produce HOLD, not silently convert the controller back into a recurrence-only system.

This distinction is important.

## 7. Verified consequence as a separate evidence tier

Objective verification was then used for two separate purposes:

1. calibrate source reliability, and
2. directly update the candidate's value estimate.

Under severe common-mode poisoning, direct verified outcomes improved the system as verification
became more available, but did not eliminate the attack.

 verify_prob  confidence_min  utility_capture  wrong_recall_rate     writes  junk_slots  critical_slots  useful_slots  feedback_accept_rate
        0.02             0.0         0.619274           0.162292 137.500000    2.777778        2.555556      7.222222              1.000000
        0.02             0.2         0.594177           0.172292 134.111111    2.777778        2.555556      7.222222              0.929965
        0.05             0.0         0.649493           0.173160 134.555556    2.388889        2.777778      7.611111              1.000000
        0.05             0.2         0.653330           0.174097 133.833333    2.388889        2.833333      7.611111              0.969653
        0.10             0.0         0.670697           0.167083 129.222222    2.055556        2.722222      7.944444              1.000000
        0.10             0.2         0.678003           0.164236 127.222222    2.055556        2.833333      7.944444              0.982535
        0.30             0.0         0.707315           0.166528 131.888889    1.555556        2.833333      8.444444              1.000000
        0.30             0.2         0.696856           0.166424 133.388889    2.222222        2.777778      7.777778              0.993056

At 30% verification, true utility capture was around **0.707**
under this deliberately difficult common-mode corruption.

This remains the strongest unresolved failure in the current trust architecture.

## 8. What is now established inside the benchmark

1. Per-source reliability is a functional memory-control signal.
2. Sparse independent verification can be enough to distinguish reliable, noisy and adversarial sources.
3. Trust-weighted value estimates outperform equal source weighting.
4. Trust must remain adaptive because source quality can change.
5. Provenance matters: duplicate identities do not constitute independent corroboration.
6. HOLD must apply to uncertain value evidence itself, not merely to memory candidates.
7. Verified consequences are qualitatively different from unverified reports and deserve a separate evidence tier.
8. Coordinated/common-mode corruption remains difficult because agreement does not imply truth.

## 9. Current glass-box evidence hierarchy

A useful current hierarchy is:

Level 0: raw value claim
Level 1: source-debiased claim
Level 2: trust-weighted claim
Level 3: independently corroborated claim
Level 4: objectively verified consequence

The memory controller should never collapse these levels into one undifferentiated number.

## 10. Next hard problem

The current unresolved issue is **common-mode failure**.

If multiple sources are wrong for the same hidden reason, ordinary agreement and individual source
reputation are insufficient.

The next defensible extension would model:

- causal/provenance independence,
- correlated error history,
- confidence in the verifier itself,
- and explicit `VALUE_UNRESOLVED` state when no sufficiently independent evidence exists.

That would turn trust from a scalar reputation score into a small transparent evidence graph.
