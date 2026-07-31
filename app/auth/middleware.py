from datetime import datetime, timezone

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.auth import token_store
from app.auth.security import decode_jwt

EXEMPT_PATHS = {"/auth/login", "/docs", "/openapi.json", "/redoc", "/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Reads the Authorization header, validates against the in-memory token
    store (not just the JWT signature), and attaches user context to
    request.state for downstream Depends() to read. Role-based route
    authorization layers on top via app.auth.dependencies.require_permission —
    this middleware only establishes identity."""

    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        header = request.headers.get("authorization", "")
        if not header.startswith("Bearer "):
            return JSONResponse(status_code=401, content={"detail": "Missing bearer token"})

        token = header[len("Bearer "):].strip()
        try:
            payload = decode_jwt(token)
        except jwt.InvalidTokenError:
            return JSONResponse(status_code=401, content={"detail": "Invalid or expired token"})

        jti = payload.get("jti")
        record = token_store.get(jti) if jti else None
        if record is None:
            return JSONResponse(
                status_code=401,
                content={"detail": "Token not recognized (revoked, or server restarted)"},
            )
        if record["expires_at"] < datetime.now(timezone.utc):
            token_store.revoke(jti)
            return JSONResponse(status_code=401, content={"detail": "Token expired"})

        request.state.jti = jti
        request.state.user_id = record["user_id"]
        request.state.username = record["username"]
        request.state.role = record["role"]
        request.state.domain = record["domain"]
        request.state.vendor_id = record["vendor_id"]
        request.state.approval_level = record["approval_level"]
        return await call_next(request)
