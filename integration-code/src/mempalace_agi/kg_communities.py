"""
Knowledge Graph Community Detection.

Detects communities/clusters in the MemPalace-AGI knowledge graph using
networkx built-in algorithms (Louvain, greedy modularity). Identifies
bridge entities that connect different research domains and suggests
under-connected communities as investigation targets.

Adapted from ASI:BUILD (https://gitlab.com/asi-build/asi-build), MIT License.
Original: graph_intelligence/community_detection.py

Unlike the ASI:BUILD version, this operates on our SQLite-backed KG
via KnowledgeGraphBridge rather than a Memgraph database, and uses
networkx.community built-ins rather than the hand-rolled Louvain.
"""

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import networkx as nx

logger = logging.getLogger("mempalace_agi")

# networkx.algorithms.community — available since networkx 2.6+
try:
    from networkx.algorithms.community import louvain_communities
    _HAS_LOUVAIN = True
except ImportError:
    _HAS_LOUVAIN = False

try:
    from networkx.algorithms.community import greedy_modularity_communities
    _HAS_GREEDY = True
except ImportError:
    _HAS_GREEDY = False


@dataclass
class CommunityReport:
    """Full community detection report."""
    communities: List[Set[str]]
    modularity: float
    algorithm: str
    bridge_entities: List[Dict[str, Any]]
    investigation_targets: List[Dict[str, Any]]
    processing_time: float
    node_count: int
    edge_count: int


class KGCommunityDetector:
    """
    Detect communities/clusters in the knowledge graph.

    Uses networkx built-in algorithms over our SQLite-backed KG.
    """

    def __init__(self, kg_bridge: Any):
        """
        Args:
            kg_bridge: KnowledgeGraphBridge instance (has .get_valid_triples()).
        """
        self._kg_bridge = kg_bridge

    # ── Graph Construction ─────────────────────────────────────────────

    def build_graph(self) -> nx.Graph:
        """Convert KG triples to an undirected networkx graph.

        Nodes = entities, edges = relationships.
        Edge weight = confidence (default 0.5 if missing).
        Node attribute 'predicates' tracks which predicates involve that entity.
        """
        g = nx.Graph()

        try:
            triples = self._kg_bridge.get_valid_triples()
        except Exception:
            triples = []

        for triple in triples:
            subj = triple.get("subject", "")
            obj = triple.get("object", "")
            pred = triple.get("predicate", "related_to")
            conf = triple.get("confidence", 0.5)
            if isinstance(conf, str):
                try:
                    conf = float(conf)
                except (ValueError, TypeError):
                    conf = 0.5

            if not subj or not obj:
                continue

            # Add nodes with predicate tracking
            if subj not in g:
                g.add_node(subj, predicates=set())
            g.nodes[subj]["predicates"].add(pred)

            if obj not in g:
                g.add_node(obj, predicates=set())
            g.nodes[obj]["predicates"].add(pred)

            # Add or update edge (max weight for parallel edges)
            if g.has_edge(subj, obj):
                existing_w = g[subj][obj].get("weight", 0.0)
                g[subj][obj]["weight"] = max(existing_w, conf)
            else:
                g.add_edge(subj, obj, weight=conf, predicate=pred)

        logger.info("Built KG graph: %d nodes, %d edges", g.number_of_nodes(), g.number_of_edges())
        return g

    # ── Community Detection ────────────────────────────────────────────

    def detect_communities_louvain(
        self,
        resolution: float = 1.0,
        seed: Optional[int] = None,
        graph: Optional[nx.Graph] = None,
    ) -> List[Set[str]]:
        """Louvain community detection via networkx.community.louvain_communities.

        Returns:
            List of sets of entity names, one set per community.
        """
        if graph is None:
            graph = self.build_graph()

        if graph.number_of_nodes() == 0:
            return []

        if _HAS_LOUVAIN:
            communities = louvain_communities(
                graph, weight="weight", resolution=resolution, seed=seed
            )
            return [set(c) for c in communities]
        else:
            # Fallback to greedy
            logger.warning("Louvain not available, falling back to greedy modularity")
            return self.detect_communities_greedy(graph=graph)

    def detect_communities_greedy(
        self,
        graph: Optional[nx.Graph] = None,
    ) -> List[Set[str]]:
        """Greedy modularity community detection via networkx.

        Returns:
            List of sets of entity names, one set per community.
        """
        if graph is None:
            graph = self.build_graph()

        if graph.number_of_nodes() == 0:
            return []

        if _HAS_GREEDY:
            communities = greedy_modularity_communities(graph, weight="weight")
            return [set(c) for c in communities]
        else:
            # Ultra-fallback: connected components
            logger.warning("Greedy modularity not available, using connected components")
            return [set(c) for c in nx.connected_components(graph)]

    # ── Bridge Entities ────────────────────────────────────────────────

    def get_cross_domain_bridges(
        self,
        top_n: int = 10,
        communities: Optional[List[Set[str]]] = None,
        graph: Optional[nx.Graph] = None,
    ) -> List[Tuple[str, str, float]]:
        """Find entities that bridge multiple communities.

        High betweenness centrality entities are "vocabulary bridges" that
        connect otherwise-separate knowledge clusters.

        Returns:
            List of (entity, community_ids_str, betweenness) sorted by
            betweenness descending.
        """
        if graph is None:
            graph = self.build_graph()
        if communities is None:
            communities = self.detect_communities_louvain(graph=graph)

        if graph.number_of_nodes() == 0:
            return []

        # Build entity → community map
        entity_community: Dict[str, Set[int]] = defaultdict(set)
        for idx, community in enumerate(communities):
            for entity in community:
                entity_community[entity].add(idx)

        # Betweenness centrality
        betweenness = nx.betweenness_centrality(graph, weight="weight")

        # Filter to entities in multiple communities or with high betweenness
        bridges: List[Tuple[str, str, float]] = []
        for entity, bc in betweenness.items():
            comm_ids = entity_community.get(entity, set())
            # A bridge entity connects to nodes in multiple communities
            neighbor_communities: Set[int] = set()
            for neighbor in graph.neighbors(entity):
                for cid in entity_community.get(neighbor, set()):
                    neighbor_communities.add(cid)
            neighbor_communities |= comm_ids

            if len(neighbor_communities) > 1 or bc > 0.0:
                comm_str = ",".join(str(c) for c in sorted(neighbor_communities))
                bridges.append((entity, comm_str, bc))

        bridges.sort(key=lambda t: t[2], reverse=True)
        return bridges[:top_n]

    # ── Investigation Targets ──────────────────────────────────────────

    def suggest_investigation_targets(
        self,
        communities: Optional[List[Set[str]]] = None,
        graph: Optional[nx.Graph] = None,
    ) -> List[dict]:
        """Suggest under-connected communities as investigation targets.

        Communities with few external edges may have undiscovered
        cross-domain links — these are high-value investigation targets.

        Returns:
            List of dicts: {community_id, members, size, internal_edges,
                           external_edges, isolation_score, suggestion}
        """
        if graph is None:
            graph = self.build_graph()
        if communities is None:
            communities = self.detect_communities_louvain(graph=graph)

        if not communities:
            return []

        # Build entity → community index
        entity_comm: Dict[str, int] = {}
        for idx, comm in enumerate(communities):
            for entity in comm:
                entity_comm[entity] = idx

        targets: List[dict] = []
        for idx, comm in enumerate(communities):
            internal = 0
            external = 0
            for entity in comm:
                if entity not in graph:
                    continue
                for neighbor in graph.neighbors(entity):
                    if neighbor in comm:
                        internal += 1
                    else:
                        external += 1
            # Each internal edge counted twice
            internal = internal // 2

            total_edges = internal + external
            isolation = 1.0 - (external / total_edges) if total_edges > 0 else 1.0

            suggestion = ""
            if isolation > 0.8 and len(comm) >= 2:
                suggestion = "Highly isolated — investigate cross-domain links"
            elif isolation > 0.5:
                suggestion = "Moderately isolated — potential bridging opportunities"
            elif len(comm) <= 1:
                suggestion = "Singleton — may need more data"

            targets.append({
                "community_id": idx,
                "members": sorted(comm),
                "size": len(comm),
                "internal_edges": internal,
                "external_edges": external,
                "isolation_score": round(isolation, 3),
                "suggestion": suggestion,
            })

        # Sort by isolation (most isolated first)
        targets.sort(key=lambda t: t["isolation_score"], reverse=True)
        return targets

    # ── Modularity ─────────────────────────────────────────────────────

    def compute_modularity(
        self,
        communities: Optional[List[Set[str]]] = None,
        graph: Optional[nx.Graph] = None,
    ) -> float:
        """Compute modularity score of the partition.

        Returns:
            Modularity in [-0.5, 1.0]. Higher = better partition.
        """
        if graph is None:
            graph = self.build_graph()
        if communities is None:
            communities = self.detect_communities_louvain(graph=graph)

        if not communities or graph.number_of_edges() == 0:
            return 0.0

        try:
            from networkx.algorithms.community.quality import modularity as nx_modularity
            return nx_modularity(graph, communities, weight="weight")
        except Exception:
            return 0.0

    # ── Full Report ────────────────────────────────────────────────────

    def get_community_report(
        self,
        algorithm: str = "louvain",
        resolution: float = 1.0,
    ) -> dict:
        """Full community detection report.

        Args:
            algorithm: "louvain" or "greedy"
            resolution: Louvain resolution parameter

        Returns:
            Dict with communities, sizes, bridges, modularity, targets.
        """
        t0 = time.time()
        graph = self.build_graph()

        if algorithm == "greedy":
            communities = self.detect_communities_greedy(graph=graph)
        else:
            communities = self.detect_communities_louvain(
                graph=graph, resolution=resolution
            )

        modularity = self.compute_modularity(communities=communities, graph=graph)
        bridges = self.get_cross_domain_bridges(
            communities=communities, graph=graph
        )
        targets = self.suggest_investigation_targets(
            communities=communities, graph=graph
        )
        elapsed = time.time() - t0

        report = CommunityReport(
            communities=communities,
            modularity=modularity,
            algorithm=algorithm,
            bridge_entities=[
                {"entity": e, "communities": c, "betweenness": round(b, 4)}
                for e, c, b in bridges
            ],
            investigation_targets=targets,
            processing_time=round(elapsed, 3),
            node_count=graph.number_of_nodes(),
            edge_count=graph.number_of_edges(),
        )

        return {
            "communities": [sorted(c) for c in report.communities],
            "community_count": len(report.communities),
            "community_sizes": [len(c) for c in report.communities],
            "modularity": report.modularity,
            "algorithm": report.algorithm,
            "bridge_entities": report.bridge_entities,
            "investigation_targets": report.investigation_targets,
            "processing_time": report.processing_time,
            "node_count": report.node_count,
            "edge_count": report.edge_count,
        }
