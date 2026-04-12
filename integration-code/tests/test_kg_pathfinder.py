"""Tests for kg_pathfinder.py — Semantic A* pathfinding over SQLite KG."""

import os
import sqlite3

import numpy as np
import pytest


# ── Helpers ─────────────────────────────────────────────────────────

def _make_kg_db(tmp_path, triples=None):
    """Create a minimal KG SQLite database for testing.

    Args:
        triples: List of (id, subject, predicate, object, confidence) tuples.
                 If None, creates a default linear graph:
                 A → B → C → D
    """
    db_path = os.path.join(str(tmp_path), "test_kg.sqlite3")
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS triples (
            id TEXT PRIMARY KEY,
            subject TEXT,
            predicate TEXT,
            object TEXT,
            confidence REAL DEFAULT 0.5,
            valid_from TEXT,
            valid_to TEXT,
            source_closet TEXT,
            source_file TEXT,
            success_pheromone REAL DEFAULT 0.0,
            traversal_pheromone REAL DEFAULT 0.0,
            recency_pheromone REAL DEFAULT 0.0
        )
    """)

    if triples is None:
        triples = [
            ("t1", "a", "causes", "b", 0.8),
            ("t2", "b", "causes", "c", 0.7),
            ("t3", "c", "causes", "d", 0.9),
        ]

    for t in triples:
        conn.execute(
            "INSERT INTO triples (id, subject, predicate, object, confidence) VALUES (?, ?, ?, ?, ?)",
            t,
        )
    conn.commit()
    conn.close()
    return db_path


def _const_embedding(dim=8):
    """Return a factory that produces unique but deterministic embeddings."""
    _cache = {}

    def factory(entity: str):
        if entity not in _cache:
            # Generate deterministic embedding from entity name
            rng = np.random.RandomState(hash(entity) % (2**31))
            _cache[entity] = rng.randn(dim).astype(np.float32)
        return _cache[entity]

    return factory


# ── GraphAdapter tests ──────────────────────────────────────────────

class TestGraphAdapter:
    def test_get_neighbors_bidirectional(self, tmp_path):
        """Neighbors include both outgoing and incoming connections."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        # 'b' is both object of (a,causes,b) and subject of (b,causes,c)
        neighbors = adapter.get_neighbors("b")
        assert set(neighbors) == {"a", "c"}

    def test_get_neighbors_empty(self, tmp_path):
        """Entity not in KG returns empty list."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        neighbors = adapter.get_neighbors("nonexistent")
        assert neighbors == []

    def test_get_edge_cost_with_confidence(self, tmp_path):
        """Higher confidence should reduce edge cost."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        cost = adapter.get_edge_cost("a", "b")
        # 'causes' base_cost = 0.3, confidence 0.8
        # cost = 0.3 * (1 - 0.8 * 0.3) = 0.3 * 0.76 = 0.228
        assert cost == pytest.approx(0.228, abs=0.01)

    def test_get_edge_cost_no_edge(self, tmp_path):
        """No edge → default cost 1.0."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        cost = adapter.get_edge_cost("a", "d")  # No direct edge
        assert cost == 1.0

    def test_get_edge_cost_with_pheromones(self, tmp_path):
        """Pheromone modifier should reduce edge cost."""
        from mempalace_agi.kg_pathfinder import GraphAdapter
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 1.0)
        pm.deposit_recency("t1", 1.0)
        pm.deposit_traversal("t1", 1.0)

        adapter = GraphAdapter(db_path, pheromone_manager=pm)
        cost_with = adapter.get_edge_cost("a", "b")

        adapter_no_pheromone = GraphAdapter(db_path)
        cost_without = adapter_no_pheromone.get_edge_cost("a", "b")

        assert cost_with < cost_without

    def test_get_node_embedding(self, tmp_path):
        """Embedding function should be called and cached."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        call_count = [0]

        def emb_fn(entity):
            call_count[0] += 1
            return np.ones(4, dtype=np.float32) * hash(entity) % 10

        adapter = GraphAdapter(db_path, embedding_fn=emb_fn)

        e1 = adapter.get_node_embedding("a")
        e2 = adapter.get_node_embedding("a")  # Should use cache
        assert call_count[0] == 1  # Only called once
        assert np.array_equal(e1, e2)

    def test_get_node_embedding_none(self, tmp_path):
        """No embedding function → returns None."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        assert adapter.get_node_embedding("a") is None

    def test_resolve_entity(self, tmp_path):
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        assert adapter.resolve_entity("a") == "a"
        assert adapter.resolve_entity("A") == "a"  # Case normalization
        assert adapter.resolve_entity("zzz_unknown") is None


# ── A* Pathfinding tests ────────────────────────────────────────────

class TestSemanticAStarPathfinder:
    def test_simple_path(self, tmp_path):
        """A* finds the path A→B→C→D in a linear graph."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("a", "d")
        assert result.complete is True
        assert result.path == ["a", "b", "c", "d"]
        assert result.total_cost > 0
        assert result.nodes_explored >= 4

    def test_start_equals_goal(self, tmp_path):
        """Start == Goal → trivial single-node path."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("a", "a")
        assert result.complete is True
        assert result.path == ["a"]
        assert result.total_cost == 0.0
        assert result.iterations == 0

    def test_disconnected_graph(self, tmp_path):
        """A* handles disconnected subgraphs (returns incomplete)."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        triples = [
            ("t1", "a", "causes", "b", 0.8),
            ("t2", "c", "causes", "d", 0.7),  # Disconnected from a-b
        ]
        db_path = _make_kg_db(tmp_path, triples=triples)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("a", "d")
        assert result.complete is False
        assert result.path == []

    def test_max_iterations_limit(self, tmp_path):
        """A* respects max_iterations."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("a", "d", max_iterations=1)
        # With only 1 iteration, should not complete
        assert result.iterations <= 1

    def test_empty_graph(self, tmp_path):
        """A* on empty graph returns incomplete."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        db_path = _make_kg_db(tmp_path, triples=[])
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("x", "y")
        assert result.complete is False

    def test_edges_collected(self, tmp_path):
        """Edges along the path should be populated."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("a", "d")
        assert result.complete is True
        assert len(result.edges) == 3  # a→b, b→c, c→d
        assert result.edges[0]["source"] == "a"
        assert result.edges[0]["target"] == "b"
        assert "predicate" in result.edges[0]

    def test_bidirectional_path(self, tmp_path):
        """A* can traverse edges in reverse direction."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, SemanticAStarPathfinder

        # Only edge: a causes b. Can we go b→a?
        triples = [("t1", "a", "causes", "b", 0.8)]
        db_path = _make_kg_db(tmp_path, triples=triples)
        adapter = GraphAdapter(db_path)
        pathfinder = SemanticAStarPathfinder(graph=adapter)

        result = pathfinder.find_path("b", "a")
        assert result.complete is True
        assert result.path == ["b", "a"]


# ── Heuristic tests ─────────────────────────────────────────────────

class TestSemanticHeuristic:
    def test_same_node_heuristic_zero(self, tmp_path):
        from mempalace_agi.kg_pathfinder import GraphAdapter, semantic_heuristic

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)

        h = semantic_heuristic("a", "a", adapter)
        assert h == 0.0

    def test_no_embeddings_fallback(self, tmp_path):
        """Missing embeddings → h = 1.0."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, semantic_heuristic

        db_path = _make_kg_db(tmp_path)
        adapter = GraphAdapter(db_path)  # No embedding_fn

        h = semantic_heuristic("a", "b", adapter)
        assert h == 1.0

    def test_same_domain_weighting(self, tmp_path):
        """High similarity → 90% semantic weight."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, semantic_heuristic

        db_path = _make_kg_db(tmp_path)

        # Create similar embeddings (similarity > 0.3)
        emb_a = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        emb_b = np.array([0.9, 0.1, 0.0, 0.0], dtype=np.float32)

        def emb_fn(entity):
            return emb_a if entity == "a" else emb_b

        adapter = GraphAdapter(db_path, embedding_fn=emb_fn)
        h = semantic_heuristic("a", "b", adapter)

        # similarity is high (> 0.3), so same-domain weighting applies
        # h should be relatively small since embeddings are similar
        assert 0.0 < h < 0.5

    def test_cross_domain_weighting(self, tmp_path):
        """Low similarity → 50/50 semantic/graph weight."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, semantic_heuristic

        db_path = _make_kg_db(tmp_path)

        # Create dissimilar embeddings (similarity < 0.3)
        emb_a = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)
        emb_b = np.array([0.0, 1.0, 0.0, 0.0], dtype=np.float32)  # Orthogonal

        def emb_fn(entity):
            return emb_a if entity == "a" else emb_b

        adapter = GraphAdapter(db_path, embedding_fn=emb_fn)
        h = semantic_heuristic("a", "b", adapter)

        # Orthogonal vectors → similarity=0, cross-domain
        # h should be close to 1.0
        assert h > 0.5

    def test_heuristic_bounded(self, tmp_path):
        """Heuristic value should always be in [0, 1]."""
        from mempalace_agi.kg_pathfinder import GraphAdapter, semantic_heuristic

        db_path = _make_kg_db(tmp_path)
        emb_fn = _const_embedding(dim=8)
        adapter = GraphAdapter(db_path, embedding_fn=emb_fn)

        for start in ["a", "b", "c", "d"]:
            for goal in ["a", "b", "c", "d"]:
                h = semantic_heuristic(start, goal, adapter)
                assert 0.0 <= h <= 1.0, f"h({start},{goal}) = {h}"


# ── Convenience function tests ──────────────────────────────────────

class TestFindKnowledgePath:
    def test_find_knowledge_path_success(self, tmp_path):
        from mempalace_agi.kg_pathfinder import find_knowledge_path

        db_path = _make_kg_db(tmp_path)
        result = find_knowledge_path(db_path, "a", "d")
        assert result is not None
        assert result.complete is True

    def test_find_knowledge_path_nonexistent_entity(self, tmp_path):
        from mempalace_agi.kg_pathfinder import find_knowledge_path

        db_path = _make_kg_db(tmp_path)
        result = find_knowledge_path(db_path, "zzz", "d")
        assert result is None

    def test_path_with_pheromone_discount(self, tmp_path):
        """Pheromone-modified path should have lower cost."""
        from mempalace_agi.kg_pathfinder import find_knowledge_path
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = _make_kg_db(tmp_path)

        # Path without pheromones
        result_base = find_knowledge_path(db_path, "a", "d")
        assert result_base is not None and result_base.complete

        # Add pheromones to the path
        pm = PheromoneManager(db_path)
        pm.deposit_success("t1", 1.0)
        pm.deposit_success("t2", 1.0)
        pm.deposit_success("t3", 1.0)
        pm.deposit_recency("t1", 1.0)
        pm.deposit_recency("t2", 1.0)
        pm.deposit_recency("t3", 1.0)

        result_pheromone = find_knowledge_path(
            db_path, "a", "d", pheromone_manager=pm
        )
        assert result_pheromone is not None and result_pheromone.complete

        assert result_pheromone.total_cost < result_base.total_cost
