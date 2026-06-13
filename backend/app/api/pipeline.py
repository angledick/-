"""合规流水线API — /api/v1/pipeline

流水线健康度与阶段聚合查询。
流水线执行由 EventBus + Worker 体系驱动，不再由本模块编排。
"""

import yaml
from pathlib import Path
from typing import List, Dict, Any

from fastapi import APIRouter

from app.models.schemas import PipelineHealthResponse, PipelineStageStatus

router = APIRouter(prefix="/api/v1/pipeline", tags=["pipeline"])

# ── 阶段配置加载 ──────────────────────────────────

_STAGES_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "stages"


def _load_stage_configs() -> List[Dict[str, Any]]:
    """从 data/stages/stage_*.yaml 加载阶段配置。

    返回按 number 排序的阶段列表，每项包含 number 和 name。
    配置文件必须存在且可解析，否则抛出异常。
    """
    if not _STAGES_DIR.exists():
        raise FileNotFoundError(f"阶段配置目录缺失: {_STAGES_DIR}")

    stages = []
    for yaml_file in sorted(_STAGES_DIR.glob("stage_*.yaml")):
        data = yaml.safe_load(yaml_file.read_text(encoding="utf-8"))
        stage = data.get("stage", {})
        if isinstance(stage, dict) and "number" in stage:
            stages.append({
                "number": stage["number"],
                "name": stage.get("name", f"阶段{stage['number']}"),
            })
    return stages


_STAGE_CONFIGS = _load_stage_configs()

# 业务阶段号 → 产品生命周期枚举映射（延迟初始化，避免循环导入）
_LIFECYCLE_MAP: Dict[int, Any] = {}


def _get_lifecycle_map() -> Dict[int, Any]:
    if _LIFECYCLE_MAP:
        return _LIFECYCLE_MAP
    from app.models.schemas import ProductLifecycleStage
    _LIFECYCLE_MAP.update({
        1: ProductLifecycleStage.CONCEPT,
        2: ProductLifecycleStage.DESIGN,
        3: ProductLifecycleStage.SOURCING,
        4: ProductLifecycleStage.READY,
        5: ProductLifecycleStage.ACTIVE,
        6: ProductLifecycleStage.ACTIVE,
        7: ProductLifecycleStage.ACTIVE,
        8: ProductLifecycleStage.FULFILLING,
        9: ProductLifecycleStage.AFTERSALE,
        10: ProductLifecycleStage.END,
    })
    return _LIFECYCLE_MAP


# ── 健康度计算 ──────────────────────────────────


async def _compute_pipeline_health() -> PipelineHealthResponse:
    """计算流水线健康度（按产品生命周期阶段聚合）。"""
    from app.core.product_storage import get_product_storage

    storage = get_product_storage()
    lifecycle_map = _get_lifecycle_map()

    stages = []
    total_score = 0
    for cfg in _STAGE_CONFIGS:
        stage_num = cfg["number"]
        stage_name = cfg["name"]
        lifecycle = lifecycle_map.get(stage_num)
        products_in_stage = storage.list_products(lifecycle_stage=lifecycle, limit=1000)
        total = len(products_in_stage)
        passed = sum(1 for p in products_in_stage if p.compliance_status == "passed")
        risk = sum(1 for p in products_in_stage if p.risk_level in ("high", "critical"))

        pass_rate = passed / total if total > 0 else 1.0
        status = "healthy" if pass_rate > 0.8 else ("warning" if pass_rate > 0.5 else "critical")

        stages.append(PipelineStageStatus(
            stage_number=stage_num,
            stage_name=stage_name,
            pass_rate=pass_rate,
            total_products=total,
            passed_products=passed,
            risk_products=risk,
            status=status,
        ))
        total_score += pass_rate * 10

    overall = total_score / len(_STAGE_CONFIGS) if _STAGE_CONFIGS else 0

    return PipelineHealthResponse(
        overall_score=round(overall, 1),
        stages=stages,
    )


# ── API 端点 ──────────────────────────────────


@router.get("/health", response_model=PipelineHealthResponse)
async def get_pipeline_health():
    """获取合规流水线健康度"""
    return await _compute_pipeline_health()


@router.get("/stages")
async def get_pipeline_stages():
    """获取流水线各阶段聚合数据"""
    health = await _compute_pipeline_health()
    return {"stages": [s.model_dump() for s in health.stages]}


@router.get("/metrics")
async def get_pipeline_metrics():
    """获取流水线聚合指标"""
    health = await _compute_pipeline_health()
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
