"""LLM 调度管理 API — /api/v1/llm-dispatch

提供：
  LLM 网关状态查询（可用性/调用统计）
  手动触发各类 LLM 分析任务
  生命周期阶段推进决策
  风险情报处置决策
"""

import logging
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Query
from typing import Optional
from pydantic import BaseModel

from app.core.auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/llm-dispatch", tags=["llm-dispatch"])


# ─────────────────────────────────────────────────────────────────────────────
# 请求模型
# ─────────────────────────────────────────────────────────────────────────────

class LifecycleDispatchReq(BaseModel):
    product_id: str
    current_stage: str
    context: dict = {}


class RiskDispatchReq(BaseModel):
    intel_id: str


# ─────────────────────────────────────────────────────────────────────────────
# 状态与统计
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(current_user: dict = Depends(get_current_user)):
    """LLM 网关状态：可用性 + 各角色调用统计。"""
    from app.core.llm_gateway import get_llm_gateway, get_model_config
    gw = get_llm_gateway()

    roles = ["risk_analysis", "lifecycle_analysis", "dispatch"]
    status = {}
    for role in roles:
        cfg = get_model_config(role)
        status[role] = {
            "available":   cfg["available"],
            "provider":    cfg["provider"],
            "model":       cfg["model"],
            "base_url":    cfg["base_url"],
            "max_tokens":  cfg["max_tokens"],
            "temperature": cfg["temperature"],
        }

    return {
        "gateway_available": gw.available("risk_analysis"),
        "roles": status,
        "call_stats": gw.get_stats(),
    }


# ─────────────────────────────────────────────────────────────────────────────
# 手动触发 — 生命周期
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/lifecycle/scan")
async def trigger_lifecycle_scan(
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """手动触发生命周期批量 LLM 扫描（供应商/合同/报关单）。"""
    from app.core.llm_dispatcher import get_llm_dispatcher
    dispatcher = get_llm_dispatcher()

    async def _run():
        stats = await dispatcher.scan_lifecycle_assets()
        logger.info("[API] lifecycle_llm_scan 完成: %s", stats)

    background_tasks.add_task(_run)
    return {"status": "queued", "message": "生命周期 LLM 批量扫描已提交后台"}


@router.post("/lifecycle/dispatch")
async def dispatch_lifecycle_stage(
    req: LifecycleDispatchReq,
    current_user: dict = Depends(get_current_user),
):
    """对指定产品的生命周期阶段进行 LLM 推进决策。"""
    from app.core.llm_dispatcher import get_llm_dispatcher
    from app.core.product_storage import get_product_storage

    storage = get_product_storage()
    product = storage.get_product(req.product_id)
    if not product:
        raise HTTPException(404, f"产品 {req.product_id} 不存在")

    dispatcher = get_llm_dispatcher()
    result = await dispatcher.dispatch_lifecycle_stage(
        product=product.model_dump() if hasattr(product, 'model_dump') else dict(product),
        current_stage=req.current_stage,
        context=req.context,
    )
    return result


@router.post("/lifecycle/supplier/{supplier_id}")
async def dispatch_supplier_review(
    supplier_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """手动触发单个供应商 LLM 资质审核。"""
    from app.storage.supplier_store import get_supplier, save_ai_review
    s = get_supplier(supplier_id)
    if not s:
        raise HTTPException(404, f"供应商 {supplier_id} 不存在")

    async def _run():
        from app.core.lifecycle_analyzer import analyze_supplier
        result = await analyze_supplier(s)
        save_ai_review(supplier_id, result)
        try:
            from app.services.ws_manager import ws_manager
            await ws_manager.broadcast({
                "type": "supplier_reviewed",
                "payload": {"supplier_id": supplier_id, "name": s["name"],
                            "risk_level": result.get("risk_level"), "score": result.get("score")},
            })
        except Exception:
            pass

    background_tasks.add_task(_run)
    return {"status": "queued", "supplier_id": supplier_id,
            "message": "LLM 资质审核已提交，结果将通过 WebSocket 推送"}


@router.post("/lifecycle/contract/{contract_id}")
async def dispatch_contract_review(
    contract_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """手动触发合同 LLM 合规审查。"""
    from app.storage.contract_store import get_contract, save_compliance_review
    c = get_contract(contract_id)
    if not c:
        raise HTTPException(404, f"合同 {contract_id} 不存在")

    async def _run():
        from app.core.lifecycle_analyzer import analyze_contract
        result = await analyze_contract(c)
        save_compliance_review(contract_id, result.get("issues", []), result.get("score", 0))
        try:
            from app.services.ws_manager import ws_manager
            await ws_manager.broadcast({
                "type": "contract_reviewed",
                "payload": {"contract_id": contract_id, "title": c["title"],
                            "score": result.get("score"), "issues": len(result.get("issues", []))},
            })
        except Exception:
            pass

    background_tasks.add_task(_run)
    return {"status": "queued", "contract_id": contract_id,
            "message": "LLM 合规审查已提交，结果将通过 WebSocket 推送"}


# ─────────────────────────────────────────────────────────────────────────────
# 手动触发 — 风险情报
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/risk/dispatch")
async def trigger_risk_dispatch(
    background_tasks: BackgroundTasks,
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    """手动触发风险情报 LLM 批量决策调度。"""
    from app.core.llm_dispatcher import get_llm_dispatcher

    async def _run():
        dispatcher = get_llm_dispatcher()
        result = await dispatcher.batch_dispatch_risk_intel(limit=limit)
        logger.info("[API] risk_intel_dispatch 完成: %s", result)

    background_tasks.add_task(_run)
    return {"status": "queued", "limit": limit,
            "message": f"风险情报 LLM 决策调度已提交，处理最多 {limit} 条"}


@router.post("/risk/dispatch-item")
async def dispatch_single_risk_item(
    req: RiskDispatchReq,
    current_user: dict = Depends(get_current_user),
):
    """对单条风险情报进行 LLM 处置决策（同步返回）。"""
    from app.core.llm_dispatcher import get_llm_dispatcher
    from app.storage.risk_intel_store import get_item

    item = get_item(req.intel_id)
    if not item:
        raise HTTPException(404, f"情报 {req.intel_id} 不存在")

    dispatcher = get_llm_dispatcher()
    result = await dispatcher.dispatch_risk_intel(item)
    return {"intel_id": req.intel_id, "decision": result}
