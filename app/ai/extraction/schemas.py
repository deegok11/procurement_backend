from typing import Optional

from pydantic import BaseModel, Field

EXTRACTION_PROMPT = (
    "The following is OCR-extracted text from a vendor-supplied procurement document "
    "(a quotation or a bill/invoice). Some fields (phone numbers, emails, tax/bank IDs) "
    "have already been redacted for privacy and appear as [REDACTED:<TYPE>] placeholders "
    "in the text below — do not attempt to guess or reconstruct their original values; "
    "leave the corresponding output field blank/null if the source was redacted.\n\n"
    "Identify: the vendor's business details (name, address, and any other identifying "
    "business information visible in the text), the document's own number/date, its "
    "currency, and every line item (description, unit of measure, quantity, unit price, "
    "tax percentage). For every line item, include a self-reported confidence between 0 "
    "and 1, and the page_number (from the '--- PAGE N ---' markers in the text below) it "
    "was found on, if determinable.\n\n"
    "--- DOCUMENT TEXT ---\n{document_text}\n--- END DOCUMENT TEXT ---"
)


class ExtractedVendorDetails(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    business_notes: Optional[str] = Field(
        default=None,
        description="Any other business-identifying text visible (e.g. registration "
        "details) that wasn't redacted.",
    )


class ExtractedLineItem(BaseModel):
    description: str
    uom: str
    quantity: str
    unit_price: str
    tax_pct: str = "0"
    confidence: float = Field(description="Self-reported confidence, 0-1.")
    page_number: Optional[int] = None


class ExtractedDocument(BaseModel):
    vendor: ExtractedVendorDetails
    document_number: Optional[str] = None
    document_date: Optional[str] = None
    currency: Optional[str] = None
    line_items: list[ExtractedLineItem]
