# Adrianic v3.21 — Latent Common-Cause Evidence Model

This experiment extends learned residual-dependency control from pairwise graph edges to low-rank latent error factors.

Compared controllers:
- equal source weighting;
- scalar per-source trust;
- hard pairwise residual-correlation graph;
- single top residual factor;
- multi-factor residual model using up to three leading covariance eigenvectors;
- oracle hidden dependence labels.

Verified source errors update an exponentially weighted residual covariance matrix. The single-factor controller uses the top eigenvector. The multi-factor controller keeps distinct high-loading source families from up to three leading factors and caps each family's aggregate voting weight. This lets the system represent both the adversarial alias family and an intermittent common-mode factor instead of forcing both into one latent direction.

Tests:
- independent-source negative control;
- intermittent common-mode failure affecting A/B/D/E;
- factor reversal where the hidden affected set changes halfway through;
- sparse-verification sweep;
- bad durable-memory-write rate.

These are transparent dependency/factor inference tests. They do not establish causal direction, and the loading/strength thresholds remain hand-set.
