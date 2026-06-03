"""Users API — 管理员用户管理（admin only）。"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.auth import require_admin, get_current_user
from app.storage.user_store import list_users, delete_user, update_role

router = APIRouter(prefix="/api/v1", tags=["users"])


class UserInfo(BaseModel):
    id: str
    username: str
    role: str
    created_at: int


class UpdateRoleRequest(BaseModel):
    role: str


@router.get("/users", response_model=list[UserInfo], summary="获取用户列表（admin）")
async def get_users(_admin: dict = Depends(require_admin)):
    return [UserInfo(**u) for u in list_users()]


@router.delete("/users/{user_id}", summary="删除用户（admin）")
async def remove_user(
    user_id: str,
    admin: dict = Depends(require_admin),
):
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除自己")
    ok = delete_user(user_id)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True}


@router.put("/users/{user_id}/role", summary="修改用户角色（admin）")
async def change_role(
    user_id: str,
    body: UpdateRoleRequest,
    admin: dict = Depends(require_admin),
):
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 user")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能修改自己的角色")
    ok = update_role(user_id, body.role)
    if not ok:
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"ok": True}
