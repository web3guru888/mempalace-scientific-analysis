"""
KG Pheromone System — Stigmergic learning for the knowledge graph.

Ported from STAN_X v8's stigmergy module, adapted for our SQLite-backed
KG (not Memgraph).  Pheromones are stored as columns on the ``triples``
table so they travel with the triple and are queryable via SQL.

Three pheromone channels per triple:
    success_pheromone   — deposited when triple participates in a confirmed
                          hypothesis path.  Slow decay (ρ=0.03).
    traversal_pheromone — deposited each time the triple is traversed during
                          pathfinding.  Moderate decay (ρ=0.08).
    recency_pheromone   — deposited on recent usage.  Fast decay (ρ=0.15).

Pheromone modifier (used by pathfinder to adjust edge costs):
    modifier = 1.0 - (0.5·min(success,1) + 0.3·min(recency,1) + 0.2·min(traversal,1)) × 0.5
    This reduces cost for high-pheromone triples (makes them "cheaper").

Decay formula:  τ(t+1) = τ(t) × (1 − ρ)

Backend abstraction (2026-04-11)
---------------------------------
Now accepts either a ``KGBackend`` instance or a ``db_path`` string.
When ``db_path`` is given, creates an ``SQLiteKGBackend`` for backward
compatibility.  All raw ``sqlite3`` operations have been replaced by
``KGBackend`` method calls.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger("mempalace_agi")

# Default decay rates from STAN_X v8 (SPEC.md FR-014)
DEFAULT_DECAY_RATES: Dict[str, float] = {
    "success": 0.03,
    "traversal": 0.08,
    "recency": 0.15,
}


class PheromoneManager:
    """Manage pheromone levels on KG triples.

    Handles schema migration (safe column addition), deposit, decay,
    and modifier computation.

    Can be initialized with either:
    - ``backend``: A :class:`KGBackend` instance (preferred).
    - ``db_path``: A filesystem path (creates ``SQLiteKGBackend`` internally).

    Args:
        db_path: Path to the KG SQLite database (backward compat).
        backend: Pre-created :class:`KGBackend` instance.
    """

    def __init__(
        self,
        db_path: str = "",
        *,
        backend: Optional[Any] = None,
    ):
        if backend is not None:
            self._backend = backend
        elif db_path:
            from .backends import SQLiteKGBackend
            self._backend = SQLiteKGBackend(db_path=db_path)
        else:
            raise ValueError("Either db_path or backend must be provided")

        # Expose db_path for backward compatibility (tests, orchestrator)
        self.db_path = getattr(self._backend, "db_path", db_path)

        logger.info("PheromoneManager initialized (backend=%r)", self._backend)

    # ── Deposit operations ──────────────────────────────────────────

    def deposit_success(self, triple_id: str, amount: float = 1.0) -> None:
        """Add success pheromone to a triple.

        Args:
            triple_id: The triple ID (string or int, coerced to str for SQL).
            amount: Amount to add (default 1.0).
        """
        self._backend.update_pheromone(triple_id, "success_pheromone", amount, mode="add")

    def deposit_traversal(self, triple_id: str, amount: float = 0.1) -> None:
        """Add traversal pheromone to a triple.

        Args:
            triple_id: The triple ID.
            amount: Amount to add (default 0.1).
        """
        self._backend.update_pheromone(triple_id, "traversal_pheromone", amount, mode="add")

    def deposit_recency(self, triple_id: str, amount: float = 1.0) -> None:
        """Set recency pheromone on a triple (additive).

        Args:
            triple_id: The triple ID.
            amount: Amount to add (default 1.0).
        """
        self._backend.update_pheromone(triple_id, "recency_pheromone", amount, mode="add")

    def deposit_on_path(
        self,
        path_triple_ids: List[str],
        base_reward: float = 1.0,
    ) -> None:
        """Position-weighted success deposit along a path.

        Earlier edges get more reward:  reward(i) = base × (1 − i/len)

        Args:
            path_triple_ids: Ordered list of triple IDs along the path.
            base_reward: Reward for the first edge (default 1.0).
        """
        if not path_triple_ids:
            return
        n = len(path_triple_ids)
        for i, tid in enumerate(path_triple_ids):
            weight = 1.0 - (i / n)
            reward = base_reward * weight
            self._backend.update_pheromone(tid, "success_pheromone", reward, mode="add")
        logger.debug(
            "Deposited position-weighted success on %d triples (base=%.2f)",
            n,
            base_reward,
        )

    # ── Decay ───────────────────────────────────────────────────────

    def decay_all(self, rates: Optional[Dict[str, float]] = None) -> int:
        """Apply exponential decay to all pheromones.

        Formula:  τ(t+1) = τ(t) × (1 − ρ)

        Args:
            rates: Dict with keys ``success``, ``traversal``, ``recency``
                   mapping to decay rates.  Defaults to STAN_X rates.

        Returns:
            Number of triples updated.
        """
        r = {**DEFAULT_DECAY_RATES, **(rates or {})}
        # Map short names to column names
        column_rates = {
            "success_pheromone": r["success"],
            "traversal_pheromone": r["traversal"],
            "recency_pheromone": r["recency"],
        }
        updated = self._backend.decay_pheromones(column_rates)
        logger.info(
            "Decayed pheromones on %d triples (rates: s=%.3f, t=%.3f, r=%.3f)",
            updated,
            r["success"],
            r["traversal"],
            r["recency"],
        )
        return updated

    # ── Modifier (used by pathfinder) ───────────────────────────────

    def get_pheromone_modifier(self, triple_id: str) -> float:
        """Compute the cost modifier from a triple's pheromone levels.

        Formula (from STAN_X v8 recompute_edge_cost):
            factor = 0.5·min(success,1) + 0.3·min(recency,1) + 0.2·min(traversal,1)
            modifier = 1.0 − factor × 0.5

        Higher pheromones → lower modifier → cheaper edge.

        Returns:
            Float in (0.5, 1.0].  Defaults to 1.0 (no effect) if triple
            not found or all pheromones are zero.
        """
        levels = self._backend.get_pheromone_levels(triple_id)
        if levels is None:
            return 1.0

        sp = min(levels.get("success", 0.0), 1.0)
        tp = min(levels.get("traversal", 0.0), 1.0)
        rp = min(levels.get("recency", 0.0), 1.0)

        factor = 0.5 * sp + 0.3 * rp + 0.2 * tp
        modifier = 1.0 - factor * 0.5
        return modifier

    def get_pheromone_levels(self, triple_id: str) -> Optional[Dict[str, float]]:
        """Return raw pheromone levels for a triple.

        Returns:
            Dict with ``success``, ``traversal``, ``recency`` keys,
            or None if triple not found.
        """
        return self._backend.get_pheromone_levels(triple_id)

    # ── Statistics ──────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return pheromone statistics across all triples.

        Returns:
            Dict with avg, max, and count of non-zero triples per channel.
        """
        return self._backend.get_pheromone_stats()


__all__ = ["PheromoneManager", "DEFAULT_DECAY_RATES"]
