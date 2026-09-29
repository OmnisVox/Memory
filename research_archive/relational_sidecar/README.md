# Relational Memory Sidecar for a Continuous-State SSM

This package is meant to be **patched beside** an existing continuous-state SSM memory system.

It does **not** replace:

- the persistent continuous state vector,
- the FAISS/cosine geometric retrieval path,
- the existing SQLite episodic memory,
- the current interpretability/VAE layer.

It adds one additional memory lane:

> persistent entity / relationship identity with exact-identity two-hop traversal.

---

## Why add this?

A continuous geometric memory is good at questions like:

> "When was the agent in a structurally similar internal state?"

That is useful and should stay.

It is not necessarily good at:

> "What is specifically connected to this exact entity?"

The relational sidecar answers that second kind of question.

The two memory lanes should remain separate because they represent different evidence.

---

# Files

## `relational_memory.py`

Main implementation.

Contains:

- `RelationalMemory`
- `HybridMemory`
- direct relationship lookup
- consequence/reliability updates
- explicit unresolved state
- exact-identity two-hop traversal

## `example_adapter.py`

Minimal example showing how to attach the new relational lane to an existing state-memory object.

## `smoke_test.py`

Tiny isolated test proving that:

```text
A -> B
B -> C
```

can structurally retrieve:

```text
A -> B -> C
```

through the exact same `B`.

---

# Installation

The module itself uses only the Python standard library.

Python 3.10+ is recommended.

No FAISS package is required by this module itself because it does not replace the existing FAISS code.

---

# First test

From this directory:

```bash
python smoke_test.py
```

Expected result:

```text
PASS
ComposedHit(...)
```

Do this **before touching the real agent**.

---

# Integration steps

## 1. Keep the existing state memory unchanged

Do not remove the current 64-D persistent state, FAISS index, episodic memory, or geometric search.

The new module is a sidecar.

---

## 2. Import the sidecar

```python
from relational_memory import RelationalMemory, HybridMemory
```

Initialize it once:

```python
relations = RelationalMemory(
    db_path="agent_memory.sqlite"
)
```

It can safely use the existing SQLite file because it creates its own table:

```text
relational_edges
```

If you prefer isolation during testing, use a separate file first:

```python
relations = RelationalMemory(
    db_path="relational_test.sqlite"
)
```

That is safer for the first integration.

---

## 3. Wrap the existing state memory

Suppose the existing system has:

```python
state_memory.search(z, k=5)
```

Then:

```python
memory = HybridMemory(
    state_memory=state_memory,
    relational_memory=relations,
)
```

If the existing method is named something else, edit this line inside `HybridMemory.recall()`:

```python
geometric = self.state_memory.search(z, k=state_k)
```

That should be the only mandatory API adaptation.

For example, if the real method is:

```python
state_memory.retrieve_similar(z, top_k=5)
```

change it to:

```python
geometric = self.state_memory.retrieve_similar(
    z,
    top_k=state_k,
)
```

---

# Recording relationships

Whenever the agent has an observation that can be represented as:

```text
source --relation--> target
```

record it:

```python
relations.observe(
    source="matilda",
    relation="working_on",
    target="memory_system",
    evidence=0.82,
)
```

A later event might be:

```python
relations.observe(
    source="memory_system",
    relation="uses",
    target="persistent_state",
    evidence=0.91,
)
```

The system now has:

```text
matilda -> memory_system
memory_system -> persistent_state
```

The important structural fact is that `memory_system` is the **same identity** in both observations.

---

# Two-hop structural retrieval

```python
result = memory.reason_two_hop(
    entity="matilda"
)
```

Possible result:

```text
matilda
    -> memory_system
    -> persistent_state
```

No explicit rule saying:

> `working_on + uses = persistent_state`

is encoded.

The bridge exists because the same stored identity appears in both edges.

---

# Direct relation retrieval

```python
hits = relations.neighbors("matilda")

for hit in hits:
    print(
        hit.source,
        hit.relation,
        hit.target,
        hit.confidence,
    )
```

You can optionally constrain the relation:

```python
hits = relations.neighbors(
    "matilda",
    relation="working_on",
)
```

---

# Consequence feedback

Observation and trust are separate.

If a relationship later proves useful/correct:

```python
relations.verify(
    source="matilda",
    relation="working_on",
    target="memory_system",
    success=True,
)
```

If it proves wrong:

```python
relations.verify(
    source="matilda",
    relation="working_on",
    target="memory_system",
    success=False,
)
```

The edge is not immediately deleted.

Its historical reliability changes gradually.

---

# Hybrid recall

The current state lane and relational lane are returned separately:

```python
result = memory.recall(
    z=current_64d_state,
    entity="matilda",
)

similar_states = result["geometric_context"]
relations = result["relational_context"]
```

Do **not** immediately collapse those into one scalar score.

They answer different questions:

```text
geometric context:
    "what past state resembles this state?"

relational context:
    "what is structurally connected to this identity?"
```

A later trust/controller layer can decide how much each deserves to influence behavior.

---

# Suggested connection to the existing interpretability layer

If the current model already has confidence estimates from its VAE/interpreter, treat those as another evidence source.

For example:

```python
decision_context = {
    "state_matches": similar_states,
    "relations": relational_hits,
    "state_confidence": state_confidence,
    "relation_confidence": [
        x.confidence for x in relational_hits
    ],
}
```

Do not allow the interpreter to become an oracle.

A labeled latent dimension should gain or lose trust from downstream consequences.

---

# Recommended identity strategy

This part matters.

Free-form strings are fine for the first test, but eventually entities should have stable IDs.

Good:

```text
person:matilda
project:memory_system
concept:persistent_state
```

Better, once entity resolution exists:

```text
entity_0183
entity_2af1
entity_a952
```

The display name can change while the internal identity stays stable.

The relational system is only as good as identity continuity.

---

# What NOT to do yet

Do not immediately:

1. replace the geometric memory,
2. merge geometric similarity and structural confidence into one number,
3. automatically write every sentence as a relationship,
4. let one repeated source count as many independent proofs,
5. treat a two-hop result as ground truth,
6. delete unresolved relationships aggressively,
7. rewrite the existing episodic database before isolated testing works.

Keep the first patch boring and reversible.

---

# Suggested rollout

## Phase 1 — isolated sidecar

Use a separate SQLite file.

Manually add a few relationships.

Verify:

```text
A -> B
B -> C
```

retrieves:

```text
A -> B -> C
```

Run `smoke_test.py`.

---

## Phase 2 — read-only integration

Let the agent query the relational sidecar, but do not let relational results affect decisions yet.

Log:

- query,
- direct hits,
- two-hop hits,
- confidence,
- geometric-memory result,
- whether the structural result was useful later.

---

## Phase 3 — consequence feedback

Start calling:

```python
relations.verify(...)
```

when a result is later corroborated or contradicted.

Observe whether reliability separates useful from bad relations.

---

## Phase 4 — decision integration

Only after logging shows the relational lane is behaving sensibly should it influence action or generated context.

Keep geometric and relational evidence visible separately in logs.

---

# Important limitation

This module does **not** solve automatic extraction of entities and relations from raw language.

Something upstream still has to decide that an observation corresponds to:

```text
source
relation
target
```

For a first patch this can be explicit/manual or use whatever entity/event representation the project already has.

Do not hide that dependency.

---

# Debugging

## Nothing retrieves

Temporarily lower:

```python
min_confidence=0.0
unresolved_threshold=0.0
```

If retrieval then works, the issue is confidence calibration rather than identity storage.

---

## Wrong entities connect

Inspect normalization and identity creation.

Most relational-memory failures are actually entity-resolution failures.

Do not solve this by lowering thresholds.

---

## Too many repeated edges look certain

The recurrence term already saturates:

```python
1 - exp(-support / 4)
```

If repetition is still overpowering the system, lower the recurrence weight in `_edge_score()`.

---

## Database safety

For first integration use:

```text
relational_test.sqlite
```

rather than the production episodic database.

Once stable, the table can live inside the existing SQLite database if desired.

---

# Architecture in one picture

```text
                 current observation
                         |
              +----------+-----------+
              |                      |
              v                      v
       continuous state z      entity/relation IDs
              |                      |
              v                      v
      FAISS geometric memory   relational sidecar
              |                      |
              |                exact identity joins
              |                      |
              +----------+-----------+
                         |
                         v
                 evidence / trust
                         |
                         v
                 behavior / context
```

The point is not to replace the current system.

The point is to let it remember both:

> "this feels structurally similar"

and

> "this exact thing is connected to that exact thing."

Those are different kinds of memory.
