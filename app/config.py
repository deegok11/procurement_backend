from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    GEMINI_API_KEY: str = ""
    JWT_SECRET: str = "dev-only-change-me"
    JWT_ALGORITHM: str = "HS256"
    TOKEN_TTL_MINUTES: int = 60

    CHAT_MODEL: str = "gemini-3.6-flash"
    EXTRACTION_MODEL: str = "gemini-3.6-flash"
    # Cheaper than CHAT_MODEL/EXTRACTION_MODEL on purpose — the guardrail is a
    # single-message in/out-of-scope classification, not open-ended reasoning
    # or extraction, and it runs on every chat turn (see AGENTS.md §9), so its
    # per-call cost matters more than the other two. flash-lite is Google's
    # low-latency, low-cost tier, explicitly positioned for exactly this kind
    # of high-volume, simple-classification workload.
    GUARDRAIL_MODEL: str = "gemini-3.5-flash-lite"

    FISCAL_YEAR_START_MONTH: int = 4  # April
    APPROVAL_TOLERANCE_PCT: float = 2.0  # allowed over-receipt/over-bill tolerance

    DATA_DIR: Path = Path("./data")
    UPLOAD_DIR: Path = Path("./app/uploads")

    @property
    def users_file(self) -> Path:
        return self.DATA_DIR / "users.json"

    @property
    def documents_file(self) -> Path:
        return self.DATA_DIR / "documents.json"

    @property
    def items_file(self) -> Path:
        return self.DATA_DIR / "items.json"

    @property
    def permissions_file(self) -> Path:
        return self.DATA_DIR / "permissions.json"

    @property
    def events_file(self) -> Path:
        return self.DATA_DIR / "events.jsonl"

    @property
    def counters_file(self) -> Path:
        return self.DATA_DIR / "counters.json"


settings = Settings()
settings.DATA_DIR.mkdir(parents=True, exist_ok=True)
settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
