from typing import Optional

from app.ai.tools.context import current_user_ctx
from app.domain.errors import DomainError, NotAuthorizedError
from app.domain.services import item_service


def list_items(is_active: bool = True) -> str:
    """List items in the item master catalog, so you know what item codes and
    descriptions are available to reference when creating a requisition or a
    quotation.

    Args:
        is_active: If true (default), only list active items.
    """
    user = current_user_ctx.get()
    try:
        items = item_service.list_items(user, is_active=is_active)
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    if not items:
        return "No items found."
    return "\n".join(f"{i.item_id}: {i.item_code} — {i.description} ({i.uom})" for i in items)


def create_item(item_code: str, description: str, uom: str, category: Optional[str] = None) -> str:
    """Add a new item to the item master catalog. Requester/approver only —
    vendors can read the catalog but cannot add to it.

    Args:
        item_code: A unique, human-readable code, e.g. "ITM-0002".
        description: What the item is.
        uom: Unit of measure, e.g. "EA", "KG", "HR".
        category: Optional free-text grouping.
    """
    user = current_user_ctx.get()
    try:
        item = item_service.create_item(
            user, item_code=item_code, description=description, uom=uom, category=category,
            source="chat_tool",
        )
        return f"Created item {item.item_id} ({item.item_code}: {item.description})."
    except NotAuthorizedError as e:
        return f"NOT AUTHORIZED: {e}"
    except DomainError as e:
        return f"REJECTED: {e}"
