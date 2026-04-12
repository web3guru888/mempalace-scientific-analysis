"""
sqlite_kg_backend.py — SQLite concrete KGBackend
=================================================

Wraps ``sqlite3`` to implement the :class:`KGBackend` interface.  This is
the *current* production backend, mirroring the raw SQL patterns found in
``knowledge_graph_bridge.py``, ``kg_pathfinder.py``, and ``kg_pheromones.py``.

All connections use WAL mode and a 10-second timeout for safe concurrent
access (matching the pattern used throughout the integration codebase).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from .kg_backend import KGBackend

logger = logging.getLogger(__name__)


def _entity_id(name: str) -> str:
    """Normalise an entity name to its canonical ID form.

    Matches ``KnowledgeGraph._entity_id`` and the normalisation used
    in ``GraphAdapter`` and ``PheromoneManager``.
    """
    return name.lower().replace(" ", "_").replace("'", "")


class SQLiteKGBackend(KGBackend):
    """SQLite-backed :class:`KGBackend`.

    Connects to the same ``triples`` / ``entities`` / ``triple_provenance``
    tables that ``knowledge_graph.py`` (MemPalace upstream) creates.

    Args:
        db_path: Path to the SQLite database file.
        auto_create_schema: If ``True`` (default), create tables if they
            don't exist.  Set to ``False`` when the DB is managed by
            upstream ``KnowledgeGraph``.
    """

    # Pheromone columns that may need to be added via ALTER TABLE
    _PHEROMONE_COLUMNS = [
        ("success_pheromone", "REAL DEFAULT 0.0"),
        ("traversal_pheromone", "REAL DEFAULT 0.0"),
        ("recency_pheromone", "REAL DEFAULT 0.0"),
        ("pheromone_level", "REAL DEFAULT 0.0"),
    ]

    def __init__(
        self,
        db_path: str,
        *,
        auto_create_schema: bool = True,
        **kwargs: Any,
    ) -> None:
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        if auto_create_schema:
            self._ensure_schema()

        logger.debug("SQLiteKGBackend initialized: %s", db_path)

    # ── Connection helper ─────────────────────────────────────────────

    def _conn(self) -> sqlite3.Connection:
        """Open a WAL-mode connection with Row factory."""
        conn = sqlite3.connect(self.db_path, timeout=10)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.row_factory = sqlite3.Row
        return conn

    def close(self) -> None:
        """No persistent connection to close (connections are per-call)."""
        pass

    # ── Schema management ─────────────────────────────────────────────

    def _ensure_schema(self) -> None:
        """Create core tables and indices if they don't exist.

        Matches the schema from ``knowledge_graph.py`` and adds
        pheromone columns from ``kg_pheromones.py``.
        """
        conn = self._conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS entities (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                type TEXT DEFAULT 'unknown',
                properties TEXT DEFAULT '{}',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS triples (
                id TEXT PRIMARY KEY,
                subject TEXT NOT NULL,
                predicate TEXT NOT NULL,
                object TEXT NOT NULL,
                valid_from TEXT,
                valid_to TEXT,
                confidence REAL DEFAULT 1.0,
                source_closet TEXT,
                source_file TEXT,
                extracted_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (subject) REFERENCES entities(id),
                FOREIGN KEY (object) REFERENCES entities(id)
            );

            CREATE INDEX IF NOT EXISTS idx_triples_subject ON triples(subject);
            CREATE INDEX IF NOT EXISTS idx_triples_object ON triples(object);
            CREATE INDEX IF NOT EXISTS idx_triples_predicate ON triples(predicate);
            CREATE INDEX IF NOT EXISTS idx_triples_valid ON triples(valid_from, valid_to);
        """)

        # Add pheromone columns if missing
        existing_cols = {
            row[1] for row in conn.execute("PRAGMA table_info(triples)").fetchall()
        }
        for col_name, col_def in self._PHEROMONE_COLUMNS:
            if col_name not in existing_cols:
                try:
                    conn.execute(f"ALTER TABLE triples ADD COLUMN {col_name} {col_def}")
                    logger.info("Added column triples.%s", col_name)
                except sqlite3.OperationalError:
                    pass  # Column already exists (race condition)

        conn.commit()
        conn.close()

    # ── Triple CRUD ───────────────────────────────────────────────────

    def add_triple(
        self,
        subject: str,
        predicate: str,
        object: str,
        confidence: float = 1.0,
        source: Optional[str] = None,
        timestamp: Optional[str] = None,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        source_closet: Optional[str] = None,
        source_file: Optional[str] = None,
    ) -> str:
        sub_id = _entity_id(subject)
        obj_id = _entity_id(object)
        pred = predicate.lower().replace(" ", "_")

        conn = self._conn()

        # Auto-create entities
        conn.execute(
            "INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)",
            (sub_id, subject),
        )
        conn.execute(
            "INSERT OR IGNORE INTO entities (id, name) VALUES (?, ?)",
            (obj_id, object),
        )

        # Check for existing identical active triple (idempotent)
        existing = conn.execute(
            "SELECT id FROM triples WHERE subject=? AND predicate=? AND object=? "
            "AND valid_to IS NULL",
            (sub_id, pred, obj_id),
        ).fetchone()

        if existing:
            conn.close()
            return existing[0]

        # Generate deterministic ID
        ts = timestamp or valid_from or datetime.now().isoformat()
        triple_id = (
            f"t_{sub_id}_{pred}_{obj_id}_"
            f"{hashlib.md5(f'{ts}{datetime.now().isoformat()}'.encode()).hexdigest()[:8]}"
        )

        conn.execute(
            """INSERT INTO triples
               (id, subject, predicate, object, valid_from, valid_to,
                confidence, source_closet, source_file)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                triple_id, sub_id, pred, obj_id,
                valid_from, valid_to, confidence,
                source_closet or source, source_file,
            ),
        )
        conn.commit()
        conn.close()
        return triple_id

    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[Any] = []

        if subject:
            conditions.append("subject = ?")
            params.append(_entity_id(subject))
        if predicate:
            conditions.append("predicate = ?")
            params.append(predicate.lower().replace(" ", "_"))
        if object:
            conditions.append("object = ?")
            params.append(_entity_id(object))
        if not include_expired:
            conditions.append("(valid_to IS NULL OR valid_to = '')")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        conn = self._conn()
        rows = conn.execute(
            f"SELECT * FROM triples {where} ORDER BY extracted_at DESC LIMIT ?",
            params + [limit],
        ).fetchall()
        conn.close()

        return [self._row_to_dict(row) for row in rows]

    def get_entity_relations(
        self,
        entity: str,
        direction: str = "both",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        eid = _entity_id(entity)
        conn = self._conn()
        results: List[Dict[str, Any]] = []

        if direction in ("outgoing", "both"):
            rows = conn.execute(
                "SELECT * FROM triples WHERE subject = ? "
                "AND (valid_to IS NULL OR valid_to = '') LIMIT ?",
                (eid, limit),
            ).fetchall()
            results.extend(self._row_to_dict(r) for r in rows)

        if direction in ("incoming", "both"):
            remaining = limit - len(results)
            if remaining > 0:
                rows = conn.execute(
                    "SELECT * FROM triples WHERE object = ? "
                    "AND (valid_to IS NULL OR valid_to = '') LIMIT ?",
                    (eid, remaining),
                ).fetchall()
                results.extend(self._row_to_dict(r) for r in rows)

        conn.close()
        return results

    def get_edge_info(
        self,
        source: str,
        target: str,
    ) -> Optional[Dict[str, Any]]:
        src = _entity_id(source)
        tgt = _entity_id(target)
        conn = self._conn()
        row = conn.execute(
            """SELECT id, predicate, confidence FROM triples
               WHERE ((subject = ? AND object = ?) OR (subject = ? AND object = ?))
                 AND (valid_to IS NULL OR valid_to = '')
               ORDER BY confidence DESC
               LIMIT 1""",
            (src, tgt, tgt, src),
        ).fetchone()
        conn.close()

        if row is None:
            return None
        return {
            "id": row["id"],
            "predicate": row["predicate"],
            "confidence": float(row["confidence"]) if row["confidence"] else 0.5,
        }

    def resolve_entity(self, name: str) -> Optional[str]:
        eid = _entity_id(name)
        conn = self._conn()

        row = conn.execute(
            "SELECT subject FROM triples WHERE subject = ? LIMIT 1",
            (eid,),
        ).fetchone()
        if row:
            conn.close()
            return eid

        row = conn.execute(
            "SELECT object FROM triples WHERE object = ? LIMIT 1",
            (eid,),
        ).fetchone()
        conn.close()
        return eid if row else None

    # ── Counts & stats ────────────────────────────────────────────────

    def count_triples(self) -> int:
        conn = self._conn()
        n = conn.execute("SELECT COUNT(*) FROM triples").fetchone()[0]
        conn.close()
        return n

    def count_entities(self) -> int:
        conn = self._conn()
        n = conn.execute("SELECT COUNT(*) FROM entities").fetchone()[0]
        conn.close()
        return n

    def get_all_entities(self, limit: int = 1000) -> List[str]:
        conn = self._conn()
        rows = conn.execute(
            "SELECT id FROM entities ORDER BY id LIMIT ?", (limit,),
        ).fetchall()
        conn.close()
        return [row["id"] for row in rows]

    # ── Pheromone operations ──────────────────────────────────────────

    def update_pheromone(
        self,
        triple_id: str,
        column: str,
        amount: float,
        mode: str = "add",
    ) -> None:
        conn = self._conn()
        if mode == "set":
            conn.execute(
                f"UPDATE triples SET {column} = ? WHERE id = ?",
                (amount, str(triple_id)),
            )
        else:  # "add"
            conn.execute(
                f"UPDATE triples SET {column} = COALESCE({column}, 0.0) + ? WHERE id = ?",
                (amount, str(triple_id)),
            )
        conn.commit()
        conn.close()

    def decay_pheromones(self, rates: Dict[str, float]) -> int:
        conn = self._conn()
        # Build SET clause for all pheromone columns present in rates
        set_parts = []
        params = []
        for col, rate in rates.items():
            set_parts.append(f"{col} = COALESCE({col}, 0.0) * (1.0 - ?)")
            params.append(rate)

        if not set_parts:
            conn.close()
            return 0

        cur = conn.execute(
            f"UPDATE triples SET {', '.join(set_parts)}", params,
        )
        updated = cur.rowcount
        conn.commit()
        conn.close()
        return updated

    def get_pheromone_levels(self, triple_id: str) -> Optional[Dict[str, float]]:
        conn = self._conn()
        row = conn.execute(
            """SELECT COALESCE(success_pheromone, 0.0)   AS sp,
                      COALESCE(traversal_pheromone, 0.0) AS tp,
                      COALESCE(recency_pheromone, 0.0)   AS rp
               FROM triples WHERE id = ?""",
            (str(triple_id),),
        ).fetchone()
        conn.close()

        if row is None:
            return None
        return {
            "success": float(row["sp"]),
            "traversal": float(row["tp"]),
            "recency": float(row["rp"]),
        }

    def get_pheromone_stats(self) -> Dict[str, Any]:
        conn = self._conn()
        row = conn.execute(
            """SELECT
                   AVG(COALESCE(success_pheromone, 0))   AS avg_success,
                   MAX(COALESCE(success_pheromone, 0))   AS max_success,
                   AVG(COALESCE(traversal_pheromone, 0)) AS avg_traversal,
                   MAX(COALESCE(traversal_pheromone, 0)) AS max_traversal,
                   AVG(COALESCE(recency_pheromone, 0))   AS avg_recency,
                   MAX(COALESCE(recency_pheromone, 0))   AS max_recency,
                   SUM(CASE WHEN COALESCE(success_pheromone, 0) > 0
                       THEN 1 ELSE 0 END)   AS nonzero_success,
                   SUM(CASE WHEN COALESCE(traversal_pheromone, 0) > 0
                       THEN 1 ELSE 0 END) AS nonzero_traversal,
                   SUM(CASE WHEN COALESCE(recency_pheromone, 0) > 0
                       THEN 1 ELSE 0 END)   AS nonzero_recency,
                   COUNT(*) AS total_triples
               FROM triples"""
        ).fetchone()
        conn.close()

        if row is None or row["total_triples"] == 0:
            return {
                "total_triples": 0,
                "success": {"avg": 0.0, "max": 0.0, "nonzero": 0},
                "traversal": {"avg": 0.0, "max": 0.0, "nonzero": 0},
                "recency": {"avg": 0.0, "max": 0.0, "nonzero": 0},
            }

        return {
            "total_triples": row["total_triples"],
            "success": {
                "avg": round(float(row["avg_success"] or 0), 6),
                "max": round(float(row["max_success"] or 0), 6),
                "nonzero": int(row["nonzero_success"] or 0),
            },
            "traversal": {
                "avg": round(float(row["avg_traversal"] or 0), 6),
                "max": round(float(row["max_traversal"] or 0), 6),
                "nonzero": int(row["nonzero_traversal"] or 0),
            },
            "recency": {
                "avg": round(float(row["avg_recency"] or 0), 6),
                "max": round(float(row["max_recency"] or 0), 6),
                "nonzero": int(row["nonzero_recency"] or 0),
            },
        }

    # ── Provenance ────────────────────────────────────────────────────

    def ensure_provenance_schema(self) -> None:
        conn = self._conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS triple_provenance (
                triple_id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL DEFAULT '',
                cycle_id TEXT NOT NULL DEFAULT '',
                evidence_chain TEXT NOT NULL DEFAULT '[]',
                confidence_history TEXT NOT NULL DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                valid_at TEXT DEFAULT NULL,
                invalid_at TEXT DEFAULT NULL,
                expired_at TEXT DEFAULT NULL,
                statement_type TEXT DEFAULT 'fact',
                temporal_type TEXT DEFAULT 'static'
            )
        """)

        # Schema migration: add columns if upgrading from older schema
        existing_cols = {
            row[1] for row in conn.execute(
                "PRAGMA table_info(triple_provenance)"
            ).fetchall()
        }
        for col, col_def in [
            ("valid_at", "TEXT DEFAULT NULL"),
            ("invalid_at", "TEXT DEFAULT NULL"),
            ("expired_at", "TEXT DEFAULT NULL"),
            ("statement_type", "TEXT DEFAULT 'fact'"),
            ("temporal_type", "TEXT DEFAULT 'static'"),
        ]:
            if col not in existing_cols:
                try:
                    conn.execute(
                        f"ALTER TABLE triple_provenance ADD COLUMN {col} {col_def}"
                    )
                except sqlite3.OperationalError:
                    pass

        conn.commit()
        conn.close()

    def store_provenance(
        self,
        triple_id: str,
        agent_id: str = "",
        cycle_id: str = "",
        evidence_chain: Optional[List[str]] = None,
        confidence: float = 1.0,
        reason: str = "",
        valid_at: Optional[str] = None,
        invalid_at: Optional[str] = None,
        statement_type: Optional[str] = None,
        temporal_type: Optional[str] = None,
    ) -> None:
        now = datetime.now().isoformat()
        chain = evidence_chain or []
        conn = self._conn()

        existing = conn.execute(
            "SELECT * FROM triple_provenance WHERE triple_id = ?",
            (triple_id,),
        ).fetchone()

        if existing:
            # Merge: append to confidence_history and evidence_chain
            old_history = json.loads(existing["confidence_history"] or "[]")
            old_chain = json.loads(existing["evidence_chain"] or "[]")

            old_history.append({
                "confidence": confidence,
                "reason": reason,
                "timestamp": now,
                "agent_id": agent_id,
            })
            merged_chain = list(set(old_chain + chain))

            update_fields = {
                "confidence_history": json.dumps(old_history),
                "evidence_chain": json.dumps(merged_chain),
                "updated_at": now,
            }
            if agent_id:
                update_fields["agent_id"] = agent_id
            if cycle_id:
                update_fields["cycle_id"] = cycle_id
            if valid_at is not None:
                update_fields["valid_at"] = valid_at
            if invalid_at is not None:
                update_fields["invalid_at"] = invalid_at
            if statement_type is not None:
                update_fields["statement_type"] = statement_type
            if temporal_type is not None:
                update_fields["temporal_type"] = temporal_type

            set_clause = ", ".join(f"{k} = ?" for k in update_fields)
            vals = list(update_fields.values()) + [triple_id]
            conn.execute(
                f"UPDATE triple_provenance SET {set_clause} WHERE triple_id = ?",
                vals,
            )
        else:
            # Insert new provenance
            history = [{
                "confidence": confidence,
                "reason": reason,
                "timestamp": now,
                "agent_id": agent_id,
            }]
            conn.execute(
                """INSERT INTO triple_provenance
                   (triple_id, agent_id, cycle_id, evidence_chain,
                    confidence_history, created_at, updated_at,
                    valid_at, invalid_at, statement_type, temporal_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    triple_id, agent_id, cycle_id,
                    json.dumps(chain), json.dumps(history),
                    now, now,
                    valid_at, invalid_at,
                    statement_type or "fact",
                    temporal_type or "static",
                ),
            )

        conn.commit()
        conn.close()

    def get_provenance(self, triple_id: str) -> Optional[Dict[str, Any]]:
        conn = self._conn()
        row = conn.execute(
            "SELECT * FROM triple_provenance WHERE triple_id = ?",
            (triple_id,),
        ).fetchone()
        conn.close()

        if row is None:
            return None

        return {
            "triple_id": row["triple_id"],
            "agent_id": row["agent_id"],
            "cycle_id": row["cycle_id"],
            "evidence_chain": json.loads(row["evidence_chain"]),
            "confidence_history": json.loads(row["confidence_history"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "valid_at": row["valid_at"],
            "invalid_at": row["invalid_at"],
            "expired_at": row["expired_at"],
            "statement_type": row["statement_type"],
            "temporal_type": row["temporal_type"],
        }

    def query_temporal_triples(
        self,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        include_invalidated: bool = False,
    ) -> List[Dict[str, Any]]:
        conditions: List[str] = []
        params: List[str] = []

        if valid_from:
            conditions.append("p.valid_at >= ?")
            params.append(valid_from)
        if valid_to:
            conditions.append("p.valid_at <= ?")
            params.append(valid_to)
        if not include_invalidated:
            conditions.append("p.invalid_at IS NULL")

        where = ""
        if conditions:
            where = "WHERE " + " AND ".join(conditions)

        conn = self._conn()
        rows = conn.execute(
            f"""SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                       t.valid_from, t.valid_to,
                       p.valid_at, p.invalid_at, p.agent_id, p.cycle_id,
                       p.confidence_history, p.evidence_chain,
                       p.statement_type, p.temporal_type
                FROM triples t
                LEFT JOIN triple_provenance p ON t.id = p.triple_id
                {where}
                ORDER BY p.valid_at ASC NULLS LAST""",
            params,
        ).fetchall()
        conn.close()

        results = []
        for row in rows:
            results.append({
                "triple_id": row["id"],
                "subject": row["subject"],
                "predicate": row["predicate"],
                "object": row["object"],
                "confidence": row["confidence"],
                "valid_from": row["valid_from"],
                "valid_to": row["valid_to"],
                "valid_at": row["valid_at"],
                "invalid_at": row["invalid_at"],
                "agent_id": row["agent_id"] if row["agent_id"] else "",
                "cycle_id": row["cycle_id"] if row["cycle_id"] else "",
                "confidence_history": (
                    json.loads(row["confidence_history"])
                    if row["confidence_history"] else []
                ),
                "evidence_chain": (
                    json.loads(row["evidence_chain"])
                    if row["evidence_chain"] else []
                ),
                "statement_type": (
                    row["statement_type"] if row["statement_type"] else "fact"
                ),
                "temporal_type": (
                    row["temporal_type"] if row["temporal_type"] else "static"
                ),
            })
        return results

    # ── Escape hatch ──────────────────────────────────────────────────

    def execute_raw(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> List[Dict[str, Any]]:
        conn = self._conn()
        cursor = conn.execute(sql, params or [])

        # For SELECT statements, return rows as dicts
        if cursor.description:
            cols = [desc[0] for desc in cursor.description]
            rows = cursor.fetchall()
            conn.close()
            return [dict(zip(cols, row)) for row in rows]

        # For INSERT/UPDATE/DELETE, commit and return affected count
        conn.commit()
        affected = cursor.rowcount
        conn.close()
        return [{"rows_affected": affected}]

    # ── Internal helpers ──────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> Dict[str, Any]:
        """Convert a sqlite3.Row to a plain dict."""
        return {
            "id": row["id"],
            "subject": row["subject"],
            "predicate": row["predicate"],
            "object": row["object"],
            "confidence": row["confidence"],
            "valid_from": row["valid_from"],
            "valid_to": row["valid_to"],
            "source_closet": row["source_closet"] if "source_closet" in row.keys() else None,
            "source_file": row["source_file"] if "source_file" in row.keys() else None,
        }

    def __repr__(self) -> str:
        return f"<SQLiteKGBackend db_path={self.db_path!r}>"


__all__ = ["SQLiteKGBackend"]
