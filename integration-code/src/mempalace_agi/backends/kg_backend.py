"""
kg_backend.py — Abstract knowledge-graph backend for MemPalace-AGI
===================================================================

Defines the :class:`KGBackend` ABC whose methods cover the raw ``sqlite3``
operations that ``knowledge_graph_bridge.py``, ``kg_pathfinder.py``, and
``kg_pheromones.py`` perform against the KG's ``triples`` and ``entities``
tables.

Why a separate abstraction from MemPalaceKG?
---------------------------------------------
``knowledge_graph.py``'s ``KnowledgeGraph`` class is MemPalace upstream code
that we don't control.  Our integration code makes *additional* raw sqlite3
queries (provenance, pheromones, pathfinding neighbor lookups, temporal
bi-temporal queries, confidence history) that go around ``KnowledgeGraph``.

This backend abstracts those raw accesses so that:

1. If MemPalace upstream changes its storage (PR #574 LanceDB, etc.),
   our additional queries have a single implementation point to update.
2. ``kg_pheromones.py`` (full rewrite needed for LanceDB) and
   ``kg_pathfinder.py`` can use this instead of raw ``sqlite3.connect()``.

API surface extracted from actual code
---------------------------------------

Module                    | Raw sqlite3 operations
--------------------------|-----------------------------------------------
knowledge_graph_bridge.py | CREATE TABLE triple_provenance, INSERT/UPDATE
                          | provenance, SELECT triples JOIN provenance,
                          | SELECT triples WHERE subject/object = ?
kg_pathfinder.py          | SELECT subject,object FROM triples WHERE …
                          | SELECT id,predicate,confidence FROM triples
                          | SELECT subject/object FROM triples LIMIT 1
kg_pheromones.py          | ALTER TABLE ADD COLUMN, UPDATE triples SET
                          | pheromone = …, SELECT pheromone columns,
                          | aggregate stats (AVG/MAX/SUM/COUNT)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Sequence, Tuple


class KGBackend(ABC):
    """Abstract interface for knowledge-graph triple storage.

    Covers the *raw* SQL operations our integration performs beyond what
    ``KnowledgeGraph`` (upstream) already provides.  Each method maps to
    a concrete pattern found in ``kg_pathfinder.py``, ``kg_pheromones.py``,
    or ``knowledge_graph_bridge.py``.

    Lifecycle::

        backend = SQLiteKGBackend(db_path="/tmp/kg.db")
        backend.add_triple("temperature", "causes", "ice_melt", confidence=0.9)
        triples = backend.query_triples(subject="temperature")
        backend.close()
    """

    # ── Lifecycle ─────────────────────────────────────────────────────

    @abstractmethod
    def __init__(self, db_path: str, **kwargs: Any) -> None:
        """Initialize the KG backend.

        Args:
            db_path: Filesystem path for the database.
            **kwargs: Backend-specific options.
        """
        ...

    def close(self) -> None:
        """Release resources.  Default no-op."""
        pass

    # ── Triple CRUD ───────────────────────────────────────────────────

    @abstractmethod
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
        """Add a triple to the knowledge graph.

        If an identical active triple (subject, predicate, object with
        ``valid_to IS NULL``) already exists, return its existing ID
        (idempotent, matching ``KnowledgeGraph.add_triple`` semantics).

        Args:
            subject: Subject entity name.
            predicate: Relationship type.
            object: Object entity name.
            confidence: Float [0, 1] — how confident we are in this fact.
            source: Free-text source attribution.
            timestamp: ISO timestamp for when this triple was created.
            valid_from: ISO timestamp — when this fact became true.
            valid_to: ISO timestamp — when this fact ceased being true
                (``None`` = still current).
            source_closet: MemPalace closet reference.
            source_file: MemPalace file reference.

        Returns:
            Triple ID (string).
        """
        ...

    @abstractmethod
    def query_triples(
        self,
        subject: Optional[str] = None,
        predicate: Optional[str] = None,
        object: Optional[str] = None,
        include_expired: bool = False,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Query triples with optional filters.

        Args:
            subject: Filter by subject entity.
            predicate: Filter by predicate/relationship type.
            object: Filter by object entity.
            include_expired: If ``True``, include triples where
                ``valid_to IS NOT NULL``.  Default: active only.
            limit: Maximum results.

        Returns:
            List of dicts, each with at minimum:
            ``{"id", "subject", "predicate", "object", "confidence",
            "valid_from", "valid_to"}``.
        """
        ...

    @abstractmethod
    def get_entity_relations(
        self,
        entity: str,
        direction: str = "both",
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get all triples involving an entity.

        Used by ``kg_pathfinder.py``'s ``GraphAdapter.get_neighbors()`` and
        ``knowledge_graph_bridge.py``'s ``get_confidence_history()``.

        Args:
            entity: Entity name (will be normalised internally).
            direction: ``"outgoing"`` (entity as subject),
                ``"incoming"`` (entity as object), or ``"both"``.
            limit: Maximum results.

        Returns:
            List of dicts with triple fields.
        """
        ...

    @abstractmethod
    def get_edge_info(
        self,
        source: str,
        target: str,
    ) -> Optional[Dict[str, Any]]:
        """Get the best (highest-confidence) edge between two entities.

        Used by ``kg_pathfinder.py``'s ``GraphAdapter.get_edge_info()``.
        Looks in both directions (bidirectional).

        Args:
            source: Source entity name.
            target: Target entity name.

        Returns:
            Dict with ``{"id", "predicate", "confidence"}`` or ``None``.
        """
        ...

    @abstractmethod
    def resolve_entity(self, name: str) -> Optional[str]:
        """Check if an entity exists in the KG and return its normalised ID.

        Used by ``kg_pathfinder.py``'s ``GraphAdapter.resolve_entity()``.

        Args:
            name: Entity name (free-text, will be normalised).

        Returns:
            Normalised entity ID string, or ``None`` if not found.
        """
        ...

    # ── Counts & stats ────────────────────────────────────────────────

    @abstractmethod
    def count_triples(self) -> int:
        """Return total number of triples (active + expired)."""
        ...

    @abstractmethod
    def count_entities(self) -> int:
        """Return total number of distinct entities."""
        ...

    @abstractmethod
    def get_all_entities(self, limit: int = 1000) -> List[str]:
        """Return all entity names (IDs).

        Args:
            limit: Maximum number of entities to return.

        Returns:
            List of entity ID strings.
        """
        ...

    # ── Pheromone operations ──────────────────────────────────────────
    #
    # These map to kg_pheromones.py's raw UPDATE/SELECT on the triples
    # table's pheromone columns.

    @abstractmethod
    def update_pheromone(
        self,
        triple_id: str,
        column: str,
        amount: float,
        mode: str = "add",
    ) -> None:
        """Update a pheromone value on a triple.

        Args:
            triple_id: The triple to update.
            column: Pheromone channel name (e.g. ``"success_pheromone"``).
            amount: Value to add or set.
            mode: ``"add"`` (increment) or ``"set"`` (replace).
        """
        ...

    @abstractmethod
    def decay_pheromones(
        self,
        rates: Dict[str, float],
    ) -> int:
        """Apply exponential decay to all pheromone columns.

        Formula: ``value = value × (1 − rate)``

        Args:
            rates: Dict mapping column name to decay rate.
                Example: ``{"success_pheromone": 0.1, ...}``

        Returns:
            Number of triples updated.
        """
        ...

    @abstractmethod
    def get_pheromone_levels(self, triple_id: str) -> Optional[Dict[str, float]]:
        """Return raw pheromone levels for a triple.

        Args:
            triple_id: The triple ID.

        Returns:
            Dict with ``{"success": float, "traversal": float, "recency": float}``
            or ``None`` if triple not found.
        """
        ...

    @abstractmethod
    def get_pheromone_stats(self) -> Dict[str, Any]:
        """Return aggregate pheromone statistics.

        Returns:
            Dict with ``total_triples`` and per-channel ``avg``, ``max``,
            ``nonzero`` counts.
        """
        ...

    # ── Provenance (knowledge_graph_bridge.py) ────────────────────────
    #
    # The provenance table lives alongside the triples table.  These
    # methods abstract the raw INSERT/UPDATE/SELECT on triple_provenance.

    @abstractmethod
    def ensure_provenance_schema(self) -> None:
        """Create the provenance table and any needed columns.

        Idempotent — safe to call multiple times.
        """
        ...

    @abstractmethod
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
        """Store or update provenance metadata for a triple.

        If provenance already exists, appends to ``confidence_history``
        and merges ``evidence_chain``.
        """
        ...

    @abstractmethod
    def get_provenance(self, triple_id: str) -> Optional[Dict[str, Any]]:
        """Return the full provenance record for a triple.

        Returns:
            Dict with provenance fields, or ``None``.
        """
        ...

    @abstractmethod
    def query_temporal_triples(
        self,
        valid_from: Optional[str] = None,
        valid_to: Optional[str] = None,
        include_invalidated: bool = False,
    ) -> List[Dict[str, Any]]:
        """Query triples joined with provenance, filtered by temporal window.

        Used by ``knowledge_graph_bridge.py``'s ``get_temporal_triples()``.

        Args:
            valid_from: Only triples with ``valid_at >= this``.
            valid_to: Only triples with ``valid_at <= this``.
            include_invalidated: Include triples with ``invalid_at IS NOT NULL``.

        Returns:
            List of dicts with triple + provenance fields.
        """
        ...

    # ── Escape hatch ──────────────────────────────────────────────────

    @abstractmethod
    def execute_raw(
        self,
        sql: str,
        params: Optional[Sequence[Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a raw SQL query (or backend-native query) and return rows.

        **Escape hatch** for complex queries not covered by the abstract
        interface (e.g. multi-table JOINs, aggregations).

        For SQL backends, this runs the query directly.  For non-SQL
        backends, this may raise ``NotImplementedError`` or translate
        the query as best as possible.

        Args:
            sql: SQL query string (or backend-native query).
            params: Query parameters (positional ``?`` placeholders for SQL).

        Returns:
            List of dicts (one per row).
        """
        ...

    # ── Utility ───────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return f"<{type(self).__name__}>"


__all__ = ["KGBackend"]
