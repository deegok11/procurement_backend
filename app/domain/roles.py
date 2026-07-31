from enum import Enum


class Role(str, Enum):
    REQUESTER = "requester"
    APPROVER = "approver"
    VENDOR = "vendor"
    SUPER_ADMIN = "super_admin"


class Domain(str, Enum):
    INTERNAL = "internal"
    VENDOR = "vendor"


# Permission strings are "resource:action" — one entry per REST route / chat tool.
#
# This used to be the actual runtime source of truth (a hardcoded dict), read
# directly by has_permission(). It's now only the *bootstrap* default — the
# first time app/storage/permissions_repo.py is ever read (a fresh deployment,
# or a fresh test DATA_DIR), it seeds data/permissions.json from exactly this
# dict, and from then on the JSON file is what has_permission() actually
# checks. Editing this dict after a system has already booted once has no
# effect — permissions are managed at runtime instead (super_admin role,
# permissions:manage permission, PUT /permissions/{role} — see
# app/domain/services/permissions_service.py). Kept here, not inline in
# permissions_repo.py, because ALL_PERMISSIONS (below) is derived from it and
# both are conceptually "the fixed vocabulary of roles/permissions this system
# knows about" — only the *grants* (which role has which permission) are
# runtime-editable, not the roles or permission strings themselves.
#
# Reading a document used to be gated by one blanket "document:read" permission
# shared by every document type. It's now one "<type>:read" permission per level
# of the procurement lifecycle (pr/quotation/po/grn/bill/transaction), so a
# role's read access can be tuned per type instead of all-or-nothing.
DEFAULT_ROLE_PERMISSIONS: dict[Role, frozenset[str]] = {
    Role.REQUESTER: frozenset(
        {
            "item:read",
            "item:create",
            "pr:create",
            "pr:submit",
            "pr:cancel",
            "pr:invite_vendors",
            "pr:read",
            "quotation:compare",
            "quotation:read",
            "po:create",
            "po:cancel",
            "po:read",
            "grn:create",
            "grn:cancel",
            "grn:read",
            "bill:create",
            "bill:cancel",
            "bill:read",
            "transaction:read",
            "extraction:upload",
            "extraction:confirm",
            "chat:use",
        }
    ),
    Role.APPROVER: frozenset(
        {
            "item:read",
            "item:create",
            "pr:approve",
            "pr:reject",
            "pr:cancel",
            "pr:read",
            "quotation:compare",
            "quotation:read",
            "po:cancel",
            "po:read",
            "grn:cancel",
            "grn:read",
            "bill:acknowledge_exception",
            "bill:cancel",
            "bill:read",
            "transaction:create",
            "transaction:cancel",
            "transaction:read",
            "chat:use",
        }
    ),
    Role.VENDOR: frozenset(
        {
            "item:read",
            "quotation:submit",
            "quotation:withdraw",
            "quotation:read",
            "pr:read",
            "po:read",
            "grn:read",
            "bill:read",
            "transaction:read",
            "extraction:upload",
            "chat:use",
        }
    ),
    # Deliberately a pure administrative role: permissions:manage plus
    # read-only visibility across every document type, and nothing that
    # creates/approves/cancels/uploads anything. Keeps its blast radius small
    # and its purpose unambiguous — it manages who can do what, it doesn't do
    # the procurement work itself.
    Role.SUPER_ADMIN: frozenset(
        {
            "permissions:manage",
            "item:read",
            "pr:read",
            "quotation:read",
            "po:read",
            "grn:read",
            "bill:read",
            "transaction:read",
            "chat:use",
        }
    ),
}

# The fixed vocabulary of every permission string that exists anywhere in the
# system — what PUT /permissions/{role} validates a new grant list against.
# Permission *strings* are fixed in code, by design; only which role holds
# which of them is runtime-editable (see the docstring above).
ALL_PERMISSIONS: frozenset[str] = frozenset(
    permission for permissions in DEFAULT_ROLE_PERMISSIONS.values() for permission in permissions
)


def has_permission(role: Role, permission: str) -> bool:
    from app.storage.permissions_repo import permissions_repo  # deferred: see permissions_repo.py's own note

    return permission in permissions_repo.get_role_permissions(role.value)
