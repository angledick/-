"""物流管理 API — /api/v1/logistics"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from typing import Optional
from pydantic import BaseModel, Field

from app.core.auth import get_current_user

router = APIRouter(prefix="/api/v1/logistics", tags=["logistics"])


class ShipmentCreate(BaseModel):
    product_id: str
    carrier: str = Field(..., description="dhl|fedex|ups|sf_express|ems|cainiao")
    tracking_number: str = ""
    service_type: str = "国际快件"
    incoterm: str = "FOB"
    dest_country: str
    origin_country: str = "CN"
    order_id: str = ""
    insured: bool = False
    insured_value: float = 0.0
    weight_kg: float = 0.0
    freight_cost: float = 0.0
    freight_currency: str = "USD"
    customs_declaration_id: Optional[str] = None
    metadata: dict = {}


class TrackingRefresh(BaseModel):
    force: bool = False


# ── 端点 ──────────────────────────────────────────────────────────────────────

@router.get("/carriers")
async def list_carriers(current_user: dict = Depends(get_current_user)):
    from app.storage.logistics_store import list_carriers as _lc
    return _lc()


@router.post("/shipments", status_code=201)
async def create_shipment(req: ShipmentCreate, current_user: dict = Depends(get_current_user)):
    from app.storage.logistics_store import create_order as _co
    order = _co(req.model_dump())
    _publish("logistics:picked_up", {"logistics_id": order["id"],
                                      "product_id": order["product_id"],
                                      "carrier": order["carrier"],
                                      "tracking": order.get("tracking_number", "")})
    return order


@router.get("/shipments")
async def list_shipments(
    product_id: Optional[str] = None,
    status: Optional[str] = None,
    carrier: Optional[str] = None,
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
):
    from app.storage.logistics_store import list_orders as _lo
    return _lo(product_id=product_id, status=status, carrier=carrier, limit=limit)


@router.get("/shipments/{shipment_id}")
async def get_shipment(shipment_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.logistics_store import get_order as _go
    o = _go(shipment_id)
    if not o:
        raise HTTPException(404, f"物流单 {shipment_id} 不存在")
    return o


@router.get("/shipments/{shipment_id}/tracking")
async def get_tracking(shipment_id: str, current_user: dict = Depends(get_current_user)):
    from app.storage.logistics_store import get_order as _go, get_tracking_events
    o = _go(shipment_id)
    if not o:
        raise HTTPException(404, f"物流单 {shipment_id} 不存在")
    events = get_tracking_events(shipment_id)
    return {
        "shipment_id": shipment_id,
        "tracking_number": o.get("tracking_number"),
        "carrier": o["carrier"],
        "status": o["status"],
        "estimated_delivery": o.get("estimated_delivery"),
        "events": events,
        "tracking_url": _tracking_url(o["carrier"], o.get("tracking_number", "")),
    }


@router.post("/shipments/{shipment_id}/refresh")
async def refresh_tracking(
    shipment_id: str,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """调 17TRACK API 刷新物流轨迹（后台执行）。"""
    from app.storage.logistics_store import get_order as _go
    o = _go(shipment_id)
    if not o:
        raise HTTPException(404, f"物流单 {shipment_id} 不存在")

    async def _refresh():
        await _fetch_17track(shipment_id, o.get("tracking_number", ""), o["carrier"])

    background_tasks.add_task(_refresh)
    return {"status": "queued", "shipment_id": shipment_id}


@router.post("/webhook/17track")
async def webhook_17track(payload: dict):
    """接收 17TRACK Webhook 推送。"""
    try:
        for item in payload.get("data", {}).get("accepted", []):
            num = item.get("number", "")
            events_raw = item.get("track", {}).get("z2", []) or []
            from app.storage.logistics_store import get_order, save_tracking_result
            import sqlite3
            db_path = __import__('pathlib').Path(__file__).parent.parent.parent / "data" / "sessions.db"
            conn = sqlite3.connect(str(db_path))
            row = conn.execute("SELECT id FROM logistics_orders WHERE tracking_number=?", (num,)).fetchone()
            conn.close()
            if row:
                oid = row[0]
                events = [{"timestamp": e.get("a", ""), "location": e.get("c", ""),
                           "description": e.get("z", ""), "status_code": e.get("d", "")}
                          for e in events_raw]
                status = _map_17track_status(item.get("track", {}).get("e"))
                save_tracking_result(oid, events, status)
    except Exception:
        pass
    return {"received": True}


@router.post("/webhook/aftership")
async def webhook_aftership(payload: dict):
    """接收 AfterShip Webhook 推送。"""
    try:
        msg = payload.get("msg", {})
        num = msg.get("tracking_number", "")
        checkpoints = msg.get("checkpoints", [])
        import sqlite3
        db_path = __import__('pathlib').Path(__file__).parent.parent.parent / "data" / "sessions.db"
        conn = sqlite3.connect(str(db_path))
        row = conn.execute("SELECT id FROM logistics_orders WHERE tracking_number=?", (num,)).fetchone()
        conn.close()
        if row:
            from app.storage.logistics_store import save_tracking_result
            events = [{"timestamp": cp.get("checkpoint_time", ""),
                       "location": f"{cp.get('city','')} {cp.get('country_iso3','')}".strip(),
                       "description": cp.get("message", ""),
                       "status_code": cp.get("subtag", "")}
                      for cp in checkpoints]
            tag = msg.get("tag", "")
            status = _map_aftership_status(tag)
            save_tracking_result(row[0], events, status)
    except Exception:
        pass
    return {"received": True}


# ── 辅助 ─────────────────────────────────────────────────────────────────────

def _tracking_url(carrier: str, num: str) -> str:
    from app.storage.logistics_store import CARRIERS
    tmpl = CARRIERS.get(carrier, {}).get("tracking_url", "")
    return tmpl.replace("{num}", num) if tmpl and num else ""


def _map_17track_status(code: Optional[str]) -> str:
    mapping = {"0": "pending", "10": "in_transit", "20": "out_for_delivery",
               "30": "delivered", "35": "exception", "40": "customs_import"}
    return mapping.get(str(code or ""), "in_transit")


def _map_aftership_status(tag: str) -> str:
    mapping = {"Pending": "pending", "InTransit": "in_transit",
               "OutForDelivery": "out_for_delivery", "Delivered": "delivered",
               "Exception": "exception", "AttemptFail": "exception"}
    return mapping.get(tag, "in_transit")


async def _fetch_17track(shipment_id: str, tracking_num: str, carrier: str):
    """实际调用 17TRACK API 获取轨迹。"""
    if not tracking_num:
        return
    import os
    api_key = os.environ.get("TRACK17_API_KEY", "")
    if not api_key:
        return  # 未配置 Key，跳过
    try:
        import httpx
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                "https://api.17track.net/track/v2.2/gettrackinfo",
                headers={"17token": api_key, "Content-Type": "application/json"},
                json=[{"number": tracking_num}],
            )
            if resp.status_code == 200:
                data = resp.json()
                for item in data.get("data", {}).get("accepted", []):
                    events = [{"timestamp": e.get("a", ""), "location": e.get("c", ""),
                               "description": e.get("z", "")}
                              for e in (item.get("track", {}).get("z2") or [])]
                    status = _map_17track_status(item.get("track", {}).get("e"))
                    from app.storage.logistics_store import save_tracking_result
                    save_tracking_result(shipment_id, events, status)
    except Exception:
        pass


def _publish(event_type: str, data: dict):
    try:
        import asyncio
        from app.core.event_bus import get_event_bus
        bus = get_event_bus()
        loop = asyncio.get_event_loop()
        if loop.is_running():
            asyncio.create_task(bus.publish_raw({"type": event_type, "source": "logistics_api",
                                                  "severity": "medium", "data": data}))
    except Exception:
        pass
