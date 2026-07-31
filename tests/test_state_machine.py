import pytest

from app.domain.errors import InvalidTransitionError, ReasonRequiredError
from app.domain.schemas import DocumentType
from app.domain.state_machine import STATE_MACHINES, validate_transition


@pytest.mark.parametrize(
    "document_type,transition",
    [
        (dt, t)
        for dt, transitions in STATE_MACHINES.items()
        for t in transitions
    ],
)
def test_every_declared_transition_is_allowed(document_type, transition):
    reason = "a reason" if transition.requires_reason else None
    # Should not raise
    validate_transition(document_type, transition.from_status, transition.to_status, reason)


@pytest.mark.parametrize(
    "document_type,transition",
    [
        (dt, t)
        for dt, transitions in STATE_MACHINES.items()
        for t in transitions
        if t.requires_reason
    ],
)
def test_reason_required_transitions_reject_empty_reason(document_type, transition):
    with pytest.raises(ReasonRequiredError):
        validate_transition(document_type, transition.from_status, transition.to_status, None)
    with pytest.raises(ReasonRequiredError):
        validate_transition(document_type, transition.from_status, transition.to_status, "   ")


def test_undeclared_transition_is_rejected():
    with pytest.raises(InvalidTransitionError):
        validate_transition(DocumentType.PR, "DRAFT", "APPROVED", None)  # must go through SUBMITTED


def test_terminal_status_has_no_outgoing_transitions():
    with pytest.raises(InvalidTransitionError):
        validate_transition(DocumentType.PR, "CANCELLED", "SUBMITTED", None)
    with pytest.raises(InvalidTransitionError):
        validate_transition(DocumentType.PR, "REJECTED", "APPROVED", None)


def test_po_cannot_skip_to_cancelled_with_wrong_status_name():
    with pytest.raises(InvalidTransitionError):
        validate_transition(DocumentType.PO, "DRAFT", "CANCELLED", "reason")  # PO has no DRAFT status
