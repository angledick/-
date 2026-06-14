"""Shopify Admin REST API 直连客户端。

使用 httpx.AsyncClient 直接调用 Shopify Admin REST API。

认证流程:
  1. 通过 client_credentials grant 获取 Admin API Access Token
  2. 使用 X-Shopify-Access-Token header 调用 Admin REST API
  3. 令牌缓存（默认 24 小时过期）
"""

import json
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ── 令牌缓存 ──
_cached_token: Optional[str] = None
_cached_token_expiry: float = 0


def _base_url() -> str:
    """构建 Shopify Admin REST API base URL。"""
    domain = settings.shopify_domain or "99hg9z-1k.myshopify.com"
    version = settings.shopify_api_version or "2026-07"
    return f"https://{domain}/admin/api/{version}"


async def _get_access_token() -> str:
    """通过 client_credentials grant 获取 Admin API Access Token。

    POST https://{shop}.myshopify.com/admin/oauth/access_token
      grant_type=client_credentials
      client_id=...
      client_secret=...

    返回的令牌默认 24 小时过期，缓存到内存。
    """
    global _cached_token, _cached_token_expiry

    # 检查缓存
    if _cached_token and time.time() < _cached_token_expiry - 60:
        return _cached_token

    domain = settings.shopify_domain or "99hg9z-1k.myshopify.com"
    token_url = f"https://{domain}/admin/oauth/access_token"

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            token_url,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": settings.shopify_client_id,
                "client_secret": settings.shopify_client_secret,
            },
        )
        resp.raise_for_status()
        data = resp.json()

    _cached_token = data.get("access_token", "")
    expires_in = data.get("expires_in", 86400)
    _cached_token_expiry = time.time() + expires_in

    logger.info("Shopify Admin API 令牌已获取, 有效期=%ds", expires_in)
    return _cached_token


async def _headers() -> dict:
    """构建请求头（包含动态获取的 access token）。"""
    token = await _get_access_token()
    return {
        "X-Shopify-Access-Token": token,
        "Content-Type": "application/json",
    }


# ════════════════════════════════════════════════════════════════
# 商品 CRUD
# ════════════════════════════════════════════════════════════════


async def get_products(
    limit: int = 50,
    since_id: Optional[int] = None,
    fields: Optional[str] = None,
) -> dict:
    """获取商品列表。

    Args:
        limit: 每页数量 (1-250)
        since_id: 分页游标（只返回 ID > since_id 的商品）
        fields: 限定返回字段（逗号分隔）

    Returns:
        {"products": [...]}
    """
    params: dict[str, Any] = {"limit": min(limit, 250)}
    if since_id:
        params["since_id"] = since_id
    if fields:
        params["fields"] = fields

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_base_url()}/products.json",
            headers=await _headers(),
            params=params,
        )
        resp.raise_for_status()
        return resp.json()


async def get_product(product_id: int) -> dict:
    """获取单个商品详情。

    Returns:
        {"product": {...}}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_base_url()}/products/{product_id}.json",
            headers=await _headers(),
        )
        resp.raise_for_status()
        return resp.json()


async def create_product(data: dict) -> dict:
    """创建商品。

    Args:
        data: 商品数据（需包含 product 对象）

    Returns:
        {"product": {...}}
    """
    if "product" not in data:
        data = {"product": data}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(
            f"{_base_url()}/products.json",
            headers=await _headers(),
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


async def update_product(product_id: int, data: dict) -> dict:
    """更新商品。

    Args:
        product_id: 商品 ID
        data: 更新数据（需包含 product 对象，或直接是字段）

    Returns:
        {"product": {...}}
    """
    if "product" not in data:
        data = {"product": {**data, "id": product_id}}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{_base_url()}/products/{product_id}.json",
            headers=await _headers(),
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


async def delete_product(product_id: int) -> None:
    """删除商品。"""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.delete(
            f"{_base_url()}/products/{product_id}.json",
            headers=await _headers(),
        )
        resp.raise_for_status()


async def count_products() -> dict:
    """获取商品总数。

    Returns:
        {"count": 42}
    """
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{_base_url()}/products/count.json",
            headers=await _headers(),
        )
        resp.raise_for_status()
        return resp.json()


# ════════════════════════════════════════════════════════════════
# Variant / InventoryItem 更新（合规字段）
# ════════════════════════════════════════════════════════════════


async def update_variant(variant_id: int, data: dict) -> dict:
    """更新单个 Variant（含合规字段）。

    可更新字段:
      - price, compare_at_price, sku, barcode, weight, weight_unit
      - country_code_of_origin (原产国，如 "CN")
      - harmonized_system_code (HS 编码，如 "9405.42")
      - taxable, requires_shipping, fulfillment_service

    Returns:
        {"variant": {...}}
    """
    if "variant" not in data:
        data = {"variant": {**data, "id": variant_id}}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{_base_url()}/variants/{variant_id}.json",
            headers=await _headers(),
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


async def update_inventory_item(inventory_item_id: int, data: dict) -> dict:
    """更新 InventoryItem（成本字段）。

    可更新字段:
      - cost (单件成本，如 "12.50")
      - tracked (是否跟踪库存)
      - country_code_of_origin, harmonized_system_code

    Returns:
        {"inventory_item": {...}}
    """
    if "inventory_item" not in data:
        data = {"inventory_item": {**data, "id": inventory_item_id}}

    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.put(
            f"{_base_url()}/inventory_items/{inventory_item_id}.json",
            headers=await _headers(),
            json=data,
        )
        resp.raise_for_status()
        return resp.json()


async def update_product_compliance(
    product_id: int,
    *,
    country_code_of_origin: str | None = None,
    harmonized_system_code: str | None = None,
    cost: str | None = None,
) -> dict:
    """一站式更新商品合规字段。

    自动查找商品的 variant_id 和 inventory_item_id，
    分别调用 variant 和 inventory_item 接口更新。

    Returns:
        {"variant": {...}, "inventory_item": {...}}
    """
    # 获取商品详情，拿 variant_id / inventory_item_id
    detail = await get_product(product_id)
    product = detail.get("product", {})
    variants = product.get("variants", [])
    if not variants:
        raise ValueError(f"商品 {product_id} 没有 variant")

    variant_id = variants[0]["id"]
    inventory_item_id = variants[0].get("inventory_item_id")

    result = {"product_id": product_id, "variant_id": variant_id}
    errors = []

    # 更新 variant 合规字段（需要 write_products 权限）
    variant_data: dict = {}
    if country_code_of_origin:
        variant_data["country_code_of_origin"] = country_code_of_origin
    if harmonized_system_code:
        variant_data["harmonized_system_code"] = harmonized_system_code
    if variant_data:
        try:
            v = await update_variant(variant_id, variant_data)
            result["variant"] = v.get("variant", {})
        except httpx.HTTPStatusError as e:
            logger.warning("variant 合规字段更新失败 (可能权限不足): %s", e)
            errors.append(f"variant: {e.response.status_code}")

    # 更新 inventory_item 成本（需要 write_inventory 权限）
    if cost and inventory_item_id:
        try:
            ii = await update_inventory_item(
                inventory_item_id, {"cost": cost}
            )
            result["inventory_item"] = ii.get("inventory_item", {})
        except httpx.HTTPStatusError as e:
            logger.warning("inventory_item 成本更新失败 (可能缺少 write_inventory 权限): %s", e)
            errors.append(f"inventory_item: {e.response.status_code}")

    if errors:
        result["warnings"] = errors

    logger.info("商品 %s 合规字段更新完成: ok=%s warnings=%s", product_id, [k for k in result if k not in ("product_id","variant_id","warnings")], errors)
    return result


# ════════════════════════════════════════════════════════════════
# 同步到本地 ProductStorage
# ════════════════════════════════════════════════════════════════


async def sync_to_local(limit: int = 250) -> dict:
    """从 Shopify 拉取商品并同步到本地 ProductStorage。

    Args:
        limit: 一次同步的商品数量上限

    Returns:
        {"synced": N, "total": M, "products": [...]}
    """
    from app.core.product_storage import ProductStorage
    from app.models.schemas import ProductCreateRequest, ProductUpdateRequest

    storage = ProductStorage()

    # 拉取 Shopify 商品
    data = await get_products(limit=limit)
    products = data.get("products", [])

    synced = 0
    for sp in products:
        pid = f"shopify_{sp['id']}"
        title = sp.get("title", f"Shopify Product {sp['id']}")
        ptype = sp.get("product_type", "未分类")
        vendor = sp.get("vendor", "")
        tags_raw = sp.get("tags", "")
        tags_list = [t.strip() for t in tags_raw.split(",") if t.strip()] if tags_raw else []

        existing = storage.get_product(pid)

        # 额外元数据存入 metadata
        meta = {
            "shopify_id": sp["id"],
            "handle": sp.get("handle", ""),
            "status": sp.get("status", "active"),
            "variants": sp.get("variants", []),
            "images": sp.get("images", []),
        }

        if existing:
            # 更新
            try:
                await storage.update_product(pid, ProductUpdateRequest(
                    name=title,
                    product_type=ptype,
                    vendor=vendor,
                    tags=tags_list,
                ))
            except Exception as e:
                logger.warning("更新商品失败 pid=%s: %s", pid, e)
        else:
            # 创建
            try:
                await storage.create_product(ProductCreateRequest(
                    name=title,
                    product_type=ptype,
                    vendor=vendor,
                    tags=tags_list,
                ), product_id=pid)
            except Exception as e:
                logger.warning("创建商品失败 shopify_id=%s: %s", sp["id"], e)
                continue

        # 写入 Shopify 元数据
        product = storage.get_product(pid)
        if product:
            product.metadata.update(meta)
            from pathlib import Path
            from app.config import settings as _s
            _products_dir = Path(_s.data_dir) / "products"
            storage._write_product(_products_dir / pid, product)

        synced += 1

    total = (await count_products()).get("count", 0)
    logger.info("Shopify 同步完成: synced=%d total=%d", synced, total)
    return {"synced": synced, "total": total, "products": products}


# ════════════════════════════════════════════════════════════════
# 本地产品 → Shopify 推送（缺失字段自动补全）
# ════════════════════════════════════════════════════════════════


# ── 缺失字段默认值映射 ──
_DEFAULT_PRODUCT_TYPE = "General"          # Shopify product_type 默认值
_DEFAULT_VENDOR = "Unknown"               # Shopify vendor 默认值
_DEFAULT_BODY_HTML = "<p>Product description pending.</p>"
_DEFAULT_PRICE = "0.00"                    # Shopify variant 默认价格
_DEFAULT_SKU_PREFIX = "AST"                # 自动生成 SKU 前缀


def _build_shopify_product_payload(product: Any) -> dict:
    """将本地 ProductInfo 转换为 Shopify Admin REST API 创建商品的 payload。

n    自动补全缺失的 Shopify 必填字段：
      - title        → product.name（必填）
      - product_type → product.product_type 或默认 "General"
      - vendor       → product.vendor 或默认 "Unknown"
      - body_html    → 从 tags / target_markets 生成简介
      - tags         → product.tags + target_markets 拼接
      - variants     → 含 price / sku / requires_shipping
      - status       → "draft"（待人工上架）
    """
    name = getattr(product, "name", "") or "Untitled Product"
    product_type = getattr(product, "product_type", "") or _DEFAULT_PRODUCT_TYPE
    vendor = getattr(product, "vendor", "") or _DEFAULT_VENDOR
    tags_list = list(getattr(product, "tags", []) or [])
    target_markets = list(getattr(product, "target_markets", []) or [])
    hs_code = getattr(product, "hs_code", "") or ""
    product_id = getattr(product, "id", "") or ""

    # 合并 tags（本地 tags + 目标市场）
    all_tags = list(set(tags_list + target_markets))
    if hs_code:
        all_tags.append(f"HS:{hs_code}")
    tags_str = ", ".join(sorted(all_tags)) if all_tags else ""

    # 自动生成 body_html
    market_text = ", ".join(target_markets) if target_markets else "Global"
    body_parts = [f"<p><strong>{name}</strong></p>"]
    if product_type and product_type != _DEFAULT_PRODUCT_TYPE:
        body_parts.append(f"<p>Category: {product_type}</p>")
    body_parts.append(f"<p>Target Markets: {market_text}</p>")
    if hs_code:
        body_parts.append(f"<p>HS Code: {hs_code}</p>")
    body_html = "\n".join(body_parts)

    # 自动生成 SKU（本地 product_id + 时间戳后4位保证唯一性）
    import time
    sku_suffix = str(int(time.time()))[-4:]
    sku = f"{_DEFAULT_SKU_PREFIX}-{product_id[:8].upper()}-{sku_suffix}" if product_id else f"{_DEFAULT_SKU_PREFIX}-{sku_suffix}"

    payload = {
        "product": {
            "title": name,
            "body_html": body_html,
            "product_type": product_type,
            "vendor": vendor,
            "tags": tags_str,
            "status": "draft",          # 草稿状态，需人工审核后上架
            "variants": [
                {
                    "title": "Default",
                    "price": _DEFAULT_PRICE,
                    "sku": sku,
                    "requires_shipping": True,
                }
            ],
        }
    }
    return payload


async def sync_to_shopify(product: Any) -> dict:
    """将本地创建的产品同步推送到 Shopify，自动补全缺失字段。

n    流程：
      1. 检查 Shopify 是否已连接（env 配置存在）
      2. 构建商品 payload（缺失字段自动补全）
      3. 调用 Shopify Admin REST API 创建商品
      4. 创建成功后自动补充合规字段（HS Code / 原产国）
      5. 将 Shopify 返回的 ID / handle 写入本地 product.metadata

n    Args:
        product: ProductInfo 对象（含 id, name, product_type, hs_code 等）

n    Returns:
        {"ok": True, "shopify_product_id": 123, "handle": "...", "warnings": [...]} 或
        {"ok": False, "error": "...", "skipped": True}
    """
    # ── 前置检查：Shopify 凭证是否配置 ──
    if not settings.shopify_client_id or not settings.shopify_client_secret:
        logger.info("sync_to_shopify: Shopify 未配置凭证，跳过同步 (product_id=%s)", getattr(product, "id", "?"))
        return {"ok": False, "skipped": True, "reason": "shopify_not_configured"}

    product_id = getattr(product, "id", "")
    product_name = getattr(product, "name", "unknown")

    # ── 检查是否已经同步过（metadata 中已有 shopify_id）──
    existing_meta = getattr(product, "metadata", {}) or {}
    if existing_meta.get("shopify_id"):
        logger.info("sync_to_shopify: 产品 %s 已有 Shopify ID=%s，跳过重复推送",
                     product_id, existing_meta["shopify_id"])
        return {"ok": True, "skipped": True, "reason": "already_synced",
                "shopify_product_id": existing_meta["shopify_id"]}

    logger.info("sync_to_shopify: 开始推送产品 %s (%s) → Shopify", product_id, product_name)

    # ── Step 1: 构建带补全字段的 payload ──
    payload = _build_shopify_product_payload(product)
    warnings = []

    try:
        # ── Step 2: 创建 Shopify 商品 ──
        result = await create_product(payload)
        sp = result.get("product", {})
        shopify_pid = sp.get("id")
        handle = sp.get("handle", "")

        if not shopify_pid:
            logger.warning("sync_to_shopify: Shopify 创建返回无 product_id, result=%s", result)
            return {"ok": False, "error": "Shopify 返回无效响应"}

        logger.info("sync_to_shopify: Shopify 商品创建成功 id=%s handle=%s", shopify_pid, handle)

        # ── Step 3: 补充合规字段（HS Code + 原产国 CN）──
        hs_code = getattr(product, "hs_code", "") or ""
        if hs_code:
            # Shopify HS Code 需要纯数字或带点格式（如 9405.40）
            hs_formatted = hs_code.replace("-", ".").strip()
            try:
                compliance_result = await update_product_compliance(
                    shopify_pid,
                    country_code_of_origin="CN",
                    harmonized_system_code=hs_formatted,
                )
                if compliance_result.get("warnings"):
                    warnings.extend(compliance_result["warnings"])
                logger.info("sync_to_shopify: 合规字段更新成功 hs=%s origin=CN", hs_formatted)
            except Exception as e:
                warnings.append(f"compliance_update_failed: {e}")
                logger.warning("sync_to_shopify: 合规字段更新失败: %s", e)

        # ── Step 4: 将 Shopify 元数据写回本地产品 ──
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            local_product = storage.get_product(product_id)
            if local_product:
                local_product.metadata.update({
                    "shopify_id": shopify_pid,
                    "shopify_handle": handle,
                    "shopify_status": "draft",
                    "shopify_synced_at": datetime.now(timezone.utc).isoformat(),
                })
                from pathlib import Path as _P
                _products_dir = _P(settings.data_dir) / "products"
                storage._write_product(_products_dir / product_id, local_product)
                logger.info("sync_to_shopify: 本地产品 %s metadata 已更新 shopify_id=%s", product_id, shopify_pid)
        except Exception as e:
            warnings.append(f"metadata_writeback_failed: {e}")
            logger.warning("sync_to_shopify: 元数据回写失败: %s", e)

        # ── Step 5: WS 推送同步结果 ──
        try:
            from app.services.ws_manager import ws_manager
            await ws_manager.broadcast({
                "type": "shopify_synced",
                "payload": {
                    "product_id": product_id,
                    "shopify_product_id": shopify_pid,
                    "handle": handle,
                    "status": "draft",
                },
            })
        except Exception:
            pass

        return {
            "ok": True,
            "shopify_product_id": shopify_pid,
            "handle": handle,
            "warnings": warnings if warnings else None,
        }

    except httpx.HTTPStatusError as e:
        error_body = ""
        try:
            error_body = e.response.text[:500]
        except Exception:
            pass
        logger.error("sync_to_shopify: Shopify API 错误 %s: %s", e.response.status_code, error_body)
        return {"ok": False, "error": f"Shopify API {e.response.status_code}: {error_body}", "skipped": False}
    except Exception as e:
        logger.error("sync_to_shopify: 同步失败 product_id=%s: %s", product_id, e, exc_info=True)
        return {"ok": False, "error": str(e), "skipped": False}
