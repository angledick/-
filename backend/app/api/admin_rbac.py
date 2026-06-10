"""
RBAC 管理 API — 角色分配与权限检查。

端点:
  GET  /api/v1/rbac/roles                 — 角色定义列表
  POST /api/v1/rbac/assign                — 分配角色
  GET  /api/v1/rbac/users                 — 用户RBAC列表
  GET  /api/v1/rbac/users/{user_id}       — 用户权限详情
  GET  /api/v1/rbac/users/{user_id}/permissions — 用户权限列表
  POST /api/v1/rbac/check                 — 权限检查
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api/v1/rbac", tags=["rbac"])


class AssignRoleRequest(BaseModel):
    user_id: str
    username: str
    role: str


@router.get("/roles", summary="角色定义列表")
async def list_roles():
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"roles": rbac.get_roles()}


@router.post("/assign", summary="分配角色")
async def assign_role(req: AssignRoleRequest):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    try:
        return rbac.assign_role(req.user_id, req.username, req.role)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/users/{user_id}", summary="撤销用户角色")
async def revoke_role(user_id: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    if rbac.remove_role(user_id):
        return {"status": "revoked", "user_id": user_id}
    raise HTTPException(status_code=404, detail="User not found")


@router.get("/users", summary="用户RBAC列表")
async def list_rbac_users():
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"users": rbac.list_users()}


@router.get("/users/{user_id}", summary="用户权限详情")
async def get_user_rbac(user_id: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    user = rbac.get_user(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@router.get("/users/{user_id}/permissions", summary="用户权限列表")
async def get_user_permissions(user_id: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    return {"user_id": user_id, "permissions": rbac.get_permissions(user_id)}


@router.post("/check", summary="权限检查")
async def check_permission(user_id: str, resource: str, action: str):
    from app.core.rbac import get_rbac_manager
    rbac = get_rbac_manager()
    allowed = rbac.check_permission(user_id, resource, action)
    return {"user_id": user_id, "resource": resource, "action": action, "allowed": allowed}
