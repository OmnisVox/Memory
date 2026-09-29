# Adrianic Memory Project — Canonical Reconstruction

A self-contained project base assembled from the recovered Adrianic memory lineage.

**Current checkpoint: 0.4.1.** The project now includes a formal claim-retraction ledger.
The v5.0 semantic consequence-governance demonstration is retracted because its evidence
channel encoded the correct retained hypothesis; the architecture concept itself remains open.
The retraction starts at v5.0: v4.x uses different non-oracular evidence mechanisms, with
separate proxy-run and small-sample boundaries documented explicitly.

This repository is deliberately split into **runtime code**, **original evidence**,
and **research experiments** so later work cannot silently replace earlier mechanisms.

## Start here

- `docs/ARCHITECTURE.md` — complete layer map
- `docs/RECONSTRUCTION_LOG.md` — what was restored, what was reconstructed, and why
- `docs/PROJECT_STATUS.md` — current capabilities and unresolved gaps
- `docs/RETRACTION_LEDGER.md` — claim-level retractions and blast radius
- `docs/V50_ORACLE_CONTROL_AUDIT.md` — reproducible no-retraining v5.0 falsification control
- `docs/V4_EVIDENCE_BOUNDARIES.md` — v4.x mechanism families, proxy-run boundaries, and seed counts
- `evidence/MANIFEST.json` — SHA-256 and ZIP-integrity manifest for original bundles

## Install locally

```bash
python -m pip install -e .
```

For tests:

```bash
python -m pip install -e ".[dev]"
pytest -q
```

## Smoke example

```bash
python examples/canonical_smoke.py
```

## Core package

`src/adrianic_memory/`

- `complex_field.py` — complex slow-memory primitive
- `timescale.py` — source-of-surprise learn/recall triage
- `bank.py` — finite transparent addressable memory
- `consolidation.py` — INCLUDE / EXCLUDE / HOLD
- `parity.py` — P/Q integrity repair
- `evidence.py` — reliability, bias, provenance, dependency-aware value
- `dependency.py` — learned residual dependency / latent factor interfaces
- `roles.py` — recovered seven-role architecture definitions
- `relational.py` — sparse relational sidecar
- `engine.py` — narrow integrated API and audit log

## Original evidence

`evidence/original_bundles/` contains the supplied ZIPs unchanged.

Notably recovered:
- v3.15 seven-slot search
- v3.16 behavioral consolidation
- v3.17 frozen transfer
- v3.18 trust adaptation
- v3.19 evidence graph
- v3.20 learned dependency graph
- v3.21 latent common-cause model
- multi-slot memory study
- messy-world memory study
- trust-calibration study
- relational sidecar
- v5.3+ semantic/reasoning code pack

## Project philosophy

1. No “latest notebook wins.”
2. No reconstructed mechanism is labeled original.
3. No result-only bundle is silently converted into a fake reproduction.
4. Every permanent architecture change should have:
   - hypothesis,
   - source/provenance,
   - ablation/control,
   - regression test,
   - reason for retention/removal,
   - log entry.

That rule is now part of the project, not just a working preference.


## v0.3 recovered full-stack corrections

The final recovered bundles add four important engineering constraints to the canonical core:

- **honest address resolution**: a query must be close enough in absolute distance *and* win by a sufficient margin;
- **comparative replacement**: a full bank compares candidate future value against the retained value of the slot that would be destroyed;
- **dual address/template representation**: robust address state may be averaged, but topology-sensitive complex recall templates are stored from the best qualified raw observation rather than phase-smeared by arithmetic averaging;
- **robust verification cross-check + causal logging**: imperfect routine anchors can be cross-checked against independent verifier consensus, and verification-to-memory propagation can be logged as an explicit causal ledger.

The calibrated thresholds reported by the vortex-family experiments remain benchmark-specific and are not treated as universal constants.
