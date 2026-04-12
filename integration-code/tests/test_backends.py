"""
Tests for the pluggable backend abstractions (VectorBackend + KGBackend).

These tests verify:
1. Abstract base classes cannot be instantiated directly
2. Factory functions create correct concrete types
3. Factory functions reject unknown backend types
4. ChromaDBVectorBackend full CRUD lifecycle
5. SQLiteKGBackend full CRUD lifecycle including pheromones and provenance
6. Interface contracts: all abstract methods are exercised

Created: 2026-04-11 as part of LanceDB migration preparation.
"""
import os
import tempfile

import pytest

from mempalace_agi.backends import (
    ChromaDBVectorBackend,
    KGBackend,
    SQLiteKGBackend,
    VectorBackend,
    create_kg_backend,
    create_vector_backend,
)


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture
def tmp_dir():
    """Provide a temporary directory cleaned up after the test."""
    with tempfile.TemporaryDirectory() as td:
        yield td


@pytest.fixture
def vector_backend(tmp_dir):
    """Create a ChromaDB vector backend in a temp directory."""
    vb = create_vector_backend(
        "chromadb",
        path=os.path.join(tmp_dir, "vec"),
        collection_name="test_collection",
    )
    yield vb
    vb.close()


@pytest.fixture
def kg_backend(tmp_dir):
    """Create a SQLite KG backend in a temp directory."""
    kb = create_kg_backend(
        "sqlite",
        db_path=os.path.join(tmp_dir, "test_kg.db"),
    )
    yield kb
    kb.close()


# ──────────────────────────────────────────────────────────────────
# ABC enforcement
# ──────────────────────────────────────────────────────────────────

class TestABCEnforcement:
    """Verify abstract base classes cannot be instantiated."""

    def test_vector_backend_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            VectorBackend()

    def test_kg_backend_is_abstract(self):
        with pytest.raises(TypeError, match="abstract"):
            KGBackend()


# ──────────────────────────────────────────────────────────────────
# Factory functions
# ──────────────────────────────────────────────────────────────────

class TestFactoryFunctions:
    """Verify factory functions create correct types and reject unknowns."""

    def test_create_chromadb_vector_backend(self, tmp_dir):
        vb = create_vector_backend(
            "chromadb",
            path=os.path.join(tmp_dir, "v1"),
            collection_name="test_factory",
        )
        assert isinstance(vb, ChromaDBVectorBackend)
        assert isinstance(vb, VectorBackend)
        vb.close()

    def test_create_chromadb_case_insensitive(self, tmp_dir):
        vb = create_vector_backend(
            "ChromaDB",
            path=os.path.join(tmp_dir, "v2"),
            collection_name="test_case",
        )
        assert isinstance(vb, ChromaDBVectorBackend)
        vb.close()

    def test_create_sqlite_kg_backend(self, tmp_dir):
        kb = create_kg_backend("sqlite", db_path=os.path.join(tmp_dir, "k.db"))
        assert isinstance(kb, SQLiteKGBackend)
        assert isinstance(kb, KGBackend)
        kb.close()

    def test_unknown_vector_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown vector backend"):
            create_vector_backend("redis")

    def test_unknown_kg_backend_raises(self):
        with pytest.raises(ValueError, match="Unknown KG backend"):
            create_kg_backend("postgres")


# ──────────────────────────────────────────────────────────────────
# ChromaDBVectorBackend — full CRUD
# ──────────────────────────────────────────────────────────────────

class TestChromaDBVectorBackend:
    """Test the ChromaDB concrete implementation."""

    def test_add_and_count(self, vector_backend):
        assert vector_backend.count() == 0
        vector_backend.add(
            ids=["d1", "d2"],
            documents=["first document", "second document"],
            metadatas=[{"wing": "astro"}, {"wing": "econ"}],
        )
        assert vector_backend.count() == 2

    def test_query_returns_correct_structure(self, vector_backend):
        vector_backend.add(
            ids=["d1"],
            documents=["climate change effects on coral reefs"],
            metadatas=[{"wing": "climate"}],
        )
        results = vector_backend.query(query_texts=["coral reef climate"], n_results=1)
        # ChromaDB-shaped results
        assert "ids" in results
        assert "documents" in results
        assert "metadatas" in results
        assert "distances" in results
        assert len(results["ids"]) == 1  # one query
        assert len(results["ids"][0]) == 1  # one result
        assert results["ids"][0][0] == "d1"

    def test_query_multiple_results(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2", "d3"],
            documents=["sun is a star", "moon orbits earth", "mars is red"],
            metadatas=[{"wing": "astro"}] * 3,
        )
        results = vector_backend.query(query_texts=["solar system"], n_results=3)
        assert len(results["ids"][0]) == 3

    def test_upsert_updates_existing(self, vector_backend):
        vector_backend.add(
            ids=["d1"],
            documents=["original text"],
            metadatas=[{"version": "1"}],
        )
        assert vector_backend.count() == 1
        vector_backend.upsert(
            ids=["d1"],
            documents=["updated text"],
            metadatas=[{"version": "2"}],
        )
        assert vector_backend.count() == 1
        result = vector_backend.get(ids=["d1"])
        assert result["documents"][0] == "updated text"
        assert result["metadatas"][0]["version"] == "2"

    def test_upsert_adds_new(self, vector_backend):
        vector_backend.upsert(
            ids=["new1"],
            documents=["brand new"],
            metadatas=[{"fresh": "yes"}],
        )
        assert vector_backend.count() == 1

    def test_get_by_ids(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2"],
            documents=["doc one", "doc two"],
            metadatas=[{"k": "v1"}, {"k": "v2"}],
        )
        result = vector_backend.get(ids=["d1"])
        assert len(result["ids"]) == 1
        assert result["ids"][0] == "d1"
        assert result["documents"][0] == "doc one"

    def test_get_with_where(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2"],
            documents=["doc one", "doc two"],
            metadatas=[{"wing": "astro"}, {"wing": "econ"}],
        )
        result = vector_backend.get(where={"wing": "astro"})
        assert len(result["ids"]) == 1
        assert result["ids"][0] == "d1"

    def test_delete_by_ids(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2"],
            documents=["doc one", "doc two"],
            metadatas=[{"k": "v1"}, {"k": "v2"}],
        )
        assert vector_backend.count() == 2
        vector_backend.delete(ids=["d1"])
        assert vector_backend.count() == 1

    def test_delete_by_where(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2"],
            documents=["doc one", "doc two"],
            metadatas=[{"wing": "astro"}, {"wing": "econ"}],
        )
        vector_backend.delete(where={"wing": "astro"})
        assert vector_backend.count() == 1

    def test_peek(self, vector_backend):
        vector_backend.add(
            ids=["d1", "d2", "d3"],
            documents=["alpha doc", "beta doc", "gamma doc"],
            metadatas=[{"n": "1"}, {"n": "2"}, {"n": "3"}],
        )
        result = vector_backend.peek(limit=2)
        assert "ids" in result
        assert len(result["ids"]) <= 2

    def test_embed(self, vector_backend):
        """Test that embed() produces vectors for given texts."""
        vectors = vector_backend.embed(["hello world", "test embedding"])
        assert len(vectors) == 2
        assert isinstance(vectors[0], list)
        assert len(vectors[0]) > 0
        # All elements should be floats
        assert isinstance(vectors[0][0], float)

    def test_get_embedding_function(self, vector_backend):
        """get_embedding_function() returns a callable for ChromaDB backend."""
        ef = vector_backend.get_embedding_function()
        assert ef is not None
        assert callable(ef)
        # Should produce embeddings when called
        result = ef(["test text"])
        assert len(result) == 1
        assert len(result[0]) > 0

    def test_repr(self, vector_backend):
        """Repr includes class name, path, and collection info."""
        r = repr(vector_backend)
        assert "ChromaDBVectorBackend" in r

    def test_close_is_noop(self, vector_backend):
        """ChromaDB backend close() is a no-op — doesn't crash."""
        vector_backend.close()
        # Backend should still work after close (PersistentClient has no close)
        assert vector_backend.count() >= 0


# ──────────────────────────────────────────────────────────────────
# PalaceDiscoveryMemory — Backend Injection
# ──────────────────────────────────────────────────────────────────

class TestPalaceBackendInjection:
    """Verify PalaceDiscoveryMemory accepts and uses injected VectorBackend."""

    def test_default_creates_chromadb_backend(self, tmp_dir):
        """Without backend param, defaults to ChromaDB."""
        from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
        from mempalace_agi.config import IntegrationConfig
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace_default"),
            discovery_db_path=os.path.join(tmp_dir, "disc_default.db"),
        )
        mem = PalaceDiscoveryMemory(config=config, max_records=50)
        assert isinstance(mem._backend, ChromaDBVectorBackend)
        assert mem._collection is mem._backend  # backward-compat alias

    def test_injected_backend_used(self, tmp_dir):
        """An injected backend is used instead of creating a new one."""
        from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
        from mempalace_agi.config import IntegrationConfig
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace_inject"),
            discovery_db_path=os.path.join(tmp_dir, "disc_inject.db"),
        )
        injected = create_vector_backend(
            "chromadb",
            path=os.path.join(tmp_dir, "palace_inject"),
            collection_name="custom_collection",
        )
        mem = PalaceDiscoveryMemory(config=config, max_records=50, backend=injected)
        assert mem._backend is injected
        # Recording should work through injected backend
        rec = mem.record_discovery(
            hypothesis_id="H_inject",
            domain="Astrophysics",
            finding_type="correlation",
            variables=["x", "y"],
            statistic=3.0,
            p_value=0.01,
            description="Test via injected backend",
            data_source="test",
        )
        assert rec is not None
        assert injected.count() > 0

    def test_semantic_search_through_backend(self, tmp_dir):
        """Semantic search goes through the backend abstraction."""
        from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
        from mempalace_agi.config import IntegrationConfig
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace_search"),
            discovery_db_path=os.path.join(tmp_dir, "disc_search.db"),
        )
        mem = PalaceDiscoveryMemory(config=config, max_records=50)
        mem.record_discovery(
            hypothesis_id="H_search",
            domain="Astrophysics",
            finding_type="scaling",
            variables=["luminosity", "mass"],
            statistic=5.0,
            p_value=0.001,
            description="Stellar luminosity scales with mass",
            data_source="test_data",
        )
        results = mem.semantic_search("star mass luminosity", n_results=5)
        assert len(results) >= 1
        assert results[0]["domain"] == "Astrophysics"


# ──────────────────────────────────────────────────────────────────
# SQLiteKGBackend — full CRUD + pheromones + provenance
# ──────────────────────────────────────────────────────────────────

class TestSQLiteKGBackend:
    """Test the SQLite KG concrete implementation."""

    # --- Basic triples ---

    def test_add_and_count_triples(self, kg_backend):
        kg_backend.add_triple("sun", "is_a", "star", confidence=0.99, source="test")
        kg_backend.add_triple("earth", "orbits", "sun", confidence=0.95, source="test")
        assert kg_backend.count_triples() >= 2

    def test_add_triple_returns_id(self, kg_backend):
        triple_id = kg_backend.add_triple("A", "causes", "B", source="test")
        assert isinstance(triple_id, str)
        assert len(triple_id) > 0

    def test_query_triples_by_subject(self, kg_backend):
        kg_backend.add_triple("sun", "is_a", "star", confidence=0.99, source="test")
        kg_backend.add_triple("sun", "has_property", "hot", confidence=0.8, source="test")
        kg_backend.add_triple("moon", "orbits", "earth", confidence=0.9, source="test")
        results = kg_backend.query_triples(subject="sun")
        assert len(results) == 2
        subjects = {r["subject"] for r in results}
        assert subjects == {"sun"}

    def test_query_triples_by_predicate(self, kg_backend):
        kg_backend.add_triple("earth", "orbits", "sun", source="test")
        kg_backend.add_triple("moon", "orbits", "earth", source="test")
        results = kg_backend.query_triples(predicate="orbits")
        assert len(results) == 2

    def test_query_triples_by_object(self, kg_backend):
        kg_backend.add_triple("earth", "orbits", "sun", source="test")
        kg_backend.add_triple("mars", "orbits", "sun", source="test")
        results = kg_backend.query_triples(object="sun")
        assert len(results) == 2

    # --- Entities ---

    def test_count_entities(self, kg_backend):
        kg_backend.add_triple("sun", "is_a", "star", source="test")
        # At minimum, "sun" and "star" are entities
        assert kg_backend.count_entities() >= 2

    def test_get_all_entities(self, kg_backend):
        kg_backend.add_triple("sun", "is_a", "star", source="test")
        kg_backend.add_triple("earth", "orbits", "sun", source="test")
        entities = kg_backend.get_all_entities()
        assert "sun" in entities
        assert "earth" in entities
        assert "star" in entities

    def test_get_entity_relations(self, kg_backend):
        kg_backend.add_triple("sun", "is_a", "star", source="test")
        kg_backend.add_triple("earth", "orbits", "sun", source="test")
        rels = kg_backend.get_entity_relations("sun")
        # sun is_a star (outgoing) + earth orbits sun (incoming)
        assert len(rels) >= 2

    # --- Pheromones ---

    def test_update_and_get_pheromone(self, kg_backend):
        triple_id = kg_backend.add_triple("A", "causes", "B", source="test")
        kg_backend.update_pheromone(triple_id, "success_pheromone", 0.5)
        levels = kg_backend.get_pheromone_levels(triple_id)
        assert levels is not None
        assert levels.get("success", 0) >= 0.5 or levels.get("success_pheromone", 0) >= 0.5

    def test_decay_pheromones(self, kg_backend):
        triple_id = kg_backend.add_triple("A", "causes", "B", source="test")
        kg_backend.update_pheromone(triple_id, "success_pheromone", 1.0)
        # Decay rates: column_name → rate
        kg_backend.decay_pheromones({"success_pheromone": 0.5})
        levels = kg_backend.get_pheromone_levels(triple_id)
        assert levels is not None
        # After 50% decay from 1.0, should be ~0.5
        sp = levels.get("success", 0) or levels.get("success_pheromone", 0)
        assert sp <= 0.6

    def test_get_pheromone_stats(self, kg_backend):
        triple_id = kg_backend.add_triple("A", "causes", "B", source="test")
        kg_backend.update_pheromone(triple_id, "success_pheromone", 1.0)
        stats = kg_backend.get_pheromone_stats()
        assert isinstance(stats, dict)
        assert "total_triples" in stats or len(stats) > 0

    # --- Provenance ---

    def test_provenance_lifecycle(self, kg_backend):
        kg_backend.ensure_provenance_schema()
        triple_id = kg_backend.add_triple("X", "influences", "Y", source="test")
        kg_backend.store_provenance(
            triple_id=triple_id,
            agent_id="test_agent",
            cycle_id="cycle_1",
            evidence_chain=["obs1", "obs2"],
            confidence=0.85,
            reason="correlation analysis",
        )
        prov = kg_backend.get_provenance(triple_id)
        assert len(prov) >= 1

    # --- Temporal queries ---

    def test_query_temporal_triples(self, kg_backend):
        kg_backend.ensure_provenance_schema()
        triple_id = kg_backend.add_triple("A", "causes", "B", source="test")
        kg_backend.store_provenance(
            triple_id=triple_id,
            agent_id="test",
            valid_at="2026-01-01",
        )
        # Query all triples (no filter = returns everything)
        results = kg_backend.query_temporal_triples()
        assert len(results) >= 1

    # --- Edge info ---

    def test_get_edge_info(self, kg_backend):
        """get_edge_info takes (source, target) — bidirectional lookup."""
        kg_backend.add_triple("A", "causes", "B", confidence=0.9, source="test")
        info = kg_backend.get_edge_info("A", "B")
        assert info is not None
        assert info.get("confidence", 0) >= 0.9

    def test_get_edge_info_bidirectional(self, kg_backend):
        """Should find edge regardless of direction."""
        kg_backend.add_triple("X", "relates_to", "Y", confidence=0.8, source="test")
        # Query in reverse direction
        info = kg_backend.get_edge_info("Y", "X")
        assert info is not None

    # --- Entity resolution ---

    def test_resolve_entity(self, kg_backend):
        kg_backend.add_triple("temperature", "affects", "sea_level", source="test")
        # Exact match should return the entity
        resolved = kg_backend.resolve_entity("temperature")
        assert resolved == "temperature"

    # --- Raw escape hatch ---

    def test_execute_raw(self, kg_backend):
        kg_backend.add_triple("X", "rel", "Y", source="test")
        results = kg_backend.execute_raw(
            "SELECT COUNT(*) as cnt FROM triples",
        )
        assert len(results) >= 1
        assert results[0]["cnt"] >= 1

    def test_execute_raw_with_params(self, kg_backend):
        kg_backend.add_triple("alpha", "connects", "beta", source="test")
        results = kg_backend.execute_raw(
            "SELECT * FROM triples WHERE subject = ?",
            ("alpha",),
        )
        assert len(results) >= 1


# ──────────────────────────────────────────────────────────────────
# KGBackend Injection — PheromoneManager
# ──────────────────────────────────────────────────────────────────

class TestPheromoneManagerBackendInjection:
    """Verify PheromoneManager works with injected KGBackend."""

    def test_pheromone_with_injected_backend(self, kg_backend):
        """PheromoneManager should accept a KGBackend instance."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        # Seed a triple
        tid = kg_backend.add_triple("temp", "causes", "ice_melt", confidence=0.9, source="test")

        pm = PheromoneManager(backend=kg_backend)
        pm.deposit_success(tid, 0.7)
        levels = pm.get_pheromone_levels(tid)
        assert levels is not None
        assert levels["success"] >= 0.7

    def test_pheromone_backward_compat_db_path(self, tmp_dir):
        """PheromoneManager should still work with db_path string."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        db_path = os.path.join(tmp_dir, "pheromone_compat.db")
        # Create a minimal KG db
        kb = create_kg_backend("sqlite", db_path=db_path)
        tid = kb.add_triple("A", "causes", "B", source="test")
        kb.close()

        pm = PheromoneManager(db_path=db_path)
        pm.deposit_success(tid, 1.0)
        levels = pm.get_pheromone_levels(tid)
        assert levels is not None
        assert levels["success"] >= 1.0

    def test_pheromone_no_args_raises(self):
        """PheromoneManager should raise if neither db_path nor backend given."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        with pytest.raises(ValueError, match="Either db_path or backend"):
            PheromoneManager()

    def test_pheromone_deposit_on_path_via_backend(self, kg_backend):
        """deposit_on_path should work via injected backend."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        t1 = kg_backend.add_triple("A", "causes", "B", source="test")
        t2 = kg_backend.add_triple("B", "causes", "C", source="test")
        t3 = kg_backend.add_triple("C", "causes", "D", source="test")

        pm = PheromoneManager(backend=kg_backend)
        pm.deposit_on_path([t1, t2, t3], base_reward=1.0)

        l1 = pm.get_pheromone_levels(t1)
        l3 = pm.get_pheromone_levels(t3)
        assert l1["success"] > l3["success"]  # First gets more

    def test_pheromone_decay_via_backend(self, kg_backend):
        """decay_all should work via injected backend."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        tid = kg_backend.add_triple("X", "rel", "Y", source="test")
        pm = PheromoneManager(backend=kg_backend)
        pm.deposit_success(tid, 1.0)
        pm.decay_all(rates={"success": 0.5, "traversal": 0.5, "recency": 0.5})
        levels = pm.get_pheromone_levels(tid)
        assert levels["success"] <= 0.6  # Decayed from 1.0 by 50%

    def test_pheromone_modifier_via_backend(self, kg_backend):
        """get_pheromone_modifier should work via injected backend."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        tid = kg_backend.add_triple("X", "causes", "Y", source="test")
        pm = PheromoneManager(backend=kg_backend)

        # No pheromones → modifier should be 1.0
        mod0 = pm.get_pheromone_modifier(tid)
        assert mod0 == 1.0

        # Add pheromones → modifier should decrease
        pm.deposit_success(tid, 1.0)
        pm.deposit_recency(tid, 1.0)
        mod1 = pm.get_pheromone_modifier(tid)
        assert mod1 < 1.0

    def test_pheromone_stats_via_backend(self, kg_backend):
        """get_stats should work via injected backend."""
        from mempalace_agi.kg_pheromones import PheromoneManager

        kg_backend.add_triple("X", "causes", "Y", source="test")
        pm = PheromoneManager(backend=kg_backend)
        pm.deposit_success(
            kg_backend.query_triples(subject="x")[0]["id"], 0.5
        )
        stats = pm.get_stats()
        assert "total_triples" in stats
        assert stats["total_triples"] >= 1


# ──────────────────────────────────────────────────────────────────
# KGBackend Injection — GraphAdapter (Pathfinder)
# ──────────────────────────────────────────────────────────────────

class TestGraphAdapterBackendInjection:
    """Verify GraphAdapter works with injected KGBackend."""

    def test_adapter_with_injected_backend(self, kg_backend):
        """GraphAdapter should accept a KGBackend instance."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        kg_backend.add_triple("a", "causes", "b", confidence=0.8, source="test")
        kg_backend.add_triple("b", "causes", "c", confidence=0.7, source="test")

        adapter = GraphAdapter(backend=kg_backend)
        neighbors = adapter.get_neighbors("b")
        assert "a" in neighbors
        assert "c" in neighbors

    def test_adapter_backward_compat_db_path(self, tmp_dir):
        """GraphAdapter should still work with db_path string."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        db_path = os.path.join(tmp_dir, "adapter_compat.db")
        kb = create_kg_backend("sqlite", db_path=db_path)
        kb.add_triple("x", "causes", "y", confidence=0.9, source="test")
        kb.close()

        adapter = GraphAdapter(db_path=db_path)
        neighbors = adapter.get_neighbors("x")
        assert "y" in neighbors

    def test_adapter_no_args_raises(self):
        """GraphAdapter should raise if neither db_path nor backend given."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        with pytest.raises(ValueError, match="Either db_path or backend"):
            GraphAdapter()

    def test_adapter_edge_info_via_backend(self, kg_backend):
        """get_edge_info should work via injected backend."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        kg_backend.add_triple("sun", "causes", "photosynthesis", confidence=0.95, source="test")
        adapter = GraphAdapter(backend=kg_backend)
        info = adapter.get_edge_info("sun", "photosynthesis")
        assert info is not None
        assert info["confidence"] >= 0.95
        assert info["predicate"] == "causes"

    def test_adapter_edge_cost_via_backend(self, kg_backend):
        """get_edge_cost should work via injected backend."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        kg_backend.add_triple("a", "causes", "b", confidence=0.9, source="test")
        adapter = GraphAdapter(backend=kg_backend)
        cost = adapter.get_edge_cost("a", "b")
        assert 0 < cost < 1.0  # "causes" with high confidence → low cost

    def test_adapter_resolve_entity_via_backend(self, kg_backend):
        """resolve_entity should work via injected backend."""
        from mempalace_agi.kg_pathfinder import GraphAdapter

        kg_backend.add_triple("dark_matter", "influences", "galaxy_rotation", source="test")
        adapter = GraphAdapter(backend=kg_backend)
        resolved = adapter.resolve_entity("dark_matter")
        assert resolved == "dark_matter"
        assert adapter.resolve_entity("nonexistent") is None

    def test_find_knowledge_path_via_backend(self, kg_backend):
        """find_knowledge_path should accept a backend keyword arg."""
        from mempalace_agi.kg_pathfinder import find_knowledge_path

        kg_backend.add_triple("a", "causes", "b", confidence=0.8, source="test")
        kg_backend.add_triple("b", "causes", "c", confidence=0.7, source="test")

        result = find_knowledge_path(
            start_entity="a",
            goal_entity="c",
            backend=kg_backend,
        )
        assert result is not None
        assert result.complete
        assert result.path == ["a", "b", "c"]


# ──────────────────────────────────────────────────────────────────
# KGBackend Injection — KnowledgeGraphBridge
# ──────────────────────────────────────────────────────────────────

class TestKGBridgeBackendInjection:
    """Verify KnowledgeGraphBridge works with injected KGBackend."""

    def test_bridge_with_injected_backend(self, tmp_dir):
        """KnowledgeGraphBridge should accept a KGBackend instance."""
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
        from mempalace_agi.config import IntegrationConfig

        db_path = os.path.join(tmp_dir, "bridge_inject.db")
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace"),
            kg_db_path=db_path,
            discovery_db_path=os.path.join(tmp_dir, "disc.db"),
        )

        kb = create_kg_backend("sqlite", db_path=db_path)
        bridge = KnowledgeGraphBridge(config=config, backend=kb)

        # Backend property should expose the injected backend
        assert bridge.backend is kb

        # Recording should work through injected backend
        from dataclasses import dataclass

        @dataclass
        class MockEdge:
            source: str
            target: str
            edge_type: str = "→"
            confidence: float = 0.8
            p_value: float = 0.01
            conditioning_set: list = None

            def __post_init__(self):
                if self.conditioning_set is None:
                    self.conditioning_set = []

        @dataclass
        class MockGraph:
            variables: list
            edges: list
            algorithm: str = "PC"

        graph = MockGraph(
            variables=["X", "Y"],
            edges=[MockEdge(source="X", target="Y")],
        )
        ids = bridge.record_causal_edges(graph, source_hypothesis="H1")
        assert len(ids) == 1

        # Provenance should be stored through backend
        prov = bridge.get_provenance(ids[0])
        assert prov is not None

    def test_bridge_default_creates_sqlite_backend(self, tmp_dir):
        """Without backend param, creates SQLiteKGBackend internally."""
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
        from mempalace_agi.config import IntegrationConfig

        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace_default"),
            kg_db_path=os.path.join(tmp_dir, "bridge_default.db"),
            discovery_db_path=os.path.join(tmp_dir, "disc_default.db"),
        )
        bridge = KnowledgeGraphBridge(config=config)
        assert isinstance(bridge.backend, SQLiteKGBackend)

    def test_bridge_update_confidence_via_backend(self, tmp_dir):
        """update_confidence uses KGBackend.execute_raw instead of raw sqlite3."""
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
        from mempalace_agi.config import IntegrationConfig

        db_path = os.path.join(tmp_dir, "confidence.db")
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace"),
            kg_db_path=db_path,
            discovery_db_path=os.path.join(tmp_dir, "disc.db"),
        )
        bridge = KnowledgeGraphBridge(config=config)

        # Add a triple through upstream KG
        tid = bridge.kg.add_triple(
            subject="A", predicate="causes", obj="B",
            valid_from="2026-01-01", confidence=0.5,
        )

        # Update confidence via bridge (should use backend, not raw sqlite3)
        bridge.update_confidence(tid, 0.9, reason="new evidence")

        # Verify via backend
        rows = bridge.backend.execute_raw(
            "SELECT confidence FROM triples WHERE id = ?", (tid,),
        )
        assert rows[0]["confidence"] == 0.9

    def test_bridge_check_contradictions_via_backend(self, tmp_dir):
        """check_contradictions uses KGBackend.execute_raw."""
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
        from mempalace_agi.config import IntegrationConfig

        db_path = os.path.join(tmp_dir, "contradict.db")
        config = IntegrationConfig(
            palace_path=os.path.join(tmp_dir, "palace"),
            kg_db_path=db_path,
            discovery_db_path=os.path.join(tmp_dir, "disc.db"),
        )
        bridge = KnowledgeGraphBridge(config=config)

        # Add an existing triple
        bridge.kg.add_entity(name="rain", entity_type="variable")
        bridge.kg.add_entity(name="floods", entity_type="variable")
        bridge.kg.add_triple(
            subject="rain", predicate="causes", obj="floods",
            valid_from="2026-01-01", confidence=0.5,
        )

        # Check contradiction with higher confidence
        results = bridge.check_contradictions(
            new_subject="rain",
            new_predicate="causes",
            new_object="drought",  # contradicts floods
            confidence=0.9,
        )
        assert len(results) >= 1
        assert results[0]["action"] == "invalidated"
