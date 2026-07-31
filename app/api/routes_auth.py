import jwt
from fastapi import APIRouter, Request

from app.auth import service as auth_service
from app.auth.models import LoginRequest, LoginResponse
from app.auth.security import decode_jwt

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    return auth_service.login(body.username, body.password)


@router.post("/logout")
def logout(request: Request) -> dict:
    header = request.headers.get("authorization", "")
    if header.startswith("Bearer "):
        try:
            payload = decode_jwt(header[len("Bearer "):].strip())
            auth_service.logout(payload["jti"])
        except jwt.InvalidTokenError:
            pass
    return {"detail": "logged out"}
