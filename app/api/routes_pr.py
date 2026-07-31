from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document
from app.domain.services import pr_service
from app.domain.services.pr_service import LineItemInput

router = APIRouter(prefix="/prs", tags=["purchase-requisitions"])


class LineItemBody(BaseModel):
    item_id: Optional[str] = None
    description: str
    uom: str
    quantity: str
    unit_price: str
    tax_pct: str = "0"


class CreatePrRequest(BaseModel):
    title: str
    line_items: list[LineItemBody]
    currency: str = "USD"
    needed_by_date: Optional[str] = None


class ReasonBody(BaseModel):
    reason: str


class ApproveBody(BaseModel):
    notes: str = ""


class InviteVendorsBody(BaseModel):
    vendor_ids: list[str]


@router.post("", response_model=Document)
def create_pr(body: CreatePrRequest, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    inputs = [
        LineItemInput(
            item_id=li.item_id, description=li.description, uom=li.uom,
            quantity=li.quantity, unit_price=li.unit_price, tax_pct=li.tax_pct,
        )
        for li in body.line_items
    ]
    return pr_service.create_pr_draft(
        current_user, title=body.title, line_items=inputs,
        currency=body.currency, needed_by_date=body.needed_by_date,
    )


@router.get("", response_model=list[Document])
def list_prs(current_user: CurrentUser = Depends(get_current_user)) -> list[Document]:
    return pr_service.list_prs(current_user)


@router.get("/{pr_id}", response_model=Document)
def get_pr(pr_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return pr_service.get_pr(current_user, pr_id)


@router.post("/{pr_id}/submit", response_model=Document)
def submit_pr(pr_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return pr_service.submit_pr(current_user, pr_id)


@router.post("/{pr_id}/approve", response_model=Document)
def approve_pr(
    pr_id: str, body: ApproveBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return pr_service.approve_pr(current_user, pr_id, notes=body.notes)


@router.post("/{pr_id}/reject", response_model=Document)
def reject_pr(
    pr_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return pr_service.reject_pr(current_user, pr_id, body.reason)


@router.post("/{pr_id}/cancel", response_model=Document)
def cancel_pr(
    pr_id: str, body: ReasonBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return pr_service.cancel_pr(current_user, pr_id, body.reason)


@router.post("/{pr_id}/invite-vendors", response_model=Document)
def invite_vendors(
    pr_id: str, body: InviteVendorsBody, current_user: CurrentUser = Depends(get_current_user)
) -> Document:
    return pr_service.invite_vendors_to_pr(current_user, pr_id, body.vendor_ids)


@router.get("/{pr_id}/compare-quotations", response_model=list[Document])
def compare_quotations(
    pr_id: str, current_user: CurrentUser = Depends(get_current_user)
) -> list[Document]:
    return pr_service.compare_quotations(current_user, pr_id)
