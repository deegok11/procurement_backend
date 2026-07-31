from pathlib import Path
from typing import Optional

from app.ai.extraction.pipeline import run_extraction
from app.ai.guardrail import run_guardrail
from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.permissions import require_permission
from app.domain.roles import Domain, Role
from app.domain.schemas import (
    Amounts,
    CurrentUser,
    Document,
    DocumentType,
    ExtractionField,
    ExtractionProvenance,
    LineItem,
    now_iso,
)
from app.domain.services._events import log_event
from app.domain.state_machine import validate_transition
from app.storage.documents_repo import documents_repo


def upload_and_extract(
    current_user: CurrentUser,
    pdf_path: Path,
    target_document_type: DocumentType,
    parent_document_id: str,
    *,
    custom_prompt: Optional[str] = None,
    source: str = "api",
) -> Document:
    """Validates the upload and creates the document immediately at
    status=EXTRACTING — the slow part (OCR -> PII-redact -> Gemini-extract)
    runs afterwards in a background task (see run_extraction_and_update) so
    the HTTP request doesn't block on the LLM call. P4 still holds: nothing
    here is trusted into a comparison, a PO, or a payment until a human
    confirms it via the /confirm endpoint once the background job lands the
    document at PENDING_REVIEW.

    custom_prompt: optional uploader-supplied extra instructions for the
    extraction model (already trimmed/blank-checked by the route — never an
    empty string here, only a real value or None). Recorded on the document
    for provenance and handed to run_extraction_and_update to actually
    influence the Gemini call."""
    require_permission(current_user, "extraction:upload")

    if target_document_type == DocumentType.QUOTATION:
        if current_user.role != Role.VENDOR:
            raise NotAuthorizedError("only a vendor may upload a quotation PDF")
        pr = documents_repo.get(parent_document_id)
        if pr.document_type != DocumentType.PR:
            raise DomainError(f"{parent_document_id} is not a PR")
        if pr.status != "APPROVED":
            raise DomainError(f"PR must be APPROVED before quoting (currently {pr.status})")
        invited = set(pr.extra.get("invited_vendor_ids") or [])
        if current_user.vendor_id not in invited:
            raise NotAuthorizedError("this vendor was not invited to quote on this PR")
        domain, vendor_id, root_pr_id, series_code = (
            Domain.VENDOR, current_user.vendor_id, pr.root_pr_id or pr.id, "QT",
        )
        title = f"Quotation for {pr.title} (extracting…)"
    elif target_document_type == DocumentType.BILL:
        if current_user.role != Role.REQUESTER:
            raise NotAuthorizedError("only a requester may upload a bill PDF")
        grn = documents_repo.get(parent_document_id)
        if grn.document_type != DocumentType.GRN_SRN:
            raise DomainError(f"{parent_document_id} is not a GRN/SRN")
        domain, vendor_id, root_pr_id, series_code = (
            Domain.INTERNAL, grn.vendor_id, grn.root_pr_id, "BILL",
        )
        title = f"Bill for {grn.document_number or grn.id} (extracting…)"
    else:
        raise DomainError(f"extraction is not supported for document_type {target_document_type.value}")

    doc = Document(
        document_type=target_document_type,
        series_code=series_code,
        parent_document_id=parent_document_id,
        root_pr_id=root_pr_id,
        domain=domain,
        vendor_id=vendor_id,
        status="EXTRACTING",
        requester_id=current_user.user_id,
        title=title,
        currency="USD",
        line_items=[],
        amounts=Amounts(),
        extra={"extraction_prompt": custom_prompt} if custom_prompt else {},
        created_by=current_user.user_id,
        updated_by=current_user.user_id,
    )
    documents_repo.add(doc)
    log_event(
        doc, event_type="CREATED", from_status=None, to_status="EXTRACTING",
        actor=current_user, source=source,
    )
    return doc


def run_extraction_and_update(
    document_id: str,
    pdf_path: Path,
    current_user: CurrentUser,
    *,
    custom_prompt: Optional[str] = None,
    source: str = "api",
) -> None:
    """The slow half of the upload — meant to be scheduled as a background
    task by the route handler, never awaited inline. Runs the OCR -> redact
    -> Gemini pipeline, then reads the document back from the store (its
    canonical, current state) and updates it in place: PENDING_REVIEW on
    success, EXTRACTION_FAILED (with the error recorded in extra) if the
    pipeline raises. Either way this is the only place that writes the
    extraction result, so a slow/failed run can never race a human action
    taken in the EXTRACTING window (there isn't one — no route accepts an
    EXTRACTING document as input to anything but a read).

    custom_prompt: passed through the same scope guardrail used for chat
    (run_guardrail) before it ever reaches run_extraction — an uploader hint
    that isn't actually about procurement/reading the document is dropped
    (custom_prompt reset to None) rather than forwarded into the extraction
    LLM call. This never blocks the upload itself, only what gets appended
    to the model prompt; see run_extraction/EXTRACTION_PROMPT for how a
    surviving custom_prompt is appended. None means "use the default
    extraction instructions only," which is also what an empty/
    whitespace-only value collapses to before it ever reaches here."""
    doc = documents_repo.get_unscoped(document_id)

    try:
        if custom_prompt:
            guardrail = run_guardrail(custom_prompt, [])
            if guardrail.category != "in_scope":
                custom_prompt = None
        result = run_extraction(pdf_path, custom_prompt=custom_prompt)
    except Exception as e:  # noqa: BLE001 — any failure here must land as EXTRACTION_FAILED, not a crash
        validate_transition(doc.document_type, doc.status, "EXTRACTION_FAILED", str(e))
        doc.status = "EXTRACTION_FAILED"
        doc.title = doc.title.replace(" (extracting…)", " (extraction failed)")
        doc.extra["extraction_error"] = str(e)
        doc.updated_at = now_iso()
        doc.updated_by = current_user.user_id
        documents_repo.update(doc)
        log_event(
            doc, event_type="STATUS_CHANGED", from_status="EXTRACTING", to_status="EXTRACTION_FAILED",
            actor=current_user, reason=str(e), source=source,
        )
        return

    preview_lines = [
        LineItem(
            line_no=idx,
            ref_line_no=None,  # not yet linked to a parent line — the human sets this on confirm
            item_id=None,
            description=li.get("description", ""),
            uom=li.get("uom", ""),
            quantity=li.get("quantity", "0"),
            unit_price=li.get("unit_price"),
            tax_pct=li.get("tax_pct"),
        )
        for idx, li in enumerate(result.line_items, start=1)
    ]
    fields = [
        ExtractionField(
            field_name=f"line_item[{idx}].{key}",
            value=str(li.get(key)),
            confidence=float(li.get("confidence", 0)),
            page_number=li.get("page_number"),
        )
        for idx, li in enumerate(result.line_items, start=1)
        for key in ("description", "quantity", "unit_price", "tax_pct")
        if li.get(key) is not None
    ]

    validate_transition(doc.document_type, doc.status, "PENDING_REVIEW", None)
    doc.status = "PENDING_REVIEW"
    doc.title = doc.title.replace(" (extracting…)", " (pending review)")
    doc.currency = result.currency or doc.currency
    doc.line_items = preview_lines
    doc.extra.update({
        "vendor_name_extracted": result.vendor_name,
        "vendor_address_extracted": result.vendor_address,
        "vendor_business_notes_extracted": result.vendor_business_notes,
        "document_number_extracted": result.document_number,
    })
    doc.extraction_provenance = ExtractionProvenance(
        model=result.model,
        request_id=result.request_id,
        fields=fields,
        status="PENDING_REVIEW",
        redaction_summary=result.redaction_summary,
    )
    doc.updated_at = now_iso()
    doc.updated_by = current_user.user_id
    documents_repo.update(doc)
    log_event(
        doc, event_type="STATUS_CHANGED", from_status="EXTRACTING", to_status="PENDING_REVIEW",
        actor=current_user, source=source,
        metadata={"extraction_model": result.model, "redaction_summary": result.redaction_summary},
    )
