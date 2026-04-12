"""
AnalogyHypothesisBridge — Converts cross-domain structural analogies into
testable hypotheses for the OODA cycle.

The ASTRA-dev AnalogyEngine detects 33,000+ structural isomorphisms between
validated hypotheses across domains, but these analogies are never consumed by
the hypothesis generator.  This bridge closes that gap:

    AnalogyEngine.get_novel_analogies()
        → filter(similarity > threshold)
        → transform into hypothesis dicts
        → inject into the OODA cycle's hypothesis pool

Each generated hypothesis:
- Targets domain_b (the transfer target), not domain_a (the source)
- Has finding_type="analogy_transfer" for traceable metrics
- Carries a conservative confidence = structural_similarity × 0.4
- Links back to the source analogy via source_analogy_id

Experiments #43 and #44 showed cross-domain transfer is NEGATIVE without this
pipeline.  This module is the missing link.

Usage:
    from mempalace_agi.analogy_hypothesis_bridge import inject_analogy_hypotheses

    # During Orient/Update phase:
    new_hyps = inject_analogy_hypotheses(engine, theory_engine, max_new=2)
    hypothesis_pool.extend(new_hyps)
"""

import logging
from typing import List, Dict, Set, Optional, Any, Protocol, runtime_checkable

logger = logging.getLogger("mempalace_agi.analogy_bridge")


# ── Protocol definitions for loose coupling ─────────────────────────────────
# These allow the bridge to work with mock objects in tests without importing
# the full ASTRA-dev stack.


@runtime_checkable
class AnalogyLike(Protocol):
    """Structural type for Analogy objects."""
    id: str
    domain_a: str
    domain_b: str
    hypothesis_id_a: str
    hypothesis_id_b: str
    mathematical_form: str
    structural_similarity: float
    unification_proposal: str
    novel: bool


@runtime_checkable
class AnalogyEngineLike(Protocol):
    """Structural type for AnalogyEngine-compatible objects."""
    def get_novel_analogies(self) -> list: ...
    def get_all_analogies(self) -> list: ...


@runtime_checkable
class HypothesisGeneratorLike(Protocol):
    """Structural type for HypothesisGenerator-compatible objects."""
    def generate_from_discoveries(
        self, current_cycle: int, existing_names: set, max_new: int
    ) -> List[Dict]: ...


# ── Domain mapping ──────────────────────────────────────────────────────────
# Maps domain names to canonical data sources for hypothesis compatibility.

_DOMAIN_DATA_SOURCES = {
    "Astrophysics": "sdss",
    "Economics": "worldbank",
    "Climate": "noaa",
    "Epidemiology": "who",
    "Cross-Domain": "multi",
    "Cryptography": "eccp131",
    "Cosmology": "pantheon",
}


def _domain_to_source(domain: str) -> str:
    """Map domain name to its canonical data source."""
    # Try exact match first, then case-insensitive prefix match
    if domain in _DOMAIN_DATA_SOURCES:
        return _DOMAIN_DATA_SOURCES[domain]
    domain_lower = domain.lower()
    for key, source in _DOMAIN_DATA_SOURCES.items():
        if domain_lower.startswith(key.lower()):
            return source
    return "multi"


# ── AnalogyHypothesisBridge ─────────────────────────────────────────────────


class AnalogyHypothesisBridge:
    """Converts cross-domain analogies into testable transfer hypotheses.

    The bridge reads novel analogies from the AnalogyEngine, filters by
    structural similarity, and produces hypothesis dicts that are directly
    compatible with the HypothesisGenerator output format.

    Parameters
    ----------
    analogy_engine : AnalogyEngineLike
        Source of analogies (must have get_novel_analogies() method).
    similarity_threshold : float
        Minimum structural_similarity to convert an analogy into a hypothesis.
        Default 0.70 (matches AnalogyEngine's own SIMILARITY_THRESHOLD).
        NOTE: The AnalogyEngine's _structural_similarity() function produces
        discrete values; the practical max is 0.72 (form+direction+causal
        match but no exponent match). Set to 0.70 to capture these.
    confidence_multiplier : float
        Conservative multiplier: hypothesis confidence = similarity × this.
        Default 0.4 (a 0.90 similarity analogy gets 0.36 confidence).
    include_non_novel : bool
        If True, also consider non-novel (known) analogies. Default False.
    """

    def __init__(
        self,
        analogy_engine: Any,
        similarity_threshold: float = 0.70,
        confidence_multiplier: float = 0.4,
        include_non_novel: bool = False,
    ):
        self.analogy_engine = analogy_engine
        self.similarity_threshold = similarity_threshold
        self.confidence_multiplier = confidence_multiplier
        self.include_non_novel = include_non_novel

    def generate_from_analogies(
        self,
        max_new: int = 3,
        existing_names: Optional[Set[str]] = None,
    ) -> List[Dict]:
        """Generate transfer hypotheses from cross-domain analogies.

        Each hypothesis proposes testing whether a finding from domain_a
        also holds in domain_b, motivated by structural similarity.

        Parameters
        ----------
        max_new : int
            Maximum number of hypotheses to generate.
        existing_names : set of str, optional
            Hypothesis names already in the pool (for deduplication).

        Returns
        -------
        list of dict
            Hypothesis dicts compatible with HypothesisGenerator output format.
            Keys: name, domain, description, confidence, finding_type,
                  data_source, variables, source_discovery_id, source_analogy_id.
        """
        if existing_names is None:
            existing_names = set()

        # 1. Retrieve analogies
        if self.include_non_novel:
            analogies = self.analogy_engine.get_all_analogies()
        else:
            analogies = self.analogy_engine.get_novel_analogies()

        if not analogies:
            logger.debug("No analogies available for hypothesis generation")
            return []

        # 2. Filter by similarity threshold
        strong_analogies = [
            a for a in analogies
            if a.structural_similarity >= self.similarity_threshold
        ]

        if not strong_analogies:
            logger.debug(
                "No analogies above threshold %.2f (had %d total)",
                self.similarity_threshold,
                len(analogies),
            )
            return []

        # 3. Sort by similarity (highest first) for best-first selection
        strong_analogies.sort(
            key=lambda a: a.structural_similarity, reverse=True
        )

        # 4. Generate hypotheses
        hypotheses: List[Dict] = []
        seen_names: Set[str] = set(existing_names)

        for analogy in strong_analogies:
            if len(hypotheses) >= max_new:
                break

            hyp = self._analogy_to_hypothesis(analogy)

            # Deduplicate by name
            if hyp["name"] in seen_names:
                # Try alternate name with reversed direction
                alt_name = (
                    f"Analogy Transfer: {analogy.domain_b} "
                    f"{analogy.mathematical_form} → {analogy.domain_a}"
                )
                if alt_name in seen_names:
                    logger.debug("Skipping duplicate analogy hypothesis: %s", hyp["name"])
                    continue
                hyp["name"] = alt_name
                # Reverse the transfer direction
                hyp["domain"] = analogy.domain_a
                hyp["data_source"] = _domain_to_source(analogy.domain_a)

            seen_names.add(hyp["name"])
            hypotheses.append(hyp)

        logger.info(
            "Generated %d analogy-transfer hypotheses from %d novel analogies "
            "(threshold=%.2f)",
            len(hypotheses),
            len(strong_analogies),
            self.similarity_threshold,
        )
        return hypotheses

    def _analogy_to_hypothesis(self, analogy: Any) -> Dict:
        """Convert a single Analogy into a hypothesis dict.

        The hypothesis targets domain_b (the transfer destination):
        "We found X in domain_a; does it also hold in domain_b?"

        Parameters
        ----------
        analogy : Analogy-like
            Must have: id, domain_a, domain_b, mathematical_form,
            structural_similarity, unification_proposal, hypothesis_id_a,
            hypothesis_id_b.

        Returns
        -------
        dict
            Hypothesis dict with all required keys.
        """
        # Build descriptive name
        name = (
            f"Analogy Transfer: {analogy.domain_a} "
            f"{analogy.mathematical_form} → {analogy.domain_b}"
        )

        # Build description from unification proposal
        description = (
            f"Cross-domain transfer hypothesis motivated by structural analogy "
            f"(similarity={analogy.structural_similarity:.2f}). "
            f"{analogy.unification_proposal} "
            f"Test whether the {analogy.mathematical_form} pattern observed in "
            f"{analogy.domain_a} also governs {analogy.domain_b} phenomena."
        )

        # Conservative confidence: higher similarity → higher but still cautious
        confidence = round(
            analogy.structural_similarity * self.confidence_multiplier, 4
        )

        # Infer variables from the mathematical form
        variables = self._infer_variables(analogy)

        return {
            "name": name,
            "domain": analogy.domain_b,  # Target domain
            "description": description,
            "confidence": confidence,
            "finding_type": "analogy_transfer",
            "data_source": _domain_to_source(analogy.domain_b),
            "variables": variables,
            "source_discovery_id": analogy.hypothesis_id_a,  # Source hypothesis
            "source_analogy_id": analogy.id,
        }

    @staticmethod
    def _infer_variables(analogy: Any) -> List[str]:
        """Infer variable names from the analogy's mathematical form.

        Since analogies don't carry explicit variables, we derive them from
        the shared mathematical form.  These are generic but semantically
        meaningful for downstream investigation.
        """
        _form_variables = {
            "power_law": ["exponent", "amplitude", "scale"],
            "exponential": ["rate", "amplitude", "timescale"],
            "linear": ["slope", "intercept"],
            "bimodal": ["peak1", "peak2", "valley"],
            "causal_chain": ["driver", "response", "lag"],
            "periodic": ["period", "amplitude", "phase"],
            "lognormal": ["mu", "sigma"],
        }
        return _form_variables.get(analogy.mathematical_form, ["value"])


# ── Convenience integration function ────────────────────────────────────────


def inject_analogy_hypotheses(
    engine: Any,
    theory_engine: Any,
    max_new: int = 2,
    existing_names: Optional[Set[str]] = None,
    similarity_threshold: float = 0.70,
) -> List[Dict]:
    """Generate analogy-transfer hypotheses for injection into the OODA cycle.

    Convenience function for calling from the Orient or Update phase.
    Creates an AnalogyHypothesisBridge from the engine's components and
    returns hypothesis dicts ready for the pool.

    Parameters
    ----------
    engine : object
        The OODA engine (e.g., MemPalaceAGI or orchestrator).
        Not used directly; present for future integration hooks.
    theory_engine : object
        Must have an ``analogy_engine`` attribute (AnalogyEngine instance)
        or be an AnalogyEngine itself.
    max_new : int
        Maximum number of analogy-transfer hypotheses to generate.
    existing_names : set of str, optional
        Names of hypotheses already in the pool.
    similarity_threshold : float
        Minimum structural similarity for conversion.

    Returns
    -------
    list of dict
        Hypothesis dicts with finding_type="analogy_transfer".

    Examples
    --------
    >>> from mempalace_agi.analogy_hypothesis_bridge import inject_analogy_hypotheses
    >>> new_hyps = inject_analogy_hypotheses(engine, theory_engine, max_new=3)
    >>> for h in new_hyps:
    ...     print(f"{h['name']} → {h['domain']} (conf={h['confidence']:.2f})")
    """
    # Resolve the analogy source from the theory engine.
    # The TheoryEngine.tick() runs asynchronously in a daemon thread, so
    # analogy_engine._all_analogies may be empty/stale when we check during
    # the Update phase.  The TheoryEngine also maintains a stable cumulative
    # cache in _analogies (populated in _run_cycle under lock).
    # Strategy: prefer the TheoryEngine's _analogies cache (stable, cumulative)
    # then fall back to the AnalogyEngine (per-scan, may be mid-update).

    analogy_source = None

    # 1. Try TheoryEngine's cumulative cache (most reliable)
    if hasattr(theory_engine, "_analogies") and theory_engine._analogies:
        # Wrap the cache as an AnalogyEngine-like object
        class _CachedAnalogySource:
            """Reads from TheoryEngine's stable cumulative analogy cache."""
            def __init__(self, analogies):
                self._analogies = list(analogies)
            def get_all_analogies(self):
                return self._analogies
            def get_novel_analogies(self):
                return [a for a in self._analogies if getattr(a, 'novel', False)]

        analogy_source = _CachedAnalogySource(theory_engine._analogies)
        logger.debug(
            "Using TheoryEngine._analogies cache (%d total)",
            len(theory_engine._analogies),
        )

    # 2. Fall back to analogy_engine directly
    elif hasattr(theory_engine, "analogy_engine") and theory_engine.analogy_engine:
        analogy_source = theory_engine.analogy_engine
        logger.debug("Using theory_engine.analogy_engine directly")

    # 3. Theory engine IS the analogy engine
    elif hasattr(theory_engine, "get_novel_analogies"):
        analogy_source = theory_engine
        logger.debug("theory_engine is the analogy engine")

    else:
        logger.warning(
            "theory_engine has no _analogies cache, no analogy_engine attribute, "
            "and no get_novel_analogies method — cannot generate analogy hypotheses"
        )
        return []

    bridge = AnalogyHypothesisBridge(
        analogy_engine=analogy_source,
        similarity_threshold=similarity_threshold,
    )

    return bridge.generate_from_analogies(
        max_new=max_new,
        existing_names=existing_names or set(),
    )
