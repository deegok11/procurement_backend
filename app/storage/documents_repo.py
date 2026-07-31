from typing import Optional

from app.config import settings
from app.domain.errors import NotFoundError
from app.domain.permissions import QueryScope
from app.domain.roles import Domain
from app.domain.schemas import Document, DocumentType
from app.storage.json_store import JsonFileStore

_store = JsonFileStore(settings.documents_file, "documents")


def _visible_to_vendor(raw: dict, vendor_id: Optional[str]) -> bool:
    # A vendor sees documents that concern them directly (their QUOTATION/PO/BILL/...)
    # plus PRs they've been invited to quote against — a PR's own vendor_id is null
    # (it's internal-domain), so the invite list is the only signal for that case.
    if raw.get("vendor_id") == vendor_id:
        return True
    if raw.get("document_type") == "PR":
        return vendor_id in (raw.get("extra") or {}).get("invited_vendor_ids", [])
    return False


def _apply_scope(items: list[dict], scope: Optional[QueryScope]) -> list[dict]:
    if scope is None or scope.domain != Domain.VENDOR:
        return items
    return [i for i in items if _visible_to_vendor(i, scope.vendor_id)]


class DocumentsRepository:
    def add(self, document: Document) -> Document:
        def _op(items: list[dict]) -> None:
            items.append(document.model_dump(mode="json"))

        _store.mutate(_op)
        return document

    def get(self, document_id: str, scope: Optional[QueryScope] = None) -> Document:
        items = _apply_scope(_store.read_all(), scope)
        for raw in items:
            if raw["id"] == document_id:
                return Document.model_validate(raw)
        raise NotFoundError(f"document {document_id} not found")

    def get_unscoped(self, document_id: str) -> Document:
        """Internal service-to-service lookups (e.g. walking parent_document_id
        chains) that must succeed regardless of the *caller's* tenant scope —
        the scope check already happened once, on the top-level document."""
        return self.get(document_id, scope=None)

    def list(
        self,
        *,
        document_type: Optional[DocumentType] = None,
        status: Optional[str] = None,
        vendor_id: Optional[str] = None,
        parent_document_id: Optional[str] = None,
        root_pr_id: Optional[str] = None,
        scope: Optional[QueryScope] = None,
        include_deleted: bool = False,
    ) -> list[Document]:
        items = _apply_scope(_store.read_all(), scope)
        docs = [Document.model_validate(raw) for raw in items]
        if document_type is not None:
            docs = [d for d in docs if d.document_type == document_type]
        if status is not None:
            docs = [d for d in docs if d.status == status]
        if vendor_id is not None:
            docs = [d for d in docs if d.vendor_id == vendor_id]
        if parent_document_id is not None:
            docs = [d for d in docs if d.parent_document_id == parent_document_id]
        if root_pr_id is not None:
            docs = [d for d in docs if d.root_pr_id == root_pr_id]
        if not include_deleted:
            docs = [d for d in docs if not d.soft_delete.is_deleted]
        return docs

    def update(self, document: Document) -> Document:
        def _op(items: list[dict]) -> None:
            for idx, raw in enumerate(items):
                if raw["id"] == document.id:
                    items[idx] = document.model_dump(mode="json")
                    return
            raise NotFoundError(f"document {document.id} not found")

        _store.mutate(_op)
        return document


documents_repo = DocumentsRepository()
