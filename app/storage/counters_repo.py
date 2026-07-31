import json
import os
from datetime import datetime, timezone
from pathlib import Path

from filelock import FileLock

from app.config import settings


def current_financial_year(as_of: datetime | None = None) -> str:
    """e.g. FISCAL_YEAR_START_MONTH=4 (April): 2025-06-01 -> "FY2025-26"; 2026-02-01 -> "FY2025-26"."""
    as_of = as_of or datetime.now(timezone.utc)
    start_month = settings.FISCAL_YEAR_START_MONTH
    if as_of.month >= start_month:
        start_year = as_of.year
    else:
        start_year = as_of.year - 1
    return f"FY{start_year}-{str(start_year + 1)[-2:]}"


class CountersRepository:
    """Gapless, sequential-per-series-per-financial-year document numbering.
    A number is allocated exactly once, under the file lock, so two concurrent
    requests can never receive the same number — "gapless" means no duplicates
    and no skips due to concurrency, not that a cancelled document's number
    gets reused."""

    def __init__(self, path: Path):
        self.path = path
        self.lock_path = str(path) + ".lock"
        if not self.path.exists():
            self.path.write_text(json.dumps({"counters": {}}, indent=2))

    def next_document_number(self, series_code: str, financial_year: str) -> str:
        key = f"{series_code}-{financial_year}"
        with FileLock(self.lock_path):
            data = json.loads(self.path.read_text() or "{}")
            counters = data.setdefault("counters", {})
            counters[key] = counters.get(key, 0) + 1
            seq = counters[key]
            tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp_path.write_text(json.dumps(data, indent=2))
            os.replace(tmp_path, self.path)
        return f"{series_code}-{financial_year}-{seq:05d}"


counters_repo = CountersRepository(settings.counters_file)
