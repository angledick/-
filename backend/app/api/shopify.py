"""Shopify 集成 API 路由 — 直连 Admin REST API。

端点：
- GET    /api/v1/shopify/products           — 获取商品列表
- GET    /api/v1/shopify/products/{id}       — 获取单个商品
- POST   /api/v1/shopify/products            — 创建商品
- PUT    /api/v1/shopify/products/{id}       — 更新商品
- DELETE /api/v1/shopify/products/{id}       — 删除商品
- PUT    /api/v1/shopify/products/{id}/compliance — 更新商品合规字段
- POST   /api/v1/shopify/products/{id}/enrich     — 自动补足合规字段（三层策略）
- POST   /api/v1/shopify/sync                — 同步 Shopify 商品到本地
- GET    /api/v1/shopify/shops               — 已配置店铺信息
- POST   /api/v1/shopify/webhook             — Webhook 接收（HMAC 验证）
"""

import base64
import hashlib
import hmac
import json
import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.config import settings
from app.services import shopify_api

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1", tags=["shopify"])


# ════════════════════════════════════════════════════════════════
# 店铺信息
# ════════════════════════════════════════════════════════════════


@router.get(
    "/shopify/shops",
    summary="已配置店铺信息",
    description="返回当前 .env 中配置的 Shopify 店铺信息。",
)
async def list_shops():
    """返回已配置的店铺信息和应用配置（静态，来自 .env）。"""
    return [
        {
            "shop": settings.shopify_domain or "未配置",
            "client_id": settings.shopify_client_id[:8] + "..." if settings.shopify_client_id else "",
            "api_version": settings.shopify_api_version,
            "webhook_api_version": settings.shopify_webhook_api_version,
            "app_url": settings.shopify_app_url,
            "embedded": settings.shopify_embedded,
            "configured": bool(settings.shopify_domain and settings.shopify_client_secret),
        }
    ]


# ════════════════════════════════════════════════════════════════
# 商品 CRUD — 直连 Shopify Admin REST API
# ════════════════════════════════════════════════════════════════


@router.get(
    "/shopify/products",
    summary="获取 Shopify 商品列表",
)
async def get_products(
    limit: int = Query(50, description="每页数量 (1-250)", le=250),
    since_id: int = Query(None, description="分页游标"),
):
    """直接从 Shopify Admin REST API 获取商品列表。"""
    try:
        return await shopify_api.get_products(limit=limit, since_id=since_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


@router.get(
    "/shopify/products/count",
    summary="商品总数",
)
async def count_products():
    """获取 Shopify 商品的总数。"""
    try:
        return await shopify_api.count_products()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


@router.get(
    "/shopify/products/{product_id}",
    summary="获取单个商品",
)
async def get_product(product_id: int):
    """获取单个 Shopify 商品详情。"""
    try:
        return await shopify_api.get_product(product_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


@router.post(
    "/shopify/products",
    summary="创建商品",
)
async def create_product(request: Request):
    """在 Shopify 创建商品。Body 为商品 JSON（可直接传 Shopify 格式）。"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON body")

    try:
        return await shopify_api.create_product(data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


@router.put(
    "/shopify/products/{product_id}",
    summary="更新商品",
)
async def update_product(product_id: int, request: Request):
    """更新 Shopify 商品。"""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="无效的 JSON body")

    try:
        return await shopify_api.update_product(product_id, data)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


@router.delete(
    "/shopify/products/{product_id}",
    summary="删除商品",
)
async def delete_product(product_id: int):
    """删除 Shopify 商品。"""
    try:
        await shopify_api.delete_product(product_id)
        return {"status": "deleted", "product_id": product_id}
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Shopify API 错误: {e}")


# ════════════════════════════════════════════════════════════════
# 商品合规字段自动补足（HS编码 / 原产国 / 法规认证）
# ════════════════════════════════════════════════════════════════


@router.post(
    "/shopify/products/{product_id}/enrich",
    summary="自动补足商品合规字段",
    description="三层策略自动补足 HS 编码、原产国、认证要求：本地 HS 库 → RAG 法规 → 在线搜索。",
)
async def enrich_compliance(
    product_id: int,
    body: dict = None,
):
    """自动补足商品合规字段。

    可选 Body 参数:
      - market: 目标市场（默认 eu）
      - use_online: 是否启用在线搜索（默认 true）
      - title / product_type / tags / vendor: 覆盖商品信息（默认从 Shopify 拉取）
    """
    try:
        from app.services.compliance_enrichment import enrich_product_compliance

        body = body or {}
        market = body.get("market", "eu")
        use_online = body.get("use_online", True)

        # 如果未提供商品信息，从 Shopify 拉取
        title = body.get("title", "")
        product_type = body.get("product_type", "")
        tags = body.get("tags", "")
        vendor = body.get("vendor", "")

        if not title:
            detail = await shopify_api.get_product(product_id)
            p = detail.get("product", {})
            title = p.get("title", "")
            product_type = p.get("product_type", "")
            tags = p.get("tags", "")
            vendor = p.get("vendor", "")

        return await enrich_product_compliance(
            product_id=product_id,
            title=title,
            product_type=product_type,
            tags=tags,
            vendor=vendor,
            market=market,
            use_online=use_online,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"合规补足失败: {e}")


# ════════════════════════════════════════════════════════════════
# 商品合规字段手动更新（原产国 / HS编码 / 成本）
# ════════════════════════════════════════════════════════════════


@router.put(
    "/shopify/products/{product_id}/compliance",
    summary="更新商品合规字段",
    description="更新 Shopify 商品的原产国、HS 编码、单件成本等跨境合规字段。",
)
async def update_compliance(
    product_id: int,
    body: dict,
):
    """更新商品合规字段。

    Body 参数（均可选）:
      - country_code_of_origin: 原产国代码（如 "CN"）
      - harmonized_system_code: HS 编码（如 "9405.42"）
      - cost: 单件成本（如 "12.50"）
    """
    try:
        return await shopify_api.update_product_compliance(
            product_id,
            country_code_of_origin=body.get("country_code_of_origin"),
            harmonized_system_code=body.get("harmonized_system_code"),
            cost=body.get("cost"),
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"合规字段更新失败: {e}")


# ════════════════════════════════════════════════════════════════
# 同步到本地
# ════════════════════════════════════════════════════════════════


@router.post(
    "/shopify/sync",
    summary="同步 Shopify 商品到本地",
    description="从 Shopify 拉取商品列表，同步到本地 ProductStorage。",
)
async def sync_products(
    limit: int = Query(250, description="同步数量上限", le=250),
):
    """同步 Shopify 商品到本地 ProductStorage。"""
    try:
        return await shopify_api.sync_to_local(limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"同步失败: {e}")


# ════════════════════════════════════════════════════════════════
# Webhook 接收 — HMAC 验证 + 日志
# ════════════════════════════════════════════════════════════════


# Shopify Webhook topic → 内部事件编码映射
WEBHOOK_TOPIC_MAP = {
    "products/create": "product:created",
    "products/update": "product:content_updated",
    "products/delete": "product:ended",
    "orders/create": "order:created",
    "orders/updated": "order:updated",
    "orders/cancelled": "order:cancelled",
    "orders/fulfilled": "order:fulfilled",
    "inventory_levels/update": "product:status_changed",
}


def _verify_webhook(hmac_header: str, raw_body: bytes) -> bool:
    """验证 Shopify Webhook HMAC 签名。"""
    secret = settings.shopify_client_secret
    if not secret:
        return False
    digest = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    if hmac_header == digest.hex():
        return True
    return hmac_header == base64.b64encode(digest).decode("utf-8")


def _log_webhook(topic: str, shop_domain: str, body_data: dict):
    """记录 Webhook 事件到文件日志。"""
    from pathlib import Path
    import uuid

    webhook_log_dir = Path(settings.data_dir) / "shopify" / "webhooks"
    webhook_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = webhook_log_dir / f"{shop_domain.replace('.', '_')}.jsonl"

    log_entry = {
        "topic": topic,
        "shop": shop_domain,
        "data": body_data,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")


@router.post(
    "/shopify/webhook",
    summary="Shopify Webhook 接收",
    description="""
    接收 Shopify 推送的事件通知，验证 HMAC 签名并记录日志。
    商品操作走直连 API，Webhook 仅用于事件感知和日志。
    """,
)
async def shopify_webhook(request: Request):
    """接收 Shopify Webhook → HMAC 验证 → 日志记录。"""
    raw_body = await request.body()

    # HMAC 验证
    hmac_header = request.headers.get("X-Shopify-Hmac-SHA256", "")
    if hmac_header and not _verify_webhook(hmac_header, raw_body):
        raise HTTPException(status_code=403, detail="HMAC 验证失败")

    topic = request.headers.get("X-Shopify-Topic", "unknown")
    shop_domain = request.headers.get(
        "X-Shopify-Shop-Domain",
        request.headers.get("X-Shopify-Shop", "unknown"),
    )

    try:
        body_data = json.loads(raw_body)
    except Exception:
        body_data = {"raw": raw_body.decode("utf-8", errors="replace")}

    # 记录 Webhook 日志
    _log_webhook(topic, shop_domain, body_data)

    event_code = WEBHOOK_TOPIC_MAP.get(topic, "system:shopify_webhook")

    # 商品变更时自动同步到本地
    if topic in ("products/create", "products/update", "products/delete"):
        try:
            await shopify_api.sync_to_local(limit=50)
            logger.info("Webhook 触发自动同步: topic=%s", topic)
        except Exception as e:
            logger.warning("Webhook 触发同步失败: %s", e)

    # 商品创建时自动触发合规字段补足
    if topic == "products/create":
        product_id = body_data.get("id")
        if product_id:
            import asyncio as _aio
            from app.services.compliance_enrichment import enrich_product_compliance
            try:
                enrich_result = await enrich_product_compliance(
                    product_id=product_id,
                    title=body_data.get("title", ""),
                    product_type=body_data.get("product_type", ""),
                    tags=body_data.get("tags", ""),
                    vendor=body_data.get("vendor", ""),
                    market="eu",
                    use_online=False,  # Webhook 触发时先只用本地+RAG
                )
                logger.info(
                    "Webhook 触发合规补足: product=%s hs=%s",
                    product_id, enrich_result.get("hs_code"),
                )
            except Exception as e:
                logger.warning("Webhook 触发合规补足失败: product=%s err=%s", product_id, e)

    logger.info(
        "Shopify Webhook 已接收: topic=%s → event_code=%s shop=%s",
        topic, event_code, shop_domain,
    )

    return {
        "status": "received",
        "topic": topic,
        "event_code": event_code,
        "shop": shop_domain,
    }
