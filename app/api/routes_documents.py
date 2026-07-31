from typing import Optional

from fastapi import APIRouter, Depends

from app.api.deps import get_current_user
from app.domain.schemas import CurrentUser, Document, DocumentType, EventRecord
from app.domain.services import document_service

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[Document])
def list_documents(
    document_type: Optional[DocumentType] = None,
    status: Optional[str] = None,
    vendor_id: Optional[str] = None,
    parent_document_id: Optional[str] = None,
    root_pr_id: Optional[str] = None,
    current_user: CurrentUser = Depends(get_current_user),
) -> list[Document]:
    return document_service.list_documents(
        current_user, document_type=document_type, status=status, vendor_id=vendor_id,
        parent_document_id=parent_document_id, root_pr_id=root_pr_id,
    )


@router.get("/{document_id}", response_model=Document)
def get_document(document_id: str, current_user: CurrentUser = Depends(get_current_user)) -> Document:
    return document_service.get_document(current_user, document_id)


@router.get("/{document_id}/events", response_model=list[EventRecord])
def get_document_events(
    document_id: str, current_user: CurrentUser = Depends(get_current_user)
) -> list[EventRecord]:
    return document_service.get_document_events(current_user, document_id)
