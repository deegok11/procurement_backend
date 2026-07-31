from typing import Optional

from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, InvariantViolationError, NotAuthorizedError
from app.domain.services import transaction_service


def create_transaction(
    bill_id: str, amount: str, payment_method: Optional[str] = None, reference_number: Optional[str] = None
) -> str:
    """Record a payment against a MATCHED or ACKNOWLEDGED bill. Approver only
    — this is the one action in the whole system that moves money, and it can
    only be called by a human with the approver role. Cumulative paid amount
    can never exceed the bill's total.

    Args:
        bill_id: The bill's document id being paid.
        amount: Payment amount as a decimal string.
        payment_method: Optional, e.g. "wire", "check".
        reference_number: Optional payment reference/confirmation number.
    """
    user = current_user_ctx.get()
    try:
        doc = transaction_service.create_transaction(
            user, bill_id, amount, payment_method=payment_method,
            reference_number=reference_number, source="chat_tool",
        )
        return f"Payment {doc.document_number} recorded for {amount} {doc.currency}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except InvariantViolationError as e:
        return f"REJECTED (invariant): {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def cancel_transaction(transaction_id: str, reason: str) -> str:
    """Cancel a recorded payment. Approver only.

    Args:
        transaction_id: The transaction's document id.
        reason: Why it's being cancelled.
    """
    user = current_user_ctx.get()
    try:
        doc = transaction_service.cancel_transaction(user, transaction_id, reason, source="chat_tool")
        return f"Transaction {doc.document_number} cancelled."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
