# Adrianic v3.18 — Trust-Calibrated Regime Adaptation

v3.18 combines the seven-role fault-tolerant memory with the uploaded transparent
trust-calibration layer.

Per-source reliability uses:

    q_s = exp(-|u_s-y|/sigma)
    rho_s <- (1-eta)rho_s + eta q_s
    b_s <- (1-eta)b_s + eta(u_s-y)

and trust weights are proportional to rho_s^3.

Sources are cue/current evidence, current field, working memory, durable A/B,
and recurrence. A/B share a provenance group so duplicate memory evidence does
not multiply its voting power.

If evidence is insufficient or highly conflicting, the controller returns
VALUE_UNRESOLVED/HOLD rather than silently falling back to recurrence.

The hard test changes the field physics and reverses the action polarity
mid-run, making previously useful durable memories semantically wrong. Trust
must adapt from sparse verified consequences. Later, A/B are physically
corrupted; parity repairs their integrity, while trust determines whether the
repaired memories deserve influence.
