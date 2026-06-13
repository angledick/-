"""
Shopify 集成 API 路由 — OAuth 授权 + 产品同步 + 合规检查。

端点：
- GET  /api/v1/shopify/auth        — 发起 OAuth 授权
- GET  /api/v1/shopify/callback    — OAuth 回调
- GET  /api/v1/shopify/shops       — 列出已连接店铺
- GET  /api/v1/shopify/{shop}/products    — 获取产品列表
- POST /api/v1/shopify/{shop}/check/{product_id} — 对产品做合规检查
- POST /api/v1/shopify/webhook     — 接收 Shopify Webhook
"""

from fastapi import APIRouter, HTTPException, Query, Request
import uuid

from app.models.schemas import (
    ShopifyAuthRequest,
    ShopifyShopInfo,
    ShopifyProductInfo,
    ShopifyComplianceCheckRequest,
    ShopifyImportRequest,
    ChatResponse,
    ComplianceResult,
)
from app.services.shopify import (
    build_authorization_url,
    exchange_code_for_token,
    list_connected_shops,
    fetch_products,
    fetch_product_by_id,
    verify_webhook,
    product_to_compliance_request,
)
from app.core.compliance_rules import check_compliance
from app.knowledge.store import retrieve_context, format_context_for_assistant
from app.core.action_chain import ActionChain

router = APIRouter(prefix="/api/v1", tags=["shopify"])


@router.get(
    "/shopify/auth",
    summary="Shopify OAuth 授权",
    description="""
    发起 Shopify OAuth 2.0 授权流程。
    返回 Shopify 授权页面的 URL，前端应重定向到该地址。
    """,
)
async def shopify_auth(shop: str = Query(..., description="店铺域名，如 my-store.myshopify.com")):
    """发起 Shopify OAuth 授权，返回授权 URL。"""
    if not shop.endswith(".myshopify.com"):
        raise HTTPException(
            status_code=400,
            detail="店铺域名格式错误，应为 *.myshopify.com",
        )
    state = uuid.uuid4().hex[:16]
    auth_url = build_authorization_url(shop, state=state)
    return {"authorization_url": auth_url, "shop": shop, "state": state}


@router.get(
    "/shopify/callback",
    summary="Shopify OAuth 回调",
    description="Shopify OAuth 授权完成后的回调处理，交换授权码获取访问令牌。",
)
async def shopify_callback(
    code: str = Query(..., description="授权码"),
    shop: str = Query(..., description="店铺域名"),
    state: str = Query(..., description="CSRF 校验令牌"),
    timestamp: str = Query(..., description="时间戳"),
    hmac: str = Query(..., description="HMAC 签名"),
):
    """处理 Shopify OAuth 回调，交换授权码为访问令牌。

    Shopify SDK 内部会自动验证 HMAC 签名。
    """
    params = {
        "code": code,
        "shop": shop,
        "state": state,
        "timestamp": timestamp,
        "hmac": hmac,
    }
    try:
        token = exchange_code_for_token(shop, code, callback_params=params)
        return {
            "status": "success",
            "shop": token.shop,
            "scope": token.scope,
            "message": f"店铺 {token.shop} 授权成功",
        }
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get(
    "/shopify/shops",
    response_model=list[ShopifyShopInfo],
    summary="已连接店铺列表",
    description="列出所有已完成 OAuth 授权的 Shopify 店铺。",
)
async def list_shops():
    """列出已连接的所有 Shopify 店铺。"""
    return list_connected_shops()


@router.get(
    "/shopify/{shop}/products",
    response_model=list[ShopifyProductInfo],
    summary="获取产品列表",
    description="拉取指定 Shopify 店铺的产品列表。需要店铺已完成 OAuth 授权。",
)
async def get_products(
    shop: str,
    max_count: int = Query(50, description="最大产品数", le=250),
):
    """获取 Shopify 店铺的产品列表。"""
    try:
        products = await fetch_products(shop, max_count=max_count)
        return [p.to_dict() for p in products]
    except RuntimeError as e:
        if "未授权" in str(e):
            raise HTTPException(status_code=401, detail=str(e))
        raise HTTPException(status_code=502, detail=str(e))


@router.post(
    "/shopify/{shop}/check/{product_id}",
    response_model=ChatResponse,
    summary="产品合规检查",
    description="""
    对指定的 Shopify 产品执行合规检查。

    流程：获取产品详情 → NLU 解析（基于产品标题/类型/标签）→ 规则引擎 → RAG 检索 → 合规报告
    """,
)
async def check_shopify_product(
    shop: str,
    product_id: int,
    req: ShopifyComplianceCheckRequest,
):
    """对 Shopify 产品执行完整合规检查。"""
    # 1. 获取产品信息
    try:
        product = await fetch_product_by_id(shop, product_id)
    except RuntimeError as e:
        raise HTTPException(status_code=401, detail=str(e))
    if not product:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")

    # 2. 构建合规查询
    query_data = product_to_compliance_request(product, target_market=req.target_market)
    product_name = query_data["product_name"]
    target_market = req.target_market

    # 3. 初始化操作链
    chain = ActionChain()
    chain.add_action(
        action_type="shopify_import",
        description_nl=f"从 Shopify 导入产品: {product_name} ({shop})",
        agent="Shopify",
        input_data={"shop": shop, "product_id": product_id},
    )

    # 4. 合规数据检查
    rule_action = chain.add_action(
        action_type="compliance_check",
        description_nl=f"合规数据层执行合规检查: 产品={product_name}, 国家={target_market}",
        agent="ComplianceRules",
    )
    rule_action.start()
    compliance_dict = check_compliance(product_name, target_market)
    rule_action.complete(compliance_dict)

    # 5. RAG 检索
    rag_action = chain.add_action(
        action_type="rag_retrieval",
        description_nl=f"RAG 检索法规知识库: {product_name} {target_market}",
        agent="RAG",
    )
    rag_action.start()
    rag_results = retrieve_context(f"{product_name} 出口 {target_market} 合规要求 认证")
    rag_context = format_context_for_assistant(rag_results)
    rag_action.complete({"result_count": len(rag_results)})

    # 6. 组装报告
    from app.services.compliance import format_compliance_report
    report = format_compliance_report(product_name, target_market, compliance_dict)
    if rag_results:
        report += f"\n\n---\n{rag_context}"

    chain.save()

    return ChatResponse(
        message=report,
        compliance_result=ComplianceResult(**compliance_dict),
        sources=[r["text"][:120] + "..." for r in rag_results],
        session_id=chain.chain_id,
        action_chain_id=chain.chain_id,
    )


@router.post(
    "/shopify/webhook",
    summary="Shopify Webhook 接收",
    description="接收 Shopify 推送的产品变更通知（新增/更新/删除时自动触发）。",
)
async def shopify_webhook(
    request: Request,
    x_shopify_hmac_sha256: str = Query(None, alias="X-Shopify-Hmac-SHA256"),
    x_shopify_topic: str = Query(None, alias="X-Shopify-Topic"),
    x_shopify_shop: str = Query(None, alias="X-Shopify-Shop"),
):
    """接收 Shopify Webhook 事件。

    支持的事件类型：
    - products/create
    - products/update
    - products/delete
    """
    raw_body = await request.body()

    # HMAC 验证
    if x_shopify_hmac_sha256 and not verify_webhook(x_shopify_hmac_sha256, raw_body):
        raise HTTPException(status_code=403, detail="HMAC 验证失败")

    topic = x_shopify_topic or "unknown"
    shop_domain = x_shopify_shop or "unknown"

    # 记录事件日志
    import json
    from pathlib import Path
    from app.config import settings

    webhook_log_dir = Path(settings.data_dir) / "shopify" / "webhooks"
    webhook_log_dir.mkdir(parents=True, exist_ok=True)
    log_path = webhook_log_dir / f"{shop_domain.replace('.', '_')}.jsonl"

    try:
        body_data = json.loads(raw_body)
    except Exception:
        body_data = {"raw": raw_body.decode("utf-8", errors="replace")}

    log_entry = {
        "topic": topic,
        "shop": shop_domain,
        "data": body_data,
    }
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

    return {
        "status": "received",
        "topic": topic,
        "shop": shop_domain,
    }
