from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.deps import get_current_user
from app.domain.roles import ALL_PERMISSIONS, Role
from app.domain.schemas import CurrentUser
from app.domain.services import permissions_service

router = APIRouter(prefix="/permissions", tags=["permissions"])


class PermissionsMatrixResponse(BaseModel):
    matrix: dict[str, list[str]]
    all_permissions: list[str]


class UpdateRolePermissionsRequest(BaseModel):
    permissions: list[str]


def _response(matrix: dict[str, list[str]]) -> PermissionsMatrixResponse:
    return PermissionsMatrixResponse(matrix=matrix, all_permissions=sorted(ALL_PERMISSIONS))


@router.get("", response_model=PermissionsMatrixResponse)
def get_permissions(current_user: CurrentUser = Depends(get_current_user)) -> PermissionsMatrixResponse:
    return _response(permissions_service.get_permissions_matrix(current_user))


@router.put("/{role}", response_model=PermissionsMatrixResponse)
def update_permissions(
    role: Role, body: UpdateRolePermissionsRequest, current_user: CurrentUser = Depends(get_current_user)
) -> PermissionsMatrixResponse:
    return _response(permissions_service.update_role_permissions(current_user, role, body.permissions))
