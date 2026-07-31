from fastapi import Depends, HTTPException, Request

from app.domain.errors import NotAuthorizedError
from app.domain.permissions import require_permission as _require_permission
from app.domain.roles import Role
from app.domain.schemas import CurrentUser


def get_current_user(request: Request) -> CurrentUser:
    """Reads the identity the AuthMiddleware already attached to request.state.
    If this raises AttributeError, the middleware didn't run for this path —
    that's a routing bug (the path should be in EXEMPT_PATHS or protected),
    not something to silently work around here."""
    return CurrentUser(
        user_id=request.state.user_id,
        username=request.state.username,
        role=request.state.role,
        domain=request.state.domain,
        vendor_id=request.state.vendor_id,
        approval_level=request.state.approval_level,
    )


def require_role(*roles: Role):
    def _dep(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if current_user.role not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"role '{current_user.role.value}' cannot access this endpoint",
            )
        return current_user

    return _dep


def require_permission(permission: str):
    """Defense-in-depth on top of the service layer's own require_permission
    call — a route wearing the wrong permission decorator fails loudly here
    before ever reaching the domain service."""

    def _dep(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        try:
            _require_permission(current_user, permission)
        except NotAuthorizedError as e:
            raise HTTPException(status_code=403, detail=str(e))
        return current_user

    return _dep
