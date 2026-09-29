"""
smoke_test.py

Run:
    python smoke_test.py
"""

import os
import tempfile

from relational_memory import RelationalMemory


def main():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    os.close(fd)

    try:
        mem = RelationalMemory(
            path,
            min_confidence=0.0,
            unresolved_threshold=0.0,
        )

        # A -> B
        mem.observe("A", "r1", "B", evidence=0.9)
        mem.observe("A", "r1", "B", evidence=0.9)

        # B -> C
        mem.observe("B", "r2", "C", evidence=0.9)
        mem.observe("B", "r2", "C", evidence=0.9)

        hits = mem.compose_two_hop("A")

        assert hits, "No composed result was produced."
        assert hits[0].bridge == "b", hits[0]
        assert hits[0].target == "c", hits[0]

        print("PASS")
        print(hits[0])

        mem.close()

    finally:
        try:
            os.remove(path)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    main()
