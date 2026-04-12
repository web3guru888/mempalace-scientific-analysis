"""
Cross-Domain Discovery Synergy Analyzer.

Measures information-theoretic synergy between research domains using 7 metrics:
mutual information, transfer entropy, phase locking value, spectral coherence,
emergence index, integration index, and complexity resonance.

Adapted from ASI:BUILD (https://gitlab.com/asi-build/asi-build), MIT License.
Original: cognitive_synergy/core/synergy_metrics.py
"""

import math
import numpy as np
from dataclasses import dataclass, field
from itertools import combinations
from typing import Dict, List, Optional, Set, Tuple

from scipy.signal import coherence as scipy_coherence, hilbert
from scipy.stats import entropy as scipy_entropy
from sklearn.metrics import normalized_mutual_info_score


@dataclass
class SynergyProfile:
    """Full synergy profile for a domain pair."""
    pair_name: str
    mutual_information: float = 0.0
    transfer_entropy: float = 0.0
    phase_locking_value: float = 0.0
    spectral_coherence: float = 0.0
    emergence_index: float = 0.0
    integration_index: float = 0.0
    complexity_resonance: float = 0.0


class SynergyMetrics:
    """
    7 information-theoretic synergy metrics.
    
    Ported from ASI:BUILD cognitive_synergy — algorithms preserved with
    Lempel-Ziv complexity fixed to proper O(n log n) LZ76.
    """

    def __init__(self, n_bins: int = 10):
        self._n_bins = n_bins

    # ── 1. Mutual Information ──────────────────────────────────────────

    def mutual_information(self, x: np.ndarray, y: np.ndarray) -> float:
        """Normalized mutual information via sklearn on discretized signals.
        
        Returns value in [0, 1]. 1 = perfect dependence, 0 = independent.
        """
        if len(x) < 2 or len(y) < 2 or len(x) != len(y):
            return 0.0
        xd = self._discretize(x)
        yd = self._discretize(y)
        try:
            mi = normalized_mutual_info_score(xd, yd)
            return float(np.clip(mi, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 2. Transfer Entropy ────────────────────────────────────────────

    def transfer_entropy(self, x: np.ndarray, y: np.ndarray, lag: int = 1) -> float:
        """Transfer entropy TE(X→Y) = H(Y_{t+lag}|Y_t) - H(Y_{t+lag}|Y_t, X_t).
        
        Measures directed information flow from X to Y.
        Returns value in [0, 1].
        """
        if len(x) < lag + 2 or len(y) < lag + 2:
            return 0.0
        try:
            x_t = self._discretize(x[:-lag])
            y_t = self._discretize(y[:-lag])
            y_future = self._discretize(y[lag:])

            # H(Y_{t+1} | Y_t)
            h_y_given_yt = self._conditional_entropy(y_future, y_t)

            # H(Y_{t+1} | Y_t, X_t) — condition on joint
            joint_yx = np.column_stack([y_t, x_t])
            h_y_given_yx = self._conditional_entropy(y_future, joint_yx)

            te = h_y_given_yt - h_y_given_yx
            return float(np.clip(te, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 3. Phase Locking Value ─────────────────────────────────────────

    def phase_locking_value(self, x: np.ndarray, y: np.ndarray) -> float:
        """Hilbert-transform Phase Locking Value (PLV).
        
        Measures phase synchronization. Returns [0, 1].
        """
        if len(x) < 4 or len(y) < 4 or len(x) != len(y):
            return 0.0
        try:
            xa = hilbert(x - np.mean(x))
            ya = hilbert(y - np.mean(y))
            phase_diff = np.angle(xa) - np.angle(ya)
            plv = float(np.abs(np.mean(np.exp(1j * phase_diff))))
            return float(np.clip(plv, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 4. Spectral Coherence ──────────────────────────────────────────

    def spectral_coherence(self, x: np.ndarray, y: np.ndarray, fs: float = 1.0) -> float:
        """Mean magnitude-squared coherence via scipy.signal.coherence.
        
        Returns [0, 1]. High value = functionally connected in frequency domain.
        """
        if len(x) < 8 or len(y) < 8 or len(x) != len(y):
            return 0.0
        try:
            nperseg = min(64, len(x) // 4)
            if nperseg < 2:
                return 0.0
            _, coh = scipy_coherence(x, y, fs=fs, nperseg=nperseg)
            val = float(np.mean(coh))
            return float(np.clip(val, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 5. Emergence Index ─────────────────────────────────────────────

    def emergence_index(self, x: np.ndarray, y: np.ndarray) -> float:
        """Emergence index: MI - max(H(X), H(Y)) + joint_complexity.
        
        Measures whether the pair produces more information together
        than either alone. Normalized to [0, 1].
        """
        if len(x) < 2 or len(y) < 2:
            return 0.0
        try:
            mi = self.mutual_information(x, y)
            hx = self._shannon_entropy(self._discretize(x))
            hy = self._shannon_entropy(self._discretize(y))

            # Joint complexity approximated by joint entropy
            xd = self._discretize(x)
            yd = self._discretize(y)
            joint_labels = [f"{a}_{b}" for a, b in zip(xd, yd)]
            joint_c = self._shannon_entropy(np.array(joint_labels))

            ei = mi - max(hx, hy) + joint_c
            # Normalize roughly to [0, 1]
            return float(np.clip((ei + 2.0) / 4.0, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 6. Integration Index ───────────────────────────────────────────

    def integration_index(self, x: np.ndarray, y: np.ndarray) -> float:
        """Geometric mean of MI × PLV × coherence. Returns [0, 1]."""
        if len(x) < 8 or len(y) < 8:
            return 0.0
        try:
            mi = self.mutual_information(x, y)
            plv = self.phase_locking_value(x, y)
            coh = self.spectral_coherence(x, y)
            ii = (mi * plv * coh) ** (1.0 / 3.0)
            return float(np.clip(ii, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── 7. Complexity Resonance ────────────────────────────────────────

    def complexity_resonance(self, x: np.ndarray, y: np.ndarray) -> float:
        """1 - |LZ(X) - LZ(Y)| / (LZ(X) + LZ(Y)).
        
        Measures matched complexity levels. Uses proper O(n log n) LZ76.
        Returns [0, 1]. 1 = perfectly matched complexity.
        """
        if len(x) < 2 or len(y) < 2:
            return 0.0
        try:
            cx = self.lempel_ziv_complexity(self._discretize(x))
            cy = self.lempel_ziv_complexity(self._discretize(y))
            if cx + cy == 0:
                return 1.0
            cr = 1.0 - abs(cx - cy) / (cx + cy)
            return float(np.clip(cr, 0.0, 1.0))
        except Exception:
            return 0.0

    # ── Lempel-Ziv 76 Complexity — O(n log n) ─────────────────────────

    @staticmethod
    def lempel_ziv_complexity(sequence: np.ndarray) -> float:
        """Proper LZ76 complexity normalized by n/log2(n).
        
        The ASI:BUILD original uses O(n²) substring enumeration which is
        incorrect and slow. This implements the standard sequential scan:
        walk the string, extending the current word until it's new, then
        start a new word. Count of words = raw complexity. Normalize by
        the asymptotic bound n / log₂(n).
        
        Returns a float ≥ 0 (typically 0–1 for normalized signals).
        """
        if len(sequence) == 0:
            return 0.0
        s = "".join(str(int(v)) for v in sequence)
        n = len(s)
        if n <= 1:
            return 0.0

        # Standard LZ76: scan and count new words
        dictionary: set = set()
        word = ""
        complexity = 0
        for ch in s:
            word += ch
            if word not in dictionary:
                dictionary.add(word)
                complexity += 1
                word = ""
        if word:  # residual
            complexity += 1

        # Normalize by asymptotic bound
        normalizer = n / math.log2(n) if n > 1 else 1.0
        return complexity / normalizer

    # ── Internal Helpers ───────────────────────────────────────────────

    def _discretize(self, signal: np.ndarray) -> np.ndarray:
        """Quantile-based discretization into n_bins bins."""
        if len(signal) == 0:
            return np.array([], dtype=int)
        if np.std(signal) < 1e-10:
            return np.zeros(len(signal), dtype=int)
        try:
            bins = np.unique(np.quantile(signal, np.linspace(0, 1, self._n_bins + 1)))
            if len(bins) <= 1:
                return np.zeros(len(signal), dtype=int)
            return np.digitize(signal, bins[1:-1]).astype(int)
        except Exception:
            return np.zeros(len(signal), dtype=int)

    def _shannon_entropy(self, discrete_signal: np.ndarray) -> float:
        """Shannon entropy H(X) in bits."""
        if len(discrete_signal) == 0:
            return 0.0
        _, counts = np.unique(discrete_signal, return_counts=True)
        if len(counts) <= 1:
            return 0.0
        probs = counts / len(discrete_signal)
        h = float(scipy_entropy(probs, base=2))
        return h if not np.isnan(h) else 0.0

    def _conditional_entropy(self, y: np.ndarray, x: np.ndarray) -> float:
        """H(Y|X) = H(Y,X) - H(X)."""
        try:
            if x.ndim > 1:
                x_labels = np.array([str(tuple(row)) for row in x])
            else:
                x_labels = x.astype(str)
            joint_labels = np.array([f"{a}_{b}" for a, b in zip(y.astype(str), x_labels)])
            h_joint = self._shannon_entropy(joint_labels)
            h_x = self._shannon_entropy(x_labels)
            return max(0.0, h_joint - h_x)
        except Exception:
            return 0.0

    def compute_all(self, x: np.ndarray, y: np.ndarray, pair_name: str = "") -> SynergyProfile:
        """Compute all 7 metrics and return a SynergyProfile."""
        return SynergyProfile(
            pair_name=pair_name,
            mutual_information=self.mutual_information(x, y),
            transfer_entropy=self.transfer_entropy(x, y),
            phase_locking_value=self.phase_locking_value(x, y),
            spectral_coherence=self.spectral_coherence(x, y),
            emergence_index=self.emergence_index(x, y),
            integration_index=self.integration_index(x, y),
            complexity_resonance=self.complexity_resonance(x, y),
        )


class DiscoverySynergyAnalyzer:
    """
    Wraps SynergyMetrics for MemPalace-AGI discovery domain pairs.
    
    After each OODA cycle, call ``record_cycle()`` with per-domain discovery
    counts. Once enough data has accumulated (≥ ``min_samples``), pairwise
    synergy can be computed.
    """

    def __init__(self, window_size: int = 500, min_samples: int = 10):
        self._metrics = SynergyMetrics()
        self._domain_series: Dict[str, List[float]] = {}
        self._window_size = window_size
        self._min_samples = min_samples

    # ── Recording ──────────────────────────────────────────────────────

    def record_cycle(self, domain_counts: Dict[str, int]) -> None:
        """After each OODA cycle, record per-domain discovery counts.
        
        Args:
            domain_counts: e.g. {"astrophysics": 3, "climate": 1, "economics": 0}
        """
        for domain, count in domain_counts.items():
            if domain not in self._domain_series:
                self._domain_series[domain] = []
            series = self._domain_series[domain]
            series.append(float(count))
            # Trim to window
            if len(series) > self._window_size:
                self._domain_series[domain] = series[-self._window_size:]

    @property
    def domains(self) -> List[str]:
        """Currently tracked domains."""
        return sorted(self._domain_series.keys())

    @property
    def sample_count(self) -> int:
        """Number of cycles recorded (min across domains)."""
        if not self._domain_series:
            return 0
        return min(len(v) for v in self._domain_series.values())

    # ── Pairwise Synergy ───────────────────────────────────────────────

    def compute_pairwise_synergy(self) -> Dict[str, SynergyProfile]:
        """Compute all 7 metrics for every domain pair.
        
        Returns:
            {pair_name: SynergyProfile} where pair_name = "domA↔domB"
        """
        result: Dict[str, SynergyProfile] = {}
        domains = self.domains
        if len(domains) < 2 or self.sample_count < self._min_samples:
            return result

        for da, db in combinations(domains, 2):
            xa = np.array(self._domain_series[da])
            xb = np.array(self._domain_series[db])
            # Align lengths
            n = min(len(xa), len(xb))
            pair_name = f"{da}↔{db}"
            result[pair_name] = self._metrics.compute_all(xa[-n:], xb[-n:], pair_name)

        return result

    # ── Transfer Entropy Matrix ────────────────────────────────────────

    def get_transfer_entropy_matrix(self) -> Dict[str, Dict[str, float]]:
        """NxN directed TE matrix. Shows which domains drive others.
        
        Returns:
            {source_domain: {target_domain: TE_value}}
        """
        domains = self.domains
        matrix: Dict[str, Dict[str, float]] = {d: {} for d in domains}
        if len(domains) < 2 or self.sample_count < self._min_samples:
            return matrix

        for da in domains:
            for db in domains:
                if da == db:
                    matrix[da][db] = 0.0
                    continue
                xa = np.array(self._domain_series[da])
                xb = np.array(self._domain_series[db])
                n = min(len(xa), len(xb))
                matrix[da][db] = self._metrics.transfer_entropy(xa[-n:], xb[-n:])

        return matrix

    # ── Top Synergies ──────────────────────────────────────────────────

    def get_top_synergies(self, n: int = 5) -> List[Tuple[str, str, float]]:
        """Top N domain pairs by integration index.
        
        Returns:
            List of (domain_a, domain_b, integration_index) sorted desc.
        """
        profiles = self.compute_pairwise_synergy()
        ranked: List[Tuple[str, str, float]] = []
        for pair_name, profile in profiles.items():
            parts = pair_name.split("↔")
            ranked.append((parts[0], parts[1], profile.integration_index))
        ranked.sort(key=lambda t: t[2], reverse=True)
        return ranked[:n]

    # ── Overall Emergence Score ────────────────────────────────────────

    def get_emergence_score(self) -> float:
        """Overall emergence: are domains producing more together than apart?
        
        Returns mean emergence_index across all pairs, or 0.0 if insufficient data.
        """
        profiles = self.compute_pairwise_synergy()
        if not profiles:
            return 0.0
        return float(np.mean([p.emergence_index for p in profiles.values()]))

    # ── Full Report ────────────────────────────────────────────────────

    def get_synergy_report(self) -> dict:
        """Full synergy report for all domain pairs."""
        profiles = self.compute_pairwise_synergy()
        te_matrix = self.get_transfer_entropy_matrix()
        top = self.get_top_synergies()
        emergence = self.get_emergence_score()

        return {
            "domains": self.domains,
            "sample_count": self.sample_count,
            "pairwise": {
                name: {
                    "mutual_information": p.mutual_information,
                    "transfer_entropy": p.transfer_entropy,
                    "phase_locking_value": p.phase_locking_value,
                    "spectral_coherence": p.spectral_coherence,
                    "emergence_index": p.emergence_index,
                    "integration_index": p.integration_index,
                    "complexity_resonance": p.complexity_resonance,
                }
                for name, p in profiles.items()
            },
            "transfer_entropy_matrix": te_matrix,
            "top_synergies": [
                {"domain_a": a, "domain_b": b, "integration_index": ii}
                for a, b, ii in top
            ],
            "overall_emergence": emergence,
        }
