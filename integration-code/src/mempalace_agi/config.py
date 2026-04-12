"""
MemPalace-AGI Configuration
"""

import os
from dataclasses import dataclass, field
from typing import Dict


@dataclass
class IntegrationConfig:
    """Central configuration for the MemPalace-AGI integration."""

    # Palace storage
    palace_path: str = ""
    collection_name: str = "mempalace_agi_drawers"

    # Knowledge graph
    kg_db_path: str = ""

    # ASTRA discovery SQLite (backward compat)
    discovery_db_path: str = ""

    # Semantic search defaults
    semantic_search_results: int = 5
    orient_memory_depth: int = 5

    # Batch sync settings
    batch_size: int = 100

    # ── Query isolation (Issue #333) ─────────────────────────────────
    # MiniLM-L6-v2 embedding quality degrades sharply above ~1000 chars;
    # system-prompt preambles concatenated to the query can push past
    # that cliff and destroy retrieval (R@10 drops from 89.8% to 1.0%).
    # This limit is applied by _isolate_query() before any ChromaDB call.
    #
    # Raised from 256→500 (2026-04-11): orient composite queries are
    # consistently 485 chars of legitimate scientific content (hypothesis
    # names + descriptions + variables). At 256 we were losing 47% of
    # the query, degrading retrieval. 500 is aligned with upstream
    # MemPalace PR #385 (query_sanitizer.py MAX_QUERY_LENGTH=500) and
    # still well under the 1000-char MiniLM cliff.
    query_max_length: int = 500

    # ── Tiered duplicate detection ──────────────────────────────────
    # ChromaDB's default all-MiniLM-L6-v2 embeddings saturate similarity
    # below 0.90 for paraphrased text; true duplicates typically score ~0.85.
    #
    # Hard threshold (≥0.86): near-verbatim copies → auto-reject
    # Soft threshold (0.55–0.86): moderate paraphrases → store with flag
    # Novel (<0.55): genuinely new content → store normally
    #
    # Cycle 2 analysis showed 0.84 only catches verbatim dupes; moderate
    # rephrasings (sim 0.55–0.72) slipped through.  The soft tier catches
    # those while still storing them for review.
    # Cycle 3 raised hard from 0.84→0.86 (paraphrases at 0.85 were being
    # hard-rejected) and lowered soft from 0.60→0.55 (reduces false
    # positives on cross-domain terms).
    # Cycle 29 (drawer bloat fix): raised hard 0.86→0.92 to reject
    # near-identical findings. In the 431-cycle corpus, 98.4% of stored
    # drawers had NN sim ≥ 0.90 — threshold of 0.92 catches ~87% of
    # redundant drawers. Raised soft 0.55→0.72 to flag moderate
    # paraphrases earlier. See Monitoring-35 analysis: +10 drawers/cycle
    # law, 12.2:1 bloat ratio.
    hard_duplicate_threshold: float = 0.92
    soft_duplicate_threshold: float = 0.72

    @property
    def duplicate_threshold(self) -> float:
        """Backward-compatible alias → hard_duplicate_threshold."""
        return self.hard_duplicate_threshold

    @duplicate_threshold.setter
    def duplicate_threshold(self, value: float):
        """Backward-compatible alias → hard_duplicate_threshold."""
        self.hard_duplicate_threshold = value

    # Domain → Wing mapping
    # Includes all domains from ASTRA-dev's HypothesisGenerator.ALL_DOMAINS
    # plus the diversification domains (Physics, Cosmology) added in
    # generate_diversification_hypotheses() (upstream commit cf60b52).
    domain_wings: Dict[str, str] = field(default_factory=lambda: {
        "Astrophysics": "wing_astrophysics",
        "Economics": "wing_economics",
        "Climate": "wing_climate",
        "Epidemiology": "wing_epidemiology",
        "Cryptography": "wing_cryptography",
        "Physics": "wing_physics",
        "Cosmology": "wing_cosmology",
        "Cross-Domain": "wing_crossdomain",
        "CrossDomain": "wing_crossdomain",
        "General": "wing_general",
    })

    def __post_init__(self):
        base = os.path.expanduser("~/.mempalace-agi")
        if not self.palace_path:
            self.palace_path = os.path.join(base, "palace")
        if not self.kg_db_path:
            self.kg_db_path = os.path.join(base, "knowledge_graph.sqlite3")
        if not self.discovery_db_path:
            self.discovery_db_path = os.path.join(base, "astra_discoveries.db")

    def wing_for_domain(self, domain: str) -> str:
        """Map an ASTRA domain string to a palace wing name."""
        return self.domain_wings.get(domain, f"wing_{domain.lower().replace(' ', '_')}")

    def room_for_hypothesis(self, hypothesis_id: str) -> str:
        """Map an ASTRA hypothesis ID to a palace room name."""
        return f"room_{hypothesis_id}"
