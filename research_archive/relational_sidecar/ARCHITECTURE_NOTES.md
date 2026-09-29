# Architecture Notes

## Existing lane

The described system already has a persistent continuous state vector and
geometric episodic retrieval. Preserve it.

That lane is well suited to:

- similar internal states,
- similar episodes,
- dynamical context,
- continuity of personality/state.

## Added lane

The sidecar stores sparse directed identity relationships.

That lane is well suited to:

- entity-specific lookup,
- exact identity continuity,
- relational paths,
- explicit provenance/trust updates.

## Why not collapse them?

Cosine similarity is not identity.

Identity is not similarity.

An event can be geometrically similar but involve a different entity.

An event can involve the same entity while occurring in a very different
continuous state.

Keeping the two lanes distinct avoids silently treating those as equivalent.

## Two-hop binding

If the memory contains:

    X -> Y
    Y -> Z

then Y can serve as a structural bridge because it is the exact same identity.

This provides a composition primitive without embedding a hand-written rule
for the semantic meaning of the two relations.

The result remains a candidate and can still be VALUE_UNRESOLVED.

## Confidence

Confidence should not be used as a magical truth score.

The implementation separates:

- recurrence/support,
- current evidence,
- historical consequence reliability.

Those remain inspectable.
