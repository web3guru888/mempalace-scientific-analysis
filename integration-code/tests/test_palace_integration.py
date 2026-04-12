"""Tests for palace_integration_measure — IIT Φ for Knowledge Graph Wings.

Tests IITCalculator (pure graph Φ computation) and PalaceIntegrationMeasure
(KG-backed palace integration analysis).
"""

import time

import pytest

from mempalace_agi.palace_integration_measure import (
    IITCalculator,
    PalaceIntegrationMeasure,
    PhiResult,
)


# ── Mock KG Bridge ────────────────────────────────────────────────────

class MockKGBridge:
    """Minimal mock of KnowledgeGraphBridge for PalaceIntegrationMeasure tests."""

    def __init__(self, triples=None):
        self._triples = triples or []

    def get_valid_triples(self):
        return list(self._triples)


def _make_triple(subj, pred, obj, confidence=0.5, domain=None):
    """Helper to build a triple dict."""
    t = {
        "subject": subj,
        "predicate": pred,
        "object": obj,
        "confidence": confidence,
    }
    if domain:
        t["domain"] = domain
    return t


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def calc():
    """Fresh IITCalculator."""
    return IITCalculator()


@pytest.fixture
def three_node_calc():
    """IITCalculator with A→B(0.8), B→C(0.6), A→C(0.4)."""
    c = IITCalculator()
    c.add_element("A", state=1.0)
    c.add_element("B", state=0.7)
    c.add_element("C", state=0.3)
    c.add_connection("A", "B", 0.8)
    c.add_connection("B", "C", 0.6)
    c.add_connection("A", "C", 0.4)
    return c


@pytest.fixture
def cross_domain_triples():
    """Triples that connect entities across domains."""
    return [
        _make_triple("astro_entity_1", "correlates_with", "econ_entity_1", 0.8),
        _make_triple("econ_entity_1", "causes", "climate_entity_1", 0.6),
        _make_triple("climate_entity_1", "scales_with", "astro_entity_2", 0.7),
        _make_triple("astro_entity_1", "predicts", "astro_entity_2", 0.9),
    ]


# ═══════════════════════════════════════════════════════════════════════
# IITCalculator Tests
# ═══════════════════════════════════════════════════════════════════════


class TestIITCalculatorEmpty:
    """Tests 1–3: edge cases with no meaningful integration."""

    def test_empty_system_phi_zero(self, calc):
        """1. Empty system → Φ = 0."""
        assert calc.compute_phi() == 0.0

    def test_single_element_phi_zero(self, calc):
        """2. Single element → Φ = 0 (can't partition one node)."""
        calc.add_element("sole", state=1.0)
        assert calc.compute_phi() == 0.0

    def test_two_disconnected_phi_zero(self, calc):
        """3. Two disconnected elements → Φ = 0 (no cross-cut edges)."""
        calc.add_element("X", state=0.5)
        calc.add_element("Y", state=0.5)
        phi = calc.compute_phi()
        assert phi == 0.0


class TestIITCalculatorConnected:
    """Tests 4–5: connected systems have Φ > 0."""

    def test_two_connected_phi_positive(self, calc):
        """4. Two connected elements → Φ > 0."""
        calc.add_element("A", state=0.8)
        calc.add_element("B", state=0.6)
        calc.add_connection("A", "B", 1.0)
        phi = calc.compute_phi()
        assert phi > 0.0

    def test_three_node_phi_positive(self, three_node_calc):
        """5. Three connected elements → Φ > 0."""
        phi = three_node_calc.compute_phi()
        assert phi > 0.0

    def test_three_node_phi_value_reasonable(self, three_node_calc):
        """Phi for 3-node graph should be finite and reasonable."""
        phi = three_node_calc.compute_phi()
        # Φ is the *minimum* cross-cut information; should be a moderate value
        assert 0.0 < phi < 100.0


class TestIITCalculatorErrors:
    """Tests 6–7: error handling."""

    def test_add_connection_nonexistent_element(self, calc):
        """6. add_connection with nonexistent element → ValueError."""
        calc.add_element("A")
        with pytest.raises(ValueError, match="Both endpoints must exist"):
            calc.add_connection("A", "ghost", 0.5)

    def test_add_connection_both_nonexistent(self, calc):
        """add_connection with both nonexistent → ValueError."""
        with pytest.raises(ValueError):
            calc.add_connection("x", "y", 0.5)

    def test_set_state_unknown_element(self, calc):
        """7. set_state on unknown element → KeyError."""
        with pytest.raises(KeyError):
            calc.set_state("no_such_element", 1.0)


class TestIITCalculatorPartition:
    """Test 8: minimum information partition."""

    def test_find_mip_three_nodes(self, three_node_calc):
        """8. MIP on 3 connected nodes returns two non-empty partition sets."""
        part_a, part_b = three_node_calc.find_minimum_information_partition()
        assert isinstance(part_a, frozenset)
        assert isinstance(part_b, frozenset)
        # Both partitions non-empty for 3 nodes
        assert len(part_a) >= 1
        assert len(part_b) >= 1
        # Together they cover all elements
        assert part_a | part_b == frozenset({"A", "B", "C"})
        # No overlap
        assert part_a & part_b == frozenset()

    def test_mip_single_returns_trivial(self, calc):
        """MIP on single element returns (element, empty)."""
        calc.add_element("solo")
        part_a, part_b = calc.find_minimum_information_partition()
        assert part_a == frozenset({"solo"})
        assert part_b == frozenset()


class TestIITCalculatorCache:
    """Tests 9–10: caching behaviour."""

    def test_cache_returns_same_result(self, three_node_calc):
        """9. Second call to compute_phi returns cached result (same value)."""
        phi1 = three_node_calc.compute_phi()
        phi2 = three_node_calc.compute_phi()
        assert phi1 == phi2
        # Verify cache was populated
        assert len(three_node_calc._partition_cache) > 0

    def test_cache_clears_on_add_element(self, three_node_calc):
        """10. Adding a new element clears the partition cache."""
        # Warm the cache
        three_node_calc.compute_phi()
        assert len(three_node_calc._partition_cache) > 0
        # Adding element should clear
        three_node_calc.add_element("D", state=0.5)
        assert len(three_node_calc._partition_cache) == 0

    def test_cache_clears_on_add_connection(self, three_node_calc):
        """Adding a connection also clears cache."""
        three_node_calc.compute_phi()
        assert len(three_node_calc._partition_cache) > 0
        three_node_calc.add_connection("C", "A", 0.3)
        assert len(three_node_calc._partition_cache) == 0

    def test_clear_cache_explicit(self, three_node_calc):
        """clear_cache() empties the cache."""
        three_node_calc.compute_phi()
        assert len(three_node_calc._partition_cache) > 0
        three_node_calc.clear_cache()
        assert len(three_node_calc._partition_cache) == 0


class TestIITCalculatorStateHistory:
    """Tests 11–12: state snapshots and reset."""

    def test_record_state_snapshot_affects_entropy(self, calc):
        """11. Recording state snapshots changes entropy calculation."""
        calc.add_element("A", state=0.9)
        calc.add_element("B", state=0.1)
        calc.add_connection("A", "B", 1.0)

        # Compute phi without history (uses current states directly)
        phi_no_history = calc.compute_phi()
        calc.clear_cache()

        # Record a sequence of different state snapshots to create entropy
        for i in range(10):
            calc.set_state("A", 0.9 if i % 2 == 0 else 0.1)
            calc.set_state("B", 0.1 if i % 2 == 0 else 0.9)
            calc.record_state_snapshot()

        phi_with_history = calc.compute_phi()
        # With varying state history, entropy changes → phi changes
        # (they may differ; the key assertion is both are computed successfully)
        assert isinstance(phi_with_history, float)
        assert phi_with_history >= 0.0
        # The alternating pattern creates maximum entropy (1 bit),
        # which should differ from the static-state entropy
        assert phi_no_history != phi_with_history

    def test_reset_clears_everything(self, three_node_calc):
        """12. reset() clears elements, connections, history, and cache."""
        three_node_calc.compute_phi()
        three_node_calc.record_state_snapshot()

        three_node_calc.reset()

        assert len(three_node_calc._elements) == 0
        assert len(three_node_calc._connections) == 0
        assert len(three_node_calc._state_history) == 0
        assert len(three_node_calc._partition_cache) == 0
        # Post-reset phi is 0
        assert three_node_calc.compute_phi() == 0.0


# ═══════════════════════════════════════════════════════════════════════
# PalaceIntegrationMeasure Tests (mock KG bridge)
# ═══════════════════════════════════════════════════════════════════════


class TestPalaceIntegrationMeasurePhi:
    """Tests 13–14: palace-level Φ computation."""

    def test_compute_palace_phi_with_triples(self, cross_domain_triples):
        """13. compute_palace_phi with entity-level analysis returns Φ > 0."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        phi = pim.compute_palace_phi()
        assert isinstance(phi, float)
        # 4 entities with cross-links → should have positive integration
        assert phi > 0.0

    def test_compute_wing_pair_phi(self, cross_domain_triples):
        """14. compute_wing_pair_phi between two wings with cross-edges."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        # Wings whose names appear in entity names
        phi = pim.compute_wing_pair_phi("astro", "econ")
        assert isinstance(phi, float)
        # astro_entity_1 → econ_entity_1 connection exists → positive Φ
        assert phi >= 0.0


class TestPalaceIntegrationReport:
    """Test 15: report structure."""

    def test_get_integration_report_structure(self, cross_domain_triples):
        """15. Report has all required keys and correct types."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        report = pim.get_integration_report()

        # Check all required keys
        assert "overall_phi" in report
        assert "per_pair_phi" in report
        assert "minimum_partition" in report
        assert "phi_history" in report
        assert "num_elements" in report
        assert "num_connections" in report

        # Type checks
        assert isinstance(report["overall_phi"], float)
        assert isinstance(report["per_pair_phi"], dict)
        assert isinstance(report["minimum_partition"], dict)
        assert "part_a" in report["minimum_partition"]
        assert "part_b" in report["minimum_partition"]
        assert isinstance(report["phi_history"], list)
        assert isinstance(report["num_elements"], int)
        assert isinstance(report["num_connections"], int)

        # Entity-level: 4 unique entities
        assert report["num_elements"] == 4
        assert report["num_connections"] > 0

    def test_report_per_pair_phi_covers_all_pairs(self, cross_domain_triples):
        """Per-pair Φ should cover all C(n,2) pairs."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        report = pim.get_integration_report()
        n = report["num_elements"]
        expected_pairs = n * (n - 1) // 2
        assert len(report["per_pair_phi"]) == expected_pairs


class TestPalacePhiHistory:
    """Test 16: history tracking."""

    def test_track_phi_history_appends(self):
        """16. track_phi_history appends entries with timestamps."""
        bridge = MockKGBridge([])
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        assert len(pim._phi_history) == 0

        pim.track_phi_history(0.5)
        pim.track_phi_history(0.7)
        pim.track_phi_history(0.9)

        assert len(pim._phi_history) == 3
        # Entries are (timestamp, phi) tuples
        assert pim._phi_history[0][1] == 0.5
        assert pim._phi_history[1][1] == 0.7
        assert pim._phi_history[2][1] == 0.9
        # Timestamps are monotonically non-decreasing
        assert pim._phi_history[0][0] <= pim._phi_history[1][0]
        assert pim._phi_history[1][0] <= pim._phi_history[2][0]

    def test_phi_history_appears_in_report(self):
        """Tracked history shows up in the integration report."""
        bridge = MockKGBridge([])
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        pim.track_phi_history(0.42)
        report = pim.get_integration_report()

        assert len(report["phi_history"]) == 1
        assert report["phi_history"][0]["phi"] == 0.42
        assert "timestamp" in report["phi_history"][0]

    def test_phi_history_bounded_at_500(self):
        """History truncates to last 500 entries."""
        bridge = MockKGBridge([])
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        for i in range(600):
            pim.track_phi_history(float(i))

        assert len(pim._phi_history) == 500
        # Should keep the last 500 (values 100–599)
        assert pim._phi_history[0][1] == 100.0
        assert pim._phi_history[-1][1] == 599.0


class TestPalaceEmptyKG:
    """Test 17: empty KG."""

    def test_empty_kg_phi_zero(self):
        """17. Empty KG → Φ = 0 (no elements, no connections)."""
        bridge = MockKGBridge([])
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        phi = pim.compute_palace_phi()
        assert phi == 0.0

    def test_empty_kg_report_all_zeros(self):
        """Empty KG report has 0 elements, 0 connections, phi 0."""
        bridge = MockKGBridge([])
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        report = pim.get_integration_report()
        assert report["overall_phi"] == 0.0
        assert report["num_elements"] == 0
        assert report["num_connections"] == 0
        assert report["per_pair_phi"] == {}


class TestPalaceIntegrationWingLevel:
    """Wing-level analysis with explicit wing names."""

    def test_wing_level_phi_with_cross_domain(self, cross_domain_triples):
        """Wing-level Φ with named wings picking up cross-domain edges."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        # Entities contain astro_, econ_, climate_ in names
        phi = pim.compute_palace_phi(wings=["astro", "econ", "climate"])
        assert isinstance(phi, float)
        assert phi >= 0.0

    def test_wing_level_report_elements_match_wings(self, cross_domain_triples):
        """Report with explicit wings should show wing count, not entity count."""
        bridge = MockKGBridge(cross_domain_triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        wings = ["astro", "econ", "climate"]
        report = pim.get_integration_report(wings=wings)
        assert report["num_elements"] == 3


class TestPalaceIntegrationEdgeCases:
    """Additional edge cases."""

    def test_kg_bridge_exception_returns_zero(self):
        """If KG bridge raises, Φ = 0 (graceful degradation)."""

        class BrokenBridge:
            def get_valid_triples(self):
                raise RuntimeError("DB connection lost")

        pim = PalaceIntegrationMeasure(kg_bridge=BrokenBridge())
        phi = pim.compute_palace_phi()
        assert phi == 0.0

    def test_confidence_as_string(self):
        """Confidence values provided as strings are parsed correctly."""
        triples = [
            _make_triple("alpha", "relates_to", "beta", confidence="0.75"),
        ]
        bridge = MockKGBridge(triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        # Entity-level: two nodes with a connection
        phi = pim.compute_palace_phi()
        assert phi > 0.0

    def test_invalid_confidence_fallback(self):
        """Non-numeric confidence falls back to 0.5."""
        triples = [
            _make_triple("x", "links", "y", confidence="not_a_number"),
        ]
        bridge = MockKGBridge(triples)
        pim = PalaceIntegrationMeasure(kg_bridge=bridge)

        phi = pim.compute_palace_phi()
        # Should still compute without error, using fallback confidence
        assert isinstance(phi, float)
        assert phi > 0.0


class TestPhiResultDataclass:
    """PhiResult dataclass sanity."""

    def test_phi_result_creation(self):
        """PhiResult can be created and has auto-timestamp."""
        before = time.time()
        result = PhiResult(
            phi=1.23,
            partition=(frozenset({"A"}), frozenset({"B"})),
            elements=frozenset({"A", "B"}),
        )
        after = time.time()

        assert result.phi == 1.23
        assert result.elements == frozenset({"A", "B"})
        assert before <= result.timestamp <= after
