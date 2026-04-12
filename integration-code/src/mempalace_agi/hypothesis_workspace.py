"""
Hypothesis Workspace — Global Workspace Theory for Hypothesis Selection.

Implements a competition-coalition-broadcast mechanism for selecting which
hypothesis to investigate next. Hypotheses compete for "workspace attention"
based on activation (urgency), coalition support (domain specialists that
endorse it), novelty, and recency.

Adapted from ASI:BUILD (https://gitlab.com/asi-build/asi-build), MIT License.
Original: consciousness_engine/global_workspace.py
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("mempalace_agi")


@dataclass
class WorkspaceItem:
    """A hypothesis competing for investigation attention."""

    hypothesis_id: str
    content: str
    domain: str
    activation: float = 0.5  # priority/urgency  [0, 1]
    coalition: Set[str] = field(default_factory=set)
    competition_strength: float = 0.0
    broadcast_count: int = 0
    created_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def calculate_strength(
        self,
        coalition_weight: float = 0.15,
        novelty_bonus: float = 0.0,
        time_decay_rate: float = 0.005,
    ) -> float:
        """Competition strength = activation + coalition bonus + novelty − time decay.

        The ASI:BUILD original uses ``coalition_strength = len(coalition) * 0.1``
        and ``time_decay = exp(−(now − created) * 0.01)``. We add novelty and
        make the weights configurable.
        """
        coalition_bonus = len(self.coalition) * coalition_weight
        time_elapsed = time.time() - self.created_at
        decay = math.exp(-time_elapsed * time_decay_rate)
        # Penalise hypotheses that have been selected many times
        broadcast_penalty = 0.02 * self.broadcast_count
        raw = (self.activation + coalition_bonus + novelty_bonus - broadcast_penalty) * decay
        self.competition_strength = max(0.0, raw)
        return self.competition_strength


@dataclass
class DomainSpecialistProxy:
    """Lightweight stand-in for a domain specialist that can evaluate hypotheses.

    In the orchestrator, real DomainSpecialist objects will be wrapped in this.
    """

    domain: str
    evaluate_fn: Optional[Callable[[WorkspaceItem], float]] = None

    def evaluate(self, item: WorkspaceItem) -> float:
        """Return support score [0, 1] for the given workspace item.

        Default heuristic: 0.8 if same domain, 0.2 for cross-domain.
        """
        if self.evaluate_fn:
            return self.evaluate_fn(item)
        return 0.8 if item.domain == self.domain else 0.2


class HypothesisWorkspace:
    """
    Global Workspace for hypothesis selection.

    Capacity-limited buffer (default 7 — the magical number). Hypotheses
    compete in rounds where specialists form coalitions, strength is
    calculated, and the winner is "broadcast" (selected for investigation).

    Ported from ASI:BUILD's GlobalWorkspaceTheory, decoupled from
    BaseConsciousness and threading locks (our orchestrator is single-threaded).
    """

    def __init__(
        self,
        capacity: int = 7,
        competition_rounds: int = 3,
        selection_threshold: float = 0.1,
        coalition_support_threshold: float = 0.3,
    ):
        self._workspace: List[WorkspaceItem] = []
        self._capacity = capacity
        self._competition_rounds = competition_rounds
        self._selection_threshold = selection_threshold
        self._coalition_support_threshold = coalition_support_threshold

        self._specialists: Dict[str, DomainSpecialistProxy] = {}
        self._broadcast_history: List[WorkspaceItem] = []

    # ── Specialist Registration ────────────────────────────────────────

    def register_specialist(
        self,
        domain: str,
        specialist: Optional[DomainSpecialistProxy] = None,
    ) -> None:
        """Register a domain specialist that can form coalitions.

        Args:
            domain: Domain name (e.g. "astrophysics").
            specialist: Proxy object. If None, a default one is created.
        """
        if specialist is None:
            specialist = DomainSpecialistProxy(domain=domain)
        self._specialists[domain] = specialist

    def unregister_specialist(self, domain: str) -> None:
        """Remove a specialist."""
        self._specialists.pop(domain, None)

    # ── Submission ─────────────────────────────────────────────────────

    def submit_hypothesis(
        self,
        hypothesis_id: str,
        content: str,
        domain: str,
        activation: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> WorkspaceItem:
        """Submit a hypothesis to compete for workspace attention.

        If the workspace is at capacity, the weakest item is evicted.

        Returns:
            The WorkspaceItem created (or the existing one if already present).
        """
        # Deduplicate by hypothesis_id
        for existing in self._workspace:
            if existing.hypothesis_id == hypothesis_id:
                # Update activation if higher
                existing.activation = max(existing.activation, activation)
                return existing

        item = WorkspaceItem(
            hypothesis_id=hypothesis_id,
            content=content,
            domain=domain,
            activation=max(0.0, min(1.0, float(activation))),
            metadata=metadata or {},
        )
        self._workspace.append(item)

        # Enforce capacity
        if len(self._workspace) > self._capacity:
            # Evict weakest
            self._workspace.sort(key=lambda w: w.calculate_strength())
            evicted = self._workspace.pop(0)
            logger.debug("Evicted hypothesis %s (strength %.3f)",
                         evicted.hypothesis_id, evicted.competition_strength)

        return item

    # ── Competition ────────────────────────────────────────────────────

    def run_competition(self) -> Optional[WorkspaceItem]:
        """Run competition rounds and broadcast (select) the winner.

        1. Each specialist reviews workspace items, adds support (coalition).
        2. Items calculate strength = activation + coalition_bonus + novelty − time_decay.
        3. Top item wins, gets broadcast.

        Returns:
            The winning WorkspaceItem, or None if workspace is empty or
            no item exceeds the selection threshold.
        """
        if not self._workspace:
            return None

        for _round in range(self._competition_rounds):
            # Coalition formation
            for item in self._workspace:
                item.coalition.clear()
                for domain, specialist in self._specialists.items():
                    support = specialist.evaluate(item)
                    if support >= self._coalition_support_threshold:
                        item.coalition.add(domain)

                # Calculate novelty: inverse of broadcast_count
                novelty = 0.1 / (1 + item.broadcast_count)
                item.calculate_strength(novelty_bonus=novelty)

        # Select winner
        self._workspace.sort(key=lambda w: w.competition_strength, reverse=True)
        winner = self._workspace[0]

        if winner.competition_strength < self._selection_threshold:
            logger.debug("No hypothesis passed threshold (best: %.3f < %.3f)",
                         winner.competition_strength, self._selection_threshold)
            return None

        # Broadcast: record and remove from workspace
        winner.broadcast_count += 1
        self._broadcast_history.append(winner)
        self._workspace.remove(winner)

        logger.info("Hypothesis %s won competition (strength=%.3f, coalition=%s)",
                     winner.hypothesis_id, winner.competition_strength,
                     sorted(winner.coalition))

        return winner

    # ── Querying ───────────────────────────────────────────────────────

    def get_workspace_state(self) -> List[WorkspaceItem]:
        """Current workspace contents sorted by strength (desc)."""
        for item in self._workspace:
            item.calculate_strength()
        return sorted(self._workspace, key=lambda w: w.competition_strength, reverse=True)

    def get_broadcast_history(self) -> List[WorkspaceItem]:
        """All previously broadcast (selected) hypotheses."""
        return list(self._broadcast_history)

    @property
    def workspace_size(self) -> int:
        return len(self._workspace)

    @property
    def total_broadcasts(self) -> int:
        return len(self._broadcast_history)

    def clear(self) -> None:
        """Clear workspace and history."""
        self._workspace.clear()
        self._broadcast_history.clear()

    def get_status(self) -> dict:
        """Summary status."""
        return {
            "workspace_size": self.workspace_size,
            "capacity": self._capacity,
            "specialists": sorted(self._specialists.keys()),
            "total_broadcasts": self.total_broadcasts,
            "workspace_items": [
                {
                    "hypothesis_id": item.hypothesis_id,
                    "domain": item.domain,
                    "activation": item.activation,
                    "strength": item.competition_strength,
                    "coalition_size": len(item.coalition),
                    "broadcast_count": item.broadcast_count,
                }
                for item in self.get_workspace_state()
            ],
        }

