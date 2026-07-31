from dataclasses import dataclass

from app.domain.errors import InvalidTransitionError, ReasonRequiredError
from app.domain.schemas import DocumentType


@dataclass(frozen=True)
class Transition:
    from_status: str
    to_status: str
    requires_reason: bool = False


# One small table per document_type. "from_status: None" would mean "on create" —
# we model creation status separately in each service (it's not a transition FROM
# anything), so every entry here is a genuine status -> status move.
STATE_MACHINES: dict[DocumentType, list[Transition]] = {
    DocumentType.PR: [
        Transition("DRAFT", "SUBMITTED"),
        Transition("SUBMITTED", "APPROVED"),
        Transition("SUBMITTED", "REJECTED", requires_reason=True),
        Transition("DRAFT", "CANCELLED", requires_reason=True),
        Transition("SUBMITTED", "CANCELLED", requires_reason=True),
        Transition("APPROVED", "CANCELLED", requires_reason=True),
    ],
    DocumentType.QUOTATION: [
        # EXTRACTING is the status an uploaded-PDF quotation is created at —
        # the upload request returns immediately with this status while OCR +
        # Gemini extraction run in a background task; PENDING_REVIEW is only
        # reached once that background work finishes (or EXTRACTION_FAILED if
        # it errors out).
        Transition("EXTRACTING", "PENDING_REVIEW"),
        Transition("EXTRACTING", "EXTRACTION_FAILED", requires_reason=True),
        Transition("PENDING_REVIEW", "SUBMITTED"),
        Transition("SUBMITTED", "WITHDRAWN", requires_reason=True),
        Transition("SUBMITTED", "SELECTED"),
    ],
    DocumentType.PO: [
        Transition("ISSUED", "CANCELLED", requires_reason=True),
    ],
    DocumentType.GRN_SRN: [
        Transition("RECORDED", "CANCELLED", requires_reason=True),
    ],
    DocumentType.BILL: [
        Transition("EXTRACTING", "PENDING_REVIEW"),
        Transition("EXTRACTING", "EXTRACTION_FAILED", requires_reason=True),
        Transition("PENDING_REVIEW", "MATCHED"),
        Transition("PENDING_REVIEW", "MATCH_EXCEPTION"),
        Transition("MATCH_EXCEPTION", "ACKNOWLEDGED"),
        Transition("MATCHED", "CANCELLED", requires_reason=True),
        Transition("ACKNOWLEDGED", "CANCELLED", requires_reason=True),
        Transition("MATCH_EXCEPTION", "CANCELLED", requires_reason=True),
    ],
    DocumentType.TRANSACTION: [
        Transition("RECORDED", "CANCELLED", requires_reason=True),
    ],
}

# Valid initial statuses per type, for reference/validation at creation time.
CREATION_STATUSES: dict[DocumentType, set[str]] = {
    DocumentType.PR: {"DRAFT"},
    DocumentType.QUOTATION: {"EXTRACTING", "PENDING_REVIEW", "SUBMITTED"},
    DocumentType.PO: {"ISSUED"},
    DocumentType.GRN_SRN: {"RECORDED"},
    DocumentType.BILL: {"EXTRACTING", "PENDING_REVIEW", "MATCHED", "MATCH_EXCEPTION"},
    DocumentType.TRANSACTION: {"RECORDED"},
}


def validate_transition(
    document_type: DocumentType, from_status: str, to_status: str, reason: str | None
) -> None:
    allowed = [
        t
        for t in STATE_MACHINES[document_type]
        if t.from_status == from_status and t.to_status == to_status
    ]
    if not allowed:
        raise InvalidTransitionError(
            f"{document_type.value}: {from_status} -> {to_status} is not an allowed transition"
        )
    if allowed[0].requires_reason and not (reason and reason.strip()):
        raise ReasonRequiredError(
            f"{document_type.value}: {from_status} -> {to_status} requires a non-empty reason"
        )
