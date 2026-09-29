# Adrianic v5.3+ code pack

This pack starts at **v5.3** and contains the next three experimental harnesses.
All scripts import `common_v51.py`, which is the verified v5.1 entity/coreference + consequence-governance base.

## v5.3 — Progressive Evidence-Gated Semantic Recall

File: `v53_progressive_recall.py`

Question: **Can recalling more variables help without keeping the entire hypothesis space active all the time?**

Mechanism:

1. Start with the top 4 semantic parses.
2. Update trust from downstream consequence evidence.
3. If the active set is unresolved, recall 4 more hypotheses.
4. Replay already-observed evidence into the newly recalled candidates.
5. Stop growing when evidence resolves the competition or the 24-parse compute ceiling is reached.

The expansion decision does not see the answer key.

Smoke-run status: **executed successfully** with a reduced local configuration. In that smoke run progressive recall beat fixed K=8 at all three noise levels, but it expanded close to the full 24-candidate ceiling on many cases. That is an actual residual: the current resolution criterion is conservative.

Example:

```bash
python v53_progressive_recall.py --seeds 4
```

## v5.4 — Learned Mention-Role Proposal

File: `v54_learned_mention_roles.py`

Removes the deterministic known-name slotter from inference. A character-level token encoder plus contextual Transformer proposes which raw tokens fill discourse roles `<n0>..<n3>`. Those learned slots are then handed to the existing semantic parser and consequence-governance layer.

This is a supervised synthetic mention detector, **not unrestricted open-world NER**.

Smoke-run status: **executed successfully** at deliberately reduced training epochs. The low-epoch smoke test had poor exact mention-role accuracy, so the code path is verified but the architecture is not claimed solved.

Example:

```bash
python v54_learned_mention_roles.py --seeds 4
```

## v5.5 — Consequence-Grounded Ontology Slot Growth

File: `v55_consequence_ontology_growth.py`

Starts with no named ontology slots. Semantic relation vectors and opaque downstream consequence vectors are assigned to growing unlabeled prototypes. A new prototype is born only when both semantic and consequence residuals are too large for existing slots. Human relation names are used only for post-hoc evaluation.

Boundary: the semantic encoder itself is still supervised on the synthetic relation task, so this is **prototype/ontology growth around learned semantics**, not fully unsupervised language ontology induction.

Smoke-run status: **executed successfully**. A reduced one-seed run grew 6 slots and showed higher held-out cluster purity when consequence evidence was used than in the semantic-only assignment ablation. Treat that only as a mechanics check, not a final benchmark.

Example:

```bash
python v55_consequence_ontology_growth.py --seeds 4
```

## Dependency

`common_v51.py` is included locally. Run the scripts from this directory so the import resolves:

```bash
cd adrianic_v53_plus
python v53_progressive_recall.py --seeds 4
```

## Scientific status

- v5.3: runnable + smoke-run verified; full multi-seed benchmark still needed.
- v5.4: runnable + smoke-run verified; mention discovery remains an open bottleneck.
- v5.5: runnable + smoke-run verified; ontology-growth claim remains intentionally narrow.

No later version in this pack should be called fully verified until its intended full-seed gate has actually been run.
