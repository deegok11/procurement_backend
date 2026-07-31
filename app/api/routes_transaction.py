from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import transaction_service

router = APIRouter(prefix="/transactions", tags=["transactions"])


class CreateTransactionRequest(BaseModel):
    bill_id: str
    amount: str
    payment_method: Optional[str] = None
    reference_number: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str


@router.post("", response_model=Document)
def create_transaction(
    body: CreateTransactionRequest, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return transaction_service.create_transaction(
        current_user, body.bill_id, body.amount,
        payment_method=body.payment_method, reference_number=body.reference_number,
    )


@router.get("", response_model=list[Document])
def list_transactions(
    bill_id: Optional[str] = None, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return transaction_service.list_transactions(current_user, parent_document_id=bill_id)


@router.get("/{transaction_id}", response_model=Document)
def get_transaction(
    transaction_id: str, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return transaction_service.get_transaction(current_user, transaction_id)


@router.post("/{transaction_id}/cancel", response_model=Document)
def cancel_transaction(
    transaction_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return transaction_service.cancel_transaction(current_user, transaction_id, body.reason)
