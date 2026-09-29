# Original runner rerun status

- **v3.18 — PASS:** recovered original runner completed locally and regenerated
  `results.json` exactly matching the recovered bundle.
- **v3.19 — NOT COMPLETED:** source is preserved, but the full runner exceeded the
  local execution window on repeated attempts. This is recorded as a timeout, not
  as a scientific failure.
- **v3.21 — PASS:** recovered original runner completed locally and regenerated
  `results.json` exactly matching the recovered bundle.
