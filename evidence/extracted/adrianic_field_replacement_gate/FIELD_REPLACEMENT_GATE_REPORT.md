# Comparative Replacement Gate — Complex-Field Reintegration

## Question

Does the comparative replacement fix still help once it is wired back into the complex vortex-field memory bank rather than tested only on abstract event identities?

## Addressing correction

The first stream-level integration exposed a bad rule: the bank could choose the nearest stored slot even when every stored slot was far from the query.

A corruption-atlas calibration showed that, for this controlled 24-member vortex family, about 99.7% of same-memory damaged vectors lie below normalized distance 0.20, while nonmatching memories almost never do.

The final resolver therefore requires:

- nearest distance < 0.20,
- best-vs-second-best margin > 0.035.

With that change, wrong resolved addresses were essentially zero.

## 1. Comparative replacement survives field reintegration

The field bank had 8 permanent slots competing over 24 possible vortex memories.

Queries included clean states, total phase wipe, 35% dropout with deterministic repair, mixed amplitude/phase noise, and harder mixed corruption.

The robust address vector remained the transparent 12-D representation:

v = (x1,y1,x2,y2,xc,yc,d, mean_x,mean_y,Sxx,Syy,Sxy).

The old full-bank rule was:

candidate passes commit threshold -> evict weakest slot.

The new rule computes a future-value proxy for the candidate and compares it with the value of the weakest retained slot. Replacement occurs only when the difference exceeds the field-level margin.

Held-out results:

 hard_value  auto_utility  gate_utility  mean_paired_delta  median_paired_delta  fraction_seeds_improved  p05_delta  p95_delta  auto_writes  gate_writes  auto_replacements  gate_replacements  auto_wrong_address_rate  gate_wrong_address_rate
      False      0.891318      0.897766           0.006448             0.005379                 0.866667  -0.001343   0.015204    31.700000    10.400000          23.700000           2.400000                      0.0                      0.0
       True      0.883143      0.895252           0.012109             0.013567                 0.933333  -0.000440   0.022354    42.766667    12.566667          34.766667           4.566667                      0.0                      0.0

Filtered-value stream:

- automatic utility capture: 0.8913
- comparative gate: 0.8978
- paired seeds improved: 86.7%

Hard/noisy-value stream:

- automatic utility capture: 0.8831
- comparative gate: 0.8953
- mean paired improvement: 0.0121
- paired seeds improved: 93.3%

Hard-stream permanent writes fell from about
42.8
to
12.6
per 800 events.

Replacements fell from about
34.8
to
4.6.

The best tested field-level margin was 0.28, not the 0.16 found in the earlier abstract benchmark. That parameter is therefore calibration-dependent, not universal.

## 2. A second integration bug: complex phase smearing

The replacement fix worked, but the first field implementation arithmetic-averaged damaged complex observations into the permanent recall template.

That was a mistake.

The 12-D address vector tolerated averaging because it is deliberately phase-agnostic. The complex template did not.

Arithmetic complex averaging gave mean target overlap near 0.91, while exact microscopic plaquette signatures survived only about 15.6% of stored templates.

So the architecture now separates:

- ADDRESS STATE: averaged robust vector,
- COMPLEX TEMPLATE: best topology-qualified raw observation.

## 3. Topology-qualified template storage

For this vortex-pair family, the transparent template-quality diagnostic uses:

- defect count,
- net winding magnitude on this discretization,
- wrapped phase-gradient smoothness.

Clean members score approximately 1. Phase wipe and strongly corrupted observations score near zero.

A candidate can therefore be ADDRESS_READY while remaining TEMPLATE_UNRESOLVED.

Permanent complex-field storage waits for a topology-quality score above 0.50.

Final topology-qualified results:

 hard_value margin  utility_capture  utility_std  address_precision  wrong_address_rate    writes  replacements   blocked  template_holds  template_overlap_mean  template_overlap_min  exact_topology_rate
      False   0.28         0.852780     0.030558                1.0                 0.0  9.800000      1.800000 22.266667       29.833333                    1.0                   1.0                  1.0
      False   auto         0.846827     0.028472                1.0                 0.0 17.566667      9.566667  0.000000       42.966667                    1.0                   1.0                  1.0
       True   0.28         0.850569     0.030711                1.0                 0.0 11.200000      3.200000 34.366667       38.033333                    1.0                   1.0                  1.0
       True   auto         0.840545     0.031689                1.0                 0.0 23.600000     15.600000  0.000000       54.833333                    1.0                   1.0                  1.0

Stored-template target overlap was 1.0 and the stored topology signature was 100% exact in these runs.

The replacement gate continued to outperform automatic replacement after this extra constraint:

 hard_value  auto_utility  gate_utility  mean_paired_delta  median_paired_delta  fraction_seeds_improved  p05_delta  p95_delta  auto_writes  gate_writes  auto_replacements  gate_replacements  auto_topology_rate  gate_topology_rate
      False      0.846827      0.852780           0.005953             0.005467                 0.766667  -0.012294   0.015623    17.566667          9.8           9.566667                1.8                 1.0                 1.0
       True      0.840545      0.850569           0.010025             0.009662                 0.900000  -0.002648   0.021602    23.600000         11.2          15.600000                3.2                 1.0                 1.0

The cost is delayed availability while a candidate waits for a topology-coherent observation.

## 4. End-to-end field recall

Fresh damaged fields were then generated after training.

Addressing used only the field-derived vector.

For the selected permanent slot, recall used the linear memory relaxation primitive

dpsi/dt = mu_R (chi_j - psi),

with mu_R = 2.5, dt = 0.006 and recall duration 1.6.

Results:

      kind  address_accuracy  overlap_median  loop_winding_recovery
phase_wipe          1.000000        0.999961               1.000000
 dropout35          1.000000        0.999963               1.000000
     mixed          1.000000        0.999957               1.000000
hard_mixed          0.983333        0.999910               0.983333

Phase wipe, dropout and ordinary mixed corruption achieved 100% address success in this test.

Hard mixed corruption achieved about 98.3% address accuracy.

For correctly addressed states, final target overlap was above 0.9999.

## 5. Robust topological metric

A temporary global plaquette-count test gave a misleading failure even when overlap was numerically 1.0.

The reason is mathematical: phase is undefined at amplitude zeros, so microscopic plaquette defect counts can change under arbitrarily tiny residual perturbations.

The recall test therefore uses finite-loop winding around the two recovered cores:

W_C = (1/2pi) sum Arg(psi_(k+1) psi_k*).

Every clean library member has the core-loop signature (+1,-1).

Loop-winding recovery at T=1.6 is shown in the table above.

For hard-mixed corruption, aggregate winding recovery equals address success; conditional on correct addressing, the winding was recovered.

## Conclusion

Within this controlled vortex-family benchmark, the comparative replacement fix does survive complex-field reintegration.

It:

1. improves downstream utility,
2. sharply reduces destructive writes and replacements,
3. remains beneficial under noisier value evidence,
4. does not rely on forced wrong-address guesses,
5. works after complex-template topology is preserved separately from address averaging,
6. supports fresh corrupted-field recall to essentially unit overlap and the correct robust winding.

This is still a structural surrogate memory system, not a term-for-term validation of the original Adrianic nonlinear PDE.

The next full-stack test is to combine the independently tested layers:

corrupted complex field
-> honest field address
-> evidence graph
-> selective commit
-> comparative replacement
-> topology-qualified template
-> field recall.
