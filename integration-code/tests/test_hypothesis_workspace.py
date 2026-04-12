"""Tests for hypothesis_workspace — Global Workspace Theory for hypothesis selection."""

import math
import time

import pytest

from mempalace_agi.hypothesis_workspace import (
    DomainSpecialistProxy,
    HypothesisWorkspace,
    WorkspaceItem,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_item(
    hid: str = "H001",
    content: str = "test hypothesis",
    domain: str = "astrophysics",
    activation: float = 0.5,
    broadcast_count: int = 0,
    created_at: float | None = None,
    coalition: set | None = None,
) -> WorkspaceItem:
    item = WorkspaceItem(
        hypothesis_id=hid,
        content=content,
        domain=domain,
        activation=activation,
        broadcast_count=broadcast_count,
    )
    if created_at is not None:
        item.created_at = created_at
    if coalition is not None:
        item.coalition = coalition
    return item


# ===================================================================
# WorkspaceItem.calculate_strength
# ===================================================================

class TestWorkspaceItemStrength:
    """Test 13: WorkspaceItem.calculate_strength basic math."""

    def test_fresh_item_strength(self):
        """A freshly created item has strength ≈ activation (decay ≈ 1)."""
        item = _make_item(activation=0.7)
        strength = item.calculate_strength()
        # Just created so decay ≈ 1.0, no coalition, novelty 0.0
        assert 0.65 < strength <= 0.7

    def test_coalition_increases_strength(self):
        """Adding coalition members increases strength."""
        item = _make_item(activation=0.5, coalition={"astro", "econ"})
        strength = item.calculate_strength(coalition_weight=0.15)
        # 2 members × 0.15 = 0.30 bonus → (0.5 + 0.30 − 0) × ≈1.0
        assert strength > 0.7

    def test_time_decay_reduces_strength(self):
        """Test 11: time_decay reduces strength for old items."""
        old_time = time.time() - 600  # 10 minutes ago
        item = _make_item(activation=0.8, created_at=old_time)
        strength = item.calculate_strength(time_decay_rate=0.005)
        expected_decay = math.exp(-600 * 0.005)  # ≈ 0.0498
        assert strength == pytest.approx(0.8 * expected_decay, abs=0.01)

    def test_broadcast_penalty_reduces_strength(self):
        """Test 12: broadcast_count penalty reduces strength."""
        item = _make_item(activation=0.5, broadcast_count=5)
        strength = item.calculate_strength()
        # penalty = 0.02 × 5 = 0.10, so raw ≈ (0.5 − 0.10) × ≈1.0 = 0.40
        assert strength < 0.45

    def test_strength_never_negative(self):
        """Strength is clamped to >= 0."""
        old_time = time.time() - 10000
        item = _make_item(activation=0.01, broadcast_count=10, created_at=old_time)
        strength = item.calculate_strength(time_decay_rate=0.01)
        assert strength >= 0.0

    def test_strength_stored_on_item(self):
        """calculate_strength updates item.competition_strength."""
        item = _make_item(activation=0.6)
        result = item.calculate_strength()
        assert item.competition_strength == result


# ===================================================================
# DomainSpecialistProxy
# ===================================================================

class TestDomainSpecialistProxy:
    """Tests 14 & 15: DomainSpecialistProxy default and custom evaluate."""

    def test_default_evaluate_same_domain(self):
        """Test 14a: Default evaluate returns 0.8 for same-domain item."""
        specialist = DomainSpecialistProxy(domain="astrophysics")
        item = _make_item(domain="astrophysics")
        assert specialist.evaluate(item) == 0.8

    def test_default_evaluate_different_domain(self):
        """Test 14b: Default evaluate returns 0.2 for cross-domain item."""
        specialist = DomainSpecialistProxy(domain="economics")
        item = _make_item(domain="astrophysics")
        assert specialist.evaluate(item) == 0.2

    def test_custom_evaluate_fn(self):
        """Test 15: Custom evaluate_fn overrides default behaviour."""
        specialist = DomainSpecialistProxy(
            domain="astrophysics",
            evaluate_fn=lambda item: 0.95 if "dark matter" in item.content else 0.1,
        )
        dark = _make_item(content="dark matter hypothesis")
        other = _make_item(content="inflation rate")
        assert specialist.evaluate(dark) == 0.95
        assert specialist.evaluate(other) == 0.1


# ===================================================================
# HypothesisWorkspace — Submission
# ===================================================================

class TestSubmission:
    """Tests 1–3: submit, dedup, and capacity eviction."""

    def test_submit_creates_item(self):
        """Test 1: submit_hypothesis creates a WorkspaceItem in the workspace."""
        ws = HypothesisWorkspace()
        item = ws.submit_hypothesis("H001", "test hyp", "astro", activation=0.6)
        assert isinstance(item, WorkspaceItem)
        assert item.hypothesis_id == "H001"
        assert item.activation == 0.6
        assert ws.workspace_size == 1

    def test_submit_deduplicates_by_id(self):
        """Test 2: submit_hypothesis deduplicates by id, updates activation."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H001", "test hyp", "astro", activation=0.3)
        item2 = ws.submit_hypothesis("H001", "test hyp v2", "astro", activation=0.7)
        assert ws.workspace_size == 1  # no duplicate
        assert item2.activation == 0.7  # updated to max

    def test_dedup_keeps_higher_activation(self):
        """Dedup keeps the higher of old and new activation."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H001", "test", "astro", activation=0.9)
        item = ws.submit_hypothesis("H001", "test", "astro", activation=0.3)
        assert item.activation == 0.9  # original was higher

    def test_capacity_eviction(self):
        """Test 3: Capacity eviction — weakest item is removed."""
        ws = HypothesisWorkspace(capacity=3)
        ws.submit_hypothesis("H1", "a", "astro", activation=0.9)
        ws.submit_hypothesis("H2", "b", "astro", activation=0.8)
        ws.submit_hypothesis("H3", "c", "astro", activation=0.7)
        ws.submit_hypothesis("H4", "d", "astro", activation=0.6)
        assert ws.workspace_size == 3
        # The lowest-activation item should have been evicted
        ids = [item.hypothesis_id for item in ws._workspace]
        assert "H4" not in ids  # H4 has lowest strength (activation 0.6)


# ===================================================================
# HypothesisWorkspace — Competition
# ===================================================================

class TestCompetition:
    """Tests 4–7: run_competition variants."""

    def test_competition_returns_winner(self):
        """Test 4: run_competition returns the winning item."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "low", "astro", activation=0.3)
        ws.submit_hypothesis("H2", "high", "astro", activation=0.9)
        winner = ws.run_competition()
        assert winner is not None
        assert winner.hypothesis_id == "H2"

    def test_competition_empty_workspace(self):
        """Test 5: run_competition on empty workspace returns None."""
        ws = HypothesisWorkspace()
        assert ws.run_competition() is None

    def test_competition_removes_winner(self):
        """Test 6: Winner is removed from the workspace after broadcast."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.5)
        ws.submit_hypothesis("H2", "b", "astro", activation=0.9)
        winner = ws.run_competition()
        assert winner.hypothesis_id == "H2"
        ids = [item.hypothesis_id for item in ws._workspace]
        assert "H2" not in ids
        assert ws.workspace_size == 1

    def test_competition_adds_to_history(self):
        """Test 7: Winner is appended to broadcast_history."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        winner = ws.run_competition()
        history = ws.get_broadcast_history()
        assert len(history) == 1
        assert history[0].hypothesis_id == winner.hypothesis_id

    def test_winner_broadcast_count_incremented(self):
        """Winner's broadcast_count is incremented."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        winner = ws.run_competition()
        assert winner.broadcast_count == 1

    def test_selection_threshold_blocks_weak_items(self):
        """Test 20: Low-strength items below threshold don't win."""
        ws = HypothesisWorkspace(selection_threshold=0.9)
        ws.submit_hypothesis("H1", "a", "astro", activation=0.1)
        result = ws.run_competition()
        assert result is None  # strength too low to pass threshold
        assert ws.workspace_size == 1  # item not removed


# ===================================================================
# HypothesisWorkspace — Specialists & Coalition
# ===================================================================

class TestSpecialistsCoalition:
    """Tests 8–10: register, unregister, coalition strength boost."""

    def test_register_specialist(self):
        """Test 8: register_specialist adds specialist and forms coalitions."""
        ws = HypothesisWorkspace()
        ws.register_specialist("astrophysics")
        ws.register_specialist("economics")
        ws.submit_hypothesis("H1", "dark energy", "astrophysics", activation=0.5)
        # Run competition to trigger coalition formation
        winner = ws.run_competition()
        assert winner is not None
        # Astrophysics specialist should have joined (0.8 >= 0.3 threshold)
        # Economics specialist gives 0.2 < 0.3, so it won't join
        assert "astrophysics" in winner.coalition
        assert "economics" not in winner.coalition

    def test_unregister_specialist(self):
        """Test 9: unregister_specialist removes specialist."""
        ws = HypothesisWorkspace()
        ws.register_specialist("astrophysics")
        ws.unregister_specialist("astrophysics")
        assert "astrophysics" not in ws._specialists

    def test_unregister_nonexistent_is_noop(self):
        """Unregistering a specialist that doesn't exist is a no-op."""
        ws = HypothesisWorkspace()
        ws.unregister_specialist("nonexistent")  # should not raise

    def test_coalition_increases_strength(self):
        """Test 10: Coalition membership increases competition strength."""
        ws = HypothesisWorkspace()

        # Item without specialists
        item_alone = _make_item(activation=0.5)
        strength_alone = item_alone.calculate_strength(coalition_weight=0.15)

        # Item with coalition of 3
        item_supported = _make_item(activation=0.5, coalition={"a", "b", "c"})
        strength_supported = item_supported.calculate_strength(coalition_weight=0.15)

        assert strength_supported > strength_alone

    def test_register_specialist_with_custom_proxy(self):
        """register_specialist accepts a custom DomainSpecialistProxy."""
        ws = HypothesisWorkspace()
        proxy = DomainSpecialistProxy(
            domain="climate",
            evaluate_fn=lambda item: 1.0,  # Always fully supports
        )
        ws.register_specialist("climate", specialist=proxy)
        ws.submit_hypothesis("H1", "warming", "economics", activation=0.5)
        winner = ws.run_competition()
        assert "climate" in winner.coalition


# ===================================================================
# HypothesisWorkspace — Querying & State
# ===================================================================

class TestQueryingAndState:
    """Tests 16–19: get_workspace_state, broadcast_history, status, clear."""

    def test_get_workspace_state_sorted_by_strength(self):
        """Test 16: get_workspace_state returns items sorted desc by strength."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H_low", "low", "astro", activation=0.2)
        ws.submit_hypothesis("H_mid", "mid", "astro", activation=0.5)
        ws.submit_hypothesis("H_high", "high", "astro", activation=0.9)
        state = ws.get_workspace_state()
        ids = [item.hypothesis_id for item in state]
        assert ids == ["H_high", "H_mid", "H_low"]

    def test_get_broadcast_history(self):
        """Test 17: get_broadcast_history returns list of past winners."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.9)
        ws.submit_hypothesis("H2", "b", "astro", activation=0.8)
        ws.run_competition()  # H1 wins
        ws.run_competition()  # H2 wins
        history = ws.get_broadcast_history()
        assert len(history) == 2
        assert history[0].hypothesis_id == "H1"
        assert history[1].hypothesis_id == "H2"

    def test_broadcast_history_is_copy(self):
        """get_broadcast_history returns a copy, not the internal list."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        ws.run_competition()
        history = ws.get_broadcast_history()
        history.clear()
        assert ws.total_broadcasts == 1  # Internal list unaffected

    def test_get_status_structure(self):
        """Test 18: get_status returns correct dict structure."""
        ws = HypothesisWorkspace(capacity=5)
        ws.register_specialist("astrophysics")
        ws.submit_hypothesis("H1", "test", "astrophysics", activation=0.6)
        status = ws.get_status()
        assert status["workspace_size"] == 1
        assert status["capacity"] == 5
        assert "astrophysics" in status["specialists"]
        assert status["total_broadcasts"] == 0
        assert len(status["workspace_items"]) == 1
        item_info = status["workspace_items"][0]
        assert "hypothesis_id" in item_info
        assert "domain" in item_info
        assert "activation" in item_info
        assert "strength" in item_info
        assert "coalition_size" in item_info
        assert "broadcast_count" in item_info

    def test_clear_resets_everything(self):
        """Test 19: clear() empties workspace and broadcast history."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        ws.run_competition()
        assert ws.total_broadcasts == 1
        assert ws.workspace_size == 0
        ws.submit_hypothesis("H2", "b", "astro", activation=0.7)
        ws.clear()
        assert ws.workspace_size == 0
        assert ws.total_broadcasts == 0
        assert ws.get_broadcast_history() == []

    def test_workspace_size_property(self):
        """workspace_size returns correct count."""
        ws = HypothesisWorkspace()
        assert ws.workspace_size == 0
        ws.submit_hypothesis("H1", "a", "astro")
        assert ws.workspace_size == 1
        ws.submit_hypothesis("H2", "b", "astro")
        assert ws.workspace_size == 2

    def test_total_broadcasts_property(self):
        """total_broadcasts increments with each competition win."""
        ws = HypothesisWorkspace()
        assert ws.total_broadcasts == 0
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        ws.run_competition()
        assert ws.total_broadcasts == 1


# ===================================================================
# Integration / Edge Cases
# ===================================================================

class TestEdgeCases:
    """Additional edge cases and integration scenarios."""

    def test_activation_clamped(self):
        """Activation is clamped to [0, 1]."""
        ws = HypothesisWorkspace()
        item = ws.submit_hypothesis("H1", "a", "astro", activation=2.5)
        assert item.activation == 1.0
        item2 = ws.submit_hypothesis("H2", "b", "astro", activation=-0.5)
        assert item2.activation == 0.0

    def test_multiple_competition_rounds(self):
        """Multiple successive competitions deplete the workspace."""
        ws = HypothesisWorkspace()
        for i in range(5):
            ws.submit_hypothesis(f"H{i}", f"hyp {i}", "astro", activation=0.5 + 0.1 * i)
        winners = []
        for _ in range(5):
            w = ws.run_competition()
            if w is None:
                break
            winners.append(w)
        assert len(winners) == 5
        assert ws.workspace_size == 0

    def test_resubmit_after_broadcast(self):
        """A hypothesis that was broadcast can be resubmitted."""
        ws = HypothesisWorkspace()
        ws.submit_hypothesis("H1", "a", "astro", activation=0.8)
        winner = ws.run_competition()
        assert winner.hypothesis_id == "H1"
        assert ws.workspace_size == 0
        # Resubmit
        item = ws.submit_hypothesis("H1", "a revised", "astro", activation=0.9)
        assert ws.workspace_size == 1
        assert item.hypothesis_id == "H1"
