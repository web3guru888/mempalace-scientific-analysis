"""
Tests for KG Pathfinder (causal chain) integration in the Orient phase — Phase 20.

Validates that:
1. use_kg_paths field is correctly set on profiles
2. compose() preserves the new field
3. MemoryAugmentedOrient accepts kg_db_path
4. Causal chains are found when KG contains connecting triples
5. Similarity gets boosted for KG-backed cross-domain hits
6. The feature is entirely optional — no crashes when disabled
"""

import json
import os
import sqlite3
import sys
import tempfile
import shutil
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.retrieval_profiles import (
    RetrievalProfile,
    ORIENT_BREADTH,
    EVALUATE_PRECISION,
    DECIDE_RECENCY,
    compose,
)
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import (
    MemoryAugmentedOrient,
    KG_PATH_BOOST,
)
from mempalace_agi.config import IntegrationConfig


@dataclass
class MockHypothesis:
    id: str
    description: str
    domain: str
    name: str = ""
    variables: list = None


# ── Helper: create a KG SQLite database with test triples ─────────────


def _create_test_kg(db_path: str):
    """Create a small KG with cross-domain causal triples."""
    conn = sqlite3.connect(db_path)
    conn.execute("""CREATE TABLE IF NOT EXISTS triples (
        id INTEGER PRIMARY KEY,
        subject TEXT,
        predicate TEXT,
        object TEXT,
        confidence REAL DEFAULT 0.8,
        source TEXT DEFAULT 'test',
        valid_from TEXT DEFAULT '',
        valid_to TEXT DEFAULT ''
    )""")
    # Climate→Economics chain: co2 → temperature → gdp_change
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('co2', 'causes', 'temperature', 0.9)"
    )
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('temperature', 'causes', 'gdp_change', 0.7)"
    )
    # Economics→Epidemiology chain: population → gdp → life_expectancy
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('population', 'correlated_with', 'gdp', 0.8)"
    )
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('gdp', 'causes', 'life_expectancy', 0.75)"
    )
    # Domain nodes for resolution
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('climate', 'involves_variable', 'co2', 0.9)"
    )
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('climate', 'involves_variable', 'temperature', 0.9)"
    )
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('economics', 'involves_variable', 'gdp', 0.85)"
    )
    conn.execute(
        "INSERT INTO triples (subject, predicate, object, confidence) "
        "VALUES ('economics', 'involves_variable', 'gdp_change', 0.85)"
    )
    conn.commit()
    conn.close()


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
def kg_dir():
    """Temporary directory for KG database."""
    d = tempfile.mkdtemp(prefix="kg_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def kg_db_path(kg_dir):
    """Path to a populated test KG database."""
    path = os.path.join(kg_dir, "test_kg.sqlite3")
    _create_test_kg(path)
    return path


@pytest.fixture
def empty_kg_db_path(kg_dir):
    """Path to an empty KG database (schema only, no triples)."""
    path = os.path.join(kg_dir, "empty_kg.sqlite3")
    conn = sqlite3.connect(path)
    conn.execute("""CREATE TABLE IF NOT EXISTS triples (
        id INTEGER PRIMARY KEY,
        subject TEXT, predicate TEXT, object TEXT,
        confidence REAL DEFAULT 0.8,
        source TEXT DEFAULT 'test',
        valid_from TEXT DEFAULT '',
        valid_to TEXT DEFAULT ''
    )""")
    conn.commit()
    conn.close()
    return path


@pytest.fixture
def memory(test_config):
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


def _populate_cross_domain(memory):
    """Populate memory with discoveries across Climate and Economics domains."""
    memory.record_discovery(
        hypothesis_id="H001", domain="Climate",
        finding_type="anomaly", variables=["temperature", "co2"],
        statistic=6.0, p_value=0.00001,
        description="Temperature anomaly closely tracks atmospheric CO2 levels",
        data_source="gistemp",
    )
    memory.record_discovery(
        hypothesis_id="H002", domain="Economics",
        finding_type="correlation", variables=["gdp_change", "temperature"],
        statistic=3.5, p_value=0.005,
        description="GDP change correlates with temperature fluctuations across nations",
        data_source="worldbank",
    )
    memory.record_discovery(
        hypothesis_id="H003", domain="Epidemiology",
        finding_type="scaling", variables=["life_expectancy", "gdp"],
        statistic=4.2, p_value=0.001,
        description="Life expectancy scales with GDP per capita",
        data_source="who",
    )
    memory.record_discovery(
        hypothesis_id="H004", domain="Astrophysics",
        finding_type="scaling", variables=["mass", "radius"],
        statistic=5.0, p_value=0.0001,
        description="Mass-radius power law in exoplanets",
        data_source="exoplanets",
    )


# ── 1. Profile field tests ────────────────────────────────────────────


class TestUseKgPathsInProfile:
    """Verify use_kg_paths is correctly set on standard profiles."""

    def test_orient_breadth_has_use_kg_paths_true(self):
        assert ORIENT_BREADTH.use_kg_paths is True

    def test_evaluate_precision_has_use_kg_paths_false(self):
        assert EVALUATE_PRECISION.use_kg_paths is False

    def test_decide_recency_has_use_kg_paths_false(self):
        assert DECIDE_RECENCY.use_kg_paths is False

    def test_default_use_kg_paths_is_false(self):
        """A profile created without explicit use_kg_paths defaults to False."""
        p = RetrievalProfile(
            name="test",
            n_results=5,
            min_similarity=0.3,
            time_decay=False,
            half_life_days=None,
            exclude_domain=False,
            require_status=None,
            description="test profile",
        )
        assert p.use_kg_paths is False


# ── 2. compose() tests ───────────────────────────────────────────────


class TestComposePreservesUseKgPaths:
    """compose() correctly handles the use_kg_paths field."""

    def test_compose_preserves_use_kg_paths_true(self):
        custom = compose(ORIENT_BREADTH, n_results=20)
        assert custom.use_kg_paths is True

    def test_compose_preserves_use_kg_paths_false(self):
        custom = compose(EVALUATE_PRECISION, n_results=20)
        assert custom.use_kg_paths is False

    def test_compose_can_override_use_kg_paths(self):
        custom = compose(ORIENT_BREADTH, use_kg_paths=False)
        assert custom.use_kg_paths is False

    def test_compose_can_enable_use_kg_paths(self):
        custom = compose(DECIDE_RECENCY, use_kg_paths=True)
        assert custom.use_kg_paths is True


# ── 3. Constructor tests ──────────────────────────────────────────────


class TestOrientAcceptsKgDbPath:
    """MemoryAugmentedOrient accepts and stores kg_db_path."""

    def test_orient_stores_kg_db_path(self, memory):
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path="/tmp/test_kg.sqlite3",
        )
        assert o.kg_db_path == "/tmp/test_kg.sqlite3"

    def test_orient_stores_pheromone_manager(self, memory):
        sentinel = object()
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            pheromone_manager=sentinel,
        )
        assert o.pheromone_manager is sentinel

    def test_orient_defaults_kg_db_path_none(self, memory):
        o = MemoryAugmentedOrient(palace_memory=memory)
        assert o.kg_db_path is None

    def test_orient_defaults_pheromone_manager_none(self, memory):
        o = MemoryAugmentedOrient(palace_memory=memory)
        assert o.pheromone_manager is None


# ── 4. No kg_db_path → empty causal chains ───────────────────────────


class TestCausalChainWithoutKgDbPath:
    """When kg_db_path is None, causal_chains should be empty."""

    def test_causal_chains_empty_when_no_kg(self, memory):
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(palace_memory=memory)  # No kg_db_path
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="Temperature anomaly CO2",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        assert ctx["causal_chains"] == []

    def test_causal_chains_key_present_when_no_kg(self, memory):
        """The causal_chains key should always be present, even without KG."""
        o = MemoryAugmentedOrient(palace_memory=memory)
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="Test",
                domain="Test",
            )],
            current_domain="Test",
            phase="orient",
        )
        assert "causal_chains" in ctx


# ── 5. Full integration: causal chains found via KG ──────────────────


class TestCausalChainWithKg:
    """Create KG with triples, store discoveries, verify causal chains."""

    def test_finds_causal_chain_climate_to_economics(self, memory, kg_db_path):
        """Climate domain should find causal chain to Economics discoveries."""
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature relationship atmospheric",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )

        # Should have found at least one causal chain
        chains = ctx["causal_chains"]
        assert len(chains) >= 1, (
            f"Expected at least 1 causal chain, got {len(chains)}. "
            f"Cross-domain hits: {[h.get('domain') for h in ctx['cross_domain']]}"
        )

        # Each chain should have the expected structure
        for chain in chains:
            assert "start" in chain
            assert "goal" in chain
            assert "path" in chain
            assert "cost" in chain
            assert "hops" in chain
            assert "discovery_id" in chain
            assert chain["hops"] >= 1
            assert len(chain["path"]) >= 2

    def test_kg_path_metadata_on_hit(self, memory, kg_db_path):
        """Cross-domain hits with KG path should have kg_path metadata."""
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature atmospheric",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )

        # Find hits that have kg_path metadata
        hits_with_path = [
            h for h in ctx["cross_domain"]
            if "kg_path" in h
        ]

        if ctx["causal_chains"]:
            assert len(hits_with_path) >= 1
            for h in hits_with_path:
                assert "path" in h["kg_path"]
                assert "cost" in h["kg_path"]
                assert "hops" in h["kg_path"]


# ── 6. Similarity boost ──────────────────────────────────────────────


class TestKgPathBoostsSimilarity:
    """Cross-domain hits with KG paths get boosted similarity."""

    def test_boost_increases_similarity(self, memory, kg_db_path):
        """A hit with a KG path should have a higher similarity than without."""
        _populate_cross_domain(memory)

        # First: get cross-domain hits WITHOUT KG paths
        o_no_kg = MemoryAugmentedOrient(
            palace_memory=memory,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx_no_kg = o_no_kg.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature atmospheric",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        sims_no_kg = {
            h["discovery_id"]: h["similarity"]
            for h in ctx_no_kg["cross_domain"]
        }

        # Second: get cross-domain hits WITH KG paths
        o_with_kg = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx_with_kg = o_with_kg.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature atmospheric",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )

        # Any hit that got a KG path should have higher (or equal) similarity
        for hit in ctx_with_kg["cross_domain"]:
            did = hit["discovery_id"]
            if "kg_path" in hit and did in sims_no_kg:
                original_sim = sims_no_kg[did]
                boosted_sim = hit["similarity"]
                assert boosted_sim >= original_sim, (
                    f"Expected boosted sim >= original for {did}: "
                    f"{boosted_sim} < {original_sim}"
                )


# ── 7. causal_chains key always in result ────────────────────────────


class TestCausalChainsKeyInResult:
    """retrieve_context result always has a 'causal_chains' key."""

    def test_key_present_with_orient(self, memory):
        ctx = MemoryAugmentedOrient(palace_memory=memory).retrieve_context(
            hypotheses=[MockHypothesis(id="H1", description="test", domain="X")],
            current_domain="X",
            phase="orient",
        )
        assert "causal_chains" in ctx
        assert isinstance(ctx["causal_chains"], list)

    def test_key_present_with_evaluate(self, memory):
        ctx = MemoryAugmentedOrient(palace_memory=memory).retrieve_context(
            hypotheses=[MockHypothesis(id="H1", description="test", domain="X")],
            current_domain="X",
            phase="evaluate",
        )
        assert "causal_chains" in ctx

    def test_key_present_with_decide(self, memory):
        ctx = MemoryAugmentedOrient(palace_memory=memory).retrieve_context(
            hypotheses=[MockHypothesis(id="H1", description="test", domain="X")],
            current_domain="X",
            phase="decide",
        )
        assert "causal_chains" in ctx


# ── 8. No boost when use_kg_paths=False ──────────────────────────────


class TestNoBoostWithoutProfileFlag:
    """When use_kg_paths=False, no boost applied even if kg_db_path is set."""

    def test_evaluate_no_boost_even_with_kg(self, memory, kg_db_path):
        """EVALUATE_PRECISION has use_kg_paths=False — no causal chains."""
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            evaluate_profile=compose(EVALUATE_PRECISION, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="evaluate",
        )
        assert ctx["causal_chains"] == []

    def test_custom_profile_no_kg_paths(self, memory, kg_db_path):
        """A custom orient profile with use_kg_paths=False should not boost."""
        _populate_cross_domain(memory)
        no_kg_profile = compose(ORIENT_BREADTH, use_kg_paths=False, min_similarity=0.0)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=no_kg_profile,
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        assert ctx["causal_chains"] == []
        # No hit should have kg_path metadata
        for hit in ctx["cross_domain"]:
            assert "kg_path" not in hit


# ── 9. Graceful degradation ──────────────────────────────────────────


class TestGracefulDegradation:
    """If KG is empty, no triples connect, or errors occur, no crash."""

    def test_empty_kg_no_crash(self, memory, empty_kg_db_path):
        """Empty KG (no triples) should produce empty causal_chains."""
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=empty_kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        assert ctx["causal_chains"] == []
        # Cross-domain hits should still be returned (just no boost)
        # (may be empty if no cross-domain discoveries match)

    def test_nonexistent_kg_path_no_crash(self, memory, kg_dir):
        """A KG path pointing to a non-existent file should not crash."""
        _populate_cross_domain(memory)
        bad_path = os.path.join(kg_dir, "nonexistent.sqlite3")
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=bad_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        # Should not raise — _find_causal_chains wraps errors
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        assert "causal_chains" in ctx

    def test_no_cross_domain_hits_no_crash(self, memory, kg_db_path):
        """When there are no cross-domain discoveries, causal_chains is empty."""
        # Only populate one domain — no cross-domain hits possible
        memory.record_discovery(
            hypothesis_id="H001", domain="Climate",
            finding_type="anomaly", variables=["temperature", "co2"],
            statistic=6.0, p_value=0.00001,
            description="Temperature anomaly tracks CO2",
            data_source="gistemp",
        )
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="Temperature CO2",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )
        assert ctx["causal_chains"] == []


# ── 10. Boost capped at 1.0 ──────────────────────────────────────────


class TestBoostCappedAt1:
    """Similarity after boost should never exceed 1.0."""

    def test_boost_cap(self, memory, kg_db_path):
        """Even with KG_PATH_BOOST applied, similarity stays ≤ 1.0."""
        _populate_cross_domain(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            kg_db_path=kg_db_path,
            orient_profile=compose(ORIENT_BREADTH, min_similarity=0.0),
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(
                id="H010",
                description="CO2 temperature atmospheric",
                domain="Climate",
            )],
            current_domain="Climate",
            phase="orient",
        )

        for hit in ctx["cross_domain"]:
            assert hit["similarity"] <= 1.0, (
                f"Similarity exceeds 1.0 for {hit['discovery_id']}: "
                f"{hit['similarity']}"
            )

    def test_boost_factor_value(self):
        """KG_PATH_BOOST should be 1.2."""
        assert KG_PATH_BOOST == 1.2
