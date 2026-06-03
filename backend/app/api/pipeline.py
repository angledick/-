"""合规流水线API — /api/v1/pipeline"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional, List

from app.models.schemas import PipelineHealthResponse
from app.core.compliance_flow import get_compliance_flow

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])


@router.get("/health", response_model=PipelineHealthResponse)
async def get_pipeline_health():
    """获取合规流水线健康度"""
    flow = get_compliance_flow()
    return await flow.get_pipeline_health()


@router.get("/stages")
async def get_pipeline_stages():
    """获取流水线各阶段聚合数据"""
    flow = get_compliance_flow()
    health = await flow.get_pipeline_health()
    return {"stages": [s.model_dump() for s in health.stages]}


@router.get("/metrics")
async def get_pipeline_metrics():
    """获取流水线聚合指标"""
    flow = get_compliance_flow()
    health = await flow.get_pipeline_health()
    stages = health.stages
    total_products = sum(s.total_products for s in stages)
    total_passed = sum(s.passed_products for s in stages)
    total_risk = sum(s.risk_products for s in stages)
    avg_pass_rate = (sum(s.pass_rate for s in stages) / len(stages)) if stages else 0
    return {
        "overall_score": health.overall_score,
        "total_products": total_products,
        "total_passed": total_passed,
        "total_risk": total_risk,
        "avg_pass_rate": round(avg_pass_rate, 2),
        "stage_count": len(stages),
        "healthy_stages": sum(1 for s in stages if s.status == "healthy"),
        "warning_stages": sum(1 for s in stages if s.status == "warning"),
        "critical_stages": sum(1 for s in stages if s.status == "critical"),
    }


@router.get("/mode")
async def get_pipeline_mode():
    """获取流水线模式"""
    flow = get_compliance_flow()
    return {"mode": flow._pipeline_mode}


@router.put("/mode")
async def set_pipeline_mode(mode: str):
    """设置流水线模式 (6step/5step)"""
    if mode not in ("5step", "6step"):
        raise HTTPException(status_code=400, detail="模式必须为 5step 或 6step")
    flow = get_compliance_flow()
    flow._pipeline_mode = mode
    return {"mode": mode}


@router.get("/interactions")
async def list_pending_interactions():
    """获取待处理的交互请求"""
    flow = get_compliance_flow()
    interactions = []
    for iid, data in flow._pending_interactions.items():
        interactions.append({
            "interaction_id": iid,
            "recommendations": data.get("recommendations", []),
            "created_at": data.get("created_at", ""),
        })
    return {"interactions": interactions, "total": len(interactions)}


@router.post("/interactions/{interaction_id}")
async def handle_interaction(
    interaction_id: str,
    action: str = Query(..., description="用户选择的操作"),
    confirmed: bool = Query(True, description="是否确认执行"),
):
    """处理用户交互响应"""
    flow = get_compliance_flow()
    try:
        result = await flow.handle_user_action(interaction_id, action, confirmed)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
