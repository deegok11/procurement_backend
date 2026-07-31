from app.ai.tools._arg_models import LineOfferArg
from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.services import quotation_service


def submit_quotation(pr_id: str, line_offers: list[LineOfferArg]) -> str:
    """Submit a vendor's quotation against a PR the vendor was invited to.
    Vendor role only. The PR must be APPROVED and this vendor must be on its
    invited list.

    Args:
        pr_id: The PR's document id being quoted against.
        line_offers: The vendor's priced offer per PR line.
    """
    user = current_user_ctx.get()
    try:
        doc = quotation_service.submit_quotation(
            user, pr_id, [o.model_dump() for o in line_offers], source="chat_tool"
        )
        return f"Submitted quotation {doc.document_number}, total {doc.amounts.grand_total} {doc.currency}."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"


def withdraw_quotation(quotation_id: str, reason: str) -> str:
    """Withdraw a previously submitted quotation. Vendor (owner) only.

    Args:
        quotation_id: The quotation's document id.
        reason: Why it's being withdrawn.
    """
    user = current_user_ctx.get()
    try:
        doc = quotation_service.withdraw_quotation(user, quotation_id, reason, source="chat_tool")
        return f"Quotation {doc.document_number} withdrawn."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
