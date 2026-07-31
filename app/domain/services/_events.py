from app.domain.schemas import CurrentUser, Document, EventRecord
from app.storage.events_repo import events_repo


def log_event(
    document: Document,
    *,
    event_type: str,
    from_status: str | None,
    to_status: str | None,
    actor: CurrentUser,
    reason: str | None = None,
    source: str = "api",
    metadata: dict | None = None,
) -> None:
    events_repo.append(
        EventRecord(
            document_id=document.id,
            document_type=document.document_type.value,
            event_type=event_type,
            from_status=from_status,
            to_status=to_status,
            actor_user_id=actor.user_id,
            actor_role=actor.role.value,
            reason=reason,
            source=source,
            metadata=metadata or {},
        )
    )
