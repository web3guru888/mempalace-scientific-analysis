"""
Smoke test — exercises all 4 ASI:BUILD gem adoptions end-to-end.

This is NOT a unit test — it instantiates real objects, feeds them data,
and prints a report. Run it with:
    python -m pytest tests/test_asi_adoption_smoke.py -v -s
"""

import sys
import os
import time

import numpy as np
import pytest

# ── Ensure paths ───────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.discovery_synergy import DiscoverySynergyAnalyzer, SynergyMetrics
from mempalace_agi.palace_integration_measure import IITCalculator, PalaceIntegrationMeasure
from mempalace_agi.hypothesis_workspace import HypothesisWorkspace, DomainSpecialistProxy
from mempalace_agi.kg_communities import KGCommunityDetector


# ── Mock KG Bridge ─────────────────────────────────────────────────────

class MockKGBridge:
    """Fake KG bridge with cross-domain triples for testing."""

    def __init__(self):
        self._triples = [
            # Astrophysics cluster
            {"subject": "dark_matter", "predicate": "correlated_with", "object": "galaxy_rotation", "confidence": 0.9},
            {"subject": "galaxy_rotation", "predicate": "scales_with", "object": "luminosity", "confidence": 0.85},
            {"subject": "dark_matter", "predicate": "related_to", "object": "gravitational_lensing", "confidence": 0.8},
            # Economics cluster
            {"subject": "inflation", "predicate": "causes", "object": "interest_rate", "confidence": 0.95},
            {"subject": "interest_rate", "predicate": "correlated_with", "object": "gdp_growth", "confidence": 0.75},
            {"subject": "gdp_growth", "predicate": "trends_with", "object": "employment", "confidence": 0.8},
            # Climate cluster
            {"subject": "co2_emissions", "predicate": "causes", "object": "temperature_rise", "confidence": 0.92},
            {"subject": "temperature_rise", "predicate": "correlated_with", "object": "sea_level", "confidence": 0.88},
            # Cross-domain bridges
            {"subject": "temperature_rise", "predicate": "correlated_with", "object": "gdp_growth", "confidence": 0.45},
            {"subject": "gravitational_lensing", "predicate": "related_to", "object": "co2_emissions", "confidence": 0.1},  # weak
        ]

    def get_valid_triples(self):
        return self._triples


# ── Test 1: Discovery Synergy Analyzer ─────────────────────────────────

class TestSynergySmoke:
    """Feeds 20 fake OODA cycles to the synergy analyzer and computes all metrics."""

    def test_full_synergy_workflow(self):
        analyzer = DiscoverySynergyAnalyzer(window_size=100, min_samples=10)
        rng = np.random.default_rng(42)

        # Simulate 20 OODA cycles across 4 domains
        for cycle in range(20):
            counts = {
                "astrophysics": int(rng.poisson(3)),
                "climate": int(rng.poisson(2)),
                "economics": int(rng.poisson(4)),
                "epidemiology": int(rng.poisson(1)),
            }
            analyzer.record_cycle(counts)

        assert analyzer.sample_count == 20
        assert len(analyzer.domains) == 4

        # Pairwise synergy
        profiles = analyzer.compute_pairwise_synergy()
        assert len(profiles) == 6  # C(4,2)
        for pair_name, profile in profiles.items():
            assert 0.0 <= profile.mutual_information <= 1.0
            assert 0.0 <= profile.complexity_resonance <= 1.0

        # Transfer entropy matrix
        te_matrix = analyzer.get_transfer_entropy_matrix()
        assert len(te_matrix) == 4
        for domain in te_matrix:
            assert te_matrix[domain][domain] == 0.0  # diagonal

        # Top synergies
        top = analyzer.get_top_synergies(n=3)
        assert len(top) <= 3
        assert all(isinstance(t, tuple) and len(t) == 3 for t in top)

        # Emergence score
        emergence = analyzer.get_emergence_score()
        assert 0.0 <= emergence <= 1.0

        # Full report
        report = analyzer.get_synergy_report()
        assert "domains" in report
        assert "pairwise" in report
        assert "overall_emergence" in report
        assert report["sample_count"] == 20


# ── Test 2: Palace Integration Measure (IIT Φ) ────────────────────────

class TestIntegrationSmoke:
    """Builds a mock palace with cross-domain connections and computes Φ."""

    def test_full_phi_workflow(self):
        mock_kg = MockKGBridge()
        measure = PalaceIntegrationMeasure(kg_bridge=mock_kg)

        # Entity-level Φ
        phi = measure.compute_palace_phi()
        assert isinstance(phi, float)
        assert phi >= 0.0

        # Full report
        report = measure.get_integration_report()
        assert "overall_phi" in report
        assert "per_pair_phi" in report
        assert "minimum_partition" in report
        assert report["num_elements"] >= 8  # 8+ unique entities
        assert report["num_connections"] > 0

        # Track history
        measure.track_phi_history(phi)
        measure.track_phi_history(phi + 0.1)
        assert len(measure._phi_history) == 2

    def test_iit_calculator_directly(self):
        """Verify the calculator on a 5-wing palace."""
        calc = IITCalculator()
        wings = ["Astrophysics", "Climate", "Economics", "Epidemiology", "Cryptography"]
        for w in wings:
            calc.add_element(w, state=1.0)

        # Add cross-wing connections
        calc.add_connection("Astrophysics", "Climate", 0.5)
        calc.add_connection("Climate", "Economics", 0.6)
        calc.add_connection("Economics", "Epidemiology", 0.4)
        calc.add_connection("Epidemiology", "Cryptography", 0.3)
        calc.add_connection("Cryptography", "Astrophysics", 0.2)  # ring topology

        phi = calc.compute_phi()
        assert phi > 0.0, "Ring-connected wings should have positive Φ"

        mip_a, mip_b = calc.find_minimum_information_partition()
        assert len(mip_a) + len(mip_b) == 5
        assert mip_a & mip_b == frozenset()


# ── Test 3: Hypothesis Workspace (GWT) ────────────────────────────────

class TestWorkspaceSmoke:
    """Submits 5 hypotheses, runs competition, verifies winner selection."""

    def test_full_workspace_workflow(self):
        ws = HypothesisWorkspace(capacity=7, competition_rounds=3)

        # Register 4 domain specialists
        for domain in ["astrophysics", "climate", "economics", "epidemiology"]:
            ws.register_specialist(domain)

        # Submit 5 hypotheses
        hypotheses = [
            ("H001", "Dark matter distribution follows NFW profile", "astrophysics", 0.9),
            ("H002", "CO2 forcing has 30-year lag on sea level", "climate", 0.7),
            ("H003", "Interest rates predict equity returns", "economics", 0.6),
            ("H004", "Epidemic threshold depends on network topology", "epidemiology", 0.8),
            ("H005", "Cross-domain: climate affects epidemic spread", "epidemiology", 0.5),
        ]
        for hid, content, domain, activation in hypotheses:
            ws.submit_hypothesis(hid, content, domain, activation)

        assert ws.workspace_size == 5

        # Run competition
        winner = ws.run_competition()
        assert winner is not None
        assert winner.hypothesis_id in [h[0] for h in hypotheses]
        assert ws.workspace_size == 4  # winner removed
        assert ws.total_broadcasts == 1

        # Run again
        winner2 = ws.run_competition()
        assert winner2 is not None
        assert winner2.hypothesis_id != winner.hypothesis_id or winner2.broadcast_count > 1
        assert ws.total_broadcasts == 2

        # Status
        status = ws.get_status()
        assert status["total_broadcasts"] == 2
        assert len(status["specialists"]) == 4


# ── Test 4: KG Community Detection ────────────────────────────────────

class TestCommunitiesSmoke:
    """Detects communities in the mock KG, finds bridges."""

    def test_full_community_workflow(self):
        mock_kg = MockKGBridge()
        detector = KGCommunityDetector(kg_bridge=mock_kg)

        # Build graph
        graph = detector.build_graph()
        assert graph.number_of_nodes() >= 8
        assert graph.number_of_edges() >= 8

        # Detect communities
        communities = detector.detect_communities_louvain(graph=graph)
        assert len(communities) >= 2  # should find at least astro + econ clusters

        # All entities assigned
        all_entities = set()
        for comm in communities:
            all_entities.update(comm)
        assert all_entities == set(graph.nodes())

        # Bridges
        bridges = detector.get_cross_domain_bridges(communities=communities, graph=graph)
        assert len(bridges) >= 1  # temperature_rise or gdp_growth bridge

        # Investigation targets
        targets = detector.suggest_investigation_targets(
            communities=communities, graph=graph
        )
        assert len(targets) >= 2

        # Modularity
        mod = detector.compute_modularity(communities=communities, graph=graph)
        assert mod > 0.0

        # Full report
        report = detector.get_community_report()
        assert report["community_count"] >= 2
        assert report["modularity"] > 0.0
        assert len(report["bridge_entities"]) >= 1


# ── Test 5: Orchestrator Workspace Wiring ──────────────────────────────

class TestOrchestratorWiring:
    """Verify the workspace is wired into the orchestrator."""

    def test_orchestrator_has_workspace(self, test_config):
        from mempalace_agi.orchestrator import MemPalaceAGI

        class MinimalEngine:
            def __init__(self):
                self.cycle_count = 0
                self.discovery_memory = None
            def orient(self): pass
            def select(self): pass
            def investigate(self): pass
            def evaluate(self): pass
            def update(self): pass
            def run_cycle(self):
                self.cycle_count += 1
                self.orient(); self.select(); self.investigate()
                self.evaluate(); self.update()
            class store:
                @staticmethod
                def active(): return []

        agi = MemPalaceAGI(config=test_config, engine_mock=MinimalEngine())
        assert hasattr(agi, "hypothesis_workspace")
        assert isinstance(agi.hypothesis_workspace, HypothesisWorkspace)

        # GWT disabled by default
        status = agi.get_status()
        assert status["gwt_select_enabled"] is False
        assert "hypothesis_workspace" in status

        # Enable GWT
        agi.use_gwt_select(True)
        assert agi._use_gwt_select is True
