"""
Tests for DiscoverySynergyAnalyzer and SynergyMetrics.

Covers all 7 information-theoretic metrics and the analyzer wrapper.
"""

import sys
import os
import math

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mempalace_agi.discovery_synergy import (
    SynergyMetrics,
    SynergyProfile,
    DiscoverySynergyAnalyzer,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def metrics():
    return SynergyMetrics(n_bins=10)


@pytest.fixture
def rng():
    """Reproducible RNG."""
    return np.random.default_rng(42)


@pytest.fixture
def correlated_pair(rng):
    """X and Y with known correlation (Y = X + small noise)."""
    x = rng.standard_normal(200)
    y = x + rng.standard_normal(200) * 0.1
    return x, y


@pytest.fixture
def independent_pair(rng):
    """Two fully independent random signals."""
    x = rng.standard_normal(200)
    y = rng.standard_normal(200)
    return x, y


@pytest.fixture
def causal_pair(rng):
    """Y follows X with a 1-step lag (causal link X→Y)."""
    n = 300
    x = rng.standard_normal(n)
    y = np.zeros(n)
    y[0] = rng.standard_normal()
    for t in range(1, n):
        y[t] = 0.7 * x[t - 1] + 0.3 * rng.standard_normal()
    return x, y


@pytest.fixture
def phase_locked_pair():
    """Two sine waves locked in phase (same frequency, small phase offset)."""
    t = np.linspace(0, 10 * np.pi, 500)
    x = np.sin(t)
    y = np.sin(t + 0.1)  # tiny constant phase offset
    return x, y


@pytest.fixture
def analyzer():
    """Fresh analyzer with min_samples=5 for testing."""
    return DiscoverySynergyAnalyzer(window_size=500, min_samples=5)


# ═══════════════════════════════════════════════════════════════════════
#  1–3. Mutual Information
# ═══════════════════════════════════════════════════════════════════════

class TestMutualInformation:

    def test_identical_signals_high_mi(self, metrics):
        """Identical signals should produce MI close to 1.0."""
        x = np.linspace(0, 10, 100)
        mi = metrics.mutual_information(x, x.copy())
        assert mi >= 0.9, f"MI for identical signals should be ~1.0, got {mi}"

    def test_independent_signals_low_mi(self, metrics, independent_pair):
        """Independent random signals should produce low MI."""
        x, y = independent_pair
        mi = metrics.mutual_information(x, y)
        assert mi < 0.3, f"MI for independent signals should be low, got {mi}"

    def test_empty_signal_returns_zero(self, metrics):
        """Empty or length-1 signals → 0.0."""
        assert metrics.mutual_information(np.array([]), np.array([])) == 0.0
        assert metrics.mutual_information(np.array([1.0]), np.array([2.0])) == 0.0

    def test_length_mismatch_returns_zero(self, metrics):
        """Mismatched lengths → 0.0."""
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([1.0, 2.0])
        assert metrics.mutual_information(x, y) == 0.0

    def test_correlated_signals_moderate_to_high_mi(self, metrics, correlated_pair):
        """Highly correlated (Y = X + noise) should give MI > 0.5."""
        x, y = correlated_pair
        mi = metrics.mutual_information(x, y)
        assert mi > 0.5, f"Correlated pair MI should be high, got {mi}"


# ═══════════════════════════════════════════════════════════════════════
#  4–5. Transfer Entropy
# ═══════════════════════════════════════════════════════════════════════

class TestTransferEntropy:

    def test_causal_lag_positive_te(self, metrics, causal_pair):
        """When Y follows X with lag, TE(X→Y) should be > 0."""
        x, y = causal_pair
        te = metrics.transfer_entropy(x, y, lag=1)
        assert te > 0.0, f"TE(X→Y) for causal pair should be positive, got {te}"

    def test_independent_lower_te_than_causal(self, metrics, rng):
        """Independent signals should have lower TE than causal pair (given enough data)."""
        # TE requires many samples to resolve — use 2000
        n = 2000
        x_ind = rng.standard_normal(n)
        y_ind = rng.standard_normal(n)
        te_ind = metrics.transfer_entropy(x_ind, y_ind)

        x_causal = rng.standard_normal(n)
        y_causal = np.zeros(n)
        y_causal[0] = rng.standard_normal()
        for t in range(1, n):
            y_causal[t] = 0.7 * x_causal[t - 1] + 0.3 * rng.standard_normal()
        te_causal = metrics.transfer_entropy(x_causal, y_causal)

        assert te_causal > te_ind, (
            f"Causal TE ({te_causal}) should exceed independent TE ({te_ind})"
        )

    def test_short_signal_returns_zero(self, metrics):
        """Too-short signals → 0.0."""
        x = np.array([1.0, 2.0])
        y = np.array([3.0, 4.0])
        assert metrics.transfer_entropy(x, y, lag=1) == 0.0

    def test_directed_asymmetry(self, metrics):
        """TE(X→Y) > TE(Y→X) when X causes Y (needs large N to resolve)."""
        rng = np.random.default_rng(123)
        n = 2000
        x = rng.standard_normal(n)
        y = np.zeros(n)
        y[0] = rng.standard_normal()
        for t in range(1, n):
            y[t] = 0.7 * x[t - 1] + 0.3 * rng.standard_normal()
        te_xy = metrics.transfer_entropy(x, y, lag=1)
        te_yx = metrics.transfer_entropy(y, x, lag=1)
        assert te_xy > te_yx, (
            f"TE(X→Y)={te_xy} should exceed TE(Y→X)={te_yx} for causal direction"
        )


# ═══════════════════════════════════════════════════════════════════════
#  6–7. Phase Locking Value
# ═══════════════════════════════════════════════════════════════════════

class TestPhaseLockingValue:

    def test_phase_locked_high_plv(self, metrics, phase_locked_pair):
        """Phase-locked sine waves → PLV close to 1.0."""
        x, y = phase_locked_pair
        plv = metrics.phase_locking_value(x, y)
        assert plv > 0.9, f"PLV for phase-locked sines should be ~1.0, got {plv}"

    def test_independent_random_low_plv(self, metrics, rng):
        """Independent random signals → low PLV."""
        x = rng.standard_normal(200)
        y = rng.standard_normal(200)
        plv = metrics.phase_locking_value(x, y)
        assert plv < 0.5, f"PLV for random signals should be low, got {plv}"

    def test_short_signal_returns_zero(self, metrics):
        """Signals with < 4 samples → 0.0."""
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([1.0, 2.0, 3.0])
        assert metrics.phase_locking_value(x, y) == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  8–9. Spectral Coherence
# ═══════════════════════════════════════════════════════════════════════

class TestSpectralCoherence:

    def test_correlated_signals_high_coherence(self, metrics, correlated_pair):
        """Highly correlated signals → high spectral coherence."""
        x, y = correlated_pair
        coh = metrics.spectral_coherence(x, y)
        assert coh > 0.5, f"Coherence for correlated pair should be high, got {coh}"

    def test_short_signal_returns_zero(self, metrics):
        """Signals with < 8 samples → 0.0."""
        x = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        y = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        assert metrics.spectral_coherence(x, y) == 0.0

    def test_returns_bounded(self, metrics, rng):
        """Coherence must be in [0, 1]."""
        x = rng.standard_normal(100)
        y = rng.standard_normal(100)
        coh = metrics.spectral_coherence(x, y)
        assert 0.0 <= coh <= 1.0


# ═══════════════════════════════════════════════════════════════════════
#  10. Emergence Index
# ═══════════════════════════════════════════════════════════════════════

class TestEmergenceIndex:

    def test_returns_bounded(self, metrics, rng):
        """Emergence index must be in [0, 1]."""
        x = rng.standard_normal(100)
        y = rng.standard_normal(100)
        ei = metrics.emergence_index(x, y)
        assert 0.0 <= ei <= 1.0, f"Emergence index out of range: {ei}"

    def test_short_signal_returns_zero(self, metrics):
        assert metrics.emergence_index(np.array([1.0]), np.array([2.0])) == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  11. Integration Index
# ═══════════════════════════════════════════════════════════════════════

class TestIntegrationIndex:

    def test_returns_bounded(self, metrics, correlated_pair):
        """Integration index = (MI * PLV * coherence)^(1/3), must be in [0,1]."""
        x, y = correlated_pair
        ii = metrics.integration_index(x, y)
        assert 0.0 <= ii <= 1.0

    def test_high_for_correlated(self, metrics, correlated_pair):
        """Correlated pair should have non-trivial integration index."""
        x, y = correlated_pair
        ii = metrics.integration_index(x, y)
        # All three sub-metrics should contribute
        assert ii > 0.3, f"Integration index for correlated pair should be decent, got {ii}"

    def test_short_signal_returns_zero(self, metrics):
        """< 8 samples → 0.0 (coherence requires ≥ 8)."""
        x = np.array([1.0, 2.0, 3.0])
        y = np.array([1.0, 2.0, 3.0])
        assert metrics.integration_index(x, y) == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  12–13. Complexity Resonance
# ═══════════════════════════════════════════════════════════════════════

class TestComplexityResonance:

    def test_identical_signals_perfect_resonance(self, metrics):
        """Identical signals → LZ(X) == LZ(Y), resonance = 1.0."""
        x = np.linspace(0, 5, 50)
        cr = metrics.complexity_resonance(x, x.copy())
        assert cr == pytest.approx(1.0), f"Identical signals should give CR=1.0, got {cr}"

    def test_different_complexity_lower(self, metrics):
        """Constant vs random should have mismatched complexity, CR < 1."""
        x = np.ones(50)         # constant → LZ = 0 (std≈0 → all same bin)
        y = np.random.default_rng(7).standard_normal(50)  # random → higher LZ
        cr = metrics.complexity_resonance(x, y)
        # Constant discretizes to all zeros, random to varied bins
        assert cr < 1.0, f"Mismatched complexity should give CR < 1.0, got {cr}"

    def test_short_signal_returns_zero(self, metrics):
        assert metrics.complexity_resonance(np.array([1.0]), np.array([2.0])) == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  14–16. Lempel-Ziv Complexity
# ═══════════════════════════════════════════════════════════════════════

class TestLempelZivComplexity:

    def test_constant_signal_lower_than_random(self, metrics):
        """A constant signal should have lower LZ than a random signal.
        
        Note: LZ76 on "000...0" is not zero — repeated chars still generate
        O(sqrt(n)) new words. But it should be less complex than random.
        """
        seq_const = np.zeros(200, dtype=int)
        lz_const = metrics.lempel_ziv_complexity(seq_const)

        rng = np.random.default_rng(77)
        seq_rand = rng.integers(0, 10, size=200)
        lz_rand = metrics.lempel_ziv_complexity(seq_rand)

        assert lz_const < lz_rand, (
            f"Constant LZ ({lz_const}) should be less than random LZ ({lz_rand})"
        )

    def test_random_signal_higher(self, metrics):
        """A random signal should have significantly higher LZ than constant."""
        rng = np.random.default_rng(99)
        seq_rand = rng.integers(0, 10, size=100)
        lz_rand = metrics.lempel_ziv_complexity(seq_rand)

        seq_const = np.zeros(100, dtype=int)
        lz_const = metrics.lempel_ziv_complexity(seq_const)

        assert lz_rand > lz_const, (
            f"Random LZ ({lz_rand}) should exceed constant LZ ({lz_const})"
        )

    def test_empty_returns_zero(self, metrics):
        """Empty sequence → 0.0."""
        assert metrics.lempel_ziv_complexity(np.array([])) == 0.0

    def test_single_element_returns_zero(self, metrics):
        """Length-1 → 0.0."""
        assert metrics.lempel_ziv_complexity(np.array([5])) == 0.0

    def test_lz_normalized_nonnegative(self, metrics):
        """LZ complexity should always be ≥ 0."""
        for _ in range(10):
            seq = np.random.default_rng().integers(0, 5, size=50)
            assert metrics.lempel_ziv_complexity(seq) >= 0.0


# ═══════════════════════════════════════════════════════════════════════
#  17. compute_all
# ═══════════════════════════════════════════════════════════════════════

class TestComputeAll:

    def test_returns_synergy_profile(self, metrics, correlated_pair):
        """compute_all should return a SynergyProfile with all 7 metrics."""
        x, y = correlated_pair
        profile = metrics.compute_all(x, y, pair_name="test↔pair")

        assert isinstance(profile, SynergyProfile)
        assert profile.pair_name == "test↔pair"
        # Each metric should be a float in [0, 1]
        for field_name in [
            "mutual_information",
            "transfer_entropy",
            "phase_locking_value",
            "spectral_coherence",
            "emergence_index",
            "integration_index",
            "complexity_resonance",
        ]:
            val = getattr(profile, field_name)
            assert isinstance(val, float), f"{field_name} should be float, got {type(val)}"
            assert 0.0 <= val <= 1.0, f"{field_name} out of [0,1]: {val}"


# ═══════════════════════════════════════════════════════════════════════
#  18–22. DiscoverySynergyAnalyzer
# ═══════════════════════════════════════════════════════════════════════

class TestDiscoverySynergyAnalyzer:

    def _populate(self, analyzer, rng, n_cycles=30):
        """Helper: record n_cycles of random discovery counts for 3 domains."""
        for i in range(n_cycles):
            analyzer.record_cycle({
                "astrophysics": int(rng.poisson(3)),
                "climate": int(rng.poisson(2)),
                "economics": int(rng.poisson(1)),
            })

    def test_record_cycle_tracking(self, analyzer):
        """record_cycle populates domain series."""
        analyzer.record_cycle({"astro": 5, "econ": 2})
        assert analyzer.domains == ["astro", "econ"]
        assert analyzer.sample_count == 1

    def test_compute_pairwise_synergy(self, analyzer, rng):
        """After enough data, pairwise synergy returns profiles for all pairs."""
        self._populate(analyzer, rng)
        profiles = analyzer.compute_pairwise_synergy()
        # 3 domains → 3 pairs
        assert len(profiles) == 3
        for pair_name, profile in profiles.items():
            assert "↔" in pair_name
            assert isinstance(profile, SynergyProfile)

    def test_pairwise_insufficient_data(self, analyzer):
        """< min_samples → empty dict."""
        analyzer.record_cycle({"a": 1, "b": 2})
        assert analyzer.compute_pairwise_synergy() == {}

    def test_get_transfer_entropy_matrix(self, analyzer, rng):
        """TE matrix should be NxN with zeros on diagonal."""
        self._populate(analyzer, rng)
        matrix = analyzer.get_transfer_entropy_matrix()
        domains = analyzer.domains
        assert len(matrix) == 3
        for d in domains:
            assert d in matrix
            assert matrix[d][d] == 0.0
            for d2 in domains:
                assert d2 in matrix[d]
                assert 0.0 <= matrix[d][d2] <= 1.0

    def test_get_top_synergies(self, analyzer, rng):
        """Top synergies returns tuples sorted by integration index desc."""
        self._populate(analyzer, rng)
        top = analyzer.get_top_synergies(n=2)
        assert len(top) <= 2
        assert all(len(t) == 3 for t in top)
        # Check sorted descending
        if len(top) == 2:
            assert top[0][2] >= top[1][2]

    def test_get_emergence_score_insufficient_data(self, analyzer):
        """No data → emergence = 0.0."""
        assert analyzer.get_emergence_score() == 0.0

    def test_get_emergence_score_with_data(self, analyzer, rng):
        """With enough data, emergence score should be in [0, 1]."""
        self._populate(analyzer, rng)
        score = analyzer.get_emergence_score()
        assert 0.0 <= score <= 1.0

    def test_get_synergy_report_structure(self, analyzer, rng):
        """Full report should have all expected keys."""
        self._populate(analyzer, rng)
        report = analyzer.get_synergy_report()

        assert "domains" in report
        assert "sample_count" in report
        assert "pairwise" in report
        assert "transfer_entropy_matrix" in report
        assert "top_synergies" in report
        assert "overall_emergence" in report

        assert report["sample_count"] >= 5
        assert len(report["domains"]) == 3
        assert len(report["pairwise"]) == 3  # 3 pairs from 3 domains
        assert isinstance(report["overall_emergence"], float)

    def test_window_trimming(self):
        """Series should be trimmed to window_size."""
        a = DiscoverySynergyAnalyzer(window_size=10, min_samples=1)
        for i in range(20):
            a.record_cycle({"x": i})
        # Internal series should have at most 10 entries
        assert len(a._domain_series["x"]) == 10
        # Last entry should be 19
        assert a._domain_series["x"][-1] == 19.0

    def test_single_domain_no_pairs(self, analyzer, rng):
        """Single domain → no pairwise synergy possible."""
        for _ in range(20):
            analyzer.record_cycle({"solo": int(rng.poisson(2))})
        assert analyzer.compute_pairwise_synergy() == {}
        assert analyzer.get_emergence_score() == 0.0


# ═══════════════════════════════════════════════════════════════════════
#  SynergyProfile dataclass
# ═══════════════════════════════════════════════════════════════════════

class TestSynergyProfile:

    def test_defaults(self):
        """All metric fields default to 0.0."""
        p = SynergyProfile(pair_name="a↔b")
        assert p.mutual_information == 0.0
        assert p.transfer_entropy == 0.0
        assert p.phase_locking_value == 0.0
        assert p.spectral_coherence == 0.0
        assert p.emergence_index == 0.0
        assert p.integration_index == 0.0
        assert p.complexity_resonance == 0.0

    def test_construction(self):
        p = SynergyProfile(
            pair_name="x↔y",
            mutual_information=0.5,
            transfer_entropy=0.3,
            phase_locking_value=0.8,
            spectral_coherence=0.6,
            emergence_index=0.4,
            integration_index=0.55,
            complexity_resonance=0.9,
        )
        assert p.pair_name == "x↔y"
        assert p.mutual_information == 0.5
        assert p.complexity_resonance == 0.9
