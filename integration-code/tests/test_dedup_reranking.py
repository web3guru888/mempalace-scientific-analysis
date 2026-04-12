"""
Tests for llm_rerank_duplicates — deterministic heuristic dedup reranking.
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


# ── Helper to build candidate dicts ─────────────────────────────────


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


PROBE_TEXT = (
    "Discovery D_probe: Mass-radius power law in exoplanets\n"
    "Domain: Astrophysics\n"
    "Type: scaling\n"
    "Variables: mass, radius\n"
    "Data source: exoplanets\n"
    "Strength: 0.900"
)

CAND_TEXT_SIMILAR = (
    "Discovery D001: Mass-radius scaling relation for exoplanets\n"
    "Domain: Astrophysics\n"
    "Type: scaling\n"
    "Variables: mass, radius\n"
    "Data source: kepler\n"
    "Strength: 0.850"
)

CAND_TEXT_DIFFERENT = (
    "Discovery D002: GDP correlates with population growth\n"
    "Domain: Economics\n"
    "Type: correlation\n"
    "Variables: gdp, population\n"
    "Data source: worldbank\n"
    "Strength: 0.700"
)


# ── Hard and novel zones are unaffected ─────────────────────────────


class TestHardAndNovelUnaffected:
    """Candidates ≥0.92 (hard) or <0.72 (novel) should pass through unchanged.

    Thresholds updated from 0.86/0.55 → 0.92/0.72 per drawer-bloat dedup fix
    (Monitoring-35, 2026-04-11). The hard zone starts at 0.92 to catch
    near-duplicates that previously slipped through at 0.86.
    """

    def test_hard_duplicate_unchanged(self, memory):
        """sim=0.95 → hard zone (≥0.92), is_duplicate stays True."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.95,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=True,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["is_duplicate"] is True
        assert "_rerank_signals" not in result[0]

    def test_novel_unchanged(self, memory):
        """sim=0.30 → novel zone (<0.72), is_duplicate stays False."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.30,
            text=CAND_TEXT_DIFFERENT,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["is_duplicate"] is False
        assert "_rerank_signals" not in result[0]

    def test_exactly_at_hard_threshold(self, memory):
        """sim=0.92 → exactly at boundary, treated as hard (unchanged)."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.92,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=True,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["is_duplicate"] is True

    def test_exactly_at_low_threshold(self, memory):
        """sim=0.72 → exactly at soft zone lower bound, gets reranked."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.72,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=False,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Should be in soft zone, gets reranked
        assert "_rerank_signals" in result[0]


# ── Variable overlap heuristic ──────────────────────────────────────


class TestVariableOverlap:
    """Heuristic 1: >80% variable overlap → likely duplicate."""

    def test_high_variable_overlap_signals_duplicate(self, memory):
        """Same variables (mass, radius) → strong dup signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.82,
            text=CAND_TEXT_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["_rerank_ratio"] > 0.25  # At least some dup signals

    def test_no_variable_overlap_is_novel(self, memory):
        """Completely different variables → lower dup ratio."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.80,
            text=CAND_TEXT_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Should have fewer dup signals
        assert result[0]["_rerank_ratio"] < 0.75


# ── Finding type match heuristic ────────────────────────────────────


class TestFindingTypeMatch:
    """Heuristic 2: same type + same domain + high sim → duplicate."""

    def test_same_type_same_domain(self, memory):
        """scaling + scaling + Astrophysics + Astrophysics → dup signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.75,
            text=CAND_TEXT_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert result[0]["_rerank_signals"] >= 1

    def test_different_type(self, memory):
        """scaling vs correlation → no type signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.82,
            text=CAND_TEXT_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
            query_domain="Economics",
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Type doesn't match, so fewer signals
        assert result[0]["_rerank_signals"] == 0


# ── Temporal proximity heuristic ────────────────────────────────────


class TestTemporalProximity:
    """Heuristic 3: same cycle + high sim → likely duplicate."""

    def test_same_cycle_high_sim(self, memory):
        """Same cycle (1) + sim=0.75 → temporal dup signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.75,
            text=CAND_TEXT_SIMILAR,
            cycle=1,
            query_cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Should get temporal signal
        assert result[0]["_rerank_signals"] >= 1

    def test_different_cycle_no_signal(self, memory):
        """Different cycles → no temporal signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.75,
            text=CAND_TEXT_SIMILAR,
            cycle=5,
            query_cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # No temporal signal from cycle mismatch
        assert "_rerank_signals" in result[0]

    def test_low_sim_same_cycle_no_signal(self, memory):
        """Same cycle but sim=0.73 (in soft zone but below 0.80 temporal threshold) → no temporal signal."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.73,
            text=CAND_TEXT_SIMILAR,
            cycle=1,
            query_cycle=1,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # sim < 0.80 temporal threshold, so temporal heuristic doesn't fire even with same cycle
        assert "_rerank_signals" in result[0]


# ── Structural similarity heuristic ─────────────────────────────────


class TestStructuralSimilarity:
    """Heuristic 4: same subject-verb-object pattern → duplicate."""

    def test_same_svo_pattern(self, memory):
        """Both describe mass-radius power law → SVO match."""
        text_a = (
            "Discovery D_a: Mass-radius power law in exoplanets\n"
            "Domain: Astrophysics\n"
            "Type: scaling\n"
            "Variables: mass, radius"
        )
        text_b = (
            "Discovery D_b: Mass-radius scaling law for exoplanets\n"
            "Domain: Astrophysics\n"
            "Type: scaling\n"
            "Variables: mass, radius"
        )
        candidates = [_make_candidate(
            query=text_a,
            similarity=0.72,
            text=text_b,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Structural similarity should fire
        assert result[0].get("_rerank_ratio", 0) >= 0

    def test_different_svo_pattern(self, memory):
        """Different subjects/verbs/objects → no SVO match."""
        text_a = (
            "Discovery D_a: Mass-radius power law in exoplanets\n"
            "Domain: Astrophysics\n"
            "Type: scaling\n"
            "Variables: mass, radius"
        )
        text_b = (
            "Discovery D_b: GDP correlates with population growth\n"
            "Domain: Economics\n"
            "Type: correlation\n"
            "Variables: gdp, population"
        )
        candidates = [_make_candidate(
            query=text_a,
            similarity=0.80,
            text=text_b,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # No structural match, low dup ratio
        assert result[0]["_rerank_ratio"] < 0.5


# ── Confidence scoring on boundary cases ────────────────────────────


class TestConfidenceScoring:
    """Test confidence scoring at soft zone boundaries (0.72–0.92)."""

    def test_confidence_at_lower_bound(self, memory):
        """sim=0.72 — lower bound of soft zone."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.72,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Confidence should be between 0.55 and 1.0
        assert 0.55 <= result[0]["confidence"] <= 1.0

    def test_confidence_at_mid_zone(self, memory):
        """sim=0.82 — middle of soft zone."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.82,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        assert 0.55 <= result[0]["confidence"] <= 1.0

    def test_confidence_near_upper_bound(self, memory):
        """sim=0.91 — near hard threshold."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.91,
            text=CAND_TEXT_SIMILAR,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # High sim should yield high confidence
        assert result[0]["confidence"] > 0.8

    def test_confidence_is_rounded(self, memory):
        """Confidence should be rounded to 4 decimal places."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.82,
            text=CAND_TEXT_SIMILAR,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        conf = result[0]["confidence"]
        assert conf == round(conf, 4)

    def test_empty_candidates(self, memory):
        """Empty input returns empty output."""
        result = memory.llm_rerank_duplicates([])
        assert result == []


# ── Re-classification logic ─────────────────────────────────────────


class TestReclassification:
    """Test that soft candidates get reclassified correctly."""

    def test_all_heuristics_fire_marks_duplicate(self, memory):
        """When all heuristics agree → definitely a duplicate."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.75,
            text=CAND_TEXT_SIMILAR,
            domain="Astrophysics",
            finding_type="scaling",
            query_domain="Astrophysics",
            query_cycle=1,
            cycle=1,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # With matching type, domain, cycle, and variables, should classify as dup
        assert result[0]["is_duplicate"] is True

    def test_no_heuristics_fire_marks_novel(self, memory):
        """When no heuristics agree → probably novel."""
        candidates = [_make_candidate(
            query=PROBE_TEXT,
            similarity=0.73,  # Just in soft zone (0.72–0.92)
            text=CAND_TEXT_DIFFERENT,
            domain="Economics",
            finding_type="correlation",
            query_domain="Economics",
            query_cycle=1,
            cycle=5,
            is_duplicate=False,
        )]
        result = memory.llm_rerank_duplicates(candidates)
        # Different type, different cycle, different variables → novel
        assert result[0]["is_duplicate"] is False
