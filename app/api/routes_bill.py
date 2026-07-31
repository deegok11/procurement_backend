from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import bill_service

router = APIRouter(prefix="/bills", tags=["bills"])


class BilledLineBody(BaseModel):
    ref_line_no: int
    quantity: str
    unit_price: str
    tax_pct: str = "0"


class CreateBillRequest(BaseModel):
    grn_id: str
    billed_lines: list[BilledLineBody]
    invoice_number: Optional[str] = None
    invoice_date: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str


class AckBody(BaseModel):
    notes: str = ""


@router.post("", response_model=Document)
def create_bill(body: CreateBillRequest, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return bill_service.create_bill(
        current_user,
        body.grn_id,
        [bl.model_dump() for bl in body.billed_lines],
        invoice_number=body.invoice_number,
        invoice_date=body.invoice_date,
    )


@router.get("", response_model=list[Document])
def list_bills(
    grn_id: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return bill_service.list_bills(current_user, parent_document_id=grn_id)


@router.get("/{bill_id}", response_model=Document)
def get_bill(bill_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return bill_service.get_bill(current_user, bill_id)


@router.post("/{bill_id}/acknowledge-exception", response_model=Document)
def acknowledge_exception(
    bill_id: str, body: AckBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return bill_service.acknowledge_bill_exception(current_user, bill_id, notes=body.notes)


@router.post("/{bill_id}/cancel", response_model=Document)
def cancel_bill(
    bill_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return bill_service.cancel_bill(current_user, bill_id, body.reason)
