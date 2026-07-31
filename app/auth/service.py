from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.auth import token_store
from app.auth.models import LoginResponse, TokenRecord
from app.auth.security import encode_jwt, verify_password
from app.config import settings
from app.domain.errors import NotAuthorizedError
from app.storage.users_repo import get_user_by_username


def login(username: str, password: str) -> LoginResponse:
    user = get_user_by_username(username)
    if user is None or not verify_password(password, user.password_hash):
        raise NotAuthorizedError("invalid username or password")

    jti = uuid4().hex
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.TOKEN_TTL_MINUTES)

    token_store.put(
        jti,
        TokenRecord(
            user_id=user.user_id,
            username=user.username,
            role=user.role,
            domain=user.domain,
            vendor_id=user.vendor_id,
            approval_level=user.approval_level,
            expires_at=expires_at,
        ),
    )
    access_token = encode_jwt(
        user_id=user.user_id, username=user.username, jti=jti, expires_at=expires_at
    )
    return LoginResponse(
        access_token=access_token, expires_at=expires_at, role=user.role, domain=user.domain
    )


def logout(jti: str) -> None:
    token_store.revoke(jti)
