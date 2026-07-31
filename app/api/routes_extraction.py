import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.config import settings
from app.domain.errors import DomainError
from app.domain.schemas import CurrentUser, Document, DocumentType
from app.domain.services import bill_service, extraction_service, quotation_service
from app.storage.documents_repo import documents_repo

router = APIRouter(prefix="/extraction", tags=["extraction"])


class ConfirmLineBody(BaseModel):
    ref_line_no: int
    quantity: str
    unit_price: str
    tax_pct: str = "0"


class ConfirmExtractionRequest(BaseModel):
    lines: list[ConfirmLineBody]


@router.post("/upload", response_model=Document)
def upload_document(
    background_tasks: BackgroundTasks,
    target_document_type: DocumentType = Form(...),
    parent_document_id: str = Form(...),
    file: UploadFile = File(...),
    prompt: Optional[str] = Form(None),
    current_user: CurrentUser = Depends(get_current_user),
) -> Document:
    # A blank/whitespace-only prompt is treated as "not provided" — the
    # pipeline falls back to its default extraction instructions rather than
    # appending an empty block to them.
    custom_prompt = prompt.strip() if prompt is not None and prompt.strip() else None

    # Date-prefixed so uploads are sortable/browsable on disk by day, before
    # the disambiguating uuid and the original filename.
    date_prefix = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    dest = settings.UPLOAD_DIR / f"{date_prefix}_{uuid.uuid4().hex}_{file.filename}"
    with dest.open("wb") as out:
        out.write(file.file.read())

    # Returns as soon as the document is created at EXTRACTING — the actual
    # OCR + Gemini extraction (the slow part) runs after the response is
    # sent. The frontend/chat check current status by re-reading the
    # document from the store (GET /quotations/{id}, GET /bills/{id}, or the
    # check_extraction_status chat tool) once the background task lands it
    # at PENDING_REVIEW or EXTRACTION_FAILED.
    doc = extraction_service.upload_and_extract(
        current_user, dest, target_document_type, parent_document_id,
        custom_prompt=custom_prompt, source="api",
    )
    background_tasks.add_task(
        extraction_service.run_extraction_and_update, doc.id, dest, current_user,
        custom_prompt=custom_prompt, source="api",
    )
    return doc


@router.post("/{document_id}/confirm", response_model=Document)
def confirm_extraction(
    document_id: str, body: ConfirmExtractionRequest, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    doc = documents_repo.get(document_id)
    lines = [ln.model_dump() for ln in body.lines]
    if doc.document_type == DocumentType.QUOTATION:
        return quotation_service.confirm_quotation_extraction(current_user, document_id, lines)
    if doc.document_type == DocumentType.BILL:
        return bill_service.confirm_bill_extraction(current_user, document_id, lines)
    raise DomainError(f"extraction confirm is not supported for document_type {doc.document_type.value}")
