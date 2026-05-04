from enum import Enum


class Status(str, Enum):
    OPEN          = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RESOLVED      = "RESOLVED"
    CLOSED        = "CLOSED"


# Valid forward transitions only — no skipping, no going back
VALID_TRANSITIONS: dict[Status, list[Status]] = {
    Status.OPEN:          [Status.INVESTIGATING],
    Status.INVESTIGATING: [Status.RESOLVED],
    Status.RESOLVED:      [Status.CLOSED],
    Status.CLOSED:        [],
}


class InvalidTransitionError(Exception):
    pass


class RCARequiredError(Exception):
    pass


class RCAIncompleteError(Exception):
    pass


class WorkItemStateMachine:
    """
    Enforces the incident lifecycle using the State Pattern.

    Why a state machine matters:
    Without it, engineers can skip states or close incidents without RCA.
    This makes illegal states unrepresentable in code, not just convention.

    Transitions:
        OPEN -> INVESTIGATING -> RESOLVED -> CLOSED
    Rules:
        - No skipping states
        - No backward transitions
        - CLOSED requires a complete RCA object
    """

    def __init__(self, current_status: str):
        self.current_status = Status(current_status)

    def transition(self, new_status: str, rca=None) -> Status:
        """
        Validates and performs a state transition.
        Raises InvalidTransitionError if transition is not allowed.
        Raises RCARequiredError / RCAIncompleteError if closing without valid RCA.
        """
        try:
            target = Status(new_status)
        except ValueError:
            raise InvalidTransitionError(f"'{new_status}' is not a valid status")

        allowed = VALID_TRANSITIONS[self.current_status]

        if target not in allowed:
            raise InvalidTransitionError(
                f"Cannot transition from {self.current_status} to {target}. "
                f"Allowed: {[s.value for s in allowed] or 'none (already CLOSED)'}"
            )

        if target == Status.CLOSED:
            self._validate_rca(rca)

        self.current_status = target
        return self.current_status

    def _validate_rca(self, rca):
        """
        Validates RCA completeness before allowing CLOSED transition.
        This is the mandatory postmortem gate.
        """
        if rca is None:
            raise RCARequiredError(
                "Cannot close incident without an RCA. "
                "Submit RCA via POST /rca first."
            )

        required_fields = ["root_cause_category", "fix_applied", "prevention_steps"]
        missing = [f for f in required_fields if not getattr(rca, f, None)]

        if missing:
            raise RCAIncompleteError(
                f"RCA is incomplete. Missing or empty fields: {missing}"
            )

        # Ensure fields aren't just whitespace
        blank = [f for f in required_fields if not str(getattr(rca, f, "")).strip()]
        if blank:
            raise RCAIncompleteError(f"RCA fields cannot be blank: {blank}")