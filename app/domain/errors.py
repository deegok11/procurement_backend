class DomainError(Exception):
    """Base class for business-rule violations (invariant breaches, bad requests)."""


class NotAuthorizedError(DomainError):
    """Caller is not authorized to perform this action on this document."""


class InvalidTransitionError(DomainError):
    """Requested status transition is not allowed for this document_type."""


class ReasonRequiredError(DomainError):
    """This transition requires a non-empty reason and none was given."""


class NotFoundError(DomainError):
    """Referenced document/item/user does not exist (or is outside the caller's tenant scope)."""


class InvariantViolationError(DomainError):
    """A hard invariant (tolerance, cumulative value, no-receipt-against-cancelled-PO, ...) was violated."""
