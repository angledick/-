"""JWT 认证工具 + FastAPI 依赖注入。

DEV_MODE=true 时跳过 token 校验，直接以 mock admin 身份放行。
"""

import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.config import settings

# 开发模式开关
DEV_MODE = os.getenv("DEV_MODE", "true").lower() in ("1", "true", "yes")

_MOCK_ADMIN = {"id": "dev-admin", "username": "admin", "role": "admin", "created_at": 1700000000}

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=not DEV_MODE)

ALGORITHM = "HS256"


# ── Token 创建 / 验证 ─────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(hours=settings.jwt_expire_hours)
    )
    payload["exp"] = expire
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI 依赖 ──────────────────────────────────────────────────────────────

async def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> dict:
    """解析 token，返回 {id, username, role}。DEV_MODE 下直接返回 mock admin。"""
    if DEV_MODE:
        return _MOCK_ADMIN

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="未提供 Token")

    payload = _decode_token(token)
    user_id: str = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token 格式错误")

    from app.storage.user_store import get_user_by_id
    user = get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """仅允许 admin 角色，否则抛 403。DEV_MODE 下已自动放行。"""
    if user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")
    return user
