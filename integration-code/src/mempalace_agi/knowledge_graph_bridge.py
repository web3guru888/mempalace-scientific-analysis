"""
KnowledgeGraphBridge — Bridges ASTRA-dev's DynamicKnowledgeGraph with
MemPalace's temporal entity-relationship KnowledgeGraph.

ASTRA-dev has a sophisticated knowledge graph with:
- Typed entities (10 EntityType variants)
- Typed relations (16 RelationType variants)
- networkx MultiDiGraph for in-memory operations
- Belief propagation, gap detection, analogy discovery

MemPalace has a simpler but persistent knowledge graph with:
- SQLite-backed entities and triples
- Temporal validity (valid_from, valid_to)
- Confidence scores
- Source provenance (source_closet, source_file)

Strategy: Don't replace ASTRA's KG — sync discoveries and causal findings
INTO MemPalace's KG for persistent temporal tracking.

Backend abstraction (2026-04-11)
---------------------------------
Provenance and raw triple queries now go through a ``KGBackend`` instance
(default: ``SQLiteKGBackend``).  The upstream ``MemPalaceKG`` is still
used for entity/triple/timeline/invalidate operations that have first-class
API methods.  This separation ensures that when LanceDB (PR #574) lands,
we only need to add a ``LanceDBKGBackend`` implementation.
"""

import json
import logging
import os
import sys
from datetime import datetime
from typing import Dict, List, Optional, Any

logger = logging.getLogger("mempalace_agi")

# Import MemPalace's KnowledgeGraph
_mempalace_path = os.environ.get("MEMPALACE_PATH", "/shared/mempalace")
if _mempalace_path not in sys.path:
    sys.path.insert(0, _mempalace_path)

from mempalace.knowledge_graph import KnowledgeGraph as MemPalaceKG

# Import ASTRA-dev's types
_astra_path = os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev")
if _astra_path not in sys.path:
    sys.path.insert(0, _astra_path)

from .config import IntegrationConfig


class KnowledgeGraphBridge:
    """
    Bridges ASTRA-dev's knowledge graph operations with MemPalace's
    persistent temporal knowledge graph.

    Primary use cases:
    1. Causal discovery results → MemPalace triples
    2. Hypothesis relationships → MemPalace triples
    3. Cross-domain links → MemPalace triples
    4. Discovery provenance → MemPalace entity + triples

    Can be initialized with an optional ``KGBackend`` for provenance
    and raw-query operations.  If not provided, creates an
    ``SQLiteKGBackend`` internally.
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        *,
        backend: Optional[Any] = None,
    ):
        self.config = config or IntegrationConfig()
        self._kg = MemPalaceKG(db_path=self.config.kg_db_path)
        self._synced_entities = set()  # Track what we've already synced
        self._synced_triples = set()

        # Initialize KGBackend for provenance + raw queries
        if backend is not None:
            self._backend = backend
        else:
            from .backends import SQLiteKGBackend
            self._backend = SQLiteKGBackend(db_path=self.config.kg_db_path)

        # Ensure provenance schema exists
        self._backend.ensure_provenance_schema()

        logger.info(
            "KnowledgeGraphBridge initialized with KG at %s (backend=%r)",
            self.config.kg_db_path,
            self._backend,
        )

    # ── Provenance Storage ──────────────────────────────────────────

    def _store_provenance(
        self,
        triple_id: str,
        agent_id: str = "",
        cycle_id: str = "",
        evidence_chain: list | None = None,
        confidence: float = 1.0,
        reason: str = "",
        valid_at: str | None = None,
        invalid_at: str | None = None,
        statement_type: str | None = None,
        temporal_type: str | None = None,
    ) -> None:
        """Store or update provenance for a triple.

        If provenance already exists (e.g. the KG returned an existing
        triple_id), we append to confidence_history and merge the
        evidence chain.

        Bi-temporal params:
            valid_at:   When the fact actually occurred (ISO format)
            invalid_at: When the fact ceased being true (ISO format)

        Statement classification params:
            statement_type: 'fact', 'prediction', or 'opinion'
            temporal_type:  'static' (single event), 'dynamic' (ongoing),
                            or 'atemporal' (universal law)
        """
        self._backend.store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            cycle_id=cycle_id,
            evidence_chain=evidence_chain or [],
            confidence=confidence,
            reason=reason,
            valid_at=valid_at,
            invalid_at=invalid_at,
            statement_type=statement_type,
            temporal_type=temporal_type,
        )

    @property
    def kg(self) -> MemPalaceKG:
        """Direct access to the underlying MemPalace KG."""
        return self._kg

    @property
    def backend(self) -> Any:
        """Direct access to the underlying KGBackend."""
        return self._backend

    # ── Causal Discovery → KG Triples ───────────────────────────────

    def record_causal_edges(
        self,
        causal_graph: Any,
        source_hypothesis: str = "",
        cycle: int = 0,
        agent_id: str = "",
        evidence_chain: list | None = None,
        cycle_id: str = "",
    ) -> List[str]:
        """
        Convert ASTRA-dev causal discovery results into MemPalace KG triples.

        Args:
            causal_graph: CausalGraph object from astra_live_backend.causal
            source_hypothesis: Hypothesis ID that triggered causal discovery
            cycle: OODA cycle number
            agent_id: Which specialist agent or OODA phase produced this
            evidence_chain: References to source discoveries/data points
            cycle_id: Which OODA cycle produced this (string identifier)

        Returns:
            List of triple IDs created
        """
        triple_ids = []
        timestamp = datetime.now().isoformat()

        if not hasattr(causal_graph, "edges"):
            logger.warning("causal_graph has no 'edges' attribute")
            return triple_ids

        algorithm = getattr(causal_graph, "algorithm", "unknown")

        # ── Format detection: networkx DiGraph vs ASTRA CausalGraph ──
        # networkx graphs expose edges via .edges(data=True) → (u, v, dict)
        # ASTRA CausalGraph stores edge objects with .source/.target attrs.
        # Detect networkx by checking for the canonical .nodes attribute
        # and callable .edges (which also accepts keyword args).
        _is_networkx = (
            hasattr(causal_graph, "nodes")
            and hasattr(causal_graph, "adj")
            and callable(getattr(causal_graph, "edges", None))
        )

        if _is_networkx:
            edge_iter = self._iter_networkx_edges(causal_graph)
        else:
            edge_iter = self._iter_causal_graph_edges(causal_graph)

        for source, target, edge_type, confidence, p_value in edge_iter:
            if not source or not target:
                continue

            # Ensure entities exist
            source_props = {"origin": "causal_discovery", "cycle": str(cycle)}
            target_props = {"origin": "causal_discovery", "cycle": str(cycle)}

            self._kg.add_entity(
                name=source,
                entity_type="variable",
                properties=source_props,
            )
            self._kg.add_entity(
                name=target,
                entity_type="variable",
                properties=target_props,
            )

            # Map edge types to predicates
            predicate = self._edge_type_to_predicate(edge_type)

            # Add the triple
            triple_id = self._kg.add_triple(
                subject=source,
                predicate=predicate,
                obj=target,
                valid_from=timestamp,
                confidence=confidence,
                source_closet="causal_inference",
                source_file=f"hypothesis_{source_hypothesis}_cycle_{cycle}",
            )
            triple_ids.append(triple_id)

            # Store provenance
            self._store_provenance(
                triple_id=triple_id,
                agent_id=agent_id,
                cycle_id=cycle_id or f"cycle_{cycle}",
                evidence_chain=evidence_chain or [],
                confidence=confidence,
                reason=f"Causal discovery via {algorithm} algorithm",
            )

            logger.debug(
                "Causal triple: %s %s %s (conf=%.2f)",
                source, predicate, target, confidence,
            )

        logger.info(
            "Recorded %d causal triples from hypothesis %s",
            len(triple_ids), source_hypothesis,
        )
        return triple_ids

    @staticmethod
    def _iter_causal_graph_edges(causal_graph):
        """Yield (source, target, edge_type, confidence, p_value) from ASTRA CausalGraph."""
        for edge in causal_graph.edges:
            yield (
                getattr(edge, "source", None),
                getattr(edge, "target", None),
                getattr(edge, "edge_type", "→"),
                getattr(edge, "confidence", 0.5),
                getattr(edge, "p_value", None),
            )

    @staticmethod
    def _iter_networkx_edges(graph):
        """Yield (source, target, edge_type, confidence, p_value) from a networkx DiGraph.

        networkx ``graph.edges(data=True)`` yields ``(u, v, attr_dict)`` tuples.
        We pull recognised keys from the attribute dict and apply sensible defaults
        so the downstream code path is identical to the CausalGraph path.
        """
        for u, v, data in graph.edges(data=True):
            yield (
                str(u),
                str(v),
                data.get("edge_type", "→"),
                data.get("confidence", data.get("weight", 0.5)),
                data.get("p_value", None),
            )

    def _edge_type_to_predicate(self, edge_type: str) -> str:
        """Map ASTRA's causal edge types to MemPalace predicates."""
        mapping = {
            "→": "causes",
            "←": "caused_by",
            "o-o": "associated_with",
            "—": "correlated_with",
            "x→": "possibly_causes",
            "↔": "bidirectionally_causes",
        }
        return mapping.get(edge_type, "related_to")

    # ── Discovery → KG Entities ──────────────────────────────────────

    def record_discovery_entity(
        self,
        discovery_id: str,
        domain: str,
        finding_type: str,
        description: str,
        hypothesis_id: str,
        variables: list,
        strength: float,
        agent_id: str = "",
        cycle_id: str = "",
    ) -> str:
        """
        Create a KG entity for a discovery and link it to its hypothesis.

        Args:
            discovery_id: ASTRA discovery ID (e.g., "D0042")
            domain: Research domain
            finding_type: Type of finding (scaling, correlation, etc.)
            description: Finding description
            hypothesis_id: Source hypothesis ID
            variables: Variables involved
            strength: Discovery strength score
            agent_id: Which specialist agent produced this
            cycle_id: Which OODA cycle produced this

        Returns:
            Entity ID
        """
        # Create discovery entity
        entity_id = self._kg.add_entity(
            name=discovery_id,
            entity_type="discovery",
            properties={
                "domain": domain,
                "finding_type": finding_type,
                "description": description[:500],
                "variables": ",".join(variables),
                "strength": str(strength),
            },
        )

        # Create hypothesis entity if not exists
        self._kg.add_entity(
            name=hypothesis_id,
            entity_type="hypothesis",
            properties={"domain": domain},
        )

        # Link discovery to hypothesis
        triple_id = self._kg.add_triple(
            subject=discovery_id,
            predicate="produced_by",
            obj=hypothesis_id,
            valid_from=datetime.now().isoformat(),
            confidence=1.0,
            source_closet="discovery_engine",
        )
        self._store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            cycle_id=cycle_id,
            evidence_chain=[hypothesis_id],
            confidence=1.0,
            reason=f"Discovery {discovery_id} produced by hypothesis {hypothesis_id}",
        )

        # Link discovery to domain
        domain_entity = domain.lower().replace(" ", "_")
        self._kg.add_entity(
            name=domain_entity,
            entity_type="domain",
            properties={"display_name": domain},
        )
        triple_id = self._kg.add_triple(
            subject=discovery_id,
            predicate="belongs_to_domain",
            obj=domain_entity,
            valid_from=datetime.now().isoformat(),
            confidence=1.0,
            source_closet="discovery_engine",
        )
        self._store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            cycle_id=cycle_id,
            confidence=1.0,
            reason=f"Discovery {discovery_id} belongs to domain {domain}",
        )

        # Link discovery to variables
        for var in variables:
            self._kg.add_entity(
                name=var,
                entity_type="variable",
                properties={"domain": domain},
            )
            triple_id = self._kg.add_triple(
                subject=discovery_id,
                predicate="involves_variable",
                obj=var,
                valid_from=datetime.now().isoformat(),
                confidence=1.0,
                source_closet="discovery_engine",
            )
            self._store_provenance(
                triple_id=triple_id,
                agent_id=agent_id,
                cycle_id=cycle_id,
                confidence=1.0,
                reason=f"Discovery {discovery_id} involves variable {var}",
            )

        return entity_id

    # ── Hypothesis Lifecycle → KG ────────────────────────────────────

    def record_hypothesis_transition(
        self,
        hypothesis_id: str,
        from_phase: str,
        to_phase: str,
        confidence: float,
        agent_id: str = "",
        cycle_id: str = "",
        reason: str = "",
    ):
        """
        Record a hypothesis phase transition in the KG.

        This creates a temporal trail of hypothesis evolution.

        Bi-temporal mapping (Phase 16):
            valid_at   = when the hypothesis entered this new phase
            invalid_at = when the hypothesis left the previous phase
                         (set on the *previous* phase's provenance row)

        Args:
            hypothesis_id: Hypothesis being transitioned
            from_phase: Previous phase
            to_phase: New phase
            confidence: Current confidence
            agent_id: Which agent triggered the transition
            cycle_id: Which OODA cycle triggered the transition
            reason: Human-readable reason for the transition
        """
        timestamp = datetime.now().isoformat()

        # Ensure hypothesis entity exists
        self._kg.add_entity(
            name=hypothesis_id,
            entity_type="hypothesis",
            properties={"current_phase": to_phase, "confidence": str(confidence)},
        )

        # Bi-temporal: mark the previous phase triple as invalidated
        # Find the existing "in_phase" triple for from_phase and set invalid_at
        # Normalize subject ID to match KG storage (lowercase, underscores)
        norm_subject = hypothesis_id.lower().replace(" ", "_").replace("'", "")
        if from_phase:
            from_entity = from_phase.lower()
            prev_triples = self._backend.query_triples(
                subject=norm_subject,
                predicate="in_phase",
                object=from_entity,
                limit=1,
            )
            for prev in prev_triples:
                self._store_provenance(
                    triple_id=prev["id"],
                    invalid_at=timestamp,
                    reason=f"Superseded by transition to {to_phase}",
                )

        # Invalidate previous phase triple (existing MemPalace API)
        self._kg.invalidate(
            subject=hypothesis_id,
            predicate="in_phase",
            obj=from_phase.lower(),
            ended=timestamp,
        )

        # Add new phase triple with valid_at = now
        triple_id = self._kg.add_triple(
            subject=hypothesis_id,
            predicate="in_phase",
            obj=to_phase.lower(),
            valid_from=timestamp,
            confidence=confidence,
            source_closet="hypothesis_lifecycle",
        )

        transition_reason = reason or f"Phase transition: {from_phase} → {to_phase}"
        self._store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            cycle_id=cycle_id,
            confidence=confidence,
            reason=transition_reason,
            valid_at=timestamp,
        )

    # ── Cross-domain Links ───────────────────────────────────────────

    def record_cross_domain_link(
        self,
        discovery_a: str,
        discovery_b: str,
        link_type: str = "structurally_similar",
        similarity: float = 0.5,
    ):
        """Record a cross-domain link between two discoveries."""
        self._kg.add_triple(
            subject=discovery_a,
            predicate=link_type,
            obj=discovery_b,
            valid_from=datetime.now().isoformat(),
            confidence=similarity,
            source_closet="cross_domain_analysis",
        )

    # ── Provenance Queries & Updates ────────────────────────────────

    def update_confidence(
        self,
        triple_id: str,
        new_confidence: float,
        reason: str = "",
        agent_id: str = "",
    ) -> None:
        """Update the confidence of a KG triple and record the change in provenance.

        Uses ``KGBackend.execute_raw()`` to update the triples table directly
        (upstream KG has no ``update_confidence()`` method).

        Args:
            triple_id: The triple whose confidence should be updated
            new_confidence: New confidence value (0.0–1.0)
            reason: Why the confidence changed
            agent_id: Which agent is making the update
        """
        # Update confidence in the KG triples table via backend
        self._backend.execute_raw(
            "UPDATE triples SET confidence = ? WHERE id = ?",
            (new_confidence, triple_id),
        )

        # Update or create provenance record with new confidence entry
        self._store_provenance(
            triple_id=triple_id,
            agent_id=agent_id,
            confidence=new_confidence,
            reason=reason or f"Confidence updated to {new_confidence}",
        )

        logger.debug(
            "Updated confidence for %s to %.3f: %s",
            triple_id, new_confidence, reason,
        )

    def get_provenance(self, triple_id: str) -> Optional[Dict[str, Any]]:
        """Return the full provenance record for a triple.

        Returns:
            Dict with keys: triple_id, agent_id, cycle_id,
            evidence_chain (list), confidence_history (list of dicts),
            created_at, updated_at.  ``None`` if no provenance exists.
        """
        return self._backend.get_provenance(triple_id)

    def get_confidence_history(self, entity: str) -> List[Dict[str, Any]]:
        """Return confidence history for all triples involving an entity.

        Searches both the ``subject`` and ``object`` columns of the KG
        triples table, then looks up provenance for each matching triple.

        Args:
            entity: Entity name (will be normalised to the KG's id format)

        Returns:
            List of dicts, each with triple info and its confidence_history.
        """
        # Use backend's get_entity_relations to find all triples involving entity
        relations = self._backend.get_entity_relations(entity, direction="both", limit=500)

        results = []
        for rel in relations:
            tid = rel.get("id", "")
            prov = self.get_provenance(tid)
            results.append({
                "triple_id": tid,
                "subject": rel.get("subject", ""),
                "predicate": rel.get("predicate", ""),
                "object": rel.get("object", ""),
                "current_confidence": rel.get("confidence", 0.0),
                "confidence_history": prov["confidence_history"] if prov else [],
                "agent_id": prov["agent_id"] if prov else "",
            })

        return results

    # ── Query Helpers ────────────────────────────────────────────────

    def get_hypothesis_timeline(self, hypothesis_id: str) -> list:
        """Get the full timeline of a hypothesis's evolution."""
        return self._kg.timeline(hypothesis_id)

    def get_discovery_relationships(self, discovery_id: str) -> list:
        """Get all relationships for a discovery entity."""
        return self._kg.query_entity(discovery_id, direction="outgoing")

    def get_causal_triples(self) -> list:
        """Get all causal relationship triples."""
        causes = self._kg.query_relationship("causes")
        possibly_causes = self._kg.query_relationship("possibly_causes")
        return causes + possibly_causes

    def get_domain_triples(self, domain: str) -> list:
        """Get all triples for a domain."""
        domain_entity = domain.lower().replace(" ", "_")
        return self._kg.query_entity(domain_entity, direction="incoming")

    # ── Bi-temporal Queries (Phase 16) ────────────────────────────────

    def get_temporal_triples(
        self,
        valid_from: str | None = None,
        valid_to: str | None = None,
        include_invalidated: bool = False,
    ) -> list[dict[str, Any]]:
        """Query triples within a temporal validity window.

        Args:
            valid_from: ISO timestamp — only return triples whose valid_at >= this
            valid_to:   ISO timestamp — only return triples whose valid_at <= this
            include_invalidated: If False (default), exclude triples that have
                                 a non-NULL invalid_at. If True, include all.

        Returns:
            List of dicts with KG triple fields plus provenance fields
            (valid_at, invalid_at, agent_id, cycle_id, confidence_history).
        """
        return self._backend.query_temporal_triples(
            valid_from=valid_from,
            valid_to=valid_to,
            include_invalidated=include_invalidated,
        )

    def invalidate_triple(
        self,
        triple_id: str,
        reason: str = "",
        invalidated_by: str = "",
    ) -> None:
        """Mark a triple as invalidated (no longer true).

        Sets invalid_at and expired_at to the current timestamp in provenance
        and records the reason in confidence_history as a zero-confidence entry
        (the relationship is no longer believed).  Does NOT delete — preserves
        full temporal history.

        Args:
            triple_id: The triple to invalidate
            reason: Why the triple is being invalidated
            invalidated_by: Which agent is performing the invalidation
        """
        now = datetime.now().isoformat()
        evidence = [f"Invalidated: {reason}"] if reason else ["Invalidated"]
        self._store_provenance(
            triple_id=triple_id,
            agent_id=invalidated_by,
            confidence=0.0,
            reason=reason or "Triple invalidated",
            invalid_at=now,
            evidence_chain=evidence,
        )

        # Also set expired_at via backend (not supported by _store_provenance's
        # merge path since it's a write-once field)
        self._backend.execute_raw(
            """UPDATE triple_provenance
               SET expired_at = ?, updated_at = ?
               WHERE triple_id = ?""",
            (now, now, triple_id),
        )

        # Also expire the triple in the KG itself so queries exclude it
        self._backend.execute_raw(
            "UPDATE triples SET valid_to = ? WHERE id = ?",
            (now, triple_id),
        )

        logger.debug("Invalidated triple %s: %s", triple_id, reason)

    # ── Temporal Query Methods ─────────────────────────────────────────

    def get_valid_triples(
        self,
        as_of: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return triples that are currently valid.

        A triple is valid if its ``invalid_at`` is NULL.  When ``as_of`` is
        provided, a triple is valid if ``invalid_at`` was NULL at that
        timestamp (i.e. ``invalid_at IS NULL OR invalid_at > as_of``).

        Args:
            as_of: ISO timestamp — check validity as-of this point in time.
                   If None, returns triples with ``invalid_at IS NULL``.

        Returns:
            List of dicts with KG triple + provenance fields.
        """
        if as_of:
            rows = self._backend.execute_raw(
                """SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                          t.valid_from, t.valid_to,
                          p.valid_at, p.invalid_at, p.expired_at,
                          p.agent_id, p.cycle_id, p.confidence_history,
                          p.evidence_chain, p.statement_type, p.temporal_type
                   FROM triples t
                   LEFT JOIN triple_provenance p ON t.id = p.triple_id
                   WHERE p.invalid_at IS NULL OR p.invalid_at > ?
                   ORDER BY p.valid_at ASC NULLS LAST""",
                (as_of,),
            )
        else:
            rows = self._backend.execute_raw(
                """SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                          t.valid_from, t.valid_to,
                          p.valid_at, p.invalid_at, p.expired_at,
                          p.agent_id, p.cycle_id, p.confidence_history,
                          p.evidence_chain, p.statement_type, p.temporal_type
                   FROM triples t
                   LEFT JOIN triple_provenance p ON t.id = p.triple_id
                   WHERE p.invalid_at IS NULL OR p.triple_id IS NULL
                   ORDER BY p.valid_at ASC NULLS LAST""",
            )

        return [self._row_to_triple_dict(r) for r in rows]

    def get_invalidated_triples(
        self,
        since: str | None = None,
    ) -> list[dict[str, Any]]:
        """Return triples that have been invalidated.

        Args:
            since: ISO timestamp — only return triples invalidated after this.
                   If None, return all invalidated triples.

        Returns:
            List of dicts with KG triple + provenance fields.
        """
        if since:
            rows = self._backend.execute_raw(
                """SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                          t.valid_from, t.valid_to,
                          p.valid_at, p.invalid_at, p.expired_at,
                          p.agent_id, p.cycle_id, p.confidence_history,
                          p.evidence_chain, p.statement_type, p.temporal_type
                   FROM triples t
                   JOIN triple_provenance p ON t.id = p.triple_id
                   WHERE p.invalid_at IS NOT NULL AND p.invalid_at >= ?
                   ORDER BY p.invalid_at DESC""",
                (since,),
            )
        else:
            rows = self._backend.execute_raw(
                """SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                          t.valid_from, t.valid_to,
                          p.valid_at, p.invalid_at, p.expired_at,
                          p.agent_id, p.cycle_id, p.confidence_history,
                          p.evidence_chain, p.statement_type, p.temporal_type
                   FROM triples t
                   JOIN triple_provenance p ON t.id = p.triple_id
                   WHERE p.invalid_at IS NOT NULL
                   ORDER BY p.invalid_at DESC""",
            )

        return [self._row_to_triple_dict(r) for r in rows]

    def get_temporal_history(self, triple_id: str) -> dict[str, Any] | None:
        """Return the full temporal history for a triple.

        Includes confidence history, invalidation chain, and all
        bi-temporal metadata.

        Args:
            triple_id: The triple to get history for.

        Returns:
            Dict with triple info + full confidence_history + invalidation
            details, or None if triple not found.
        """
        prov = self.get_provenance(triple_id)
        if prov is None:
            # Triple may exist without provenance — try KG via backend
            rows = self._backend.execute_raw(
                "SELECT * FROM triples WHERE id = ?",
                (triple_id,),
            )
            if not rows:
                return None
            row = rows[0]
            return {
                "triple_id": row.get("id", triple_id),
                "subject": row.get("subject", ""),
                "predicate": row.get("predicate", ""),
                "object": row.get("object", ""),
                "confidence": row.get("confidence", 0.0),
                "valid_from": row.get("valid_from"),
                "valid_to": row.get("valid_to"),
                "confidence_history": [],
                "evidence_chain": [],
                "valid_at": None,
                "invalid_at": None,
                "expired_at": None,
                "statement_type": "fact",
                "temporal_type": "static",
                "invalidation_chain": [],
            }

        # Build the invalidation chain from evidence entries that mention invalidation
        inv_chain = [
            entry for entry in prov.get("evidence_chain", [])
            if isinstance(entry, str) and entry.startswith("Invalidated:")
        ]

        return {
            "triple_id": prov["triple_id"],
            "agent_id": prov["agent_id"],
            "cycle_id": prov["cycle_id"],
            "confidence_history": prov["confidence_history"],
            "evidence_chain": prov["evidence_chain"],
            "valid_at": prov["valid_at"],
            "invalid_at": prov["invalid_at"],
            "expired_at": prov["expired_at"],
            "statement_type": prov["statement_type"],
            "temporal_type": prov["temporal_type"],
            "invalidation_chain": inv_chain,
        }

    def get_triples_by_type(
        self,
        statement_type: str,
    ) -> list[dict[str, Any]]:
        """Return triples filtered by statement type.

        Args:
            statement_type: One of 'fact', 'prediction', 'opinion'.

        Returns:
            List of dicts with KG triple + provenance fields.
        """
        rows = self._backend.execute_raw(
            """SELECT t.id, t.subject, t.predicate, t.object, t.confidence,
                      t.valid_from, t.valid_to,
                      p.valid_at, p.invalid_at, p.expired_at,
                      p.agent_id, p.cycle_id, p.confidence_history,
                      p.evidence_chain, p.statement_type, p.temporal_type
               FROM triples t
               JOIN triple_provenance p ON t.id = p.triple_id
               WHERE p.statement_type = ?
               ORDER BY p.created_at DESC""",
            (statement_type,),
        )

        return [self._row_to_triple_dict(r) for r in rows]

    def _row_to_triple_dict(self, row: dict[str, Any]) -> dict[str, Any]:
        """Convert a JOINed triple+provenance row (dict) to a standardized dict.

        Works with both ``sqlite3.Row`` objects and plain dicts (from
        ``KGBackend.execute_raw()``).
        """
        # Handle confidence_history / evidence_chain which may be JSON strings
        conf_history = row.get("confidence_history")
        if isinstance(conf_history, str):
            try:
                conf_history = json.loads(conf_history)
            except (json.JSONDecodeError, TypeError):
                conf_history = []
        elif conf_history is None:
            conf_history = []

        ev_chain = row.get("evidence_chain")
        if isinstance(ev_chain, str):
            try:
                ev_chain = json.loads(ev_chain)
            except (json.JSONDecodeError, TypeError):
                ev_chain = []
        elif ev_chain is None:
            ev_chain = []

        return {
            "triple_id": row.get("id", ""),
            "subject": row.get("subject", ""),
            "predicate": row.get("predicate", ""),
            "object": row.get("object", ""),
            "confidence": row.get("confidence", 0.0),
            "valid_from": row.get("valid_from"),
            "valid_to": row.get("valid_to"),
            "valid_at": row.get("valid_at"),
            "invalid_at": row.get("invalid_at"),
            "expired_at": row.get("expired_at"),
            "agent_id": row.get("agent_id") or "",
            "cycle_id": row.get("cycle_id") or "",
            "confidence_history": conf_history,
            "evidence_chain": ev_chain,
            "statement_type": row.get("statement_type") or "fact",
            "temporal_type": row.get("temporal_type") or "static",
        }

    # ── Contradiction Detection ────────────────────────────────────────

    def check_contradictions(
        self,
        new_subject: str,
        new_predicate: str,
        new_object: str,
        confidence: float,
    ) -> list[dict[str, Any]]:
        """Check for contradictory triples and auto-invalidate weaker ones.

        Searches existing KG for triples with the same subject+predicate but
        a different object.  If the new confidence exceeds the existing
        triple's confidence, the old triple is invalidated.

        Args:
            new_subject: Subject of the new triple
            new_predicate: Predicate of the new triple
            new_object: Object of the new triple
            confidence: Confidence of the new triple

        Returns:
            List of result dicts with keys:
            - action: 'invalidated', 'kept', or 'new'
            - triple_id: The existing triple ID (if any)
            - reason: Explanation
        """
        subject_id = new_subject.lower().replace(" ", "_").replace("'", "")
        object_id = new_object.lower().replace(" ", "_").replace("'", "")

        # Query via backend for triples with same subject+predicate but different object
        existing = self._backend.execute_raw(
            """SELECT t.id, t.subject, t.predicate, t.object, t.confidence
               FROM triples t
               WHERE t.subject = ? AND t.predicate = ?
                 AND t.object != ?
                 AND (t.valid_to IS NULL OR t.valid_to = '')""",
            (subject_id, new_predicate, object_id),
        )

        results = []
        for row in existing:
            old_conf = row.get("confidence", 0.0) or 0.0
            old_tid = row.get("id", "")
            if confidence > old_conf:
                reason = (
                    f"Contradiction: '{new_subject} {new_predicate} {new_object}' "
                    f"(conf={confidence:.2f}) supersedes "
                    f"'{row.get('object', '')}' (conf={old_conf:.2f})"
                )
                self.invalidate_triple(
                    triple_id=old_tid,
                    reason=reason,
                    invalidated_by="contradiction_detector",
                )
                results.append({
                    "action": "invalidated",
                    "triple_id": old_tid,
                    "reason": reason,
                })
                logger.warning(
                    "Invalidated contradictory triple %s: %s %s %s (conf=%.2f) "
                    "superseded by %s (conf=%.2f)",
                    old_tid, new_subject, new_predicate, row.get("object", ""),
                    old_conf, new_object, confidence,
                )
            else:
                results.append({
                    "action": "kept",
                    "triple_id": old_tid,
                    "reason": (
                        f"Existing triple has higher or equal confidence "
                        f"({old_conf:.2f} >= {confidence:.2f})"
                    ),
                })

        if not results:
            results.append({
                "action": "new",
                "triple_id": "",
                "reason": "No contradictions found — new triple is novel",
            })

        return results

    def stats(self) -> dict:
        """Get knowledge graph statistics.

        Returns canonical ``total_entities`` / ``total_triples`` keys plus the
        original upstream keys (``entities``, ``triples``) as backward-compat
        aliases so both old and new callers work.
        """
        raw = self._kg.stats()
        # Canonical keys with total_ prefix
        raw["total_entities"] = raw.get("entities", 0)
        raw["total_triples"] = raw.get("triples", 0)
        return raw

    # ── Pathfinding Integration (Phase 18) ────────────────────────────

    def find_path(
        self,
        start_entity: str,
        goal_entity: str,
        max_iterations: int = 10000,
        pheromone_manager: Any | None = None,
        embedding_fn: Any | None = None,
    ) -> Any | None:
        """Find a path between two entities in the KG using Semantic A*.

        Convenience method that wraps ``kg_pathfinder.find_knowledge_path``.

        Args:
            start_entity: Start entity name.
            goal_entity:  Goal entity name.
            max_iterations: A* iteration limit.
            pheromone_manager: Optional PheromoneManager.
            embedding_fn: Optional entity→embedding callable.

        Returns:
            PathResult if a path was found (check .complete), or None if
            either entity doesn't exist.
        """
        from .kg_pathfinder import find_knowledge_path

        return find_knowledge_path(
            db_path=self.config.kg_db_path,
            start_entity=start_entity,
            goal_entity=goal_entity,
            max_iterations=max_iterations,
            pheromone_manager=pheromone_manager,
            embedding_fn=embedding_fn,
            backend=self._backend,
        )

    # ── Wikidata Enrichment Integration (Phase 18) ────────────────────

    def enrich_from_wikidata(self, entity_name: str) -> Any:
        """Enrich an entity from Wikidata and add triples to the KG.

        Convenience method that wraps ``wikidata_enricher.WikidataEnricher``.
        Creates a temporary enricher for the call.

        Args:
            entity_name: Entity label to search for on Wikidata.

        Returns:
            EnrichmentResult with counts and any errors.
        """
        from .wikidata_enricher import WikidataEnricher

        enricher = WikidataEnricher(kg_bridge=self)
        return enricher.enrich_entity(entity_name)
