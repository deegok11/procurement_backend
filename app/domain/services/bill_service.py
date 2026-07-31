from decimal import Decimal

from app.domain.errors import DomainError
from app.domain.invariants import check_cumulative_billed_not_exceed_received, run_three_way_match
from app.domain.permissions import build_scope, require_permission
from app.domain.roles import Domain
from app.domain.schemas import CurrentUser, Document, DocumentType, LineItem, now_iso
from app.domain.services._cumulative import (
    cumulative_billed_value_for_po_line,
    received_value_for_po_line,
)
from app.domain.services._events import log_event
from app.domain.services._pricing import compute_amounts, compute_line_total
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


def build_bill_lines_and_match(grn: Document, po: Document, billed_lines: list[dict]):
    """Pure line-building + invariant checks + 3-way match — shared by the
    direct create_bill path and the extraction-confirm path (extraction_service)
    so both go through identical validation. Returns (lines, match_result).
    billed_lines: [{"ref_line_no": int, "quantity": str, "unit_price": str, "tax_pct": str}]
    ref_line_no matches the GRN line being billed."""
    if not billed_lines:
        raise DomainError("a bill must have at least one line item")

    grn_lines_by_no = {ln.line_no: ln for ln in grn.line_items}
    lines: list[LineItem] = []
    for idx, bl in enumerate(billed_lines, start=1):
        grn_line = grn_lines_by_no.get(bl["ref_line_no"])
        if grn_line is None:
            raise DomainError(f"GRN has no line_no {bl['ref_line_no']}")
        po_line_no = grn_line.extra.get("po_line_no")
        tax_pct = bl.get("tax_pct", grn_line.tax_pct or "0")
        line_total = compute_line_total(bl["quantity"], bl["unit_price"], tax_pct)

        # Hard invariant, checked per PO line before this bill is allowed to exist:
        # cumulative billed value can never exceed received value. No tolerance.
        cumulative_billed = cumulative_billed_value_for_po_line(po.id, po_line_no) + Decimal(line_total)
        received_value = received_value_for_po_line(po.id, po_line_no)
        check_cumulative_billed_not_exceed_received(str(received_value), str(cumulative_billed))

        lines.append(
            LineItem(
                line_no=idx,
                ref_line_no=grn_line.line_no,
                item_id=grn_line.item_id,
                description=grn_line.description,
                uom=grn_line.uom,
                quantity=bl["quantity"],
                unit_price=bl["unit_price"],
                line_total=line_total,
                tax_pct=tax_pct,
                extra={"po_line_no": po_line_no},
            )
        )

    match_result = run_three_way_match(lines, grn.line_items, po.line_items)
    return lines, match_result


def create_bill(
    current_user: CurrentUser,
    grn_id: str,
    billed_lines: list[dict],
    *,
    invoice_number: str | None = None,
    invoice_date: str | None = None,
    source: str = "api",
) -> Document:
    require_permission(current_user, "bill:create")
    grn = documents_repo.get(grn_id)
    if grn.document_type != DocumentType.GRN_SRN:
        raise DomainError(f"{grn_id} is not a GRN/SRN")
    po = documents_repo.get(grn.parent_document_id)

    lines, match_result = build_bill_lines_and_match(grn, po, billed_lines)

    doc = Document(
        document_type=DocumentType.BILL,
        series_code="BILL",
        parent_document_id=grn.id,
        root_pr_id=grn.root_pr_id,
        domain=Domain.INTERNAL,
        vendor_id=grn.vendor_id,
        status=match_result.status,
        requester_id=current_user.user_id,
        approver_id=po.approver_id,
        title=f"Bill for {grn.document_number or grn.id}",
        currency=po.currency,
        line_items=lines,
        amounts=compute_amounts(lines),
        extra={
            "invoice_number": invoice_number,
            "invoice_date": invoice_date,
            "po_document_id": po.id,
            "three_way_match": [r._asdict() for r in match_result.line_results],
        },
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("BILL", fy)
    doc.financial_year = fy
    documents_repo.add(doc)
    log_event(
        doc, event_type="CREATED", from_status=None, to_status=match_result.status, actor=current_user,
        source=source, metadata={"three_way_match": doc.extra["three_way_match"]},
    )
    return doc


def confirm_bill_extraction(
    current_user: CurrentUser, document_id: str, billed_lines: list[dict], *, source: str = "extraction_pipeline"
) -> Document:
    """P4: an AI-extracted bill sits in PENDING_REVIEW and cannot be paid
    against until a buyer (requester) confirms it here — the human's values
    replace the AI's proposal, then the exact same 3-way-match logic runs as
    on a directly-created bill."""
    require_permission(current_user, "extraction:confirm")
    doc = documents_repo.get(document_id)
    if doc.document_type != DocumentType.BILL:
        raise DomainError(f"{document_id} is not a bill")
    if doc.status != "PENDING_REVIEW":
        raise DomainError(f"bill {document_id} is not pending review (status {doc.status})")
    grn = documents_repo.get(doc.parent_document_id)
    po = documents_repo.get(grn.parent_document_id)

    lines, match_result = build_bill_lines_and_match(grn, po, billed_lines)
    validate_transition(DocumentType.BILL, "PENDING_REVIEW", match_result.status, None)

    doc.line_items = lines
    doc.amounts = compute_amounts(lines)
    doc.status = match_result.status
    doc.extra["three_way_match"] = [r._asdict() for r in match_result.line_results]
    if doc.extraction_provenance is not None:
        doc.extraction_provenance.status = "VERIFIED"
        doc.extraction_provenance.reviewed_by = current_user.user_id
        doc.extraction_provenance.reviewed_at = now_iso()
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("BILL", fy)
    doc.financial_year = fy
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(
        doc, event_type="EXTRACTION_CONFIRMED", from_status="PENDING_REVIEW", to_status=match_result.status,
        actor=current_user, source=source, metadata={"three_way_match": doc.extra["three_way_match"]},
    )
    return doc


def acknowledge_bill_exception(
    current_user: CurrentUser, bill_id: str, *, notes: str = "", source: str = "api"
) -> Document:
    require_permission(current_user, "bill:acknowledge_exception")
    doc = documents_repo.get(bill_id)
    validate_transition(DocumentType.BILL, doc.status, "ACKNOWLEDGED", None)

    doc.status = "ACKNOWLEDGED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(
        doc, event_type="STATUS_CHANGED", from_status="MATCH_EXCEPTION", to_status="ACKNOWLEDGED",
        actor=current_user, reason=notes or None, source=source,
    )
    return doc


def cancel_bill(current_user: CurrentUser, bill_id: str, reason: str, *, source: str = "api") -> Document:
    require_permission(current_user, "bill:cancel")
    doc = documents_repo.get(bill_id)
    active_txns = [
        t for t in documents_repo.list(document_type=DocumentType.TRANSACTION, parent_document_id=bill_id)
        if t.status != "CANCELLED"
    ]
    if active_txns:
        raise DomainError(f"cannot cancel bill {bill_id}: {len(active_txns)} active transaction(s) reference it")

    from_status = doc.status
    validate_transition(DocumentType.BILL, doc.status, "CANCELLED", reason)
    doc.status = "CANCELLED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(doc, event_type="CANCELLED", from_status=from_status, to_status="CANCELLED", actor=current_user, reason=reason, source=source)
    return doc


def get_bill(current_user: CurrentUser, bill_id: str) -> Document:
    require_permission(current_user, "bill:read")
    return documents_repo.get(bill_id, scope=build_scope(current_user))


def list_bills(current_user: CurrentUser, *, parent_document_id: str | None = None) -> list[Document]:
    require_permission(current_user, "bill:read")
    return documents_repo.list(
        document_type=DocumentType.BILL, parent_document_id=parent_document_id, scope=build_scope(current_user),
    )
