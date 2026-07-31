from typing import Optional

from app.domain.errors import DomainError
from app.domain.permissions import require_permission
from app.domain.schemas import CurrentUser, EventRecord, ItemMaster
from app.storage.events_repo import events_repo
from app.storage.items_repo import items_repo


def create_item(
    current_user: CurrentUser,
    *,
    item_code: str,
    description: str,
    uom: str,
    category: Optional[str] = None,
    reference_unit_price: Optional[str] = None,
    source: str = "api",
) -> ItemMaster:
    require_permission(current_user, "item:create")

    if items_repo.get_by_code(item_code) is not None:
        raise DomainError(f"item_code '{item_code}' already exists")

    item = ItemMaster(
        item_code=item_code,
        description=description,
        uom=uom,
        category=category,
        reference_unit_price=reference_unit_price,
        created_by=current_user.user_id,
    )
    items_repo.add(item)
    events_repo.append(
        EventRecord(
            document_id=item.item_id,
            document_type="ITEM",
            event_type="CREATED",
            to_status="ACTIVE",
            actor_user_id=current_user.user_id,
            actor_role=current_user.role.value,
            metadata={"item_code": item_code},
            source=source,
        )
    )
    return item


def list_items(current_user: CurrentUser, *, is_active: Optional[bool] = True) -> list[ItemMaster]:
    require_permission(current_user, "item:read")
    return items_repo.list(is_active=is_active)


def get_item(current_user: CurrentUser, item_id: str) -> ItemMaster:
    require_permission(current_user, "item:read")
    return items_repo.get(item_id)


def deactivate_item(
    current_user: CurrentUser, item_id: str, reason: str, *, source: str = "api"
) -> ItemMaster:
    require_permission(current_user, "item:create")  # same permission governs master-data writes
    if not reason or not reason.strip():
        raise DomainError("a reason is required to deactivate an item")

    item = items_repo.get(item_id)
    item.is_active = False
    items_repo.update(item)
    events_repo.append(
        EventRecord(
            document_id=item.item_id,
            document_type="ITEM",
            event_type="DEACTIVATED",
            from_status="ACTIVE",
            to_status="INACTIVE",
            actor_user_id=current_user.user_id,
            actor_role=current_user.role.value,
            reason=reason,
            source=source,
        )
    )
    return item
