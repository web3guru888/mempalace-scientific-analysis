"""
RetrievalProfile — Formalizes retrieval parameter sets for different OODA phases.

Different OODA phases need different retrieval behavior:
- Orient: wide breadth, low similarity threshold, cross-domain
- Evaluate: tight precision, high similarity, domain-focused
- Decide: recency-biased, authoritative sources only

Rather than magic numbers scattered through the code, we define named
profiles that can be composed and overridden.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class RetrievalProfile:
    """Named set of retrieval parameters for a specific OODA phase.

    Attributes:
        name:            Human-readable profile identifier.
        n_results:       Maximum number of results to return.
        min_similarity:  Minimum cosine similarity threshold (0–1).
        time_decay:      Whether to apply recency weighting.
        half_life_days:  Decay half-life in days (None = no decay).
        exclude_domain:  Whether to exclude the current domain from results.
        require_status:  Required record status (None = any).
        use_kg_paths:    Whether to search KG for causal chains between
                         cross-domain discoveries and current domain.
        description:     Human-readable description of this profile's purpose.
    """

    name: str
    n_results: int
    min_similarity: float
    time_decay: bool
    half_life_days: Optional[int]
    exclude_domain: bool
    require_status: Optional[str]
    use_kg_paths: bool = False
    description: str = ""


# ── Standard Profiles ───────────────────────────────────────────────

ORIENT_BREADTH = RetrievalProfile(
    name="orient_breadth",
    n_results=16,
    min_similarity=0.2,
    time_decay=False,
    half_life_days=None,
    exclude_domain=False,
    require_status=None,
    use_kg_paths=True,
    description="Wide cast for cross-domain pattern discovery during Orient phase",
)

EVALUATE_PRECISION = RetrievalProfile(
    name="evaluate_precision",
    n_results=8,
    min_similarity=0.6,
    time_decay=False,
    half_life_days=None,
    exclude_domain=True,
    require_status="decided",
    description="Tight semantic match for hypothesis validation during Evaluate phase",
)

DECIDE_RECENCY = RetrievalProfile(
    name="decide_recency",
    n_results=5,
    min_similarity=0.4,
    time_decay=True,
    half_life_days=30,
    exclude_domain=False,
    require_status="decided",
    description="Recent authoritative decisions for the Decide phase",
)

# Registry for lookup by name
_PROFILE_REGISTRY: dict[str, RetrievalProfile] = {
    "orient_breadth": ORIENT_BREADTH,
    "evaluate_precision": EVALUATE_PRECISION,
    "decide_recency": DECIDE_RECENCY,
}


def get_profile(name: str) -> RetrievalProfile:
    """Look up a standard profile by name.

    Raises ValueError if the name is not recognized.
    """
    if name not in _PROFILE_REGISTRY:
        available = ", ".join(sorted(_PROFILE_REGISTRY))
        raise ValueError(f"Unknown profile {name!r}. Available: {available}")
    return _PROFILE_REGISTRY[name]


def compose(
    profile: RetrievalProfile,
    **overrides,
) -> RetrievalProfile:
    """Create a modified copy of *profile* with the given field overrides.

    Example::

        custom = compose(ORIENT_BREADTH, n_results=20, min_similarity=0.15)
    """
    fields = {
        "name": profile.name,
        "n_results": profile.n_results,
        "min_similarity": profile.min_similarity,
        "time_decay": profile.time_decay,
        "half_life_days": profile.half_life_days,
        "exclude_domain": profile.exclude_domain,
        "require_status": profile.require_status,
        "use_kg_paths": profile.use_kg_paths,
        "description": profile.description,
    }
    fields.update(overrides)
    return RetrievalProfile(**fields)
