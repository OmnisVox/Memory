# Integration Checklist

Use this while patching.

## Before editing the real model

- [ ] Unzip into a separate directory.
- [ ] Run `python smoke_test.py`.
- [ ] Confirm `PASS`.
- [ ] Read the "What NOT to do yet" section in README.
- [ ] Decide whether first test uses a separate SQLite file.

## Minimal code integration

- [ ] `from relational_memory import RelationalMemory, HybridMemory`
- [ ] Create one `RelationalMemory(...)` instance.
- [ ] Pass the existing FAISS/state-memory object to `HybridMemory(...)`.
- [ ] Adapt the single `.search(z, k=...)` line if the existing API differs.
- [ ] Do not modify the existing 64-D state update.

## First data test

- [ ] Add a known `A -> B`.
- [ ] Add a known `B -> C`.
- [ ] Confirm `compose_two_hop("A")` returns a path through `B`.
- [ ] Confirm wrong/unrelated identities do not bridge.
- [ ] Test an unresolved case.

## Logging

Log at least:

- [ ] query identity
- [ ] direct relation hits
- [ ] two-hop relation hits
- [ ] confidence
- [ ] geometric-memory hits
- [ ] later success/failure
- [ ] relation reliability changes

## Only after the above works

- [ ] connect consequence feedback with `verify(...)`
- [ ] test with real episodic data
- [ ] test duplicate observations
- [ ] test contradictory observations
- [ ] test stale relationships
- [ ] test renamed/display-name entities with stable internal IDs
- [ ] consider feeding relational evidence into the existing confidence layer

## Do not claim yet

- [ ] automatic semantic understanding
- [ ] general logical reasoning
- [ ] reliable relation extraction from raw text
- [ ] that geometric memory is obsolete

The patch is a structural sidecar, not a replacement architecture.
