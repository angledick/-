"""Shopify 服务层辅助函数 — Webhook 验证与事件标准化。

注意：OAuth token 管理已移除（直连模式使用 SHOPIFY_CLIENT_SECRET 作为 Access Token）。
Webhook 验证逻辑已内联到 api/shopify.py，此模块仅保留向后兼容的函数签名。
"""

import base64
import hashlib
import hmac
import json
import logging
import uuid
from pathlib import Path
from typing import Any, Dict

from app.config import settings

logger = logging.getLogger(__name__)

# Shopify Webhook topic → 内部事件编码映射
WEBHOOK_TOPIC_MAP: Dict[str, str] = {
    "products/create": "product:created",
    "products/update": "product:content_updated",
    "products/delete": "product:ended",
    "orders/create": "order:created",
    "orders/updated": "order:updated",
    "orders/cancelled": "order:cancelled",
    "orders/fulfilled": "order:fulfilled",
    "inventory_levels/update": "product:status_changed",
}


def verify_webhook(hmac_header: str, raw_body: bytes) -> bool:
    """验证 Shopify Webhook HMAC 签名。"""
    if not settings.shopify_client_secret:
        return False
    digest = hmac.new(
        settings.shopify_client_secret.encode("utf-8"),
        raw_body,
        hashlib.sha256,
    ).digest()
    if hmac_header == digest.hex():
        return True
    return hmac_header == base64.b64encode(digest).decode("utf-8")


def normalize_webhook_event(topic: str, shop: str, body: dict) -> Dict[str, Any]:
    """将 Shopify Webhook 数据标准化为内部事件格式。"""
    event_code = WEBHOOK_TOPIC_MAP.get(topic, "system:shopify_webhook")
    entity_id = body.get("id", "")
    product_id = str(body.get("id", "")) if "product" in topic else ""
    order_id = str(body.get("id", "")) if "order" in topic else ""

    normalized = {
        "event_code": event_code,
        "source": "shopify",
        "shop": shop,
        "shopify_topic": topic,
        "message_id": f"shopify_{topic}_{entity_id}_{uuid.uuid4().hex[:8]}",
        "data": body,
    }

    if product_id:
        normalized["product_id"] = product_id
        normalized["product_title"] = body.get("title", "")
        normalized["product_type"] = body.get("product_type", "")
        normalized["vendor"] = body.get("vendor", "")
        normalized["tags"] = body.get("tags", "")
        normalized["handle"] = body.get("handle", "")

    if order_id:
        normalized["order_id"] = order_id

    return normalized


def log_webhook_event(topic: str, shop_domain: str, body_data: dict) -> Path:
    """记录 Webhook 事件到文件日志。"""
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

    return log_path


# ── 向后兼容：旧代码可能引用的函数 ──────────────────

def get_shop_config() -> dict:
    """返回当前店铺配置。"""
    return {
        "shop": settings.shopify_domain,
        "client_id": settings.shopify_client_id,
        "client_secret": settings.shopify_client_secret,
        "api_version": settings.shopify_api_version,
    }
