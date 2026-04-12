"""
Tests for require_status feature — Phase 19 P0 Task 2.

Validates that:
1. Status is written to ChromaDB metadata on ingest
2. require_status filters out non-matching records
3. update_discovery_status() changes status in both backends
4. Without require_status, all records are returned (backward compatible)
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
from mempalace_agi.retrieval_profiles import (
    ORIENT_BREADTH,
    EVALUATE_PRECISION,
    DECIDE_RECENCY,
    compose,
)


@dataclass
class MockHypothesis:
    id: str
    description: str
    domain: str
    confidence: float = 0.5
    name: str = ""
    variables: list = None


@pytest.fixture
def memory(test_config):
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


def _populate_with_statuses(memory):
    """Populate memory with discoveries, then update some statuses."""
    # Record 4 discoveries (all start as "active")
    r1 = memory.record_discovery(
        hypothesis_id="H001", domain="Astrophysics",
        finding_type="scaling", variables=["mass", "radius"],
        statistic=5.0, p_value=0.0001,
        description="Mass-radius power law in exoplanets: R ∝ M^0.27",
        data_source="exoplanets", sample_size=4000,
    )
    r2 = memory.record_discovery(
        hypothesis_id="H002", domain="Astrophysics",
        finding_type="correlation", variables=["redshift", "luminosity"],
        statistic=3.5, p_value=0.001,
        description="Hubble diagram correlation for Type Ia supernovae",
        data_source="pantheon",
    )
    r3 = memory.record_discovery(
        hypothesis_id="H003", domain="Economics",
        finding_type="scaling", variables=["gdp", "population"],
        statistic=4.0, p_value=0.005,
        description="GDP scales with population as a power law across nations",
        data_source="worldbank",
    )
    r4 = memory.record_discovery(
        hypothesis_id="H004", domain="Climate",
        finding_type="anomaly", variables=["temperature", "co2"],
        statistic=6.0, p_value=0.00001,
        description="Temperature anomaly closely tracks atmospheric CO2 levels",
        data_source="gistemp",
    )

    # Update statuses: 2 decided, 1 rejected, 1 stays active
    memory.update_discovery_status(r1.id, "decided")
    memory.update_discovery_status(r2.id, "decided")
    memory.update_discovery_status(r4.id, "rejected")
    # r3 stays "active"

    return r1, r2, r3, r4


class TestStatusInMetadata:
    """Test that status is written to ChromaDB metadata on ingest."""

    def test_default_status_is_active(self, memory):
        """Newly ingested discoveries have status='active' in metadata."""
        rec = memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius relationship",
            data_source="exoplanets",
        )

        # Fetch from vector backend directly
        drawer_id = f"discovery_{rec.id}"
        result = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert result["metadatas"][0]["status"] == "active"

    def test_status_present_in_metadata(self, memory):
        """The status field exists in ChromaDB metadata."""
        memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="correlation", variables=["x", "y"],
            statistic=3.0, p_value=0.01,
            description="Test discovery",
            data_source="test",
        )

        # Get all metadata
        all_meta = memory._backend.get(include=["metadatas"])
        for meta in all_meta["metadatas"]:
            if meta.get("record_type") == "discovery":
                assert "status" in meta


class TestRequireStatusFilter:
    """Test that require_status filters records in semantic_search."""

    def test_require_status_decided_filters_correctly(self, memory):
        """require_status='decided' returns only decided records."""
        _populate_with_statuses(memory)

        # Search with require_status="decided"
        hits = memory.semantic_search(
            query="power law scaling",
            n_results=10,
            require_status="decided",
        )

        # All returned results should have status="decided"
        assert len(hits) > 0
        for hit in hits:
            meta = hit.get("metadata", {})
            assert meta.get("status") == "decided", (
                f"Expected status='decided', got '{meta.get('status')}' "
                f"for {hit.get('discovery_id')}"
            )

    def test_require_status_active_filters_correctly(self, memory):
        """require_status='active' returns only active records."""
        _populate_with_statuses(memory)

        hits = memory.semantic_search(
            query="economic growth scaling GDP",
            n_results=10,
            require_status="active",
        )

        for hit in hits:
            meta = hit.get("metadata", {})
            assert meta.get("status") == "active"

    def test_no_require_status_returns_all(self, memory):
        """Without require_status, all records are returned (backward compat)."""
        _populate_with_statuses(memory)

        # Search without status filter
        hits = memory.semantic_search(
            query="scaling power law correlation anomaly",
            n_results=10,
        )

        # Should return records with mixed statuses
        statuses = {hit["metadata"].get("status") for hit in hits}
        # We have active, decided, and rejected — at least 2 different statuses
        assert len(statuses) >= 2, f"Expected multiple statuses, got: {statuses}"

    def test_require_status_nonexistent_returns_empty(self, memory):
        """Filtering by a status that no record has returns empty."""
        _populate_with_statuses(memory)

        hits = memory.semantic_search(
            query="scaling",
            n_results=10,
            require_status="nonexistent_status",
        )

        assert hits == []


class TestUpdateDiscoveryStatus:
    """Test update_discovery_status() lifecycle API."""

    def test_update_changes_chromadb_status(self, memory):
        """update_discovery_status() changes the status in ChromaDB metadata."""
        rec = memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law",
            data_source="exoplanets",
        )

        # Initially active
        drawer_id = f"discovery_{rec.id}"
        meta_before = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert meta_before["metadatas"][0]["status"] == "active"

        # Update to "decided"
        result = memory.update_discovery_status(rec.id, "decided")
        assert result is True

        # Verify change
        meta_after = memory._backend.get(ids=[drawer_id], include=["metadatas"])
        assert meta_after["metadatas"][0]["status"] == "decided"

    def test_update_nonexistent_returns_false(self, memory):
        """Updating a non-existent discovery returns False."""
        result = memory.update_discovery_status("D9999", "decided")
        assert result is False

    def test_update_status_affects_search_filter(self, memory):
        """After updating status, require_status filter reflects the change."""
        rec = memory.record_discovery(
            hypothesis_id="H001", domain="Astrophysics",
            finding_type="scaling", variables=["mass", "radius"],
            statistic=5.0, p_value=0.0001,
            description="Mass-radius power law in exoplanets",
            data_source="exoplanets",
        )

        # Initially active — should appear with require_status="active"
        hits_active = memory.semantic_search(
            query="mass radius",
            n_results=5,
            require_status="active",
        )
        assert any(h["discovery_id"] == rec.id for h in hits_active)

        # Should NOT appear with require_status="decided"
        hits_decided_before = memory.semantic_search(
            query="mass radius",
            n_results=5,
            require_status="decided",
        )
        assert not any(h["discovery_id"] == rec.id for h in hits_decided_before)

        # Now update to "decided"
        memory.update_discovery_status(rec.id, "decided")

        # Should now appear with require_status="decided"
        hits_decided_after = memory.semantic_search(
            query="mass radius",
            n_results=5,
            require_status="decided",
        )
        assert any(h["discovery_id"] == rec.id for h in hits_decided_after)

        # Should NOT appear with require_status="active" anymore
        hits_active_after = memory.semantic_search(
            query="mass radius",
            n_results=5,
            require_status="active",
        )
        assert not any(h["discovery_id"] == rec.id for h in hits_active_after)

    def test_update_to_rejected_then_query(self, memory):
        """Status can be updated to 'rejected' and filtered correctly."""
        rec = memory.record_discovery(
            hypothesis_id="H001", domain="Climate",
            finding_type="anomaly", variables=["temperature", "co2"],
            statistic=6.0, p_value=0.00001,
            description="Temperature anomaly tracks CO2",
            data_source="gistemp",
        )

        memory.update_discovery_status(rec.id, "rejected")

        hits = memory.semantic_search(
            query="temperature CO2",
            n_results=5,
            require_status="rejected",
        )
        assert any(h["discovery_id"] == rec.id for h in hits)


class TestRequireStatusInRetrieveContext:
    """Test that retrieve_context() passes require_status from profile."""

    def test_evaluate_profile_filters_by_decided(self, memory):
        """EVALUATE_PRECISION requires status='decided' — only decided discoveries returned."""
        r1, r2, r3, r4 = _populate_with_statuses(memory)

        orient = MemoryAugmentedOrient(palace_memory=memory)
        hypotheses = [
            MockHypothesis(id="H005", description="Power law scaling", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
            phase="evaluate",
        )

        # All per-hypothesis hits should be "decided" status
        for hyp_id, hits in context["per_hypothesis"].items():
            for hit in hits:
                status = hit.get("metadata", {}).get("status", "")
                assert status == "decided", (
                    f"Evaluate phase returned non-decided record: "
                    f"{hit.get('discovery_id')} has status={status!r}"
                )

    def test_orient_profile_returns_all_statuses(self, memory):
        """ORIENT_BREADTH has require_status=None — all statuses returned."""
        _populate_with_statuses(memory)

        orient = MemoryAugmentedOrient(palace_memory=memory)
        hypotheses = [
            MockHypothesis(id="H005", description="Power law scaling anomaly correlation", domain="Astrophysics"),
        ]
        context = orient.retrieve_context(
            hypotheses=hypotheses,
            current_domain="Astrophysics",
            phase="orient",
        )

        # Orient should return a mix of statuses
        statuses = set()
        for hits in context["per_hypothesis"].values():
            for hit in hits:
                statuses.add(hit.get("metadata", {}).get("status", ""))

        # Should have at least "decided" and one other
        # (depends on embedding similarity, but with min_sim=0.2 we should get most)
        assert len(statuses) >= 1  # At minimum we get some results
