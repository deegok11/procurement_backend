from typing import Optional

from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.services import po_service


def create_po_from_quotation(quotation_id: str, payment_terms: Optional[str] = None) -> str:
    """Issue a purchase order from a submitted (never PENDING_REVIEW) quotation.
    Requester only. The resulting PO amount is re-checked against the PR's
    approved amount.

    Args:
        quotation_id: The winning quotation's document id.
        payment_terms: Optional free-text payment terms.
    """
    user = current_user_ctx.get()
    try:
        doc = po_service.create_po_from_quotation(
            user, quotation_id, payment_terms=payment_terms, source="chat_tool"
        )
        return f"Issued PO {doc.document_number}, total {doc.amounts.grand_total} {doc.currency}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def cancel_po(po_id: str, reason: str) -> str:
    """Cancel a purchase order. Blocked if any active GRN/SRN already
    references it. Requester or approver.

    Args:
        po_id: The PO's document id.
        reason: Why it's being cancelled.
    """
    user = current_user_ctx.get()
    try:
        doc = po_service.cancel_po(user, po_id, reason, source="chat_tool")
        return f"PO {doc.document_number} cancelled."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
