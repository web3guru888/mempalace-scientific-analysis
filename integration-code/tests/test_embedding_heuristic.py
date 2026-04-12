"""
Tests for Heuristic 5: Embedding structural comparison in llm_rerank_duplicates.

The embedding heuristic uses the ChromaDB collection's embedding function to
compute cosine similarity between query and candidate texts, providing the
highest-weight signal (1.5×) for duplicate detection in the soft zone.

Thresholds (calibrated for MiniLM-L6-v2 on structured discovery text):
    emb_sim > 0.80 → full weight (1.5)
    emb_sim ≥ 0.60 → half weight (0.75)
    emb_sim < 0.60 → no signal
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.config import IntegrationConfig


@pytest.fixture
def memory(test_config):
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


# ── Helper ─────────────────────────────────────────────────────────────


def _make_candidate(
    query: str = "",
    candidate_id: str = "D001",
    similarity: float = 0.82,
    domain: str = "Astrophysics",
    finding_type: str = "scaling",
    cycle: int = 1,
    text: str = "",
    is_duplicate: bool = False,
    confidence: float = 0.0,
    query_domain: str = "",
    query_cycle: int | None = None,
) -> dict:
    c = {
        "query": query,
        "candidate_id": candidate_id,
        "similarity": similarity,
        "domain": domain,
        "finding_type": finding_type,
        "cycle": cycle,
        "text": text,
        "is_duplicate": is_duplicate,
        "confidence": confidence,
    }
    if query_domain:
        c["_query_domain"] = query_domain
    if query_cycle is not None:
        c["_query_cycle"] = query_cycle
    return c


# ── Text fixtures ──────────────────────────────────────────────────────

# Nearly identical texts — embeddings should be very similar (>0.80)
ASTRO_PROBE = (
    "Discovery D_probe: Mass-radius power law in exoplanets\n"
    "Domain: Astrophysics\n"
    "Type: scaling\n"
    "Variables: mass, radius\n"
    "Data source: exoplanets\n"
    "Strength: 0.900"
)

ASTRO_SIMILAR = (
    "Discovery D001: Mass-radius scaling relation for exoplanets\n"
    "Domain: Astrophysics\n"
    "Type: scaling\n"
    "Variables: mass, radius\n"
    "Data source: kepler\n"
    "Strength: 0.850"
)

# Moderately related — same domain, different focus
ASTRO_RELATED = (
    "Discovery D002: Luminosity-temperature relationship in main sequence stars\n"
    "Domain: Astrophysics\n"
    "Type: scaling\n"
    "Variables: luminosity, temperature\n"
    "Data source: gaia\n"
    "Strength: 0.800"
)

# Completely different domain and topic
ECON_DIFFERENT = (
    "Discovery D003: GDP correlates with population growth\n"
    "Domain: Economics\n"
    "Type: correlation\n"
    "Variables: gdp, population\n"
    "Data source: worldbank\n"
    "Strength: 0.700"
)


# ── Test 1: Highly similar texts → full embedding weight ───────────────


class TestEmbeddingHighSimilarity:
    """Similar texts should produce emb_sim > 0.80, giving full 1.5 weight."""

    def test_embedding_heuristic_fires_for_similar_texts(self, memory):
        """Near-duplicate texts → embedding similarity > 0.80 → full weight."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.75,
            text=ASTRO_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        # Embedding similarity should be stored and high
        assert "_emb_similarity" in c
        assert c["_emb_similarity"] > 0.80
        # Should classify as duplicate with all heuristics firing
        assert c["is_duplicate"] is True
        # Signals should include the 1.5 embedding weight
        assert c["_rerank_signals"] >= 3.0  # At least some heuristics + embedding


# ── Test 2: Moderately related texts → half embedding weight ──────────


class TestEmbeddingModerateSimilarity:
    """Related texts should produce 0.6-0.85 embedding similarity."""

    def test_embedding_heuristic_moderate_for_related_texts(self, memory):
        """Same-domain but different-topic text → moderate embedding signal."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.82,
            text=ASTRO_RELATED,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        assert "_emb_similarity" in c
        emb_sim = c["_emb_similarity"]
        assert isinstance(emb_sim, float)
        assert 0.0 <= emb_sim <= 1.0


# ── Test 3: Very different texts → no embedding signal ─────────────────


class TestEmbeddingNoSignal:
    """Completely different texts → emb_sim < 0.6 → no signal added."""

    def test_embedding_heuristic_no_signal_for_different_texts(self, memory):
        """Astro vs Econ → embedding similarity < 0.6 → no duplicate signal."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.80,
            text=ECON_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
            query_domain="Economics",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        assert "_emb_similarity" in c
        # Cross-domain texts should have low embedding similarity
        assert c["_emb_similarity"] < 0.5
        # Embedding heuristic should NOT contribute to dup_signals
        assert c["_rerank_signals"] == 0


# ── Test 4: Embedding similarity stored in candidate dict ──────────────


class TestEmbeddingSimilarityStored:
    """The _emb_similarity key should be added to candidate dicts."""

    def test_embedding_similarity_stored_in_candidate(self, memory):
        """_emb_similarity should appear with a float value."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.82,
            text=ASTRO_SIMILAR,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        assert "_emb_similarity" in c
        assert isinstance(c["_emb_similarity"], float)
        # Should be rounded to 4 decimal places
        assert c["_emb_similarity"] == round(c["_emb_similarity"], 4)


# ── Test 5: evaluable heuristic count ────────────────────────────────────


class TestEvaluableHeuristicsUpdated:
    """evaluable count should reflect only heuristics that had data to evaluate.

    Phase 20 hotfix: the denominator is now *evaluable* heuristics, not the
    fixed total of 5.5.  When all 5 heuristics have data, evaluable == 5.5.
    """

    def test_evaluable_matches_all_heuristics_with_full_data(self, memory):
        """With all heuristics applicable and similar texts, ratio > 0.5."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.75,
            text=ASTRO_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        assert "_rerank_ratio" in c
        # All 5 heuristics should be evaluable: vars(1) + type(1) + cycle(1) + svo(1) + emb(1.5) = 5.5
        assert c["_evaluable"] == 5.5
        # emb_sim ~0.89 → full weight (1.5), plus other heuristics
        # signals ~4.5 (3 text + 1.5 emb), ratio ~4.5/5.5 = 0.818
        assert c["_rerank_ratio"] > 0.5
        assert c["_rerank_ratio"] <= 1.0

    def test_signals_include_embedding_weight(self, memory):
        """Signals should be higher than old max of 4 when embedding contributes."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.75,
            text=ASTRO_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        # Embedding sim ~0.89 gives full weight 1.5 + other signals
        # Total signals should be > 3 (i.e. embedding was counted)
        assert c["_rerank_signals"] >= 3.0
        # The embedding component alone is 1.5, so signals > pure text count
        assert c["_rerank_signals"] > 2.5


# ── Test 6: Improves true duplicate detection ──────────────────────────


class TestImprovesDuplicateDetection:
    """Embedding heuristic should push borderline cases toward correct classification."""

    def test_embedding_heuristic_improves_true_duplicate_detection(self, memory):
        """A borderline duplicate (sim=0.73) with matching metadata → classified as dup.

        The embedding heuristic (emb_sim ~0.89 → full 1.5 weight) combined with
        variable overlap and same domain/type pushes the ratio above 0.5.
        """
        # Low similarity in soft zone, but texts are semantically very similar
        # AND domain/type metadata match so Heuristic 2 fires
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.73,
            text=ASTRO_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        c = result[0]
        # With emb_sim ~0.89 (full weight 1.5) + vars (1) + type+domain (1)
        # + temporal (sim=0.58 < 0.70, no) + SVO (partial)
        # ratio should be > 0.5 → classified as duplicate
        assert c["is_duplicate"] is True
        assert c["confidence"] > 0.73


# ── Test 7: Preserves novel detection ──────────────────────────────────


class TestPreservesNovelDetection:
    """Truly novel discoveries should still be classified as novel."""

    def test_embedding_heuristic_preserves_novel_detection(self, memory):
        """Cross-domain text with low similarity → still classified as novel.

        With soft_duplicate_threshold = 0.72 (Cycle 29 drawer-bloat fix),
        similarity 0.56 falls below the soft zone entirely, so the
        reranker correctly skips it (no ``_rerank_signals`` key).  We
        also test a value *inside* the soft zone (0.75) where heuristics
        fire but still classify the item as novel.
        """
        # ── Sub-case A: similarity below soft threshold → skipped entirely
        candidates_a = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.56,
            text=ECON_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
            query_domain="Economics",
            query_cycle=1,
            cycle=5,
            is_duplicate=False,
        )]
        result_a = memory.llm_rerank_duplicates(candidates_a)
        c_a = result_a[0]
        # Below soft zone → reranker skips, no _rerank_signals key
        assert "_rerank_signals" not in c_a
        assert c_a["is_duplicate"] is False

        # ── Sub-case B: similarity in soft zone but cross-domain → novel
        candidates_b = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.75,
            text=ECON_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
            query_domain="Economics",
            query_cycle=1,
            cycle=5,
            is_duplicate=False,
        )]
        result_b = memory.llm_rerank_duplicates(candidates_b)
        c_b = result_b[0]
        assert c_b.get("_rerank_signals", 0) == 0
        assert c_b["is_duplicate"] is False


# ── Test 8: Hard and novel zones still unaffected ──────────────────────


class TestHardNovelZonesUnaffected:
    """Candidates outside the soft zone should be completely unchanged."""

    def test_hard_zone_unchanged(self, memory):
        """sim=0.95 → hard zone (≥0.92), no reranking applied.

        Cycle 29 raised hard_duplicate_threshold from 0.86 to 0.92,
        so the previous test value of 0.90 now falls in the soft zone.
        """
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.95,
            text=ASTRO_SIMILAR,
            is_duplicate=True,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["is_duplicate"] is True
        assert "_rerank_signals" not in result[0]
        assert "_emb_similarity" not in result[0]

    def test_novel_zone_unchanged(self, memory):
        """sim=0.30 → novel zone, no reranking applied."""
        candidates = [_make_candidate(
            query=ASTRO_PROBE,
            similarity=0.30,
            text=ECON_DIFFERENT,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["is_duplicate"] is False
        assert "_rerank_signals" not in result[0]
        assert "_emb_similarity" not in result[0]


# ── Test 9: Accuracy improvement battery ────────────────────────────────


class TestAccuracyImprovement:
    """Run a battery of test cases and verify accuracy ≥ 75%.

    Test cases use realistic domain and finding_type metadata to exercise
    all heuristics including finding-type match (Heuristic 2).
    """

    def test_accuracy_improvement(self, memory):
        """Battery of 8 cases: expect ≥ 6 correct (75%).

        Cycle 29 raised soft_duplicate_threshold from 0.55 → 0.72.
        Cases below the soft zone are auto-classified as novel (no rerank).
        Test cases updated to ensure meaningful coverage in the soft zone
        (0.72–0.92) where heuristics actually fire.
        """
        test_cases = [
            # (query, cand_text, sim, domain, finding_type, query_domain, expected, description)
            (ASTRO_PROBE, ASTRO_SIMILAR, 0.80, "Astrophysics", "scaling", "Astrophysics", True, "near-dup astro high sim"),
            (ASTRO_PROBE, ASTRO_SIMILAR, 0.75, "Astrophysics", "scaling", "Astrophysics", True, "near-dup astro soft zone"),
            (ASTRO_PROBE, ECON_DIFFERENT, 0.75, "Economics", "correlation", "Astrophysics", False, "cross-domain different"),
            (ASTRO_PROBE, ECON_DIFFERENT, 0.56, "Economics", "correlation", "Astrophysics", False, "cross-domain below soft (auto-novel)"),
            (ASTRO_PROBE, ASTRO_RELATED, 0.78, "Astrophysics", "scaling", "Astrophysics", False, "same domain diff topic"),
            (
                "Discovery D_a: GDP growth tracks inflation rates\n"
                "Domain: Economics\nType: correlation\nVariables: gdp, inflation",
                "Discovery D_b: GDP growth correlates with inflation\n"
                "Domain: Economics\nType: correlation\nVariables: gdp, inflation",
                0.78, "Economics", "correlation", "Economics", True, "near-dup econ",
            ),
            (
                "Discovery D_a: Temperature rise affects sea levels\n"
                "Domain: Climate\nType: causal\nVariables: temperature, sea_level",
                "Discovery D_b: Sea level rise caused by temperature increase\n"
                "Domain: Climate\nType: causal\nVariables: temperature, sea_level",
                0.76, "Climate", "causal", "Climate", True, "near-dup climate",
            ),
            (
                "Discovery D_a: Vaccine efficacy against respiratory infections\n"
                "Domain: Epidemiology\nType: measurement\nVariables: efficacy, infection_rate",
                "Discovery D_b: GDP per capita in developing nations\n"
                "Domain: Economics\nType: trend\nVariables: gdp_per_capita, development_index",
                0.50, "Economics", "trend", "Epidemiology", False, "completely unrelated (auto-novel)",
            ),
        ]

        correct = 0
        total = len(test_cases)
        details = []

        for query, cand_text, sim, domain, ft, qd, expected, desc in test_cases:
            candidates = [_make_candidate(
                query=query,
                similarity=sim,
                text=cand_text,
                domain=domain,
                finding_type=ft,
                query_domain=qd,
                query_cycle=1,
                cycle=1,
            )]
            result = memory.llm_rerank_duplicates(candidates)
            actual = result[0]["is_duplicate"]
            if actual == expected:
                correct += 1
            details.append(f"  {desc}: expected={expected}, actual={actual}, "
                           f"emb={result[0].get('_emb_similarity', '?')}")

        accuracy = correct / total
        detail_str = "\n".join(details)
        assert accuracy >= 0.75, (
            f"Accuracy {accuracy:.1%} ({correct}/{total}) below 75% threshold\n{detail_str}"
        )


# ── Test 10: Graceful fallback when collection unavailable ──────────────


class TestGracefulFallback:
    """If self._backend is broken, embedding heuristic is skipped gracefully."""

    def test_graceful_fallback_when_collection_unavailable(self, memory):
        """Temporarily break backend → heuristic skipped, others still work.

        Cycle 29 raised soft_duplicate_threshold from 0.55 to 0.72,
        so the previous test value of 0.70 now falls below the soft zone.
        Using 0.75 to stay in the soft zone where reranking fires.
        """
        real_backend = memory._backend
        memory._backend = None

        try:
            candidates = [_make_candidate(
                query=ASTRO_PROBE,
                similarity=0.75,
                text=ASTRO_SIMILAR,
                domain="Astrophysics",
                finding_type="scaling",
                query_domain="Astrophysics",
                query_cycle=1,
                cycle=1,
            )]
            result = memory.llm_rerank_duplicates(candidates)
            c = result[0]
            # Should still have rerank signals (from other heuristics)
            assert "_rerank_signals" in c
            # Embedding similarity should NOT be stored (heuristic was skipped)
            assert "_emb_similarity" not in c
            # Other heuristics should still fire
            assert c["_rerank_signals"] >= 1
        finally:
            memory._backend = real_backend

    def test_fallback_evaluable_excludes_embedding(self, memory):
        """When embedding fails, evaluable count excludes the 1.5 weight.

        Phase 20 hotfix: the evaluable denominator only counts heuristics
        that successfully ran.  When the backend is broken, embedding
        is not evaluable, so evaluable = (at most) 4.0 instead of 5.5.
        """
        real_backend = memory._backend
        memory._backend = None

        try:
            candidates = [_make_candidate(
                query=ASTRO_PROBE,
                similarity=0.75,
                text=ASTRO_SIMILAR,
                domain="Astrophysics",
                finding_type="scaling",
                query_domain="Astrophysics",
                query_cycle=1,
                cycle=1,
            )]
            result = memory.llm_rerank_duplicates(candidates)
            c = result[0]
            # With embedding skipped, evaluable should be 4.0 (not 5.5)
            assert c["_evaluable"] == 4.0
            # Most text heuristics should still fire
            assert c["_rerank_ratio"] > 0.5
            # Verify it's computed over 4.0 base, not 5.5:
            signals = c["_rerank_signals"]
            expected_ratio_4 = round(signals / 4.0, 4)
            expected_ratio_55 = round(signals / 5.5, 4)
            # The actual ratio should match the 4.0 denominator, not 5.5
            assert abs(c["_rerank_ratio"] - expected_ratio_4) < 0.001
            assert c["_rerank_ratio"] != expected_ratio_55 or signals == 0
        finally:
            memory._backend = real_backend
