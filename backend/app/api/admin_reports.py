"""
合规报表 API — 报表列表与导出。

端点:
  GET  /api/v1/reports                — 合规报表列表
  POST /api/v1/reports/{report_id}/export — 导出报表
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict

router = APIRouter(prefix="/api/v1/reports", tags=["reports"])


class ExportRequest(BaseModel):
    format: str = "json"          # json / csv / pdf / excel
    filters: Dict[str, Any] = {}


@router.get("", summary="合规报表列表")
async def list_reports():
    """生成可用报表清单"""
    return {
        "reports": [
            {"id": "compliance_overview", "name": "合规总览报告",
             "description": "所有产品合规状态汇总", "formats": ["json", "csv"]},
            {"id": "certification_status", "name": "认证状态报告",
             "description": "认证到期/有效/过期统计", "formats": ["json", "csv"]},
            {"id": "risk_assessment", "name": "风险评估报告",
             "description": "各风险等级产品分布与趋势", "formats": ["json", "csv"]},
            {"id": "regulation_changes", "name": "法规变更报告",
             "description": "近期法规变更及影响分析", "formats": ["json", "csv"]},
            {"id": "audit_trail", "name": "审计追踪报告",
             "description": "用户操作/审批/系统事件追踪", "formats": ["json", "csv"]},
            {"id": "pipeline_health", "name": "流水线健康报告",
             "description": "10阶段合规流水线健康度", "formats": ["json", "csv"]},
        ],
    }


@router.post("/{report_id}/export", summary="导出报表")
async def export_report(report_id: str, req: ExportRequest):
    """导出指定报表"""
    report_data = await _generate_report(report_id, req.filters)
    if report_data is None:
        raise HTTPException(status_code=404, detail="Report not found")

    if req.format == "json":
        return {"report_id": report_id, "format": "json", "data": report_data}
    elif req.format == "csv":
        import csv
        import io
        output = io.StringIO()
        if report_data and isinstance(report_data, list) and len(report_data) > 0:
            writer = csv.DictWriter(output, fieldnames=report_data[0].keys())
            writer.writeheader()
            writer.writerows(report_data)
        return {"report_id": report_id, "format": "csv", "content": output.getvalue()}
    else:
        return {"report_id": report_id, "format": req.format,
                "message": f"Export as {req.format} — data ready for conversion",
                "data": report_data}


async def _generate_report(report_id: str, filters: Dict) -> Any:
    """生成报表数据"""
    if report_id == "compliance_overview":
        try:
            from app.core.product_storage import get_product_storage
            storage = get_product_storage()
            products = storage.list_products()
            return [
                {"product_id": p.id, "name": p.name,
                 "lifecycle_stage": p.lifecycle_stage.value if hasattr(p.lifecycle_stage, 'value') else str(p.lifecycle_stage),
                 "risk_level": p.risk_level}
                for p in products
            ]
        except Exception:
            return [{"message": "Product storage not available"}]

    elif report_id == "certification_status":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            cert_data = await engine.check_cert_expiry()
            return cert_data.get("results", [])
        except Exception:
            return [{"message": "Certification data not available"}]

    elif report_id == "risk_assessment":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            metrics = await engine.aggregate_global_metrics()
            return [metrics]
        except Exception:
            return [{"message": "Risk data not available"}]

    elif report_id == "regulation_changes":
        return [{"message": "Regulation changes report", "recent_changes": []}]

    elif report_id == "audit_trail":
        try:
            from app.core.security_sandbox import get_security_sandbox
            sandbox = get_security_sandbox()
            events = sandbox.get_events(limit=100)
            return events
        except Exception:
            return [{"message": "Audit trail not available"}]

    elif report_id == "pipeline_health":
        try:
            from app.core.proactive_engine import get_proactive_engine
            engine = get_proactive_engine()
            metrics = await engine.aggregate_global_metrics()
            return [{"pipeline_health": metrics.get("system_health", "unknown")}]
        except Exception:
            return [{"message": "Pipeline data not available"}]

    return None
