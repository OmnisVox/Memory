"""
example_adapter.py

This file shows the intended integration shape.

Replace DummyStateMemory with the project's real 64-D FAISS memory object.
"""

from relational_memory import RelationalMemory, HybridMemory


class DummyStateMemory:
    """
    Placeholder only.
    Replace this with the existing geometric/FAISS memory class.
    """

    def search(self, z, k=5):
        return [
            {
                "similarity": 0.91,
                "note": "placeholder geometric memory result",
            }
        ][:k]


def main():
    state_memory = DummyStateMemory()

    relations = RelationalMemory(
        db_path="agent_memory.sqlite",
        min_confidence=0.35,
        unresolved_threshold=0.45,
    )

    memory = HybridMemory(
        state_memory=state_memory,
        relational_memory=relations,
    )

    # Repeated observations are allowed to increase support.
    relations.observe(
        source="matilda",
        relation="working_on",
        target="memory_system",
        evidence=0.82,
    )

    relations.observe(
        source="memory_system",
        relation="uses",
        target="persistent_state",
        evidence=0.91,
    )

    # Direct relationship lookup.
    print("\nDirect relations:")
    for hit in relations.neighbors("matilda"):
        print(hit)

    # Structural two-hop traversal through exact shared identity.
    print("\nTwo-hop result:")
    result = memory.reason_two_hop("matilda")
    print(result)

    # Existing 64-D state memory remains independent.
    fake_z = [0.0] * 64
    print("\nHybrid recall:")
    print(memory.recall(fake_z, entity="matilda"))

    # Later consequence feedback can change reliability.
    relations.verify(
        source="matilda",
        relation="working_on",
        target="memory_system",
        success=True,
    )

    relations.close()


if __name__ == "__main__":
    main()
