"""
RLM Context Handle Protocol — Lazy memory retrieval with fidelity control.

Implements the handle-based retrieval pattern proposed in MemPalace Issue #498.
Instead of materializing full document text for every semantic search hit,
this module provides lightweight handles that can be selectively resolved
at the appropriate fidelity level.

See: /shared/kb/mempalace-agi-docs/rlm-handle-protocol-design.md
"""

from __future__ import annotations

import logging
import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .palace_discovery_memory import PalaceDiscoveryMemory
    from .knowledge_graph_bridge import KnowledgeGraphBridge
    from .config import IntegrationConfig

logger = logging.getLogger(__name__)


# ── Data Classes ───────────────────────────────────────────────────────


@dataclass
class HeatMetrics:
    """Per-drawer heat tracking data.

    Stored in-memory with periodic SQLite flush for persistence (Phase B).
    """

    drawer_id: str
    access_count: int = 0
    last_accessed: float = 0.0  # Unix timestamp
    is_correction: bool = False  # Set when a discovery invalidates a prior
    inbound_edge_count: int = 0  # From KG bridge
    _cached_score: Optional[float] = field(default=None, repr=False)

    def invalidate_cache(self) -> None:
        self._cached_score = None


@dataclass
class MemoryHandle:
    """Lightweight reference to a set of palace memories without materializing content.

    Created by PalaceHandleManager.allocate(), contains only metadata until
    resolve() is called at the desired fidelity level.
    """

    handle_id: str  # UUID
    query: str  # Original query text
    wing: Optional[str]  # Optional wing filter applied
    room: Optional[str]  # Optional room filter applied
    count: int  # Number of matching memories
    preview: List[Dict[str, Any]]  # [{id, title, domain, confidence, heat_score, combined_score}]
    created_at: float  # Unix timestamp
    resolved_fidelity: Optional[str] = None  # None until first resolve()
    resolved_ids: set = field(default_factory=set)  # Track which IDs have been resolved

    @property
    def age_seconds(self) -> float:
        """Seconds since this handle was created."""
        return time.time() - self.created_at

    @property
    def is_stale(self) -> bool:
        """Handles older than 5 minutes are considered stale."""
        return self.age_seconds > 300.0

    def __repr__(self) -> str:
        return (
            f"MemoryHandle(id={self.handle_id[:8]}..., "
            f"query={self.query[:40]!r}, "
            f"count={self.count}, "
            f"resolved={self.resolved_fidelity})"
        )


# ── Valid fidelity levels ──────────────────────────────────────────────

_VALID_FIDELITIES = frozenset(("meta", "summary", "full"))


# ── Handle Manager ─────────────────────────────────────────────────────


class PalaceHandleManager:
    """Lazy memory retrieval with fidelity control.

    Wraps PalaceDiscoveryMemory's semantic_search() to provide handle-based
    access.  The ChromaDB query is executed eagerly during allocate(), but
    only metadata is exposed.  Full document content stays in an internal
    cache until resolve() is called.

    Thread Safety:
        Not thread-safe.  Each OODA cycle should use its own instance,
        or calls must be serialised.

    Memory Management:
        Handles hold references to ChromaDB query results.  Call invalidate()
        when done, or use the context-manager pattern.  Stale handles (>5 min)
        are automatically cleaned on the next allocate() call.
    """

    # Maximum number of live handles before forced eviction
    MAX_LIVE_HANDLES = 50

    def __init__(
        self,
        palace_memory: "PalaceDiscoveryMemory",
        kg_bridge: "Optional[KnowledgeGraphBridge]" = None,
        heat_db_path: Optional[str] = None,
    ):
        """
        Args:
            palace_memory: The PalaceDiscoveryMemory instance to query.
            kg_bridge: Optional KnowledgeGraphBridge for inbound_edge counts
                       and full-fidelity KG triple resolution.
            heat_db_path: Optional path for persistent heat metrics SQLite DB.
                          If None, heat metrics are in-memory only (reset per process).
        """
        self._palace = palace_memory
        self._kg = kg_bridge
        self._heat_db_path = heat_db_path

        # Internal state
        self._handles: Dict[str, MemoryHandle] = {}  # handle_id → MemoryHandle
        self._result_cache: Dict[str, List[Dict]] = {}  # handle_id → full ChromaDB results
        self._heat_tracker: Dict[str, HeatMetrics] = {}  # drawer_id → HeatMetrics

        # Stats
        self._total_allocations = 0
        self._total_resolutions = 0
        self._total_docs_avoided = 0  # docs allocated but never resolved

        # Load persistent heat metrics if configured
        if heat_db_path:
            self._load_heat_metrics()

    # ── Core Protocol ───────────────────────────────────────────────────

    def allocate(
        self,
        query: str,
        wing: Optional[str] = None,
        room: Optional[str] = None,
        n_results: int = 20,
        min_similarity: float = 0.3,
        exclude_domain: Optional[str] = None,
        require_status: Optional[str] = None,
    ) -> MemoryHandle:
        """Execute the ChromaDB query but only return metadata handles.

        The full query results (including document text) are cached internally
        keyed by handle_id.  Only metadata is exposed in the returned handle.

        Args:
            query: Natural language query (will be passed through _isolate_query).
            wing: Optional wing filter (maps to domain).
            room: Optional room filter (maps to hypothesis).
            n_results: Maximum number of results from ChromaDB.
            min_similarity: Minimum cosine similarity threshold.
            exclude_domain: Optional domain to exclude from results.
            require_status: Optional status filter ("decided", "active", etc.).

        Returns:
            MemoryHandle with count and metadata-only preview, sorted by combined_score.
        """
        # Cleanup stale handles (TTL expiry only — not capacity).
        # Capacity eviction happens after this handle is inserted.
        self._cleanup_stale(enforce_capacity=False)

        # Map wing back to domain for semantic_search API compatibility
        domain = None
        if wing:
            # Reverse lookup: wing_astrophysics → Astrophysics
            for d, w in self._palace.config.domain_wings.items():
                if w == wing:
                    domain = d
                    break

        # Build search kwargs
        search_kwargs: Dict[str, Any] = dict(
            query=query,
            n_results=n_results,
        )
        if domain:
            search_kwargs["domain"] = domain
        if exclude_domain:
            search_kwargs["exclude_domain"] = exclude_domain
        if require_status:
            search_kwargs["require_status"] = require_status

        # Execute the ChromaDB query via existing semantic_search()
        raw_hits = self._palace.semantic_search(**search_kwargs)

        # Filter by minimum similarity
        hits = [h for h in raw_hits if h.get("similarity", 0) >= min_similarity]

        # Compute heat scores and combined scores for each hit
        previews: List[Dict[str, Any]] = []
        for hit in hits:
            drawer_id = hit.get("discovery_id", "")
            heat = self.compute_heat(drawer_id)
            similarity = hit.get("similarity", 0.0)
            combined = (similarity * 0.6) + (heat * 0.4)

            previews.append({
                "id": drawer_id,
                "title": self._extract_title(hit),
                "domain": hit.get("domain", ""),
                "confidence": hit.get("strength", 0.0),
                "heat_score": round(heat, 4),
                "semantic_similarity": round(similarity, 4),
                "combined_score": round(combined, 4),
                "finding_type": hit.get("finding_type", ""),
            })

        # Sort by combined score descending
        previews.sort(key=lambda p: p["combined_score"], reverse=True)

        # Create handle
        handle_id = str(uuid.uuid4())
        handle = MemoryHandle(
            handle_id=handle_id,
            query=query,
            wing=wing,
            room=room,
            count=len(hits),
            preview=previews,
            created_at=time.time(),
        )

        # Cache the full results internally (keyed by handle_id)
        self._handles[handle_id] = handle
        self._result_cache[handle_id] = hits  # Full dicts including "text" key

        # Now enforce capacity limit (evict oldest if over MAX_LIVE_HANDLES)
        self._enforce_capacity()

        self._total_allocations += 1
        logger.info(
            "Handle allocated: %s (query=%r, count=%d, wing=%s)",
            handle_id[:8],
            query[:40],
            len(hits),
            wing,
        )

        return handle

    def resolve(
        self,
        handle_id: str,
        fidelity: str = "meta",
        ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """Materialize memory content at requested fidelity.

        Fidelity levels:
        - "meta":    id, title, domain, confidence, heat_score (same as preview)
        - "summary": meta + first 200 chars of content + status + cycle_number
        - "full":    complete document text + all metadata + KG triples

        Args:
            handle_id: Handle ID from a prior allocate() call.
            fidelity: One of "meta", "summary", "full".
            ids: Optional list of specific discovery IDs to resolve.
                 If None, resolves all results in the handle.

        Returns:
            List of dicts at the requested fidelity level.

        Raises:
            KeyError: If handle_id is unknown or has been invalidated.
            ValueError: If fidelity is not one of the valid levels.
        """
        if handle_id not in self._handles:
            raise KeyError(
                f"Unknown handle {handle_id[:8]}... — "
                "it may have been invalidated or never allocated"
            )
        if fidelity not in _VALID_FIDELITIES:
            raise ValueError(
                f"Invalid fidelity {fidelity!r}. Must be 'meta', 'summary', or 'full'."
            )

        handle = self._handles[handle_id]
        cached_hits = self._result_cache[handle_id]

        # Warn on stale handles
        if handle.is_stale:
            logger.warning(
                "Resolving stale handle %s (age=%.0fs). "
                "Results may not reflect recent palace changes.",
                handle_id[:8],
                handle.age_seconds,
            )

        # Filter to requested IDs if specified
        if ids:
            id_set = set(ids)
            target_hits = [h for h in cached_hits if h.get("discovery_id") in id_set]
        else:
            target_hits = cached_hits

        results: List[Dict[str, Any]] = []
        for hit in target_hits:
            drawer_id = hit.get("discovery_id", "")
            heat = self.compute_heat(drawer_id)

            # Track access for heat scoring
            self._record_access(drawer_id)
            handle.resolved_ids.add(drawer_id)

            if fidelity == "meta":
                results.append({
                    "id": drawer_id,
                    "title": self._extract_title(hit),
                    "domain": hit.get("domain", ""),
                    "confidence": hit.get("strength", 0.0),
                    "heat_score": round(heat, 4),
                })

            elif fidelity == "summary":
                text = hit.get("text", "")
                results.append({
                    "id": drawer_id,
                    "title": self._extract_title(hit),
                    "domain": hit.get("domain", ""),
                    "confidence": hit.get("strength", 0.0),
                    "heat_score": round(heat, 4),
                    "summary": text[:200] + ("..." if len(text) > 200 else ""),
                    "status": hit.get("metadata", {}).get("status", "unknown"),
                    "cycle": hit.get("metadata", {}).get("cycle", 0),
                    "finding_type": hit.get("finding_type", ""),
                    "hypothesis_id": hit.get("hypothesis_id", ""),
                    "similarity": hit.get("similarity", 0.0),
                })

            elif fidelity == "full":
                full_record: Dict[str, Any] = {
                    "id": drawer_id,
                    "title": self._extract_title(hit),
                    "domain": hit.get("domain", ""),
                    "confidence": hit.get("strength", 0.0),
                    "heat_score": round(heat, 4),
                    "text": hit.get("text", ""),
                    "similarity": hit.get("similarity", 0.0),
                    "finding_type": hit.get("finding_type", ""),
                    "hypothesis_id": hit.get("hypothesis_id", ""),
                    "data_source": hit.get("data_source", ""),
                    "metadata": hit.get("metadata", {}),
                }

                # Enrich with KG triples if bridge available
                if self._kg:
                    try:
                        kg_relationships = self._kg.get_discovery_relationships(drawer_id)
                        full_record["kg_triples"] = kg_relationships
                    except Exception as e:
                        logger.warning("KG enrichment failed for %s: %s", drawer_id, e)
                        full_record["kg_triples"] = []
                else:
                    full_record["kg_triples"] = []

                results.append(full_record)

        # Update handle state
        handle.resolved_fidelity = fidelity
        self._total_resolutions += 1

        logger.info(
            "Handle %s resolved: fidelity=%s, count=%d/%d",
            handle_id[:8],
            fidelity,
            len(results),
            handle.count,
        )

        return results

    def invalidate(self, handle_id: str) -> None:
        """Release a handle's cached results (memory cleanup).

        After invalidation, the handle_id cannot be resolved.
        Tracks how many documents were allocated but never resolved
        (the "savings" from lazy loading).
        """
        if handle_id in self._handles:
            handle = self._handles[handle_id]
            never_resolved = handle.count - len(handle.resolved_ids)
            self._total_docs_avoided += max(0, never_resolved)

            del self._handles[handle_id]
            del self._result_cache[handle_id]

            logger.debug(
                "Handle %s invalidated: %d docs never resolved (saved)",
                handle_id[:8],
                never_resolved,
            )

    def invalidate_all(self) -> int:
        """Invalidate all live handles.  Returns count of handles released."""
        handle_ids = list(self._handles.keys())
        for hid in handle_ids:
            self.invalidate(hid)
        return len(handle_ids)

    # ── Heat Score System ───────────────────────────────────────────────

    def compute_heat(self, drawer_id: str) -> float:
        """Compute the LCM heat score for a drawer.

        Formula:
            heat = (access_freq * 0.35) + (is_correction * 0.30) +
                   (recency * 0.20) + (inbound_edges * 0.15)

        Where:
            access_freq: sigmoid normalised access count (center at 10 accesses)
            is_correction: 1.0 if this discovery corrects/invalidates a prior, else 0.0
            recency: exponential decay from last access (half-life = 1 hour)
            inbound_edges: sigmoid normalised KG inbound edge count (center at 3 edges)

        Returns:
            Float in [0.0, 1.0].
        """
        metrics = self._heat_tracker.get(drawer_id)
        if not metrics:
            # No tracking data yet — cold start
            inbound = self._count_inbound_edges(drawer_id) if self._kg else 0
            metrics = HeatMetrics(
                drawer_id=drawer_id,
                inbound_edge_count=inbound,
            )
            self._heat_tracker[drawer_id] = metrics

        # Use cached score if available
        if metrics._cached_score is not None:
            return metrics._cached_score

        # access_freq: sigmoid (center at 10 accesses → 0.5)
        access_freq = 1.0 / (1.0 + math.exp(-metrics.access_count / 5.0 + 2.0))

        # is_correction: binary
        is_correction = 1.0 if metrics.is_correction else 0.0

        # recency: exponential decay (half-life = 3600s = 1 hour)
        if metrics.last_accessed > 0:
            age_seconds = time.time() - metrics.last_accessed
            recency = math.exp(-0.693 * age_seconds / 3600.0)  # ln(2) ≈ 0.693
        else:
            recency = 0.0  # Never accessed → zero recency

        # inbound_edges: sigmoid (center at 3 edges → 0.5)
        inbound_edges = 1.0 / (1.0 + math.exp(-metrics.inbound_edge_count / 3.0 + 1.0))

        heat = (
            access_freq * 0.35
            + is_correction * 0.30
            + recency * 0.20
            + inbound_edges * 0.15
        )

        # Clamp to [0, 1]
        heat = max(0.0, min(1.0, heat))

        # Cache
        metrics._cached_score = heat
        return heat

    def mark_correction(self, drawer_id: str) -> None:
        """Mark a drawer as containing a correction to a prior discovery.

        This significantly boosts its heat score (0.30 weight), reflecting
        that corrections are high-priority information for hypothesis evaluation.
        """
        metrics = self._get_or_create_metrics(drawer_id)
        metrics.is_correction = True
        metrics.invalidate_cache()

    def get_heat_scores(self, drawer_ids: List[str]) -> Dict[str, float]:
        """Batch compute heat scores for a set of drawer IDs.

        Returns:
            Dict mapping drawer_id → heat_score.
        """
        return {did: self.compute_heat(did) for did in drawer_ids}

    # ── Statistics ──────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return handle manager statistics.

        Useful for monitoring the effectiveness of lazy loading.
        """
        total_allocated_and_resolved = self._total_docs_avoided + self._total_resolutions
        return {
            "live_handles": len(self._handles),
            "total_allocations": self._total_allocations,
            "total_resolutions": self._total_resolutions,
            "total_docs_avoided": self._total_docs_avoided,
            "tracked_drawers": len(self._heat_tracker),
            "savings_ratio": (
                self._total_docs_avoided / max(1, total_allocated_and_resolved)
            ),
        }

    # ── Internal Helpers ────────────────────────────────────────────────

    def _extract_title(self, hit: Dict[str, Any]) -> str:
        """Extract a short title from a discovery hit.

        Uses the first line of the text, truncated to 80 chars.
        Falls back to discovery_id if text is empty.
        """
        text = hit.get("text", "")
        if text:
            first_line = text.split("\n")[0].strip()
            return first_line[:80] + ("..." if len(first_line) > 80 else "")
        return hit.get("discovery_id", "unknown")

    def _record_access(self, drawer_id: str) -> None:
        """Record an access event for heat tracking."""
        metrics = self._get_or_create_metrics(drawer_id)
        metrics.access_count += 1
        metrics.last_accessed = time.time()
        metrics.invalidate_cache()

    def _get_or_create_metrics(self, drawer_id: str) -> HeatMetrics:
        """Get or lazily create heat metrics for a drawer."""
        if drawer_id not in self._heat_tracker:
            inbound = self._count_inbound_edges(drawer_id) if self._kg else 0
            self._heat_tracker[drawer_id] = HeatMetrics(
                drawer_id=drawer_id,
                inbound_edge_count=inbound,
            )
        return self._heat_tracker[drawer_id]

    def _count_inbound_edges(self, drawer_id: str) -> int:
        """Count KG triples where this drawer's entity appears as object."""
        if not self._kg:
            return 0
        try:
            relationships = self._kg.get_discovery_relationships(drawer_id)
            # Count triples where this entity is the object (inbound)
            return sum(
                1 for r in relationships if r.get("object", "").find(drawer_id) >= 0
            )
        except Exception:
            return 0

    def _cleanup_stale(self, enforce_capacity: bool = True) -> int:
        """Remove stale handles (older than 5 minutes).  Returns count removed."""
        stale_ids = [hid for hid, h in self._handles.items() if h.is_stale]
        for hid in stale_ids:
            self.invalidate(hid)

        removed = len(stale_ids)

        # Optionally also enforce MAX_LIVE_HANDLES
        if enforce_capacity:
            removed += self._enforce_capacity()

        if removed:
            logger.info("Cleaned up %d stale/excess handles", removed)
        return removed

    def _enforce_capacity(self) -> int:
        """Evict oldest handles if over MAX_LIVE_HANDLES.  Returns count evicted."""
        if len(self._handles) <= self.MAX_LIVE_HANDLES:
            return 0

        sorted_handles = sorted(
            self._handles.items(),
            key=lambda kv: kv[1].created_at,
        )
        excess = len(self._handles) - self.MAX_LIVE_HANDLES
        for hid, _ in sorted_handles[:excess]:
            self.invalidate(hid)
        return excess

    def _load_heat_metrics(self) -> None:
        """Load persistent heat metrics from SQLite.  Phase B stub."""
        # Phase B implementation — see §10 of the design doc
        pass

    def _flush_heat_metrics(self) -> None:
        """Flush in-memory heat metrics to SQLite for persistence.  Phase B stub."""
        # Phase B implementation — see §10 of the design doc
        pass
