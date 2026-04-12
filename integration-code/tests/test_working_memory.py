"""
Tests for WorkingMemoryBuffer — capacity-limited recency cache.

Phase 23: ASI:BUILD adoption from consciousness_engine/memory_integration.py.
"""

import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.memory_augmented_orient import (
    WorkingMemoryBuffer,
    WorkingMemoryItem,
    MemoryAugmentedOrient,
    WORKING_MEMORY_BOOST,
)
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.config import IntegrationConfig
from dataclasses import dataclass


@dataclass
class MockHypothesis:
    """Minimal hypothesis object for testing."""
    id: str
    description: str
    domain: str
    confidence: float = 0.5
    name: str = ""
    variables: list = None


class TestWorkingMemoryBufferBasics:
    """Test core buffer operations."""

    def test_initial_state(self):
        """Buffer starts empty."""
        buf = WorkingMemoryBuffer(capacity=7)
        assert buf.size == 0
        assert not buf.is_full
        assert buf.get_items() == []

    def test_access_adds_item(self):
        """Accessing an item adds it to the buffer."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "galaxy rotation curves", "Astrophysics", 0.8)
        assert buf.size == 1
        assert buf.contains("D001")

    def test_access_count_increments(self):
        """Re-accessing the same item increments its access count."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "galaxy rotation curves", "Astrophysics", 0.8)
        buf.access("D001", "galaxy rotation curves", "Astrophysics", 0.6)
        assert buf.size == 1  # Still 1 item
        items = buf.get_items()
        assert items[0].access_count == 2
        # Relevance should be the max of all accesses
        assert items[0].relevance_score == 0.8

    def test_relevance_takes_max(self):
        """Re-access with higher relevance updates the score."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "test", "Astrophysics", 0.5)
        buf.access("D001", "test", "Astrophysics", 0.9)
        assert buf.get_items()[0].relevance_score == 0.9

    def test_capacity_limit(self):
        """Buffer doesn't exceed capacity."""
        buf = WorkingMemoryBuffer(capacity=3)
        buf.access("D001", "a", "A", 0.5)
        buf.access("D002", "b", "B", 0.5)
        buf.access("D003", "c", "C", 0.5)
        assert buf.size == 3
        assert buf.is_full
        # Adding a 4th should evict the oldest (D001)
        buf.access("D004", "d", "D", 0.5)
        assert buf.size == 3
        assert not buf.contains("D001")
        assert buf.contains("D004")

    def test_eviction_order(self):
        """Oldest accessed item is evicted first (LRU)."""
        buf = WorkingMemoryBuffer(capacity=3)
        buf.access("D001", "first", "A", 0.5)
        buf.access("D002", "second", "B", 0.5)
        buf.access("D003", "third", "C", 0.5)
        # Re-access D001 to make it recent
        buf.access("D001", "first", "A", 0.5)
        # Now D002 is the oldest → should be evicted
        buf.access("D004", "fourth", "D", 0.5)
        assert buf.contains("D001")  # Re-accessed recently
        assert not buf.contains("D002")  # Oldest, evicted
        assert buf.contains("D003")
        assert buf.contains("D004")

    def test_get_items_sorted_by_relevance(self):
        """get_items returns items sorted by relevance (highest first)."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "low relevance", "A", 0.3)
        buf.access("D002", "high relevance", "B", 0.9)
        buf.access("D003", "mid relevance", "C", 0.6)
        items = buf.get_items()
        scores = [item.relevance_score for item in items]
        assert scores == sorted(scores, reverse=True)
        assert items[0].discovery_id == "D002"

    def test_clear(self):
        """clear() empties the buffer."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "test", "A", 0.5)
        buf.access("D002", "test", "B", 0.5)
        buf.clear()
        assert buf.size == 0
        assert not buf.contains("D001")

    def test_contains_false_for_missing(self):
        """contains returns False for items not in buffer."""
        buf = WorkingMemoryBuffer(capacity=7)
        assert not buf.contains("D999")


class TestWorkingMemorySearch:
    """Test keyword search within working memory."""

    def test_search_finds_matching_items(self):
        """search_working_memory finds items with overlapping keywords."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "galaxy rotation curves dark matter", "Astrophysics", 0.8)
        buf.access("D002", "GDP population scaling law", "Economics", 0.7)
        buf.access("D003", "galaxy cluster luminosity", "Astrophysics", 0.6)

        results = buf.search_working_memory({"galaxy", "rotation"})
        assert len(results) >= 1
        ids = [r.discovery_id for r in results]
        assert "D001" in ids

    def test_search_returns_sorted_by_relevance(self):
        """Search results are sorted by relevance_score descending."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "scaling law power", "A", 0.3)
        buf.access("D002", "scaling relation fit", "B", 0.9)
        results = buf.search_working_memory({"scaling"})
        assert len(results) == 2
        assert results[0].relevance_score >= results[1].relevance_score

    def test_search_no_match(self):
        """Search returns empty when no keywords match."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "galaxy rotation", "A", 0.5)
        results = buf.search_working_memory({"quantum", "entanglement"})
        assert results == []

    def test_search_case_insensitive(self):
        """Search is case-insensitive (content stored lowercase)."""
        buf = WorkingMemoryBuffer(capacity=7)
        buf.access("D001", "Galaxy Rotation Curves", "A", 0.8)
        # Query terms should be lowercase, content is lowercased in search
        results = buf.search_working_memory({"galaxy"})
        assert len(results) == 1


class TestWorkingMemoryIntegration:
    """Test integration of WorkingMemoryBuffer into MemoryAugmentedOrient."""

    @pytest.fixture
    def memory(self, test_config):
        return PalaceDiscoveryMemory(config=test_config, max_records=100)

    @pytest.fixture
    def orient(self, memory):
        return MemoryAugmentedOrient(
            palace_memory=memory,
            max_results_per_hypothesis=3,
            cross_domain_results=2,
            min_similarity=0.0,
        )

    def test_orient_has_working_memory(self, orient):
        """MemoryAugmentedOrient initializes with a WorkingMemoryBuffer."""
        assert hasattr(orient, "working_memory")
        assert isinstance(orient.working_memory, WorkingMemoryBuffer)
        assert orient.working_memory.capacity == 7

    def test_working_memory_populated_after_retrieval(self, memory, orient):
        """After retrieve_context, working memory contains retrieved discoveries."""
        # Store a discovery
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law in exoplanets",
            data_source="exoplanets",
        )

        hypotheses = [MockHypothesis(id="H005", description="Planetary mass affects radius", domain="Astrophysics")]
        orient.retrieve_context(hypotheses=hypotheses, current_domain="Astrophysics")

        # Working memory should now contain the retrieved discovery
        assert orient.working_memory.size > 0

    def test_working_memory_stats_in_result(self, memory, orient):
        """retrieve_context includes working_memory stats in memory_stats."""
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law",
            data_source="exoplanets",
        )

        hypotheses = [MockHypothesis(id="H005", description="Mass radius", domain="Astrophysics")]
        result = orient.retrieve_context(hypotheses=hypotheses, current_domain="Astrophysics")

        assert "working_memory_hits" in result["memory_stats"]
        assert "working_memory_size" in result["memory_stats"]

    def test_second_retrieval_gets_wm_hits(self, memory, orient):
        """Second retrieval benefits from working memory (fast path)."""
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law in exoplanets",
            data_source="exoplanets",
        )

        hyps = [MockHypothesis(id="H005", description="mass radius exoplanets power law", domain="Astrophysics")]

        # First retrieval populates working memory
        result1 = orient.retrieve_context(hypotheses=hyps, current_domain="Astrophysics")
        assert orient.working_memory.size > 0

        # Second retrieval should get working memory hits
        result2 = orient.retrieve_context(hypotheses=hyps, current_domain="Astrophysics")
        assert result2["memory_stats"]["working_memory_hits"] > 0
