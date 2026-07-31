from app.config import settings
from app.storage.json_store import JsonFileStore

_store = JsonFileStore(settings.permissions_file, "role_permissions")


class PermissionsRepository:
    """One record per role: {"role": "requester", "permissions": ["item:read", ...]}.
    A plain list-of-dicts, same shape JsonFileStore already handles for every
    other collection — no bespoke storage needed for this one case."""

    def _ensure_seeded(self) -> list[dict]:
        items = _store.read_all()
        if items:
            return items
        # First-ever read (fresh deployment, or a fresh test DATA_DIR) — bootstrap
        # from the built-in defaults so nobody ever starts locked out of
        # everything. Deferred import: app.domain.roles imports this module at
        # module level (has_permission reads through it), so importing roles.py
        # back at *this* module's top level would be circular; a function-local
        # import here resolves fine since by the time this actually runs both
        # modules have finished loading.
        from app.domain.roles import DEFAULT_ROLE_PERMISSIONS

        seeded = [
            {"role": role.value, "permissions": sorted(perms)}
            for role, perms in DEFAULT_ROLE_PERMISSIONS.items()
        ]
        _store.mutate(lambda current: current.extend(seeded))
        return seeded

    def get_role_permissions(self, role: str) -> list[str]:
        for raw in self._ensure_seeded():
            if raw["role"] == role:
                return raw["permissions"]
        return []

    def list_all(self) -> dict[str, list[str]]:
        return {raw["role"]: raw["permissions"] for raw in self._ensure_seeded()}

    def set_role_permissions(self, role: str, permissions: list[str]) -> None:
        self._ensure_seeded()  # make sure every other role's row already exists
        deduped = sorted(set(permissions))

        def _op(items: list[dict]) -> None:
            for raw in items:
                if raw["role"] == role:
                    raw["permissions"] = deduped
                    return
            items.append({"role": role, "permissions": deduped})

        _store.mutate(_op)


permissions_repo = PermissionsRepository()
