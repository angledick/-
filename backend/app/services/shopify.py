"""
Shopify 集成服务 — 基于官方 ShopifyAPI SDK（v12+）。

OAuth 授权 + 产品数据同步 + Webhook 验证。
所有外部 API 调用均通过 shopify.Session / shopify.Product 等 SDK 方法完成，
不使用任何爬虫或页面抓取。
"""

import asyncio
import base64
import hmac
import hashlib
import html2text
import json
import uuid
from pathlib import Path
from typing import Optional
from pyactiveresource.connection import ResourceNotFound
from urllib.parse import urlencode

import shopify
from app.config import settings

# ── Shopify SDK 全局初始化 ──
# 设置 API Key / Secret，供 Session.create_permission_url 等类方法使用
shopify.Session.setup(
    api_key=settings.shopify_client_id,
    secret=settings.shopify_client_secret,
)

# ── 存储目录 ──
TOKENS_DIR = Path(settings.data_dir) / "shopify" / "tokens"


# ════════════════════════════════════════════════════════════════
# 数据结构
# ════════════════════════════════════════════════════════════════


class ShopifyToken:
    """Shopify 店铺访问令牌"""

    def __init__(self, shop: str, access_token: str, scope: str = ""):
        self.shop = shop
        self.access_token = access_token
        self.scope = scope

    def to_dict(self) -> dict:
        return {
            "shop": self.shop,
            "access_token": self.access_token,
            "scope": self.scope,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ShopifyToken":
        return cls(
            shop=data["shop"],
            access_token=data["access_token"],
            scope=data.get("scope", ""),
        )


class ShopifyProduct:
    """Shopify 产品（轻量封装，数据来自 shopify.Product）"""

    def __init__(self, shopify_id: int, title: str, handle: str,
                 product_type: str, vendor: str, variants: list[dict],
                 tags: list[str], body_html: str = ""):
        self.shopify_id = shopify_id
        self.title = title
        self.handle = handle
        self.product_type = product_type
        self.vendor = vendor
        self.variants = variants
        self.tags = tags
        self.body_html = body_html

    def to_dict(self) -> dict:
        return {
            "shopify_id": self.shopify_id,
            "title": self.title,
            "handle": self.handle,
            "product_type": self.product_type,
            "vendor": self.vendor,
            "variants": self.variants,
            "tags": self.tags,
            "body_html": self.body_html,
        }

    @property
    def description(self) -> str:
        """从 body_html 中提取纯文本描述（使用 html2text 库）。"""
        if not self.body_html:
            return ""
        return html2text.html2text(self.body_html).strip()

    @property
    def min_price(self) -> float:
        """最低变体价格。"""
        prices = [float(v["price"]) for v in self.variants if v.get("price")]
        return min(prices) if prices else 0.0


# ════════════════════════════════════════════════════════════════
# SDK 会话管理
# ════════════════════════════════════════════════════════════════


def _activate_session(shop: str, token: str) -> None:
    """激活 Shopify API 会话。"""
    session = shopify.Session(shop, settings.shopify_api_version)
    session.token = token
    shopify.ShopifyResource.activate_session(session)


def _clear_session() -> None:
    """清除当前 Shopify API 会话。"""
    shopify.ShopifyResource.clear_session()


def _run_in_session(shop: str, token: str, func, *args, **kwargs):
    """在 Shopify 会话上下文中执行同步操作。"""
    _activate_session(shop, token)
    try:
        return func(*args, **kwargs)
    finally:
        _clear_session()


async def _run_async(shop: str, token: str, func, *args, **kwargs):
    """异步执行 Shopify SDK 同步调用（通过线程池避免阻塞事件循环）。"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None, _run_in_session, shop, token, func, *args, **kwargs
    )


# ════════════════════════════════════════════════════════════════
# OAuth 授权流
# ════════════════════════════════════════════════════════════════


def build_authorization_url(shop: str, state: str = "") -> str:
    """构建 Shopify OAuth 授权 URL。

    基于 shopify.Session.create_permission_url 生成官方授权链接。

    Args:
        shop: 店铺域名，如 'my-store.myshopify.com'
        state: 防 CSRF 随机字符串（建议用 uuid）

    Returns:
        完整的 Shopify OAuth 授权 URL
    """
    if not state:
        state = uuid.uuid4().hex[:16]

    shop_url = f"https://{shop}"
    scopes = settings.shopify_scopes.split(",")
    redirect_uri = settings.shopify_redirect_uri

    session = shopify.Session(shop_url, settings.shopify_api_version)
    return session.create_permission_url(scopes, redirect_uri, state)


def exchange_code_for_token(shop: str, code: str, callback_params: Optional[dict] = None) -> ShopifyToken:
    """用授权码换取长期访问令牌。

    基于 shopify.Session.request_token 完成 OAuth 令牌交换。
    callback_params 应包含 OAuth 回调收到的完整参数（code, shop, hmac, timestamp, state），
    SDK 会自动验证 HMAC 签名。

    Args:
        shop: 店铺域名
        code: Shopify 返回的授权码
        callback_params: OAuth 回调完整参数字典（含 hmac/timestamp/state 等）

    Returns:
        ShopifyToken 对象

    Raises:
        RuntimeError: 令牌交换失败
    """
    shop_url = f"https://{shop}"
    try:
        session = shopify.Session(shop_url, settings.shopify_api_version)
        # 使用 SDK 的 request_token，自动验证 HMAC
        session.request_token(callback_params or {"code": code})
        token = ShopifyToken(
            shop=shop,
            access_token=session.token,
            scope=getattr(session, 'access_scopes', ''),
        )
        _save_token(token)
        return token
    except Exception as e:
        raise RuntimeError(f"Shopify OAuth token exchange failed: {e}")


# ════════════════════════════════════════════════════════════════
# 令牌管理
# ════════════════════════════════════════════════════════════════


def _save_token(token: ShopifyToken) -> None:
    """保存访问令牌到文件。"""
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    path = TOKENS_DIR / f"{token.shop}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(token.to_dict(), f, ensure_ascii=False, indent=2)


def load_token(shop: str) -> Optional[ShopifyToken]:
    """从文件加载访问令牌。

    Args:
        shop: 店铺域名

    Returns:
        ShopifyToken 对象，不存在返回 None
    """
    path = TOKENS_DIR / f"{shop}.json"
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ShopifyToken.from_dict(data)
    except Exception:
        return None


def list_connected_shops() -> list[dict]:
    """列出已连接的所有 Shopify 店铺摘要。"""
    if not TOKENS_DIR.exists():
        return []
    shops = []
    for path in sorted(TOKENS_DIR.glob("*.json")):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            shops.append({
                "shop": data.get("shop", path.stem),
                "scope": data.get("scope", ""),
            })
        except Exception:
            continue
    return shops


# ════════════════════════════════════════════════════════════════
# 产品数据同步（基于 shopify.Product SDK）
# ════════════════════════════════════════════════════════════════


async def fetch_products(shop: str, max_count: int = 50) -> list[ShopifyProduct]:
    """拉取 Shopify 店铺的产品列表。

    通过 shopify.Product.find() SDK 读取官方 API，
    不使用任何爬虫或页面抓取。

    Args:
        shop: 店铺域名
        max_count: 最大产品数（默认 50）

    Returns:
        ShopifyProduct 列表

    Raises:
        RuntimeError: 店铺未授权或 API 调用失败
    """
    token = load_token(shop)
    if not token:
        raise RuntimeError(f"Shop {shop} 未授权，请先完成 OAuth 授权")

    shop_url = f"https://{shop}"

    def _fetch():
        _activate_session(shop_url, token.access_token)
        try:
            raw_products = shopify.Product.find(limit=min(max_count, 250))
            results = []
            for item in raw_products:
                results.append(ShopifyProduct(
                    shopify_id=item.id,
                    title=item.title,
                    handle=item.handle if hasattr(item, 'handle') else "",
                    product_type=item.product_type or "",
                    vendor=item.vendor or "",
                    variants=[
                        {
                            "id": v.id,
                            "title": v.title,
                            "price": v.price,
                            "sku": getattr(v, 'sku', '') or '',
                            "requires_shipping": getattr(v, 'requires_shipping', True),
                        }
                        for v in getattr(item, 'variants', [])
                    ],
                    tags=[t.strip() for t in (item.tags or "").split(",") if t.strip()],
                    body_html=item.body_html or "",
                ))
            return results
        finally:
            _clear_session()

    return await _run_async(shop_url, token.access_token, _fetch)


async def fetch_product_by_id(shop: str, product_id: int) -> Optional[ShopifyProduct]:
    """按 ID 获取单个 Shopify 产品详情。

    通过 shopify.Product.find() SDK 读取官方 API。

    Args:
        shop: 店铺域名
        product_id: Shopify 产品 ID

    Returns:
        ShopifyProduct 对象，不存在返回 None
    """
    token = load_token(shop)
    if not token:
        raise RuntimeError(f"Shop {shop} 未授权")

    shop_url = f"https://{shop}"

    def _fetch():
        _activate_session(shop_url, token.access_token)
        try:
            item = shopify.Product.find(product_id)
            if not item:
                return None
            return ShopifyProduct(
                shopify_id=item.id,
                title=item.title,
                handle=item.handle if hasattr(item, 'handle') else "",
                product_type=item.product_type or "",
                vendor=item.vendor or "",
                variants=[
                    {
                        "id": v.id,
                        "title": v.title,
                        "price": v.price,
                        "sku": getattr(v, 'sku', '') or '',
                        "requires_shipping": getattr(v, 'requires_shipping', True),
                    }
                    for v in getattr(item, 'variants', [])
                ],
                tags=[t.strip() for t in (item.tags or "").split(",") if t.strip()],
                body_html=item.body_html or "",
            )
        except ResourceNotFound:
            return None
        finally:
            _clear_session()

    return await _run_async(shop_url, token.access_token, _fetch)


# ════════════════════════════════════════════════════════════════
# Webhook 验证 (HMAC)
# ════════════════════════════════════════════════════════════════


def verify_webhook(hmac_header: str, raw_body: bytes) -> bool:
    """验证 Shopify Webhook HMAC 签名。

    Args:
        hmac_header: 请求头 X-Shopify-Hmac-SHA256 的值
        raw_body: 请求的原始二进制 body

    Returns:
        True 表示签名有效
    """
    if not settings.shopify_client_secret:
        return False
    digest = hmac.new(
        settings.shopify_client_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    computed = hmac_header == digest.hex()
    if not computed:
        computed_base64 = hmac.new(
            settings.shopify_client_secret.encode("utf-8"),
            raw_body,
            hashlib.sha256,
        ).digest()
        computed = hmac_header == base64.b64encode(computed_base64).decode("utf-8")
    return computed


# ════════════════════════════════════════════════════════════════
# 序列化辅助
# ════════════════════════════════════════════════════════════════


def product_to_compliance_request(product: ShopifyProduct, target_market: str = "欧盟") -> dict:
    """将 Shopify 产品转换为合规查询请求数据。

    利用产品标题、类型、描述、价格及标签构建语义丰富的合规查询。

    Args:
        product: Shopify 产品
        target_market: 目标市场（默认欧盟）

    Returns:
        可用于 check_compliance() 的字典
    """
    query_parts = [
        product.title,
        product.product_type,
        product.description,
        f"价格 {product.min_price}",
    ] + product.tags
    query = " ".join(p for p in query_parts if p)
    return {
        "message": f"{query} 出口 {target_market}",
        "product_name": product.title,
        "product_type": product.product_type,
        "product_description": product.description[:500] if product.description else "",
        "product_price": product.min_price,
        "shopify_product_id": product.shopify_id,
    }
