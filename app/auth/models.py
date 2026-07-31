from datetime import datetime
from typing import Optional, TypedDict

from pydantic import BaseModel

from app.domain.roles import Domain, Role


class User(BaseModel):
    """A row in data/users.json — checked directly against this file at login,
    no database. password_hash is bcrypt (passlib); never store or compare
    plaintext, even for a local-only project — it's a one-line addition."""

    user_id: str
    username: str
    password_hash: str
    full_name: str = ""
    role: Role
    domain: Domain
    vendor_id: Optional[str] = None
    approval_level: Optional[int] = None
    is_active: bool = True


class TokenRecord(TypedDict):
    """The in-memory store's value shape, keyed by jti. This — not the JWT's
    own signature — is the authoritative source of session validity, role,
    domain, and vendor_id. Created once at server startup; a restart empties
    it, invalidating every outstanding token even though signatures still
    verify (an accepted local-dev tradeoff, documented in AGENTS.md)."""

    user_id: str
    username: str
    role: Role
    domain: Domain
    vendor_id: Optional[str]
    approval_level: Optional[int]
    expires_at: datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_at: datetime
    role: Role
    domain: Domain
