"""
MemoryAugmentedOrient — Injects semantic memory retrieval into ASTRA-dev's Orient phase.

The Orient phase in ASTRA-dev's OODA cycle currently only scans cached data feeds
and stigmergy signals. It has NO semantic search of past discoveries.

This module wraps the Orient phase to:
1. Query ChromaDB for semantically similar past discoveries
2. Surface relevant cross-domain findings
3. Provide enriched context for hypothesis generation

This is the highest-value integration point between MemPalace and ASTRA-dev.

Phase 17 adds RetrievalProfile support so each OODA phase (Orient, Evaluate,
Decide) uses formally defined retrieval parameters instead of magic numbers.

Phase 20 adds KG-pathfinder integration: when ``use_kg_paths`` is set on the
active profile **and** a ``kg_db_path`` is configured, the Orient phase will
attempt to find causal chains (A* paths through the knowledge graph) connecting
cross-domain discoveries back to the current domain.  Discoveries with a
KG-backed causal chain receive a similarity boost (``KG_PATH_BOOST``).
"""

import json
import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from .palace_discovery_memory import PalaceDiscoveryMemory
from .retrieval_profiles import (
    RetrievalProfile,
    ORIENT_BREADTH,
    EVALUATE_PRECISION,
    DECIDE_RECENCY,
    compose,
)

logger = logging.getLogger("mempalace_agi")

# 20% similarity boost for cross-domain hits backed by a KG causal chain
KG_PATH_BOOST = 1.2

# Relevance boost for items found in working memory (avoids redundant embeddings)
WORKING_MEMORY_BOOST = 1.05


# ── Working Memory Buffer (ASI:BUILD adoption) ──────────────────────
#
# Concept from: ASI:BUILD consciousness_engine/memory_integration.py
# Capacity-limited working memory (Miller's Law: 7±2 items).
# Keeps recently accessed discoveries in a fast cache, reducing
# ChromaDB embedding calls during the Orient phase.


@dataclass
class WorkingMemoryItem:
    """An item in working memory — recently accessed/relevant discovery."""
    discovery_id: str
    content: str
    domain: str
    relevance_score: float
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 1


class WorkingMemoryBuffer:
    """Capacity-limited working memory buffer (Miller's Law: 7±2 items).

    Inspired by ASI:BUILD consciousness_engine/memory_integration.py.
    Keeps the most recently/frequently accessed discoveries in fast cache,
    reducing ChromaDB embedding calls during Orient phase.
    """

    def __init__(self, capacity: int = 7):
        self.capacity = capacity
        self._items: Dict[str, WorkingMemoryItem] = {}
        self._access_order: deque = deque(maxlen=capacity)

    def access(self, discovery_id: str, content: str, domain: str, relevance: float = 0.5):
        """Add or refresh an item in working memory."""
        if discovery_id in self._items:
            item = self._items[discovery_id]
            item.accessed_at = time.time()
            item.access_count += 1
            item.relevance_score = max(item.relevance_score, relevance)
        else:
            if len(self._items) >= self.capacity:
                self._evict_oldest()
            item = WorkingMemoryItem(discovery_id, content, domain, relevance)
            self._items[discovery_id] = item
        # Move to front of access order
        if discovery_id in self._access_order:
            self._access_order.remove(discovery_id)
        self._access_order.append(discovery_id)

    def _evict_oldest(self):
        """Evict least recently accessed item."""
        if self._access_order:
            oldest_id = self._access_order.popleft()
            self._items.pop(oldest_id, None)

    def get_items(self) -> List[WorkingMemoryItem]:
        """Get all items sorted by relevance (highest first)."""
        return sorted(self._items.values(), key=lambda x: x.relevance_score, reverse=True)

    def search_working_memory(self, query_terms: set) -> List[WorkingMemoryItem]:
        """Fast keyword search within working memory (no embedding needed)."""
        results = []
        for item in self._items.values():
            overlap = query_terms & set(item.content.lower().split())
            if overlap:
                results.append(item)
        return sorted(results, key=lambda x: x.relevance_score, reverse=True)

    def contains(self, discovery_id: str) -> bool:
        return discovery_id in self._items

    def clear(self):
        self._items.clear()
        self._access_order.clear()

    @property
    def size(self) -> int:
        return len(self._items)

    @property
    def is_full(self) -> bool:
        return len(self._items) >= self.capacity


class MemoryAugmentedOrient:
    """
    Augments ASTRA-dev's Orient phase with semantic memory retrieval.

    Usage:
        palace_memory = PalaceDiscoveryMemory(config)
        augmented_orient = MemoryAugmentedOrient(palace_memory)

        # During OODA cycle:
        memory_context = augmented_orient.retrieve_context(
            hypotheses=engine.hypothesis_store.active(),
            current_domain="Astrophysics",
        )

    Phase 17: Each OODA phase can use a different RetrievalProfile:
        orient   → ORIENT_BREADTH  (wide, cross-domain)
        evaluate → EVALUATE_PRECISION (tight, domain-focused)
        decide   → DECIDE_RECENCY  (recent, authoritative)
    """

    def __init__(
        self,
        palace_memory: PalaceDiscoveryMemory,
        # ── Backward-compatible numeric params (Phase 16 style) ──────────
        max_results_per_hypothesis: Optional[int] = None,
        cross_domain_results: Optional[int] = None,
        min_similarity: Optional[float] = None,
        # ── Phase 17: RetrievalProfile params ────────────────────────────
        orient_profile: Optional[RetrievalProfile] = None,
        evaluate_profile: Optional[RetrievalProfile] = None,
        decide_profile: Optional[RetrievalProfile] = None,
        # ── Phase 20: KG pathfinder integration ──────────────────────────
        kg_db_path: Optional[str] = None,
        pheromone_manager: Optional[Any] = None,
    ):
        self.palace_memory = palace_memory
        self.kg_db_path = kg_db_path
        self.pheromone_manager = pheromone_manager

        # ── Phase 23: Working Memory Buffer (ASI:BUILD adoption) ─────
        self.working_memory = WorkingMemoryBuffer(capacity=7)

        # Resolve profiles: explicit profile wins, then numeric overrides,
        # then defaults from the standard profiles.
        if orient_profile is not None:
            self.orient_profile = orient_profile
        elif any(v is not None for v in (max_results_per_hypothesis, min_similarity)):
            # Backward compat: build a profile from numeric overrides
            overrides = {}
            if max_results_per_hypothesis is not None:
                overrides["n_results"] = max_results_per_hypothesis
            if min_similarity is not None:
                overrides["min_similarity"] = min_similarity
            self.orient_profile = compose(ORIENT_BREADTH, **overrides)
        else:
            self.orient_profile = ORIENT_BREADTH

        self.evaluate_profile = evaluate_profile or EVALUATE_PRECISION
        self.decide_profile = decide_profile or DECIDE_RECENCY

        # ── Backward-compat attributes (used by retrieve_context) ────────
        # Derive from orient_profile so old code that reads these still works.
        self.max_results_per_hypothesis = self.orient_profile.n_results
        self.min_similarity = self.orient_profile.min_similarity
        # cross_domain_results: prefer explicit numeric override, else default 10
        # (preserving Phase 16 default — cross-domain pass is separate from
        # per-hypothesis retrieval and needs its own result count).
        if cross_domain_results is not None:
            self.cross_domain_results = cross_domain_results
        else:
            self.cross_domain_results = 10

    def retrieve_context(
        self,
        hypotheses: list,
        current_domain: str | None = None,
        cycle_number: int = 0,
        phase: str = "orient",
    ) -> Dict[str, Any]:
        """
        Retrieve memory context relevant to the current set of hypotheses.

        This should be called at the beginning of the Orient phase, before
        hypothesis scoring.

        Args:
            hypotheses: List of Hypothesis objects (from ASTRA-dev's HypothesisStore)
            current_domain: Optional domain focus for this cycle
            cycle_number: Current OODA cycle number
            phase: OODA phase name — "orient", "evaluate", or "decide".
                   Selects the RetrievalProfile to use. Default "orient" for
                   backward compatibility.

        Returns:
            Dict with:
                - per_hypothesis: {hypothesis_id: [relevant_discoveries]}
                - cross_domain: [cross-domain findings — backward compat alias]
                - cross_domain_discoveries: [dedicated cross-domain hits, explicitly
                  excluding current domain so they don't compete with in-domain]
                - domain_context: [recent discoveries in current domain]
                - suggestions: [new hypothesis suggestions based on memory]
                - profile_used: name of the RetrievalProfile applied
        """
        # Select profile based on phase
        profile = self._profile_for_phase(phase)

        # Effective parameters from profile
        n_results = profile.n_results
        min_sim = profile.min_similarity

        result = {
            "per_hypothesis": {},
            "cross_domain": [],
            "domain_context": [],
            "suggestions": [],
            "profile_used": profile.name,
            "memory_stats": {
                "total_queries": 0,
                "total_hits": 0,
                "unique_discoveries_surfaced": set(),
            },
        }

        # 1. Per-hypothesis semantic retrieval
        #    Phase 23: check working memory first for fast hits, then ChromaDB.
        wm_hits_total = 0
        for hyp in hypotheses:
            hyp_id = hyp.id if hasattr(hyp, "id") else str(hyp)
            description = hyp.description if hasattr(hyp, "description") else str(hyp)

            query = f"{description}"

            # ── Phase 23: Working memory fast path ───────────────────
            # Check if working memory has relevant items (keyword match,
            # no embedding call needed).  Items found here get a small
            # relevance boost so recent context stays prominent.
            wm_hit_ids: set = set()
            query_terms = set(query.lower().split())
            wm_matches = self.working_memory.search_working_memory(query_terms)
            for wm_item in wm_matches:
                wm_hit_ids.add(wm_item.discovery_id)
            wm_hits_total += len(wm_hit_ids)

            # Issue #333: semantic_search() internally calls _isolate_query()
            # which strips system-prompt preambles and enforces max length.
            # Hypothesis descriptions are typically clean, but the protection
            # is always active in case upstream callers concatenate context.
            search_kwargs: Dict[str, Any] = dict(
                query=query,
                n_results=n_results,
            )
            if profile.require_status:
                search_kwargs["require_status"] = profile.require_status

            hits = self.palace_memory.semantic_search(**search_kwargs)

            # Filter by minimum similarity
            relevant = [h for h in hits if h["similarity"] >= min_sim]

            # ── Phase 23: Boost items already in working memory ──────
            for h in relevant:
                did = h.get("discovery_id", "")
                if did and did in wm_hit_ids:
                    h["similarity"] = min(1.0, h["similarity"] * WORKING_MEMORY_BOOST)
                    h["working_memory_hit"] = True

            # ── Phase 23: Populate working memory with new results ───
            for h in relevant:
                did = h.get("discovery_id", "")
                if did:
                    self.working_memory.access(
                        discovery_id=did,
                        content=h.get("text", ""),
                        domain=h.get("domain", ""),
                        relevance=h.get("similarity", 0.5),
                    )

            # Apply time decay reranking if enabled
            if profile.time_decay and profile.half_life_days:
                relevant = self._apply_time_decay(relevant, profile.half_life_days)

            result["per_hypothesis"][hyp_id] = relevant
            result["memory_stats"]["total_queries"] += 1
            result["memory_stats"]["total_hits"] += len(relevant)
            for h in relevant:
                result["memory_stats"]["unique_discoveries_surfaced"].add(
                    h["discovery_id"]
                )

        result["memory_stats"]["working_memory_hits"] = wm_hits_total
        result["memory_stats"]["working_memory_size"] = self.working_memory.size

        # 2. Dedicated cross-domain search pass
        #    Uses exclude_domain to ensure in-domain results never crowd
        #    out cross-domain hits (Cycle 2 regression: 9→4 cross-domain).
        #    Results are scored and returned separately as
        #    ``cross_domain_discoveries`` so they don't compete with
        #    per-hypothesis in-domain results.
        cross_domain_discoveries: List[Dict] = []

        if current_domain and hypotheses:
            # Build a composite query from all hypothesis descriptions
            composite_query = " ".join(
                getattr(h, "description", str(h))[:100]
                for h in hypotheses[:5]
            )
            # When only 1 hypothesis is active, the composite query is too
            # narrow for cross-domain retrieval (embeddings focus on a single
            # topic).  Augment with the domain name and any variables so the
            # query surface is broader, e.g.
            #   "Epidemiology: Pandemic Recovery Trajectory involving
            #    life_expectancy, vaccination_rate"
            if len(hypotheses) == 1:
                h0 = hypotheses[0]
                parts = [current_domain + ":"]
                name = getattr(h0, "name", None)
                if isinstance(name, str) and name:
                    parts.append(name)
                parts.append(composite_query)
                variables = getattr(h0, "variables", None)
                if isinstance(variables, (list, tuple)) and variables:
                    parts.append("involving " + ", ".join(str(v) for v in variables))
                composite_query = " ".join(parts)

            # Dedicated cross-domain pass: explicitly EXCLUDE current domain
            # at the DB level so all returned slots go to other domains.
            # Issue #333: composite_query may be long (multiple hypothesis
            # snippets), but _isolate_query() inside semantic_search() will
            # truncate it to config.query_max_length automatically.
            #
            # Use profile's exclude_domain setting — for orient we want
            # cross-domain; for evaluate we may not.
            cd_exclude = current_domain if profile.exclude_domain else None
            cd_search_kwargs: Dict[str, Any] = dict(
                query=composite_query,
                exclude_domain=cd_exclude if cd_exclude else current_domain,
                n_results=self.cross_domain_results,
            )
            if profile.require_status:
                cd_search_kwargs["require_status"] = profile.require_status

            cross_domain_hits = self.palace_memory.semantic_search(**cd_search_kwargs)
            cross_domain_discoveries = [
                h for h in cross_domain_hits
                if h["similarity"] >= min_sim
            ]

            # Apply time decay to cross-domain results too
            if profile.time_decay and profile.half_life_days:
                cross_domain_discoveries = self._apply_time_decay(
                    cross_domain_discoveries, profile.half_life_days,
                )

        # 2b. KG causal chain enrichment (Phase 20)
        #     When the profile enables KG paths AND a KG database is configured,
        #     try to find A* paths from the current domain to each cross-domain
        #     discovery's domain.  Hits with a KG-backed causal chain get a
        #     similarity boost (KG_PATH_BOOST).
        causal_chains: List[Dict] = []
        if (
            profile.use_kg_paths
            and self.kg_db_path
            and current_domain
            and cross_domain_discoveries
        ):
            cross_domain_discoveries, causal_chains = self._find_causal_chains(
                cross_domain_discoveries, current_domain,
            )

        # Populate both keys (cross_domain for backward compat, cross_domain_discoveries as new)
        result["cross_domain"] = cross_domain_discoveries
        result["cross_domain_discoveries"] = cross_domain_discoveries
        result["causal_chains"] = causal_chains

        # Track cross-domain discoveries in stats
        result["memory_stats"]["total_queries"] += 1 if cross_domain_discoveries else 0
        result["memory_stats"]["total_hits"] += len(cross_domain_discoveries)
        for h in cross_domain_discoveries:
            result["memory_stats"]["unique_discoveries_surfaced"].add(
                h["discovery_id"]
            )

        # 3. Domain context: recent discoveries in the current domain
        if current_domain:
            result["domain_context"] = self.palace_memory.get_domain_context(
                domain=current_domain,
                n_recent=10,
            )

        # 4. Suggestion generation based on memory patterns
        result["suggestions"] = self._generate_suggestions(result)

        # Convert set to count for JSON serialization
        result["memory_stats"]["unique_discoveries_surfaced"] = len(
            result["memory_stats"]["unique_discoveries_surfaced"]
        )

        return result

    # ── Phase-specific convenience methods ───────────────────────────

    def retrieve_for_evaluate(
        self,
        hypotheses: list,
        current_domain: str | None = None,
        cycle_number: int = 0,
    ) -> Dict[str, Any]:
        """Retrieve context using the EVALUATE_PRECISION profile.

        Tight semantic matching focused on same-domain validation with
        only confirmed/validated evidence.
        """
        return self.retrieve_context(
            hypotheses=hypotheses,
            current_domain=current_domain,
            cycle_number=cycle_number,
            phase="evaluate",
        )

    def retrieve_for_decide(
        self,
        hypotheses: list,
        current_domain: str | None = None,
        cycle_number: int = 0,
    ) -> Dict[str, Any]:
        """Retrieve context using the DECIDE_RECENCY profile.

        Recent authoritative decisions with time-decay weighting.
        """
        return self.retrieve_context(
            hypotheses=hypotheses,
            current_domain=current_domain,
            cycle_number=cycle_number,
            phase="decide",
        )

    # ── Internal helpers ─────────────────────────────────────────────

    def _profile_for_phase(self, phase: str) -> RetrievalProfile:
        """Return the appropriate RetrievalProfile for a phase name."""
        mapping = {
            "orient": self.orient_profile,
            "evaluate": self.evaluate_profile,
            "decide": self.decide_profile,
        }
        if phase not in mapping:
            logger.warning("Unknown phase %r, defaulting to orient", phase)
            return self.orient_profile
        return mapping[phase]

    @staticmethod
    def _apply_time_decay(
        results: List[Dict],
        half_life_days: int,
    ) -> List[Dict]:
        """Rerank *results* by recency-weighted similarity.

        Formula: ``decayed_score = similarity × 2^(-age_days / half_life_days)``

        Each result dict is expected to carry ``similarity`` (float) and
        either ``metadata.filed_at`` (ISO timestamp) or ``metadata.timestamp``
        (epoch float) for computing age.  Results without a parseable
        timestamp keep their original similarity (decay factor = 1.0).

        Returns a **new list** sorted by ``decayed_similarity`` descending.
        Each dict gets two new keys: ``decayed_similarity`` and ``age_days``.
        """
        now = datetime.utcnow()

        for hit in results:
            age_days: float = 0.0
            meta = hit.get("metadata", {})

            # Try filed_at (ISO string) first, then timestamp (epoch float)
            filed_at = meta.get("filed_at", "")
            timestamp = meta.get("timestamp", 0.0)

            if filed_at:
                try:
                    stored = datetime.fromisoformat(filed_at)
                    age_days = max((now - stored).total_seconds() / 86400.0, 0.0)
                except (ValueError, TypeError):
                    age_days = 0.0
            elif timestamp:
                try:
                    stored = datetime.utcfromtimestamp(float(timestamp))
                    age_days = max((now - stored).total_seconds() / 86400.0, 0.0)
                except (ValueError, TypeError, OSError):
                    age_days = 0.0

            decay_factor = math.pow(2, -age_days / half_life_days) if half_life_days > 0 else 1.0
            hit["age_days"] = round(age_days, 2)
            hit["decayed_similarity"] = round(hit.get("similarity", 0.0) * decay_factor, 6)

        # Sort by decayed similarity descending
        results.sort(key=lambda h: h.get("decayed_similarity", 0.0), reverse=True)
        return results

    def _find_causal_chains(
        self,
        cross_domain_hits: List[Dict],
        current_domain: str,
    ) -> Tuple[List[Dict], List[Dict]]:
        """Find KG paths connecting cross-domain discoveries to current domain.

        For each cross-domain hit, extract key entities (from variables or
        domain names) and try to find A* paths in the knowledge graph.

        Phase 20 hotfix: uses a per-call dict cache keyed on
        ``(start_entity, goal_entity)`` to avoid redundant A* searches.
        In Cycle 7 many cross-domain hits share the same entity pairs
        (e.g., multiple Economics hits all route from ``climate`` → same
        goal entities), so the cache typically eliminates 60-80% of A*
        calls, bringing orient time from ~4400ms back to ~1000-1500ms.

        Returns:
            ``(enriched_hits, causal_chains)`` where:

            - *enriched_hits*: same list with ``kg_path`` metadata and
              similarity boost applied to hits that have a KG-backed path.
            - *causal_chains*: list of successful path dicts
              ``{"start", "goal", "path", "cost", "hops", "discovery_id"}``.
        """
        # Lazy import so the module remains importable even if kg_pathfinder
        # has heavier dependencies (numpy etc.) — the import only runs when
        # the feature is actually used.
        from .kg_pathfinder import find_knowledge_path  # noqa: F811

        causal_chains: List[Dict] = []

        # Per-call cache: (start, goal) → PathResult | None
        # Cleared implicitly each time _find_causal_chains is invoked
        # (new dict per call), so stale results can't persist across
        # retrieve_context() calls.
        _path_cache: Dict[tuple, Any] = {}

        # Normalise current domain to KG entity format
        current_entities = [current_domain.lower().replace(" ", "_").replace("'", "")]

        for hit in cross_domain_hits:
            hit_domain = hit.get("domain", "")
            if not hit_domain:
                continue

            # Build candidate goal entities from the hit
            goal_entities: List[str] = []
            # 1. The hit's domain name
            goal_entities.append(hit_domain.lower().replace(" ", "_").replace("'", ""))
            # 2. Variables from the hit metadata (if present)
            meta = hit.get("metadata", {})
            variables_raw = meta.get("variables", "")
            if isinstance(variables_raw, str) and variables_raw:
                try:
                    parsed = json.loads(variables_raw)
                    if isinstance(parsed, list):
                        goal_entities.extend(
                            str(v).lower().replace(" ", "_").replace("'", "")
                            for v in parsed
                        )
                except (json.JSONDecodeError, TypeError):
                    # Could be comma-separated instead of JSON
                    goal_entities.extend(
                        v.strip().lower().replace(" ", "_").replace("'", "")
                        for v in variables_raw.split(",")
                        if v.strip()
                    )

            # Try to find a path from any current entity to any goal entity
            best_path = None
            best_start = None
            best_goal = None
            for start_ent in current_entities:
                for goal_ent in goal_entities:
                    if start_ent == goal_ent:
                        continue

                    cache_key = (start_ent, goal_ent)
                    if cache_key in _path_cache:
                        path_result = _path_cache[cache_key]
                    else:
                        try:
                            path_result = find_knowledge_path(
                                db_path=self.kg_db_path,
                                start_entity=start_ent,
                                goal_entity=goal_ent,
                                pheromone_manager=self.pheromone_manager,
                            )
                        except Exception as e:
                            logger.debug(
                                "KG pathfinding error %s→%s: %s",
                                start_ent, goal_ent, e,
                            )
                            path_result = None
                        _path_cache[cache_key] = path_result

                    if path_result is None or not path_result.complete:
                        continue

                    # Keep shortest path found
                    if best_path is None or path_result.total_cost < best_path.total_cost:
                        best_path = path_result
                        best_start = start_ent
                        best_goal = goal_ent

            if best_path is not None:
                # Enrich the hit with KG path metadata
                hit["kg_path"] = {
                    "path": best_path.path,
                    "cost": best_path.total_cost,
                    "hops": len(best_path.path) - 1,
                }
                # Boost similarity (capped at 1.0)
                hit["similarity"] = min(1.0, hit.get("similarity", 0.0) * KG_PATH_BOOST)

                causal_chains.append({
                    "start": best_start,
                    "goal": best_goal,
                    "path": best_path.path,
                    "cost": best_path.total_cost,
                    "hops": len(best_path.path) - 1,
                    "discovery_id": hit.get("discovery_id", ""),
                })

        return cross_domain_hits, causal_chains

    def _generate_suggestions(self, context: Dict) -> List[str]:
        """
        Generate hypothesis suggestions based on memory patterns.

        Looks for:
        - Cross-domain discoveries with similar structure (analogy potential)
        - High-strength findings that haven't generated follow-ups
        - Patterns across different hypothesis contexts
        """
        suggestions = []

        # Cross-domain analogies
        for hit in context.get("cross_domain", []):
            if hit["similarity"] > 0.6:
                suggestions.append(
                    f"Cross-domain analogy: {hit['domain']} finding "
                    f"({hit['discovery_id']}) shows {hit['finding_type']} "
                    f"pattern similar to current focus (similarity: {hit['similarity']:.2f}). "
                    f"Consider testing analogous hypothesis."
                )

        # Strong findings across hypotheses
        seen_strong = set()
        for hyp_id, hits in context.get("per_hypothesis", {}).items():
            for hit in hits:
                if hit["strength"] > 0.7 and hit["discovery_id"] not in seen_strong:
                    seen_strong.add(hit["discovery_id"])
                    suggestions.append(
                        f"Strong prior finding {hit['discovery_id']} "
                        f"(strength: {hit['strength']:.2f}) is relevant to "
                        f"hypothesis {hyp_id}. Consider building on this evidence."
                    )

        return suggestions[:10]  # Cap at 10 suggestions

    def score_hypothesis_with_memory(
        self,
        hypothesis,
        memory_hits: List[Dict],
    ) -> float:
        """
        Compute a memory-informed score boost for a hypothesis.

        This score can be added to ASTRA-dev's existing hypothesis scoring
        (info_gain * 0.4 + novelty * 0.3 + testability * 0.3) as a memory bonus.

        Args:
            hypothesis: ASTRA Hypothesis object
            memory_hits: Results from semantic_search for this hypothesis

        Returns:
            Score between 0.0 and 0.3 (to be added to existing 0-1 score)
        """
        if not memory_hits:
            return 0.0

        # Factors:
        # 1. Similarity of past findings (higher = more promising area)
        avg_similarity = sum(h["similarity"] for h in memory_hits) / len(memory_hits)

        # 2. Strength of related discoveries (higher = more robust area)
        avg_strength = sum(h["strength"] for h in memory_hits) / len(memory_hits)

        # 3. Cross-domain coverage (more domains = more general finding)
        domains = set(h["domain"] for h in memory_hits)
        domain_diversity = min(1.0, len(domains) / 3.0)  # Normalize to 3 domains

        # Weighted combination, capped at 0.3
        memory_score = (
            0.4 * avg_similarity
            + 0.4 * avg_strength
            + 0.2 * domain_diversity
        ) * 0.3  # Scale to [0, 0.3] range

        return round(min(0.3, memory_score), 4)
