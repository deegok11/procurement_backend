from typing import Optional

from app.domain.permissions import build_scope, require_permission
from app.domain.roles import has_permission
from app.domain.schemas import CurrentUser, Document, DocumentType, EventRecord
from app.storage.documents_repo import documents_repo
from app.storage.events_repo import events_repo

# Maps each document_type to the permission that gates reading a document of
# that type. Single source of truth for the generic, cross-type surface
# (REST's /documents routes and the chat read tools) so a document is never
# reachable there under looser rules than its type-specific route enforces —
# e.g. a caller without "bill:read" can't see a bill via GET /documents/{id}
# just because they can see some other type.
DOCUMENT_TYPE_READ_PERMISSION: dict[DocumentType, str] = {
    DocumentType.PR: "pr:read",
    DocumentType.QUOTATION: "quotation:read",
    DocumentType.PO: "po:read",
    DocumentType.GRN_SRN: "grn:read",
    DocumentType.BILL: "bill:read",
    DocumentType.TRANSACTION: "transaction:read",
}


def get_document(current_user: CurrentUser, document_id: str) -> Document:
    # Tenant scope + existence first — 404s either way, so this never leaks
    # whether an out-of-scope id exists. Only once that passes do we check the
    # type-specific read permission for whatever this document turns out to be.
    doc = documents_repo.get(document_id, scope=build_scope(current_user))
    require_permission(current_user, DOCUMENT_TYPE_READ_PERMISSION[doc.document_type])
    return doc


def list_documents(
    current_user: CurrentUser,
    *,
    document_type: Optional[DocumentType] = None,
    status: Optional[str] = None,
    vendor_id: Optional[str] = None,
    parent_document_id: Optional[str] = None,
    root_pr_id: Optional[str] = None,
) -> list[Document]:
    if document_type is not None:
        # Asked for one type explicitly — fail fast if this role can't read it
        # at all, rather than silently returning an empty list.
        require_permission(current_user, DOCUMENT_TYPE_READ_PERMISSION[document_type])

    docs = documents_repo.list(
        document_type=document_type, status=status, vendor_id=vendor_id,
        parent_document_id=parent_document_id, root_pr_id=root_pr_id,
        scope=build_scope(current_user),
    )
    if document_type is None:
        # Spans every type — a single blanket permission check can't express
        # "yes to PRs, no to transactions," so narrow per-item instead.
        docs = [
            d for d in docs
            if has_permission(current_user.role, DOCUMENT_TYPE_READ_PERMISSION[d.document_type])
        ]
    return docs


def get_document_events(current_user: CurrentUser, document_id: str) -> list[EventRecord]:
    get_document(current_user, document_id)  # same scope + type-read check as reading the document itself
    return events_repo.list_for_document(document_id)
