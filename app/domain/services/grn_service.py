from decimal import Decimal

from app.config import settings
from app.domain.errors import DomainError
from app.domain.invariants import check_grn_tolerance, check_no_receipt_against_invalid_po
from app.domain.permissions import build_scope, require_permission
from app.domain.roles import Domain
from app.domain.schemas import CurrentUser, Document, DocumentType, LineItem, now_iso
from app.domain.services._cumulative import cumulative_received_qty_for_po_line
from app.domain.services._events import log_event
from app.domain.services._pricing import compute_amounts, compute_line_total
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


def create_grn(
    current_user: CurrentUser,
    po_id: str,
    received_lines: list[dict],
    *,
    received_date: str | None = None,
    source: str = "api",
) -> Document:
    """received_lines: [{"ref_line_no": int, "received_qty": str}] — ref_line_no
    matches the PO line being (partially or fully) received."""
    require_permission(current_user, "grn:create")
    po = documents_repo.get(po_id)
    if po.document_type != DocumentType.PO:
        raise DomainError(f"{po_id} is not a PO")
    check_no_receipt_against_invalid_po(po)

    if not received_lines:
        raise DomainError("a GRN/SRN must have at least one line item")

    po_lines_by_no = {ln.line_no: ln for ln in po.line_items}
    lines: list[LineItem] = []
    for idx, rl in enumerate(received_lines, start=1):
        po_line = po_lines_by_no.get(rl["ref_line_no"])
        if po_line is None:
            raise DomainError(f"PO has no line_no {rl['ref_line_no']}")

        cumulative = cumulative_received_qty_for_po_line(po.id, po_line.line_no) + Decimal(
            rl["received_qty"]
        )
        check_grn_tolerance(po_line.quantity, str(cumulative), settings.APPROVAL_TOLERANCE_PCT)

        lines.append(
            LineItem(
                line_no=idx,
                ref_line_no=po_line.line_no,
                item_id=po_line.item_id,
                description=po_line.description,
                uom=po_line.uom,
                quantity=rl["received_qty"],
                unit_price=po_line.unit_price,
                line_total=compute_line_total(rl["received_qty"], po_line.unit_price, po_line.tax_pct),
                tax_pct=po_line.tax_pct,
                extra={"po_line_no": po_line.line_no},
            )
        )

    doc = Document(
        document_type=DocumentType.GRN_SRN,
        series_code="GRN",
        parent_document_id=po.id,
        root_pr_id=po.root_pr_id,
        domain=Domain.INTERNAL,
        vendor_id=po.vendor_id,
        status="RECORDED",
        requester_id=current_user.user_id,
        approver_id=po.approver_id,
        title=f"GRN for {po.document_number or po.id}",
        currency=po.currency,
        line_items=lines,
        amounts=compute_amounts(lines),
        extra={"received_date": received_date},
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("GRN", fy)
    doc.financial_year = fy
    documents_repo.add(doc)
    log_event(doc, event_type="CREATED", from_status=None, to_status="RECORDED", actor=current_user, source=source)
    return doc


def cancel_grn(current_user: CurrentUser, grn_id: str, reason: str, *, source: str = "api") -> Document:
    require_permission(current_user, "grn:cancel")
    doc = documents_repo.get(grn_id)
    active_bills = [
        b for b in documents_repo.list(document_type=DocumentType.BILL, parent_document_id=grn_id)
        if b.status != "CANCELLED"
    ]
    if active_bills:
        raise DomainError(f"cannot cancel GRN {grn_id}: {len(active_bills)} active bill(s) reference it")

    validate_transition(DocumentType.GRN_SRN, doc.status, "CANCELLED", reason)
    doc.status = "CANCELLED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(doc, event_type="CANCELLED", from_status="RECORDED", to_status="CANCELLED", actor=current_user, reason=reason, source=source)
    return doc


def get_grn(current_user: CurrentUser, grn_id: str) -> Document:
    require_permission(current_user, "grn:read")
    return documents_repo.get(grn_id, scope=build_scope(current_user))


def list_grns(current_user: CurrentUser, *, parent_document_id: str | None = None) -> list[Document]:
    require_permission(current_user, "grn:read")
    return documents_repo.list(
        document_type=DocumentType.GRN_SRN, parent_document_id=parent_document_id, scope=build_scope(current_user),
    )
