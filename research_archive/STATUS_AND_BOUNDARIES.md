# Status and boundaries

## Strongest memory-only evidence preserved here

- Multi-slot addressing: compact 12-D representation reported mean exact retrieval ~0.9983 across
  the tested corruption battery, worst corruption-class accuracy ~0.9931.
- Selective commit: in the reported 100-seed benchmark, weighted useful-hit score improved while
  permanent writes dropped from roughly 482 to 40 per 1,200 events; transient permanent commits
  dropped to zero in the tested runs.
- Timescale separation: 24:1 recall/update cadence reported balanced score ~0.9747 versus ~0.9487
  for equal continuous cadence at matched rates; source-of-surprise control materially improved
  several memory-damage conditions.

## What is not established

- These results do not establish general-purpose semantic memory in arbitrary real-world data.
- The complex-field/address benchmarks are synthetic and specialized.
- Some thresholds are model-specific calibrations, not universal constants.
- Parity/checksum mechanisms are engineered error-control redundancy.
- Developmental birth/prune/search occurs inside an engineered candidate substrate.
- Later semantic models do not imply the earlier memory mechanisms remained fully integrated.
- The archive is not evidence of AGI or consciousness.

## Productization recommendation

Treat this archive as the source-of-truth research bundle.

A commercial/dev package should expose a narrow interface around:
- provisional observe
- retrieve
- unresolved/hold
- consequence verification
- commit/reject
- save/load
- audit decision path

Keep developmental architecture search and experimental semantic consumers behind optional modules
until their integration is regression-tested against the memory-only benchmarks.
