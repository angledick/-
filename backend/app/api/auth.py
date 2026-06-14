"""Auth API — 登录 / 注册 / 当前用户信息 / 修改密码。"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional

from app.core.auth import create_access_token, get_current_user, require_admin
from app.storage.user_store import (
    get_user_by_username,
    create_user,
    verify_password,
    update_password,
)

router = APIRouter(prefix="/api/v1", tags=["auth"])


# ── 请求/响应模型 ─────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str
    role: str = "user"


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    username: str
    user_id: str


class UserInfoResponse(BaseModel):
    id: str
    username: str
    role: str
    created_at: Optional[int] = None


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.post("/auth/login", response_model=TokenResponse, summary="用户登录")
async def login(body: LoginRequest):
    user = get_user_by_username(body.username)
    if not user or not verify_password(body.password, user["hashed_pw"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    token = create_access_token({"sub": user["id"]})
    return TokenResponse(
        access_token=token,
        role=user["role"],
        username=user["username"],
        user_id=user["id"],
    )


# 兼容 OAuth2PasswordRequestForm (swagger UI)
@router.post("/auth/token", include_in_schema=False)
async def login_form(form: OAuth2PasswordRequestForm = Depends()):
    user = get_user_by_username(form.username)
    if not user or not verify_password(form.password, user["hashed_pw"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = create_access_token({"sub": user["id"]})
    return {"access_token": token, "token_type": "bearer"}


@router.post("/auth/register", response_model=UserInfoResponse, summary="新建用户（仅 admin）")
async def register(body: RegisterRequest, _admin: dict = Depends(require_admin)):
    if body.role not in ("admin", "user"):
        raise HTTPException(status_code=400, detail="角色只能是 admin 或 user")
    try:
        user = create_user(body.username, body.password, role=body.role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))
    return UserInfoResponse(**{k: v for k, v in user.items() if k != "hashed_pw"})


@router.get("/auth/me", response_model=UserInfoResponse, summary="获取当前用户信息")
async def me(current_user: dict = Depends(get_current_user)):
    return UserInfoResponse(**{k: v for k, v in current_user.items() if k != "hashed_pw"})


@router.put("/auth/me/password", summary="修改当前用户密码")
async def change_password(
    body: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user),
):
    if not verify_password(body.old_password, current_user["hashed_pw"]):
        raise HTTPException(status_code=400, detail="原密码不正确")
    if len(body.new_password) < 6:
        raise HTTPException(status_code=400, detail="新密码至少 6 位")
    update_password(current_user["id"], body.new_password)
    return {"ok": True, "message": "密码已修改"}
