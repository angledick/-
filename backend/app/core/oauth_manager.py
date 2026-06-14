"""
OAuthManager — 统一OAuth连接管理（Phase 3.1）

参考开源选型：
- Shopify OAuth（官方SDK）
- 飞书/钉钉/Slack — 对齐指南 §3.5.11 Chatwoot 全渠道接入思路
- ERPNext（指南 §3.5.3）/ GreaterWMS（指南 §3.5.4）等第三方系统对接

支持Provider:
  - shopify: Shopify OAuth2 (已有 shopify.py 底层实现)
  - feishu: 飞书开放平台 OAuth2
  - dingtalk: 钉钉开放平台 OAuth2
  - slack: Slack OAuth2
  - erpnext: ERPNext API Token
  - listmonk: Listmonk Basic Auth

持久化: data/config/oauth_connections.json
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from app.config import settings


# ── 数据模型 ────────────────────────────────────────


class ProviderStatus(str, Enum):
    disconnected = "disconnected"
    connecting = "connecting"
    connected = "connected"
    error = "error"
    expired = "expired"


@dataclass
class OAuthToken:
    """OAuth令牌（通用）"""
    access_token: str = ""
    refresh_token: str = ""
    expires_at: float = 0.0  # Unix timestamp, 0 = never expires
    token_type: str = "Bearer"
    scope: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        if self.expires_at == 0:
            return False
        return time.time() >= self.expires_at - 60  # 60s buffer

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "OAuthToken":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class OAuthConnection:
    """OAuth连接记录"""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    provider: str = ""                    # shopify / feishu / dingtalk / slack / erpnext / listmonk
    label: str = ""                       # 显示名称，如 "我的Shopify店铺"
    status: ProviderStatus = ProviderStatus.disconnected
    config: Dict[str, Any] = field(default_factory=dict)  # provider特定配置
    token: Optional[OAuthToken] = None
    last_sync_at: float = 0.0
    last_error: str = ""
    created_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    updated_at: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "OAuthConnection":
        token_data = data.pop("token", None)
        status_val = data.pop("status", "disconnected")
        conn = cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        conn.status = ProviderStatus(status_val) if isinstance(status_val, str) else status_val
        if token_data:
            conn.token = OAuthToken.from_dict(token_data)
        return conn


logger = logging.getLogger(__name__)


# ── Provider配置模板（从 data/oauth/providers.yaml 加载）──────

OAUTH_PROVIDERS_YAML = Path(settings.data_dir) / "oauth" / "providers.yaml"


def _load_provider_templates() -> Dict[str, Dict[str, Any]]:
    """从 YAML 加载 OAuth Provider 配置模板。"""
    if OAUTH_PROVIDERS_YAML.exists():
        try:
            with open(OAUTH_PROVIDERS_YAML, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data.get("providers", {})
        except Exception:
            pass
    logger.warning("OAuth Provider YAML 未找到: %s，使用空配置", OAUTH_PROVIDERS_YAML)
    return {}


# 所有代码通过 PROVIDER_TEMPLATES 访问 Provider 定义
PROVIDER_TEMPLATES: Dict[str, Dict[str, Any]] = _load_provider_templates()


# ── 持久化层 ──────────────────────────────────────

CONN_FILE = Path(settings.data_dir) / "config" / "oauth_connections.json"


def _load_connections() -> Dict[str, dict]:
    if CONN_FILE.exists():
        try:
            with open(CONN_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_connections(data: Dict[str, dict]) -> None:
    CONN_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(CONN_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── OAuthManager ──────────────────────────────────


class OAuthManager:
    """统一OAuth连接管理器"""

    def __init__(self):
        self._connections: Dict[str, OAuthConnection] = {}
        self._load_all()

    def _load_all(self):
        raw = _load_connections()
        for cid, cdata in raw.items():
            try:
                self._connections[cid] = OAuthConnection.from_dict(cdata)
            except Exception:
                continue

    def _persist(self):
        _save_connections({cid: c.to_dict() for cid, c in self._connections.items()})

    # ── CRUD ────────────────────────────────────

    def list_connections(self, provider: Optional[str] = None) -> List[Dict]:
        conns = self._connections.values()
        if provider:
            conns = [c for c in conns if c.provider == provider]
        return [c.to_dict() for c in conns]

    def get_connection(self, conn_id: str) -> Optional[Dict]:
        conn = self._connections.get(conn_id)
        return conn.to_dict() if conn else None

    def create_connection(self, provider: str, label: str = "", config: Dict[str, Any] = None) -> Dict:
        template = PROVIDER_TEMPLATES.get(provider)
        if not template:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDER_TEMPLATES.keys())}")
        conn = OAuthConnection(
            provider=provider,
            label=label or f"{template['name']} Connection",
            status=ProviderStatus.disconnected,
            config=config or {},
        )
        self._connections[conn.id] = conn
        self._persist()
        return conn.to_dict()

    def update_config(self, conn_id: str, config: Dict[str, Any]) -> Optional[Dict]:
        conn = self._connections.get(conn_id)
        if not conn:
            return None
        conn.config.update(config)
        conn.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        return conn.to_dict()

    def delete_connection(self, conn_id: str) -> bool:
        if conn_id in self._connections:
            del self._connections[conn_id]
            self._persist()
            return True
        return False

    # ── OAuth流 ─────────────────────────────────

    def get_auth_url(self, conn_id: str, state: str = "") -> Optional[str]:
        """获取OAuth授权URL"""
        conn = self._connections.get(conn_id)
        if not conn:
            return None
        template = PROVIDER_TEMPLATES.get(conn.provider)
        if not template or template.get("auth_type") != "oauth2":
            return None

        auth_url = template["auth_url"]
        params = {"state": state or uuid.uuid4().hex[:16]}

        if conn.provider == "shopify":
            shop = conn.config.get("shop", "")
            auth_url = auth_url.replace("{shop}", shop)
            params["client_id"] = conn.config.get("api_key", settings.shopify_client_id)
            params["scope"] = template["scopes"]
            params["redirect_uri"] = conn.config.get("redirect_uri", settings.shopify_redirect_uri)
        elif conn.provider == "feishu":
            params["app_id"] = conn.config.get("app_id", "")
            params["redirect_uri"] = conn.config.get("redirect_uri", "")
            params["scope"] = template["scopes"]
        elif conn.provider == "dingtalk":
            params["client_id"] = conn.config.get("app_key", "")
            params["redirect_uri"] = conn.config.get("redirect_uri", "")
            params["response_type"] = "code"
            params["scope"] = template["scopes"]
        elif conn.provider == "slack":
            params["client_id"] = conn.config.get("client_id", "")
            params["scope"] = template["scopes"]
            params["redirect_uri"] = conn.config.get("redirect_uri", "")

        from urllib.parse import urlencode
        conn.status = ProviderStatus.connecting
        conn.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._persist()
        return f"{auth_url}?{urlencode(params)}"

    async def handle_callback(self, conn_id: str, callback_params: Dict[str, Any]) -> Dict:
        """处理OAuth回调，交换令牌"""
        conn = self._connections.get(conn_id)
        if not conn:
            raise ValueError(f"Connection {conn_id} not found")

        try:
            token = await self._exchange_token(conn, callback_params)
            conn.token = token
            conn.status = ProviderStatus.connected
            conn.last_error = ""
            conn.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._persist()

            # 触发连接成功事件
            try:
                from app.core.event_bus import get_event_bus
                bus = get_event_bus()
                await bus.publish_raw({
                    "type": "system:integration_connected",
                    "source": "oauth_manager",
                    "data": {
                        "provider": conn.provider,
                        "connection_id": conn.id,
                        "label": conn.label,
                    },
                })
            except Exception:
                pass

            return conn.to_dict()
        except Exception as e:
            conn.status = ProviderStatus.error
            conn.last_error = str(e)
            conn.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._persist()
            raise

    async def _exchange_token(self, conn: OAuthConnection, params: Dict) -> OAuthToken:
        """令牌交换（按provider分支）"""
        import httpx

        template = PROVIDER_TEMPLATES.get(conn.provider, {})
        token_url = template.get("token_url", "")

        if conn.provider == "shopify":
            # 使用现有shopify.py的SDK方式
            from app.services.shopify import exchange_code_for_token as shopify_exchange
            shop = conn.config.get("shop", "")
            code = params.get("code", "")
            stk = shopify_exchange(shop, code, params)
            return OAuthToken(
                access_token=stk.access_token,
                scope=stk.scope,
            )
        elif conn.provider == "feishu":
            # 飞书OAuth: 先用code换app_access_token，再换user_access_token
            async with httpx.AsyncClient() as client:
                # Step 1: app_access_token
                app_resp = await client.post(
                    "https://open.feishu.cn/open-apis/auth/v3/app_access_token/internal",
                    json={
                        "app_id": conn.config.get("app_id", ""),
                        "app_secret": conn.config.get("app_secret", ""),
                    },
                )
                app_data = app_resp.json()
                app_token = app_data.get("app_access_token", "")

                # Step 2: user_access_token
                user_resp = await client.post(
                    "https://open.feishu.cn/open-apis/authen/v1/oidc/access_token",
                    headers={"Authorization": f"Bearer {app_token}"},
                    json={
                        "grant_type": "authorization_code",
                        "code": params.get("code", ""),
                    },
                )
                user_data = user_resp.json().get("data", {})
                return OAuthToken(
                    access_token=user_data.get("access_token", ""),
                    refresh_token=user_data.get("refresh_token", ""),
                    expires_at=time.time() + user_data.get("expires_in", 7200),
                    token_type=user_data.get("token_type", "Bearer"),
                    scope=user_data.get("scope", ""),
                )
        elif conn.provider == "dingtalk":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://api.dingtalk.com/v1.0/oauth2/userAccessToken",
                    json={
                        "clientId": conn.config.get("app_key", ""),
                        "clientSecret": conn.config.get("app_secret", ""),
                        "code": params.get("code", ""),
                        "grantType": "authorization_code",
                    },
                )
                data = resp.json()
                return OAuthToken(
                    access_token=data.get("accessToken", ""),
                    refresh_token=data.get("refreshToken", ""),
                    expires_at=time.time() + int(data.get("expireIn", 7200)),
                )
        elif conn.provider == "slack":
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "client_id": conn.config.get("client_id", ""),
                        "client_secret": conn.config.get("client_secret", ""),
                        "code": params.get("code", ""),
                        "redirect_uri": conn.config.get("redirect_uri", ""),
                    },
                )
                data = resp.json()
                if not data.get("ok"):
                    raise RuntimeError(f"Slack OAuth failed: {data.get('error')}")
                return OAuthToken(
                    access_token=data.get("access_token", ""),
                    scope=data.get("scope", ""),
                    extra={"team": data.get("team", {}), "bot_user_id": data.get("bot_user_id", "")},
                )
        else:
            # Token-based providers (erpnext, listmonk, 17track, chatwoot)
            # No OAuth flow needed, just validate config
            return OAuthToken(
                access_token=conn.config.get("api_key", conn.config.get("api_access_token", "")),
                token_type="Token",
            )

    async def test_connection(self, conn_id: str) -> Dict:
        """测试连接有效性"""
        conn = self._connections.get(conn_id)
        if not conn:
            return {"status": "error", "message": "Connection not found"}

        if not conn.token:
            return {"status": "error", "message": "No token available, please complete OAuth first"}

        if conn.token.is_expired:
            conn.status = ProviderStatus.expired
            self._persist()
            return {"status": "expired", "message": "Token expired, please re-authorize"}

        try:
            result = await self._ping_provider(conn)
            conn.status = ProviderStatus.connected if result.get("ok") else ProviderStatus.error
            conn.last_error = "" if result.get("ok") else result.get("error", "Unknown error")
            conn.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            self._persist()
            return result
        except Exception as e:
            conn.status = ProviderStatus.error
            conn.last_error = str(e)
            self._persist()
            return {"status": "error", "ok": False, "message": str(e)}

    async def _ping_provider(self, conn: OAuthConnection) -> Dict:
        """Ping各Provider检查连接"""
        import httpx

        if conn.provider == "shopify":
            try:
                from app.services.shopify import load_token
                tok = load_token(conn.config.get("shop", ""))
                return {"ok": tok is not None, "status": "connected" if tok else "error",
                        "provider": "shopify", "shop": conn.config.get("shop", "")}
            except Exception as e:
                return {"ok": False, "status": "error", "error": str(e)}
        elif conn.provider in ("feishu", "dingtalk", "slack"):
            # For messaging platforms, just check token exists
            return {"ok": bool(conn.token and conn.token.access_token),
                    "status": "connected", "provider": conn.provider}
        elif conn.provider == "erpnext":
            base_url = conn.config.get("base_url", "")
            if not base_url:
                return {"ok": False, "error": "base_url not configured"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/method/frappe.ping",
                    headers={"Authorization": f"token {conn.config.get('api_key', '')}:{conn.config.get('api_secret', '')}"},
                    timeout=10,
                )
                return {"ok": resp.status_code == 200, "status": "connected" if resp.status_code == 200 else "error",
                        "provider": "erpnext"}
        elif conn.provider == "listmonk":
            base_url = conn.config.get("base_url", "")
            if not base_url:
                return {"ok": False, "error": "base_url not configured"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/health",
                    auth=(conn.config.get("username", ""), conn.config.get("password", "")),
                    timeout=10,
                )
                return {"ok": resp.status_code == 200, "status": "connected" if resp.status_code == 200 else "error",
                        "provider": "listmonk"}
        elif conn.provider == "17track":
            return {"ok": bool(conn.config.get("api_key")), "status": "connected", "provider": "17track"}
        elif conn.provider == "chatwoot":
            base_url = conn.config.get("base_url", "")
            token = conn.config.get("api_access_token", "")
            if not base_url or not token:
                return {"ok": False, "error": "Chatwoot config incomplete"}
            async with httpx.AsyncClient() as client:
                resp = await client.get(
                    f"{base_url}/api/v1/accounts/{conn.config.get('account_id', '1')}",
                    headers={"api_access_token": token},
                    timeout=10,
                )
                return {"ok": resp.status_code == 200, "status": "connected" if resp.status_code == 200 else "error",
                        "provider": "chatwoot"}

        return {"ok": True, "status": "connected", "provider": conn.provider}

    # ── 状态查询 ────────────────────────────────

    def get_status_summary(self) -> Dict:
        """所有Provider连接状态汇总（含 env-based 预配置检测）"""
        from app.config import settings
        summary = {}

        # env-based 预配置检测：若 .env 中填写了凭证，标记为 configured
        env_configured = {
            "feishu":  bool(settings.feishu_app_id and settings.feishu_app_secret),
            "shopify": bool(settings.shopify_client_id and settings.shopify_client_secret),
        }

        for pkey, template in PROVIDER_TEMPLATES.items():
            conns = [c for c in self._connections.values() if c.provider == pkey]
            connected = [c for c in conns if c.status == ProviderStatus.connected]
            is_env_configured = env_configured.get(pkey, False)

            if connected:
                status_str = "connected"
            elif conns or is_env_configured:
                status_str = "configured"
            else:
                status_str = "not_configured"

            summary[pkey] = {
                "name": template["name"],
                "icon": template["icon"],
                "total_connections": len(conns),
                "connected": len(connected),
                "status": status_str,
                "env_configured": is_env_configured,
            }
        return summary

    def get_provider_templates(self) -> List[Dict]:
        """获取所有Provider配置模板"""
        result = []
        for key, tmpl in PROVIDER_TEMPLATES.items():
            result.append({
                "provider": key,
                **tmpl,
                "connection_count": len([c for c in self._connections.values() if c.provider == key]),
            })
        return result


# ── 单例 ──────────────────────────────────────────

_oauth_manager: Optional[OAuthManager] = None


def get_oauth_manager() -> OAuthManager:
    global _oauth_manager
    if _oauth_manager is None:
        _oauth_manager = OAuthManager()
    return _oauth_manager
