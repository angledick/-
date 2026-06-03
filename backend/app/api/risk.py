"""风险/指标/预警 API 路由。

所有端点前缀: /api/v1/risk/..., /api/v1/metrics/..., /api/v1/prompts/...
"""

from fastapi import APIRouter, Query, Path, HTTPException
from typing import Optional
from app.core.risk_alert import (
    create_alert,
    dismiss_alert,
    get_alerts,
    get_unread_count,
    get_last_scan_time,
    save_last_scan_time,
)
from app.core.market_monitor import MarketMonitor
from app.core.metrics import get_dashboard
from app.services.prompt_loader import reload_all, list_prompts

router = APIRouter(prefix="/api/v1", tags=["risk"])


# ── 风险预警 ─────────────────────────────────────

@router.get("/risk/alerts", summary="预警列表")
async def list_alerts(
    user_id: str = Query("default", description="用户ID"),
    alert_type: Optional[str] = Query(None, description="筛选类型"),
    severity: Optional[str] = Query(None, description="筛选严重度"),
    page: int = Query(1, ge=1, description="页码"),
    size: int = Query(20, ge=1, le=100, description="每页条数"),
):
    """获取预警列表，支持分页和筛选。"""
    return {
        "alerts": get_alerts(user_id, alert_type, severity, page, size),
        "page": page,
        "size": size,
    }


@router.get("/risk/alerts/unread-count", summary="未读预警数")
async def unread_count(
    user_id: str = Query("default", description="用户ID"),
):
    """获取未读预警数。"""
    return {"unread_count": get_unread_count(user_id)}


@router.post("/risk/alerts/{alert_id}/dismiss", summary="忽略预警")
async def dismiss(
    alert_id: str = Path(..., description="预警ID"),
    user_id: str = Query("default", description="用户ID"),
):
    """标记预警为已忽略。"""
    success = dismiss_alert(alert_id, user_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Alert {alert_id} not found")
    return {"status": "ok", "alert_id": alert_id}


# ── 市场扫描 ─────────────────────────────────────

@router.post("/risk/scan", summary="手动触发市场扫描")
async def trigger_scan(
    user_id: str = Query("default", description="用户ID"),
):
    """手动触发一次完整的市场扫描（AstraAssistant 联网搜索 → 影响分析 → 预警）。"""
    from app.services.ws_manager import ws_manager

    monitor = MarketMonitor()

    # 通知前端扫描开始
    await ws_manager.send_scan_update(user_id, "scanning")

    try:
        # AstraAssistant 联网搜索市场变更
        events = await monitor.poll_markets()
        alerts_created = []
        for event in events:
            if not event.get("has_change"):
                continue
            impacts = await monitor.analyze_impact(event)
            alert = create_alert(
                alert_type="regulation_change" if event.get("severity") in ("critical", "high") else "market_hotspot",
                severity=event.get("severity", "medium"),
                title=f"[{event.get('market', '?').upper()}] {event.get('summary', '')[:80]}",
                description=event.get("summary", ""),
                affected_markets=[event.get("market", "")],
                affected_products=[i.get("product_id", "") for i in impacts if i.get("product_id")],
                source=event.get("source", "Astra Market Monitor"),
                source_url=event.get("source_url", ""),
                user_ids=[user_id],
            )
            alerts_created.append(alert)
            await ws_manager.send_alert(user_id, alert)

        save_last_scan_time(user_id)
        await ws_manager.send_scan_update(user_id, "completed", f"发现 {len(alerts_created)} 条预警")

        return {
            "status": "completed",
            "alerts_created": len(alerts_created),
            "events_found": len(events),
        }
    except Exception as e:
        await ws_manager.send_scan_update(user_id, "error", str(e))
        raise HTTPException(status_code=500, detail=f"Scan failed: {e}")


@router.get("/risk/market-status", summary="市场监控状态")
async def market_status(
    user_id: str = Query("default", description="用户ID"),
):
    """获取各市场最新扫描状态。"""
    last_scan = get_last_scan_time(user_id)
    alerts = get_alerts(user_id, size=1000)
    # 聚合每个市场的预警数
    market_counts: dict[str, int] = {}
    for a in alerts:
        for m in a.get("affected_markets", []):
            market_counts[m] = market_counts.get(m, 0) + 1
    return {
        "last_scan": last_scan or "never",
        "active_alerts": len([a for a in alerts if not a.get("dismissed", False)]),
        "markets": [{"code": m, "alerts": c} for m, c in sorted(market_counts.items())],
    }


# ── 指标仪表盘 ───────────────────────────────────

@router.get("/metrics/dashboard", summary="用户仪表盘")
async def dashboard(
    user_id: str = Query("default", description="用户ID"),
):
    """获取用户合规仪表盘数据。"""
    return get_dashboard(user_id)


# ── Prompt 管理 ──────────────────────────────────

@router.post("/prompts/reload", summary="热加载 Prompt 模板")
async def reload_prompts():
    """热加载所有 prompt 模板（微调 YAML 后调用）。
    
    调用后，所有使用 prompt_loader 的组件将使用新 prompt。
    """
    reload_all()
    prompts = list_prompts()
    return {
        "status": "ok",
        "reloaded": len(prompts),
        "prompts": prompts,
    }
