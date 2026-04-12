"""
Palace Integration Measure — IIT Φ for Knowledge Graph Wings.

Computes Integrated Information Theory Φ across palace wings, measuring how
much the knowledge graph loses when partitioned. Higher Φ means the wings
are more informationally integrated — discoveries in one wing depend on
discoveries in others.

Adapted from ASI:BUILD (https://gitlab.com/asi-build/asi-build), MIT License.
Original: consciousness_engine/integrated_information.py
"""

import itertools
import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

logger = logging.getLogger("mempalace_agi")


@dataclass
class PhiResult:
    """Result of a Φ computation."""
    phi: float
    partition: Tuple[frozenset, frozenset]  # (set_a, set_b) of the MIP
    elements: frozenset
    timestamp: float = field(default_factory=time.time)


class IITCalculator:
    """
    Integrated Information Theory Φ computation.

    Decoupled from ASI:BUILD's BaseConsciousness — operates on a pure
    element+connection graph. Elements are named nodes, connections are
    weighted directed edges. Φ is the minimum information lost across
    all bipartitions.

    For our palace use-case with 5 wings (≤31 bipartitions) this is
    exact and trivially fast.
    """

    def __init__(self):
        self._elements: Dict[str, float] = {}       # name → current state
        self._connections: List[Tuple[str, str, float]] = []  # (src, tgt, weight)
        self._state_history: List[Dict[str, float]] = []
        self._partition_cache: Dict[str, float] = {}

    # ── Building the system ────────────────────────────────────────────

    def add_element(self, name: str, state: float = 0.0) -> None:
        """Add a named element (node) to the system."""
        self._elements[name] = state
        self._partition_cache.clear()

    def add_connection(self, source: str, target: str, weight: float = 1.0) -> None:
        """Add a directed weighted connection (edge)."""
        if source not in self._elements or target not in self._elements:
            raise ValueError(
                f"Both endpoints must exist. Missing: "
                f"{source if source not in self._elements else target}"
            )
        self._connections.append((source, target, weight))
        self._partition_cache.clear()

    def set_state(self, name: str, value: float) -> None:
        """Update the state of an element."""
        if name not in self._elements:
            raise KeyError(name)
        self._elements[name] = value

    def record_state_snapshot(self) -> None:
        """Record current element states for entropy calculation."""
        self._state_history.append(dict(self._elements))
        # Keep bounded
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-100:]

    @property
    def element_names(self) -> frozenset:
        return frozenset(self._elements.keys())

    # ── Φ Computation ──────────────────────────────────────────────────

    def compute_phi(self, subset: Optional[Set[str]] = None) -> float:
        """Compute Φ for a subset of elements (default: all).

        Φ = min over bipartitions of effective_information(A, B).
        """
        elements = frozenset(subset) if subset else self.element_names
        if len(elements) <= 1:
            return 0.0

        cache_key = "_".join(sorted(elements))
        if cache_key in self._partition_cache:
            return self._partition_cache[cache_key]

        min_phi = float("inf")
        for part_a, part_b in self._all_bipartitions(elements):
            phi_cut = self._compute_effective_information(part_a, part_b)
            if phi_cut < min_phi:
                min_phi = phi_cut

        result = max(0.0, min_phi)
        self._partition_cache[cache_key] = result
        return result

    def find_minimum_information_partition(
        self, subset: Optional[Set[str]] = None
    ) -> Tuple[frozenset, frozenset]:
        """Find the Minimum Information Partition (MIP).

        Returns (part_a, part_b) where Φ is minimized.
        """
        elements = frozenset(subset) if subset else self.element_names
        if len(elements) <= 1:
            return (elements, frozenset())

        min_phi = float("inf")
        best = (elements, frozenset())
        for part_a, part_b in self._all_bipartitions(elements):
            phi_cut = self._compute_effective_information(part_a, part_b)
            if phi_cut < min_phi:
                min_phi = phi_cut
                best = (part_a, part_b)
        return best

    # ── Internal Mechanics ─────────────────────────────────────────────

    def _all_bipartitions(self, elements: frozenset):
        """Yield all non-trivial bipartitions of elements."""
        elems = sorted(elements)
        n = len(elems)
        for size in range(1, n):
            for combo in itertools.combinations(elems, size):
                part_a = frozenset(combo)
                part_b = elements - part_a
                # Avoid duplicates: only yield when |A| ≤ |B|
                if len(part_a) <= len(part_b):
                    yield part_a, part_b

    def _compute_effective_information(
        self, part_a: frozenset, part_b: frozenset
    ) -> float:
        """Effective information lost by cutting connections between A and B.

        Uses connection-weight based measure: sum of weights of cross-cut
        edges, weighted by state entropy of connected elements.
        """
        all_elements = part_a | part_b

        # Find cross-partition connections
        cross_weights: List[float] = []
        for src, tgt, w in self._connections:
            if src not in all_elements or tgt not in all_elements:
                continue
            if (src in part_a and tgt in part_b) or (src in part_b and tgt in part_a):
                cross_weights.append(abs(w))

        if not cross_weights:
            return 0.0

        # Weight by entropy of states (information richness)
        entropy_factor = self._compute_entropy(all_elements)
        if entropy_factor == 0.0:
            # Fallback: use raw connection weight sum
            return sum(cross_weights)

        return sum(cross_weights) * entropy_factor

    def _compute_entropy(self, elements: frozenset) -> float:
        """Entropy of element states based on state history.

        If no history recorded, uses current state directly (binary discretization).
        """
        if self._state_history:
            # Use state history for entropy
            state_tuples = []
            for snapshot in self._state_history[-20:]:
                state = tuple(
                    1 if snapshot.get(e, 0.0) > 0.5 else 0
                    for e in sorted(elements)
                )
                state_tuples.append(state)

            counts: Dict[tuple, int] = defaultdict(int)
            for st in state_tuples:
                counts[st] += 1

            total = len(state_tuples)
            entropy = 0.0
            for c in counts.values():
                p = c / total
                if p > 0:
                    entropy -= p * np.log2(p)
            return entropy
        else:
            # No history — use current states
            states = [self._elements.get(e, 0.0) for e in elements]
            if not states:
                return 0.0
            # Treat as probability distribution
            total = sum(abs(s) for s in states)
            if total == 0:
                return 0.0
            probs = [abs(s) / total for s in states]
            entropy = 0.0
            for p in probs:
                if p > 0:
                    entropy -= p * np.log2(p)
            return entropy

    def clear_cache(self) -> None:
        """Clear partition cache (call after topology changes)."""
        self._partition_cache.clear()

    def reset(self) -> None:
        """Full reset."""
        self._elements.clear()
        self._connections.clear()
        self._state_history.clear()
        self._partition_cache.clear()


class PalaceIntegrationMeasure:
    """
    Measures information integration across palace wings using IIT Φ.

    Maps:
    - Wings → IIT elements
    - Cross-domain KG edges → connections (weight = confidence)
    - Φ tells us how interdependent our knowledge domains are

    Higher Φ = more integrated knowledge = discoveries in one domain
    depend on and inform discoveries in others.
    """

    def __init__(self, kg_bridge: Any, palace_memory: Any = None):
        """
        Args:
            kg_bridge: KnowledgeGraphBridge instance (has .get_valid_triples(), .kg)
            palace_memory: PalaceDiscoveryMemory instance (optional, for wing enumeration)
        """
        self._kg_bridge = kg_bridge
        self._palace_memory = palace_memory
        self._phi_history: List[Tuple[float, float]] = []  # (timestamp, phi)
        self._calculator = IITCalculator()

    # ── Build IIT Graph from KG ────────────────────────────────────────

    def _build_iit_graph(self, wings: Optional[List[str]] = None) -> IITCalculator:
        """Build an IITCalculator from KG triples.

        Elements = unique entities (or wings if specified).
        Connections = KG triples with confidence as weight.
        """
        calc = IITCalculator()

        # Get all valid triples
        try:
            triples = self._kg_bridge.get_valid_triples()
        except Exception:
            triples = []

        if wings:
            # Wing-level analysis: each wing is an element
            for w in wings:
                calc.add_element(w, state=1.0)

            # Map entities to wings via domain metadata
            entity_wing_map = self._map_entities_to_wings(triples, wings)

            # Create wing-to-wing connections from cross-domain triples
            for triple in triples:
                subj = triple.get("subject", "")
                obj = triple.get("object", "")
                conf = triple.get("confidence", 0.5)
                if isinstance(conf, str):
                    try:
                        conf = float(conf)
                    except (ValueError, TypeError):
                        conf = 0.5

                wing_s = entity_wing_map.get(subj)
                wing_o = entity_wing_map.get(obj)

                if wing_s and wing_o and wing_s != wing_o:
                    calc.add_connection(wing_s, wing_o, weight=conf)
        else:
            # Entity-level analysis
            entities: Set[str] = set()
            for triple in triples:
                entities.add(triple.get("subject", ""))
                entities.add(triple.get("object", ""))
            entities.discard("")

            for e in entities:
                calc.add_element(e, state=1.0)

            for triple in triples:
                subj = triple.get("subject", "")
                obj = triple.get("object", "")
                conf = triple.get("confidence", 0.5)
                if isinstance(conf, str):
                    try:
                        conf = float(conf)
                    except (ValueError, TypeError):
                        conf = 0.5
                if subj and obj and subj in entities and obj in entities:
                    try:
                        calc.add_connection(subj, obj, weight=conf)
                    except ValueError:
                        pass

        return calc

    def _map_entities_to_wings(
        self, triples: List[dict], wings: List[str]
    ) -> Dict[str, str]:
        """Map entity names to wings by domain heuristic.

        Uses entity properties (domain field) or keyword matching to the
        canonical wing names.
        """
        wing_lower = {w.lower(): w for w in wings}
        entity_map: Dict[str, str] = {}

        for triple in triples:
            for key in ("subject", "object"):
                entity = triple.get(key, "")
                if not entity or entity in entity_map:
                    continue
                # Check if entity name contains a wing name
                ent_lower = entity.lower()
                for wl, w in wing_lower.items():
                    if wl in ent_lower or ent_lower in wl:
                        entity_map[entity] = w
                        break

        return entity_map

    # ── Public API ─────────────────────────────────────────────────────

    def compute_palace_phi(self, wings: Optional[List[str]] = None) -> float:
        """Compute Φ across all palace wings.

        Args:
            wings: Explicit list of wing names. If None, auto-detects from KG.

        Returns:
            Φ value (0.0 = no integration, higher = more integrated).
        """
        calc = self._build_iit_graph(wings=wings)
        return calc.compute_phi()

    def compute_wing_pair_phi(self, wing_a: str, wing_b: str) -> float:
        """Φ between two specific wings."""
        calc = self._build_iit_graph(wings=[wing_a, wing_b])
        return calc.compute_phi(subset={wing_a, wing_b})

    def get_integration_report(self, wings: Optional[List[str]] = None) -> dict:
        """Full integration report.

        Returns:
            {
                "overall_phi": float,
                "per_pair_phi": {pair_name: phi},
                "minimum_partition": {"part_a": [...], "part_b": [...]},
                "phi_history": [{timestamp, phi}],
                "num_elements": int,
                "num_connections": int,
            }
        """
        calc = self._build_iit_graph(wings=wings)
        elements = list(calc.element_names)

        overall_phi = calc.compute_phi()
        mip_a, mip_b = calc.find_minimum_information_partition()

        # Per-pair Φ
        per_pair: Dict[str, float] = {}
        for ea, eb in itertools.combinations(sorted(elements), 2):
            pair_name = f"{ea}↔{eb}"
            per_pair[pair_name] = calc.compute_phi(subset={ea, eb})

        return {
            "overall_phi": overall_phi,
            "per_pair_phi": per_pair,
            "minimum_partition": {
                "part_a": sorted(mip_a),
                "part_b": sorted(mip_b),
            },
            "phi_history": [
                {"timestamp": ts, "phi": phi}
                for ts, phi in self._phi_history
            ],
            "num_elements": len(elements),
            "num_connections": len(calc._connections),
        }

    def track_phi_history(self, phi: float) -> None:
        """Record Φ value for trend analysis."""
        self._phi_history.append((time.time(), phi))
        # Keep bounded
        if len(self._phi_history) > 500:
            self._phi_history = self._phi_history[-500:]
