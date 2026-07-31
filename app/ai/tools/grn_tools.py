from typing import Optional

from app.ai.tools._arg_models import ReceivedLineArg
from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, InvariantViolationError, NotAuthorizedError
from app.domain.services import grn_service


def create_grn(po_id: str, received_lines: list[ReceivedLineArg], received_date: Optional[str] = None) -> str:
    """Record a goods receipt / service receipt (GRN/SRN) against an ISSUED
    PO. Requester only. Cumulative received quantity per PO line cannot
    exceed the PO's ordered quantity beyond the configured tolerance.

    Args:
        po_id: The PO's document id.
        received_lines: What was received, per PO line.
        received_date: Optional ISO date of receipt.
    """
    user = current_user_ctx.get()
    try:
        doc = grn_service.create_grn(
            user, po_id, [rl.model_dump() for rl in received_lines],
            received_date=received_date, source="chat_tool",
        )
        return f"Recorded GRN {doc.document_number}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except InvariantViolationError as e:
        return f"REJECTED (invariant): {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def cancel_grn(grn_id: str, reason: str) -> str:
    """Cancel a GRN/SRN. Blocked if any active bill already references it.
    Requester or approver.

    Args:
        grn_id: The GRN/SRN's document id.
        reason: Why it's being cancelled.
    """
    user = current_user_ctx.get()
    try:
        doc = grn_service.cancel_grn(user, grn_id, reason, source="chat_tool")
        return f"GRN {doc.document_number} cancelled."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
