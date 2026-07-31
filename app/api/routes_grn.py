from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import grn_service

router = APIRouter(prefix="/grns", tags=["goods-receipts"])


class ReceivedLineBody(BaseModel):
    ref_line_no: int
    received_qty: str


class CreateGrnRequest(BaseModel):
    po_id: str
    received_lines: list[ReceivedLineBody]
    received_date: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str


@router.post("", response_model=Document)
def create_grn(body: CreateGrnRequest, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return grn_service.create_grn(
        current_user,
        body.po_id,
        [rl.model_dump() for rl in body.received_lines],
        received_date=body.received_date,
    )


@router.get("", response_model=list[Document])
def list_grns(
    po_id: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return grn_service.list_grns(current_user, parent_document_id=po_id)


@router.get("/{grn_id}", response_model=Document)
def get_grn(grn_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return grn_service.get_grn(current_user, grn_id)


@router.post("/{grn_id}/cancel", response_model=Document)
def cancel_grn(
    grn_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return grn_service.cancel_grn(current_user, grn_id, body.reason)
