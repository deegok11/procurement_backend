from app.domain.errors import DomainError
from app.domain.permissions import require_permission
from app.domain.roles import ALL_PERMISSIONS, Role
from app.domain.schemas import CurrentUser
from app.storage.permissions_repo import permissions_repo


def get_permissions_matrix(current_user: CurrentUser) -> dict[str, list[str]]:
    require_permission(current_user, "permissions:manage")
    return permissions_repo.list_all()


def update_role_permissions(
    current_user: CurrentUser, role: Role, permissions: list[str]
) -> dict[str, list[str]]:
    require_permission(current_user, "permissions:manage")

    unknown = set(permissions) - ALL_PERMISSIONS
    if unknown:
        raise DomainError(f"unknown permission string(s): {', '.join(sorted(unknown))}")

    # Self-lockout guard: permission strings/roles are fixed in code, but
    # grants are fully runtime-editable — nothing else stops every
    # super_admin from being edited down to zero admin capability, which
    # would permanently strand the system with nobody able to manage
    # permissions again short of hand-editing data/permissions.json.
    if role == Role.SUPER_ADMIN and "permissions:manage" not in permissions:
        raise DomainError(
            "cannot remove 'permissions:manage' from super_admin — this would leave nobody "
            "able to manage permissions"
        )

    permissions_repo.set_role_permissions(role.value, permissions)
    return permissions_repo.list_all()
