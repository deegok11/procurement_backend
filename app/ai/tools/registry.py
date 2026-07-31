from app.ai.tools import (
    bill_tools,
    grn_tools,
    item_tools,
    po_tools,
    pr_tools,
    quotation_tools,
    read_tools,
    transaction_tools,
)
from app.domain.roles import Role, has_permission
from app.domain.schemas import CurrentUser
from app.domain.services.document_service import DOCUMENT_TYPE_READ_PERMISSION

# get_document / list_documents / check_extraction_status can each touch any
# document type — the type-specific "<type>:read" check happens per-document
# inside document_service, so at the registry level a role just needs at
# least one of the six to have the tool offered at all. Derived from
# document_service's own mapping (not duplicated here) so a new document type
# never needs updating in two places.
_ANY_DOCUMENT_READ = tuple(DOCUMENT_TYPE_READ_PERMISSION.values())

# Every tool the agent can ever offer, paired with the permission string (or,
# for the generic cross-type tools, a tuple of alternatives — any one is
# enough) that gates it. This is the ONLY place a tool goes from "defined" to
# "offered" — build_tools_for_role() filters against has_permission()
# (app/domain/roles.py), the same runtime-editable permission matrix the REST
# routes use, so the two surfaces can't drift apart.
ALL_TOOLS: list[tuple[object, str | tuple[str, ...]]] = [
    (item_tools.list_items, "item:read"),
    (item_tools.create_item, "item:create"),
    (pr_tools.create_pr_draft, "pr:create"),
    (pr_tools.submit_pr_for_approval, "pr:submit"),
    (pr_tools.approve_pr, "pr:approve"),
    (pr_tools.reject_pr, "pr:reject"),
    (pr_tools.cancel_pr, "pr:cancel"),
    (pr_tools.invite_vendors_to_pr, "pr:invite_vendors"),
    (pr_tools.compare_quotations, "quotation:compare"),
    (quotation_tools.submit_quotation, "quotation:submit"),
    (quotation_tools.withdraw_quotation, "quotation:withdraw"),
    (po_tools.create_po_from_quotation, "po:create"),
    (po_tools.cancel_po, "po:cancel"),
    (grn_tools.create_grn, "grn:create"),
    (grn_tools.cancel_grn, "grn:cancel"),
    (bill_tools.create_bill, "bill:create"),
    (bill_tools.acknowledge_bill_exception, "bill:acknowledge_exception"),
    (bill_tools.cancel_bill, "bill:cancel"),
    (transaction_tools.create_transaction, "transaction:create"),
    (transaction_tools.cancel_transaction, "transaction:cancel"),
    (read_tools.get_document, _ANY_DOCUMENT_READ),
    (read_tools.list_documents, _ANY_DOCUMENT_READ),
    (read_tools.check_extraction_status, _ANY_DOCUMENT_READ),
]


def _role_satisfies(role: Role, permission: str | tuple[str, ...]) -> bool:
    if isinstance(permission, tuple):
        return any(has_permission(role, p) for p in permission)
    return has_permission(role, permission)


def build_tools_for_role(current_user: CurrentUser) -> list[object]:
    """The model is never even offered a tool its role can't use — this is
    defense in depth on top of the identical check every tool re-runs itself
    (in case a future caller reuses these tool objects outside this filter)."""
    return [tool for tool, permission in ALL_TOOLS if _role_satisfies(current_user.role, permission)]
