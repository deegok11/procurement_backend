from app.auth.models import TokenRecord

# Created once, at process startup (this module is imported exactly once).
# The authoritative source of session validity/role/domain/vendor_id — see
# app/auth/models.py::TokenRecord and app/auth/security.py::encode_jwt for why
# this, not the JWT payload, is what authorization reads from. Deferred to a
# disk-backed store if this ever needs to survive a restart or run across
# multiple processes (see AGENTS.md "what's deferred until we scale").
TOKENS: dict[str, TokenRecord] = {}


def put(jti: str, record: TokenRecord) -> None:
    TOKENS[jti] = record


def get(jti: str) -> TokenRecord | None:
    return TOKENS.get(jti)


def revoke(jti: str) -> None:
    TOKENS.pop(jti, None)
