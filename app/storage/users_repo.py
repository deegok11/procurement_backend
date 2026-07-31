import json

from app.auth.models import User
from app.config import settings


def load_users() -> list[User]:
    if not settings.users_file.exists():
        return []
    raw = json.loads(settings.users_file.read_text())
    return [User.model_validate(u) for u in raw.get("users", [])]


def get_user_by_username(username: str) -> User | None:
    for user in load_users():
        if user.username == username and user.is_active:
            return user
    return None


def get_user_by_id(user_id: str) -> User | None:
    for user in load_users():
        if user.user_id == user_id:
            return user
    return None
