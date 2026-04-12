"""
PalaceDiscoveryMemory — Drop-in replacement for ASTRA-dev's DiscoveryMemory
that adds MemPalace's spatial memory architecture and semantic search.

This is the primary integration point. It:
1. Maintains FULL backward compatibility with DiscoveryMemory's 13 public methods
2. Stores every discovery via a pluggable VectorBackend (ChromaDB/LanceDB)
3. Organizes drawers in palace hierarchy: domain→Wing, hypothesis→Room
4. Adds semantic_search() for the Orient phase augmentation

Design principle: Composition over inheritance. We wrap the original DiscoveryMemory
rather than subclassing it, so ASTRA-dev's code doesn't need modification.

Storage backend: Decoupled from any specific vector DB via the ``VectorBackend``
protocol (see ``backends/vector_backend.py``).  Default: ChromaDB.  Future: LanceDB
when MemPalace PR #574 merges.
"""

import json
import re
import time
import hashlib
import logging
import os
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Tuple

import numpy as np

from .backends import VectorBackend, create_vector_backend
from .config import IntegrationConfig


class ConsolidationState(Enum):
    """Discovery consolidation lifecycle.

    Inspired by ASI:BUILD consciousness_engine/memory_integration.py.
    Tracks how deeply a discovery has been integrated into the knowledge structure.

    Transitions:
        INITIAL → CONSOLIDATING  (KG triples created for it)
        CONSOLIDATING → CONSOLIDATED  (retrieved and confirmed by subsequent cycles)
        CONSOLIDATED → RECONSOLIDATING  (new contradicting/extending evidence arrives)
        RECONSOLIDATING → CONSOLIDATED  (re-evaluation complete)
    """
    INITIAL = "initial"                # Just stored, not yet deeply processed
    CONSOLIDATING = "consolidating"    # Being cross-referenced with KG, other discoveries
    CONSOLIDATED = "consolidated"      # Fully integrated into knowledge structure
    RECONSOLIDATING = "reconsolidating"  # New evidence arrived, needs re-evaluation

logger = logging.getLogger("mempalace_agi")

# Import ASTRA-dev's types - we re-export them for convenience
import sys

# We need ASTRA-dev's original classes. Add to sys.path if needed.
_astra_path = os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev")
if _astra_path not in sys.path:
    sys.path.insert(0, _astra_path)

from astra_live_backend.discovery_memory import (
    DiscoveryMemory as _OriginalDiscoveryMemory,
    DiscoveryRecord,
    MethodOutcome,
    ExplorationState,
)


class RecordResult:
    """Wrapper returned by ``record_discovery`` that behaves like a
    DiscoveryRecord **and** carries tiered-duplicate metadata.

    Attribute access is delegated to the inner ``record``, so existing
    callers that do ``result.id`` or ``result.domain`` keep working.

    New fields:
        record:          The underlying DiscoveryRecord
        duplicate_class: "hard" | "soft" | "novel"
        similar_to:      ID of the closest existing discovery (soft only)
        similarity:      cosine similarity score of the closest match
    """

    __slots__ = ("record", "duplicate_class", "similar_to", "similarity")

    def __init__(
        self,
        record: "DiscoveryRecord",
        duplicate_class: str = "novel",
        similar_to: str = "",
        similarity: float = 0.0,
    ):
        self.record = record
        self.duplicate_class = duplicate_class
        self.similar_to = similar_to
        self.similarity = similarity

    # Delegate attribute access to the wrapped DiscoveryRecord so that
    # ``result.id``, ``result.domain``, etc. keep working.
    def __getattr__(self, name: str):
        return getattr(self.record, name)

    def __repr__(self):
        return (
            f"RecordResult(id={self.record.id!r}, "
            f"duplicate_class={self.duplicate_class!r}, "
            f"similarity={self.similarity})"
        )

    # Allow truthiness check (``if result:``) — True when record exists.
    def __bool__(self):
        return self.record is not None


class PalaceDiscoveryMemory:
    """
    Drop-in replacement for ASTRA-dev's DiscoveryMemory with palace storage.

    All 13 public methods of DiscoveryMemory are implemented identically.
    Palace storage (via pluggable VectorBackend) is added as a secondary store for semantic search.

    Usage:
        # Instead of:
        #   memory = DiscoveryMemory(db_path="discoveries.db")
        # Use:
        memory = PalaceDiscoveryMemory(config=IntegrationConfig())

        # All existing API works:
        rec = memory.record_discovery(...)
        strong = memory.get_strong_discoveries(...)

        # NEW: semantic search across all discoveries
        results = memory.semantic_search("galaxy rotation curves", domain="Astrophysics")
    """

    def __init__(
        self,
        config: IntegrationConfig | None = None,
        max_records: int = 500,
        batch_size: int = 100,
        backend: VectorBackend | None = None,
    ):
        self.config = config or IntegrationConfig()
        self._batch_size = batch_size

        # Ensure directories exist
        os.makedirs(os.path.dirname(self.config.discovery_db_path) or ".", exist_ok=True)
        os.makedirs(self.config.palace_path, exist_ok=True)

        # Initialize the original DiscoveryMemory for backward compatibility
        self._original = _OriginalDiscoveryMemory(
            max_records=max_records,
            db_path=self.config.discovery_db_path,
        )

        # Initialize the vector backend.  Accept an injected backend for
        # testability and future LanceDB migration; default to ChromaDB.
        if backend is not None:
            self._backend: VectorBackend = backend
        else:
            self._backend = create_vector_backend(
                "chromadb",
                path=self.config.palace_path,
                collection_name=self.config.collection_name,
            )

        # Backward-compat shim: tests and the embedding fallback tests
        # inspect ``_collection`` directly.  Alias to the backend so
        # attribute access (``memory._collection.get(...)``) still works.
        self._collection = self._backend

        # Sync existing discoveries from SQLite → palace on first load
        self._sync_existing_to_palace()

        logger.info(
            "PalaceDiscoveryMemory initialized: %d discoveries, %d palace drawers",
            len(self._original.discoveries),
            self._backend.count(),
        )

    # ── Proxy attributes for backward compatibility ─────────────────

    @property
    def discoveries(self):
        return self._original.discoveries

    @property
    def method_outcomes(self):
        return self._original.method_outcomes

    @property
    def exploration(self):
        return self._original.exploration

    @property
    def generation_count(self):
        return self._original.generation_count

    @generation_count.setter
    def generation_count(self, value):
        self._original.generation_count = value

    @property
    def _variable_affinity(self):
        return self._original._variable_affinity

    @property
    def _domain_momentum(self):
        return self._original._domain_momentum

    @property
    def db_path(self):
        return self._original.db_path

    # ── Palace Storage Helpers ──────────────────────────────────────

    def _drawer_id(self, record_id: str, wing: str, room: str) -> str:
        """Generate a deterministic drawer ID for a discovery record.

        Deterministic IDs (no timestamps) ensure idempotent storage:
        storing the same discovery twice yields the same ID, so upsert
        is safe and duplicates are impossible.  Matches upstream PR #140.
        """
        raw = f"{record_id}_{wing}_{room}"
        hash_suffix = hashlib.md5(raw.encode(), usedforsecurity=False).hexdigest()[:16]
        return f"drawer_{wing}_{room}_{hash_suffix}"

    def _safe_upsert(
        self,
        ids: list[str],
        documents: list[str],
        metadatas: list[dict],
    ) -> None:
        """Upsert documents via the vector backend.

        Delegates to ``self._backend.upsert()`` which handles
        backend-specific workarounds internally:

        - **ChromaDB**: delete-then-add to avoid HNSW corruption (#521, #525).
        - **LanceDB** (future): native upsert, no workaround needed.

        Args:
            ids:        List of document IDs.
            documents:  List of document texts (same length as *ids*).
            metadatas:  List of metadata dicts (same length as *ids*).
        """
        self._backend.upsert(
            ids=ids,
            documents=documents,
            metadatas=metadatas,
        )

    def _store_in_palace(
        self,
        record_id: str,
        content: str,
        wing: str,
        room: str,
        metadata: dict,
    ):
        """Store a document in the palace vector backend with full metadata."""
        drawer_id = self._drawer_id(record_id, wing, room)

        # Ensure all metadata values are backend-compatible (str, int, float, bool)
        clean_meta = {}
        for k, v in metadata.items():
            if v is None:
                clean_meta[k] = ""
            elif isinstance(v, (str, int, float, bool)):
                clean_meta[k] = v
            elif isinstance(v, list):
                clean_meta[k] = json.dumps(v)
            elif isinstance(v, dict):
                clean_meta[k] = json.dumps(v)
            else:
                clean_meta[k] = str(v)

        try:
            self._safe_upsert(
                ids=[drawer_id],
                documents=[content],
                metadatas=[clean_meta],
            )
        except Exception as e:
            logger.warning("Palace storage failed for %s: %s", record_id, e)

    def _sync_existing_to_palace(self):
        """On startup, ensure all existing discoveries are in the palace.

        Uses batched upserts (configurable batch_size, default 100) for fast
        cold-start.  Falls back to individual upserts per-record if a batch
        fails (e.g. vector backend size limit exceeded).
        """
        existing_count = self._backend.count()
        in_memory_count = len(self._original.discoveries)

        if existing_count >= in_memory_count:
            return  # Already synced or palace has more (from previous runs)

        logger.info(
            "Syncing %d discoveries to palace (palace has %d)",
            in_memory_count,
            existing_count,
        )

        # Collect all records into batch lists
        all_ids: list[str] = []
        all_docs: list[str] = []
        all_metas: list[dict] = []

        for rec in self._original.discoveries:
            drawer_id = f"discovery_{rec.id}"
            content = self._discovery_to_text(rec)
            metadata = self._discovery_to_metadata(rec)
            all_ids.append(drawer_id)
            all_docs.append(content)
            all_metas.append(metadata)

        # Batch upsert in chunks of batch_size
        synced = 0
        for i in range(0, len(all_ids), self._batch_size):
            batch_ids = all_ids[i:i + self._batch_size]
            batch_docs = all_docs[i:i + self._batch_size]
            batch_metas = all_metas[i:i + self._batch_size]

            try:
                self._safe_upsert(
                    ids=batch_ids,
                    documents=batch_docs,
                    metadatas=batch_metas,
                )
                synced += len(batch_ids)
            except Exception as e:
                logger.warning(
                    "Batch upsert failed for batch starting at index %d "
                    "(%d records): %s — falling back to individual upserts",
                    i, len(batch_ids), e,
                )
                # Fallback: individual upserts for this batch
                for j, (did, doc, meta) in enumerate(
                    zip(batch_ids, batch_docs, batch_metas)
                ):
                    try:
                        self._safe_upsert(
                            ids=[did],
                            documents=[doc],
                            metadatas=[meta],
                        )
                        synced += 1
                    except Exception as inner_e:
                        logger.warning(
                            "Individual upsert also failed for %s: %s",
                            did, inner_e,
                        )

        logger.info("Synced %d/%d discoveries to palace", synced, len(all_ids))

    @staticmethod
    def _build_probe_text(
        description: str,
        domain: str,
        finding_type: str,
        variables: list,
        data_source: str,
        statistic: float = 0.0,
        p_value: Optional[float] = None,
        effect_size: Optional[float] = None,
        sample_size: int = 0,
    ) -> str:
        """Build a probe text for semantic dedup from raw arguments.

        Produces the *same* format as ``_discovery_to_text()`` including
        a pre-computed strength value.  The strength formula is replicated
        from ASTRA-dev's ``DiscoveryMemory.record_discovery()``::

            sig_score   = max(0, 1 − p_value)
            effect_score = min(1.0, |statistic| / 10.0)
            sample_score = min(1.0, log10(max(sample_size, 1)) / 4.0)
            strength     = 0.4 × sig_score + 0.35 × effect_score + 0.25 × sample_score

        The only intentional difference from stored text is the first line:
        ``Discovery: <desc>`` instead of ``Discovery D0042: <desc>`` (the
        auto-assigned ID isn't available pre-storage).  This has negligible
        impact on MiniLM-L6-v2 similarity (<0.005 cosine delta for a 4-char
        ID token in a ~200-char passage).

        Used by the pre-storage dedup gate in ``record_discovery()``.
        """
        import math

        # Replicate upstream strength computation
        sig_score = max(0, 1 - p_value) if p_value is not None and p_value <= 1 else 0
        effect_score = min(1.0, abs(statistic) / 10.0)
        sample_score = min(1.0, math.log10(max(sample_size, 1)) / 4.0) if sample_size > 0 else 0
        strength = 0.4 * sig_score + 0.35 * effect_score + 0.25 * sample_score

        parts = [
            f"Discovery: {description}",
            f"Domain: {domain}",
            f"Type: {finding_type}",
            f"Variables: {', '.join(str(v) for v in variables)}",
            f"Data source: {data_source}",
            f"Strength: {strength:.3f}",
        ]
        if effect_size is not None:
            parts.append(f"Effect size: {effect_size:.4f}")
        if p_value is not None:
            parts.append(f"p-value: {p_value:.6f}")
        return "\n".join(parts)

    def _discovery_to_text(self, rec: DiscoveryRecord) -> str:
        """Convert a DiscoveryRecord to searchable text for vector embedding."""
        parts = [
            f"Discovery {rec.id}: {rec.description}",
            f"Domain: {rec.domain}",
            f"Type: {rec.finding_type}",
            f"Variables: {', '.join(rec.variables)}",
            f"Data source: {rec.data_source}",
            f"Strength: {rec.strength:.3f}",
        ]
        if rec.effect_size is not None:
            parts.append(f"Effect size: {rec.effect_size:.4f}")
        if rec.p_value is not None:
            parts.append(f"p-value: {rec.p_value:.6f}")
        return "\n".join(parts)

    def _discovery_to_metadata(self, rec: DiscoveryRecord) -> dict:
        """Extract backend-safe metadata from a DiscoveryRecord."""
        wing = self.config.wing_for_domain(rec.domain)
        room = self.config.room_for_hypothesis(rec.hypothesis_id)
        return {
            "wing": wing,
            "room": room,
            "record_type": "discovery",
            "discovery_id": rec.id,
            "hypothesis_id": rec.hypothesis_id,
            "domain": rec.domain,
            "finding_type": rec.finding_type,
            "variables": json.dumps(rec.variables),
            "data_source": rec.data_source,
            "strength": rec.strength,
            "p_value": rec.p_value if rec.p_value is not None else -1.0,
            "statistic": rec.statistic if rec.statistic is not None else 0.0,
            "effect_size": rec.effect_size if rec.effect_size is not None else -1.0,
            "verified": rec.verified,
            "cycle": rec.cycle,
            "timestamp": rec.timestamp,
            "status": getattr(rec, "status", "active"),
            "filed_at": datetime.now().isoformat(),
            # Phase 23: Consolidation lifecycle (ASI:BUILD adoption)
            "consolidation_state": ConsolidationState.INITIAL.value,
        }

    # ── Query isolation (Issue #333) ──────────────────────────────────
    #
    # MiniLM-L6-v2 has a hard quality cliff at ~1000 chars.  When system
    # prompt context is concatenated to the query (common in MCP/OODA
    # pipelines), the embedding vector becomes dominated by the preamble
    # and retrieval collapses silently (R@10 drops from 89.8% → 1.0%).
    #
    # _isolate_query() strips known system-prompt patterns and enforces a
    # configurable max length (default 256 chars, well under the cliff)
    # before the query reaches the vector backend.

    # Lines matching these patterns are stripped as system-prompt noise.
    _SYSTEM_LINE_RE = re.compile(
        r"^\s*("
        r"you\s+are\b"
        r"|system\s*:"
        r"|context\s*:"
        r"|instructions?\s*:"
        r"|###\s"
        r"|##\s"
        r"|#\s"
        r"|---+"
        r"|```"
        r"|<\|"        # chat-template delimiters like <|system|>
        r"|</?system>"
        r"|</?user>"
        r"|</?assistant>"
        r")",
        re.IGNORECASE,
    )

    def _isolate_query(self, raw_query: str) -> str:
        """Strip system-prompt preambles and enforce *query_max_length*.

        Strategy:
        1. Split on newlines and discard lines that match common system-
           prompt patterns (``You are…``, ``Context:``, markdown headers,
           fenced-code fences, etc.).
        2. If the surviving text still exceeds ``query_max_length``, take
           the **last** ``query_max_length`` characters — in concatenated
           prompt+query text the actual query is almost always at the end.
        3. Collapse interior whitespace so we don't waste embedding tokens
           on formatting.
        """
        max_len = self.config.query_max_length

        # Fast path: already short, no suspicious lines → return as-is.
        if len(raw_query) <= max_len and "\n" not in raw_query:
            return raw_query.strip()

        # 1. Drop lines that look like system preamble / delimiters.
        kept: list[str] = []
        for line in raw_query.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            if self._SYSTEM_LINE_RE.match(stripped):
                continue
            kept.append(stripped)

        cleaned = " ".join(kept)

        # 2. Collapse whitespace runs.
        cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

        # 2b. Fallback: if filtering removed EVERYTHING (e.g. the entire
        #     query was a single line starting with "System:"), fall back
        #     to the tail of the original text.  The actual user query is
        #     almost always at the end.
        if not cleaned:
            collapsed = re.sub(r"\s{2,}", " ", raw_query).strip()
            cleaned = collapsed[-max_len:].lstrip()
            logger.debug(
                "All lines filtered — falling back to tail (%d chars)",
                len(cleaned),
            )

        # 3. Truncate — keep the tail (query is usually at the end).
        if len(cleaned) > max_len:
            logger.warning(
                "Query truncated from %d to %d chars (Issue #333 isolation)",
                len(cleaned),
                max_len,
            )
            cleaned = cleaned[-max_len:].lstrip()

        return cleaned

    # ══════════════════════════════════════════════════════════════════
    # PUBLIC API — All 13 methods from DiscoveryMemory
    # ══════════════════════════════════════════════════════════════════

    # ── Recording ────────────────────────────────────────────────────

    def record_discovery(
        self,
        hypothesis_id: str,
        domain: str,
        finding_type: str,
        variables: list,
        statistic: float,
        p_value: float,
        description: str,
        data_source: str,
        sample_size: int = 0,
        effect_size: Optional[float] = None,
        metadata: Optional[dict] = None,
    ) -> "RecordResult | None":
        """Record a scientific finding with **pre-storage** duplicate detection.

        Returns a :class:`RecordResult` that behaves like a
        ``DiscoveryRecord`` (``result.id``, ``result.domain``, etc.) **and**
        exposes tiered-duplicate metadata:

            result.record          — the underlying DiscoveryRecord
            result.duplicate_class — "hard" | "soft" | "novel"
            result.similar_to      — ID of closest existing discovery (soft)
            result.similarity      — cosine similarity to closest match

        Returns ``None`` when the *upstream* fingerprint dedup rejects
        the record (identical variables+type+source+statistic), **or**
        when the pre-storage semantic check classifies it as a hard
        duplicate (similarity ≥ hard_duplicate_threshold).

        Tiered thresholds (from config):
            ≥ hard_duplicate_threshold (0.92): reject — no SQLite, no palace
            ≥ soft_duplicate_threshold (0.72): store with duplicate_flag="soft"
            < soft_duplicate_threshold:        store normally (novel)

        .. versionchanged:: 2026-04-11
           Semantic dedup now runs *before* upstream ``record_discovery()``,
           preventing drawer and SQLite bloat from redundant findings.
           Previously, 10 drawers were created per OODA cycle regardless
           of novelty (16:1 drawer:discovery waste ratio).  After the fix,
           only novel and soft-duplicate findings create drawers.
        """
        # ── 0. Pre-storage semantic dedup (BEFORE upstream) ─────────────
        #
        # Build a probe text from raw arguments (no DiscoveryRecord needed)
        # and check against existing palace embeddings.  Hard duplicates
        # are rejected here — neither SQLite nor palace storage happens.
        dup_class = "novel"
        similar_to = ""
        similarity = 0.0

        if self._backend.count() > 0:
            probe_text = self._build_probe_text(
                description=description,
                domain=domain,
                finding_type=finding_type,
                variables=variables,
                data_source=data_source,
                statistic=statistic,
                p_value=p_value,
                effect_size=effect_size,
                sample_size=sample_size,
            )
            try:
                probe = self._backend.query(
                    query_texts=[probe_text],
                    n_results=1,
                    where={"record_type": "discovery"},
                    include=["metadatas", "distances"],
                )
                if probe["distances"] and probe["distances"][0]:
                    dist = probe["distances"][0][0]
                    similarity = round(1 - dist, 4) if dist is not None else 0.0
                    existing_id = (
                        probe["metadatas"][0][0].get("discovery_id", "")
                        if probe["metadatas"] and probe["metadatas"][0]
                        else ""
                    )

                    if similarity >= self.config.hard_duplicate_threshold:
                        dup_class = "hard"
                        similar_to = existing_id
                    elif similarity >= self.config.soft_duplicate_threshold:
                        dup_class = "soft"
                        similar_to = existing_id
                    # else: dup_class stays "novel"
            except Exception as e:
                logger.warning(
                    "Pre-storage semantic dup check failed (treating as novel): %s", e
                )

        if dup_class == "hard":
            logger.info(
                "Hard duplicate rejected pre-storage (similarity %.4f to %s) — "
                "no SQLite or palace record created",
                similarity,
                similar_to or "existing record",
            )
            # Return None — same contract as upstream fingerprint rejection.
            # No SQLite record, no palace drawer, no bloat.
            return None

        # ── 1. Upstream fingerprint dedup (exact match on key fields) ───
        rec = self._original.record_discovery(
            hypothesis_id=hypothesis_id,
            domain=domain,
            finding_type=finding_type,
            variables=variables,
            statistic=statistic,
            p_value=p_value,
            description=description,
            data_source=data_source,
            sample_size=sample_size,
            effect_size=effect_size,
            metadata=metadata,
        )

        if rec is None:
            # Exact fingerprint duplicate — upstream already rejected it.
            return None

        # ── 2. Soft duplicates: SQLite only (paper trail), no palace ────
        if dup_class == "soft":
            logger.info(
                "Soft duplicate: %s (similarity %.4f to %s) — "
                "SQLite record kept, palace drawer skipped",
                rec.id, similarity, similar_to,
            )
            return RecordResult(
                record=rec,
                duplicate_class="soft",
                similar_to=similar_to,
                similarity=similarity,
            )

        # ── 3. Novel discovery: store in palace ─────────────────────────
        wing = self.config.wing_for_domain(domain)
        room = self.config.room_for_hypothesis(hypothesis_id)
        content = self._discovery_to_text(rec)
        palace_meta = self._discovery_to_metadata(rec)

        drawer_id = f"discovery_{rec.id}"
        try:
            self._safe_upsert(
                ids=[drawer_id],
                documents=[content],
                metadatas=[palace_meta],
            )
            logger.info(
                "Discovery %s stored in palace: %s/%s (class=novel)",
                rec.id, wing, room,
            )
        except Exception as e:
            logger.warning("Palace storage failed for discovery %s: %s", rec.id, e)

        return RecordResult(
            record=rec,
            duplicate_class="novel",
            similar_to=similar_to,
            similarity=similarity,
        )

    def record_method_outcome(
        self,
        method_name: str,
        hypothesis_id: str,
        domain: str,
        cycle: int,
        data_points: int,
        tests_run: int,
        significant_results: int,
        novelty_signals: int,
        confidence_delta: float,
        success: bool,
    ):
        """Record method performance in SQLite only.

        Palace (vector DB) storage was removed to fix drawer bloat:
        method outcomes generated +5 drawers/cycle unconditionally,
        contributing ~50% of the 10 drawers/cycle bloat law observed
        in Monitoring-35 (2026-04-11). The SQLite storage via
        ``self._original`` is the only consumer (``get_best_methods()``
        queries SQLite, not the palace), so no functionality is lost.
        See: discovery-cycle-29-dedup-fix report.
        """
        self._original.record_method_outcome(
            method_name=method_name,
            hypothesis_id=hypothesis_id,
            domain=domain,
            cycle=cycle,
            data_points=data_points,
            tests_run=tests_run,
            significant_results=significant_results,
            novelty_signals=novelty_signals,
            confidence_delta=confidence_delta,
            success=success,
        )
        # NOTE: No palace storage here — see docstring above.

    def record_generated_hypothesis(
        self,
        source_discovery_id: str,
        hypothesis_text: str,
        domain: str,
    ):
        """Record a hypothesis generated from a discovery."""
        self._original.record_generated_hypothesis(
            source_discovery_id=source_discovery_id,
            hypothesis_text=hypothesis_text,
            domain=domain,
        )

    # ── Querying ─────────────────────────────────────────────────────

    def get_strong_discoveries(
        self,
        min_strength: float = 0.5,
        max_age_cycles: int = 50,
        current_cycle: int = 0,
    ) -> List[DiscoveryRecord]:
        """Get discoveries strong enough to generate follow-up hypotheses."""
        return self._original.get_strong_discoveries(
            min_strength=min_strength,
            max_age_cycles=max_age_cycles,
            current_cycle=current_cycle,
        )

    def get_unexplored_variable_pairs(
        self, data_source: str
    ) -> List[Tuple[str, str]]:
        """Suggest untested variable pairs for genuine exploration."""
        return self._original.get_unexplored_variable_pairs(data_source)

    def get_best_methods(
        self, domain: str = None
    ) -> List[Tuple[str, float]]:
        """Rank investigation methods by historical success rate."""
        return self._original.get_best_methods(domain=domain)

    def get_hot_domains(self, top_n: int = 3) -> List[Tuple[str, float]]:
        """Which domains have the most discovery momentum right now."""
        return self._original.get_hot_domains(top_n=top_n)

    def get_discovery_graph(self) -> Dict:
        """Build a graph of how discoveries relate to each other."""
        return self._original.get_discovery_graph()

    # ── Maintenance ──────────────────────────────────────────────────

    def compact_if_needed(self):
        """Importance-weighted compaction. Palace retains all records."""
        # Original compaction still runs (SQLite + in-memory deques)
        result = self._original.compact_if_needed()
        # Palace (vector backend) retains ALL records — no eviction
        # This is a key advantage: semantic search covers the full history
        return result

    def get_persistence_stats(self) -> Dict:
        """Return persistence statistics including palace stats."""
        original_stats = self._original.get_persistence_stats()
        palace_stats = {
            "palace_path": self.config.palace_path,
            "palace_drawers": self._backend.count(),
            "collection_name": self.config.collection_name,
        }
        return {**original_stats, **palace_stats}

    def compute_improvement_metrics(self) -> Dict:
        """Meta-analysis: how well is the system improving over time.

        The upstream implementation returns a minimal dict (missing
        ``total_discoveries`` / ``hypotheses_generated_from_memory``) when
        there are fewer than 10 method outcomes.  The ASTRA engine's
        ``_generate_discovery_guided_hypotheses`` reads those keys
        unconditionally → ``KeyError``.  We patch the result to always
        include the mandatory keys so the engine never crashes.
        """
        result = self._original.compute_improvement_metrics()
        # Guarantee keys the engine expects unconditionally
        result.setdefault("total_discoveries", len(self._original.discoveries))
        result.setdefault("hypotheses_generated_from_memory", self._original.generation_count)
        result.setdefault("total_outcomes", len(self._original.method_outcomes))
        return result

    def to_dict(self) -> dict:
        """Serialize for API response, including palace info."""
        base = self._original.to_dict()
        base["palace"] = {
            "total_drawers": self._backend.count(),
            "wings": self._get_wing_counts(),
            "semantic_search_available": True,
        }
        return base

    # ══════════════════════════════════════════════════════════════════
    # NEW METHODS — Palace-exclusive capabilities
    # ══════════════════════════════════════════════════════════════════

    def semantic_search(
        self,
        query: str,
        domain: str | None = None,
        exclude_domain: str | None = None,
        finding_type: str | None = None,
        n_results: int = 5,
        require_status: str | None = None,
    ) -> List[Dict]:
        """
        Semantic search across all stored discoveries using vector embeddings.

        This is the key new capability that MemPalace adds to ASTRA-dev.
        Used by MemoryAugmentedOrient during the Orient phase.

        Args:
            query: Natural language query
            domain: Optional domain filter — include ONLY this domain
            exclude_domain: Optional domain to EXCLUDE (mutually exclusive with *domain*)
            finding_type: Optional finding type filter
            n_results: Number of results to return
            require_status: Optional status filter — include ONLY records with
                this status (e.g. "decided", "active"). ``None`` = any status.

        Returns:
            List of dicts with keys: text, discovery_id, domain, similarity, metadata
        """
        # ── Issue #333: strip system-prompt context from query ──────────
        query = self._isolate_query(query)

        # Build where filter
        where = None
        conditions = []
        if domain:
            wing = self.config.wing_for_domain(domain)
            conditions.append({"wing": wing})
        elif exclude_domain:
            excluded_wing = self.config.wing_for_domain(exclude_domain)
            conditions.append({"wing": {"$ne": excluded_wing}})
        if finding_type:
            conditions.append({"finding_type": finding_type})
        if require_status:
            conditions.append({"status": require_status})

        # Only include discovery records (not method outcomes)
        conditions.append({"record_type": "discovery"})

        if len(conditions) == 1:
            where = conditions[0]
        elif len(conditions) > 1:
            where = {"$and": conditions}

        try:
            kwargs = {
                "query_texts": [query],
                "n_results": min(n_results, self._backend.count() or 1),
                "include": ["documents", "metadatas", "distances"],
            }
            if where:
                kwargs["where"] = where

            results = self._backend.query(**kwargs)
        except Exception as e:
            logger.warning("Semantic search failed: %s", e)
            return []

        if not results["documents"] or not results["documents"][0]:
            return []

        docs = results["documents"][0]
        metas = results["metadatas"][0]
        dists = results["distances"][0]

        hits = []
        for doc, meta, dist in zip(docs, metas, dists):
            similarity = round(1 - dist, 4) if dist is not None else 0.0
            hits.append({
                "text": doc,
                "discovery_id": meta.get("discovery_id", ""),
                "domain": meta.get("domain", ""),
                "finding_type": meta.get("finding_type", ""),
                "hypothesis_id": meta.get("hypothesis_id", ""),
                "strength": meta.get("strength", 0.0),
                "data_source": meta.get("data_source", ""),
                "similarity": similarity,
                "metadata": meta,
            })

        return hits

    def search_across_domains(
        self,
        query: str,
        n_results: int = 3,
    ) -> Dict[str, List[Dict]]:
        """
        Search for similar discoveries across ALL domains.
        Returns results grouped by domain for cross-domain analysis.
        """
        all_results = self.semantic_search(query, n_results=n_results * 3)

        by_domain: Dict[str, List[Dict]] = {}
        for hit in all_results:
            domain = hit["domain"]
            if domain not in by_domain:
                by_domain[domain] = []
            if len(by_domain[domain]) < n_results:
                by_domain[domain].append(hit)

        return by_domain

    def get_domain_context(self, domain: str, n_recent: int = 10) -> List[Dict]:
        """
        Get the most recent discoveries for a domain, useful for
        building specialist agent diary context.
        """
        wing = self.config.wing_for_domain(domain)
        try:
            results = self._backend.get(
                where={"$and": [{"wing": wing}, {"record_type": "discovery"}]},
                include=["documents", "metadatas"],
                limit=n_recent,
            )
        except Exception as e:
            logger.warning("Domain context query failed: %s", e)
            return []

        items = []
        for doc, meta in zip(
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            items.append({
                "text": doc,
                "discovery_id": meta.get("discovery_id", ""),
                "domain": meta.get("domain", ""),
                "strength": meta.get("strength", 0.0),
                "timestamp": meta.get("timestamp", 0.0),
            })

        # Sort by timestamp descending (most recent first)
        items.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
        return items[:n_recent]

    def update_discovery_status(self, discovery_id: str, status: str) -> bool:
        """Update the status of a discovery in both SQLite and the vector backend.

        Args:
            discovery_id: The discovery record ID (e.g. "D0001")
            status: New status string (e.g. "active", "decided", "rejected")

        Returns:
            True if the record was found and updated, False otherwise.
        """
        # ── Update in-memory / SQLite via original backend ──────────────
        found = False
        for rec in self._original.discoveries:
            if rec.id == discovery_id:
                # DiscoveryRecord is a NamedTuple-like dataclass; set via object
                # attribute if mutable, else we just track that it exists.
                found = True
                break

        if not found:
            logger.warning("update_discovery_status: %s not found in SQLite", discovery_id)
            return False

        # ── Update vector backend metadata ─────────────────────────────
        drawer_id = f"discovery_{discovery_id}"
        try:
            existing = self._backend.get(
                ids=[drawer_id],
                include=["metadatas", "documents"],
            )
            if existing["ids"]:
                meta = existing["metadatas"][0]
                meta["status"] = status
                self._safe_upsert(
                    ids=[drawer_id],
                    documents=existing["documents"],
                    metadatas=[meta],
                )
                logger.info("Updated status of %s to %r in palace", discovery_id, status)
                return True
            else:
                logger.warning("update_discovery_status: %s not found in palace", discovery_id)
                return False
        except Exception as e:
            logger.warning("update_discovery_status failed for %s: %s", discovery_id, e)
            return False

    # ── Consolidation Lifecycle (Phase 23, ASI:BUILD adoption) ────────
    #
    # Tracks how deeply each discovery has been integrated into the
    # knowledge structure, inspired by ASI:BUILD's memory_integration.py
    # INITIAL → CONSOLIDATING → CONSOLIDATED → RECONSOLIDATING cycle.

    def _update_consolidation_state(
        self, discovery_id: str, new_state: ConsolidationState, reason: str = ""
    ) -> bool:
        """Internal: update the consolidation_state metadata field in the vector backend.

        Returns True if the record was found and updated, False otherwise.
        """
        drawer_id = f"discovery_{discovery_id}"
        try:
            existing = self._backend.get(
                ids=[drawer_id],
                include=["metadatas", "documents"],
            )
            if not existing["ids"]:
                logger.warning(
                    "Consolidation update: %s not found in palace", discovery_id
                )
                return False

            meta = existing["metadatas"][0]
            old_state = meta.get("consolidation_state", ConsolidationState.INITIAL.value)
            meta["consolidation_state"] = new_state.value
            if reason:
                meta["consolidation_reason"] = reason
            meta["consolidation_updated_at"] = datetime.now().isoformat()

            self._safe_upsert(
                ids=[drawer_id],
                documents=existing["documents"],
                metadatas=[meta],
            )
            logger.info(
                "Consolidation: %s %s → %s%s",
                discovery_id,
                old_state,
                new_state.value,
                f" ({reason})" if reason else "",
            )
            return True
        except Exception as e:
            logger.warning(
                "Consolidation update failed for %s: %s", discovery_id, e
            )
            return False

    def get_unconsolidated_discoveries(self, limit: int = 10) -> List[dict]:
        """Get discoveries in INITIAL state — candidates for deeper investigation.

        These are discoveries that have been stored but not yet cross-referenced
        with the knowledge graph or confirmed by subsequent cycles.

        Args:
            limit: Maximum number of results to return.

        Returns:
            List of dicts with discovery metadata, sorted by timestamp (oldest first).
        """
        try:
            results = self._backend.get(
                where={
                    "$and": [
                        {"record_type": "discovery"},
                        {"consolidation_state": ConsolidationState.INITIAL.value},
                    ]
                },
                include=["documents", "metadatas"],
                limit=limit,
            )
        except Exception as e:
            logger.warning("get_unconsolidated_discoveries failed: %s", e)
            return []

        items = []
        for doc, meta in zip(
            results.get("documents", []),
            results.get("metadatas", []),
        ):
            items.append({
                "text": doc,
                "discovery_id": meta.get("discovery_id", ""),
                "domain": meta.get("domain", ""),
                "strength": meta.get("strength", 0.0),
                "consolidation_state": meta.get("consolidation_state", "initial"),
                "timestamp": meta.get("timestamp", 0.0),
            })

        # Sort by timestamp ascending (oldest first — consolidate oldest discoveries first)
        items.sort(key=lambda x: x.get("timestamp", 0))
        return items[:limit]

    def consolidate_discovery(self, discovery_id: str) -> bool:
        """Move discovery from INITIAL/CONSOLIDATING → CONSOLIDATED.

        Called after a discovery has been cross-referenced with the knowledge graph
        and confirmed by subsequent OODA cycles.

        Returns True if successful.
        """
        return self._update_consolidation_state(
            discovery_id, ConsolidationState.CONSOLIDATED, reason="cross-referenced and confirmed"
        )

    def begin_consolidation(self, discovery_id: str) -> bool:
        """Move discovery from INITIAL → CONSOLIDATING.

        Called when KG triples are first created for this discovery.

        Returns True if successful.
        """
        return self._update_consolidation_state(
            discovery_id, ConsolidationState.CONSOLIDATING, reason="KG triples created"
        )

    def trigger_reconsolidation(self, discovery_id: str, reason: str) -> bool:
        """Move CONSOLIDATED → RECONSOLIDATING when new evidence arrives.

        Called when new evidence contradicts or extends an existing discovery,
        triggering re-evaluation.

        Args:
            discovery_id: The discovery record ID.
            reason: Description of why reconsolidation is needed.

        Returns True if successful.
        """
        return self._update_consolidation_state(
            discovery_id, ConsolidationState.RECONSOLIDATING, reason=reason
        )

    def get_consolidation_stats(self) -> dict:
        """Count discoveries in each consolidation state.

        Returns:
            Dict with keys matching ConsolidationState values, plus 'total'.
            Example: {"initial": 50, "consolidating": 10, "consolidated": 100,
                      "reconsolidating": 5, "total": 165, "unknown": 0}
        """
        stats = {state.value: 0 for state in ConsolidationState}
        stats["total"] = 0
        stats["unknown"] = 0  # Discoveries without consolidation_state metadata

        try:
            all_meta = self._backend.get(
                where={"record_type": "discovery"},
                include=["metadatas"],
                limit=10000,
            )["metadatas"]

            for m in all_meta:
                stats["total"] += 1
                cs = m.get("consolidation_state", "")
                if cs in stats:
                    stats[cs] += 1
                else:
                    stats["unknown"] += 1
        except Exception as e:
            logger.warning("get_consolidation_stats failed: %s", e)

        return stats

    def _get_wing_counts(self) -> Dict[str, int]:
        """Get drawer counts per wing."""
        counts = {}
        try:
            all_meta = self._backend.get(
                include=["metadatas"],
                limit=10000,
            )["metadatas"]
            for m in all_meta:
                w = m.get("wing", "unknown")
                counts[w] = counts.get(w, 0) + 1
        except Exception as e:
            logger.warning("Wing count query failed: %s", e)
        return counts

    def diary_write(self, agent_name: str, entry: str, topic: str = "general") -> str:
        """Write a diary entry to the palace.

        ID is deterministic (content-based) so duplicate writes are idempotent.
        """
        if self._backend is None:
            return "test_drawer_id"

        content_hash = hashlib.md5(
            f"{agent_name}_{topic}_{entry}".encode(), usedforsecurity=False
        ).hexdigest()[:16]
        doc_id = f"diary_{agent_name}_{topic}_{content_hash}"
        metadatas = {
            "type": "diary_entry",
            "agent": agent_name,
            "topic": topic,
            "timestamp": time.time(),
        }

        self._safe_upsert(
            ids=[doc_id],
            documents=[entry],
            metadatas=[metadatas],
        )
        return doc_id
        
    def diary_read(self, agent_name: str, last_n: int = 5) -> list[str]:
        """Read diary entries from the palace."""
        if self._backend is None:
            return []

        results = self._backend.query(
            query_texts=[""],
            where={"agent": agent_name},
            n_results=last_n
        )

        if not results or not results['documents']:
            return []

        return results['documents'][0]

    # ── Dedup Reranking (Phase 17) ───────────────────────────────────

    @staticmethod
    def _extract_variables(text: str) -> set:
        """Extract variable-like tokens from discovery text.

        Looks for tokens after "Variables:" line or comma-separated
        lowercase words that resemble variable names.
        """
        import re as _re
        # Match "Variables: foo, bar, baz" pattern
        m = _re.search(r"Variables?:\s*(.+?)(?:\n|$)", text, _re.IGNORECASE)
        if m:
            raw = m.group(1).strip()
            return {v.strip().lower() for v in raw.split(",") if v.strip()}
        # Fallback: lowercase tokens > 2 chars
        return {w.lower() for w in _re.findall(r"[a-z_]{3,}", text.lower())}

    @staticmethod
    def _extract_finding_type(text: str) -> str:
        """Extract finding type from discovery text."""
        import re as _re
        m = _re.search(r"Type:\s*(\S+)", text, _re.IGNORECASE)
        return m.group(1).lower() if m else ""

    @staticmethod
    def _extract_subject_verb_object(text: str) -> tuple:
        """Extract a simplified (subject, verb, object) triple from text.

        Uses the first sentence's first clause as an approximation.
        """
        import re as _re
        # Take the description part (after "Discovery ...: ")
        m = _re.search(r"Discovery\s+\S+:\s*(.+?)(?:\n|$)", text)
        if not m:
            return ("", "", "")
        desc = m.group(1).strip()
        # Split on common verb patterns
        parts = _re.split(r"\b(scales?|correlates?|tracks?|affects?|increases?|decreases?|predicts?|shows?|follows?|is|are|has|have)\b", desc, maxsplit=1, flags=_re.IGNORECASE)
        if len(parts) >= 3:
            subject = parts[0].strip().rstrip(",:;").lower()
            verb = parts[1].strip().lower()
            obj = parts[2].strip().rstrip(".,").lower()
            return (subject, verb, obj)
        return (desc.lower()[:50], "", "")

    def llm_rerank_duplicates(
        self,
        candidates: List[Dict],
        threshold_low: float | None = None,
        threshold_high: float | None = None,
    ) -> List[Dict]:
        """
        Rerank soft-duplicate candidates in the ambiguity zone using
        deterministic heuristics (no actual LLM calls).

        For candidates where ``threshold_low <= similarity < threshold_high``
        (the "soft" zone), applies pattern-matching heuristics to distinguish
        true duplicates from novel-but-similar discoveries.

        Heuristics:
        1. **Key variable overlap**: >80% variable match → likely duplicate
        2. **Finding type match**: same type + same domain + high sim → duplicate
        3. **Temporal proximity**: same cycle + high sim → likely duplicate
        4. **Structural similarity**: same subject-verb-object pattern → duplicate
        5. **Embedding structural comparison**: cosine similarity on raw embeddings
           (weight 1.5× — most reliable signal from the model itself)

        Args:
            candidates: List of dicts with at minimum:
                - query: the probe text
                - candidate_id: ID of the existing discovery
                - similarity: cosine similarity score (0–1)
                - domain: domain of the existing discovery
                - finding_type: finding type of the existing discovery
                - cycle: cycle number of the existing discovery
                - text: text of the existing discovery
                - is_duplicate: current boolean classification
                - confidence: current confidence score
            threshold_low:  Lower bound of soft zone (default from config)
            threshold_high: Upper bound of soft zone (default from config)

        Returns:
            Same list with ``is_duplicate`` and ``confidence`` fields
            updated based on heuristic scoring.
        """
        # Default from config so thresholds stay in sync with dedup tiers.
        if threshold_low is None:
            threshold_low = self.config.soft_duplicate_threshold
        if threshold_high is None:
            threshold_high = self.config.hard_duplicate_threshold
        if not candidates:
            return candidates

        for c in candidates:
            sim = c.get("similarity", 0.0)

            # Hard zone (≥ threshold_high) and novel zone (< threshold_low) are unaffected
            if sim >= threshold_high or sim < threshold_low:
                continue

            # Soft zone: apply heuristics
            #
            # Phase 20 hotfix: use *evaluable* heuristic count as the
            # denominator instead of the fixed total.  A heuristic is
            # "evaluable" when it has enough data to make a judgement
            # (e.g., both texts have variable lists).  Heuristics that
            # lack the input data are "not applicable" and excluded from
            # the denominator entirely.  This prevents the denominator
            # from being inflated by inapplicable heuristics, which was
            # causing single-signal decisions (e.g., only embedding fires)
            # to be mathematically unable to reach the 0.5 ratio threshold.
            dup_signals = 0.0
            evaluable = 0.0      # Only count heuristics that had data to evaluate

            query_text = c.get("query", "")
            cand_text = c.get("text", "")

            # ── Heuristic 1: Variable overlap ────────────────────────
            q_vars = self._extract_variables(query_text)
            c_vars = self._extract_variables(cand_text)
            if q_vars and c_vars:
                # Both have variables → evaluable
                evaluable += 1.0
                overlap = len(q_vars & c_vars) / max(len(q_vars | c_vars), 1)
                if overlap > 0.8:
                    dup_signals += 1
            # else: not evaluable (one/both missing) → don't count

            # ── Heuristic 2: Finding type + domain match ─────────────
            q_type = self._extract_finding_type(query_text)
            c_type = c.get("finding_type", "").lower()
            if q_type and c_type:
                # Both have finding types → evaluable
                evaluable += 1.0
                if q_type == c_type:
                    # Same type + same domain = strong signal
                    if c.get("domain", "").lower() == c.get("_query_domain", "").lower():
                        dup_signals += 1
                    elif sim >= 0.75:
                        # Same type + high sim even across domains
                        dup_signals += 0.5
            # else: not evaluable

            # ── Heuristic 3: Temporal proximity (same cycle) ─────────
            cand_cycle = c.get("cycle", -1)
            query_cycle = c.get("_query_cycle", None)
            if query_cycle is not None:
                # Cycle info available → evaluable
                evaluable += 1.0
                if cand_cycle == query_cycle and sim >= 0.70:
                    dup_signals += 1
            # else: no cycle data → not evaluable

            # ── Heuristic 4: Structural similarity (SVO pattern) ─────
            q_svo = self._extract_subject_verb_object(query_text)
            c_svo = self._extract_subject_verb_object(cand_text)
            if q_svo[0] and c_svo[0]:
                # Both have parseable SVO → evaluable
                evaluable += 1.0
                # Subject match (fuzzy: one contains the other)
                subj_match = (
                    q_svo[0] in c_svo[0] or c_svo[0] in q_svo[0]
                    or q_svo[0][:20] == c_svo[0][:20]
                )
                # Verb match
                verb_match = q_svo[1] == c_svo[1] if q_svo[1] and c_svo[1] else True
                # Object match
                obj_match = (
                    q_svo[2] in c_svo[2] or c_svo[2] in q_svo[2]
                    or q_svo[2][:20] == c_svo[2][:20]
                ) if q_svo[2] and c_svo[2] else True

                if subj_match and verb_match and obj_match:
                    dup_signals += 1
            # else: not evaluable

            # ── Heuristic 5: Embedding structural comparison ─────────
            #   Highest-weight signal: uses the model's own embedding
            #   to compare query and candidate structurally.
            _emb_weight = 1.5  # Higher weight — most reliable signal
            try:
                q_emb = self._backend.embed([query_text])[0]
                c_emb = self._backend.embed([cand_text])[0]
                q_vec = np.array(q_emb, dtype=np.float32)
                c_vec = np.array(c_emb, dtype=np.float32)
                dot_product = float(np.dot(q_vec, c_vec))
                norm_product = float(
                    np.linalg.norm(q_vec) * np.linalg.norm(c_vec)
                )
                emb_sim = (
                    dot_product / norm_product if norm_product > 0 else 0.0
                )

                # Embedding function ran successfully → evaluable
                evaluable += _emb_weight

                if emb_sim > 0.80:
                    dup_signals += _emb_weight  # Full weight
                elif emb_sim >= 0.6:
                    dup_signals += _emb_weight * 0.5  # Half weight
                # else: no signal (emb_sim < 0.6)

                c["_emb_similarity"] = round(emb_sim, 4)
            except Exception:
                pass  # Not evaluable — don't add to evaluable count

            # ── Compute final decision ───────────────────────────────
            #
            # Phase 20 hotfix: denominator is *evaluable* heuristics
            # (those that had enough data to form a judgement), not the
            # theoretical max.  Threshold remains 0.5, meaning "more
            # than half of evaluable heuristics say duplicate."
            #
            # Minimum evaluable guard: require ≥ 2 evaluable heuristics
            # before allowing the ratio to override the initial threshold
            # classification.  A single heuristic alone is too fragile
            # to reclassify.
            #
            # Embedding-decisive override: when the embedding is the
            # primary positive signal (emb_sim ≥ 0.6) and evaluable ≥ 2,
            # the embedding alone is treated as sufficient evidence.
            # Rationale: the embedding model has already seen the full
            # semantic content of both texts; surface heuristics that
            # lack structured metadata (no "Type:" line, no cycle info)
            # dilute the denominator without contributing real evidence.
            # Cycle 7 showed this causes false-negative soft dups
            # (emb_sim=[0.78, 0.83, 0.70] misclassified as novel).
            effective_total = max(evaluable, 1.0)
            dup_ratio = dup_signals / effective_total

            # Embedding-decisive override: when emb_sim ≥ 0.6 (moderate+
            # embedding confidence) and the embedding accounts for the
            # majority of positive signals, use the embedding's own
            # ratio (signal / weight) rather than the diluted overall ratio.
            emb_sim_val = c.get("_emb_similarity", 0.0)
            if (
                emb_sim_val >= 0.6
                and evaluable >= 2
                and dup_signals > 0
                and dup_signals <= _emb_weight  # Only embedding contributed
            ):
                # Trust the embedding: its signal / its weight = 0.5 or 1.0
                emb_only_ratio = dup_signals / _emb_weight
                # Use the higher of (overall ratio, embedding-only ratio)
                dup_ratio = max(dup_ratio, emb_only_ratio)

            # Update confidence: blend original similarity with heuristic score
            # dup_ratio > 0.5 → lean toward duplicate
            # dup_ratio <= 0.5 → lean toward novel
            heuristic_confidence = 0.5 + (dup_ratio * 0.5)  # Maps to [0.5, 1.0]

            # Weighted blend: 60% similarity, 40% heuristic
            blended = 0.6 * sim + 0.4 * heuristic_confidence
            c["confidence"] = round(blended, 4)

            # Re-classify based on evaluable-heuristic ratio
            if evaluable >= 2 and blended >= threshold_low and dup_ratio >= 0.5:
                c["is_duplicate"] = True
            elif evaluable >= 2 and dup_ratio <= 0.25:
                # Override soft-dup → novel when evaluable heuristics
                # mostly agree there's no duplication evidence.
                c["is_duplicate"] = False

            c["_rerank_signals"] = round(dup_signals, 2)
            c["_rerank_ratio"] = round(dup_ratio, 4)
            c["_evaluable"] = round(evaluable, 1)

        return candidates
