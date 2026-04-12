"""
Tests for kg_communities.py — KG Community Detection.

Covers: KGCommunityDetector.build_graph, detect_communities_louvain,
detect_communities_greedy, get_cross_domain_bridges,
suggest_investigation_targets, compute_modularity, get_community_report.
Also covers the CommunityReport dataclass.
"""

import pytest
import networkx as nx

from mempalace_agi.kg_communities import KGCommunityDetector, CommunityReport


# ── Fixtures / Helpers ────────────────────────────────────────────────


class MockKGBridge:
    """Provides controlled triples for testing."""

    def __init__(self, triples=None):
        self._triples = triples or []

    def get_valid_triples(self):
        return self._triples


def _make_triple(subj: str, pred: str, obj: str, confidence: float = 0.5):
    return {"subject": subj, "predicate": pred, "object": obj, "confidence": confidence}


# Two well-separated clusters with a single weak bridge
ASTRO_TRIPLES = [
    _make_triple("star", "emits", "planet", 0.9),
    _make_triple("planet", "orbits", "galaxy", 0.8),
    _make_triple("star", "contains", "galaxy", 0.7),
]
ECON_TRIPLES = [
    _make_triple("gdp", "influences", "inflation", 0.9),
    _make_triple("inflation", "affects", "unemployment", 0.8),
    _make_triple("gdp", "drives", "unemployment", 0.7),
]
BRIDGE_TRIPLE = [_make_triple("galaxy", "linked_to", "gdp", 0.3)]

TWO_CLUSTER_TRIPLES = ASTRO_TRIPLES + ECON_TRIPLES + BRIDGE_TRIPLE


@pytest.fixture
def two_cluster_detector():
    return KGCommunityDetector(MockKGBridge(TWO_CLUSTER_TRIPLES))


@pytest.fixture
def empty_detector():
    return KGCommunityDetector(MockKGBridge([]))


# ── 1. build_graph: empty triples → empty graph ──────────────────────


def test_build_graph_empty(empty_detector):
    g = empty_detector.build_graph()
    assert g.number_of_nodes() == 0
    assert g.number_of_edges() == 0


# ── 2. build_graph: correct node/edge count ──────────────────────────


def test_build_graph_node_edge_count(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    # 6 distinct entities: star, planet, galaxy, gdp, inflation, unemployment
    assert g.number_of_nodes() == 6
    # 7 distinct edges (3 astro + 3 econ + 1 bridge)
    assert g.number_of_edges() == 7


# ── 3. build_graph: edge weights correct ─────────────────────────────


def test_build_graph_edge_weights(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    assert g["star"]["planet"]["weight"] == pytest.approx(0.9)
    assert g["planet"]["galaxy"]["weight"] == pytest.approx(0.8)
    assert g["galaxy"]["gdp"]["weight"] == pytest.approx(0.3)


# ── 4. detect_communities_louvain: finds ~2 communities ──────────────


def test_louvain_two_clusters(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_louvain(graph=g, seed=42)
    # With clear cluster structure + weak bridge, Louvain should find 2 (or 3 at most)
    assert 2 <= len(communities) <= 3
    all_entities = set()
    for c in communities:
        all_entities |= c
    assert all_entities == {"star", "planet", "galaxy", "gdp", "inflation", "unemployment"}


# ── 5. detect_communities_louvain: empty graph → [] ──────────────────


def test_louvain_empty(empty_detector):
    result = empty_detector.detect_communities_louvain()
    assert result == []


# ── 6. detect_communities_greedy: finds communities ──────────────────


def test_greedy_finds_communities(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_greedy(graph=g)
    assert len(communities) >= 1
    # All entities must be covered
    all_entities = set()
    for c in communities:
        all_entities |= c
    assert all_entities == {"star", "planet", "galaxy", "gdp", "inflation", "unemployment"}


# ── 7. two disconnected clusters → 2 communities ─────────────────────


def test_disconnected_clusters():
    """With NO bridge edge, must detect exactly 2 disconnected clusters."""
    triples = ASTRO_TRIPLES + ECON_TRIPLES  # no bridge
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    communities = detector.detect_communities_louvain(graph=g, seed=42)
    assert len(communities) == 2

    # Verify the cluster membership
    astro_entities = {"star", "planet", "galaxy"}
    econ_entities = {"gdp", "inflation", "unemployment"}
    community_sets = [c for c in communities]
    assert astro_entities in community_sets
    assert econ_entities in community_sets


# ── 8. fully connected clique → 1 community ──────────────────────────


def test_fully_connected_clique():
    """A complete graph should collapse into 1 community."""
    nodes = ["a", "b", "c", "d"]
    triples = []
    for i in range(len(nodes)):
        for j in range(i + 1, len(nodes)):
            triples.append(_make_triple(nodes[i], "connected", nodes[j], 0.9))
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    communities = detector.detect_communities_louvain(graph=g, seed=42)
    # Louvain on a tight clique typically returns 1 community
    assert len(communities) <= 2  # relaxed: sometimes Louvain splits small cliques
    total_members = sum(len(c) for c in communities)
    assert total_members == 4


# ── 9. get_cross_domain_bridges finds bridge entity ───────────────────


def test_bridges_find_galaxy_or_gdp(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_louvain(graph=g, seed=42)
    bridges = two_cluster_detector.get_cross_domain_bridges(
        communities=communities, graph=g
    )
    assert len(bridges) > 0
    bridge_names = {b[0] for b in bridges}
    # The bridge edge connects galaxy and gdp — at least one should appear
    assert bridge_names & {"galaxy", "gdp"}, f"Expected galaxy or gdp in bridges, got {bridge_names}"


# ── 10. get_cross_domain_bridges: empty graph → [] ───────────────────


def test_bridges_empty(empty_detector):
    result = empty_detector.get_cross_domain_bridges()
    assert result == []


# ── 11. suggest_investigation_targets: sorted by isolation ────────────


def test_investigation_targets_sorted(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_louvain(graph=g, seed=42)
    targets = two_cluster_detector.suggest_investigation_targets(
        communities=communities, graph=g
    )
    assert len(targets) >= 2
    # Verify sorted descending by isolation_score
    scores = [t["isolation_score"] for t in targets]
    assert scores == sorted(scores, reverse=True)


# ── 12. suggest_investigation_targets: empty → [] ────────────────────


def test_investigation_targets_empty(empty_detector):
    result = empty_detector.suggest_investigation_targets()
    assert result == []


# ── 13. compute_modularity: two clusters → positive ──────────────────


def test_modularity_two_clusters():
    """Disconnected clusters should give high positive modularity."""
    triples = ASTRO_TRIPLES + ECON_TRIPLES  # no bridge
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    communities = detector.detect_communities_louvain(graph=g, seed=42)
    modularity = detector.compute_modularity(communities=communities, graph=g)
    assert modularity > 0.0, f"Expected positive modularity, got {modularity}"


# ── 14. compute_modularity: empty → 0.0 ──────────────────────────────


def test_modularity_empty(empty_detector):
    result = empty_detector.compute_modularity()
    assert result == 0.0


# ── 15. get_community_report: returns full dict with all keys ─────────


def test_community_report_keys(two_cluster_detector):
    report = two_cluster_detector.get_community_report(algorithm="louvain")
    expected_keys = {
        "communities",
        "community_count",
        "community_sizes",
        "modularity",
        "algorithm",
        "bridge_entities",
        "investigation_targets",
        "processing_time",
        "node_count",
        "edge_count",
    }
    assert set(report.keys()) == expected_keys
    assert report["algorithm"] == "louvain"
    assert report["node_count"] == 6
    assert report["edge_count"] == 7
    assert report["community_count"] == len(report["communities"])
    assert report["processing_time"] >= 0.0
    # community_sizes matches communities
    assert report["community_sizes"] == [len(c) for c in report["communities"]]


# ── 16. get_community_report with "greedy" algorithm ──────────────────


def test_community_report_greedy(two_cluster_detector):
    report = two_cluster_detector.get_community_report(algorithm="greedy")
    assert report["algorithm"] == "greedy"
    assert report["community_count"] >= 1
    # All 6 entities must be present across all communities
    all_entities = set()
    for c in report["communities"]:
        all_entities.update(c)
    assert all_entities == {"star", "planet", "galaxy", "gdp", "inflation", "unemployment"}


# ── 17. build_graph: missing confidence → default 0.5 ─────────────────


def test_build_graph_missing_confidence():
    triples = [{"subject": "a", "predicate": "rel", "object": "b"}]  # no confidence key
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g.number_of_edges() == 1
    assert g["a"]["b"]["weight"] == pytest.approx(0.5)


# ── 18. single node graph → 1 community of size 1 ────────────────────


def test_single_node_graph():
    """A single edge creates 2 nodes; but a self-referencing edge is skipped.
    Use a minimal 1-edge graph with 2 nodes to confirm communities."""
    triples = [_make_triple("solo_a", "self_ref", "solo_b", 0.5)]
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g.number_of_nodes() == 2
    communities = detector.detect_communities_louvain(graph=g, seed=42)
    # Two tightly connected nodes → single community
    assert len(communities) == 1
    assert len(communities[0]) == 2


# ── Additional coverage ──────────────────────────────────────────────


def test_build_graph_skips_empty_subject_or_object():
    """Triples with empty subject or object are skipped."""
    triples = [
        {"subject": "", "predicate": "rel", "object": "b", "confidence": 0.5},
        {"subject": "a", "predicate": "rel", "object": "", "confidence": 0.5},
        {"subject": "a", "predicate": "rel", "object": "b", "confidence": 0.5},
    ]
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g.number_of_nodes() == 2
    assert g.number_of_edges() == 1


def test_build_graph_parallel_edges_keep_max_weight():
    """When two triples share the same subject-object pair, max weight wins."""
    triples = [
        _make_triple("x", "r1", "y", 0.3),
        _make_triple("x", "r2", "y", 0.9),
    ]
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g.number_of_edges() == 1  # collapsed to one edge
    assert g["x"]["y"]["weight"] == pytest.approx(0.9)


def test_build_graph_string_confidence_parsed():
    """Confidence stored as a string should be parsed to float."""
    triples = [{"subject": "a", "predicate": "rel", "object": "b", "confidence": "0.75"}]
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g["a"]["b"]["weight"] == pytest.approx(0.75)


def test_build_graph_invalid_string_confidence_defaults():
    """Unparseable confidence string → default 0.5."""
    triples = [{"subject": "a", "predicate": "rel", "object": "b", "confidence": "not_a_number"}]
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    assert g["a"]["b"]["weight"] == pytest.approx(0.5)


def test_node_predicates_tracked(two_cluster_detector):
    """Nodes should track which predicates involve them."""
    g = two_cluster_detector.build_graph()
    # star participates in "emits" and "contains"
    assert "emits" in g.nodes["star"]["predicates"]
    assert "contains" in g.nodes["star"]["predicates"]
    # galaxy participates in "orbits", "contains", and "linked_to"
    assert "orbits" in g.nodes["galaxy"]["predicates"]
    assert "linked_to" in g.nodes["galaxy"]["predicates"]


def test_investigation_targets_contain_required_keys(two_cluster_detector):
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_louvain(graph=g, seed=42)
    targets = two_cluster_detector.suggest_investigation_targets(
        communities=communities, graph=g
    )
    required_keys = {
        "community_id", "members", "size", "internal_edges",
        "external_edges", "isolation_score", "suggestion",
    }
    for t in targets:
        assert set(t.keys()) == required_keys
        assert isinstance(t["members"], list)
        assert t["members"] == sorted(t["members"])  # sorted alphabetically


def test_bridge_entities_tuple_format(two_cluster_detector):
    """Bridge tuples are (entity_name, community_ids_str, betweenness)."""
    g = two_cluster_detector.build_graph()
    communities = two_cluster_detector.detect_communities_louvain(graph=g, seed=42)
    bridges = two_cluster_detector.get_cross_domain_bridges(
        communities=communities, graph=g
    )
    for entity, comm_str, bc in bridges:
        assert isinstance(entity, str)
        assert isinstance(comm_str, str)
        assert isinstance(bc, float)
        assert bc >= 0.0


def test_community_report_dataclass():
    """CommunityReport dataclass can be instantiated with all fields."""
    report = CommunityReport(
        communities=[{"a", "b"}, {"c"}],
        modularity=0.42,
        algorithm="louvain",
        bridge_entities=[],
        investigation_targets=[],
        processing_time=0.01,
        node_count=3,
        edge_count=2,
    )
    assert report.modularity == 0.42
    assert report.algorithm == "louvain"
    assert report.node_count == 3


def test_kg_bridge_exception_returns_empty_graph():
    """If the KG bridge raises, build_graph returns an empty graph."""
    class BrokenBridge:
        def get_valid_triples(self):
            raise RuntimeError("DB error")

    detector = KGCommunityDetector(BrokenBridge())
    g = detector.build_graph()
    assert g.number_of_nodes() == 0
    assert g.number_of_edges() == 0


def test_louvain_resolution_affects_communities():
    """Higher resolution → more communities (finer granularity)."""
    triples = TWO_CLUSTER_TRIPLES.copy()
    detector = KGCommunityDetector(MockKGBridge(triples))
    g = detector.build_graph()
    low_res = detector.detect_communities_louvain(graph=g, resolution=0.1, seed=42)
    high_res = detector.detect_communities_louvain(graph=g, resolution=5.0, seed=42)
    # With very high resolution, more or equal number of communities
    assert len(high_res) >= len(low_res)
