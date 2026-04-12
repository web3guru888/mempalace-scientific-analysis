"""
Tests for ConsolidationState lifecycle — ASI:BUILD adoption.

Phase 23: Tests the INITIAL → CONSOLIDATING → CONSOLIDATED → RECONSOLIDATING
lifecycle for discovery memory entries.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.palace_discovery_memory import (
    PalaceDiscoveryMemory,
    ConsolidationState,
)
from mempalace_agi.config import IntegrationConfig


@pytest.fixture
def memory(test_config):
    """Create a PalaceDiscoveryMemory instance with test config."""
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


# Domains and descriptions that are distinct enough to avoid hard-duplicate detection
_DISCOVERY_TEMPLATES = [
    ("Astrophysics", "correlation", ["mass", "radius"], "Mass-radius power law in exoplanets"),
    ("Economics", "scaling", ["gdp", "population"], "GDP scales with population across nations"),
    ("Climate", "anomaly", ["temperature", "co2"], "Temperature anomaly tracks atmospheric CO2"),
    ("Epidemiology", "trend", ["life_expectancy", "vaccination"], "Life expectancy rises with vaccination"),
    ("Cryptography", "distribution", ["key_length", "entropy"], "Key entropy distribution analysis"),
]


def _make_discovery(memory, idx=1, domain=None):
    """Helper: record a discovery and return the result.

    Each idx gets a distinct domain/variables/description to avoid
    the hard-duplicate detector (similarity > 0.92 threshold).
    """
    tmpl = _DISCOVERY_TEMPLATES[(idx - 1) % len(_DISCOVERY_TEMPLATES)]
    use_domain = domain or tmpl[0]
    return memory.record_discovery(
        hypothesis_id=f"H{idx:03d}",
        domain=use_domain,
        finding_type=tmpl[1],
        variables=tmpl[2],
        statistic=3.5 + idx * 0.1,
        p_value=0.001,
        description=f"{tmpl[3]} (variant {idx})",
        data_source=f"source_{idx}",
        sample_size=100 + idx * 50,
    )


class TestConsolidationStateEnum:
    """Test the ConsolidationState enum itself."""

    def test_all_states_exist(self):
        """All 4 consolidation states are defined."""
        assert ConsolidationState.INITIAL.value == "initial"
        assert ConsolidationState.CONSOLIDATING.value == "consolidating"
        assert ConsolidationState.CONSOLIDATED.value == "consolidated"
        assert ConsolidationState.RECONSOLIDATING.value == "reconsolidating"

    def test_state_values_are_strings(self):
        """State values are strings (compatible with ChromaDB metadata)."""
        for state in ConsolidationState:
            assert isinstance(state.value, str)


class TestConsolidationMetadata:
    """Test that consolidation_state is stored in ChromaDB metadata."""

    def test_new_discovery_has_initial_state(self, memory):
        """Newly recorded discoveries start with INITIAL consolidation state."""
        rec = _make_discovery(memory)
        assert rec is not None

        # Query vector backend to check metadata
        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(
            ids=[drawer_id], include=["metadatas"]
        )
        assert result["ids"]
        meta = result["metadatas"][0]
        assert meta.get("consolidation_state") == "initial"

    def test_consolidation_state_in_metadata_dict(self, memory):
        """_discovery_to_metadata includes consolidation_state field."""
        rec = _make_discovery(memory)
        # Access internal method to verify metadata shape
        from mempalace_agi.palace_discovery_memory import DiscoveryRecord
        meta = memory._discovery_to_metadata(rec.record)
        assert "consolidation_state" in meta
        assert meta["consolidation_state"] == "initial"


class TestConsolidationTransitions:
    """Test state transitions in the consolidation lifecycle."""

    def test_initial_to_consolidating(self, memory):
        """INITIAL → CONSOLIDATING transition works."""
        rec = _make_discovery(memory)
        assert memory.begin_consolidation(rec.id)

        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert result["metadatas"][0]["consolidation_state"] == "consolidating"

    def test_consolidating_to_consolidated(self, memory):
        """CONSOLIDATING → CONSOLIDATED transition works."""
        rec = _make_discovery(memory)
        memory.begin_consolidation(rec.id)
        assert memory.consolidate_discovery(rec.id)

        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert result["metadatas"][0]["consolidation_state"] == "consolidated"

    def test_consolidated_to_reconsolidating(self, memory):
        """CONSOLIDATED → RECONSOLIDATING transition works."""
        rec = _make_discovery(memory)
        memory.begin_consolidation(rec.id)
        memory.consolidate_discovery(rec.id)
        assert memory.trigger_reconsolidation(rec.id, "new contradicting evidence found")

        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        meta = result["metadatas"][0]
        assert meta["consolidation_state"] == "reconsolidating"
        assert meta.get("consolidation_reason") == "new contradicting evidence found"

    def test_reconsolidation_reason_stored(self, memory):
        """Reconsolidation reason is stored in metadata."""
        rec = _make_discovery(memory)
        memory.consolidate_discovery(rec.id)
        memory.trigger_reconsolidation(rec.id, "contradictory p-value from replication")

        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert result["metadatas"][0]["consolidation_reason"] == "contradictory p-value from replication"

    def test_consolidation_updated_at_set(self, memory):
        """consolidation_updated_at is set on state transition."""
        rec = _make_discovery(memory)
        memory.begin_consolidation(rec.id)

        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert "consolidation_updated_at" in result["metadatas"][0]

    def test_nonexistent_discovery_returns_false(self, memory):
        """Transition on nonexistent discovery returns False."""
        assert not memory.begin_consolidation("D9999")
        assert not memory.consolidate_discovery("D9999")
        assert not memory.trigger_reconsolidation("D9999", "test")


class TestGetUnconsolidatedDiscoveries:
    """Test retrieval of unconsolidated discoveries."""

    def test_all_new_discoveries_are_unconsolidated(self, memory):
        """All newly stored discoveries show up as unconsolidated."""
        _make_discovery(memory, 1)
        _make_discovery(memory, 2)
        _make_discovery(memory, 3)

        uncons = memory.get_unconsolidated_discoveries(limit=10)
        assert len(uncons) == 3
        for item in uncons:
            assert item["consolidation_state"] == "initial"

    def test_consolidated_not_in_unconsolidated(self, memory):
        """Consolidated discoveries don't appear in unconsolidated list."""
        rec1 = _make_discovery(memory, 1)
        _make_discovery(memory, 2)

        # Consolidate discovery 1
        memory.consolidate_discovery(rec1.id)

        uncons = memory.get_unconsolidated_discoveries(limit=10)
        ids = [item["discovery_id"] for item in uncons]
        assert rec1.id not in ids

    def test_limit_respected(self, memory):
        """get_unconsolidated_discoveries respects the limit parameter."""
        for i in range(5):
            _make_discovery(memory, i + 1)

        uncons = memory.get_unconsolidated_discoveries(limit=2)
        assert len(uncons) == 2

    def test_sorted_by_timestamp_ascending(self, memory):
        """Results are sorted oldest-first (consolidate oldest discoveries first)."""
        for i in range(3):
            _make_discovery(memory, i + 1)

        uncons = memory.get_unconsolidated_discoveries(limit=10)
        timestamps = [item["timestamp"] for item in uncons]
        assert timestamps == sorted(timestamps)


class TestConsolidationStats:
    """Test consolidation statistics."""

    def test_stats_all_initial(self, memory):
        """Stats reflect all-initial state after fresh discoveries."""
        _make_discovery(memory, 1)
        _make_discovery(memory, 2)
        _make_discovery(memory, 3)

        stats = memory.get_consolidation_stats()
        assert stats["total"] == 3
        assert stats["initial"] == 3
        assert stats["consolidating"] == 0
        assert stats["consolidated"] == 0
        assert stats["reconsolidating"] == 0

    def test_stats_mixed_states(self, memory):
        """Stats correctly count mixed consolidation states."""
        rec1 = _make_discovery(memory, 1)
        rec2 = _make_discovery(memory, 2)
        _make_discovery(memory, 3)

        memory.begin_consolidation(rec1.id)
        memory.consolidate_discovery(rec2.id)

        stats = memory.get_consolidation_stats()
        assert stats["total"] == 3
        assert stats["initial"] == 1
        assert stats["consolidating"] == 1
        assert stats["consolidated"] == 1

    def test_stats_with_reconsolidation(self, memory):
        """Stats count reconsolidating discoveries."""
        rec1 = _make_discovery(memory, 1)
        memory.consolidate_discovery(rec1.id)
        memory.trigger_reconsolidation(rec1.id, "new data")

        stats = memory.get_consolidation_stats()
        assert stats["reconsolidating"] == 1
        assert stats["consolidated"] == 0

    def test_stats_empty_palace(self, memory):
        """Stats work on empty palace."""
        stats = memory.get_consolidation_stats()
        assert stats["total"] == 0
        assert stats["initial"] == 0
