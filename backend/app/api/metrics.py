"""
指标监控API — 产品指标 + 全局指标 + 自定义指标 + 跨产品洞察。

端点:
  GET  /api/v1/metrics/products/{product_id}  — 产品指标
  GET  /api/v1/metrics/global                 — 全局指标
  GET  /api/v1/metrics/alerts                 — 指标预警
  GET  /api/v1/metrics/builtin_templates      — 内置指标模板
  GET  /api/v1/metrics/custom                 — 自定义指标列表
  POST /api/v1/metrics/custom                 — 创建自定义指标
  PUT  /api/v1/metrics/custom/{metric_id}     — 更新自定义指标
  DELETE /api/v1/metrics/custom/{metric_id}   — 删除自定义指标
  GET  /api/v1/metrics/cross_product          — 跨产品聚合洞察

参考: 指南§6.6 个性指标, §6.11.3 产品指标池, §6.12.4 全局指标
"""

import json
from pathlib import Path
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

from app.config import settings

DATA_DIR = Path(settings.data_dir)

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


# ── 请求模型 ──────────────────────────────────

class CustomMetricCreate(BaseModel):
    name: str
    key: str
    scope: Dict[str, Any] = {}
    formula: str = ""
    threshold_warning: float = 0
    threshold_critical: float = 0
    notify_on_warning: bool = True
    notify_on_critical: bool = True
    channels: List[str] = ["dashboard"]


# ── 产品指标 ──────────────────────────────────

@router.get("/products/{product_id}", summary="产品指标")
async def get_product_metrics(product_id: str):
    """获取产品指标池（通用指标 + 个性化指标）"""
    metrics_path = DATA_DIR / "products" / product_id / "metrics" / "metrics.json"
    history_path = DATA_DIR / "products" / product_id / "metrics" / "history.json"

    if not metrics_path.exists():
        return {
            "product_id": product_id,
            "metrics": {},
            "custom_metrics": {},
            "snapshot_time": None,
            "history_available": history_path.exists(),
        }

    data = json.loads(metrics_path.read_text(encoding="utf-8"))
    return {
        "product_id": product_id,
        "metrics": data.get("metrics", {}),
        "custom_metrics": data.get("custom_metrics", {}),
        "snapshot_time": data.get("snapshot_time"),
        "history_available": history_path.exists(),
    }


@router.get("/products/{product_id}/history", summary="产品指标历史")
async def get_product_metrics_history(
    product_id: str,
    days: int = Query(30, ge=1, le=90, description="历史天数"),
):
    """获取产品指标历史趋势（最多90天）"""
    history_path = DATA_DIR / "products" / product_id / "metrics" / "history.json"

    if not history_path.exists():
        return {"product_id": product_id, "history": []}

    data = json.loads(history_path.read_text(encoding="utf-8"))
    history = data if isinstance(data, list) else data.get("history", [])

    # 按天数截断
    return {"product_id": product_id, "history": history[-days:]}


# ── 全局指标 ──────────────────────────────────

@router.get("/global", summary="全局指标")
async def get_global_metrics():
    """获取全局聚合指标"""
    agg_path = DATA_DIR / "global" / "metrics" / "agg_metrics.json"

    if not agg_path.exists():
        # 触发一次聚合
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            result = await engine.aggregate_global_metrics()
            return result
        except Exception:
            return {"metrics": {}, "aggregated_at": None}

    data = json.loads(agg_path.read_text(encoding="utf-8"))
    return data


@router.get("/alerts", summary="指标预警")
async def get_metric_alerts(
    severity: Optional[str] = Query(None, description="严重级别过滤"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取指标预警列表"""
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        alerts = engine.get_alert_history(limit=limit)

        if severity:
            alerts = [
                a for a in alerts
                if any(
                    item.get("severity") == severity
                    for item in a.get("warnings", []) + a.get("expired", [])
                ) or a.get("severity") == severity
            ]

        return {"alerts": alerts, "total": len(alerts)}
    except Exception as e:
        return {"alerts": [], "total": 0, "error": str(e)}


@router.get("/builtin_templates", summary="内置指标模板")
async def get_builtin_metric_templates():
    """获取8个内置指标模板（对齐指南§6.6.1）"""
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        return {"templates": engine.get_builtin_metrics()}
    except Exception:
        return {"templates": {}}


# ── 自定义指标 ──────────────────────────────────

@router.get("/custom", summary="自定义指标列表")
async def list_custom_metrics():
    """获取用户自定义指标"""
    custom_path = DATA_DIR / "global" / "metrics" / "custom_metrics.json"

    if not custom_path.exists():
        return {"metrics": []}

    data = json.loads(custom_path.read_text(encoding="utf-8"))
    return {"metrics": data.get("metrics", [])}


@router.post("/custom", summary="创建自定义指标")
async def create_custom_metric(req: CustomMetricCreate):
    """创建自定义指标"""
    custom_path = DATA_DIR / "global" / "metrics" / "custom_metrics.json"
    custom_path.parent.mkdir(parents=True, exist_ok=True)

    data = {"metrics": []}
    if custom_path.exists():
        data = json.loads(custom_path.read_text(encoding="utf-8"))

    # 检查key唯一性
    for m in data.get("metrics", []):
        if m.get("key") == req.key:
            raise HTTPException(status_code=409, detail=f"Metric key {req.key} already exists")

    metric = {
        "id": f"metric_{req.key}",
        "name": req.name,
        "key": req.key,
        "scope": req.scope,
        "formula": req.formula,
        "threshold_warning": req.threshold_warning,
        "threshold_critical": req.threshold_critical,
        "notify_on_warning": req.notify_on_warning,
        "notify_on_critical": req.notify_on_critical,
        "channels": req.channels,
    }

    data["metrics"].append(metric)
    custom_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    return metric


@router.put("/custom/{metric_id}", summary="更新自定义指标")
async def update_custom_metric(metric_id: str, req: CustomMetricCreate):
    """更新自定义指标"""
    custom_path = DATA_DIR / "global" / "metrics" / "custom_metrics.json"

    if not custom_path.exists():
        raise HTTPException(status_code=404, detail="No custom metrics found")

    data = json.loads(custom_path.read_text(encoding="utf-8"))
    updated = False

    for i, m in enumerate(data.get("metrics", [])):
        if m.get("id") == metric_id:
            data["metrics"][i] = {
                **m,
                "name": req.name,
                "scope": req.scope,
                "formula": req.formula,
                "threshold_warning": req.threshold_warning,
                "threshold_critical": req.threshold_critical,
                "notify_on_warning": req.notify_on_warning,
                "notify_on_critical": req.notify_on_critical,
                "channels": req.channels,
            }
            updated = True
            break

    if not updated:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")

    custom_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return data["metrics"][next(i for i, m in enumerate(data["metrics"]) if m["id"] == metric_id)]


@router.delete("/custom/{metric_id}", summary="删除自定义指标")
async def delete_custom_metric(metric_id: str):
    """删除自定义指标"""
    custom_path = DATA_DIR / "global" / "metrics" / "custom_metrics.json"

    if not custom_path.exists():
        raise HTTPException(status_code=404, detail="No custom metrics found")

    data = json.loads(custom_path.read_text(encoding="utf-8"))
    original_count = len(data.get("metrics", []))
    data["metrics"] = [m for m in data.get("metrics", []) if m.get("id") != metric_id]

    if len(data["metrics"]) == original_count:
        raise HTTPException(status_code=404, detail=f"Metric {metric_id} not found")

    custom_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"deleted": metric_id}


# ── 跨产品洞察 ──────────────────────────────────

@router.get("/cross_product", summary="跨产品聚合洞察")
async def get_cross_product_insights():
    """获取跨产品聚合洞察（按市场/品类/风险等维度）"""
    try:
        from app.core.proactive_engine import get_proactive_engine
        engine = get_proactive_engine()
        insights = await engine.generate_cross_product_insights()
        return {"insights": insights, "total": len(insights)}
    except Exception as e:
        return {"insights": [], "total": 0, "error": str(e)}
