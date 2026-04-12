"""
Tests for KnowledgeGraphBridge — bridges ASTRA-dev KG with MemPalace KG.
"""

import os
import sys
from dataclasses import dataclass
from typing import List

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.knowledge_graph_bridge import KnowledgeGraphBridge
from mempalace_agi.config import IntegrationConfig


@dataclass
class MockCausalEdge:
    """Minimal causal edge for testing."""
    source: str
    target: str
    edge_type: str = "→"
    confidence: float = 0.8
    p_value: float = 0.01
    conditioning_set: list = None

    def __post_init__(self):
        if self.conditioning_set is None:
            self.conditioning_set = []


@dataclass
class MockCausalGraph:
    """Minimal causal graph for testing."""
    variables: List[str]
    edges: List[MockCausalEdge]
    algorithm: str = "PC"


@pytest.fixture
def bridge(test_config):
    return KnowledgeGraphBridge(config=test_config)


class TestCausalEdges:
    """Test recording causal discovery results as KG triples."""

    def test_record_single_causal_edge(self, bridge):
        """A causal edge creates entities and a triple."""
        graph = MockCausalGraph(
            variables=["stellar_mass", "luminosity"],
            edges=[
                MockCausalEdge(source="stellar_mass", target="luminosity",
                               edge_type="→", confidence=0.9),
            ],
        )

        triple_ids = bridge.record_causal_edges(graph, source_hypothesis="H001", cycle=1)
        assert len(triple_ids) == 1

        # Verify the triple exists in KG
        triples = bridge.get_causal_triples()
        assert len(triples) >= 1

    def test_record_multiple_causal_edges(self, bridge):
        """Multiple edges create multiple triples."""
        graph = MockCausalGraph(
            variables=["X", "Y", "Z"],
            edges=[
                MockCausalEdge(source="X", target="Y", edge_type="→", confidence=0.8),
                MockCausalEdge(source="Y", target="Z", edge_type="→", confidence=0.7),
                MockCausalEdge(source="X", target="Z", edge_type="o-o", confidence=0.5),
            ],
        )

        triple_ids = bridge.record_causal_edges(graph, source_hypothesis="H001")
        assert len(triple_ids) == 3

    def test_edge_type_mapping(self, bridge):
        """Different edge types map to correct predicates."""
        edges = [
            MockCausalEdge(source="A", target="B", edge_type="→"),
            MockCausalEdge(source="C", target="D", edge_type="o-o"),
            MockCausalEdge(source="E", target="F", edge_type="x→"),
        ]
        graph = MockCausalGraph(variables=["A", "B", "C", "D", "E", "F"], edges=edges)

        bridge.record_causal_edges(graph, source_hypothesis="H001")

        # Query specific predicates
        causes = bridge.kg.query_relationship("causes")
        assert len(causes) >= 1

        associated = bridge.kg.query_relationship("associated_with")
        assert len(associated) >= 1

        possibly = bridge.kg.query_relationship("possibly_causes")
        assert len(possibly) >= 1

    def test_empty_causal_graph(self, bridge):
        """Empty graph produces no triples."""
        graph = MockCausalGraph(variables=[], edges=[])
        triple_ids = bridge.record_causal_edges(graph)
        assert triple_ids == []


class TestNetworkxDiGraphInput:
    """Test record_causal_edges with raw networkx DiGraph objects."""

    def test_networkx_digraph_basic(self, bridge):
        """A networkx DiGraph produces KG triples just like a CausalGraph."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("stellar_mass", "luminosity", edge_type="→", confidence=0.9, p_value=0.01)

        triple_ids = bridge.record_causal_edges(G, source_hypothesis="H001", cycle=1)
        assert len(triple_ids) == 1

        # Verify the triple exists in KG
        triples = bridge.get_causal_triples()
        assert len(triples) >= 1

    def test_networkx_digraph_multiple_edges(self, bridge):
        """Multiple networkx edges create multiple triples."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("X", "Y", edge_type="→", confidence=0.8)
        G.add_edge("Y", "Z", edge_type="→", confidence=0.7)
        G.add_edge("X", "Z", edge_type="o-o", confidence=0.5)

        triple_ids = bridge.record_causal_edges(G, source_hypothesis="H002")
        assert len(triple_ids) == 3

    def test_networkx_digraph_default_attrs(self, bridge):
        """Networkx edges without explicit attrs use sensible defaults."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("A", "B")  # No attrs at all

        triple_ids = bridge.record_causal_edges(G, source_hypothesis="H003")
        assert len(triple_ids) == 1

        # Should use default edge_type "→" → predicate "causes"
        triples = bridge.get_causal_triples()
        predicates = [t.get("predicate", "") for t in triples]
        assert "causes" in predicates

    def test_networkx_digraph_weight_as_confidence(self, bridge):
        """Networkx edges with 'weight' but no 'confidence' use weight as confidence."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("temperature", "ice_mass", weight=0.75, edge_type="→")

        triple_ids = bridge.record_causal_edges(G, source_hypothesis="H004", cycle=2)
        assert len(triple_ids) == 1

        # Verify provenance stores the weight-derived confidence
        prov = bridge.get_provenance(triple_ids[0])
        assert prov is not None
        assert prov["confidence_history"][0]["confidence"] == 0.75

    def test_networkx_digraph_provenance(self, bridge):
        """Networkx edges get full provenance tracking."""
        import networkx as nx

        G = nx.DiGraph()
        G.add_edge("co2", "temperature", edge_type="→", confidence=0.85)

        triple_ids = bridge.record_causal_edges(
            G,
            source_hypothesis="H005",
            cycle=3,
            agent_id="climate_specialist",
            evidence_chain=["dataset_gistemp"],
            cycle_id="ooda_cycle_10",
        )

        prov = bridge.get_provenance(triple_ids[0])
        assert prov is not None
        assert prov["agent_id"] == "climate_specialist"
        assert prov["cycle_id"] == "ooda_cycle_10"
        assert "dataset_gistemp" in prov["evidence_chain"]

    def test_networkx_empty_digraph(self, bridge):
        """An empty networkx DiGraph produces no triples."""
        import networkx as nx

        G = nx.DiGraph()
        triple_ids = bridge.record_causal_edges(G)
        assert triple_ids == []

    def test_causal_graph_still_works(self, bridge):
        """CausalGraph objects still work after networkx detection was added."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", edge_type="→", confidence=0.8)],
            algorithm="FCI",
        )
        triple_ids = bridge.record_causal_edges(graph, source_hypothesis="H001")
        assert len(triple_ids) == 1


class TestDiscoveryEntities:
    """Test recording discoveries as KG entities."""

    def test_record_discovery_entity(self, bridge):
        """Discovery creates entity + relationships."""
        entity_id = bridge.record_discovery_entity(
            discovery_id="D0001",
            domain="Astrophysics",
            finding_type="scaling",
            description="Mass-radius scaling in exoplanets",
            hypothesis_id="H001",
            variables=["mass", "radius"],
            strength=0.85,
        )

        assert entity_id is not None

        # Verify relationships
        rels = bridge.get_discovery_relationships("D0001")
        assert len(rels) > 0

        # Should have: produced_by, belongs_to_domain, involves_variable (x2)
        predicates = [r.get("predicate", "") for r in rels]
        assert "produced_by" in predicates
        assert "belongs_to_domain" in predicates
        assert "involves_variable" in predicates


class TestHypothesisLifecycle:
    """Test hypothesis phase tracking in KG."""

    def test_record_phase_transition(self, bridge):
        """Phase transition creates/updates KG triples."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H001",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.35,
        )

        # Check timeline
        timeline = bridge.get_hypothesis_timeline("H001")
        assert len(timeline) >= 1

    def test_multiple_transitions(self, bridge):
        """Multiple transitions create a timeline."""
        transitions = [
            ("PROPOSED", "SCREENING", 0.35),
            ("SCREENING", "TESTING", 0.55),
            ("TESTING", "VALIDATED", 0.75),
        ]

        for from_p, to_p, conf in transitions:
            bridge.record_hypothesis_transition("H001", from_p, to_p, conf)

        timeline = bridge.get_hypothesis_timeline("H001")
        assert len(timeline) >= 1  # At least some triples


class TestCrossDomainLinks:
    """Test cross-domain link recording."""

    def test_record_cross_domain_link(self, bridge):
        """Cross-domain link creates a triple."""
        # First create the discovery entities
        bridge.record_discovery_entity(
            "D0001", "Astrophysics", "scaling", "Mass-radius scaling",
            "H001", ["mass", "radius"], 0.8,
        )
        bridge.record_discovery_entity(
            "D0002", "Economics", "scaling", "GDP-population scaling",
            "H002", ["gdp", "population"], 0.7,
        )

        bridge.record_cross_domain_link(
            "D0001", "D0002",
            link_type="structurally_similar",
            similarity=0.65,
        )

        # Verify the link exists
        rels = bridge.kg.query_entity("d0001", direction="outgoing")
        link_predicates = [r.get("predicate", "") for r in rels]
        assert "structurally_similar" in link_predicates


class TestStats:
    """Test KG statistics."""

    def test_stats(self, bridge):
        """Stats returns entity/triple counts."""
        bridge.record_discovery_entity(
            "D0001", "Astrophysics", "scaling", "Test",
            "H001", ["x"], 0.5,
        )

        stats = bridge.stats()
        assert "entities" in stats or "entity_count" in stats or isinstance(stats, dict)

    def test_stats_total_aliases(self, bridge):
        """Stats includes total_entities and total_triples aliases."""
        bridge.record_discovery_entity(
            "D0002", "Economics", "correlation", "GDP test",
            "H002", ["gdp", "pop"], 0.6,
        )

        stats = bridge.stats()
        # Both original and aliased keys must be present
        assert "entities" in stats
        assert "triples" in stats
        assert "total_entities" in stats
        assert "total_triples" in stats
        # They must agree
        assert stats["total_entities"] == stats["entities"]
        assert stats["total_triples"] == stats["triples"]
        # And they should be positive after recording
        assert stats["total_entities"] > 0
        assert stats["total_triples"] > 0


class TestProvenance:
    """Test provenance tracking for KG triples."""

    def test_causal_edge_provenance_stored(self, bridge):
        """Causal edge recording creates provenance records."""
        graph = MockCausalGraph(
            variables=["stellar_mass", "luminosity"],
            edges=[
                MockCausalEdge(
                    source="stellar_mass", target="luminosity",
                    edge_type="→", confidence=0.9,
                ),
            ],
            algorithm="PC",
        )

        triple_ids = bridge.record_causal_edges(
            graph,
            source_hypothesis="H001",
            cycle=1,
            agent_id="astro_specialist",
            evidence_chain=["dataset_kepler_2024", "D0001"],
            cycle_id="ooda_cycle_7",
        )
        assert len(triple_ids) == 1

        prov = bridge.get_provenance(triple_ids[0])
        assert prov is not None
        assert prov["agent_id"] == "astro_specialist"
        assert prov["cycle_id"] == "ooda_cycle_7"
        assert "dataset_kepler_2024" in prov["evidence_chain"]
        assert "D0001" in prov["evidence_chain"]
        # Should have exactly one confidence history entry
        assert len(prov["confidence_history"]) == 1
        assert prov["confidence_history"][0]["confidence"] == 0.9
        assert "PC algorithm" in prov["confidence_history"][0]["reason"]

    def test_causal_edge_default_cycle_id(self, bridge):
        """When cycle_id is omitted, it falls back to 'cycle_{cycle}'."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B")],
        )

        triple_ids = bridge.record_causal_edges(graph, cycle=3)
        prov = bridge.get_provenance(triple_ids[0])
        assert prov is not None
        assert prov["cycle_id"] == "cycle_3"

    def test_discovery_entity_provenance(self, bridge):
        """Recording a discovery entity creates provenance for its triples."""
        bridge.record_discovery_entity(
            discovery_id="D0010",
            domain="Economics",
            finding_type="scaling",
            description="GDP scaling law",
            hypothesis_id="H010",
            variables=["gdp", "population"],
            strength=0.75,
            agent_id="econ_specialist",
            cycle_id="ooda_cycle_12",
        )

        # Get all triples for this discovery and verify provenance exists
        rels = bridge.get_discovery_relationships("D0010")
        assert len(rels) > 0

        # Check provenance for at least one triple
        # We can check using confidence_history for the entity
        history = bridge.get_confidence_history("D0010")
        assert len(history) > 0
        # At least one triple should have agent_id set
        agents = [h["agent_id"] for h in history if h["agent_id"]]
        assert "econ_specialist" in agents

    def test_hypothesis_transition_provenance(self, bridge):
        """Hypothesis transition stores provenance with reason."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H020",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.35,
            agent_id="orient_phase",
            cycle_id="ooda_cycle_5",
            reason="Passed initial plausibility check",
        )

        # The transition creates a triple for "in_phase → screening"
        timeline = bridge.get_hypothesis_timeline("H020")
        assert len(timeline) >= 1

        # Check provenance via confidence_history
        history = bridge.get_confidence_history("H020")
        assert len(history) >= 1
        # Find the in_phase triple
        phase_triples = [h for h in history if h["predicate"] == "in_phase"]
        assert len(phase_triples) >= 1
        assert phase_triples[0]["confidence_history"][0]["reason"] == "Passed initial plausibility check"

    def test_update_confidence(self, bridge):
        """update_confidence changes the KG triple and appends to provenance history."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.6)],
        )
        triple_ids = bridge.record_causal_edges(
            graph, source_hypothesis="H099", agent_id="agent_a",
        )
        tid = triple_ids[0]

        # Initially confidence should be 0.6
        prov = bridge.get_provenance(tid)
        assert prov["confidence_history"][0]["confidence"] == 0.6

        # Update confidence
        bridge.update_confidence(
            triple_id=tid,
            new_confidence=0.85,
            reason="New evidence from replication study",
            agent_id="agent_b",
        )

        prov_after = bridge.get_provenance(tid)
        assert len(prov_after["confidence_history"]) == 2
        assert prov_after["confidence_history"][1]["confidence"] == 0.85
        assert "replication study" in prov_after["confidence_history"][1]["reason"]
        # agent_id should be updated to the latest
        assert prov_after["agent_id"] == "agent_b"

    def test_update_confidence_multiple_times(self, bridge):
        """Multiple confidence updates produce a full history."""
        graph = MockCausalGraph(
            variables=["P", "Q"],
            edges=[MockCausalEdge(source="P", target="Q", confidence=0.3)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.update_confidence(tid, 0.5, "Partial confirmation")
        bridge.update_confidence(tid, 0.7, "Second confirmation")
        bridge.update_confidence(tid, 0.95, "Strong replication")

        prov = bridge.get_provenance(tid)
        assert len(prov["confidence_history"]) == 4  # initial + 3 updates
        confs = [h["confidence"] for h in prov["confidence_history"]]
        assert confs == [0.3, 0.5, 0.7, 0.95]

    def test_get_provenance_nonexistent(self, bridge):
        """get_provenance returns None for unknown triple_id."""
        assert bridge.get_provenance("nonexistent_triple_id") is None

    def test_get_confidence_history_nonexistent_entity(self, bridge):
        """get_confidence_history returns empty list for unknown entity."""
        assert bridge.get_confidence_history("no_such_entity") == []

    def test_provenance_evidence_chain_merge(self, bridge):
        """Repeated provenance writes merge evidence chains without duplicates."""
        graph = MockCausalGraph(
            variables=["M", "N"],
            edges=[MockCausalEdge(source="M", target="N", confidence=0.5)],
        )
        tid = bridge.record_causal_edges(
            graph,
            evidence_chain=["study_1", "study_2"],
            agent_id="agent_x",
        )[0]

        # Now do a confidence update which re-stores provenance
        bridge.update_confidence(tid, 0.7, "Update", agent_id="agent_y")

        prov = bridge.get_provenance(tid)
        # Original evidence should still be there
        assert "study_1" in prov["evidence_chain"]
        assert "study_2" in prov["evidence_chain"]

    def test_confidence_history_across_entity_triples(self, bridge):
        """get_confidence_history returns data for all triples involving entity."""
        # Create a discovery with multiple triples
        bridge.record_discovery_entity(
            discovery_id="D0050",
            domain="Climate",
            finding_type="trend",
            description="Temperature anomaly",
            hypothesis_id="H050",
            variables=["temperature", "co2"],
            strength=0.9,
            agent_id="climate_agent",
            cycle_id="cycle_99",
        )

        history = bridge.get_confidence_history("D0050")
        # D0050 should be subject in: produced_by, belongs_to_domain, involves_variable x2
        assert len(history) >= 4
        # All triples should have the agent set
        for entry in history:
            assert entry["agent_id"] == "climate_agent"


class TestBiTemporalModel:
    """Tests for the bi-temporal model (Phase 16)."""

    def test_valid_at_set_on_hypothesis_transition(self, bridge):
        """record_hypothesis_transition sets valid_at on the new phase triple."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_001",
            from_phase="PROPOSED",
            to_phase="TESTING",
            confidence=0.6,
            agent_id="orient_agent",
            cycle_id="cycle_10",
        )

        # The new phase triple should have valid_at set
        # (KG normalizes names to lowercase)
        temporal = bridge.get_temporal_triples(include_invalidated=True)
        phase_temporal = [t for t in temporal if t["predicate"] == "in_phase"
                          and t["subject"] == "h_temp_001"]
        assert len(phase_temporal) >= 1
        # The newly created triple should have valid_at set
        assert any(t["valid_at"] is not None for t in phase_temporal)

    def test_invalid_at_set_on_phase_leave(self, bridge):
        """When a hypothesis transitions, the old phase triple gets invalid_at."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_002",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.4,
        )

        # Now transition again — this should invalidate the SCREENING triple
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_002",
            from_phase="SCREENING",
            to_phase="TESTING",
            confidence=0.6,
        )

        # Get all temporal triples including invalidated ones
        # (KG normalizes names to lowercase)
        temporal = bridge.get_temporal_triples(include_invalidated=True)
        screening_triples = [
            t for t in temporal
            if t["subject"] == "h_temp_002"
            and t["predicate"] == "in_phase"
            and t["object"] == "screening"
        ]
        # The screening triple should have invalid_at set
        assert len(screening_triples) >= 1
        assert any(t["invalid_at"] is not None for t in screening_triples)

    def test_get_temporal_triples_excludes_invalidated(self, bridge):
        """get_temporal_triples excludes invalidated triples by default."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_003",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.3,
        )
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_003",
            from_phase="SCREENING",
            to_phase="TESTING",
            confidence=0.5,
        )

        # Default: exclude invalidated
        active = bridge.get_temporal_triples()
        active_phase = [
            t for t in active
            if t["subject"] == "h_temp_003" and t["predicate"] == "in_phase"
        ]
        # Should only have the latest (TESTING) phase — screening is invalidated
        assert all(t["invalid_at"] is None for t in active_phase)

    def test_get_temporal_triples_valid_from_filter(self, bridge):
        """get_temporal_triples filters by valid_from timestamp."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_004",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.3,
        )

        # Query with a valid_from far in the future — should return nothing
        future = "2099-01-01T00:00:00"
        results = bridge.get_temporal_triples(valid_from=future)
        phase_results = [
            r for r in results
            if r["subject"] == "h_temp_004" and r["predicate"] == "in_phase"
        ]
        assert len(phase_results) == 0

    def test_get_temporal_triples_valid_to_filter(self, bridge):
        """get_temporal_triples filters by valid_to timestamp."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_005",
            from_phase="PROPOSED",
            to_phase="SCREENING",
            confidence=0.3,
        )

        # Query with a valid_to far in the past — should return nothing
        past = "2000-01-01T00:00:00"
        results = bridge.get_temporal_triples(valid_to=past)
        phase_results = [
            r for r in results
            if r["subject"] == "h_temp_005" and r["predicate"] == "in_phase"
        ]
        assert len(phase_results) == 0

    def test_invalidate_triple(self, bridge):
        """invalidate_triple sets invalid_at and updates KG triple."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.8)],
        )
        triple_ids = bridge.record_causal_edges(graph, source_hypothesis="H_INV")
        tid = triple_ids[0]

        # Prove it's active
        prov_before = bridge.get_provenance(tid)
        assert prov_before is not None

        # Invalidate
        bridge.invalidate_triple(
            triple_id=tid,
            reason="Contradicted by new evidence",
            invalidated_by="review_agent",
        )

        # Check provenance — should have invalid_at set
        prov_after = bridge.get_provenance(tid)
        assert prov_after is not None
        assert prov_after["invalid_at"] is not None

        # Confidence history should include the invalidation entry (confidence=0)
        last_entry = prov_after["confidence_history"][-1]
        assert last_entry["confidence"] == 0.0
        assert "Contradicted" in last_entry["reason"]

    def test_invalidate_triple_excluded_from_active(self, bridge):
        """Invalidated triples don't show up in active temporal queries."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.7)],
        )
        triple_ids = bridge.record_causal_edges(graph, source_hypothesis="H_INV2")

        # Before invalidation: should be in active results
        active_before = bridge.get_temporal_triples()
        active_ids_before = {t["triple_id"] for t in active_before}
        assert triple_ids[0] in active_ids_before

        bridge.invalidate_triple(triple_ids[0], reason="Outdated")

        # After: should NOT be in active results
        active_after = bridge.get_temporal_triples()
        active_ids_after = {t["triple_id"] for t in active_after}
        assert triple_ids[0] not in active_ids_after

        # But should be in include_invalidated=True results
        all_triples = bridge.get_temporal_triples(include_invalidated=True)
        all_ids = {t["triple_id"] for t in all_triples}
        assert triple_ids[0] in all_ids

    def test_schema_migration_adds_temporal_columns(self, bridge):
        """Schema migration adds valid_at, invalid_at, expired_at to existing DB."""
        import sqlite3
        conn = sqlite3.connect(bridge.config.kg_db_path)
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(triple_provenance)"
        ).fetchall()}
        conn.close()
        assert "valid_at" in cols
        assert "invalid_at" in cols
        assert "expired_at" in cols

    def test_temporal_triple_returns_all_fields(self, bridge):
        """get_temporal_triples returns all expected fields."""
        bridge.record_hypothesis_transition(
            hypothesis_id="H_TEMP_006",
            from_phase="PROPOSED",
            to_phase="TESTING",
            confidence=0.5,
            agent_id="test_agent",
            cycle_id="cycle_1",
            reason="Initial test",
        )

        results = bridge.get_temporal_triples()
        phase_results = [
            r for r in results
            if r["subject"] == "h_temp_006" and r["predicate"] == "in_phase"
        ]
        assert len(phase_results) >= 1
        r = phase_results[0]
        # Check all expected fields are present
        for key in [
            "triple_id", "subject", "predicate", "object", "confidence",
            "valid_at", "invalid_at", "agent_id", "cycle_id",
            "confidence_history", "evidence_chain",
        ]:
            assert key in r


class TestInvalidationExtended:
    """Test invalidation sets expired_at and preserves full history."""

    def test_invalidate_sets_expired_at(self, bridge):
        """invalidate_triple sets expired_at in provenance."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.8)],
        )
        tid = bridge.record_causal_edges(graph, source_hypothesis="H_EXP")[0]

        bridge.invalidate_triple(
            triple_id=tid,
            reason="Superseded by new model",
            invalidated_by="agent_a",
        )

        prov = bridge.get_provenance(tid)
        assert prov is not None
        assert prov["expired_at"] is not None
        assert prov["invalid_at"] is not None

    def test_invalidate_does_not_delete(self, bridge):
        """Invalidated triples are still retrievable via get_provenance."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.7)],
        )
        tid = bridge.record_causal_edges(graph, source_hypothesis="H_DEL")[0]

        bridge.invalidate_triple(tid, reason="Obsolete")

        # Provenance must still exist
        prov = bridge.get_provenance(tid)
        assert prov is not None

        # Triple must still be in KG (just with valid_to set)
        import sqlite3
        conn = sqlite3.connect(bridge.config.kg_db_path)
        row = conn.execute("SELECT * FROM triples WHERE id = ?", (tid,)).fetchone()
        conn.close()
        assert row is not None

    def test_invalidate_evidence_chain_entry(self, bridge):
        """Invalidation appends 'Invalidated: {reason}' to evidence chain."""
        graph = MockCausalGraph(
            variables=["P", "Q"],
            edges=[MockCausalEdge(source="P", target="Q", confidence=0.6)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.invalidate_triple(tid, reason="Contradicted by replication")

        prov = bridge.get_provenance(tid)
        assert any(
            "Invalidated" in e and "Contradicted by replication" in e
            for e in prov["evidence_chain"]
        )


class TestStatementClassification:
    """Test statement_type and temporal_type columns."""

    def test_default_statement_type_is_fact(self, bridge):
        """Default statement_type is 'fact' when not specified."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.8)],
        )
        tid = bridge.record_causal_edges(graph)[0]
        prov = bridge.get_provenance(tid)
        assert prov["statement_type"] == "fact"

    def test_default_temporal_type_is_static(self, bridge):
        """Default temporal_type is 'static' when not specified."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.8)],
        )
        tid = bridge.record_causal_edges(graph)[0]
        prov = bridge.get_provenance(tid)
        assert prov["temporal_type"] == "static"

    def test_store_prediction(self, bridge):
        """Can store a triple with statement_type='prediction'."""
        graph = MockCausalGraph(
            variables=["GDP", "unemployment"],
            edges=[MockCausalEdge(source="GDP", target="unemployment", confidence=0.4)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        # Update provenance with prediction classification
        bridge._store_provenance(
            triple_id=tid,
            statement_type="prediction",
            temporal_type="dynamic",
            confidence=0.4,
            reason="Forecast",
        )

        prov = bridge.get_provenance(tid)
        assert prov["statement_type"] == "prediction"
        assert prov["temporal_type"] == "dynamic"

    def test_store_opinion(self, bridge):
        """Can store a triple with statement_type='opinion'."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.3)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge._store_provenance(
            triple_id=tid,
            statement_type="opinion",
            temporal_type="atemporal",
            confidence=0.3,
            reason="Expert opinion",
        )

        prov = bridge.get_provenance(tid)
        assert prov["statement_type"] == "opinion"
        assert prov["temporal_type"] == "atemporal"

    def test_classification_round_trip(self, bridge):
        """Statement/temporal types survive a full round trip."""
        graph = MockCausalGraph(
            variables=["M", "N"],
            edges=[MockCausalEdge(source="M", target="N", confidence=0.7)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge._store_provenance(
            triple_id=tid,
            statement_type="prediction",
            temporal_type="dynamic",
            confidence=0.7,
            reason="Update",
        )

        # Read back from multiple APIs
        prov = bridge.get_provenance(tid)
        assert prov["statement_type"] == "prediction"
        assert prov["temporal_type"] == "dynamic"

        temporal = bridge.get_temporal_triples()
        matching = [t for t in temporal if t["triple_id"] == tid]
        assert len(matching) == 1
        assert matching[0]["statement_type"] == "prediction"
        assert matching[0]["temporal_type"] == "dynamic"

    def test_schema_migration_adds_classification_columns(self, bridge):
        """Schema migration adds statement_type, temporal_type columns."""
        import sqlite3
        conn = sqlite3.connect(bridge.config.kg_db_path)
        cols = {row[1] for row in conn.execute(
            "PRAGMA table_info(triple_provenance)"
        ).fetchall()}
        conn.close()
        assert "statement_type" in cols
        assert "temporal_type" in cols


class TestTemporalQueries:
    """Test get_valid_triples, get_invalidated_triples, etc."""

    def test_get_valid_triples_returns_active(self, bridge):
        """get_valid_triples returns triples without invalidation."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.8)],
        )
        tid = bridge.record_causal_edges(graph, source_hypothesis="H_VALID")[0]

        valid = bridge.get_valid_triples()
        valid_ids = {t["triple_id"] for t in valid}
        assert tid in valid_ids

    def test_get_valid_triples_excludes_invalidated(self, bridge):
        """get_valid_triples does not return invalidated triples."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.7)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.invalidate_triple(tid, reason="Outdated")

        valid = bridge.get_valid_triples()
        valid_ids = {t["triple_id"] for t in valid}
        assert tid not in valid_ids

    def test_get_valid_triples_as_of(self, bridge):
        """get_valid_triples(as_of=...) checks temporal validity."""
        graph = MockCausalGraph(
            variables=["P", "Q"],
            edges=[MockCausalEdge(source="P", target="Q", confidence=0.5)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.invalidate_triple(tid, reason="Expired")

        # Query as_of a time far in the future — triple was already invalidated
        future = "2099-01-01T00:00:00"
        valid_future = bridge.get_valid_triples(as_of=future)
        valid_future_ids = {t["triple_id"] for t in valid_future}
        assert tid not in valid_future_ids

        # Query as_of a time in the past — triple should have been valid then
        past = "2000-01-01T00:00:00"
        valid_past = bridge.get_valid_triples(as_of=past)
        valid_past_ids = {t["triple_id"] for t in valid_past}
        assert tid in valid_past_ids

    def test_get_invalidated_triples_returns_invalidated(self, bridge):
        """get_invalidated_triples returns only invalidated triples."""
        graph = MockCausalGraph(
            variables=["M", "N"],
            edges=[
                MockCausalEdge(source="M", target="N", confidence=0.6),
                MockCausalEdge(source="N", target="M", confidence=0.5),
            ],
        )
        tids = bridge.record_causal_edges(graph)

        # Invalidate the first one
        bridge.invalidate_triple(tids[0], reason="Contradicted")

        invalidated = bridge.get_invalidated_triples()
        inv_ids = {t["triple_id"] for t in invalidated}
        assert tids[0] in inv_ids
        assert tids[1] not in inv_ids

    def test_get_invalidated_triples_since(self, bridge):
        """get_invalidated_triples(since=...) filters by timestamp."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.9)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.invalidate_triple(tid, reason="Old news")

        # Query since far future — nothing should match
        future = "2099-01-01T00:00:00"
        result = bridge.get_invalidated_triples(since=future)
        result_ids = {t["triple_id"] for t in result}
        assert tid not in result_ids

    def test_get_temporal_history(self, bridge):
        """get_temporal_history returns full confidence + invalidation chain."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", confidence=0.5)],
        )
        tid = bridge.record_causal_edges(graph)[0]

        bridge.update_confidence(tid, 0.7, "Replicated")
        bridge.update_confidence(tid, 0.9, "Strong evidence")
        bridge.invalidate_triple(tid, reason="Superseded by X→Z model")

        history = bridge.get_temporal_history(tid)
        assert history is not None
        assert len(history["confidence_history"]) == 4  # initial + 2 updates + invalidation
        assert history["invalid_at"] is not None
        assert any(
            "Invalidated" in e for e in history["invalidation_chain"]
        )

    def test_get_temporal_history_nonexistent(self, bridge):
        """get_temporal_history returns None for unknown triple."""
        assert bridge.get_temporal_history("nonexistent_id") is None

    def test_get_triples_by_type(self, bridge):
        """get_triples_by_type filters by statement_type."""
        graph1 = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", confidence=0.9)],
        )
        graph2 = MockCausalGraph(
            variables=["C", "D"],
            edges=[MockCausalEdge(source="C", target="D", confidence=0.4)],
        )
        tid1 = bridge.record_causal_edges(graph1)[0]
        tid2 = bridge.record_causal_edges(graph2)[0]

        # Classify tid2 as a prediction
        bridge._store_provenance(
            triple_id=tid2,
            statement_type="prediction",
            temporal_type="dynamic",
            confidence=0.4,
            reason="Forecast",
        )

        facts = bridge.get_triples_by_type("fact")
        fact_ids = {t["triple_id"] for t in facts}
        assert tid1 in fact_ids

        predictions = bridge.get_triples_by_type("prediction")
        pred_ids = {t["triple_id"] for t in predictions}
        assert tid2 in pred_ids
        assert tid1 not in pred_ids


class TestContradictionDetection:
    """Test check_contradictions method."""

    def test_no_contradictions_returns_new(self, bridge):
        """When no conflicting triples exist, returns 'new' action."""
        results = bridge.check_contradictions(
            new_subject="gdp",
            new_predicate="causes",
            new_object="inflation",
            confidence=0.8,
        )
        assert len(results) == 1
        assert results[0]["action"] == "new"

    def test_contradiction_invalidates_weaker(self, bridge):
        """Higher confidence new triple invalidates lower confidence existing."""
        # Create existing triple: gdp causes unemployment (conf=0.5)
        graph = MockCausalGraph(
            variables=["gdp", "unemployment"],
            edges=[MockCausalEdge(source="gdp", target="unemployment",
                                  edge_type="→", confidence=0.5)],
        )
        old_tid = bridge.record_causal_edges(graph)[0]

        # Now check contradictions with a new object
        results = bridge.check_contradictions(
            new_subject="gdp",
            new_predicate="causes",
            new_object="inflation",
            confidence=0.8,
        )

        assert len(results) >= 1
        invalidated = [r for r in results if r["action"] == "invalidated"]
        assert len(invalidated) == 1
        assert invalidated[0]["triple_id"] == old_tid

        # Old triple should be invalidated
        prov = bridge.get_provenance(old_tid)
        assert prov["invalid_at"] is not None

    def test_contradiction_keeps_stronger(self, bridge):
        """Lower confidence new triple does NOT invalidate higher confidence existing."""
        graph = MockCausalGraph(
            variables=["X", "Y"],
            edges=[MockCausalEdge(source="X", target="Y", edge_type="→",
                                  confidence=0.9)],
        )
        old_tid = bridge.record_causal_edges(graph)[0]

        results = bridge.check_contradictions(
            new_subject="X",
            new_predicate="causes",
            new_object="Z",
            confidence=0.3,
        )

        kept = [r for r in results if r["action"] == "kept"]
        assert len(kept) == 1
        assert kept[0]["triple_id"] == old_tid

        # Old triple should NOT be invalidated
        prov = bridge.get_provenance(old_tid)
        assert prov["invalid_at"] is None

    def test_contradiction_ignores_same_object(self, bridge):
        """Same subject+predicate+object does not trigger contradiction."""
        graph = MockCausalGraph(
            variables=["A", "B"],
            edges=[MockCausalEdge(source="A", target="B", edge_type="→",
                                  confidence=0.7)],
        )
        bridge.record_causal_edges(graph)

        results = bridge.check_contradictions(
            new_subject="A",
            new_predicate="causes",
            new_object="B",
            confidence=0.9,
        )

        # Should not find the same-object triple as a contradiction
        assert all(r["action"] != "invalidated" for r in results)

    def test_contradiction_multiple_existing(self, bridge):
        """Multiple conflicting triples all get checked."""
        graph = MockCausalGraph(
            variables=["temp", "ice", "rain"],
            edges=[
                MockCausalEdge(source="temp", target="ice", edge_type="→",
                               confidence=0.4),
                MockCausalEdge(source="temp", target="rain", edge_type="→",
                               confidence=0.3),
            ],
        )
        old_tids = bridge.record_causal_edges(graph)

        results = bridge.check_contradictions(
            new_subject="temp",
            new_predicate="causes",
            new_object="humidity",
            confidence=0.8,
        )

        # Both existing should be invalidated (conf 0.4 and 0.3 < 0.8)
        invalidated = [r for r in results if r["action"] == "invalidated"]
        assert len(invalidated) == 2
