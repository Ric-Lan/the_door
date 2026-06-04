"""The law of how a doubt moves: legal transitions + what each transition produces.

Pure: no file I/O, no persistence. The store loads/saves DoubtRecords and applies
the plan this class returns. Single home of doubt transition policy (Mealy: the
effect is keyed on the *target state* and carries transition inputs).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from the_door.models import (
    DoubtTerminalError,
    InvalidTransitionError,
    Resolution,
    StateTransition,
)


@dataclass(frozen=True)
class TransitionPlan:
    """What a single legal transition mutates. Pure value, applied by the store."""
    transition: StateTransition
    resolution: Resolution | None
    assigned_to: str | None
    set_assigned_to: bool


class DoubtLifecycle:
    """Maps (from_state, target_state, inputs) -> a TransitionPlan, or raises."""

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "discovered": {"investigating", "escalated"},
        "investigating": {"explained", "fixed", "escalated"},
        "escalated": {"explained", "fixed", "accepted_risk"},
        "explained": set(),
        "fixed": set(),
        "accepted_risk": set(),
    }
    TERMINAL_STATES: set[str] = {"explained", "fixed", "accepted_risk"}
    _RESOLVING_STATES: set[str] = {"explained", "fixed", "accepted_risk"}

    def is_terminal(self, state: str) -> bool:
        return state in self.TERMINAL_STATES

    def check_transition(self, from_state: str, to_state: str, doubt_id: str) -> None:
        """Legality only. Raises DoubtTerminalError / InvalidTransitionError."""
        if from_state in self.TERMINAL_STATES:
            raise DoubtTerminalError(doubt_id, from_state)
        if to_state not in self.VALID_TRANSITIONS.get(from_state, set()):
            raise InvalidTransitionError(from_state, to_state)

    def plan(
        self,
        *,
        doubt_id: str,
        from_state: str,
        to_state: str,
        actor: str,
        reason: str | None = None,
        assignee: str | None = None,
        description: str | None = None,
    ) -> TransitionPlan:
        """Validate legality and build the effect for *to_state* (Mealy: by target).

        Effect by target (behaviour-preserving, see spec §2.2):
          - investigating          -> set assigned_to=assignee
          - escalated               -> record reason only (no resolution)
          - explained/fixed/accepted_risk -> Resolution(type=to_state, description)
        Inputs are assumed present (callers keep their own required-input guards).
        """
        self.check_transition(from_state, to_state, doubt_id)
        now = datetime.now(timezone.utc).isoformat()
        transition = StateTransition(
            from_state=from_state, to_state=to_state,
            timestamp=now, actor=actor, reason=reason,
        )
        resolution = None
        assigned_to = None
        set_assigned = False
        if to_state == "investigating":
            assigned_to = assignee
            set_assigned = True
        elif to_state in self._RESOLVING_STATES:
            resolution = Resolution(
                type=to_state, description=description or "",
                resolved_by=actor, resolved_at=now,
            )
        return TransitionPlan(transition, resolution, assigned_to, set_assigned)
