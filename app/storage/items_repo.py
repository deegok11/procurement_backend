from typing import Optional

from app.config import settings
from app.domain.errors import NotFoundError
from app.domain.schemas import ItemMaster
from app.storage.json_store import JsonFileStore

_store = JsonFileStore(settings.items_file, "items")


class ItemsRepository:
    def add(self, item: ItemMaster) -> ItemMaster:
        def _op(items: list[dict]) -> None:
            items.append(item.model_dump(mode="json"))

        _store.mutate(_op)
        return item

    def get(self, item_id: str) -> ItemMaster:
        for raw in _store.read_all():
            if raw["item_id"] == item_id:
                return ItemMaster.model_validate(raw)
        raise NotFoundError(f"item {item_id} not found")

    def get_by_code(self, item_code: str) -> Optional[ItemMaster]:
        for raw in _store.read_all():
            if raw["item_code"] == item_code:
                return ItemMaster.model_validate(raw)
        return None

    def list(self, *, is_active: Optional[bool] = None) -> list[ItemMaster]:
        items = [ItemMaster.model_validate(raw) for raw in _store.read_all()]
        if is_active is not None:
            items = [i for i in items if i.is_active == is_active]
        return items

    def update(self, item: ItemMaster) -> ItemMaster:
        def _op(items: list[dict]) -> None:
            for idx, raw in enumerate(items):
                if raw["item_id"] == item.item_id:
                    items[idx] = item.model_dump(mode="json")
                    return
            raise NotFoundError(f"item {item.item_id} not found")

        _store.mutate(_op)
        return item


items_repo = ItemsRepository()
