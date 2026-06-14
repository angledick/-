"""销售订单管理 API — /api/v1/orders

提供：
  销售订单 CRUD（支持 Shopify/手动录入）
  支付记录管理
  三单一致性检查入口
  订单状态跟踪
"""

import logging
from fastapi import APIRouter, HTTPException, Query, Depends
from typing import Optional, List
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/orders", tags=["orders"])


# ─────────────────────────────────────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────────────────────────────────────

class OrderItem(BaseModel):
    sku:        str = ""
    name:       str
    qty:        int = 1
    unit_price: float = 0.0
    hs_code:    str = ""


class OrderCreate(BaseModel):
    platform:          str = Field("manual", description="shopify | manual | amazon | temu")
    platform_order_id: Optional[str] = None
    product_id:        Optional[str] = None
    buyer_name:        str
    buyer_email:       str = ""
    buyer_address: dict = Field(
        default={},
        description='{"country":"US","city":"NY","zip":"10001","street":"100 Broadway"}',
    )
    items:        List[OrderItem] = []
    currency:     str = "USD"
    total_amount: float = 0.0
    status:       str = "pending"
    notes:        str = ""


class OrderUpdate(BaseModel):
    buyer_name:    Optional[str] = None
    buyer_email:   Optional[str] = None
    buyer_address: Optional[dict] = None
    items:         Optional[List[OrderItem]] = None
    currency:      Optional[str] = None
    total_amount:  Optional[float] = None
    status:        Optional[str] = None
    notes:         Optional[str] = None


class PaymentCreate(BaseModel):
    channel_id:  Optional[str] = None
    payment_ref: Optional[str] = None
    amount:      float
    currency:    str = "USD"
    payer_email: str = ""
    payer_name:  str = ""
    status:      str = Field("completed", description="pending | completed | refunded | failed")
    paid_at:     Optional[str] = None
    notes:       str = ""


# ─────────────────────────────────────────────────────────────────────────────
# 订单端点
# ─────────────────────────────────────────────────────────────────────────────

@router.get("")
async def list_orders(
    product_id: Optional[str] = Query(None),
    platform:   Optional[str] = Query(None),
    status:     Optional[str] = Query(None),
    limit:      int = Query(50, ge=1, le=200),
    offset:     int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """订单列表（支持 product_id / platform / status 过滤）。"""
    from app.storage.order_store import list_orders as _lo
    return _lo(product_id=product_id, platform=platform, status=status,
                limit=limit, offset=offset)


@router.post("", status_code=201)
async def create_order(
    req: OrderCreate,
    current_user: dict = Depends(get_current_user),
):
    """创建销售订单。"""
    from app.storage.order_store import create_order as _co
    data = req.model_dump()
    # 序列化 items
    data["items"] = [item.model_dump() for item in req.items]
    # 自动计算总金额（如未提供）
    if data["total_amount"] == 0 and data["items"]:
        data["total_amount"] = sum(i["qty"] * i["unit_price"] for i in data["items"])
    order = _co(data)

    # 发布事件
    try:
        import asyncio
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        asyncio.create_task(bus.publish_raw({
            "type": "order:created",
            "source": "orders_api",
            "product_id": order.get("product_id"),
            "severity": "low",
            "data": {"order_id": order["id"], "amount": order["total_amount"],
                     "buyer": order["buyer_name"], "platform": order["platform"]},
        }))
    except Exception:
        pass

    return order


@router.get("/{order_id}")
async def get_order(order_id: str, current_user: dict = Depends(get_current_user)):
    """订单详情。"""
    from app.storage.order_store import get_order as _go
    order = _go(order_id)
    if not order:
        raise HTTPException(404, f"订单 {order_id} 不存在")
    return order


@router.put("/{order_id}")
async def update_order(
    order_id: str, req: OrderUpdate,
    current_user: dict = Depends(get_current_user),
):
    """更新订单信息。"""
    from app.storage.order_store import update_order as _uo
    updates = req.model_dump(exclude_none=True)
    if "items" in updates:
        updates["items"] = [i.model_dump() if hasattr(i, "model_dump") else i
                             for i in updates["items"]]
    order = _uo(order_id, updates)
    if not order:
        raise HTTPException(404, f"订单 {order_id} 不存在")
    return order


# ─────────────────────────────────────────────────────────────────────────────
# 支付记录
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{order_id}/payments")
async def get_payments(order_id: str, current_user: dict = Depends(get_current_user)):
    """支付记录列表 + 汇总。"""
    from app.storage.order_store import get_payments as _gp, get_payment_summary
    return {
        "payments": _gp(order_id),
        "summary":  get_payment_summary(order_id),
    }


@router.post("/{order_id}/payments", status_code=201)
async def add_payment(
    order_id: str, req: PaymentCreate,
    current_user: dict = Depends(get_current_user),
):
    """添加支付记录。"""
    from app.storage.order_store import get_order as _go, add_payment as _ap
    if not _go(order_id):
        raise HTTPException(404, f"订单 {order_id} 不存在")
    data = req.model_dump(exclude_none=True)
    return _ap(order_id, data)


# ─────────────────────────────────────────────────────────────────────────────
# 三单一致性检查
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/{order_id}/consistency-check")
async def consistency_check(
    order_id:        str,
    declaration_id:  Optional[str] = Query(None, description="关联报关单 ID"),
    logistics_id:    Optional[str] = Query(None, description="关联物流单 ID"),
    current_user:    dict = Depends(get_current_user),
):
    """三单一致性检查。

    自动尝试从报关单 order_id 字段反查关联报关单（如不传 declaration_id）。
    """
    from app.core.three_way_checker import get_three_way_checker

    # 自动关联：如未传 declaration_id，尝试通过 order_id 查找
    if not declaration_id:
        try:
            from app.storage.customs_store import list_declarations
            decls = list_declarations(status=None)
            matched = [d for d in decls if d.get("order_id") == order_id]
            if matched:
                declaration_id = matched[0]["id"]
        except Exception:
            pass

    checker = get_three_way_checker()
    return checker.check(
        order_id=order_id,
        declaration_id=declaration_id,
        logistics_id=logistics_id,
    )
