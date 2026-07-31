from typing import Optional

from app.domain.errors import DomainError
from app.domain.permissions import (
    build_scope,
    require_not_self_approval,
    require_owner,
    require_permission,
    require_within_approval_threshold,
)
from app.domain.roles import Domain
from app.domain.schemas import CurrentUser, Document, DocumentType, LineItem, now_iso
from app.domain.services._events import log_event as _log
from app.domain.services._pricing import compute_amounts, compute_line_total
from app.domain.state_machine import validate_transition
from app.storage.counters_repo import counters_repo, current_financial_year
from app.storage.documents_repo import documents_repo


class LineItemInput:
    """Plain input shape accepted from routes/tools before it's turned into a
    priced LineItem — kept separate from the persisted LineItem model since
    callers don't supply line_no/line_total/ref_line_no."""

    def __init__(
        self,
        *,
        item_id: Optional[str],
        description: str,
        uom: str,
        quantity: str,
        unit_price: str,
        tax_pct: str = "0",
    ):
        self.item_id = item_id
        self.description = description
        self.uom = uom
        self.quantity = quantity
        self.unit_price = unit_price
        self.tax_pct = tax_pct


def _build_priced_line_items(inputs: list[LineItemInput]) -> list[LineItem]:
    if not inputs:
        raise DomainError("a requisition must have at least one line item")
    lines = []
    for idx, inp in enumerate(inputs, start=1):
        lines.append(
            LineItem(
                line_no=idx,
                item_id=inp.item_id,
                description=inp.description,
                uom=inp.uom,
                quantity=inp.quantity,
                unit_price=inp.unit_price,
                line_total=compute_line_total(inp.quantity, inp.unit_price, inp.tax_pct),
                tax_pct=inp.tax_pct,
            )
        )
    return lines


def create_pr_draft(
    current_user: CurrentUser,
    *,
    title: str,
    line_items: list[LineItemInput],
    currency: str = "USD",
    needed_by_date: Optional[str] = None,
    source: str = "api",
) -> Document:
    require_permission(current_user, "pr:create")
    lines = _build_priced_line_items(line_items)
    doc = Document(
        document_type=DocumentType.PR,
        series_code="PR",
        domain=Domain.INTERNAL,
        status="DRAFT",
        requester_id=current_user.user_id,
        title=title,
        currency=currency,
        line_items=lines,
        amounts=compute_amounts(lines),
        extra={"needed_by_date": needed_by_date, "invited_vendor_ids": []},
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    doc.root_pr_id = doc.id
    documents_repo.add(doc)
    _log(doc, event_type="CREATED", from_status=None, to_status="DRAFT", actor=current_user, source=source)
    return doc


def submit_pr(current_user: CurrentUser, pr_id: str, *, source: str = "api") -> Document:
    require_permission(current_user, "pr:submit")
    doc = documents_repo.get(pr_id)
    require_owner(current_user, doc.requester_id)
    validate_transition(DocumentType.PR, doc.status, "SUBMITTED", None)

    fy = current_financial_year()
    doc.document_number = counters_repo.next_document_number("PR", fy)
    doc.financial_year = fy
    doc.status = "SUBMITTED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    _log(doc, event_type="STATUS_CHANGED", from_status="DRAFT", to_status="SUBMITTED", actor=current_user, source=source)
    return doc


def approve_pr(current_user: CurrentUser, pr_id: str, *, notes: str = "", source: str = "api") -> Document:
    require_permission(current_user, "pr:approve")
    doc = documents_repo.get(pr_id)
    require_not_self_approval(current_user, doc.requester_id)
    require_within_approval_threshold(current_user, doc.amounts.grand_total)
    validate_transition(DocumentType.PR, doc.status, "APPROVED", None)

    doc.status = "APPROVED"
    doc.approver_id = current_user.user_id
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    _log(
        doc, event_type="STATUS_CHANGED", from_status="SUBMITTED", to_status="APPROVED",
        actor=current_user, reason=notes or None, source=source,
    )
    return doc


def reject_pr(current_user: CurrentUser, pr_id: str, reason: str, *, source: str = "api") -> Document:
    require_permission(current_user, "pr:reject")
    doc = documents_repo.get(pr_id)
    validate_transition(DocumentType.PR, doc.status, "REJECTED", reason)

    doc.status = "REJECTED"
    doc.approver_id = current_user.user_id
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    _log(doc, event_type="STATUS_CHANGED", from_status="SUBMITTED", to_status="REJECTED", actor=current_user, reason=reason, source=source)
    return doc


def cancel_pr(current_user: CurrentUser, pr_id: str, reason: str, *, source: str = "api") -> Document:
    require_permission(current_user, "pr:cancel")
    doc = documents_repo.get(pr_id)
    if current_user.role.value == "requester":
        require_owner(current_user, doc.requester_id)
    validate_transition(DocumentType.PR, doc.status, "CANCELLED", reason)

    from_status = doc.status
    doc.status = "CANCELLED"
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    _log(doc, event_type="CANCELLED", from_status=from_status, to_status="CANCELLED", actor=current_user, reason=reason, source=source)
    return doc


def invite_vendors_to_pr(
    current_user: CurrentUser, pr_id: str, vendor_ids: list[str], *, source: str = "api"
) -> Document:
    require_permission(current_user, "pr:invite_vendors")
    doc = documents_repo.get(pr_id)
    require_owner(current_user, doc.requester_id)
    if doc.status != "APPROVED":
        raise DomainError(f"PR must be APPROVED before inviting vendors (currently {doc.status})")

    existing = set(doc.extra.get("invited_vendor_ids") or [])
    doc.extra["invited_vendor_ids"] = sorted(existing | set(vendor_ids))
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    _log(
        doc, event_type="FIELD_UPDATED", from_status=doc.status, to_status=doc.status,
        actor=current_user, source=source, metadata={"invited_vendor_ids": vendor_ids},
    )
    return doc


def get_pr(current_user: CurrentUser, pr_id: str) -> Document:
    require_permission(current_user, "pr:read")
    return documents_repo.get(pr_id, scope=build_scope(current_user))


def list_prs(current_user: CurrentUser) -> list[Document]:
    require_permission(current_user, "pr:read")
    return documents_repo.list(document_type=DocumentType.PR, scope=build_scope(current_user))


def compare_quotations(current_user: CurrentUser, pr_id: str) -> list[Document]:
    require_permission(current_user, "quotation:compare")
    documents_repo.get(pr_id)  # 404s if the PR doesn't exist
    quotations = documents_repo.list(
        document_type=DocumentType.QUOTATION,
        parent_document_id=pr_id,
    )
    comparable = [q for q in quotations if q.status in {"SUBMITTED", "SELECTED"}]
    return sorted(comparable, key=lambda q: float(q.amounts.grand_total))
