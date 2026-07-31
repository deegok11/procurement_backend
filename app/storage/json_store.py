import json
import os
from pathlib import Path
from typing import Callable, TypeVar

from filelock import FileLock

T = TypeVar("T")


class JsonFileStore:
    """A single JSON file holding {"<collection_key>": [...]}, guarded by a file lock.

    Every mutation goes through `mutate()`: acquire the lock, read the current
    contents, hand the list to the caller's function, write the (possibly
    modified) result back atomically (write to a temp file, then os.replace).
    This is the only write path — nothing else touches the file directly.
    """

    def __init__(self, path: Path, collection_key: str):
        self.path = path
        self.collection_key = collection_key
        self.lock_path = str(path) + ".lock"
        if not self.path.exists():
            self.path.write_text(json.dumps({collection_key: []}, indent=2))

    def _read(self) -> list[dict]:
        raw = json.loads(self.path.read_text() or "{}")
        return raw.get(self.collection_key, [])

    def _write(self, items: list[dict]) -> None:
        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp_path.write_text(json.dumps({self.collection_key: items}, indent=2, default=str))
        os.replace(tmp_path, self.path)

    def read_all(self) -> list[dict]:
        with FileLock(self.lock_path):
            return self._read()

    def mutate(self, fn: Callable[[list[dict]], T]) -> T:
        """Run fn(items) under the lock; fn mutates `items` in place and/or returns a value.
        The (possibly mutated) list is always persisted after fn returns."""
        with FileLock(self.lock_path):
            items = self._read()
            result = fn(items)
            self._write(items)
            return result
