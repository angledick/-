"""物流管理 API — /api/v1/logistics"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends, Request
from typing import Optional
from pydantic import BaseModel, Field
import hashlib, hmac, os
from pathlib import Path

from app.core.auth import get_current_user

_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _get_env(key: str) -> str:
    """从 os.environ 或 .env 文件读取配置。"""
    v = os.environ.get(key, "")
    if v:
        return v
    if _ENV_FILE.exists():
        for line in _ENV_FILE.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("#") or "=" not in line:
                continue
            k, _, val = line.partition("=")
            if k.strip() == key:
                return val.strip().strip('"').strip("'")
    return ""


def _verify_hmac(body: bytes, signature: str, secret: str) -> bool:
    """HMAC-SHA256 签名验证。"""
    if not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected.lower(), signature.lower())


def _hash_body(body: bytes) -> str:
    """生成 body 的 SHA256 短哈希（用于去重）。"""
    return hashlib.sha256(body).hexdigest()[:16]

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
async def webhook_17track(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """17TRACK Webhook — 安全加固版。

    安全措施：
    - HMAC-SHA256 签名验证（可选，需配置 TRACK17_WEBHOOK_SECRET）
    - 幂等去重（X-17Track-Event-Id 头部）
    - 异步处理（快速响应，防 Webhook 超时重试）
    - 结构化日志（不再静默吞掉异常）
    """
    import logging
    logger = logging.getLogger("webhook.17track")

    raw_body = await request.body()

    # ── 签名验证（有 secret 时强制验证）───────────────────────────────────
    secret = _get_env("TRACK17_WEBHOOK_SECRET")
    if secret:
        sig = request.headers.get("X-17Track-Signature", "")
        if not _verify_hmac(raw_body, sig, secret):
            logger.warning("17TRACK Webhook 签名验证失败，IP=%s",
                           request.client.host if request.client else "unknown")
            raise HTTPException(401, "Webhook 签名验证失败")

    # ── 解析 JSON ───────────────────────────────────────────────────────────
    try:
        import json as _json
        payload = _json.loads(raw_body)
    except Exception:
        raise HTTPException(400, "无效 JSON")

    # ── 幂等检查 ────────────────────────────────────────────────────────────
    event_id = request.headers.get("X-17Track-Event-Id", "") or \
               f"17track_{payload.get('event','')}_{_hash_body(raw_body)}"
    from app.storage.order_store import is_webhook_processed, mark_webhook_processed
    if is_webhook_processed(event_id):
        logger.debug("17TRACK Webhook 重复，已忽略 event_id=%s", event_id)
        return {"received": True, "skipped": True}

    # ── 异步处理 ────────────────────────────────────────────────────────────
    mark_webhook_processed(event_id, "17track", _hash_body(raw_body))
    background_tasks.add_task(_process_17track_payload, payload)

    return {"received": True}


async def _process_17track_payload(payload: dict):
    """17TRACK Webhook 后台处理（签名验证后在此处理）。"""
    import logging, sqlite3
    from pathlib import Path
    logger = logging.getLogger("webhook.17track")

    try:
        from app.storage.logistics_store import save_tracking_result
        db_path = Path(__file__).parent.parent.parent / "data" / "sessions.db"

        for item in payload.get("data", {}).get("accepted", []):
            num = item.get("number", "")
            if not num:
                continue
            events_raw = item.get("track", {}).get("z2", []) or []

            # 通过运单号查找物流单
            conn = sqlite3.connect(str(db_path))
            row = conn.execute(
                "SELECT id FROM logistics_orders WHERE tracking_number=?", (num,)
            ).fetchone()
            conn.close()

            if not row:
                logger.debug("17TRACK 推送运单号 %s 未匹配到物流单", num)
                continue

            oid = row[0]
            events = [
                {"timestamp": e.get("a", ""), "location": e.get("c", ""),
                 "description": e.get("z", ""), "status_code": e.get("d", "")}
                for e in events_raw
            ]
            status = _map_17track_status(item.get("track", {}).get("e"))
            save_tracking_result(oid, events, status)

            logger.info("17TRACK 轨迹更新: tracking=%s status=%s events=%d",
                        num, status, len(events))

            # WS 推送
            try:
                from app.services.ws_manager import ws_manager
                latest = events[0] if events else {}
                await ws_manager.broadcast({
                    "type": "logistics_updated",
                    "payload": {
                        "logistics_id": oid,
                        "tracking_number": num,
                        "status": status,
                        "latest_event": {
                            "timestamp": latest.get("timestamp", ""),
                            "location": latest.get("location", ""),
                            "description": latest.get("description", ""),
                        },
                    },
                })
            except Exception:
                pass

    except Exception as e:
        logging.getLogger("webhook.17track").error(
            "17TRACK Webhook 处理失败: %s", e, exc_info=True
        )


@router.post("/webhook/aftership")
async def webhook_aftership(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """AfterShip Webhook — 安全加固版。"""
    import logging, json as _json
    logger = logging.getLogger("webhook.aftership")

    raw_body = await request.body()

    # ── HMAC 签名验证 ────────────────────────────────────────────────────────
    secret = _get_env("AFTERSHIP_HMAC_SECRET")
    if secret:
        sig = request.headers.get("aftership-hmac-sha256", "")
        if not _verify_hmac(raw_body, sig, secret):
            logger.warning("AfterShip Webhook 签名验证失败")
            raise HTTPException(401, "Webhook 签名验证失败")

    try:
        payload = _json.loads(raw_body)
    except Exception:
        raise HTTPException(400, "无效 JSON")

    # ── 幂等检查 ────────────────────────────────────────────────────────────
    event_id = payload.get("id") or f"aftership_{_hash_body(raw_body)}"
    from app.storage.order_store import is_webhook_processed, mark_webhook_processed
    if is_webhook_processed(event_id):
        return {"received": True, "skipped": True}

    mark_webhook_processed(event_id, "aftership", _hash_body(raw_body))
    background_tasks.add_task(_process_aftership_payload, payload)
    return {"received": True}


async def _process_aftership_payload(payload: dict):
    """AfterShip Webhook 后台处理。"""
    import logging, sqlite3
    from pathlib import Path
    logger = logging.getLogger("webhook.aftership")

    try:
        msg = payload.get("msg", {})
        num = msg.get("tracking_number", "")
        if not num:
            return
        checkpoints = msg.get("checkpoints", [])
        db_path = Path(__file__).parent.parent.parent / "data" / "sessions.db"
        conn = sqlite3.connect(str(db_path))
        row = conn.execute(
            "SELECT id FROM logistics_orders WHERE tracking_number=?", (num,)
        ).fetchone()
        conn.close()
        if not row:
            return
        from app.storage.logistics_store import save_tracking_result
        events = [
            {"timestamp": cp.get("checkpoint_time", ""),
             "location": f"{cp.get('city','')} {cp.get('country_iso3','')}".strip(),
             "description": cp.get("message", ""),
             "status_code": cp.get("subtag", "")}
            for cp in checkpoints
        ]
        tag = msg.get("tag", "")
        status = _map_aftership_status(tag)
        save_tracking_result(row[0], events, status)
        logger.info("AfterShip 轨迹更新: tracking=%s status=%s", num, status)
        # WS 推送
        try:
            from app.services.ws_manager import ws_manager
            latest = events[0] if events else {}
            await ws_manager.broadcast({"type": "logistics_updated",
                                         "payload": {"logistics_id": row[0],
                                                     "tracking_number": num,
                                                     "status": status,
                                                     "latest_event": latest}})
        except Exception:
            pass
    except Exception as e:
        logging.getLogger("webhook.aftership").error("AfterShip Webhook 失败: %s", e, exc_info=True)


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
