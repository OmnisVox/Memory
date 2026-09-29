# v5.0 Oracle-Control Audit

This note accompanies Retraction Ledger entry R-001.

## Surviving source-level facts

The v5.0 semantic model retains top-k relation/direction proposals. Its pooled held-out
semantic measurements in the supplied eight-seed artifact are:

- top-1 accuracy: 0.2609375
- top-5 coverage: 0.7671875

These measurements occur before consequence governance and are not invalidated by the
forecast-code defect.

## Invalid inference path

The governance experiment creates a unique deterministic forecast for each
`(case_id, label)` pair. Clean external evidence is the correct label's forecast code. Trust
is then updated by exact forecast/observation equality. Thus the evidence observation
identifies the correct retained label by construction.

The original shuffled-trust control does not remove this information channel; it scrambles
it. A uniform-prior control on the same evidence is the more diagnostic test.

## Reproducible project control

Run:

```bash
python tools/replay_v50_oracle_control.py
```

The script reads only the preserved `8seed_semantic_proposals.csv`; it does not retrain the
transformer. It reproduces the original semantic-prior governed accuracy using the original
random-number stream and compares it with equal proposal priors.

Expected source-exact seed-mean results:

- noise 0.00: semantic 0.966301, uniform 1.000000
- noise 0.15: semantic 0.784456, uniform 1.000000
- noise 0.30: semantic 0.667044, uniform 0.976414

The purpose of this replay is falsification and regression protection, not to replace the
original experiment with a new positive claim.
