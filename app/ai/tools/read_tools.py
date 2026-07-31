from typing import Optional

from app.ai.tools.context import current_user_ctx
from app.domain.errors import NotAuthorizedError
from app.domain.schemas import DocumentType
from app.domain.services import document_service


def get_document(document_id: str) -> str:
    """Look up any document (PR, QUOTATION, PO, GRN_SRN, BILL, or
    TRANSACTION) by its id. Tenant-scoped — a vendor can only see documents
    that concern them. Requires the read permission for that document's own
    type (e.g. "bill:read" for a bill) — the same check its type-specific
    REST route enforces.

    Args:
        document_id: The document's id.
    """
    user = current_user_ctx.get()
    try:
        doc = document_service.get_document(user, document_id)
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except Exception as e:  # NotFoundError etc. — surfaced as a normal tool result, not a crash
        return f"NOT FOUND: {e}"
    return (
        f"{doc.id} ({doc.document_type.value} {doc.document_number or '(unnumbered)'}): "
        f"status={doc.status}, total={doc.amounts.grand_total} {doc.currency}, "
        f"vendor={doc.vendor_id}, parent={doc.parent_document_id}"
    )


def list_documents(
    document_type: Optional[str] = None,
    status: Optional[str] = None,
    parent_document_id: Optional[str] = None,
) -> str:
    """List documents, optionally filtered. Tenant-scoped — a vendor only
    sees documents that concern them plus PRs they're invited to. If
    document_type is omitted, results are narrowed to whatever types this
    role has read access to.

    Args:
        document_type: One of PR, QUOTATION, PO, GRN_SRN, BILL, TRANSACTION. Omit for all types.
        status: Filter by status, e.g. "SUBMITTED". Omit for all statuses.
        parent_document_id: Filter to children of a specific document.
    """
    user = current_user_ctx.get()
    try:
        dt = DocumentType(document_type) if document_type else None
        docs = document_service.list_documents(
            user, document_type=dt, status=status, parent_document_id=parent_document_id,
        )
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except ValueError as e:
        return f"Invalid document_type: {e}"
    if not docs:
        return "No documents found."
    return "\n".join(
        f"{d.id} ({d.document_type.value} {d.document_number or '(unnumbered)'}): status={d.status}"
        for d in docs
    )


def check_extraction_status(document_id: str) -> str:
    """Check the status of a document created by uploading a vendor PDF
    (a quotation or bill run through the OCR -> redact -> extract pipeline).
    Reports whether it's still PENDING_REVIEW (awaiting human confirmation
    via the extraction confirm endpoint) or already VERIFIED, a preview of
    the extracted fields with confidence, and a summary of what PII was
    redacted before any of it reached the extraction model. Upload and
    confirm themselves happen outside chat (file bytes and the final
    human sign-off aren't chat actions) — this tool is read-only.

    Args:
        document_id: The document's id, returned when the file was uploaded.
    """
    user = current_user_ctx.get()
    try:
        doc = document_service.get_document(user, document_id)
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except Exception as e:  # NotFoundError etc. — surfaced as a normal tool result, not a crash
        return f"NOT FOUND: {e}"

    if doc.status == "EXTRACTING":
        return (
            f"{doc.id} ({doc.document_type.value}): still extracting — OCR and the Gemini extraction "
            "call are running in the background. Check back shortly; it'll move to PENDING_REVIEW "
            "(ready for human confirmation) or EXTRACTION_FAILED."
        )
    if doc.status == "EXTRACTION_FAILED":
        error = doc.extra.get("extraction_error", "unknown error")
        return f"{doc.id} ({doc.document_type.value}): extraction failed — {error}. Re-upload to retry."

    prov = doc.extraction_provenance
    if prov is None:
        return f"{doc.id} was not created via AI extraction — nothing to check."

    lines = [
        f"{doc.id} ({doc.document_type.value}): extraction status = {prov.status}, "
        f"document status = {doc.status}, model = {prov.model or 'unknown'}",
    ]
    if prov.status == "PENDING_REVIEW":
        lines.append(
            "Awaiting human confirmation (via the extraction confirm endpoint) before it "
            "can be compared, converted to a PO, or matched/paid."
        )
    if prov.redaction_summary:
        redacted = ", ".join(f"{k}: {v}" for k, v in prov.redaction_summary.items())
        lines.append(f"PII redacted before this reached the extraction model — {redacted}.")
    else:
        lines.append("No PII patterns were found/redacted in this document.")

    low_confidence = [f for f in prov.fields if f.confidence < 0.7]
    if low_confidence:
        lines.append(
            "Low-confidence fields worth double-checking: "
            + "; ".join(f"{f.field_name}={f.value} (confidence {f.confidence:.2f})" for f in low_confidence)
        )
    return "\n".join(lines)
