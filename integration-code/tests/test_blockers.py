"""
Tests for the 5 blocker fixes required for full autonomous discovery mode.

Blocker 1: Cosmology monkey-patch (Om/Ol → Omega_m/Omega_L)
Blocker 2: KG Bridge wiring to engine discoveries
Blocker 3: Continuous discovery loop (start/stop/get_status)
Blocker 4: ChromaDB stale collection recovery
Blocker 5: Wikidata timeout configuration
"""

import json
import os
import tempfile
import threading
import time

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass, field, asdict

from mempalace_agi.config import IntegrationConfig
from mempalace_agi.orchestrator import MemPalaceAGI, _patch_cosmology


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def tmp_config():
    d = tempfile.mkdtemp(prefix="mempalace_blocker_test_")
    c = IntegrationConfig(
        palace_path=os.path.join(d, "palace"),
        kg_db_path=os.path.join(d, "kg.sqlite3"),
        discovery_db_path=os.path.join(d, "discoveries.db"),
    )
    yield c
    import shutil
    shutil.rmtree(d, ignore_errors=True)


def _make_mock_engine(discoveries=None, hypotheses=None):
    """Create a mock engine with controllable discoveries and hypotheses."""
    engine = MagicMock()
    engine.cycle_count = 0

    # Configure store
    active_hyps = hypotheses or []
    engine.store.active.return_value = active_hyps
    engine.store.all_hypotheses.return_value = active_hyps
    engine.current_domain = "Astrophysics"

    # Configure discovery_memory (will be replaced by PalaceDiscoveryMemory)
    engine.discovery_memory = None

    # Make run_cycle increment and call phases
    def run_cycle():
        engine.cycle_count += 1
        engine.orient()
        engine.select()
        engine.investigate()
        engine.evaluate()
        engine.update()

    engine.run_cycle.side_effect = run_cycle

    return engine


def _make_hypothesis(hyp_id="H001", test_results=None):
    """Create a mock hypothesis with test results."""
    hyp = Mock()
    hyp.id = hyp_id
    hyp.description = f"Test hypothesis {hyp_id}"
    hyp.memory_context = []
    hyp.memory_score_boost = 0.0
    hyp.test_results = test_results or []
    return hyp


# ══════════════════════════════════════════════════════════════════════
# Blocker 1: Cosmology Monkey-Patch
# ══════════════════════════════════════════════════════════════════════

class TestCosmologyPatch:
    """Test that the distance_modulus monkey-patch fixes Om/Ol keys."""

    def test_patch_applied(self):
        """Verify the patch was applied at module load."""
        try:
            import astra_live_backend.engine as eng_mod
            from astra_live_backend.cosmology import distance_modulus as orig

            # The patched function should differ from the original
            # (it wraps it with key mapping)
            assert eng_mod.distance_modulus is not orig
        except ImportError:
            pytest.skip("ASTRA engine not available")

    def test_patch_maps_Om_to_Omega_m(self):
        """The patched function should accept Om/Ol keys."""
        try:
            import astra_live_backend.engine as eng_mod
            import numpy as np

            # This should NOT raise KeyError anymore
            result = eng_mod.distance_modulus(
                np.array([0.01, 0.1]),
                {"H0": 70.0, "Om": 0.3, "Ol": 0.7},
            )
            assert result is not None
            assert len(result) == 2
            assert all(np.isfinite(result))
        except ImportError:
            pytest.skip("ASTRA engine not available")

    def test_patch_preserves_full_cosmo(self):
        """The patch should pass through full Planck-style dicts unchanged."""
        try:
            import astra_live_backend.engine as eng_mod
            from astra_live_backend.cosmology import PLANCK_2018
            import numpy as np

            result = eng_mod.distance_modulus(
                np.array([0.1]),
                PLANCK_2018.copy(),
            )
            assert result is not None
            assert len(result) == 1
            assert np.isfinite(result[0])
        except ImportError:
            pytest.skip("ASTRA engine not available")

    def test_patch_handles_none_cosmo(self):
        """The patch should work with cosmo=None (uses PLANCK_2018 defaults)."""
        try:
            import astra_live_backend.engine as eng_mod
            import numpy as np

            result = eng_mod.distance_modulus(np.array([0.1]), None)
            assert result is not None
            assert np.isfinite(result[0])
        except ImportError:
            pytest.skip("ASTRA engine not available")


# ══════════════════════════════════════════════════════════════════════
# Blocker 2: KG Bridge Wiring to Engine Discoveries
# ══════════════════════════════════════════════════════════════════════

class TestKGBridgeWiring:
    """Test that discoveries are properly synced to the KG after evaluate."""

    def test_discoveries_synced_to_kg_after_cycle(self, tmp_config):
        """After a cycle with discoveries, KG should have triples."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        # Record some discoveries before running a cycle
        agi.palace_memory.record_discovery(
            hypothesis_id="H001",
            domain="Astrophysics",
            finding_type="correlation",
            variables=["orbital_period", "planet_mass"],
            statistic=0.95,
            p_value=0.001,
            description="Orbital period correlates with planet mass",
            data_source="exoplanets",
            effect_size=0.7,
        )

        # Run a cycle — evaluate should sync discoveries to KG
        agi.run_augmented_cycle()

        stats = agi.kg_bridge.stats()
        assert stats["total_triples"] > 0, "KG should have triples after cycle"
        assert stats["total_entities"] > 0, "KG should have entities after cycle"

    def test_variable_triples_extracted(self, tmp_config):
        """Variable-to-variable triples should be created from discoveries."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.palace_memory.record_discovery(
            hypothesis_id="H001",
            domain="Astrophysics",
            finding_type="scaling",
            variables=["log_period", "log_sma"],
            statistic=0.98,
            p_value=0.0001,
            description="Period scales with semi-major axis (Kepler's 3rd)",
            data_source="exoplanets",
        )

        agi.run_augmented_cycle()

        # Check that variable relationship triples exist
        stats = agi.kg_bridge.stats()
        assert stats["total_triples"] >= 2  # At least produced_by + variable link

    def test_multiple_discoveries_synced(self, tmp_config):
        """Multiple discoveries should all get synced."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        # Record 3 discoveries in different domains
        for i, (domain, ft, vars_) in enumerate([
            ("Astrophysics", "correlation", ["redshift", "distance_modulus"]),
            ("Economics", "trend", ["gdp", "inflation"]),
            ("Climate", "anomaly", ["temp_anomaly", "co2_level"]),
        ]):
            agi.palace_memory.record_discovery(
                hypothesis_id=f"H{i+1:03d}",
                domain=domain,
                finding_type=ft,
                variables=vars_,
                statistic=0.8 + i * 0.05,
                p_value=0.01,
                description=f"Test discovery {i+1}",
                data_source="test",
            )

        agi.run_augmented_cycle()

        stats = agi.kg_bridge.stats()
        # Each discovery generates: produced_by + belongs_to_domain + 2 involves_variable + 1 variable triple = ~5
        assert stats["total_triples"] >= 9, (
            f"Expected ≥9 triples for 3 discoveries, got {stats['total_triples']}"
        )

    def test_no_duplicate_kg_sync(self, tmp_config):
        """Running two cycles shouldn't duplicate KG entries for existing discoveries."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.palace_memory.record_discovery(
            hypothesis_id="H001",
            domain="Astrophysics",
            finding_type="correlation",
            variables=["x", "y"],
            statistic=0.9,
            p_value=0.01,
            description="X correlates with Y",
            data_source="test",
        )

        agi.run_augmented_cycle()
        triples_after_1 = agi.kg_bridge.stats()["total_triples"]

        agi.run_augmented_cycle()
        triples_after_2 = agi.kg_bridge.stats()["total_triples"]

        # Second cycle should not duplicate triples for same discovery
        assert triples_after_2 == triples_after_1, (
            f"Triples grew from {triples_after_1} to {triples_after_2} "
            f"on second cycle (should be idempotent)"
        )

    def test_hypothesis_test_results_extracted(self, tmp_config):
        """Hypothesis test results should produce KG triples."""
        test_result = {
            "test_name": "Chi-squared GOF (ΛCDM Hubble fit)",
            "statistic": 1.05,
            "p_value": 0.03,
            "passed": True,
            "details": "H0=70.12±2.1, χ²/dof=1.05",
        }
        hyp = _make_hypothesis("H001", test_results=[test_result])
        engine = _make_mock_engine(hypotheses=[hyp])
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.run_augmented_cycle()

        stats = agi.kg_bridge.stats()
        # Should have at least one triple from the test result
        assert stats["total_triples"] >= 1

    def test_finding_type_to_predicate_mapping(self, tmp_config):
        """Different finding types should map to different predicates."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        for ft in ["correlation", "scaling", "causal"]:
            agi.palace_memory.record_discovery(
                hypothesis_id=f"H_{ft}",
                domain="Astrophysics",
                finding_type=ft,
                variables=[f"var_a_{ft}", f"var_b_{ft}"],
                statistic=0.9,
                p_value=0.01,
                description=f"Test {ft}",
                data_source="test",
            )

        agi.run_augmented_cycle()

        stats = agi.kg_bridge.stats()
        assert stats["total_triples"] >= 6  # At least 2 per finding type


# ══════════════════════════════════════════════════════════════════════
# Blocker 3: Continuous Discovery Loop
# ══════════════════════════════════════════════════════════════════════

class TestContinuousLoop:
    """Test the start/stop/get_status continuous cycling."""

    def test_start_stop_basic(self, tmp_config):
        """start() should run cycles, stop() should stop."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.start(interval_seconds=0.1, max_cycles=3)
        assert agi._running is True

        # Wait for cycles to complete
        time.sleep(2)
        agi.stop()

        assert agi._running is False
        assert agi.engine.cycle_count == 3

    def test_cycle_metrics_recorded(self, tmp_config):
        """Each completed cycle should record metrics."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.start(interval_seconds=0.1, max_cycles=2)
        time.sleep(2)
        agi.stop()

        assert len(agi._cycle_metrics) == 2
        metric = agi._cycle_metrics[0]
        assert "cycle" in metric
        assert "elapsed_seconds" in metric
        assert "discoveries" in metric
        assert "palace_drawers" in metric
        assert "kg_triples" in metric
        assert "timestamp" in metric

    def test_get_status_with_metrics(self, tmp_config):
        """get_status() should include cycle metrics."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.start(interval_seconds=0.1, max_cycles=2)
        time.sleep(2)
        agi.stop()

        status = agi.get_status()
        assert status["running"] is False
        assert status["total_cycles_completed"] == 2
        assert status["total_errors"] == 0
        assert status["last_cycle"] is not None
        assert "engine_cycle" in status
        assert "palace_stats" in status
        assert "kg_stats" in status

    def test_error_recovery(self, tmp_config):
        """Loop should survive individual cycle errors."""
        engine = _make_mock_engine()
        call_count = 0

        def flaky_run_cycle():
            nonlocal call_count
            call_count += 1
            engine.cycle_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated failure")
            engine.orient()
            engine.evaluate()

        engine.run_cycle.side_effect = flaky_run_cycle
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.start(interval_seconds=0.1, max_cycles=3)
        time.sleep(3)
        agi.stop()

        # Should have 1 error and still run remaining cycles
        assert len(agi._cycle_errors) >= 1
        assert agi._cycle_errors[0]["error"] == "Simulated failure"
        # At least 2 cycles should have succeeded (3 total - 1 error = 2 metrics)
        assert len(agi._cycle_metrics) >= 2

    def test_max_cycles_respected(self, tmp_config):
        """Loop should stop after max_cycles."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.start(interval_seconds=0.05, max_cycles=5)
        time.sleep(3)
        # Should auto-stop after 5 cycles
        assert agi._running is False
        assert agi.engine.cycle_count == 5

    def test_stop_is_idempotent(self, tmp_config):
        """Calling stop() multiple times should be safe."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        agi.stop()  # Stop before starting — should not error
        agi.start(interval_seconds=0.1, max_cycles=1)
        time.sleep(1)
        agi.stop()
        agi.stop()  # Double stop — should not error

    def test_initial_state(self, tmp_config):
        """Before start(), state should be clean."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        assert agi._running is False
        assert agi._cycle_metrics == []
        assert agi._cycle_errors == []
        assert agi._thread is None


# ══════════════════════════════════════════════════════════════════════
# Blocker 4: ChromaDB Stale Collection Recovery
# ══════════════════════════════════════════════════════════════════════

class TestChromaDBRecovery:
    """Test that stale ChromaDB collections are handled gracefully."""

    def test_normal_init(self, tmp_config):
        """Normal initialization should work."""
        mem = __import__(
            "mempalace_agi.palace_discovery_memory",
            fromlist=["PalaceDiscoveryMemory"],
        ).PalaceDiscoveryMemory(tmp_config)
        assert mem._backend is not None
        assert mem._backend.count() == 0

    def test_recovery_on_get_or_create_failure(self, tmp_config):
        """If backend init fails with stale data, should recover gracefully.

        The ChromaDBVectorBackend.__init__ handles the delete-and-recreate
        fallback internally, so we just verify that creating a second PDM
        instance pointing to the same path still works.
        """
        from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory

        # First create normally
        mem1 = PalaceDiscoveryMemory(tmp_config)
        assert mem1._backend is not None

        # Now test that even with a fresh config pointing to same path, it works
        mem2 = PalaceDiscoveryMemory(tmp_config)
        assert mem2._backend is not None


# ══════════════════════════════════════════════════════════════════════
# Blocker 5: Wikidata Timeout Configuration
# ══════════════════════════════════════════════════════════════════════

class TestWikidataTimeout:
    """Test Wikidata timeout and non-blocking behavior."""

    def test_default_timeout_is_30(self):
        """Default timeout should be 30s, not 5s."""
        from mempalace_agi.wikidata_enricher import WikidataClient
        client = WikidataClient()
        assert client.timeout == 30.0

    def test_custom_timeout(self):
        """Should accept custom timeout."""
        from mempalace_agi.wikidata_enricher import WikidataClient
        client = WikidataClient(timeout=60.0)
        assert client.timeout == 60.0

    def test_enricher_returns_empty_on_failure(self, tmp_config):
        """enrich_entity should return empty result on network failure, not crash."""
        from mempalace_agi.wikidata_enricher import WikidataEnricher, WikidataClient
        from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge

        kg = KnowledgeGraphBridge(tmp_config)

        # Client with invalid endpoint to force failure
        client = WikidataClient(
            endpoint="http://localhost:1/nonexistent",
            timeout=0.5,
        )
        enricher = WikidataEnricher(kg_bridge=kg, client=client)

        # Should NOT raise — should return empty EnrichmentResult
        result = enricher.enrich_entity("artificial intelligence")
        assert result is not None
        assert result.new_triples == 0
        # Should have recorded the error
        assert len(result.errors) > 0


# ══════════════════════════════════════════════════════════════════════
# Integration: Full Cycle with KG Populated
# ══════════════════════════════════════════════════════════════════════

class TestFullCycleIntegration:
    """End-to-end: run a cycle, verify discoveries → KG triples → status."""

    def test_full_cycle_end_to_end(self, tmp_config):
        """Run 3 cycles, adding discoveries each time, verify KG growth."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        # Cycle 1: record some discoveries
        agi.palace_memory.record_discovery(
            hypothesis_id="H001",
            domain="Astrophysics",
            finding_type="correlation",
            variables=["redshift", "distance_modulus"],
            statistic=0.92,
            p_value=0.005,
            description="Hubble diagram shows expected correlation",
            data_source="pantheon",
        )
        agi.run_augmented_cycle()

        status_1 = agi.get_status()
        kg_1 = status_1["kg_stats"]["total_triples"]
        assert kg_1 > 0, "First cycle should produce KG triples"

        # Cycle 2: add more
        agi.palace_memory.record_discovery(
            hypothesis_id="H002",
            domain="Economics",
            finding_type="trend",
            variables=["gdp_growth", "unemployment"],
            statistic=0.85,
            p_value=0.02,
            description="GDP growth inversely trends with unemployment",
            data_source="world_bank",
        )
        agi.run_augmented_cycle()

        status_2 = agi.get_status()
        kg_2 = status_2["kg_stats"]["total_triples"]
        assert kg_2 > kg_1, "Second cycle with new discovery should grow KG"

        # Cycle 3: same discoveries — KG should NOT grow
        agi.run_augmented_cycle()

        status_3 = agi.get_status()
        kg_3 = status_3["kg_stats"]["total_triples"]
        assert kg_3 == kg_2, "Third cycle with no new discoveries should not grow KG"

    def test_continuous_loop_with_discoveries(self, tmp_config):
        """Run continuous loop, verify it actually processes discoveries."""
        engine = _make_mock_engine()
        agi = MemPalaceAGI(config=tmp_config, engine_mock=engine)

        # Pre-seed a discovery
        agi.palace_memory.record_discovery(
            hypothesis_id="H001",
            domain="Climate",
            finding_type="anomaly",
            variables=["temp_anomaly", "year"],
            statistic=0.75,
            p_value=0.03,
            description="Temperature anomaly acceleration detected",
            data_source="hadcrut",
        )

        agi.start(interval_seconds=0.1, max_cycles=2)
        time.sleep(2)
        agi.stop()

        status = agi.get_status()
        assert status["total_cycles_completed"] == 2
        assert status["kg_stats"]["total_triples"] > 0
