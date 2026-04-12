"""
Tests for time_decay feature — Phase 19 P0 Task 1.

Validates that MemoryAugmentedOrient._apply_time_decay() works correctly
and that retrieve_context() applies it when profile.time_decay is True.
"""

import math
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import MemoryAugmentedOrient
from mempalace_agi.config import IntegrationConfig
from mempalace_agi.retrieval_profiles import (
    RetrievalProfile,
    ORIENT_BREADTH,
    DECIDE_RECENCY,
    compose,
)


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


def _make_results_with_ages(ages_days, base_similarity=0.8):
    """Create mock search result dicts with filed_at timestamps at given ages."""
    now = datetime.utcnow()
    results = []
    for i, age in enumerate(ages_days):
        filed_at = (now - timedelta(days=age)).isoformat()
        results.append({
            "discovery_id": f"D{i:04d}",
            "similarity": base_similarity,
            "domain": "Astrophysics",
            "finding_type": "correlation",
            "hypothesis_id": f"H{i:04d}",
            "strength": 0.7,
            "data_source": "test",
            "text": f"Discovery {i}",
            "metadata": {
                "filed_at": filed_at,
                "timestamp": (now - timedelta(days=age)).timestamp(),
            },
        })
    return results


class TestApplyTimeDecay:
    """Test _apply_time_decay static method directly."""

    def test_recent_items_score_higher_than_old(self):
        """Items 1 day old score much higher than items 180 days old."""
        results = _make_results_with_ages([1, 180], base_similarity=0.8)
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        # Recent item should have higher decayed similarity
        assert decayed[0]["discovery_id"] == "D0000"  # 1-day old first
        assert decayed[0]["decayed_similarity"] > decayed[1]["decayed_similarity"]

        # 180-day old with 30-day half-life: factor = 2^(-180/30) = 2^(-6) = 0.015625
        # decayed = 0.8 * 0.015625 ≈ 0.0125
        assert decayed[1]["decayed_similarity"] < 0.02

    def test_half_life_formula_30_days(self):
        """30-day-old item with half_life=30 gets similarity halved."""
        results = _make_results_with_ages([30], base_similarity=0.8)
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        # Expected: 0.8 * 2^(-30/30) = 0.8 * 0.5 = 0.4
        # Allow small floating-point tolerance (filed_at might be fractionally off)
        assert abs(decayed[0]["decayed_similarity"] - 0.4) < 0.01

    def test_zero_age_unchanged(self):
        """Item with age ~0 days keeps original similarity."""
        results = _make_results_with_ages([0], base_similarity=0.9)
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        # Factor should be ~1.0
        assert abs(decayed[0]["decayed_similarity"] - 0.9) < 0.01

    def test_results_reordered_by_decayed_score(self):
        """Results are sorted by decayed_similarity descending, not original similarity."""
        now = datetime.utcnow()
        results = [
            {
                "discovery_id": "D_old_high_sim",
                "similarity": 0.95,  # High similarity but old
                "metadata": {"filed_at": (now - timedelta(days=90)).isoformat()},
            },
            {
                "discovery_id": "D_new_lower_sim",
                "similarity": 0.60,  # Lower similarity but recent
                "metadata": {"filed_at": (now - timedelta(days=1)).isoformat()},
            },
        ]
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        # Old high-sim: 0.95 * 2^(-90/30) = 0.95 * 0.125 = 0.119
        # New lower-sim: 0.60 * 2^(-1/30) = 0.60 * 0.977 ≈ 0.586
        # New item should rank first
        assert decayed[0]["discovery_id"] == "D_new_lower_sim"
        assert decayed[1]["discovery_id"] == "D_old_high_sim"

    def test_age_days_populated(self):
        """Each result gets an age_days field."""
        results = _make_results_with_ages([7, 60], base_similarity=0.8)
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        for hit in decayed:
            assert "age_days" in hit
            assert hit["age_days"] >= 0

    def test_decayed_similarity_populated(self):
        """Each result gets a decayed_similarity field."""
        results = _make_results_with_ages([5], base_similarity=0.7)
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)

        assert "decayed_similarity" in decayed[0]
        assert 0 < decayed[0]["decayed_similarity"] <= 0.7

    def test_empty_results(self):
        """Empty list returns empty list."""
        decayed = MemoryAugmentedOrient._apply_time_decay([], half_life_days=30)
        assert decayed == []

    def test_missing_metadata_defaults_to_no_decay(self):
        """Results without timestamp metadata get decay factor 1.0 (no penalty)."""
        results = [{
            "discovery_id": "D_no_meta",
            "similarity": 0.8,
            "metadata": {},
        }]
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)
        # With age_days=0, decay factor=1.0, decayed = 0.8
        assert abs(decayed[0]["decayed_similarity"] - 0.8) < 0.001

    def test_epoch_timestamp_fallback(self):
        """When filed_at is missing, timestamp (epoch float) is used."""
        now = datetime.utcnow()
        epoch_30_days_ago = (now - timedelta(days=30)).timestamp()

        results = [{
            "discovery_id": "D_epoch",
            "similarity": 0.8,
            "metadata": {"timestamp": epoch_30_days_ago},  # No filed_at
        }]
        decayed = MemoryAugmentedOrient._apply_time_decay(results, half_life_days=30)
        # Should be ~0.4 (half of 0.8)
        assert abs(decayed[0]["decayed_similarity"] - 0.4) < 0.02


class TestTimeDecayInRetrieveContext:
    """Test that retrieve_context() applies time_decay when profile enables it."""

    def test_no_decay_with_orient_profile(self, memory):
        """ORIENT_BREADTH has time_decay=False — results should NOT have decayed_similarity."""
        # Populate
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="correlation", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law in exoplanets",
            data_source="exoplanets",
        )

        orient = MemoryAugmentedOrient(palace_memory=memory)
        hypotheses = [MockHypothesis(id="H005", description="Planet mass radius", domain="Astrophysics")]
        context = orient.retrieve_context(hypotheses=hypotheses, phase="orient")

        # Orient profile has time_decay=False, so no decayed_similarity should be added
        for hits in context["per_hypothesis"].values():
            for hit in hits:
                assert "decayed_similarity" not in hit

    def test_decay_applied_with_decide_profile(self, memory):
        """DECIDE_RECENCY has time_decay=True — results SHOULD have decayed_similarity."""
        # Populate
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="correlation", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law in exoplanets",
            data_source="exoplanets",
        )

        # Decide profile with time_decay=True, require_status=None for this test
        decide_no_status = compose(DECIDE_RECENCY, require_status=None)
        orient = MemoryAugmentedOrient(
            palace_memory=memory,
            decide_profile=decide_no_status,
        )
        hypotheses = [MockHypothesis(id="H005", description="Planet mass radius", domain="Astrophysics")]
        context = orient.retrieve_context(hypotheses=hypotheses, phase="decide")

        # Decide profile has time_decay=True, so decayed_similarity should be present
        for hits in context["per_hypothesis"].values():
            for hit in hits:
                assert "decayed_similarity" in hit
                assert "age_days" in hit
                # Since discovery was just stored, age is ~0, decayed ≈ original
                assert hit["decayed_similarity"] > 0

    def test_custom_profile_with_decay(self, memory):
        """Custom profile with time_decay=True applies decay."""
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law",
            data_source="test",
        )

        custom = compose(ORIENT_BREADTH, time_decay=True, half_life_days=7)
        orient = MemoryAugmentedOrient(
            palace_memory=memory,
            orient_profile=custom,
        )
        hypotheses = [MockHypothesis(id="H005", description="Mass radius", domain="Astrophysics")]
        context = orient.retrieve_context(hypotheses=hypotheses, phase="orient")

        for hits in context["per_hypothesis"].values():
            for hit in hits:
                assert "decayed_similarity" in hit
