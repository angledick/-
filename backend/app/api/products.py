"""产品管理API — /api/v1/products"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from app.models.schemas import (
    ProductInfo, ProductCreateRequest, ProductUpdateRequest,
    ProductLifecycleStage, ProductLifecycleUpdate,
)
from app.core.product_storage import get_product_storage

router = APIRouter(prefix="/api/v1/products", tags=["products"])


@router.get("", response_model=List[ProductInfo])
async def list_products(
    lifecycle_stage: Optional[str] = Query(None, description="生命周期阶段"),
    product_type: Optional[str] = Query(None, description="产品类型"),
    market: Optional[str] = Query(None, description="目标市场"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """列出产品"""
    storage = get_product_storage()
    stage = ProductLifecycleStage(lifecycle_stage) if lifecycle_stage else None
    return storage.list_products(
        lifecycle_stage=stage,
        product_type=product_type,
        market=market,
        limit=limit,
        offset=offset,
    )


@router.post("", response_model=ProductInfo)
async def create_product(request: ProductCreateRequest):
    """创建产品"""
    storage = get_product_storage()
    try:
        product = await storage.create_product(request)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    # 发布产品创建事件
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        await bus.publish_raw({
            "type": "product:created",
            "source": "api",
            "product_id": product.id,
            "business_stage": "阶段2",
            "data": {"name": product.name, "product_type": product.product_type},
        })
    except Exception:
        pass

    # 自动注册产品级定时任务
    try:
        from app.core.scheduler import register_product_jobs
        register_product_jobs(product.id)
    except Exception:
        pass

    return product


@router.get("/count")
async def count_products(lifecycle_stage: Optional[str] = None):
    """统计产品数量"""
    storage = get_product_storage()
    stage = ProductLifecycleStage(lifecycle_stage) if lifecycle_stage else None
    return {"count": storage.count_products(stage)}


@router.get("/{product_id}", response_model=ProductInfo)
async def get_product(product_id: str):
    """获取产品详情"""
    storage = get_product_storage()
    product = storage.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")
    return product


@router.put("/{product_id}", response_model=ProductInfo)
async def update_product(product_id: str, request: ProductUpdateRequest):
    """更新产品"""
    storage = get_product_storage()
    product = await storage.update_product(product_id, request)
    if not product:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")
    return product


@router.put("/{product_id}/lifecycle", response_model=ProductInfo)
async def update_lifecycle(product_id: str, request: ProductLifecycleUpdate):
    """更新产品生命周期阶段"""
    storage = get_product_storage()
    try:
        product = await storage.update_lifecycle_stage(product_id, request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not product:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")

    # 发布状态变更事件
    try:
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        await bus.publish_raw({
            "type": "product:status_changed",
            "source": "api",
            "product_id": product_id,
            "severity": "medium",
            "data": {
                "new_stage": request.lifecycle_stage.value,
                "reason": request.reason,
            },
        })
    except Exception:
        pass

    return product


@router.delete("/{product_id}")
async def delete_product(product_id: str, archive: bool = Query(True)):
    """删除或归档产品"""
    storage = get_product_storage()
    if archive:
        success = await storage.archive_product(product_id)
    else:
        success = await storage.delete_product(product_id)

    if not success:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")
    return {"success": True, "archived": archive}


@router.get("/{product_id}/events")
async def get_product_events(product_id: str, limit: int = Query(50)):
    """获取产品事件列表"""
    from app.core.event_bus import get_event_bus
    bus = get_event_bus()
    events = bus.get_recent_events(limit=limit, product_id=product_id)
    return {"events": [e.model_dump() for e in events], "total": len(events)}


@router.post("/{product_id}/compliance-check")
async def trigger_compliance_check(product_id: str, target_market: str = Query("欧盟")):
    """触发产品合规检查（通过 EventBus 发布事件，由 Worker 体系异步执行）"""
    storage = get_product_storage()
    product = storage.get_product(product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"产品 {product_id} 不存在")

    from app.core.event_bus import get_event_bus
    bus = get_event_bus()
    event = await bus.publish_raw({
        "type": "compliance:check_started",
        "source": "api",
        "product_id": product_id,
        "business_stage": product.business_stage,
        "target_market": target_market,
    })
    return {"event_id": event.id, "status": "published"}
