"""
safety_constraints.py — Formal safety constraints for hypothesis investigation.

Inspired by ASI:BUILD agi_governance/ethics/formal_verification.py.
That system uses SymPy for full theorem proving over ethical predicates.
Our version is lighter: empirical constraints (not logical axioms) that
validate hypotheses before committing investigation resources.

Phase 23: Initial implementation with 5 default constraints.
"""

import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Tuple

logger = logging.getLogger("mempalace_agi")


@dataclass
class SafetyConstraint:
    """A constraint that hypotheses must satisfy before investigation.

    Attributes:
        name:        Short identifier for the constraint.
        description: Human-readable explanation.
        check_fn:    Callable that takes a hypothesis dict and returns
                     ``(passed: bool, reason: str)``.
        severity:    ``"warning"`` (log only) or ``"blocking"`` (prevents investigation).
    """
    name: str
    description: str
    check_fn: Callable[[dict], Tuple[bool, str]]
    severity: str = "warning"  # "warning" or "blocking"


class HypothesisSafetyChecker:
    """Validates hypotheses against safety constraints before investigation.

    Inspired by ASI:BUILD formal_verification.py, but simplified for our use case.
    We don't need SymPy theorem proving — our constraints are empirical, not logical.

    Usage::

        checker = HypothesisSafetyChecker()
        result = checker.check_hypothesis({"confidence": 0.99, "status": "active"})
        if not result["passed"]:
            print("Blocked:", result["blocks"])

        # Batch filter — returns only hypotheses passing all blocking constraints
        safe = checker.check_batch(hypothesis_list)
    """

    def __init__(self):
        self._constraints: List[SafetyConstraint] = []
        self._register_default_constraints()

    def _register_default_constraints(self):
        """Register built-in safety constraints."""

        # 1. No investigation of hypotheses with confidence > 0.95 (already confirmed)
        self.add_constraint(SafetyConstraint(
            name="already_confirmed",
            description="Skip hypotheses that are already confirmed (confidence > 0.95)",
            check_fn=lambda h: (
                h.get("confidence", 0) <= 0.95,
                f"Confidence {h.get('confidence', 0):.2f} > 0.95",
            ),
            severity="blocking",
        ))

        # 2. No investigation of refuted hypotheses without new evidence
        self.add_constraint(SafetyConstraint(
            name="refuted_without_evidence",
            description="Don't reinvestigate refuted hypotheses without new evidence",
            check_fn=lambda h: (
                h.get("status") != "refuted" or h.get("new_evidence", False),
                "Refuted without new evidence",
            ),
            severity="blocking",
        ))

        # 3. Warn if hypothesis has been investigated > 5 times without progress
        self.add_constraint(SafetyConstraint(
            name="investigation_loop",
            description="Warn if hypothesis investigated >5 times without confidence change",
            check_fn=lambda h: (
                h.get("investigation_count", 0) <= 5,
                f"Investigated {h.get('investigation_count', 0)} times without progress",
            ),
            severity="warning",
        ))

        # 4. Resource budget: don't let one domain consume >40% of investigations
        #    (Needs cycle context — placeholder that always passes; checked at
        #    orchestrator level with full cycle data.)
        self.add_constraint(SafetyConstraint(
            name="domain_fairness",
            description="No single domain should consume >40% of investigation budget",
            check_fn=lambda h: (True, ""),
            severity="warning",
        ))

        # 5. Data source availability: don't investigate if required source is offline
        self.add_constraint(SafetyConstraint(
            name="source_available",
            description="Required data source must be accessible",
            check_fn=lambda h: (
                h.get("source_available", True),
                f"Data source '{h.get('required_source', '?')}' unavailable",
            ),
            severity="blocking",
        ))

    @property
    def constraints(self) -> List[SafetyConstraint]:
        """Read-only access to registered constraints."""
        return list(self._constraints)

    def add_constraint(self, constraint: SafetyConstraint):
        """Register a new safety constraint."""
        self._constraints.append(constraint)

    def remove_constraint(self, name: str) -> bool:
        """Remove a constraint by name. Returns True if found and removed."""
        before = len(self._constraints)
        self._constraints = [c for c in self._constraints if c.name != name]
        return len(self._constraints) < before

    def check_hypothesis(self, hypothesis: dict) -> dict:
        """Check all constraints against a single hypothesis.

        Returns::

            {
                "passed": bool,       # True if all blocking constraints pass
                "warnings": [str],    # Warning messages
                "blocks": [str],      # Blocking failure messages
                "details": [          # Per-constraint detail
                    {
                        "constraint": str,
                        "passed": bool,
                        "reason": str,
                        "severity": str,
                    },
                    ...
                ],
            }
        """
        result: Dict[str, Any] = {
            "passed": True,
            "warnings": [],
            "blocks": [],
            "details": [],
        }

        for constraint in self._constraints:
            try:
                passed, reason = constraint.check_fn(hypothesis)
                detail = {
                    "constraint": constraint.name,
                    "passed": passed,
                    "reason": reason,
                    "severity": constraint.severity,
                }
                result["details"].append(detail)

                if not passed:
                    if constraint.severity == "blocking":
                        result["blocks"].append(f"{constraint.name}: {reason}")
                        result["passed"] = False
                    else:
                        result["warnings"].append(f"{constraint.name}: {reason}")
            except Exception as e:
                logger.warning("Constraint %s failed: %s", constraint.name, e)
                result["warnings"].append(f"{constraint.name}: check failed ({e})")

        return result

    def check_batch(self, hypotheses: List[dict]) -> List[dict]:
        """Check multiple hypotheses, return only those passing all blocking constraints."""
        return [h for h in hypotheses if self.check_hypothesis(h)["passed"]]

    def get_stats(self) -> dict:
        """Return summary of registered constraints."""
        blocking = sum(1 for c in self._constraints if c.severity == "blocking")
        warning = sum(1 for c in self._constraints if c.severity == "warning")
        return {
            "total_constraints": len(self._constraints),
            "blocking": blocking,
            "warning": warning,
            "constraint_names": [c.name for c in self._constraints],
        }
