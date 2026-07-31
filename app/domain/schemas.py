from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.domain.roles import Domain, Role


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:12]}"


class CurrentUser(BaseModel):
    """Identity + authorization context for the calling user, attached to
    request.state by the auth middleware and threaded through to every
    service call (REST route or chat tool)."""

    user_id: str
    username: str
    role: Role
    domain: Domain
    vendor_id: Optional[str] = None
    approval_level: Optional[int] = None


class DocumentType(str, Enum):
    PR = "PR"
    QUOTATION = "QUOTATION"
    PO = "PO"
    GRN_SRN = "GRN_SRN"
    BILL = "BILL"
    TRANSACTION = "TRANSACTION"


SERIES_CODE = {
    DocumentType.PR: "PR",
    DocumentType.QUOTATION: "QT",
    DocumentType.PO: "PO",
    DocumentType.GRN_SRN: "GRN",
    DocumentType.BILL: "BILL",
    DocumentType.TRANSACTION: "TXN",
}


class LineItem(BaseModel):
    line_no: int
    ref_line_no: Optional[int] = None
    item_id: Optional[str] = None  # references ItemMaster.item_id; null for an unmapped free-text line
    description: str
    uom: str
    quantity: str  # Decimal-as-string; meaning is stage-dependent (requested/offered/ordered/received/billed)
    unit_price: Optional[str] = None
    line_total: Optional[str] = None
    tax_pct: Optional[str] = None
    extra: dict[str, Any] = Field(default_factory=dict)


class Amounts(BaseModel):
    subtotal: str = "0"
    tax_total: str = "0"
    grand_total: str = "0"


class SoftDelete(BaseModel):
    is_deleted: bool = False
    reason: Optional[str] = None
    deleted_by: Optional[str] = None
    deleted_at: Optional[str] = None


class ExtractionField(BaseModel):
    field_name: str
    value: str
    confidence: float
    page_number: Optional[int] = None
    # No bounding_box: extraction reads OCR'd text (Tesseract), not the PDF's
    # visual layout, so there's no pixel geometry to report.


class ExtractionProvenance(BaseModel):
    source: str = "ai_extraction"
    model: str
    request_id: Optional[str] = None
    fields: list[ExtractionField] = Field(default_factory=list)
    # Per-PII-type counts of what was redacted from the OCR text before it
    # was sent to the LLM (e.g. {"GSTIN": 1, "MOBILE": 2}) — never the
    # matched values themselves, just an audit trail that redaction happened.
    redaction_summary: dict[str, int] = Field(default_factory=dict)
    status: str = "PENDING_REVIEW"  # PENDING_REVIEW | VERIFIED
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[str] = None


class Document(BaseModel):
    id: str = Field(default_factory=lambda: new_id("doc"))
    document_type: DocumentType
    document_number: Optional[str] = None
    series_code: str
    financial_year: Optional[str] = None
    parent_document_id: Optional[str] = None
    root_pr_id: Optional[str] = None
    domain: Domain
    vendor_id: Optional[str] = None
    status: str
    requester_id: str
    approver_id: Optional[str] = None
    title: str
    currency: str = "USD"
    line_items: list[LineItem] = Field(default_factory=list)
    amounts: Amounts = Field(default_factory=Amounts)
    extra: dict[str, Any] = Field(default_factory=dict)
    extraction_provenance: Optional[ExtractionProvenance] = None
    soft_delete: SoftDelete = Field(default_factory=SoftDelete)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    created_by: str
    updated_by: str


class ItemMaster(BaseModel):
    item_id: str = Field(default_factory=lambda: new_id("itm"))
    item_code: str
    description: str
    uom: str
    category: Optional[str] = None
    reference_unit_price: Optional[str] = None
    is_active: bool = True
    created_at: str = Field(default_factory=now_iso)
    created_by: str


class EventRecord(BaseModel):
    event_id: str = Field(default_factory=lambda: new_id("evt"))
    document_id: Optional[str] = None
    document_type: Optional[str] = None
    event_type: str
    from_status: Optional[str] = None
    to_status: Optional[str] = None
    actor_user_id: str
    actor_role: str
    reason: Optional[str] = None
    diff: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)
    source: str  # api | chat_tool | extraction_pipeline | system
    timestamp: str = Field(default_factory=now_iso)
