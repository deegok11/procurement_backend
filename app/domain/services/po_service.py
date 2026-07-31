from decimal import Decimal

from app.config import settings
from app.domain.errors import DomainError
from app.domain.permissions import build_scope, require_permission
from app.domain.roles import Domain
from app.domain.schemas import CurrentUser, Document, DocumentType, now_iso
from app.domain.services._events import log_event
from app.domain.services._inheritance import derive_line_items
from app.domain.services._pricing import compute_amounts, compute_line_total
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


def create_po_from_quotation(
    current_user: CurrentUser,
    quotation_id: str,
    *,
    payment_terms: str | None = None,
    source: str = "api",
) -> Document:
    require_permission(current_user, "po:create")
    quotation = documents_repo.get(quotation_id)
    if quotation.document_type != DocumentType.QUOTATION:
        raise DomainError(f"{quotation_id} is not a quotation")
    if quotation.status != "SUBMITTED":
        raise DomainError(
            f"quotation must be SUBMITTED to convert to a PO (currently {quotation.status}) — "
            "an unconfirmed AI extraction (PENDING_REVIEW) can never become a PO"
        )
    pr = documents_repo.get(quotation.parent_document_id)

    # Scope-creep guard: a PO issued off a quotation must not materially exceed
    # what was actually approved on the PR. Not a per-role approval threshold
    # (the requester creating the PO has none) — it re-validates the PR's own
    # approved amount, with the same tolerance used elsewhere in the system.
    tolerance = Decimal(str(settings.APPROVAL_TOLERANCE_PCT)) / Decimal("100")
    max_allowed = Decimal(pr.amounts.grand_total) * (Decimal("1") + tolerance)
    if Decimal(quotation.amounts.grand_total) > max_allowed:
        raise DomainError(
            f"selected quotation total {quotation.amounts.grand_total} exceeds the PR's approved "
            f"amount {pr.amounts.grand_total} beyond the {settings.APPROVAL_TOLERANCE_PCT}% tolerance "
            "— the PR must be re-approved at the higher value before a PO can be issued"
        )

    lines = derive_line_items(quotation, quantity_mapper=lambda pl: pl.quantity)
    for line in lines:
        line.line_total = compute_line_total(line.quantity, line.unit_price, line.tax_pct)
    doc = Document(
        document_type=DocumentType.PO,
        series_code="PO",
        parent_document_id=quotation.id,
        root_pr_id=quotation.root_pr_id or pr.id,
        domain=Domain.INTERNAL,
        vendor_id=quotation.vendor_id,
        status="ISSUED",
        requester_id=current_user.user_id,
        approver_id=pr.approver_id,
        title=f"PO for {pr.title}",
        currency=quotation.currency,
        line_items=lines,
        amounts=compute_amounts(lines),
        extra={"payment_terms": payment_terms},
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("PO", fy)
    doc.financial_year = fy
    documents_repo.add(doc)
    log_event(doc, event_type="CREATED", from_status=None, to_status="ISSUED", actor=current_user, source=source)

    validate_transition(DocumentType.QUOTATION, quotation.status, "SELECTED", None)
    quotation.status = "SELECTED"
    quotation.updated_at = now_iso()
    quotation.updated_by = current_user.user_id
    documents_repo.update(quotation)
    log_event(
        quotation, event_type="STATUS_CHANGED", from_status="SUBMITTED", to_status="SELECTED",
        actor=current_user, source=source, metadata={"po_document_id": doc.id},
    )
    return doc


def cancel_po(current_user: CurrentUser, po_id: str, reason: str, *, source: str = "api") -> Document:
    require_permission(current_user, "po:cancel")
    doc = documents_repo.get(po_id)
    active_grns = [
        g for g in documents_repo.list(document_type=DocumentType.GRN_SRN, parent_document_id=po_id)
        if g.status != "CANCELLED"
    ]
    if active_grns:
        raise DomainError(f"cannot cancel PO {po_id}: {len(active_grns)} active GRN(s) reference it")

    validate_transition(DocumentType.PO, doc.status, "CANCELLED", reason)
    doc.status = "CANCELLED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(doc, event_type="CANCELLED", from_status="ISSUED", to_status="CANCELLED", actor=current_user, reason=reason, source=source)
    return doc


def get_po(current_user: CurrentUser, po_id: str) -> Document:
    require_permission(current_user, "po:read")
    return documents_repo.get(po_id, scope=build_scope(current_user))


def list_pos(current_user: CurrentUser, *, parent_document_id: str | None = None) -> list[Document]:
    require_permission(current_user, "po:read")
    return documents_repo.list(
        document_type=DocumentType.PO, parent_document_id=parent_document_id, scope=build_scope(current_user),
    )
