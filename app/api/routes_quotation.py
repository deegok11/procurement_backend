from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import quotation_service

router = APIRouter(prefix="/quotations", tags=["quotations"])


class LineOfferBody(BaseModel):
    ref_line_no: int
    quantity: str
    unit_price: str
    tax_pct: str = "0"


class SubmitQuotationRequest(BaseModel):
    pr_id: str
    line_offers: list[LineOfferBody]
    currency: str = "USD"


class ReasonBody(BaseModel):
    reason: str


@router.post("", response_model=Document)
def submit_quotation(
    body: SubmitQuotationRequest, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return quotation_service.submit_quotation(
        current_user,
        body.pr_id,
        [o.model_dump() for o in body.line_offers],
        currency=body.currency,
    )


@router.get("", response_model=list[Document])
def list_quotations(
    pr_id: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return quotation_service.list_quotations(current_user, parent_document_id=pr_id)


@router.get("/{quotation_id}", response_model=Document)
def get_quotation(
    quotation_id: str, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return quotation_service.get_quotation(current_user, quotation_id)


@router.post("/{quotation_id}/withdraw", response_model=Document)
def withdraw_quotation(
    quotation_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return quotation_service.withdraw_quotation(current_user, quotation_id, body.reason)
