from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.permissions import build_scope, require_owner, require_permission
from app.domain.roles import Domain
from app.domain.schemas import CurrentUser, Document, DocumentType, LineItem, now_iso
from app.domain.services._events import log_event
from app.domain.services._pricing import compute_amounts, compute_line_total
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


def build_quotation_lines(pr: Document, line_offers: list[dict]) -> list[LineItem]:
    """Pure line-building, no permission/status checks — shared by the direct
    submit_quotation path and the extraction-confirm path (extraction_service)
    so both go through identical validation and pricing logic.
    line_offers: [{"ref_line_no": int, "quantity": str, "unit_price": str, "tax_pct": str}]
    ref_line_no matches the PR line this offer responds to. Unlike later
    stages, a quotation isn't a mechanical copy of the parent — it's the
    vendor's own priced offer — but item_id/description/uom are still pulled
    straight from the PR line, same "reuse the parent's fields" pattern."""
    if not line_offers:
        raise DomainError("a quotation must have at least one line item")
    pr_lines_by_no = {ln.line_no: ln for ln in pr.line_items}
    lines: list[LineItem] = []
    for idx, offer in enumerate(line_offers, start=1):
        pr_line = pr_lines_by_no.get(offer["ref_line_no"])
        if pr_line is None:
            raise DomainError(f"PR has no line_no {offer['ref_line_no']}")
        tax_pct = offer.get("tax_pct", "0")
        lines.append(
            LineItem(
                line_no=idx,
                ref_line_no=pr_line.line_no,
                item_id=pr_line.item_id,
                description=pr_line.description,
                uom=pr_line.uom,
                quantity=offer["quantity"],
                unit_price=offer["unit_price"],
                line_total=compute_line_total(offer["quantity"], offer["unit_price"], tax_pct),
                tax_pct=tax_pct,
                extra={"po_line_no": pr_line.line_no},
            )
        )
    return lines


def submit_quotation(
    current_user: CurrentUser,
    pr_id: str,
    line_offers: list[dict],
    *,
    currency: str = "USD",
    source: str = "api",
) -> Document:
    require_permission(current_user, "quotation:submit")
    pr = documents_repo.get(pr_id, scope=build_scope(current_user))
    if pr.document_type != DocumentType.PR:
        raise DomainError(f"{pr_id} is not a PR")
    if pr.status != "APPROVED":
        raise DomainError(f"PR must be APPROVED before quoting (currently {pr.status})")
    invited = set(pr.extra.get("invited_vendor_ids") or [])
    if current_user.vendor_id not in invited:
        raise NotAuthorizedError("this vendor was not invited to quote on this PR")

    lines = build_quotation_lines(pr, line_offers)

    doc = Document(
        document_type=DocumentType.QUOTATION,
        series_code="QT",
        parent_document_id=pr.id,
        root_pr_id=pr.root_pr_id or pr.id,
        domain=Domain.VENDOR,
        vendor_id=current_user.vendor_id,
        status="SUBMITTED",
        requester_id=current_user.user_id,
        title=f"Quotation for {pr.title}",
        currency=currency,
        line_items=lines,
        amounts=compute_amounts(lines),
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("QT", fy)
    doc.financial_year = fy
    documents_repo.add(doc)
    log_event(doc, event_type="CREATED", from_status=None, to_status="SUBMITTED", actor=current_user, source=source)
    return doc


def confirm_quotation_extraction(
    current_user: CurrentUser, document_id: str, line_offers: list[dict], *, source: str = "extraction_pipeline"
) -> Document:
    """P4: values parsed from a vendor PDF sit in PENDING_REVIEW and cannot
    influence a comparison or a PO until a buyer (requester) confirms them
    here. Confirming replaces the AI-proposed line_items with the human's
    (possibly corrected) values — the AI output is superseded, never trusted
    silently — and only then does the document become SUBMITTED and eligible
    for compare_quotations / create_po_from_quotation."""
    require_permission(current_user, "extraction:confirm")
    doc = documents_repo.get(document_id)
    if doc.document_type != DocumentType.QUOTATION:
        raise DomainError(f"{document_id} is not a quotation")
    if doc.status != "PENDING_REVIEW":
        raise DomainError(f"quotation {document_id} is not pending review (status {doc.status})")
    pr = documents_repo.get(doc.parent_document_id)

    lines = build_quotation_lines(pr, line_offers)
    validate_transition(DocumentType.QUOTATION, "PENDING_REVIEW", "SUBMITTED", None)

    doc.line_items = lines
    doc.amounts = compute_amounts(lines)
    doc.status = "SUBMITTED"
    if doc.extraction_provenance is not None:
        doc.extraction_provenance.status = "VERIFIED"
        doc.extraction_provenance.reviewed_by = current_user.user_id
        doc.extraction_provenance.reviewed_at = now_iso()
    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("QT", fy)
    doc.financial_year = fy
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(
        doc, event_type="EXTRACTION_CONFIRMED", from_status="PENDING_REVIEW", to_status="SUBMITTED",
        actor=current_user, source=source,
    )
    return doc


def withdraw_quotation(
    current_user: CurrentUser, quotation_id: str, reason: str, *, source: str = "api"
) -> Document:
    require_permission(current_user, "quotation:withdraw")
    doc = documents_repo.get(quotation_id, scope=build_scope(current_user))
    require_owner(current_user, doc.requester_id)
    validate_transition(DocumentType.QUOTATION, doc.status, "WITHDRAWN", reason)

    doc.status = "WITHDRAWN"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(
        doc, event_type="STATUS_CHANGED", from_status="SUBMITTED", to_status="WITHDRAWN",
        actor=current_user, reason=reason, source=source,
    )
    return doc


def get_quotation(current_user: CurrentUser, quotation_id: str) -> Document:
    require_permission(current_user, "quotation:read")
    return documents_repo.get(quotation_id, scope=build_scope(current_user))


def list_quotations(current_user: CurrentUser, *, parent_document_id: str | None = None) -> list[Document]:
    require_permission(current_user, "quotation:read")
    return documents_repo.list(
        document_type=DocumentType.QUOTATION,
        parent_document_id=parent_document_id,
        scope=build_scope(current_user),
    )
