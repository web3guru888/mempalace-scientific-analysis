"""
Tests for HNSW index safety (ChromaDB bugs #521 / #525 mitigation).

Verifies that PalaceDiscoveryMemory uses the delete-then-add pattern
(``_safe_upsert``) instead of ``collection.upsert()`` to avoid the
``repairConnectionsForUpdate`` codepath in hnswlib that causes:

- #525: unbounded link_lists.bin growth on add() with existing IDs
- #521: race condition segfaults on upsert() with existing IDs

The fix (from PR #523): always ``delete()`` before ``add()`` so
HNSW only sees pure inserts.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.config import IntegrationConfig


@pytest.fixture
def memory(test_config):
    """Fresh PalaceDiscoveryMemory instance for each test."""
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


# ── Helper: record a discovery and return the result ─────────────────

# Each entry is a fully distinct discovery to avoid hard-duplicate rejection.
_DISTINCT_DISCOVERIES = [
    {
        "hypothesis_id": "H001",
        "domain": "Astrophysics",
        "finding_type": "correlation",
        "variables": ["redshift", "luminosity"],
        "statistic": 3.45,
        "p_value": 0.001,
        "description": "Strong correlation between redshift and luminosity in SDSS quasars",
        "data_source": "sdss",
    },
    {
        "hypothesis_id": "H002",
        "domain": "Economics",
        "finding_type": "trend",
        "variables": ["gdp_growth", "unemployment_rate"],
        "statistic": -2.10,
        "p_value": 0.023,
        "description": "Inverse trend between GDP growth and unemployment across OECD countries",
        "data_source": "world_bank",
    },
    {
        "hypothesis_id": "H003",
        "domain": "Climate",
        "finding_type": "scaling",
        "variables": ["co2_concentration", "global_temperature"],
        "statistic": 4.87,
        "p_value": 0.0001,
        "description": "Logarithmic scaling of global temperature anomaly with CO2 concentration",
        "data_source": "noaa",
    },
    {
        "hypothesis_id": "H004",
        "domain": "Epidemiology",
        "finding_type": "causal",
        "variables": ["vaccination_rate", "infection_incidence"],
        "statistic": -5.32,
        "p_value": 0.00005,
        "description": "Vaccination rate causally reduces infection incidence in population studies",
        "data_source": "who",
    },
]


def _record(memory, idx=1, domain=None, hyp=None):
    """Record a distinct discovery and return the RecordResult.

    Uses pre-defined maximally-distinct discoveries to avoid false hard-
    duplicate detection.  ``idx`` selects which template (1-based, wraps).
    """
    template = _DISTINCT_DISCOVERIES[(idx - 1) % len(_DISTINCT_DISCOVERIES)].copy()
    if domain is not None:
        template["domain"] = domain
    if hyp is not None:
        template["hypothesis_id"] = hyp
    return memory.record_discovery(
        **template,
        sample_size=500 + idx,
        effect_size=0.3 + idx * 0.01,
    )


# ═══════════════════════════════════════════════════════════════════════
# 1. Core _safe_upsert mechanics
# ═══════════════════════════════════════════════════════════════════════

class TestSafeUpsertCore:
    """Low-level tests for the _safe_upsert helper method."""

    def test_safe_upsert_new_document(self, memory):
        """Inserting a brand-new document via _safe_upsert works."""
        memory._safe_upsert(
            ids=["test_new_1"],
            documents=["Hello world"],
            metadatas=[{"record_type": "test"}],
        )

        result = memory._backend.get(ids=["test_new_1"])
        assert result["ids"] == ["test_new_1"]
        assert result["documents"] == ["Hello world"]

    def test_safe_upsert_update_existing(self, memory):
        """Updating an existing document doesn't crash (the key bug).

        With raw ``upsert()`` this would trigger repairConnectionsForUpdate
        in hnswlib, potentially causing segfaults or link_lists.bin bloat.
        The delete-then-add pattern avoids this codepath entirely.
        """
        # First insert
        memory._safe_upsert(
            ids=["test_update_1"],
            documents=["Version 1"],
            metadatas=[{"record_type": "test", "version": 1}],
        )

        # Update same ID — this is the dangerous path with raw upsert()
        memory._safe_upsert(
            ids=["test_update_1"],
            documents=["Version 2"],
            metadatas=[{"record_type": "test", "version": 2}],
        )

        result = memory._backend.get(
            ids=["test_update_1"],
            include=["documents", "metadatas"],
        )
        assert result["ids"] == ["test_update_1"]
        assert result["documents"] == ["Version 2"]
        assert result["metadatas"][0]["version"] == 2

        # Only one document should exist — no ghosts
        assert memory._backend.count() == 1

    def test_safe_upsert_batch(self, memory):
        """Batch operations work correctly with _safe_upsert."""
        ids = [f"batch_{i}" for i in range(5)]
        docs = [f"Document {i}" for i in range(5)]
        metas = [{"record_type": "test", "idx": i} for i in range(5)]

        # First batch insert
        memory._safe_upsert(ids=ids, documents=docs, metadatas=metas)
        assert memory._backend.count() == 5

        # Update the same batch — should not duplicate or corrupt
        updated_docs = [f"Updated document {i}" for i in range(5)]
        memory._safe_upsert(ids=ids, documents=updated_docs, metadatas=metas)
        assert memory._backend.count() == 5

        # Verify contents were updated
        result = memory._backend.get(ids=["batch_2"], include=["documents"])
        assert result["documents"] == ["Updated document 2"]


# ═══════════════════════════════════════════════════════════════════════
# 2. Integration: discovery recording
# ═══════════════════════════════════════════════════════════════════════

class TestDiscoveryRecordingSafety:
    """Verify that discovery storage paths use the safe HNSW pattern."""

    def test_record_discovery_double_store(self, memory):
        """Recording the same discovery twice doesn't corrupt the HNSW index.

        The second call goes through the upstream fingerprint dedup and may
        return None, but if it does store, the palace side must use the
        delete-then-add pattern.
        """
        rec1 = _record(memory, idx=1)
        assert rec1 is not None
        assert rec1.id == "D0001"

        # Record a second *different* discovery
        rec2 = _record(memory, idx=2)
        assert rec2 is not None
        assert rec2.id == "D0002"

        palace_count = memory._backend.count()
        assert palace_count >= 2  # At least both discoveries stored

        # Now manually re-store the first discovery's drawer ID
        # (simulating a restart sync scenario)
        drawer_id = f"discovery_{rec1.id}"
        memory._safe_upsert(
            ids=[drawer_id],
            documents=["Re-stored discovery"],
            metadatas=[{"record_type": "discovery", "discovery_id": rec1.id}],
        )

        # Count should not have increased by more than what we expect
        # (no ghost entries from failed HNSW updates)
        final_count = memory._backend.count()
        assert final_count == palace_count  # Same count — no duplicates


# ═══════════════════════════════════════════════════════════════════════
# 3. Status updates
# ═══════════════════════════════════════════════════════════════════════

class TestStatusUpdateSafety:
    """Verify update_discovery_status uses the safe HNSW path."""

    def test_update_discovery_status_safe(self, memory):
        """Status update on an existing discovery uses delete-then-add."""
        rec = _record(memory, idx=1)
        assert rec is not None

        # Update status
        result = memory.update_discovery_status(rec.id, "decided")
        assert result is True

        # Verify the status was actually updated in ChromaDB
        drawer_id = f"discovery_{rec.id}"
        fetched = memory._backend.get(
            ids=[drawer_id], include=["metadatas"]
        )
        assert fetched["ids"] == [drawer_id]
        assert fetched["metadatas"][0]["status"] == "decided"

        # Update status again — second update on same ID
        result2 = memory.update_discovery_status(rec.id, "rejected")
        assert result2 is True

        fetched2 = memory._backend.get(
            ids=[drawer_id], include=["metadatas"]
        )
        assert fetched2["metadatas"][0]["status"] == "rejected"

        # No ghost entries
        count_after = memory._backend.count()
        # Should be exactly 1 discovery drawer (+ possibly method outcomes)
        discovery_results = memory._backend.get(
            where={"record_type": "discovery"},
            include=["metadatas"],
        )
        assert len(discovery_results["ids"]) == 1


# ═══════════════════════════════════════════════════════════════════════
# 4. Diary writes
# ═══════════════════════════════════════════════════════════════════════

class TestDiaryWriteSafety:
    """Verify diary_write is idempotent without HNSW corruption."""

    def test_diary_write_idempotent(self, memory):
        """Writing the same diary entry twice doesn't corrupt the index.

        diary_write uses a content-based deterministic ID, so the second
        write hits the same drawer_id and must use delete-then-add.
        """
        entry = "Today I discovered that galaxy rotation curves suggest dark matter."

        doc_id1 = memory.diary_write("astro_agent", entry, topic="observations")
        count_after_first = memory._backend.count()

        # Write exact same entry again — same content hash → same ID
        doc_id2 = memory.diary_write("astro_agent", entry, topic="observations")
        count_after_second = memory._backend.count()

        # IDs should be identical (deterministic)
        assert doc_id1 == doc_id2

        # Count should not increase — delete-then-add is idempotent
        assert count_after_second == count_after_first

        # Content should still be readable
        result = memory._backend.get(ids=[doc_id1], include=["documents"])
        assert result["documents"] == [entry]


# ═══════════════════════════════════════════════════════════════════════
# 5. Startup sync safety
# ═══════════════════════════════════════════════════════════════════════

class TestSyncExistingSafety:
    """Verify _sync_existing_to_palace uses the safe HNSW path."""

    def test_sync_existing_safe(self, test_config):
        """Syncing existing discoveries on startup doesn't corrupt HNSW.

        Simulates a restart: create a memory instance, record some data,
        then create a NEW instance pointed at the same databases.  The
        second instance's _sync_existing_to_palace must safely re-insert.
        """
        # First instance — record some discoveries
        mem1 = PalaceDiscoveryMemory(config=test_config, max_records=100)
        _record(mem1, idx=1)
        _record(mem1, idx=2)
        _record(mem1, idx=3)

        count_before = mem1._backend.count()
        assert count_before >= 3

        # Delete palace data to force a re-sync (simulating a palace rebuild)
        # We keep the SQLite data intact.
        import shutil
        palace_path = test_config.palace_path
        shutil.rmtree(palace_path, ignore_errors=True)

        # Second instance — this triggers _sync_existing_to_palace
        mem2 = PalaceDiscoveryMemory(config=test_config, max_records=100)

        # All discoveries should be re-synced via _safe_upsert
        count_after = mem2._backend.count()
        assert count_after >= 3

        # Verify semantic search still works after re-sync
        results = mem2.semantic_search("discovery", n_results=10)
        assert len(results) >= 3


# ═══════════════════════════════════════════════════════════════════════
# 6. Verify no raw upsert() calls remain
# ═══════════════════════════════════════════════════════════════════════

class TestNoRawUpsert:
    """Source-level check: no direct collection.upsert() calls in prod code."""

    def test_no_raw_upsert_in_source(self):
        """The source file must not contain direct collection.upsert() calls.

        All upsert paths must go through _safe_upsert() to avoid HNSW
        corruption (ChromaDB #521 / #525).
        """
        import inspect
        from mempalace_agi import palace_discovery_memory as mod

        source = inspect.getsource(mod)

        # Find all lines with .upsert( — should only appear in:
        #   1. The docstring of _safe_upsert (explaining what we replaced)
        #   2. Comments
        import re
        upsert_calls = []
        for i, line in enumerate(source.splitlines(), 1):
            stripped = line.strip()
            # Skip comments and docstrings
            if stripped.startswith("#") or stripped.startswith('"""') or stripped.startswith("'''"):
                continue
            if stripped.startswith("``") or "``upsert()``" in stripped or "``collection.upsert()``" in stripped:
                continue
            # Look for actual method calls: .upsert(
            # Allow: _safe_upsert (our wrapper) and _backend.upsert (the
            # backend's own upsert, which encapsulates the HNSW workaround)
            if ".upsert(" in stripped and "_safe_upsert" not in stripped and "_backend.upsert" not in stripped:
                upsert_calls.append((i, stripped))

        assert upsert_calls == [], (
            f"Found raw .upsert() calls that should use _safe_upsert():\n"
            + "\n".join(f"  line {n}: {l}" for n, l in upsert_calls)
        )
