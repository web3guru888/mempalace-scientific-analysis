"""
KG Pathfinder — Semantic A* pathfinding over the knowledge graph.

Ported from STAN_X v8's pathfinding module, adapted to work with our
KnowledgeGraphBridge (SQLite triples) and PalaceDiscoveryMemory (ChromaDB
embeddings) instead of Memgraph.

Key adaptations:
- GraphAdapter wraps KGBackend (or accepts a db_path for backward compat)
  to provide the A* interface.
- Entity embeddings come from ChromaDB queries (semantic_search with n_results=1)
  or an optional in-memory cache.
- Edge cost incorporates pheromone modifier from PheromoneManager.
- Triples are treated as bidirectional (both subject→object and object→subject).

Heuristic (from STAN_X's adaptive multi-objective):
    Same-domain:   h = 0.9·h_semantic + 0.1·h_graph
    Cross-domain:  h = 0.5·h_semantic + 0.5·h_graph
    Threshold:     similarity < 0.3 → cross-domain

Backend abstraction (2026-04-11)
---------------------------------
``GraphAdapter`` now accepts a ``KGBackend`` instance or a ``db_path`` string.
All raw ``sqlite3`` calls have been replaced by ``KGBackend`` method calls.
"""

from __future__ import annotations

import heapq
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set

import numpy as np

logger = logging.getLogger("mempalace_agi")


# ── Data models ─────────────────────────────────────────────────────

@dataclass
class PathResult:
    """Result of A* pathfinding.

    Attributes:
        path:           Ordered list of entity names from start to goal.
        total_cost:     Accumulated g-score of the path.
        nodes_explored: Number of unique nodes popped from open set.
        complete:       True if goal was reached.
        iterations:     Number of main-loop iterations executed.
        edges:          List of (subject, predicate, object, triple_id) tuples
                        along the path (one per consecutive pair).
    """
    path: List[str] = field(default_factory=list)
    total_cost: float = 0.0
    nodes_explored: int = 0
    complete: bool = False
    iterations: int = 0
    edges: List[Dict[str, Any]] = field(default_factory=list)


# ── Heuristic constants (from STAN_X HeuristicConfig) ───────────────

CROSS_DOMAIN_THRESHOLD = 0.3

SAME_DOMAIN_SEMANTIC_WEIGHT = 0.9
SAME_DOMAIN_GRAPH_WEIGHT = 0.1

CROSS_DOMAIN_SEMANTIC_WEIGHT = 0.5
CROSS_DOMAIN_GRAPH_WEIGHT = 0.5

GRAPH_DISTANCE_SCALE = 0.5


# ── Cosine similarity (self-contained, no STAN_X import) ────────────

def _cosine_similarity(v1: np.ndarray, v2: np.ndarray) -> float:
    """Cosine similarity ∈ [0, 1]."""
    n1 = np.linalg.norm(v1)
    n2 = np.linalg.norm(v2)
    if n1 == 0.0 or n2 == 0.0:
        return 0.0
    sim = float(np.dot(v1, v2) / (n1 * n2))
    return max(0.0, min(1.0, sim))


# ── Graph adapter ───────────────────────────────────────────────────

class GraphAdapter:
    """Wraps KGBackend to provide the interface A* needs.

    Methods:
        get_neighbors(entity) → list of connected entity names
        get_edge_cost(source, target) → float cost
        get_node_embedding(entity) → Optional[np.ndarray]

    Triples are treated as **bidirectional** — if (A, causes, B) exists,
    both A→B and B→A are valid traversals.

    Can be initialized with either:
    - ``backend``: A :class:`KGBackend` instance (preferred).
    - ``db_path``: A filesystem path (creates ``SQLiteKGBackend`` internally).
    """

    # Base cost per predicate type (lower = stronger relationship)
    _BASE_COSTS: Dict[str, float] = {
        "causes": 0.3,
        "caused_by": 0.3,
        "bidirectionally_causes": 0.25,
        "associated_with": 0.5,
        "correlated_with": 0.6,
        "possibly_causes": 0.7,
        "related_to": 0.8,
        "produced_by": 0.4,
        "belongs_to_domain": 0.5,
        "involves_variable": 0.4,
        "in_phase": 0.6,
        "structurally_similar": 0.5,
        # Wikidata relations (from enricher)
        "instance_of": 0.3,
        "subclass_of": 0.25,
    }
    _DEFAULT_BASE_COST = 0.5

    def __init__(
        self,
        db_path: str = "",
        pheromone_manager: Optional[Any] = None,
        embedding_fn: Optional[Callable[[str], Optional[np.ndarray]]] = None,
        *,
        backend: Optional[Any] = None,
    ):
        """
        Args:
            db_path: Path to the KG SQLite database (backward compat).
            pheromone_manager: Optional PheromoneManager for cost modification.
            embedding_fn: Optional function ``entity_name → embedding vector``.
                          If not provided, embeddings are unavailable and the
                          heuristic falls back to h=1.0.
            backend: Pre-created :class:`KGBackend` instance.
        """
        if backend is not None:
            self._backend = backend
        elif db_path:
            from .backends import SQLiteKGBackend
            self._backend = SQLiteKGBackend(db_path=db_path)
        else:
            raise ValueError("Either db_path or backend must be provided")

        # Expose db_path for backward compatibility
        self.db_path = getattr(self._backend, "db_path", db_path)
        self.pheromone_manager = pheromone_manager
        self._embedding_fn = embedding_fn
        # Cache for embeddings to avoid repeated DB lookups
        self._embedding_cache: Dict[str, Optional[np.ndarray]] = {}

    def get_neighbors(self, entity: str) -> List[str]:
        """Return all entities connected to *entity* via valid triples.

        Bidirectional: looks in both subject and object columns.
        Only returns triples that are currently valid (valid_to IS NULL or empty).
        """
        entity_id = entity.lower().replace(" ", "_").replace("'", "")
        relations = self._backend.get_entity_relations(entity_id, direction="both", limit=200)

        neighbors: Set[str] = set()
        for rel in relations:
            s = rel.get("subject", "")
            o = rel.get("object", "")
            if s == entity_id:
                neighbors.add(o)
            else:
                neighbors.add(s)
        return list(neighbors)

    def get_edge_info(self, source: str, target: str) -> Optional[Dict[str, Any]]:
        """Get the best (lowest-cost) edge between source and target.

        Returns dict with ``triple_id``, ``predicate``, ``confidence``, ``base_cost``,
        or None if no edge exists.
        """
        info = self._backend.get_edge_info(source, target)
        if info is None:
            return None

        pred = info.get("predicate", "related_to")
        base_cost = self._BASE_COSTS.get(pred, self._DEFAULT_BASE_COST)
        # High confidence → lower cost (multiply base by (1 − confidence·0.3))
        conf = float(info.get("confidence", 0.5))
        cost = base_cost * (1.0 - conf * 0.3)
        return {
            "triple_id": str(info.get("id", info.get("triple_id", ""))),
            "predicate": pred,
            "confidence": conf,
            "base_cost": cost,
        }

    def get_edge_cost(self, source: str, target: str, **_kwargs) -> float:
        """Compute traversal cost from source to target.

        Base cost comes from predicate type and confidence.
        If a PheromoneManager is configured, cost is multiplied by the
        pheromone modifier (high pheromones → lower cost).
        """
        info = self.get_edge_info(source, target)
        if info is None:
            return 1.0  # No edge → max cost

        cost = info["base_cost"]

        # Apply pheromone modifier
        if self.pheromone_manager is not None:
            modifier = self.pheromone_manager.get_pheromone_modifier(info["triple_id"])
            cost *= modifier

        return cost

    def get_node_embedding(self, entity: str) -> Optional[np.ndarray]:
        """Get embedding for an entity name.

        Uses the optional embedding_fn provided at construction time.
        Results are cached per entity.
        """
        entity_id = entity.lower().replace(" ", "_").replace("'", "")
        if entity_id in self._embedding_cache:
            return self._embedding_cache[entity_id]

        emb = None
        if self._embedding_fn is not None:
            try:
                emb = self._embedding_fn(entity_id)
            except Exception as e:
                logger.debug("Embedding lookup failed for %s: %s", entity_id, e)

        self._embedding_cache[entity_id] = emb
        return emb

    def resolve_entity(self, name: str) -> Optional[str]:
        """Resolve a free-text name to a KG entity ID.

        Tries exact match first, then normalized match.
        Returns the entity name as stored in the KG, or None.
        """
        return self._backend.resolve_entity(name)


# ── Heuristic function ──────────────────────────────────────────────

def semantic_heuristic(
    current: str,
    goal: str,
    graph: GraphAdapter,
) -> float:
    """Adaptive multi-objective heuristic h(n).

    Same-domain (similarity ≥ 0.3):
        h = 0.9·h_semantic + 0.1·h_graph
    Cross-domain (similarity < 0.3):
        h = 0.5·h_semantic + 0.5·h_graph

    Falls back to h=1.0 if embeddings are unavailable.

    Returns value in [0, 1].
    """
    if current == goal:
        return 0.0

    current_emb = graph.get_node_embedding(current)
    goal_emb = graph.get_node_embedding(goal)

    if current_emb is None or goal_emb is None:
        return 1.0

    try:
        # Ensure numpy arrays
        if not isinstance(current_emb, np.ndarray):
            current_emb = np.array(current_emb, dtype=np.float32)
        if not isinstance(goal_emb, np.ndarray):
            goal_emb = np.array(goal_emb, dtype=np.float32)

        similarity = _cosine_similarity(current_emb, goal_emb)
        h_semantic = 1.0 - similarity

        # Estimate graph distance
        try:
            neighbors = graph.get_neighbors(current)
            num_neighbors = len(neighbors)
        except Exception:
            num_neighbors = 5

        connectivity = max(0.1, min(1.0, num_neighbors / 20.0))
        h_graph = min(1.0, (h_semantic / connectivity) * GRAPH_DISTANCE_SCALE)

        # Adaptive weighting
        if similarity < CROSS_DOMAIN_THRESHOLD:
            w_sem = CROSS_DOMAIN_SEMANTIC_WEIGHT
            w_graph = CROSS_DOMAIN_GRAPH_WEIGHT
        else:
            w_sem = SAME_DOMAIN_SEMANTIC_WEIGHT
            w_graph = SAME_DOMAIN_GRAPH_WEIGHT

        h = w_sem * h_semantic + w_graph * h_graph
        return float(max(0.0, min(1.0, h)))

    except Exception as e:
        logger.debug("Heuristic computation failed for %s→%s: %s", current, goal, e)
        return 1.0


# ── Semantic A* Pathfinder ──────────────────────────────────────────

class SemanticAStarPathfinder:
    """A* pathfinder over the KG with semantic heuristic.

    Adapted from STAN_X v8's SemanticAStar.

    Args:
        graph: GraphAdapter wrapping our KG.
        heuristic_fn: Heuristic function (default: semantic_heuristic).
    """

    def __init__(
        self,
        graph: GraphAdapter,
        heuristic_fn: Optional[Callable] = None,
    ):
        self.graph = graph
        self.heuristic_fn = heuristic_fn or semantic_heuristic

    def find_path(
        self,
        start: str,
        goal: str,
        max_iterations: int = 10000,
    ) -> PathResult:
        """Find shortest path from *start* to *goal* using Semantic A*.

        Args:
            start: Starting entity name (will be normalised).
            goal:  Goal entity name (will be normalised).
            max_iterations: Iteration limit (default 10 000).

        Returns:
            PathResult — check ``.complete`` to see if goal was reached.
        """
        # Normalise entity names to KG format
        start_id = start.lower().replace(" ", "_").replace("'", "")
        goal_id = goal.lower().replace(" ", "_").replace("'", "")

        logger.info("A* search: %s → %s", start_id, goal_id)

        # Trivial case
        if start_id == goal_id:
            return PathResult(
                path=[start_id],
                total_cost=0.0,
                nodes_explored=1,
                complete=True,
                iterations=0,
            )

        # A* data structures
        open_set: List[tuple] = []  # (f_score, counter, node_id)
        closed_set: Set[str] = set()
        came_from: Dict[str, str] = {}
        g_score: Dict[str, float] = {start_id: 0.0}

        h_start = self.heuristic_fn(start_id, goal_id, self.graph)
        f_score: Dict[str, float] = {start_id: h_start}

        counter = 0
        heapq.heappush(open_set, (f_score[start_id], counter, start_id))
        counter += 1

        nodes_explored = 0
        iterations = 0

        while open_set and iterations < max_iterations:
            iterations += 1
            _, _, current = heapq.heappop(open_set)

            if current in closed_set:
                continue

            nodes_explored += 1

            # Goal reached
            if current == goal_id:
                path = self._reconstruct_path(came_from, current)
                edges = self._collect_edges(path)
                return PathResult(
                    path=path,
                    total_cost=g_score[current],
                    nodes_explored=nodes_explored,
                    complete=True,
                    iterations=iterations,
                    edges=edges,
                )

            closed_set.add(current)

            # Expand neighbors
            try:
                neighbors = self.graph.get_neighbors(current)
            except Exception as e:
                logger.debug("Failed to get neighbors for %s: %s", current, e)
                neighbors = []

            for neighbor in neighbors:
                if neighbor in closed_set:
                    continue

                try:
                    edge_cost = self.graph.get_edge_cost(current, neighbor)
                except Exception:
                    edge_cost = 1.0

                tentative_g = g_score[current] + edge_cost

                if neighbor not in g_score or tentative_g < g_score[neighbor]:
                    came_from[neighbor] = current
                    g_score[neighbor] = tentative_g
                    h = self.heuristic_fn(neighbor, goal_id, self.graph)
                    f = tentative_g + h
                    f_score[neighbor] = f
                    heapq.heappush(open_set, (f, counter, neighbor))
                    counter += 1

        # No path found
        reason = "max iterations" if iterations >= max_iterations else "exhausted"
        logger.warning("No path %s→%s (%s), explored %d nodes", start_id, goal_id, reason, nodes_explored)
        return PathResult(
            path=[],
            total_cost=0.0,
            nodes_explored=nodes_explored,
            complete=False,
            iterations=iterations,
        )

    def _reconstruct_path(self, came_from: Dict[str, str], current: str) -> List[str]:
        path = [current]
        while current in came_from:
            current = came_from[current]
            path.append(current)
        path.reverse()
        return path

    def _collect_edges(self, path: List[str]) -> List[Dict[str, Any]]:
        """Collect edge info for each consecutive pair in *path*."""
        edges = []
        for i in range(len(path) - 1):
            info = self.graph.get_edge_info(path[i], path[i + 1])
            if info:
                edges.append({
                    "source": path[i],
                    "target": path[i + 1],
                    **info,
                })
            else:
                edges.append({
                    "source": path[i],
                    "target": path[i + 1],
                    "triple_id": "",
                    "predicate": "unknown",
                    "confidence": 0.0,
                    "base_cost": 1.0,
                })
        return edges


# ── Convenience function ────────────────────────────────────────────

def find_knowledge_path(
    db_path: str = "",
    start_entity: str = "",
    goal_entity: str = "",
    max_iterations: int = 10000,
    pheromone_manager: Optional[Any] = None,
    embedding_fn: Optional[Callable] = None,
    *,
    backend: Optional[Any] = None,
) -> Optional[PathResult]:
    """High-level API: find a path between two entities in the KG.

    Args:
        db_path: Path to KG SQLite database (backward compat).
        start_entity: Start entity name or concept.
        goal_entity:  Goal entity name or concept.
        max_iterations: A* iteration limit.
        pheromone_manager: Optional PheromoneManager for cost modification.
        embedding_fn: Optional ``entity → embedding`` function.
        backend: Pre-created :class:`KGBackend` instance (preferred).

    Returns:
        PathResult if a path was found (check .complete),
        or None if either entity doesn't exist in the KG.
    """
    adapter = GraphAdapter(
        db_path=db_path,
        pheromone_manager=pheromone_manager,
        embedding_fn=embedding_fn,
        backend=backend,
    )

    # Resolve entities
    start_resolved = adapter.resolve_entity(start_entity)
    if start_resolved is None:
        logger.warning("Start entity %r not found in KG", start_entity)
        return None

    goal_resolved = adapter.resolve_entity(goal_entity)
    if goal_resolved is None:
        logger.warning("Goal entity %r not found in KG", goal_entity)
        return None

    pathfinder = SemanticAStarPathfinder(graph=adapter)
    return pathfinder.find_path(start_resolved, goal_resolved, max_iterations=max_iterations)


__all__ = [
    "PathResult",
    "GraphAdapter",
    "SemanticAStarPathfinder",
    "semantic_heuristic",
    "find_knowledge_path",
]
