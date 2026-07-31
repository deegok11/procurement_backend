import json
from pathlib import Path

from filelock import FileLock

from app.config import settings
from app.domain.schemas import EventRecord


class EventLogRepository:
    """Append-only JSONL — one write per event, never edited or removed (P3)."""

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = str(path) + ".lock"
        if not self.path.exists():
            self.path.touch()

    def append(self, event: EventRecord) -> EventRecord:
        with FileLock(self.lock_path):
            with self.path.open("a") as f:
                f.write(json.dumps(event.model_dump(mode="json"), default=str) + "\n")
        return event

    def list_for_document(self, document_id: str) -> list[EventRecord]:
        if not self.path.exists():
            return []
        with FileLock(self.lock_path):
            lines = self.path.read_text().splitlines()
        events = [EventRecord.model_validate(json.loads(line)) for line in lines if line.strip()]
        return [e for e in events if e.document_id == document_id]

    def list_all(self) -> list[EventRecord]:
        if not self.path.exists():
            return []
        with FileLock(self.lock_path):
            lines = self.path.read_text().splitlines()
        return [EventRecord.model_validate(json.loads(line)) for line in lines if line.strip()]


events_repo = EventLogRepository(settings.events_file)
