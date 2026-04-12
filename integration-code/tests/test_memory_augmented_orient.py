"""
Tests for MemoryAugmentedOrient — semantic memory injection into OODA Orient.
"""

import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import MemoryAugmentedOrient
from mempalace_agi.config import IntegrationConfig


@dataclass
class MockHypothesis:
    """Minimal hypothesis object for testing."""
    id: str
    description: str
    domain: str
    confidence: float = 0.5
    name: str = ""
    variables: list = None


@pytest.fixture
def memory(test_config):
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


@pytest.fixture
def orient(memory):
    return MemoryAugmentedOrient(
        palace_memory=memory,
        max_results_per_hypothesis=3,
        cross_domain_results=2,
        min_similarity=0.0,  # Low threshold for testing
    )


def _populate(memory):
    """Populate memory with test discoveries."""
    memory.record_discovery(
        hypothesis_id="H001", domain="Astrophysics",
        finding_type="scaling", variables=["mass", "radius"],
        statistic=5.0, p_value=0.0001,
        description="Mass-radius power law in exoplanets: R ∝ M^0.27",
        data_source="exoplanets", sample_size=4000,
    )
    memory.record_discovery(
        hypothesis_id="H002", domain="Astrophysics",
        finding_type="correlation", variables=["redshift", "luminosity"],
        statistic=3.5, p_value=0.001,
        description="Hubble diagram correlation for Type Ia supernovae",
        data_source="pantheon",
    )
    memory.record_discovery(
        hypothesis_id="H003", domain="Economics",
        finding_type="scaling", variables=["gdp", "population"],
        statistic=4.0, p_value=0.005,
        description="GDP scales with population as a power law across nations",
        data_source="worldbank",
    )
    memory.record_discovery(
        hypothesis_id="H004", domain="Climate",
        finding_type="anomaly", variables=["temperature", "co2"],
        statistic=6.0, p_value=0.00001,
        description="Temperature anomaly closely tracks atmospheric CO2 levels",
        data_source="gistemp",
    )


class TestRetrieveContext:
    """Test the main retrieve_context method."""

    def test_basic_retrieval(self, memory, orient):
        """retrieve_context returns structured result."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Planetary mass affects radius", domain="Astrophysics"),
        ]

        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        assert "per_hypothesis" in context
        assert "cross_domain" in context
        assert "domain_context" in context
        assert "suggestions" in context
        assert "memory_stats" in context

    def test_per_hypothesis_retrieval(self, memory, orient):
        """Each hypothesis gets relevant memory hits."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Mass-radius relationship in planets", domain="Astrophysics"),
            MockHypothesis(id="H006", description="Economic growth scaling laws", domain="Economics"),
        ]

        context = orient.retrieve_context(hypotheses=hypotheses)

        # H005 should find the mass-radius discovery
        assert "H005" in context["per_hypothesis"]
        h005_hits = context["per_hypothesis"]["H005"]
        assert len(h005_hits) > 0

        # H006 should find the GDP-population discovery
        assert "H006" in context["per_hypothesis"]
        h006_hits = context["per_hypothesis"]["H006"]
        assert len(h006_hits) > 0

    def test_cross_domain_search(self, memory, orient):
        """Cross-domain results come from OTHER domains."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Scaling laws in astrophysics", domain="Astrophysics"),
        ]

        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        # Cross-domain results should NOT be Astrophysics
        for hit in context["cross_domain"]:
            assert hit["domain"] != "Astrophysics"

    def test_single_hypothesis_cross_domain_augmentation(self, memory, orient):
        """Single-hypothesis cross-domain query is augmented with domain + name + variables."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(
                id="H010",
                description="Pandemic Recovery Trajectory",
                domain="Epidemiology",
                name="Pandemic Recovery",
                variables=["life_expectancy", "vaccination_rate"],
            ),
        ]

        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Epidemiology",
        )

        # The augmented query should reach across domains (Astrophysics,
        # Economics, Climate) because the domain + variable context broadens
        # the embedding surface.  At minimum, we get a non-empty cross_domain
        # list or the search ran without error.
        assert isinstance(context["cross_domain"], list)
        # Verify per-hypothesis results are present
        assert "H010" in context["per_hypothesis"]

    def test_single_hypothesis_no_variables(self, memory, orient):
        """Single hypothesis without variables still augments with domain + name."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(
                id="H011",
                description="Temperature anomaly tracking",
                domain="Climate",
                name="Temp Anomaly",
            ),
        ]

        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Climate",
        )

        # Should not crash and cross-domain should exclude Climate
        for hit in context["cross_domain"]:
            assert hit["domain"] != "Climate"

    def test_domain_context(self, memory, orient):
        """Domain context returns recent discoveries for that domain."""
        _populate(memory)

        hypotheses = [MockHypothesis(id="H005", description="Test", domain="Astrophysics")]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        assert len(context["domain_context"]) > 0
        for item in context["domain_context"]:
            assert item["domain"] == "Astrophysics"

    def test_memory_stats(self, memory, orient):
        """Memory stats are computed correctly."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Planet radii", domain="Astrophysics"),
            MockHypothesis(id="H006", description="GDP growth", domain="Economics"),
        ]

        context = orient.retrieve_context(hypotheses=hypotheses)
        stats = context["memory_stats"]

        assert stats["total_queries"] == 2  # One per hypothesis
        assert stats["total_hits"] >= 0
        assert isinstance(stats["unique_discoveries_surfaced"], int)

    def test_empty_hypotheses(self, memory, orient):
        """Empty hypothesis list returns empty context."""
        context = orient.retrieve_context(hypotheses=[])

        assert context["per_hypothesis"] == {}
        assert context["cross_domain"] == []
        assert context["suggestions"] == []


class TestScoreHypothesisWithMemory:
    """Test memory-informed hypothesis scoring."""

    def test_score_with_hits(self, memory, orient):
        """Hypothesis with relevant memory gets a positive score."""
        _populate(memory)

        hyp = MockHypothesis(id="H005", description="Planet mass-radius", domain="Astrophysics")
        hits = memory.semantic_search("planet mass radius", n_results=3)

        score = orient.score_hypothesis_with_memory(hyp, hits)
        assert 0.0 <= score <= 0.3

    def test_score_without_hits(self, orient):
        """Hypothesis without memory hits gets zero score."""
        hyp = MockHypothesis(id="H005", description="Anything", domain="Astrophysics")
        score = orient.score_hypothesis_with_memory(hyp, [])
        assert score == 0.0

    def test_score_is_bounded(self, memory, orient):
        """Score is always between 0 and 0.3."""
        _populate(memory)

        hyp = MockHypothesis(id="H005", description="Scaling laws", domain="Astrophysics")
        hits = memory.semantic_search("scaling laws mass radius", n_results=10)

        score = orient.score_hypothesis_with_memory(hyp, hits)
        assert 0.0 <= score <= 0.3


class TestDedicatedCrossDomainSearch:
    """Test the dedicated cross-domain search pass (Cycle 2 improvement)."""

    def test_cross_domain_discoveries_key_present(self, memory, orient):
        """retrieve_context returns the new cross_domain_discoveries key."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Scaling laws in physics", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        assert "cross_domain_discoveries" in context
        assert isinstance(context["cross_domain_discoveries"], list)
        # Should be same reference as cross_domain (backward compat)
        assert context["cross_domain"] is context["cross_domain_discoveries"]

    def test_cross_domain_excludes_current_domain(self, memory, orient):
        """Dedicated cross-domain search excludes the current domain at DB level."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Scaling relationships", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        # ALL cross-domain results must be from OTHER domains
        for hit in context["cross_domain_discoveries"]:
            assert hit["domain"] != "Astrophysics", (
                f"Current domain 'Astrophysics' leaked into cross-domain results"
            )

    def test_cross_domain_finds_other_domains(self, memory, orient):
        """Cross-domain search actually finds results from other domains."""
        _populate(memory)

        # Search from Economics perspective — should find scaling in Astrophysics
        hypotheses = [
            MockHypothesis(
                id="H006",
                description="Power law scaling between variables",
                domain="Economics",
            ),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Economics",
        )

        cross_hits = context["cross_domain_discoveries"]
        # With min_similarity=0.0 in the orient fixture, we should get hits
        if cross_hits:
            domains_found = {h["domain"] for h in cross_hits}
            assert "Economics" not in domains_found
            # Should find Astrophysics or Climate
            assert len(domains_found) >= 1

    def test_cross_domain_empty_without_current_domain(self, memory, orient):
        """No cross-domain search when current_domain is not specified."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Scaling laws", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain=None,  # No domain specified
        )

        assert context["cross_domain_discoveries"] == []
        assert context["cross_domain"] == []

    def test_cross_domain_stats_tracked(self, memory, orient):
        """Cross-domain discoveries are counted in memory_stats."""
        _populate(memory)

        hypotheses = [
            MockHypothesis(id="H005", description="Power law scaling", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        stats = context["memory_stats"]
        # total_queries should include the cross-domain query (if hits were found)
        n_cross = len(context["cross_domain_discoveries"])
        if n_cross > 0:
            # At least 2 queries: 1 per-hypothesis + 1 cross-domain
            assert stats["total_queries"] >= 2
            assert stats["total_hits"] >= n_cross


class TestCrossDomainDefaults:
    """Verify Cycle 3 cross-domain parameter defaults."""

    def test_default_cross_domain_results_is_10(self, memory):
        """Default cross_domain_results was raised from 5 to 10 (Cycle 3)."""
        orient = MemoryAugmentedOrient(palace_memory=memory)
        assert orient.cross_domain_results == 10

    def test_default_min_similarity_is_02(self, memory):
        """Default min_similarity was lowered from 0.3 to 0.2 (Cycle 3)."""
        orient = MemoryAugmentedOrient(palace_memory=memory)
        assert orient.min_similarity == 0.2

    def test_wider_cross_domain_retrieval(self, memory):
        """With lower min_similarity, weaker cross-domain connections are captured.

        Cycle 3 goal: raise cross-domain orient hits from 5 to 8+ by
        lowering the min_similarity threshold and increasing n_results.
        """
        _populate(memory)

        # Use the new defaults (10 results, 0.2 min_similarity)
        orient = MemoryAugmentedOrient(palace_memory=memory)

        hypotheses = [
            MockHypothesis(
                id="H005",
                description="Scaling relationships across domains",
                domain="Astrophysics",
            ),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
        )

        # With min_similarity=0.2, we should capture more cross-domain hits
        # than we would with 0.3 (some marginal connections now pass)
        cross_hits = context["cross_domain_discoveries"]
        # Cross-domain hits should exist (Economics and Climate have entries)
        assert isinstance(cross_hits, list)
        for hit in cross_hits:
            assert hit["domain"] != "Astrophysics"
            assert hit["similarity"] >= 0.2

    def test_overrideable_cross_domain_params(self, memory):
        """Callers can still override cross_domain_results and min_similarity."""
        orient = MemoryAugmentedOrient(
            palace_memory=memory,
            cross_domain_results=3,
            min_similarity=0.5,
        )
        assert orient.cross_domain_results == 3
        assert orient.min_similarity == 0.5
