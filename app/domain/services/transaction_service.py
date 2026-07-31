from decimal import Decimal

from app.domain.errors import DomainError
from app.domain.invariants import check_cumulative_paid_not_exceed_billed
from app.domain.permissions import build_scope, require_permission
from app.domain.roles import Domain
from app.domain.schemas import Amounts, CurrentUser, Document, DocumentType, now_iso
from app.domain.services._cumulative import cumulative_paid_for_bill
from app.domain.services._events import log_event
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


def create_transaction(
    current_user: CurrentUser,
    bill_id: str,
    amount: str,
    *,
    payment_method: str | None = None,
    reference_number: str | None = None,
    source: str = "api",
) -> Document:
    require_permission(current_user, "transaction:create")
    bill = documents_repo.get(bill_id)
    if bill.document_type != DocumentType.BILL:
        raise DomainError(f"{bill_id} is not a bill")
    if bill.status not in {"MATCHED", "ACKNOWLEDGED"}:
        raise DomainError(
            f"bill must be MATCHED or ACKNOWLEDGED before payment (currently {bill.status})"
        )

    cumulative_paid = cumulative_paid_for_bill(bill.id) + Decimal(amount)
    check_cumulative_paid_not_exceed_billed(bill.amounts.grand_total, str(cumulative_paid))

    doc = Document(
        document_type=DocumentType.TRANSACTION,
        series_code="TXN",
        parent_document_id=bill.id,
        root_pr_id=bill.root_pr_id,
        domain=Domain.INTERNAL,
        vendor_id=bill.vendor_id,
        status="RECORDED",
        requester_id=current_user.user_id,
        approver_id=current_user.user_id,
        title=f"Payment for {bill.document_number or bill.id}",
        currency=bill.currency,
        line_items=[],
        amounts=Amounts(subtotal=amount, tax_total="0", grand_total=amount),
        extra={"payment_method": payment_method, "reference_number": reference_number},
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("TXN", fy)
    doc.financial_year = fy
    documents_repo.add(doc)
    log_event(doc, event_type="CREATED", from_status=None, to_status="RECORDED", actor=current_user, source=source)
    return doc


def cancel_transaction(
    current_user: CurrentUser, transaction_id: str, reason: str, *, source: str = "api"
) -> Document:
    require_permission(current_user, "transaction:cancel")
    doc = documents_repo.get(transaction_id)
    validate_transition(DocumentType.TRANSACTION, doc.status, "CANCELLED", reason)

    doc.status = "CANCELLED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(doc, event_type="CANCELLED", from_status="RECORDED", to_status="CANCELLED", actor=current_user, reason=reason, source=source)
    return doc


def get_transaction(current_user: CurrentUser, transaction_id: str) -> Document:
    require_permission(current_user, "transaction:read")
    return documents_repo.get(transaction_id, scope=build_scope(current_user))


def list_transactions(current_user: CurrentUser, *, parent_document_id: str | None = None) -> list[Document]:
    require_permission(current_user, "transaction:read")
    return documents_repo.list(
        document_type=DocumentType.TRANSACTION, parent_document_id=parent_document_id,
        scope=build_scope(current_user),
    )
