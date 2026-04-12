"""
Tests for RetrievalProfile abstraction and profile-aware MemoryAugmentedOrient.
"""

import os
import sys
from dataclasses import dataclass

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.environ.get("ASTRA_DEV_PATH", "/shared/ASTRA-dev"))
sys.path.insert(0, os.environ.get("MEMPALACE_PATH", "/shared/mempalace"))

from mempalace_agi.retrieval_profiles import (
    RetrievalProfile,
    ORIENT_BREADTH,
    EVALUATE_PRECISION,
    DECIDE_RECENCY,
    get_profile,
    compose,
)
from mempalace_agi.palace_discovery_memory import PalaceDiscoveryMemory
from mempalace_agi.memory_augmented_orient import MemoryAugmentedOrient
from mempalace_agi.config import IntegrationConfig


# ── RetrievalProfile Creation & Defaults ────────────────────────────


class TestProfileDefaults:
    """Verify the three standard profiles have correct field values."""

    def test_orient_breadth_name(self):
        assert ORIENT_BREADTH.name == "orient_breadth"

    def test_orient_breadth_n_results(self):
        assert ORIENT_BREADTH.n_results == 16

    def test_orient_breadth_min_similarity(self):
        assert ORIENT_BREADTH.min_similarity == 0.2

    def test_orient_breadth_no_time_decay(self):
        assert ORIENT_BREADTH.time_decay is False
        assert ORIENT_BREADTH.half_life_days is None

    def test_orient_breadth_includes_all_domains(self):
        assert ORIENT_BREADTH.exclude_domain is False

    def test_orient_breadth_no_status_filter(self):
        assert ORIENT_BREADTH.require_status is None

    def test_evaluate_precision_name(self):
        assert EVALUATE_PRECISION.name == "evaluate_precision"

    def test_evaluate_precision_n_results(self):
        assert EVALUATE_PRECISION.n_results == 8

    def test_evaluate_precision_high_threshold(self):
        assert EVALUATE_PRECISION.min_similarity == 0.6

    def test_evaluate_precision_excludes_domain(self):
        assert EVALUATE_PRECISION.exclude_domain is True

    def test_evaluate_precision_requires_decided(self):
        assert EVALUATE_PRECISION.require_status == "decided"

    def test_decide_recency_name(self):
        assert DECIDE_RECENCY.name == "decide_recency"

    def test_decide_recency_n_results(self):
        assert DECIDE_RECENCY.n_results == 5

    def test_decide_recency_time_decay(self):
        assert DECIDE_RECENCY.time_decay is True
        assert DECIDE_RECENCY.half_life_days == 30

    def test_decide_recency_requires_decided(self):
        assert DECIDE_RECENCY.require_status == "decided"

    def test_profiles_are_frozen(self):
        """RetrievalProfile is frozen — cannot mutate fields."""
        with pytest.raises(AttributeError):
            ORIENT_BREADTH.n_results = 99


# ── compose() ───────────────────────────────────────────────────────


class TestCompose:
    """Test the compose() override function."""

    def test_compose_creates_copy(self):
        custom = compose(ORIENT_BREADTH, n_results=20)
        assert custom.n_results == 20
        assert ORIENT_BREADTH.n_results == 16  # Original unchanged

    def test_compose_preserves_other_fields(self):
        custom = compose(ORIENT_BREADTH, n_results=20)
        assert custom.min_similarity == ORIENT_BREADTH.min_similarity
        assert custom.name == ORIENT_BREADTH.name
        assert custom.time_decay == ORIENT_BREADTH.time_decay

    def test_compose_multiple_overrides(self):
        custom = compose(
            EVALUATE_PRECISION,
            min_similarity=0.7,
            n_results=12,
            exclude_domain=False,
        )
        assert custom.min_similarity == 0.7
        assert custom.n_results == 12
        assert custom.exclude_domain is False
        # Unchanged fields
        assert custom.name == "evaluate_precision"
        assert custom.require_status == "decided"

    def test_compose_override_description(self):
        custom = compose(ORIENT_BREADTH, description="My custom profile")
        assert custom.description == "My custom profile"

    def test_compose_override_half_life(self):
        custom = compose(DECIDE_RECENCY, half_life_days=7)
        assert custom.half_life_days == 7

    def test_compose_returns_new_instance(self):
        custom = compose(ORIENT_BREADTH, n_results=20)
        assert custom is not ORIENT_BREADTH


# ── get_profile() factory ───────────────────────────────────────────


class TestGetProfile:
    """Test the get_profile() factory function."""

    def test_get_orient(self):
        p = get_profile("orient_breadth")
        assert p is ORIENT_BREADTH

    def test_get_evaluate(self):
        p = get_profile("evaluate_precision")
        assert p is EVALUATE_PRECISION

    def test_get_decide(self):
        p = get_profile("decide_recency")
        assert p is DECIDE_RECENCY

    def test_get_unknown_raises(self):
        with pytest.raises(ValueError, match="Unknown profile"):
            get_profile("nonexistent")


# ── Profile Integration with MemoryAugmentedOrient ──────────────────


@dataclass
class MockHypothesis:
    id: str
    description: str
    domain: str
    name: str = ""
    variables: list = None


@pytest.fixture
def memory(test_config):
    return PalaceDiscoveryMemory(config=test_config, max_records=100)


@pytest.fixture
def orient_with_profiles(memory):
    """Orient using explicit profiles."""
    return MemoryAugmentedOrient(
        palace_memory=memory,
        orient_profile=compose(ORIENT_BREADTH, n_results=3, min_similarity=0.0),
        evaluate_profile=compose(EVALUATE_PRECISION, n_results=3, min_similarity=0.0),
        decide_profile=compose(DECIDE_RECENCY, n_results=3, min_similarity=0.0),
    )


def _populate(memory):
    memory.record_discovery(
        hypothesis_id="H001", domain="Astrophysics",
        finding_type="scaling", variables=["mass", "radius"],
        statistic=5.0, p_value=0.0001,
        description="Mass-radius power law in exoplanets",
        data_source="exoplanets",
    )
    memory.record_discovery(
        hypothesis_id="H002", domain="Economics",
        finding_type="correlation", variables=["gdp", "population"],
        statistic=4.0, p_value=0.005,
        description="GDP scales with population across nations",
        data_source="worldbank",
    )
    memory.record_discovery(
        hypothesis_id="H003", domain="Climate",
        finding_type="anomaly", variables=["temperature", "co2"],
        statistic=6.0, p_value=0.00001,
        description="Temperature anomaly tracks CO2 levels",
        data_source="gistemp",
    )


class TestOrientProfileDefault:
    """Orient uses ORIENT_BREADTH by default."""

    def test_default_orient_profile(self, memory):
        o = MemoryAugmentedOrient(palace_memory=memory)
        assert o.orient_profile.name == "orient_breadth"

    def test_default_max_results_from_profile(self, memory):
        o = MemoryAugmentedOrient(palace_memory=memory)
        assert o.max_results_per_hypothesis == 16

    def test_default_min_similarity_from_profile(self, memory):
        o = MemoryAugmentedOrient(palace_memory=memory)
        assert o.min_similarity == 0.2

    def test_retrieve_context_profile_used(self, memory):
        _populate(memory)
        o = MemoryAugmentedOrient(palace_memory=memory)
        context = o.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Test", domain="Astrophysics")],
            phase="orient",
        )
        assert context["profile_used"] == "orient_breadth"


class TestPhaseSelection:
    """Each phase selects the correct profile."""

    def test_orient_phase(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
            phase="orient",
        )
        assert ctx["profile_used"] == "orient_breadth"

    def test_evaluate_phase(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
            phase="evaluate",
        )
        assert ctx["profile_used"] == "evaluate_precision"

    def test_decide_phase(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
            phase="decide",
        )
        assert ctx["profile_used"] == "decide_recency"

    def test_retrieve_for_evaluate_uses_evaluate_profile(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_for_evaluate(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
        )
        assert ctx["profile_used"] == "evaluate_precision"

    def test_retrieve_for_decide_uses_decide_profile(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_for_decide(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
        )
        assert ctx["profile_used"] == "decide_recency"

    def test_unknown_phase_defaults_to_orient(self, orient_with_profiles):
        _populate(orient_with_profiles.palace_memory)
        ctx = orient_with_profiles.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Scaling", domain="Astrophysics")],
            phase="unknown_phase",
        )
        assert ctx["profile_used"] == "orient_breadth"


class TestBackwardCompatibility:
    """Old numeric init params still work."""

    def test_numeric_max_results_per_hypothesis(self, memory):
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            max_results_per_hypothesis=3,
        )
        assert o.max_results_per_hypothesis == 3

    def test_numeric_min_similarity(self, memory):
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            min_similarity=0.5,
        )
        assert o.min_similarity == 0.5

    def test_numeric_cross_domain_results(self, memory):
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            cross_domain_results=7,
        )
        assert o.cross_domain_results == 7

    def test_numeric_params_set_orient_profile(self, memory):
        """Numeric params compose a profile from ORIENT_BREADTH."""
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            max_results_per_hypothesis=4,
            min_similarity=0.3,
        )
        assert o.orient_profile.name == "orient_breadth"
        assert o.orient_profile.n_results == 4
        assert o.orient_profile.min_similarity == 0.3

    def test_explicit_profile_overrides_numeric(self, memory):
        """When a profile is given, numeric params are ignored."""
        custom_profile = compose(ORIENT_BREADTH, n_results=7)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            max_results_per_hypothesis=999,  # Should be ignored
            orient_profile=custom_profile,
        )
        assert o.max_results_per_hypothesis == 7

    def test_old_retrieve_context_still_works(self, memory):
        """Phase param defaults to 'orient' — old callers unaffected."""
        _populate(memory)
        o = MemoryAugmentedOrient(
            palace_memory=memory,
            max_results_per_hypothesis=3,
            cross_domain_results=2,
            min_similarity=0.0,
        )
        ctx = o.retrieve_context(
            hypotheses=[MockHypothesis(id="H010", description="Mass-radius", domain="Astrophysics")],
        )
        assert "per_hypothesis" in ctx
        assert "cross_domain" in ctx
        assert "H010" in ctx["per_hypothesis"]
