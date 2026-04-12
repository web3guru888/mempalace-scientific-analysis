"""
Tests for HypothesisSafetyChecker — formal safety constraints.

Phase 23: ASI:BUILD adoption from agi_governance/ethics/formal_verification.py.
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mempalace_agi.safety_constraints import (
    HypothesisSafetyChecker,
    SafetyConstraint,
)


@pytest.fixture
def checker():
    """Create a HypothesisSafetyChecker with default constraints."""
    return HypothesisSafetyChecker()


class TestDefaultConstraints:
    """Test the 5 built-in safety constraints."""

    def test_default_constraints_registered(self, checker):
        """5 default constraints are registered on init."""
        assert len(checker.constraints) == 5
        names = [c.name for c in checker.constraints]
        assert "already_confirmed" in names
        assert "refuted_without_evidence" in names
        assert "investigation_loop" in names
        assert "domain_fairness" in names
        assert "source_available" in names

    def test_already_confirmed_blocks(self, checker):
        """Hypothesis with confidence > 0.95 is blocked."""
        h = {"confidence": 0.99, "status": "active"}
        result = checker.check_hypothesis(h)
        assert not result["passed"]
        assert any("already_confirmed" in b for b in result["blocks"])

    def test_already_confirmed_passes(self, checker):
        """Hypothesis with confidence <= 0.95 passes."""
        h = {"confidence": 0.5, "status": "active"}
        result = checker.check_hypothesis(h)
        # No block from this specific constraint (others may still be fine)
        assert not any("already_confirmed" in b for b in result["blocks"])

    def test_already_confirmed_boundary(self, checker):
        """Hypothesis with exactly 0.95 confidence passes (<=, not <)."""
        h = {"confidence": 0.95, "status": "active"}
        result = checker.check_hypothesis(h)
        assert not any("already_confirmed" in b for b in result["blocks"])

    def test_refuted_without_evidence_blocks(self, checker):
        """Refuted hypothesis without new evidence is blocked."""
        h = {"status": "refuted", "new_evidence": False}
        result = checker.check_hypothesis(h)
        assert not result["passed"]
        assert any("refuted_without_evidence" in b for b in result["blocks"])

    def test_refuted_with_evidence_passes(self, checker):
        """Refuted hypothesis WITH new evidence passes."""
        h = {"status": "refuted", "new_evidence": True}
        result = checker.check_hypothesis(h)
        assert not any("refuted_without_evidence" in b for b in result["blocks"])

    def test_active_hypothesis_passes_refuted_check(self, checker):
        """Active (non-refuted) hypothesis passes the refuted constraint."""
        h = {"status": "active", "confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert not any("refuted_without_evidence" in b for b in result["blocks"])

    def test_investigation_loop_warns(self, checker):
        """Hypothesis investigated >5 times gets a warning."""
        h = {"investigation_count": 8, "confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert any("investigation_loop" in w for w in result["warnings"])
        # Warnings don't block
        assert "investigation_loop" not in str(result["blocks"])

    def test_investigation_loop_passes_under_limit(self, checker):
        """Hypothesis investigated <=5 times gets no warning."""
        h = {"investigation_count": 3, "confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert not any("investigation_loop" in w for w in result["warnings"])

    def test_source_unavailable_blocks(self, checker):
        """Hypothesis with unavailable source is blocked."""
        h = {"source_available": False, "required_source": "FRED", "confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert not result["passed"]
        assert any("source_available" in b for b in result["blocks"])

    def test_source_available_passes(self, checker):
        """Hypothesis with available source passes."""
        h = {"source_available": True, "confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert not any("source_available" in b for b in result["blocks"])

    def test_domain_fairness_always_passes(self, checker):
        """Domain fairness is a placeholder — always passes."""
        h = {"confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert not any("domain_fairness" in b for b in result["blocks"])


class TestCheckHypothesis:
    """Test the check_hypothesis method."""

    def test_clean_hypothesis_passes(self, checker):
        """A normal hypothesis passes all constraints."""
        h = {"confidence": 0.5, "status": "active", "investigation_count": 2}
        result = checker.check_hypothesis(h)
        assert result["passed"]
        assert result["blocks"] == []

    def test_multiple_blocks_accumulated(self, checker):
        """Multiple blocking constraints can fire simultaneously."""
        h = {"confidence": 0.99, "status": "refuted", "source_available": False}
        result = checker.check_hypothesis(h)
        assert not result["passed"]
        assert len(result["blocks"]) >= 2  # At least confirmed + refuted

    def test_details_contain_all_constraints(self, checker):
        """Details list contains one entry per constraint."""
        h = {"confidence": 0.5}
        result = checker.check_hypothesis(h)
        assert len(result["details"]) == 5  # 5 default constraints

    def test_details_have_required_fields(self, checker):
        """Each detail entry has constraint, passed, reason, severity."""
        h = {"confidence": 0.5}
        result = checker.check_hypothesis(h)
        for detail in result["details"]:
            assert "constraint" in detail
            assert "passed" in detail
            assert "reason" in detail
            assert "severity" in detail

    def test_empty_hypothesis(self, checker):
        """Empty hypothesis dict doesn't crash — uses defaults."""
        h = {}
        result = checker.check_hypothesis(h)
        # confidence defaults to 0, status defaults to None (not "refuted")
        assert isinstance(result, dict)
        assert "passed" in result


class TestCheckBatch:
    """Test batch hypothesis checking."""

    def test_batch_filters_blocked(self, checker):
        """check_batch returns only hypotheses passing all blocking constraints."""
        hypotheses = [
            {"id": "H1", "confidence": 0.5, "status": "active"},   # passes
            {"id": "H2", "confidence": 0.99, "status": "active"},  # blocked (confirmed)
            {"id": "H3", "confidence": 0.3, "status": "active"},   # passes
            {"id": "H4", "status": "refuted"},                     # blocked (refuted)
        ]
        safe = checker.check_batch(hypotheses)
        ids = [h["id"] for h in safe]
        assert "H1" in ids
        assert "H3" in ids
        assert "H2" not in ids
        assert "H4" not in ids

    def test_batch_empty_input(self, checker):
        """Empty list returns empty list."""
        assert checker.check_batch([]) == []

    def test_batch_all_pass(self, checker):
        """When all pass, all are returned."""
        hypotheses = [
            {"id": "H1", "confidence": 0.5},
            {"id": "H2", "confidence": 0.3},
        ]
        safe = checker.check_batch(hypotheses)
        assert len(safe) == 2


class TestCustomConstraints:
    """Test adding and removing custom constraints."""

    def test_add_custom_constraint(self, checker):
        """Custom constraints can be added."""
        checker.add_constraint(SafetyConstraint(
            name="custom_test",
            description="Test custom constraint",
            check_fn=lambda h: (h.get("custom_field", 0) < 10, "custom_field too high"),
            severity="blocking",
        ))
        assert len(checker.constraints) == 6
        assert any(c.name == "custom_test" for c in checker.constraints)

    def test_custom_constraint_enforced(self, checker):
        """Custom constraints are checked during hypothesis validation."""
        checker.add_constraint(SafetyConstraint(
            name="max_cost",
            description="Investigation cost limit",
            check_fn=lambda h: (h.get("cost", 0) <= 100, f"Cost {h.get('cost', 0)} > 100"),
            severity="blocking",
        ))
        h = {"confidence": 0.5, "cost": 200}
        result = checker.check_hypothesis(h)
        assert not result["passed"]
        assert any("max_cost" in b for b in result["blocks"])

    def test_remove_constraint(self, checker):
        """Constraints can be removed by name."""
        assert checker.remove_constraint("already_confirmed")
        assert len(checker.constraints) == 4
        names = [c.name for c in checker.constraints]
        assert "already_confirmed" not in names

    def test_remove_nonexistent_returns_false(self, checker):
        """Removing a nonexistent constraint returns False."""
        assert not checker.remove_constraint("nonexistent")
        assert len(checker.constraints) == 5  # unchanged

    def test_get_stats(self, checker):
        """get_stats returns constraint summary."""
        stats = checker.get_stats()
        assert stats["total_constraints"] == 5
        assert stats["blocking"] == 3  # confirmed, refuted, source
        assert stats["warning"] == 2   # loop, fairness
        assert len(stats["constraint_names"]) == 5


class TestErrorHandling:
    """Test graceful handling of constraint errors."""

    def test_broken_constraint_doesnt_crash(self, checker):
        """A constraint that raises an exception is caught gracefully."""
        def broken_check(h):
            raise ValueError("intentional test error")

        checker.add_constraint(SafetyConstraint(
            name="broken",
            description="This always crashes",
            check_fn=broken_check,
            severity="blocking",
        ))
        h = {"confidence": 0.5}
        result = checker.check_hypothesis(h)
        # Should not raise — error is caught and added as warning
        assert any("broken" in w for w in result["warnings"])
        # The broken constraint doesn't block (error → warning)
        assert not any("broken" in b for b in result["blocks"])
