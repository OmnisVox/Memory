from __future__ import annotations

import sqlite3
import time
import math
from dataclasses import dataclass
from typing import Optional


@dataclass
class RelationHit:
    source: str
    relation: str
    target: str
    confidence: float
    support: int
    last_seen: float


@dataclass
class ComposedHit:
    source: str
    bridge: str
    target: str
    relation_1: str
    relation_2: str
    score: float
    evidence_1: float
    evidence_2: float


class RelationalMemory:
    """
    Sparse identity/relationship memory designed to sit beside an existing
    continuous-state / FAISS episodic memory.

    It does NOT replace the existing SSM state, FAISS index, or episodic store.

    Structural rule:
        exact identity may bridge two observed relationships

            X --r1--> Y
            Y --r2--> Z

        producing a candidate X -> Z traversal through the same Y.

    No semantic relation-composition rule is built in.
    """

    def __init__(
        self,
        db_path: str,
        min_confidence: float = 0.35,
        unresolved_threshold: float = 0.45,
        reliability_lr: float = 0.08,
    ):
        self.db = sqlite3.connect(db_path)
        self.db.row_factory = sqlite3.Row
        self.min_confidence = float(min_confidence)
        self.unresolved_threshold = float(unresolved_threshold)
        self.reliability_lr = float(reliability_lr)
        self._init_schema()

    def _init_schema(self):
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS relational_edges (
            source TEXT NOT NULL,
            relation TEXT NOT NULL,
            target TEXT NOT NULL,

            support INTEGER NOT NULL DEFAULT 1,
            reliability REAL NOT NULL DEFAULT 0.5,
            evidence REAL NOT NULL DEFAULT 0.5,

            created_at REAL NOT NULL,
            last_seen REAL NOT NULL,

            PRIMARY KEY (source, relation, target)
        );

        CREATE INDEX IF NOT EXISTS idx_rel_source
        ON relational_edges(source);

        CREATE INDEX IF NOT EXISTS idx_rel_target
        ON relational_edges(target);
        """)
        self.db.commit()

    def close(self):
        self.db.close()

    def observe(
        self,
        source: str,
        relation: str,
        target: str,
        evidence: float = 0.5,
    ):
        source = self._norm(source)
        relation = self._norm(relation)
        target = self._norm(target)

        evidence = float(max(0.0, min(1.0, evidence)))
        now = time.time()

        row = self.db.execute(
            """
            SELECT evidence
            FROM relational_edges
            WHERE source=? AND relation=? AND target=?
            """,
            (source, relation, target),
        ).fetchone()

        if row is None:
            self.db.execute(
                """
                INSERT INTO relational_edges
                (
                    source, relation, target,
                    support, reliability, evidence,
                    created_at, last_seen
                )
                VALUES (?, ?, ?, 1, 0.5, ?, ?, ?)
                """,
                (source, relation, target, evidence, now, now),
            )
        else:
            old_e = float(row["evidence"])
            new_e = 0.90 * old_e + 0.10 * evidence

            self.db.execute(
                """
                UPDATE relational_edges
                SET support=support+1,
                    evidence=?,
                    last_seen=?
                WHERE source=? AND relation=? AND target=?
                """,
                (new_e, now, source, relation, target),
            )

        self.db.commit()

    def verify(
        self,
        source: str,
        relation: str,
        target: str,
        success: bool,
    ):
        """
        Update historical reliability when downstream consequences become known.
        """
        source = self._norm(source)
        relation = self._norm(relation)
        target = self._norm(target)

        row = self.db.execute(
            """
            SELECT reliability
            FROM relational_edges
            WHERE source=? AND relation=? AND target=?
            """,
            (source, relation, target),
        ).fetchone()

        if row is None:
            return False

        old = float(row["reliability"])
        outcome = 1.0 if success else 0.0
        new = (
            (1.0 - self.reliability_lr) * old
            + self.reliability_lr * outcome
        )

        self.db.execute(
            """
            UPDATE relational_edges
            SET reliability=?
            WHERE source=? AND relation=? AND target=?
            """,
            (new, source, relation, target),
        )
        self.db.commit()
        return True

    def neighbors(
        self,
        source: str,
        relation: Optional[str] = None,
        limit: int = 20,
    ) -> list[RelationHit]:

        source = self._norm(source)

        if relation is None:
            rows = self.db.execute(
                """
                SELECT *
                FROM relational_edges
                WHERE source=?
                """,
                (source,),
            ).fetchall()
        else:
            rows = self.db.execute(
                """
                SELECT *
                FROM relational_edges
                WHERE source=? AND relation=?
                """,
                (source, self._norm(relation)),
            ).fetchall()

        hits = []
        for row in rows:
            confidence = self._edge_score(row)
            if confidence < self.min_confidence:
                continue

            hits.append(
                RelationHit(
                    source=row["source"],
                    relation=row["relation"],
                    target=row["target"],
                    confidence=confidence,
                    support=int(row["support"]),
                    last_seen=float(row["last_seen"]),
                )
            )

        hits.sort(key=lambda x: x.confidence, reverse=True)
        return hits[:limit]

    def compose_two_hop(
        self,
        source: str,
        relation_1: Optional[str] = None,
        relation_2: Optional[str] = None,
        limit: int = 20,
    ) -> list[ComposedHit]:
        """
        Exact-identity structural join:

            X --r1--> Y
            Y --r2--> Z

        The SAME Y is the bridge.
        """
        source = self._norm(source)

        first = self.neighbors(
            source,
            relation=relation_1,
            limit=100,
        )

        results = []

        for edge_1 in first:
            second = self.neighbors(
                edge_1.target,
                relation=relation_2,
                limit=100,
            )

            for edge_2 in second:
                score = math.sqrt(
                    max(0.0, edge_1.confidence)
                    * max(0.0, edge_2.confidence)
                )

                if score < self.unresolved_threshold:
                    continue

                results.append(
                    ComposedHit(
                        source=source,
                        bridge=edge_1.target,
                        target=edge_2.target,
                        relation_1=edge_1.relation,
                        relation_2=edge_2.relation,
                        score=score,
                        evidence_1=edge_1.confidence,
                        evidence_2=edge_2.confidence,
                    )
                )

        results.sort(key=lambda x: x.score, reverse=True)
        return results[:limit]

    def _edge_score(self, row) -> float:
        """
        Keep consequence reliability, current evidence, and recurrence distinct.
        Recurrence saturates so repetition is not treated as independent proof.
        """
        reliability = float(row["reliability"])
        evidence = float(row["evidence"])
        support = int(row["support"])

        recurrence = 1.0 - math.exp(-support / 4.0)

        return (
            0.45 * reliability
            + 0.40 * evidence
            + 0.15 * recurrence
        )

    @staticmethod
    def _norm(x: str) -> str:
        return " ".join(str(x).strip().lower().split())


class HybridMemory:
    """
    Thin adapter over:
      1) an existing geometric/FAISS state-memory lane
      2) the structural relational-memory lane

    The two lanes remain separate because they answer different questions.
    """

    def __init__(self, state_memory, relational_memory: RelationalMemory):
        self.state_memory = state_memory
        self.relational = relational_memory

    def recall(
        self,
        z,
        *,
        entity: Optional[str] = None,
        relation: Optional[str] = None,
        state_k: int = 5,
    ):
        """
        IMPORTANT:
        Adapt ONLY the search call below to the existing FAISS/state-memory API.
        """
        geometric = self.state_memory.search(z, k=state_k)

        relational = []
        if entity is not None:
            relational = self.relational.neighbors(
                entity,
                relation=relation,
            )

        return {
            "geometric_context": geometric,
            "relational_context": relational,
        }

    def reason_two_hop(
        self,
        entity: str,
        relation_1: Optional[str] = None,
        relation_2: Optional[str] = None,
    ):
        hits = self.relational.compose_two_hop(
            source=entity,
            relation_1=relation_1,
            relation_2=relation_2,
        )

        if not hits:
            return {
                "status": "VALUE_UNRESOLVED",
                "results": [],
            }

        return {
            "status": "RESOLVED",
            "results": hits,
        }
