from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, ItemMaster
from app.domain.services import item_service

router = APIRouter(prefix="/items", tags=["items"])


class CreateItemRequest(BaseModel):
    item_code: str
    description: str
    uom: str
    category: Optional[str] = None
    reference_unit_price: Optional[str] = None


class DeactivateItemRequest(BaseModel):
    reason: str


@router.post("/add_item", response_model=ItemMaster)
def create_item(
    body: CreateItemRequest, current_user: CurrentUser = Depends(get_current_user)
) -> ItemMaster:
    return item_service.create_item(
        current_user,
        item_code=body.item_code,
        description=body.description,
        uom=body.uom,
        category=body.category,
        reference_unit_price=body.reference_unit_price,
    )


@router.get("", response_model=list[ItemMaster])
def list_items(
    is_active: Optional[bool] = True, current_user: CurrentUser = Depends(get_current_user)
) -> list[ItemMaster]:
    return item_service.list_items(current_user, is_active=is_active)


@router.get("/{item_id}", response_model=ItemMaster)
def get_item(item_id: str, current_user: CurrentUser = Depends(get_current_user)) -> ItemMaster:
    return item_service.get_item(current_user, item_id)


@router.post("/{item_id}/deactivate", response_model=ItemMaster)
def deactivate_item(
    item_id: str,
    body: DeactivateItemRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> ItemMaster:
    return item_service.deactivate_item(current_user, item_id, body.reason)
