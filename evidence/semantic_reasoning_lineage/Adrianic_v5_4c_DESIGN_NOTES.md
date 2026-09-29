# Adrianic v5.4c — Persistent Discourse / Serial-Null Design Notes

## Corrections implemented

1. **Fresh per-edge transitions remain restored.** Every adjacency receives an independently sampled referent permutation, family permutation, and direction XOR. Inference sees the exact edge object.
2. **Discourse persists within a chain.** All clauses in a chain reuse the same four entity names, scenario, and context sentence. Only the referring expression and relation template vary. Runtime assertions enforce this.
3. **Marginal head accuracy is locked on the evaluated corpus.** The independent Gaussian test controls are tuned per true class to the semantic arm's observed per-class accuracy on that same persistent-context test corpus. This is a diagnostic matching control, not a held-out generalization estimate.
4. **Sharpness is still fitted on an independent calibration corpus.** Temperature does not change argmax accuracy.
5. **Confusion identity remains geometry-preserving.** Wrong-class identity is remapped while row correctness, true logit, true margin, centered strength, and sorted logit spectrum remain invariant.
6. **Serial statistics use an empirical independent-error null.** For each arm/head, predictions are re-simulated independently from that arm's own empirical one-site confusion matrix on the exact same latent chains and edges. Reported quantities include null mean, null SD, excess, z, and empirical two-sided p.
7. **Direction edge-coherence is removed.** Conditioning on both binary-direction predictions being wrong makes XOR coherence algebraically non-diagnostic.
8. **Ref/family edge-coherence is demoted to a negative control.** Because the clause model never sees the freshly sampled edge permutation, persistent discourse can create correlated error *occurrence* but cannot systematically reveal or follow the edge permutation. Elevated ref/family coherence would therefore suggest leakage/equivariance or some unexpected dependency, not the primary persistence mechanism.

## Primary serial diagnostics

- null-adjusted lag-1 error correlation
- null-adjusted within-chain error-rate variance

These directly test whether a persistent discourse context creates clustered errors beyond what is implied by one-site confusion and the latent state sequence.

## Synthetic validation: persistence without edge-aligned wrong labels

A separate 16-seed audit used the benchmark head accuracies (ref/fam/dir = 0.702/0.566/0.591), fresh per-edge permutations/XOR, and wrong labels sampled independently of the edge constraints. Only chain-level error difficulty was made persistent.

| context error heterogeneity | mean lag-1 error corr | coupling gain |
|---:|---:|---:|
| 0.00 | +0.004 | +19.775 pp |
| 0.05 | +0.014 | +20.215 pp |
| 0.10 | +0.048 | +17.451 pp |
| 0.20 | +0.159 | +16.133 pp |
| 0.30 | +0.357 | +10.322 pp |
| 0.40 | +0.609 | +6.162 pp |
| 0.50 | +0.784 | +1.338 pp |

This is the important validation: **serial dependence in whether observations are wrong is sufficient to erode most of the coupling benefit even when the wrong labels do not form an edge-coherent alternative trajectory.** The empirical v5.4c question is therefore well-posed once discourse context persists.

## Interpretation rule

The semantic arm is interesting only after checking that its marginal factor accuracies match the synthetic control and then asking whether its lag/within-chain variance exceeds the empirical independent-error null. If semantic coupling underperforms and the serial excess is positive, correlated perception errors are a viable mechanism. If semantic coupling underperforms without serial excess, the residual must be sought elsewhere (e.g. higher-order posterior geometry or calibration conditional on context/state).
