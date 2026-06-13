"""FeishuClient — 飞书 Bot API 封装。

提供 tenant_access_token 管理、消息发送、卡片消息、回复消息等能力。
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_FEISHU_BASE = "https://open.feishu.cn/open-apis"
_TOKEN_REFRESH_BUFFER = 300  # 提前 5 分钟刷新


class FeishuClient:
    """飞书 Bot API 客户端（单例）。"""

    def __init__(self):
        self._token: str = ""
        self._token_expires: float = 0

    def _get_app_id(self) -> str:
        """获取飞书 App ID（settings 优先，fallback 到 channels.json）。"""
        return getattr(settings, "feishu_app_id", "") or ""

    def _get_app_secret(self) -> str:
        """获取飞书 App Secret。"""
        return getattr(settings, "feishu_app_secret", "") or ""

    @staticmethod
    def _get_channel_config() -> dict:
        """从 channels.json 读取 feishu_compliance 配置（fallback）。"""
        try:
            from pathlib import Path
            config_path = Path(settings.data_dir) / "config" / "channels.json"
            if config_path.exists():
                import json
                with open(config_path, "r", encoding="utf-8") as f:
                    configs = json.load(f)
                return configs.get("feishu_compliance", {}).get("config", {})
        except Exception as e:
            logger.debug("读取 channels.json 飞书配置失败: %s", e)
        return {}

    async def get_tenant_access_token(self) -> str:
        """获取 tenant_access_token，带缓存与自动刷新。

        飞书 tenant_access_token 有效期 2 小时（7200 秒）。
        过期前 _TOKEN_REFRESH_BUFFER 秒自动刷新。
        """
        if self._token and time.time() < self._token_expires - _TOKEN_REFRESH_BUFFER:
            return self._token

        app_id = self._get_app_id()
        app_secret = self._get_app_secret()
        if not app_id or not app_secret:
            config = self._get_channel_config()
            app_id = app_id or config.get("app_id", "")
            app_secret = app_secret or config.get("app_secret", "")

        if not app_id or not app_secret:
            logger.warning("飞书 app_id/app_secret 未配置，无法获取 token")
            return ""

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_FEISHU_BASE}/auth/v3/tenant_access_token/internal",
                    json={"app_id": app_id, "app_secret": app_secret},
                )
                data = resp.json()
                if data.get("code") != 0:
                    logger.error("获取飞书 tenant_access_token 失败: code=%s msg=%s",
                                 data.get("code"), data.get("msg"))
                    return ""
                self._token = data.get("tenant_access_token", "")
                expire = data.get("expire", 7200)
                self._token_expires = time.time() + expire
                logger.info("飞书 tenant_access_token 已刷新，有效期 %ds", expire)
                return self._token
        except Exception as e:
            logger.error("获取飞书 tenant_access_token 异常: %s", e)
            return ""

    async def send_message(
        self,
        receive_id: str,
        text: str,
        receive_id_type: str = "chat_id",
        msg_type: str = "text",
    ) -> Dict[str, Any]:
        """通过 Bot API 发送消息。

        Args:
            receive_id: 接收者 ID（open_id / user_id / chat_id）
            text: 消息文本（或卡片 JSON 字符串）
            receive_id_type: ID 类型 — open_id / user_id / chat_id / union_id
            msg_type: 消息类型 — text / interactive / post

        Returns:
            飞书 API 响应 dict
        """
        token = await self.get_tenant_access_token()
        if not token:
            return {"error": "token unavailable"}

        payload: Dict[str, Any] = {
            "receive_id": receive_id,
            "msg_type": msg_type,
            "content": json.dumps({"text": text}) if msg_type == "text" else text,
        }

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_FEISHU_BASE}/im/v1/messages",
                    params={"receive_id_type": receive_id_type},
                    json=payload,
                    headers={"Authorization": f"Bearer {token}"},
                )
                data = resp.json()
                if data.get("code") != 0:
                    logger.error("飞书发送消息失败: code=%s msg=%s",
                                 data.get("code"), data.get("msg"))
                return data
        except Exception as e:
            logger.error("飞书发送消息异常: %s", e)
            return {"error": str(e)}

    async def send_card(
        self,
        receive_id: str,
        card: dict,
        receive_id_type: str = "chat_id",
    ) -> Dict[str, Any]:
        """发送交互式卡片消息。"""
        return await self.send_message(
            receive_id, json.dumps(card), receive_id_type, "interactive"
        )

    async def reply_message(
        self,
        message_id: str,
        text: str,
        msg_type: str = "text",
    ) -> Dict[str, Any]:
        """回复指定消息。"""
        token = await self.get_tenant_access_token()
        if not token:
            return {"error": "token unavailable"}

        content = json.dumps({"text": text}) if msg_type == "text" else text

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{_FEISHU_BASE}/im/v1/messages/{message_id}/reply",
                    json={"msg_type": msg_type, "content": content},
                    headers={"Authorization": f"Bearer {token}"},
                )
                return resp.json()
        except Exception as e:
            logger.error("飞书回复消息异常: %s", e)
            return {"error": str(e)}

    async def get_user_info(
        self, user_id: str, user_id_type: str = "open_id"
    ) -> Optional[Dict]:
        """获取用户信息。"""
        token = await self.get_tenant_access_token()
        if not token:
            return None

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{_FEISHU_BASE}/contact/v3/users/{user_id}",
                    params={"user_id_type": user_id_type},
                    headers={"Authorization": f"Bearer {token}"},
                )
                data = resp.json()
                if data.get("code") == 0:
                    return data.get("data", {}).get("user")
                return None
        except Exception as e:
            logger.error("飞书获取用户信息异常: %s", e)
            return None


# ── 全局单例 ──────────────────────────────────────

_feishu_client: Optional[FeishuClient] = None


def get_feishu_client() -> FeishuClient:
    """获取全局 FeishuClient 单例。"""
    global _feishu_client
    if _feishu_client is None:
        _feishu_client = FeishuClient()
    return _feishu_client


import json  # noqa: E402 — module-level import used by methods above
