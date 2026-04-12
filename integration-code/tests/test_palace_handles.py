"""Tests for the RLM Context Handle Protocol (palace_handles.py).

Covers: allocate/resolve/invalidate lifecycle, fidelity levels,
stale cleanup, heat scoring, combined scoring, stats, and MCP tools.
"""

import math
import os
import time
from unittest.mock import MagicMock, patch

import pytest

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.palace_handles import (
    HeatMetrics,
    MemoryHandle,
    PalaceHandleManager,
)


# ── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture
def palace_memory(test_config):
    """Create a PalaceDiscoveryMemory with several test discoveries."""
    mem = PalaceDiscoveryMemory(config=test_config)

    # Record a set of discoveries across domains
    mem.record_discovery(
        hypothesis_id="H001",
        domain="Astrophysics",
        finding_type="scaling",
        variables=["mass", "radius"],
        statistic=5.0,
        p_value=0.0001,
        description="Mass-radius power law in exoplanets: R ∝ M^0.27 with scatter 0.12 dex, derived from Kepler DR25 transit photometry sample of 4,000 confirmed planets.",
        data_source="exoplanets",
        sample_size=4000,
    )
    mem.record_discovery(
        hypothesis_id="H002",
        domain="Astrophysics",
        finding_type="correlation",
        variables=["redshift", "luminosity"],
        statistic=3.5,
        p_value=0.001,
        description="Hubble diagram correlation for Type Ia supernovae in the Pantheon+ sample shows a tight distance-redshift relationship consistent with ΛCDM.",
        data_source="pantheon",
    )
    mem.record_discovery(
        hypothesis_id="H003",
        domain="Economics",
        finding_type="scaling",
        variables=["gdp", "population"],
        statistic=4.0,
        p_value=0.005,
        description="GDP scales with population as a power law across nations with exponent 1.15, indicating super-linear scaling consistent with urban economics theory.",
        data_source="worldbank",
    )
    mem.record_discovery(
        hypothesis_id="H004",
        domain="Climate",
        finding_type="anomaly",
        variables=["temperature", "co2"],
        statistic=6.0,
        p_value=0.00001,
        description="Temperature anomaly closely tracks atmospheric CO2 levels over the past 150 years with correlation coefficient r = 0.93 from GISTEMP analysis.",
        data_source="gistemp",
    )
    mem.record_discovery(
        hypothesis_id="H005",
        domain="Epidemiology",
        finding_type="correlation",
        variables=["vaccination_rate", "mortality"],
        statistic=7.0,
        p_value=0.0001,
        description="Vaccination coverage inversely correlates with disease mortality across 50 countries, with a dose-response relationship showing 15% mortality reduction per 10% coverage increase.",
        data_source="who_gho",
        sample_size=50000,
    )
    return mem


@pytest.fixture
def handle_mgr(palace_memory):
    """Create a PalaceHandleManager wrapping the test palace."""
    return PalaceHandleManager(palace_memory=palace_memory)


@pytest.fixture
def handle_mgr_with_kg(palace_memory):
    """Handle manager with a mock KG bridge."""
    mock_kg = MagicMock()
    mock_kg.get_discovery_relationships.return_value = [
        {"subject": "mass", "predicate": "correlated_with", "object": "radius"},
        {"subject": "temperature", "predicate": "causes", "object": "mass"},
    ]
    return PalaceHandleManager(palace_memory=palace_memory, kg_bridge=mock_kg)


# ── Allocate Tests ──────────────────────────────────────────────────────


class TestAllocate:
    """Tests for handle allocation."""

    def test_allocate_returns_handle(self, handle_mgr):
        """Handle has expected structure: handle_id, count, preview with correct fields."""
        handle = handle_mgr.allocate("exoplanet mass radius relationship")

        assert isinstance(handle, MemoryHandle)
        assert handle.handle_id  # non-empty UUID string
        assert handle.count >= 1
        assert handle.query == "exoplanet mass radius relationship"
        assert handle.wing is None
        assert handle.room is None
        assert handle.resolved_fidelity is None
        assert len(handle.resolved_ids) == 0

        # Preview entries have required fields
        for p in handle.preview:
            assert "id" in p
            assert "title" in p
            assert "domain" in p
            assert "confidence" in p
            assert "heat_score" in p
            assert "semantic_similarity" in p
            assert "combined_score" in p

    def test_allocate_with_wing_filter(self, handle_mgr):
        """Wing filter correctly maps to domain and filters results."""
        handle = handle_mgr.allocate(
            "scaling relationship",
            wing="wing_astrophysics",
        )

        # All results should be from Astrophysics domain
        for p in handle.preview:
            assert p["domain"] == "Astrophysics", (
                f"Expected Astrophysics, got {p['domain']}"
            )

    def test_allocate_min_similarity(self, handle_mgr):
        """Results below min_similarity are excluded from the handle."""
        # Very high threshold — should exclude most or all results
        handle_high = handle_mgr.allocate(
            "something totally unrelated to our data",
            min_similarity=0.99,
        )
        # Low threshold — should include more results
        handle_low = handle_mgr.allocate(
            "something totally unrelated to our data",
            min_similarity=0.0,
        )

        assert handle_high.count <= handle_low.count

    def test_allocate_increments_stats(self, handle_mgr):
        """Each allocate increments total_allocations."""
        before = handle_mgr.stats()["total_allocations"]
        handle_mgr.allocate("test query")
        after = handle_mgr.stats()["total_allocations"]
        assert after == before + 1

    def test_allocate_preview_sorted_by_combined_score(self, handle_mgr):
        """Preview entries are sorted by combined_score descending."""
        handle = handle_mgr.allocate("climate temperature co2", n_results=10)
        if len(handle.preview) > 1:
            scores = [p["combined_score"] for p in handle.preview]
            assert scores == sorted(scores, reverse=True)


# ── Resolve Tests ───────────────────────────────────────────────────────


class TestResolve:
    """Tests for handle resolution at different fidelity levels."""

    def test_resolve_meta_fidelity(self, handle_mgr):
        """Meta fidelity returns only id, title, domain, confidence, heat."""
        handle = handle_mgr.allocate("exoplanet mass", n_results=5)
        results = handle_mgr.resolve(handle.handle_id, fidelity="meta")

        assert len(results) >= 1
        for r in results:
            assert "id" in r
            assert "title" in r
            assert "domain" in r
            assert "confidence" in r
            assert "heat_score" in r
            # Meta should NOT contain text or summary
            assert "text" not in r
            assert "summary" not in r
            assert "kg_triples" not in r

    def test_resolve_summary_fidelity(self, handle_mgr):
        """Summary includes 200-char text excerpt + status + cycle."""
        handle = handle_mgr.allocate("exoplanet mass radius", n_results=5)
        results = handle_mgr.resolve(handle.handle_id, fidelity="summary")

        assert len(results) >= 1
        for r in results:
            assert "id" in r
            assert "title" in r
            assert "summary" in r
            assert "status" in r
            assert "cycle" in r
            assert "finding_type" in r
            assert "hypothesis_id" in r
            assert "similarity" in r
            # Summary text should be truncated
            if len(r["summary"]) > 200:
                assert r["summary"].endswith("...")
            # Summary should NOT contain full text or KG triples
            assert "text" not in r
            assert "kg_triples" not in r

    def test_resolve_full_fidelity(self, handle_mgr):
        """Full includes complete text + metadata + KG triples field."""
        handle = handle_mgr.allocate("mass radius power law", n_results=5)
        results = handle_mgr.resolve(handle.handle_id, fidelity="full")

        assert len(results) >= 1
        for r in results:
            assert "id" in r
            assert "title" in r
            assert "text" in r
            assert "similarity" in r
            assert "finding_type" in r
            assert "metadata" in r
            assert "kg_triples" in r  # Present even without KG (empty list)

    def test_resolve_full_with_kg(self, handle_mgr_with_kg):
        """Full fidelity enriches with KG triples when bridge is available."""
        handle = handle_mgr_with_kg.allocate("mass radius", n_results=5)
        results = handle_mgr_with_kg.resolve(handle.handle_id, fidelity="full")

        assert len(results) >= 1
        # At least one result should have KG triples from the mock
        has_triples = any(len(r.get("kg_triples", [])) > 0 for r in results)
        assert has_triples, "Expected KG triples from mock bridge"

    def test_resolve_specific_ids(self, handle_mgr):
        """Only requested IDs are materialized."""
        handle = handle_mgr.allocate("science discovery", n_results=10, min_similarity=0.0)

        if handle.count < 2:
            pytest.skip("Need at least 2 results to test ID filtering")

        # Pick the first ID from preview
        target_id = handle.preview[0]["id"]
        results = handle_mgr.resolve(
            handle.handle_id, fidelity="meta", ids=[target_id]
        )

        assert len(results) == 1
        assert results[0]["id"] == target_id

    def test_resolve_unknown_handle(self, handle_mgr):
        """Raises KeyError for an unknown handle_id."""
        with pytest.raises(KeyError, match="Unknown handle"):
            handle_mgr.resolve("nonexistent-handle-id")

    def test_resolve_invalid_fidelity(self, handle_mgr):
        """Raises ValueError for an invalid fidelity level."""
        handle = handle_mgr.allocate("test query")
        with pytest.raises(ValueError, match="Invalid fidelity"):
            handle_mgr.resolve(handle.handle_id, fidelity="ultra")

    def test_resolve_increments_stats(self, handle_mgr):
        """Each resolve increments total_resolutions."""
        handle = handle_mgr.allocate("test query")
        before = handle_mgr.stats()["total_resolutions"]
        handle_mgr.resolve(handle.handle_id, fidelity="meta")
        after = handle_mgr.stats()["total_resolutions"]
        assert after == before + 1

    def test_resolve_tracks_resolved_ids(self, handle_mgr):
        """Resolved IDs are tracked on the handle."""
        handle = handle_mgr.allocate("mass radius", n_results=5)
        if handle.count == 0:
            pytest.skip("No results")

        handle_mgr.resolve(handle.handle_id, fidelity="meta")

        # All IDs should now be marked as resolved
        assert len(handle.resolved_ids) == handle.count


# ── Invalidate Tests ────────────────────────────────────────────────────


class TestInvalidate:
    """Tests for handle invalidation and lifecycle."""

    def test_invalidate_releases_cache(self, handle_mgr):
        """Handle can't be resolved after invalidation."""
        handle = handle_mgr.allocate("test query")
        handle_mgr.invalidate(handle.handle_id)

        with pytest.raises(KeyError, match="Unknown handle"):
            handle_mgr.resolve(handle.handle_id)

    def test_invalidate_all(self, handle_mgr):
        """invalidate_all releases all handles."""
        handle_mgr.allocate("query 1")
        handle_mgr.allocate("query 2")
        handle_mgr.allocate("query 3")

        assert handle_mgr.stats()["live_handles"] == 3
        released = handle_mgr.invalidate_all()
        assert released == 3
        assert handle_mgr.stats()["live_handles"] == 0

    def test_invalidate_idempotent(self, handle_mgr):
        """Invalidating a non-existent handle is a no-op."""
        handle_mgr.invalidate("does-not-exist")  # Should not raise

    def test_stale_handle_cleanup(self, handle_mgr):
        """Handles older than 5 min are auto-cleaned on next allocate."""
        handle = handle_mgr.allocate("old query")

        # Manually backdate the handle's created_at to make it stale
        handle.created_at = time.time() - 400  # 6+ minutes ago

        assert handle.is_stale

        # Next allocate triggers cleanup
        handle_mgr.allocate("new query")

        # Old handle should be gone
        with pytest.raises(KeyError):
            handle_mgr.resolve(handle.handle_id)

    def test_max_live_handles(self, handle_mgr):
        """Excess handles are evicted (oldest first) when MAX_LIVE_HANDLES exceeded."""
        # Temporarily lower the cap for testing
        original_max = PalaceHandleManager.MAX_LIVE_HANDLES
        PalaceHandleManager.MAX_LIVE_HANDLES = 3

        try:
            h1 = handle_mgr.allocate("query 1")
            h2 = handle_mgr.allocate("query 2")
            h3 = handle_mgr.allocate("query 3")

            assert handle_mgr.stats()["live_handles"] == 3

            # 4th allocation triggers eviction of the oldest
            h4 = handle_mgr.allocate("query 4")

            assert handle_mgr.stats()["live_handles"] <= 3

            # h1 (oldest) should have been evicted
            with pytest.raises(KeyError):
                handle_mgr.resolve(h1.handle_id)

            # h4 (newest) should still be live
            handle_mgr.resolve(h4.handle_id, fidelity="meta")  # should not raise
        finally:
            PalaceHandleManager.MAX_LIVE_HANDLES = original_max


# ── Heat Score Tests ────────────────────────────────────────────────────


class TestHeatScore:
    """Tests for the heat scoring system."""

    def test_heat_score_cold_start(self, handle_mgr):
        """New drawer returns low but non-zero heat (sigmoid of zero accesses)."""
        heat = handle_mgr.compute_heat("cold_drawer")
        assert heat > 0.0, "Cold start should have non-zero heat (sigmoid floor)"
        assert heat < 0.5, "Cold start should be below 0.5"

    def test_heat_score_after_access(self, handle_mgr):
        """Access count increases heat."""
        heat_before = handle_mgr.compute_heat("test_drawer")

        # Simulate accesses
        for _ in range(5):
            handle_mgr._record_access("test_drawer")

        heat_after = handle_mgr.compute_heat("test_drawer")
        assert heat_after > heat_before, "Heat should increase after accesses"

    def test_heat_score_correction_boost(self, handle_mgr):
        """mark_correction adds 0.30 weight to heat score."""
        heat_before = handle_mgr.compute_heat("correction_drawer")
        handle_mgr.mark_correction("correction_drawer")
        heat_after = handle_mgr.compute_heat("correction_drawer")

        # Correction adds 0.30 weight
        assert heat_after > heat_before
        assert heat_after >= heat_before + 0.25, (
            f"Correction boost too small: {heat_after} vs {heat_before}"
        )

    def test_heat_score_bounded(self, handle_mgr):
        """Heat score always in [0, 1]."""
        # Extreme case: many accesses, correction, recent, many edges
        metrics = handle_mgr._get_or_create_metrics("extreme_drawer")
        metrics.access_count = 10000
        metrics.is_correction = True
        metrics.last_accessed = time.time()
        metrics.inbound_edge_count = 10000
        metrics.invalidate_cache()

        heat = handle_mgr.compute_heat("extreme_drawer")
        assert 0.0 <= heat <= 1.0

    def test_heat_score_math(self, handle_mgr):
        """Verify heat formula components independently."""
        # Set up known metrics
        drawer_id = "math_test"
        metrics = handle_mgr._get_or_create_metrics(drawer_id)
        metrics.access_count = 10  # sigmoid(-10/5+2) = sigmoid(0) = 0.5
        metrics.is_correction = False
        metrics.last_accessed = 0  # Never accessed → recency = 0
        metrics.inbound_edge_count = 0
        metrics.invalidate_cache()

        heat = handle_mgr.compute_heat(drawer_id)

        # access_freq = sigmoid(0) = 0.5
        access_component = 0.5 * 0.35
        # is_correction = 0
        # recency = 0
        # inbound_edges: sigmoid(-0/3 + 1) = sigmoid(1) ≈ 0.269 (actually: 1/(1+e^-1) ≈ 0.731... wait)
        # sigmoid(-0/3 + 1) = 1/(1 + e^(-0/3 + 1)) = 1/(1 + e^1) ≈ 0.269
        # Wait: formula is 1/(1 + exp(-edges/3 + 1))
        # edges=0: -0/3 + 1 = 1, so 1/(1+e^1) ≈ 0.269
        # But this is the EXPONENT not in negative form. Let me re-check:
        # The formula is: 1/(1 + exp(-edges/3 + 1))
        # = 1/(1 + exp(1 - edges/3))
        # At edges=0: 1/(1 + exp(1)) ≈ 1/(1+2.718) ≈ 0.269
        inbound_component = (1.0 / (1.0 + math.exp(1.0))) * 0.15

        expected = access_component + inbound_component
        assert abs(heat - expected) < 0.01, f"Expected ~{expected:.4f}, got {heat:.4f}"


# ── Combined Score Tests ────────────────────────────────────────────────


class TestCombinedScore:
    """Tests for preview combined scoring."""

    def test_combined_score_ranking(self, handle_mgr):
        """Preview is sorted by (sim*0.6 + heat*0.4)."""
        handle = handle_mgr.allocate("mass radius correlation", n_results=10, min_similarity=0.0)

        if len(handle.preview) < 2:
            pytest.skip("Need at least 2 results to test ranking")

        # Verify sorting is descending by combined_score
        for i in range(len(handle.preview) - 1):
            assert handle.preview[i]["combined_score"] >= handle.preview[i + 1]["combined_score"]

    def test_combined_score_formula(self, handle_mgr):
        """Verify combined = sim*0.6 + heat*0.4."""
        handle = handle_mgr.allocate("exoplanet mass", n_results=5)

        for p in handle.preview:
            expected = round(p["semantic_similarity"] * 0.6 + p["heat_score"] * 0.4, 4)
            assert abs(p["combined_score"] - expected) < 0.001, (
                f"Combined score mismatch: {p['combined_score']} != {expected}"
            )


# ── Stats Tests ─────────────────────────────────────────────────────────


class TestStats:
    """Tests for handle manager statistics."""

    def test_stats_tracking(self, handle_mgr):
        """Allocation/resolution/savings counters work."""
        # Initial state
        s = handle_mgr.stats()
        assert s["live_handles"] == 0
        assert s["total_allocations"] == 0
        assert s["total_resolutions"] == 0

        # After allocate
        handle = handle_mgr.allocate("test")
        s = handle_mgr.stats()
        assert s["live_handles"] == 1
        assert s["total_allocations"] == 1

        # After resolve
        handle_mgr.resolve(handle.handle_id, fidelity="meta")
        s = handle_mgr.stats()
        assert s["total_resolutions"] == 1

        # After invalidate
        handle_mgr.invalidate(handle.handle_id)
        s = handle_mgr.stats()
        assert s["live_handles"] == 0

    def test_savings_ratio(self, handle_mgr):
        """Unresolved docs counted as avoided in savings_ratio."""
        handle = handle_mgr.allocate(
            "mass radius scaling",
            n_results=10,
            min_similarity=0.0,
        )

        if handle.count < 2:
            pytest.skip("Need at least 2 results to test savings")

        # Resolve only 1 document
        target_id = handle.preview[0]["id"]
        handle_mgr.resolve(handle.handle_id, fidelity="meta", ids=[target_id])

        # Invalidate → remaining docs become "avoided"
        handle_mgr.invalidate(handle.handle_id)

        s = handle_mgr.stats()
        assert s["total_docs_avoided"] == handle.count - 1
        assert s["savings_ratio"] > 0.0


# ── MemoryHandle Properties Tests ───────────────────────────────────────


class TestMemoryHandle:
    """Tests for the MemoryHandle dataclass."""

    def test_age_seconds(self):
        """age_seconds reflects time since creation."""
        h = MemoryHandle(
            handle_id="test",
            query="q",
            wing=None,
            room=None,
            count=0,
            preview=[],
            created_at=time.time() - 10.0,
        )
        assert h.age_seconds >= 10.0

    def test_is_stale(self):
        """Handles older than 5 min are stale."""
        fresh = MemoryHandle(
            handle_id="fresh",
            query="q",
            wing=None,
            room=None,
            count=0,
            preview=[],
            created_at=time.time(),
        )
        stale = MemoryHandle(
            handle_id="stale",
            query="q",
            wing=None,
            room=None,
            count=0,
            preview=[],
            created_at=time.time() - 301,
        )
        assert not fresh.is_stale
        assert stale.is_stale

    def test_repr(self):
        """repr is readable."""
        h = MemoryHandle(
            handle_id="abcdef12-3456-7890-abcd-ef1234567890",
            query="exoplanet mass radius",
            wing=None,
            room=None,
            count=5,
            preview=[],
            created_at=time.time(),
        )
        r = repr(h)
        assert "abcdef12" in r
        assert "count=5" in r


# ── HeatMetrics Tests ──────────────────────────────────────────────────


class TestHeatMetrics:
    """Tests for the HeatMetrics dataclass."""

    def test_invalidate_cache(self):
        """invalidate_cache clears the cached score."""
        m = HeatMetrics(drawer_id="test")
        m._cached_score = 0.5
        m.invalidate_cache()
        assert m._cached_score is None


# ── MCP Tool Tests ──────────────────────────────────────────────────────


class TestMCPTools:
    """Tests for the MCP tool integration (palace_allocate, palace_resolve, palace_heat_scores)."""

    def _build_mcp_server(self, palace_memory, handle_mgr):
        """Build an MCP server with handle manager wired in."""
        from mempalace_agi.unified_mcp_server import UnifiedMCPServer

        # Create mock engine
        mock_engine = MagicMock()
        mock_engine.cycle_count = 0
        mock_engine.store.active.return_value = []
        mock_engine.system_confidence = 0.5

        mock_kg = MagicMock()
        mock_specialist = MagicMock()
        config = palace_memory.config

        server = UnifiedMCPServer(
            palace_memory=palace_memory,
            engine=mock_engine,
            kg_bridge=mock_kg,
            specialist_manager=mock_specialist,
            config=config,
            handle_mgr=handle_mgr,
        )
        return server

    @pytest.mark.asyncio
    async def test_mcp_allocate_tool(self, palace_memory, handle_mgr):
        """MCP palace_allocate tool returns handle with expected fields."""
        server = self._build_mcp_server(palace_memory, handle_mgr)

        request = {
            "method": "tools/call",
            "params": {
                "name": "palace_allocate",
                "arguments": {
                    "query": "exoplanet mass radius",
                },
            },
            "id": 1,
        }
        response = await server.handle_request(request)

        assert response is not None
        assert "result" in response
        content = response["result"]["content"]
        assert len(content) == 1

        import json
        data = json.loads(content[0]["text"])
        assert "handle_id" in data
        assert "count" in data
        assert "preview" in data
        assert isinstance(data["preview"], list)

    @pytest.mark.asyncio
    async def test_mcp_resolve_tool(self, palace_memory, handle_mgr):
        """MCP palace_resolve tool returns memories at requested fidelity."""
        server = self._build_mcp_server(palace_memory, handle_mgr)

        # First allocate
        alloc_request = {
            "method": "tools/call",
            "params": {
                "name": "palace_allocate",
                "arguments": {"query": "exoplanet mass"},
            },
            "id": 1,
        }
        alloc_response = await server.handle_request(alloc_request)

        import json
        alloc_data = json.loads(alloc_response["result"]["content"][0]["text"])
        handle_id = alloc_data["handle_id"]

        # Then resolve
        resolve_request = {
            "method": "tools/call",
            "params": {
                "name": "palace_resolve",
                "arguments": {
                    "handle_id": handle_id,
                    "fidelity": "summary",
                },
            },
            "id": 2,
        }
        resolve_response = await server.handle_request(resolve_request)

        assert "result" in resolve_response
        resolve_data = json.loads(resolve_response["result"]["content"][0]["text"])
        assert resolve_data["fidelity"] == "summary"
        assert "count" in resolve_data
        assert "memories" in resolve_data

    @pytest.mark.asyncio
    async def test_mcp_heat_scores_tool(self, palace_memory, handle_mgr):
        """MCP palace_heat_scores tool returns valid scores."""
        server = self._build_mcp_server(palace_memory, handle_mgr)

        request = {
            "method": "tools/call",
            "params": {
                "name": "palace_heat_scores",
                "arguments": {
                    "drawer_ids": ["discovery_D0001", "discovery_D0002"],
                },
            },
            "id": 1,
        }
        response = await server.handle_request(request)

        import json
        data = json.loads(response["result"]["content"][0]["text"])
        assert "scores" in data
        assert "formula" in data
        assert "discovery_D0001" in data["scores"]
        assert "discovery_D0002" in data["scores"]

    @pytest.mark.asyncio
    async def test_mcp_tools_listed(self, palace_memory, handle_mgr):
        """The 3 new handle tools appear in tools/list."""
        server = self._build_mcp_server(palace_memory, handle_mgr)

        request = {"method": "tools/list", "params": {}, "id": 1}
        response = await server.handle_request(request)

        tool_names = [t["name"] for t in response["result"]["tools"]]
        assert "palace_allocate" in tool_names
        assert "palace_resolve" in tool_names
        assert "palace_heat_scores" in tool_names
