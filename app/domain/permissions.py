from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from app.domain.errors import NotAuthorizedError
from app.domain.roles import Domain, Role, has_permission
from app.domain.schemas import CurrentUser, Document

# Single tier today ("we're not scaling now"), shaped to add more later:
# each entry's max_amount is the largest grand_total that level may approve;
# None means unlimited.
APPROVAL_THRESHOLDS: dict[int, Optional[Decimal]] = {1: None}


@dataclass(frozen=True)
class QueryScope:
    """Turns identity into a data filter. This is the ONLY place identity
    becomes a query constraint — DocumentsRepository applies it on every
    read, so tenant isolation (P5) is enforced once, at the data layer,
    never via scattered `if current_user.role == "vendor"` checks in routes."""

    domain: Domain
    vendor_id: Optional[str]


def build_scope(current_user: CurrentUser) -> QueryScope:
    return QueryScope(domain=current_user.domain, vendor_id=current_user.vendor_id)


def require_permission(current_user: CurrentUser, permission: str) -> None:
    if not has_permission(current_user.role, permission):
        raise NotAuthorizedError(
            f"role '{current_user.role.value}' does not have permission '{permission}'"
        )


def require_owner(current_user: CurrentUser, owner_user_id: str) -> None:
    if current_user.user_id != owner_user_id:
        raise NotAuthorizedError("only the owner of this document may perform this action")


def require_not_self_approval(current_user: CurrentUser, requester_id: str) -> None:
    if current_user.user_id == requester_id:
        raise NotAuthorizedError("a requester cannot approve their own requisition (no self-approval)")


def require_within_approval_threshold(current_user: CurrentUser, grand_total: str) -> None:
    max_amount = APPROVAL_THRESHOLDS.get(current_user.approval_level or 0)
    if current_user.approval_level not in APPROVAL_THRESHOLDS:
        raise NotAuthorizedError(
            f"role '{current_user.role.value}' has no configured approval level"
        )
    if max_amount is not None and Decimal(grand_total) > max_amount:
        raise NotAuthorizedError(
            f"amount {grand_total} exceeds approval level {current_user.approval_level} "
            f"threshold ({max_amount})"
        )


def require_vendor_owns_document(current_user: CurrentUser, document: Document) -> None:
    if current_user.domain == Domain.VENDOR and document.vendor_id != current_user.vendor_id:
        raise NotAuthorizedError("this document belongs to a different vendor")
