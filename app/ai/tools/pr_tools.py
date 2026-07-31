from typing import Optional

from app.ai.tools._arg_models import LineItemArg
from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.services import pr_service
from app.domain.services.pr_service import LineItemInput


def create_pr_draft(
    title: str, line_items: list[LineItemArg], needed_by_date: Optional[str] = None
) -> str:
    """Create a purchase requisition (PR) draft. Requester only. This does not
    submit it for approval — call submit_pr_for_approval next when the
    requester is ready.

    Args:
        title: Short title for the requisition.
        line_items: The items being requested.
        needed_by_date: Optional ISO date the items are needed by.
    """
    user = current_user_ctx.get()
    try:
        inputs = [
            LineItemInput(
                item_id=li.item_id, description=li.description, uom=li.uom,
                quantity=li.quantity, unit_price=li.unit_price, tax_pct=li.tax_pct,
            )
            for li in line_items
        ]
        doc = pr_service.create_pr_draft(
            user, title=title, line_items=inputs, needed_by_date=needed_by_date, source="chat_tool"
        )
        return f"Created PR draft {doc.id} ('{title}'), total {doc.amounts.grand_total} {doc.currency}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def submit_pr_for_approval(pr_id: str) -> str:
    """Submit a draft purchase requisition for approval. Requester only, and
    only the requester who created it.

    Args:
        pr_id: The PR's document id.
    """
    user = current_user_ctx.get()
    try:
        doc = pr_service.submit_pr(user, pr_id, source="chat_tool")
        return f"PR {doc.document_number} submitted for approval."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def approve_pr(pr_id: str, notes: str = "") -> str:
    """Approve a submitted purchase requisition. Approver role only. A
    requester can NEVER approve their own requisition — if you try, this will
    return NOT AUTHORIZED and nothing will change.

    Args:
        pr_id: The PR's document id.
        notes: Optional approval notes.
    """
    user = current_user_ctx.get()
    try:
        doc = pr_service.approve_pr(user, pr_id, notes=notes, source="chat_tool")
        return f"PR {doc.document_number} approved."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def reject_pr(pr_id: str, reason: str) -> str:
    """Reject a submitted purchase requisition. Approver role only. A reason
    is required.

    Args:
        pr_id: The PR's document id.
        reason: Why it's being rejected.
    """
    user = current_user_ctx.get()
    try:
        doc = pr_service.reject_pr(user, pr_id, reason, source="chat_tool")
        return f"PR {doc.document_number} rejected."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def cancel_pr(pr_id: str, reason: str) -> str:
    """Cancel a purchase requisition (draft, submitted, or approved).
    Requester (owner only) or approver. A reason is required.

    Args:
        pr_id: The PR's document id.
        reason: Why it's being cancelled.
    """
    user = current_user_ctx.get()
    try:
        doc = pr_service.cancel_pr(user, pr_id, reason, source="chat_tool")
        return f"PR {doc.id} cancelled."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def invite_vendors_to_pr(pr_id: str, vendor_ids: list[str]) -> str:
    """Invite vendors to submit a quotation against an approved PR. Requester
    (owner) only; the PR must already be APPROVED.

    Args:
        pr_id: The PR's document id.
        vendor_ids: The vendor_id values to invite (e.g. "vnd_acme_001").
    """
    user = current_user_ctx.get()
    try:
        doc = pr_service.invite_vendors_to_pr(user, pr_id, vendor_ids, source="chat_tool")
        return f"Invited vendors {vendor_ids} to PR {doc.document_number}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def compare_quotations(pr_id: str) -> str:
    """Compare all submitted quotations against a PR, cheapest first.
    Excludes withdrawn quotations and unconfirmed AI extractions
    (PENDING_REVIEW). Requester or approver only.

    Args:
        pr_id: The PR's document id.
    """
    user = current_user_ctx.get()
    try:
        quotations = pr_service.compare_quotations(user, pr_id)
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
    if not quotations:
        return "No comparable quotations yet."
    return "\n".join(
        f"{q.id} — vendor {q.vendor_id}: {q.amounts.grand_total} {q.currency} (status {q.status})"
        for q in quotations
    )
