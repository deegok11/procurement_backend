from typing import Optional

from app.ai.tools._arg_models import BilledLineArg
from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, InvariantViolationError, NotAuthorizedError
from app.domain.services import bill_service


def create_bill(
    grn_id: str,
    billed_lines: list[BilledLineArg],
    invoice_number: Optional[str] = None,
    invoice_date: Optional[str] = None,
) -> str:
    """Record a vendor bill against a GRN/SRN and run the 3-way match (bill vs.
    receipt vs. PO). Requester only. Cumulative billed value per PO line can
    never exceed received value — that's a hard rule, not just a warning.

    Args:
        grn_id: The GRN/SRN's document id being billed.
        billed_lines: The billed quantity/price per GRN line.
        invoice_number: Optional vendor invoice number.
        invoice_date: Optional ISO date on the invoice.
    """
    user = current_user_ctx.get()
    try:
        doc = bill_service.create_bill(
            user, grn_id, [bl.model_dump() for bl in billed_lines],
            invoice_number=invoice_number, invoice_date=invoice_date, source="chat_tool",
        )
        return (
            f"Bill {doc.document_number} recorded, status {doc.status}. "
            + ("A human approver must acknowledge the mismatch before payment." if doc.status == "MATCH_EXCEPTION" else "")
        )
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except InvariantViolationError as e:
        return f"REJECTED (invariant): {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def acknowledge_bill_exception(bill_id: str, notes: str = "") -> str:
    """Acknowledge a bill that's in MATCH_EXCEPTION (e.g. price mismatch
    against the PO), clearing it to proceed toward payment. Approver only.

    Args:
        bill_id: The bill's document id.
        notes: Optional notes on why the exception is acceptable.
    """
    user = current_user_ctx.get()
    try:
        doc = bill_service.acknowledge_bill_exception(user, bill_id, notes=notes, source="chat_tool")
        return f"Bill {doc.document_number} exception acknowledged."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def cancel_bill(bill_id: str, reason: str) -> str:
    """Cancel a bill. Blocked if any active payment transaction already
    references it. Requester or approver.

    Args:
        bill_id: The bill's document id.
        reason: Why it's being cancelled.
    """
    user = current_user_ctx.get()
    try:
        doc = bill_service.cancel_bill(user, bill_id, reason, source="chat_tool")
        return f"Bill {doc.document_number} cancelled."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
