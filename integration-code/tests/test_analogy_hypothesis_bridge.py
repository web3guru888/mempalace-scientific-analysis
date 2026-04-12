"""
Tests for AnalogyHypothesisBridge — the analogy-to-hypothesis pipeline.

Validates that cross-domain structural analogies are correctly converted
into testable hypotheses compatible with the HypothesisGenerator format.
"""

import pytest
from dataclasses import dataclass, field
from typing import List, Dict
import time

import sys
import os

# Ensure the source package is on the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mempalace_agi.analogy_hypothesis_bridge import (
    AnalogyHypothesisBridge,
    inject_analogy_hypotheses,
    _domain_to_source,
)


# ── Mock Analogy dataclass ──────────────────────────────────────────────────


@dataclass
class MockAnalogy:
    """Mimics the ASTRA-dev Analogy dataclass."""
    id: str
    domain_a: str
    domain_b: str
    hypothesis_id_a: str
    hypothesis_id_b: str
    mathematical_form: str
    structural_similarity: float
    unification_proposal: str
    novel: bool
    detected_at: float = field(default_factory=time.time)


class MockAnalogyEngine:
    """Mimics AnalogyEngine with controllable analogy lists."""

    def __init__(self, analogies: List[MockAnalogy] = None):
        self._analogies = analogies or []

    def get_novel_analogies(self) -> List[MockAnalogy]:
        return [a for a in self._analogies if a.novel]

    def get_all_analogies(self) -> List[MockAnalogy]:
        return list(self._analogies)


class MockTheoryEngine:
    """Mimics a TheoryEngine with an analogy_engine attribute."""

    def __init__(self, analogy_engine: MockAnalogyEngine):
        self.analogy_engine = analogy_engine


# ── Fixtures ────────────────────────────────────────────────────────────────


def _make_analogy(
    domain_a="Astrophysics",
    domain_b="Economics",
    form="power_law",
    similarity=0.85,
    novel=True,
    id_suffix="01",
) -> MockAnalogy:
    """Helper to create a mock analogy with sensible defaults."""
    return MockAnalogy(
        id=f"AN-TEST{id_suffix}",
        domain_a=domain_a,
        domain_b=domain_b,
        hypothesis_id_a=f"H-A{id_suffix}",
        hypothesis_id_b=f"H-B{id_suffix}",
        mathematical_form=form,
        structural_similarity=similarity,
        unification_proposal=(
            f"Both {domain_a} and {domain_b} exhibit {form} structure. "
            f"A unifying framework is proposed."
        ),
        novel=novel,
    )


@pytest.fixture
def single_analogy_engine():
    """Engine with one high-quality novel analogy."""
    return MockAnalogyEngine([_make_analogy()])


@pytest.fixture
def multi_analogy_engine():
    """Engine with diverse analogies at different quality levels."""
    return MockAnalogyEngine([
        _make_analogy(
            domain_a="Astrophysics", domain_b="Economics",
            form="power_law", similarity=0.92, id_suffix="01",
        ),
        _make_analogy(
            domain_a="Climate", domain_b="Epidemiology",
            form="exponential", similarity=0.85, id_suffix="02",
        ),
        _make_analogy(
            domain_a="Astrophysics", domain_b="Climate",
            form="linear", similarity=0.75, id_suffix="03",  # Below default threshold
        ),
        _make_analogy(
            domain_a="Economics", domain_b="Epidemiology",
            form="bimodal", similarity=0.60, id_suffix="04",  # Way below threshold
        ),
        _make_analogy(
            domain_a="Astrophysics", domain_b="Cryptography",
            form="periodic", similarity=0.88, novel=False, id_suffix="05",
        ),
    ])


@pytest.fixture
def empty_engine():
    """Engine with no analogies."""
    return MockAnalogyEngine([])


# ── Tests: Bridge Creation ──────────────────────────────────────────────────


class TestBridgeCreation:
    """Test AnalogyHypothesisBridge initialization."""

    def test_create_with_defaults(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        assert bridge.analogy_engine is single_analogy_engine
        assert bridge.similarity_threshold == 0.70
        assert bridge.confidence_multiplier == 0.4
        assert bridge.include_non_novel is False

    def test_create_with_custom_params(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(
            single_analogy_engine,
            similarity_threshold=0.90,
            confidence_multiplier=0.5,
            include_non_novel=True,
        )
        assert bridge.similarity_threshold == 0.90
        assert bridge.confidence_multiplier == 0.5
        assert bridge.include_non_novel is True


# ── Tests: Empty Input ──────────────────────────────────────────────────────


class TestEmptyInput:
    """Test behavior when no analogies are available."""

    def test_empty_engine_returns_empty(self, empty_engine):
        bridge = AnalogyHypothesisBridge(empty_engine)
        result = bridge.generate_from_analogies()
        assert result == []

    def test_all_below_threshold_returns_empty(self, multi_analogy_engine):
        """Threshold higher than any analogy → empty output."""
        bridge = AnalogyHypothesisBridge(
            multi_analogy_engine, similarity_threshold=0.99
        )
        result = bridge.generate_from_analogies()
        assert result == []

    def test_only_non_novel_with_default_filter(self):
        """Non-novel analogies are excluded by default."""
        engine = MockAnalogyEngine([
            _make_analogy(similarity=0.95, novel=False, id_suffix="NV"),
        ])
        bridge = AnalogyHypothesisBridge(engine)
        result = bridge.generate_from_analogies()
        assert result == []


# ── Tests: Similarity Filtering ─────────────────────────────────────────────


class TestSimilarityFiltering:
    """Test that only high-quality analogies pass the threshold."""

    def test_default_threshold_filters_correctly(self, multi_analogy_engine):
        """Default threshold 0.70 should keep sim >= 0.70 (novel only)."""
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=10)
        # sim=0.92 ✓, sim=0.85 ✓, sim=0.75 ✓, sim=0.60 ✗, sim=0.88 but non-novel ✗
        assert len(result) == 3

    def test_lower_threshold_admits_more(self, multi_analogy_engine):
        """Lowering threshold to 0.55 admits the 0.60 analogy too."""
        bridge = AnalogyHypothesisBridge(
            multi_analogy_engine, similarity_threshold=0.55
        )
        result = bridge.generate_from_analogies(max_new=10)
        assert len(result) == 4

    def test_include_non_novel_expands_pool(self, multi_analogy_engine):
        """include_non_novel=True adds the 0.88 non-novel analogy."""
        bridge = AnalogyHypothesisBridge(
            multi_analogy_engine, include_non_novel=True
        )
        result = bridge.generate_from_analogies(max_new=10)
        # sim=0.92 ✓, sim=0.88 ✓ (non-novel but included), sim=0.85 ✓,
        # sim=0.75 ✓ (above 0.70), sim=0.60 ✗
        assert len(result) == 4

    def test_sorted_by_similarity_descending(self, multi_analogy_engine):
        """Highest similarity analogies should be selected first."""
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=2)
        # Should get 0.92 first, then 0.85
        assert result[0]["confidence"] > result[1]["confidence"]


# ── Tests: Deduplication ────────────────────────────────────────────────────


class TestDeduplication:
    """Test deduplication against existing hypothesis names."""

    def test_dedup_against_existing_names(self, single_analogy_engine):
        """Should not produce a hypothesis with a name already in pool."""
        bridge = AnalogyHypothesisBridge(single_analogy_engine)

        # First call: should produce one hypothesis
        result1 = bridge.generate_from_analogies(max_new=3)
        assert len(result1) == 1
        name = result1[0]["name"]

        # Second call with existing_names: should try alternate or skip
        result2 = bridge.generate_from_analogies(
            max_new=3, existing_names={name}
        )
        # Should produce the reverse-direction hypothesis or nothing
        if result2:
            assert result2[0]["name"] != name

    def test_dedup_both_directions_exhausted(self):
        """When both A→B and B→A names exist, skip entirely."""
        analogy = _make_analogy(
            domain_a="Astrophysics", domain_b="Economics",
            form="power_law", similarity=0.90,
        )
        engine = MockAnalogyEngine([analogy])
        bridge = AnalogyHypothesisBridge(engine)

        # Block both directions
        existing = {
            "Analogy Transfer: Astrophysics power_law → Economics",
            "Analogy Transfer: Economics power_law → Astrophysics",
        }
        result = bridge.generate_from_analogies(max_new=3, existing_names=existing)
        assert result == []


# ── Tests: Output Format ────────────────────────────────────────────────────


class TestOutputFormat:
    """Test that output matches HypothesisGenerator format."""

    REQUIRED_KEYS = {
        "name", "domain", "description", "confidence",
        "finding_type", "data_source", "variables",
        "source_discovery_id", "source_analogy_id",
    }

    def test_all_required_keys_present(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        assert len(result) == 1
        hyp = result[0]
        assert self.REQUIRED_KEYS.issubset(hyp.keys()), (
            f"Missing keys: {self.REQUIRED_KEYS - hyp.keys()}"
        )

    def test_finding_type_is_analogy_transfer(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        assert result[0]["finding_type"] == "analogy_transfer"

    def test_confidence_is_conservative(self, single_analogy_engine):
        """Confidence = similarity × 0.4 (conservative)."""
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        hyp = result[0]
        expected = round(0.85 * 0.4, 4)
        assert hyp["confidence"] == expected

    def test_confidence_with_custom_multiplier(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(
            single_analogy_engine, confidence_multiplier=0.6
        )
        result = bridge.generate_from_analogies()
        expected = round(0.85 * 0.6, 4)
        assert result[0]["confidence"] == expected

    def test_domain_is_target_domain(self, single_analogy_engine):
        """Hypothesis domain should be domain_b (the transfer target)."""
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        assert result[0]["domain"] == "Economics"

    def test_source_analogy_id_present(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        assert result[0]["source_analogy_id"] == "AN-TEST01"

    def test_source_discovery_id_is_hypothesis_a(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        assert result[0]["source_discovery_id"] == "H-A01"

    def test_variables_inferred_from_form(self):
        """Different mathematical forms should produce different variables."""
        forms_expected = {
            "power_law": ["exponent", "amplitude", "scale"],
            "exponential": ["rate", "amplitude", "timescale"],
            "linear": ["slope", "intercept"],
            "bimodal": ["peak1", "peak2", "valley"],
            "causal_chain": ["driver", "response", "lag"],
            "periodic": ["period", "amplitude", "phase"],
            "lognormal": ["mu", "sigma"],
            "weird_unknown": ["value"],  # Fallback
        }
        for form, expected_vars in forms_expected.items():
            analogy = _make_analogy(form=form, similarity=0.90, id_suffix=form[:3])
            engine = MockAnalogyEngine([analogy])
            bridge = AnalogyHypothesisBridge(engine)
            result = bridge.generate_from_analogies()
            assert result[0]["variables"] == expected_vars, (
                f"Form '{form}': expected {expected_vars}, got {result[0]['variables']}"
            )

    def test_description_includes_key_info(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        desc = result[0]["description"]
        assert "0.85" in desc  # Similarity score
        assert "power_law" in desc  # Mathematical form
        assert "Astrophysics" in desc  # Source domain
        assert "Economics" in desc  # Target domain
        assert "analogy" in desc.lower()  # It's about an analogy

    def test_name_format(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies()
        name = result[0]["name"]
        assert name == "Analogy Transfer: Astrophysics power_law → Economics"


# ── Tests: Domain Assignment ────────────────────────────────────────────────


class TestDomainAssignment:
    """Test correct domain and data_source assignment for multiple analogies."""

    def test_multiple_analogies_correct_domains(self, multi_analogy_engine):
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=5)
        # Sorted by similarity: 0.92 (Astro→Econ), 0.85 (Climate→Epi)
        assert result[0]["domain"] == "Economics"
        assert result[1]["domain"] == "Epidemiology"

    def test_data_source_matches_target_domain(self, multi_analogy_engine):
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=5)
        assert result[0]["data_source"] == "worldbank"  # Economics
        assert result[1]["data_source"] == "who"  # Epidemiology

    def test_domain_to_source_mapping(self):
        """Test the domain-to-source helper directly."""
        assert _domain_to_source("Astrophysics") == "sdss"
        assert _domain_to_source("Economics") == "worldbank"
        assert _domain_to_source("Climate") == "noaa"
        assert _domain_to_source("Epidemiology") == "who"
        assert _domain_to_source("Cross-Domain") == "multi"
        assert _domain_to_source("Cryptography") == "eccp131"
        assert _domain_to_source("UnknownDomain") == "multi"


# ── Tests: max_new Limit ────────────────────────────────────────────────────


class TestMaxNewLimit:
    """Test that max_new properly limits output."""

    def test_max_new_limits_output(self, multi_analogy_engine):
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=1)
        assert len(result) == 1

    def test_max_new_zero_returns_empty(self, multi_analogy_engine):
        bridge = AnalogyHypothesisBridge(multi_analogy_engine)
        result = bridge.generate_from_analogies(max_new=0)
        assert result == []

    def test_max_new_exceeds_available(self, single_analogy_engine):
        bridge = AnalogyHypothesisBridge(single_analogy_engine)
        result = bridge.generate_from_analogies(max_new=100)
        assert len(result) == 1  # Only one analogy available


# ── Tests: inject_analogy_hypotheses convenience function ───────────────────


class TestInjectFunction:
    """Test the inject_analogy_hypotheses convenience function."""

    def test_with_theory_engine(self):
        """TheoryEngine with analogy_engine attribute."""
        ae = MockAnalogyEngine([_make_analogy(similarity=0.90)])
        te = MockTheoryEngine(ae)
        result = inject_analogy_hypotheses(
            engine=None, theory_engine=te, max_new=2
        )
        assert len(result) == 1
        assert result[0]["finding_type"] == "analogy_transfer"

    def test_with_analogy_engine_directly(self):
        """Pass AnalogyEngine directly as theory_engine."""
        ae = MockAnalogyEngine([_make_analogy(similarity=0.90)])
        result = inject_analogy_hypotheses(
            engine=None, theory_engine=ae, max_new=2
        )
        assert len(result) == 1

    def test_with_incompatible_object(self):
        """Object without analogy methods returns empty."""
        result = inject_analogy_hypotheses(
            engine=None, theory_engine=object(), max_new=2
        )
        assert result == []

    def test_existing_names_passed_through(self):
        """existing_names should filter output."""
        ae = MockAnalogyEngine([_make_analogy(similarity=0.90)])
        te = MockTheoryEngine(ae)
        name = "Analogy Transfer: Astrophysics power_law → Economics"
        alt = "Analogy Transfer: Economics power_law → Astrophysics"
        result = inject_analogy_hypotheses(
            engine=None, theory_engine=te,
            existing_names={name, alt},
        )
        assert result == []

    def test_custom_threshold(self):
        """Threshold can be overridden."""
        ae = MockAnalogyEngine([_make_analogy(similarity=0.82)])
        te = MockTheoryEngine(ae)
        # Default threshold 0.80 → should pass
        result1 = inject_analogy_hypotheses(
            engine=None, theory_engine=te, similarity_threshold=0.80
        )
        assert len(result1) == 1
        # Higher threshold → should not pass
        result2 = inject_analogy_hypotheses(
            engine=None, theory_engine=te, similarity_threshold=0.90
        )
        assert result2 == []


# ── Tests: Integration with real Analogy dataclass ──────────────────────────


class TestRealAnalogyCompat:
    """Test compatibility with the actual ASTRA-dev Analogy dataclass."""

    def test_with_real_analogy_dataclass(self):
        """Import and use the real Analogy class from ASTRA-dev."""
        try:
            # Add ASTRA-dev to path
            astra_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "ASTRA-dev"
            )
            if os.path.isdir(astra_path):
                sys.path.insert(0, astra_path)
            from astra_live_backend.analogy_engine import Analogy

            real_analogy = Analogy(
                id="AN-REAL0001",
                domain_a="Astrophysics",
                domain_b="Climate",
                hypothesis_id_a="H-REAL-A",
                hypothesis_id_b="H-REAL-B",
                mathematical_form="power_law",
                structural_similarity=0.88,
                unification_proposal="Both systems show scale-free structure.",
                novel=True,
            )

            class RealEngine:
                def get_novel_analogies(self):
                    return [real_analogy]
                def get_all_analogies(self):
                    return [real_analogy]

            bridge = AnalogyHypothesisBridge(RealEngine())
            result = bridge.generate_from_analogies()
            assert len(result) == 1
            assert result[0]["domain"] == "Climate"
            assert result[0]["source_analogy_id"] == "AN-REAL0001"
            assert result[0]["finding_type"] == "analogy_transfer"
        except ImportError:
            pytest.skip("ASTRA-dev not available on path")


# ── Tests: Edge Cases ───────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases and boundary conditions."""

    def test_identical_domains_in_analogy(self):
        """Analogy with same domain_a and domain_b (shouldn't happen but handle)."""
        analogy = _make_analogy(
            domain_a="Astrophysics", domain_b="Astrophysics",
            similarity=0.95, id_suffix="SAME",
        )
        engine = MockAnalogyEngine([analogy])
        bridge = AnalogyHypothesisBridge(engine)
        result = bridge.generate_from_analogies()
        # Should still produce output — the bridge doesn't enforce cross-domain
        assert len(result) == 1
        assert result[0]["domain"] == "Astrophysics"

    def test_similarity_exactly_at_threshold(self):
        """Analogy with similarity exactly at threshold should be included."""
        analogy = _make_analogy(similarity=0.80, id_suffix="EDGE")
        engine = MockAnalogyEngine([analogy])
        bridge = AnalogyHypothesisBridge(engine, similarity_threshold=0.80)
        result = bridge.generate_from_analogies()
        assert len(result) == 1

    def test_similarity_just_below_threshold(self):
        """Analogy with similarity just below threshold excluded."""
        analogy = _make_analogy(similarity=0.799, id_suffix="BELOW")
        engine = MockAnalogyEngine([analogy])
        bridge = AnalogyHypothesisBridge(engine, similarity_threshold=0.80)
        result = bridge.generate_from_analogies()
        assert result == []

    def test_unknown_mathematical_form(self):
        """Unknown form → generic ['value'] variables."""
        analogy = _make_analogy(
            form="quantum_gravity_foam", similarity=0.90, id_suffix="UNK"
        )
        engine = MockAnalogyEngine([analogy])
        bridge = AnalogyHypothesisBridge(engine)
        result = bridge.generate_from_analogies()
        assert result[0]["variables"] == ["value"]

    def test_none_existing_names(self):
        """Passing None for existing_names should work."""
        engine = MockAnalogyEngine([_make_analogy(similarity=0.90)])
        bridge = AnalogyHypothesisBridge(engine)
        result = bridge.generate_from_analogies(existing_names=None)
        assert len(result) == 1

    def test_many_analogies_performance(self):
        """100 analogies should complete quickly and respect max_new."""
        # Use diverse domain+form combos to avoid name collisions
        domains = [
            "Astrophysics", "Economics", "Climate", "Epidemiology",
            "Cryptography", "Cross-Domain", "Cosmology", "Biology",
            "Physics", "Chemistry",
        ]
        forms = [
            "power_law", "exponential", "linear", "bimodal",
            "causal_chain", "periodic", "lognormal",
        ]
        analogies = [
            _make_analogy(
                similarity=0.80 + (i % 20) * 0.01,
                id_suffix=f"{i:03d}",
                domain_a=domains[i % len(domains)],
                domain_b=domains[(i + 3) % len(domains)],
                form=forms[i % len(forms)],
            )
            for i in range(100)
        ]
        engine = MockAnalogyEngine(analogies)
        bridge = AnalogyHypothesisBridge(engine)
        import time as t
        start = t.time()
        result = bridge.generate_from_analogies(max_new=10)
        elapsed = t.time() - start
        assert elapsed < 1.0, f"Took {elapsed:.2f}s for 100 analogies"
        assert len(result) == 10
        # All should be unique names
        names = [h["name"] for h in result]
        assert len(set(names)) == len(names), "Duplicate names in output"


# ── Test 10: TheoryEngine _analogies cache path ──────────────────────────

class TestCachedAnalogySource:
    """Test that inject_analogy_hypotheses works with TheoryEngine's _analogies cache."""

    def test_reads_from_theory_engine_cache(self):
        """When theory_engine._analogies has data, bridge should use it."""
        a = _make_analogy(similarity=0.90, domain_a="Astrophysics",
                          domain_b="Economics", form="power_law")

        class MockTheoryEngine:
            _analogies = [a]
            analogy_engine = None  # No direct engine

        result = inject_analogy_hypotheses(
            engine=None, theory_engine=MockTheoryEngine(),
            max_new=3, similarity_threshold=0.80,
        )
        assert len(result) == 1
        assert result[0]["domain"] == "Economics"
        assert result[0]["finding_type"] == "analogy_transfer"

    def test_cache_with_non_novel_filtered(self):
        """Novel filter should still work with cache path."""
        novel = _make_analogy(similarity=0.90, id_suffix="novel")
        non_novel = _make_analogy(similarity=0.90, id_suffix="known")
        non_novel.novel = False

        class MockTheoryEngine:
            _analogies = [novel, non_novel]
            analogy_engine = None

        result = inject_analogy_hypotheses(
            engine=None, theory_engine=MockTheoryEngine(),
            max_new=5, similarity_threshold=0.80,
        )
        # Default include_non_novel=False, so only novel should be used
        assert len(result) == 1

    def test_empty_cache_falls_through_to_analogy_engine(self):
        """If _analogies is empty, should fall back to analogy_engine."""
        a = _make_analogy(similarity=0.85)

        class MockTheoryEngine:
            _analogies = []  # Empty cache
            analogy_engine = MockAnalogyEngine([a])

        result = inject_analogy_hypotheses(
            engine=None, theory_engine=MockTheoryEngine(),
            max_new=3, similarity_threshold=0.80,
        )
        assert len(result) == 1  # Should get from analogy_engine fallback
