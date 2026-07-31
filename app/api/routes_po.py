from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import po_service

router = APIRouter(prefix="/pos", tags=["purchase-orders"])


class CreatePoRequest(BaseModel):
    quotation_id: str
    payment_terms: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str


@router.post("", response_model=Document)
def create_po(body: CreatePoRequest, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return po_service.create_po_from_quotation(
        current_user, body.quotation_id, payment_terms=body.payment_terms
    )


@router.get("", response_model=list[Document])
def list_pos(
    quotation_id: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return po_service.list_pos(current_user, parent_document_id=quotation_id)


@router.get("/{po_id}", response_model=Document)
def get_po(po_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return po_service.get_po(current_user, po_id)


@router.post("/{po_id}/cancel", response_model=Document)
def cancel_po(
    po_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return po_service.cancel_po(current_user, po_id, body.reason)
